# OCR and Search Internals

## OCR Pipeline Behavior (Current)

Implementation sources:
- `api/views.py` (`OCRMedicineSearchView` and helpers)
- `ai/ocr_pipeline.py`

### Preprocessing and OCR

- Image is converted to grayscale, denoised, CLAHE-adjusted, and upscaled when needed.
- Rotations tested by default: `0, -10, 10, -20, 20, -90, 90`.
- Engine order:
1. EasyOCR
2. Tesseract fallback (unless EasyOCR confidence is already high)
- Early exit occurs when confidence reaches configured threshold.

### Detection and Fallbacks

- YOLO detection is optional; model path from `YOLO_MODEL_PATH`.
- If model file is missing or YOLO fails, full-image OCR is used.
- If OCR yields no tokens, endpoint returns `200` with low-confidence guidance and empty matches.

### Tokenization and Candidate Strategy

- OCR text is split into tokens of length >= 2.
- Candidate query list includes:
- phrase token (`"joined full phrase"`)
- individual tokens
- Duplicates are removed in insertion order.

### Ranking and Filtering

- Search function: `search_medicines_ranked()` in `api/search.py`.
- Ranking combines full-text heuristics and RapidFuzz WRatio.
- OCR flow applies weighted query strategy:
- phrase query weight = `1.25`
- token fallback weight usually `1.0`, slight bonus `1.05` when phrase quality passes gate
- Results filtered by `OCR_RESULT_FLOOR`, deduped by medicine ID, sorted by rank score.

### Confidence and Action Semantics

- `top_score` from best fuzzy match plus OCR confidence produce `combined` confidence.
- Tier thresholds:
- `high >= OCR_HIGH_CONFIDENCE_THRESHOLD`
- `medium >= OCR_LOW_CONFIDENCE_THRESHOLD`
- else `low`
- `action_hint`:
- `low -> retake_photo`
- `medium/high -> show_results`
- low confidence path caps result count by `OCR_LOW_CONFIDENCE_MAX_RESULTS`.

## Search Service Behavior (Current)

Implementation source: `api/search.py`

- Query normalization: trim, collapse spaces, lowercase.
- Candidate sources:
- direct DB `icontains` matches on trade_name/active_ingredient/drug_class
- fuzzy matches from cached in-memory medicine rows
- Composite rank uses configurable fulltext/fuzzy weights.
- Results are bounded by configured limit and candidate expansion factor.

## Caching

- OCR medicine cache in `api/views.py`: `OCR_MEDICINE_CACHE_TTL_SECONDS`.
- Search cache in `api/search.py`: `SEARCH_MEDICINE_CACHE_TTL_SECONDS` and automatic invalidation when row count changes.
