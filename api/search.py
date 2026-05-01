from __future__ import annotations

import re
import time
from typing import Any

from django.conf import settings
from django.db.models import Q

from .models import Medicine

_SEARCH_CACHE: dict[str, Any] = {
    "loaded_at": 0.0,
    "ttl_seconds": 300,
    "items": [],
}


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", (query or "").strip()).lower()


def _get_setting(name: str, default: Any) -> Any:
    return getattr(settings, name, default)


def _load_medicine_rows() -> list[tuple[int, str, str, str]]:
    now = time.time()
    ttl = int(_get_setting("SEARCH_MEDICINE_CACHE_TTL_SECONDS", _SEARCH_CACHE["ttl_seconds"]))
    cached_items = _SEARCH_CACHE["items"]
    current_count = Medicine.objects.count()
    if cached_items and (now - _SEARCH_CACHE["loaded_at"]) < ttl and len(cached_items) == current_count:
        return cached_items

    rows = list(Medicine.objects.values_list("id", "trade_name", "active_ingredient", "drug_class"))
    _SEARCH_CACHE["items"] = rows
    _SEARCH_CACHE["loaded_at"] = now
    _SEARCH_CACHE["ttl_seconds"] = ttl
    return rows


def _fulltext_score(query_norm: str, trade_name: str, active_ingredient: str, drug_class: str) -> float:
    trade = (trade_name or "").strip().lower()
    ingredient = (active_ingredient or "").strip().lower()
    dclass = (drug_class or "").strip().lower()

    if not query_norm:
        return 0.0
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


def _fuzzy_score(query_norm: str, trade_name: str, active_ingredient: str, drug_class: str) -> float:
    from rapidfuzz import fuzz

    return max(
        float(fuzz.WRatio(query_norm, (trade_name or "").lower())) / 100.0,
        float(fuzz.WRatio(query_norm, (active_ingredient or "").lower())) / 100.0,
        float(fuzz.WRatio(query_norm, (drug_class or "").lower())) / 100.0,
    )


def search_medicines_ranked(query: str, limit: int, query_weight: float = 1.0) -> list[dict[str, Any]]:
    query_norm = normalize_query(query)
    if not query_norm:
        return []

    fuzzy_min = float(_get_setting("SEARCH_FUZZY_MIN_SCORE", 0.45))
    fulltext_weight = float(_get_setting("SEARCH_FULLTEXT_WEIGHT", 0.60))
    fuzzy_weight = float(_get_setting("SEARCH_FUZZY_WEIGHT", 0.40))
    expansion = int(_get_setting("SEARCH_CANDIDATE_EXPANSION", 4))
    expansion = max(1, expansion)
    candidate_limit = max(limit, limit * expansion)

    fulltext_q = Q(trade_name__icontains=query_norm) | Q(active_ingredient__icontains=query_norm) | Q(drug_class__icontains=query_norm)
    fulltext_ids = set(Medicine.objects.filter(fulltext_q).values_list("id", flat=True)[:candidate_limit])

    rows = _load_medicine_rows()
    fuzzy_candidates: list[tuple[int, float]] = []
    for medicine_id, trade_name, active_ingredient, drug_class in rows:
        fuzzy = _fuzzy_score(query_norm, trade_name, active_ingredient, drug_class)
        if fuzzy >= fuzzy_min:
            fuzzy_candidates.append((medicine_id, fuzzy))
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

        fulltext = _fulltext_score(
            query_norm,
            medicine.trade_name,
            medicine.active_ingredient,
            medicine.drug_class,
        )
        fuzzy = _fuzzy_score(
            query_norm,
            medicine.trade_name,
            medicine.active_ingredient,
            medicine.drug_class,
        )
        combined = (fulltext * fulltext_weight) + (fuzzy * fuzzy_weight)
        scored.append(
            {
                "medicine": medicine,
                "score": round(fuzzy, 4),
                "_rank_score": round(combined * query_weight, 4),
                "matched_query": query,
            }
        )

    scored.sort(key=lambda item: item["_rank_score"], reverse=True)
    return scored[:limit]
