from __future__ import annotations

import argparse
import csv
import json
import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="'pin_memory' argument is set as true but not supported on MPS now.*",
    category=UserWarning,
)

import cv2
from rapidfuzz import fuzz
from rapidfuzz import process as rfprocess

from ai.ocr_pipeline import try_rotations_and_ocr


def parse_angles(raw: str) -> tuple[int, ...]:
    items = [part.strip() for part in raw.split(",") if part.strip()]
    if not items:
        raise ValueError("--angles must contain at least one integer angle")
    try:
        return tuple(int(item) for item in items)
    except ValueError as exc:
        raise ValueError(f"Invalid --angles value: {raw!r}") from exc


def load_catalog(path: Path, column: str) -> list[dict[str, str]]:
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if column not in (reader.fieldnames or []):
            raise ValueError(f"Column {column!r} not found in {path}. Found: {reader.fieldnames}")
        return [row for row in reader if row.get(column) and row[column].strip()]


def fuzzy_search(
    query: str,
    catalog: list[dict[str, str]],
    choices: list[str],
    top_k: int,
    min_score: int,
    query_weight: float,
) -> list[dict]:
    if not query or not catalog or not choices:
        return []

    matches = rfprocess.extract(
        query,
        choices,
        scorer=fuzz.WRatio,
        limit=top_k,
        score_cutoff=min_score,
    )

    results = []
    for name, score, idx in matches:
        row = dict(catalog[idx])
        row["name"] = name
        row["score"] = round(score / 100.0, 4)
        row["_rank_score"] = round((score / 100.0) * query_weight, 4)
        row["matched_query"] = query
        results.append(row)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run medicine OCR search on a local image.")
    parser.add_argument("image", type=Path, help="Path to the medicine image.")
    parser.add_argument("--catalog", type=Path, default=Path("medicines.csv"), help="CSV catalog path.")
    parser.add_argument("--column", default="trade_name", help="Medicine name column in the CSV catalog.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--min-score", type=int, default=30)
    parser.add_argument(
        "--angles",
        default="0,-10,10,-20,20,-90,90",
        help="Comma-separated OCR rotation angles in degrees.",
    )
    parser.add_argument("--early-exit-confidence", type=float, default=0.92)
    parser.add_argument("--skip-tesseract-if-easyocr-confident", type=float, default=0.88)
    parser.add_argument(
        "--disable-tesseract",
        action="store_true",
        help="Skip Tesseract engine and run EasyOCR only (usually faster on CPU).",
    )
    args = parser.parse_args()

    image_bgr = cv2.imread(str(args.image))
    if image_bgr is None:
        raise SystemExit(f"Could not read image: {args.image}")

    angles = parse_angles(args.angles)
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    text, confidence, angle, engine = try_rotations_and_ocr(
        image_rgb,
        angles=angles,
        early_exit_confidence=args.early_exit_confidence,
        skip_tesseract_if_easyocr_confident=args.skip_tesseract_if_easyocr_confident,
        use_tesseract=not args.disable_tesseract,
    )
    tokens = [token for token in text.split() if len(token) >= 2]
    ocr_tokens = list(dict.fromkeys(([" ".join(tokens)] if tokens else []) + tokens))

    catalog = load_catalog(args.catalog, args.column)
    choices = [row[args.column].strip() for row in catalog]
    seen: dict[str, dict] = {}
    for idx, token in enumerate(ocr_tokens):
        query_weight = 1.15 if idx == 0 and " " in token else 1.0
        for hit in fuzzy_search(token, catalog, choices, args.top_k, args.min_score, query_weight):
            name = hit["name"]
            if name not in seen or hit["_rank_score"] > seen[name]["_rank_score"]:
                seen[name] = hit

    matches = sorted(seen.values(), key=lambda item: item["_rank_score"], reverse=True)[: args.top_k]
    for match in matches:
        match.pop("_rank_score", None)

    result = {
        "ocr_raw_text": text,
        "ocr_confidence": confidence,
        "ocr_angle": angle,
        "ocr_engine": engine,
        "ocr_tokens": ocr_tokens,
        "matches": matches,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
