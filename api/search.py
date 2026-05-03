from __future__ import annotations

import re
import time
from typing import Any

from django.conf import settings
from django.db.models import Q

from .medicine_search_enrichment import parse_aliases
from .models import Medicine

_SEARCH_CACHE: dict[str, Any] = {
    "loaded_at": 0.0,
    "ttl_seconds": 300,
    "items": [],
    "by_id": {},
}


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", (query or "").strip()).lower()


def _get_setting(name: str, default: Any) -> Any:
    return getattr(settings, name, default)


def _load_medicine_rows() -> list[dict[str, Any]]:
    now = time.time()
    ttl = int(_get_setting("SEARCH_MEDICINE_CACHE_TTL_SECONDS", _SEARCH_CACHE["ttl_seconds"]))
    cached_items = _SEARCH_CACHE["items"]
    current_count = Medicine.objects.count()
    if cached_items and (now - _SEARCH_CACHE["loaded_at"]) < ttl and len(cached_items) == current_count:
        return cached_items

    rows_raw = list(
        Medicine.objects.values_list(
            "id",
            "trade_name",
            "active_ingredient",
            "drug_class",
            "search_aliases",
            "trade_name_norm",
            "active_ingredient_norm",
            "drug_class_norm",
        )
    )
    rows: list[dict[str, Any]] = []
    by_id: dict[int, dict[str, Any]] = {}
    for item in rows_raw:
        (
            medicine_id,
            trade_name,
            active_ingredient,
            drug_class,
            raw_aliases,
            trade_name_norm,
            active_ingredient_norm,
            drug_class_norm,
        ) = item
        aliases = _parse_aliases_for_search(raw_aliases)
        row = {
            "id": medicine_id,
            "aliases": aliases,
            "trade_name_norm": normalize_query(trade_name_norm or trade_name),
            "active_ingredient_norm": normalize_query(active_ingredient_norm or active_ingredient),
            "drug_class_norm": normalize_query(drug_class_norm or drug_class),
        }
        rows.append(row)
        by_id[medicine_id] = row

    _SEARCH_CACHE["items"] = rows
    _SEARCH_CACHE["by_id"] = by_id
    _SEARCH_CACHE["loaded_at"] = now
    _SEARCH_CACHE["ttl_seconds"] = ttl
    return rows


def _fulltext_score(
    query_norm: str,
    trade_name: str,
    active_ingredient: str,
    drug_class: str,
    aliases: list[str],
) -> float:
    trade = normalize_query(trade_name)
    ingredient = normalize_query(active_ingredient)
    dclass = normalize_query(drug_class)

    if not query_norm:
        return 0.0
    if query_norm in aliases:
        return 0.98
    if query_norm == trade:
        return 1.0
    if trade.startswith(query_norm):
        return 0.95
    if query_norm in trade:
        return 0.90
    if query_norm == ingredient:
        return 0.88
    if query_norm in ingredient:
        return 0.80
    if query_norm == dclass:
        return 0.78
    if query_norm in dclass:
        return 0.70
    return 0.0


def _fuzzy_score(
    query_norm: str,
    trade_name: str,
    active_ingredient: str,
    drug_class: str,
    aliases: list[str],
) -> float:
    from rapidfuzz import fuzz

    candidates = [
        (trade_name or "").lower(),
        (active_ingredient or "").lower(),
        (drug_class or "").lower(),
        *aliases,
    ]
    return max(
        float(fuzz.WRatio(query_norm, candidate)) / 100.0
        for candidate in candidates
        if candidate
    ) if candidates else 0.0


def _coverage_boost(query_norm: str, medicine: Medicine, aliases: list[str]) -> float:
    if not query_norm:
        return 0.0
    ingredient_tokens = [token.strip() for token in (medicine.active_ingredient_tokens or "").split(";") if token.strip()]
    matched_channels = 0
    if query_norm in normalize_query(medicine.trade_name):
        matched_channels += 1
    if query_norm in normalize_query(medicine.active_ingredient):
        matched_channels += 1
    if query_norm in aliases:
        matched_channels += 1
    if query_norm in ingredient_tokens:
        matched_channels += 1
    if matched_channels <= 1:
        return 0.0
    return min(0.12, 0.04 * matched_channels)


