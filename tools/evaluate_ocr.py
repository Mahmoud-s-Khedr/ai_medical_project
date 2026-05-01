from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

import cv2
from rapidfuzz import fuzz
from rapidfuzz import process as rfprocess

# Allow running this script directly from tools/ while importing project modules.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.ocr_pipeline import try_rotations_and_ocr


def load_catalog(path: Path, column: str) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if column not in (reader.fieldnames or []):
            raise ValueError(f"Column {column!r} not found in catalog.")
        return [row[column].strip() for row in reader if row.get(column, "").strip()]


def load_labels(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"image_path", "expected_trade_name"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError("Labels CSV must contain: image_path, expected_trade_name")
        return list(reader)


def rank_matches(query: str, choices: list[str], top_k: int, min_score: int) -> list[str]:
    if not query:
        return []
    rows = rfprocess.extract(query, choices, scorer=fuzz.WRatio, limit=top_k, score_cutoff=min_score)
    return [name for name, _score, _idx in rows]


def evaluate(labels: list[dict[str, str]], choices: list[str], top_k: int, min_score: int) -> dict[str, float]:
    total = 0
    hit1 = 0
    hit3 = 0
    failures: list[dict[str, str]] = []

    for row in labels:
        image_path = Path(row["image_path"])
        expected = row["expected_trade_name"].strip()
        image_bgr = cv2.imread(str(image_path))
        if image_bgr is None:
            failures.append({"image_path": str(image_path), "reason": "image_read_failed"})
            continue

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        text, _confidence, _angle, _engine = try_rotations_and_ocr(image_rgb)
        tokens = [token for token in text.split() if len(token) >= 2]
        queries = list(dict.fromkeys(([" ".join(tokens)] if tokens else []) + tokens))

        merged: list[str] = []
        for q in queries:
            for name in rank_matches(q, choices, top_k=top_k, min_score=min_score):
                if name not in merged:
                    merged.append(name)
        merged = merged[:top_k]

        total += 1
        if merged and merged[0] == expected:
            hit1 += 1
        if expected in merged[:3]:
            hit3 += 1

    if total == 0:
        return {"samples": 0, "precision_at_1": 0.0, "precision_at_3": 0.0, "failures": failures}

    return {
        "samples": total,
        "precision_at_1": round(hit1 / total, 4),
        "precision_at_3": round(hit3 / total, 4),
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline OCR precision evaluator (p@1, p@3).")
    parser.add_argument("--catalog", type=Path, default=Path("medicines.csv"))
    parser.add_argument("--labels", type=Path, required=True, help="CSV with image_path,expected_trade_name")
    parser.add_argument("--column", default="trade_name")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--min-score", type=int, default=55)
    args = parser.parse_args()

    catalog = load_catalog(args.catalog, args.column)
    labels = load_labels(args.labels)
    report = evaluate(labels, catalog, top_k=args.top_k, min_score=args.min_score)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
