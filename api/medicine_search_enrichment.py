from __future__ import annotations

import re


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def split_tokens(value: str) -> list[str]:
    text = normalize_text(value)
    if not text:
        return []
    return [token for token in re.split(r"\s+", text) if token]


def split_ingredient_tokens(value: str) -> list[str]:
    normalized = normalize_text(value)
    if not normalized:
        return []

    chunks = re.split(r"\+|/|,|;|\(|\)", normalized)
    seen: set[str] = set()
    ordered: list[str] = []
    for chunk in chunks:
        cleaned = normalize_text(chunk)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ordered


def parse_aliases(value: str) -> list[str]:
    if not (value or "").strip():
        return []
    chunks = re.split(r"[,;\n]+", value)
    seen: set[str] = set()
    ordered: list[str] = []
    for chunk in chunks:
        alias = normalize_text(chunk)
        if not alias or alias in seen:
            continue
        seen.add(alias)
        ordered.append(alias)
    return ordered


def build_aliases(trade_name: str, active_ingredient: str, explicit_aliases: str = "") -> str:
    aliases = parse_aliases(explicit_aliases)
    candidates = [normalize_text(trade_name), normalize_text(active_ingredient)]
    candidates.extend(split_ingredient_tokens(active_ingredient))

    seen = set(aliases)
    for candidate in candidates:
        if candidate and candidate not in seen:
            aliases.append(candidate)
            seen.add(candidate)

    return "; ".join(aliases)