def _ingredient_token_boost(query_norm: str, medicine: Medicine) -> float:
    from rapidfuzz import fuzz

    ingredient_tokens = [token.strip() for token in (medicine.active_ingredient_tokens or "").split(";") if token.strip()]
    if not ingredient_tokens:
        return 0.0
    if query_norm in ingredient_tokens:
        return 0.10
    return max(
        float(fuzz.WRatio(query_norm, token)) / 100.0 * 0.06
        for token in ingredient_tokens
    )


def _drug_class_penalty(query_norm: str, medicine: Medicine) -> float:
    trade = normalize_query(medicine.trade_name)
    ingredient = normalize_query(medicine.active_ingredient)
    drug_class = normalize_query(medicine.drug_class)
    if query_norm in drug_class and query_norm not in trade and query_norm not in ingredient:
        return 0.06
    return 0.0


def _parse_aliases_for_search(raw_aliases: str) -> list[str]:
    return parse_aliases(raw_aliases)


def search_medicines_ranked(
    query: str,
    limit: int,
    query_weight: float = 1.0,
    length_penalty_strength_multiplier: float = 1.0,
) -> list[dict[str, Any]]:
    query_norm = normalize_query(query)
    if not query_norm:
        return []

    fuzzy_min = float(_get_setting("SEARCH_FUZZY_MIN_SCORE", 0.45))
    fulltext_weight = float(_get_setting("SEARCH_FULLTEXT_WEIGHT", 0.60))
    fuzzy_weight = float(_get_setting("SEARCH_FUZZY_WEIGHT", 0.40))
    alias_boost_weight = float(_get_setting("SEARCH_ALIAS_BOOST_WEIGHT", 0.10))
    ingredient_boost_weight = float(_get_setting("SEARCH_INGREDIENT_BOOST_WEIGHT", 0.10))
    coverage_boost_weight = float(_get_setting("SEARCH_COVERAGE_BOOST_WEIGHT", 0.06))
    class_penalty_weight = float(_get_setting("SEARCH_DRUG_CLASS_PENALTY_WEIGHT", 0.05))
    expansion = int(_get_setting("SEARCH_CANDIDATE_EXPANSION", 4))
    expansion = max(1, expansion)
    candidate_limit = max(limit, limit * expansion)

    fulltext_q = (
        Q(trade_name__icontains=query_norm)
        | Q(active_ingredient__icontains=query_norm)
        | Q(drug_class__icontains=query_norm)
        | Q(search_aliases__icontains=query_norm)
        | Q(active_ingredient_tokens__icontains=query_norm)
    )
    fulltext_ids = set(Medicine.objects.filter(fulltext_q).values_list("id", flat=True)[:candidate_limit])

    rows = _load_medicine_rows()
    fuzzy_candidates: list[tuple[int, float]] = []
    for row in rows:
        fuzzy = _fuzzy_score(
            query_norm,
            row["trade_name_norm"],
            row["active_ingredient_norm"],
            row["drug_class_norm"],
            row["aliases"],
        )
        if fuzzy >= fuzzy_min:
            fuzzy_candidates.append((row["id"], fuzzy))
    fuzzy_candidates.sort(key=lambda item: item[1], reverse=True)
    fuzzy_ids = {medicine_id for medicine_id, _score in fuzzy_candidates[:candidate_limit]}

    candidate_ids = fulltext_ids | fuzzy_ids
    if not candidate_ids:
        return []

    candidates = Medicine.objects.in_bulk(candidate_ids)
    scored: list[dict[str, Any]] = []
    for medicine_id in candidate_ids:
        medicine = candidates.get(medicine_id)
        if medicine is None:
            continue

        cache_row = _SEARCH_CACHE.get("by_id", {}).get(medicine_id, {})
        aliases = cache_row.get("aliases", _parse_aliases_for_search(medicine.search_aliases))
        trade_norm = cache_row.get("trade_name_norm", normalize_query(medicine.trade_name_norm or medicine.trade_name))
        ingredient_norm = cache_row.get(
            "active_ingredient_norm", normalize_query(medicine.active_ingredient_norm or medicine.active_ingredient)
        )
        class_norm = cache_row.get("drug_class_norm", normalize_query(medicine.drug_class_norm or medicine.drug_class))
        fulltext = _fulltext_score(
            query_norm,
            trade_norm,
            ingredient_norm,
            class_norm,
            aliases,
        )
        fuzzy = _fuzzy_score(
            query_norm,
            trade_norm,
            ingredient_norm,
            class_norm,
            aliases,
        )
        length_factor, length_ratio, matched_len = _length_compatibility_factor(
            query_norm,
            trade_norm,
            ingredient_norm,
            class_norm,
            penalty_strength_multiplier=length_penalty_strength_multiplier,
        )
        alias_boost = 1.0 if query_norm in aliases else 0.0
        ingredient_boost = _ingredient_token_boost(query_norm, medicine)
        coverage_boost = _coverage_boost(query_norm, medicine, aliases)
        class_penalty = _drug_class_penalty(query_norm, medicine)

        combined = (fulltext * fulltext_weight) + (fuzzy * fuzzy_weight)
        combined += (alias_boost * alias_boost_weight)
        combined += (ingredient_boost * ingredient_boost_weight)
        combined += (coverage_boost * coverage_boost_weight)
        combined -= (class_penalty * class_penalty_weight)
        combined *= length_factor
        scored.append(
            {
                "medicine": medicine,
                "score": round(fuzzy, 4),
                "_rank_score": round(combined * query_weight, 4),
                "matched_query": query,
                "_debug_length_factor": round(length_factor, 4),
                "_debug_length_ratio": round(length_ratio, 4),
                "_debug_query_len": len(query_norm.replace(" ", "")),
                "_debug_match_len": matched_len,
            }
        )

    scored.sort(key=lambda item: item["_rank_score"], reverse=True)
    return scored[:limit]


def _length_ratio(a: int, b: int) -> float:
    if a <= 0 or b <= 0:
        return 0.0
    return min(a, b) / max(a, b)


def _length_compatibility_factor(
    query_norm: str,
    trade_name: str,
    active_ingredient: str,
    drug_class: str,
    *,
    penalty_strength_multiplier: float = 1.0,
) -> tuple[float, float, int]:
    if not bool(_get_setting("SEARCH_LENGTH_PENALTY_ENABLED", True)):
        return 1.0, 1.0, len(query_norm)

    query_len = len(query_norm.replace(" ", ""))
    if query_len <= 0:
        return 1.0, 1.0, 0

    strength = float(_get_setting("SEARCH_LENGTH_PENALTY_STRENGTH", 1.6))
    strength = max(0.1, strength * max(0.1, penalty_strength_multiplier))
    ratio_floor = float(_get_setting("SEARCH_LENGTH_RATIO_FLOOR", 0.35))
    ratio_floor = max(0.0, min(1.0, ratio_floor))

    candidate_terms: list[str] = []
    for raw in (trade_name, active_ingredient, drug_class):
        normalized = normalize_query(raw)
        if not normalized:
            continue
        candidate_terms.append(normalized.replace(" ", ""))
        candidate_terms.extend(re.findall(r"\w+", normalized))

    if not candidate_terms:
        return 1.0, 1.0, query_len

    best_ratio = 0.0
    best_len = query_len
    for term in candidate_terms:
        term_len = len(term)
        ratio = _length_ratio(query_len, term_len)
        if ratio > best_ratio:
            best_ratio = ratio
            best_len = term_len

    if best_ratio < ratio_floor:
        return 0.0, best_ratio, best_len

    factor = best_ratio ** strength
    return factor, best_ratio, best_len
