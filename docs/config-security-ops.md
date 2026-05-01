# Configuration, Security, and Operations

Primary source: `medicine_backend/settings.py`.

## Core Runtime Settings

- `SECRET_KEY` default: `dev-only-medicine-ocr-secret-key`
- `DEBUG` default: `True`
- `ALLOWED_HOSTS` default: `127.0.0.1,localhost`
- `DATABASE_URL` default: sqlite at `db.sqlite3`
- `TIME_ZONE`: `Africa/Cairo`

## Upload and Request Guardrails

- `DATA_UPLOAD_MAX_MEMORY_SIZE` default: `8388608` (8 MB)
- `FILE_UPLOAD_MAX_MEMORY_SIZE` default: `8388608` (8 MB)
- `OCR_MAX_UPLOAD_BYTES` default: `8388608` (8 MB)

OCR upload path behavior:
- Rejects upload over `OCR_MAX_UPLOAD_BYTES` with `413`.
- Applies PIL decompression guard `Image.MAX_IMAGE_PIXELS = 40_000_000`.

## CORS

- `CORS_ALLOWED_ORIGINS` default: empty list
- `CORS_ALLOW_ALL_ORIGINS` default: `True`
- `CORS_ALLOW_CREDENTIALS` fixed: `True`

Note: literal `*` entries are stripped from `CORS_ALLOWED_ORIGINS` in settings.

## DRF and Auth Runtime

REST defaults:
- Default auth: `JWTAuthentication`
- Default permission: `IsAuthenticated`
- Default pagination: `api.pagination.StandardPagination`
- Default page size: `20`
- Schema class: drf-spectacular `AutoSchema`

Throttling:
- Classes: `AnonRateThrottle`, `UserRateThrottle`
- Rates:
- `anon = 30/hour`
- `user = 1000/day`
- `auth = 10/hour` (used by register/password-reset endpoints via scoped throttle)

JWT (`SIMPLE_JWT`):
- `ACCESS_TOKEN_LIFETIME`: 1 hour
- `REFRESH_TOKEN_LIFETIME`: 30 days
- Rotate refresh tokens: enabled
- Blacklist after rotation: enabled
- Header type: `Bearer`
- Update last login: enabled

Password reset:
- `PASSWORD_RESET_TIMEOUT = 86400` seconds (24h)
- Reset link uses `FRONTEND_URL` (default `http://localhost:3000`)

## OCR and Search Tunables

OCR controls:
- `OCR_MAX_CANDIDATES` default `5`
- `OCR_MIN_SCORE` default `0.55`
- `OCR_RESULT_FLOOR` default `0.60`
- `OCR_LOW_CONFIDENCE_THRESHOLD` default `0.72`
- `OCR_HIGH_CONFIDENCE_THRESHOLD` default `0.85`
- `OCR_LOW_CONFIDENCE_MAX_RESULTS` default `2`
- `OCR_MEDICINE_NAME_FIELD` fixed `trade_name`
- `OCR_MEDICINE_CACHE_TTL_SECONDS` default `300`
- `OCR_ROTATION_ANGLES` default `0,-10,10,-20,20`
- `OCR_EARLY_EXIT_CONFIDENCE` default `0.90`
- `OCR_SKIP_TESSERACT_IF_EASYOCR_CONFIDENT` default `0.88`
- `OCR_USE_TESSERACT` default `False`
- `OCR_MIN_TOKEN_LENGTH` default `3`
- `OCR_TOKEN_STOPWORDS` default common English stopwords list
- `OCR_PHRASE_STRONG_SCORE` default `0.85`
- `OCR_INCLUDE_MATCH_DEBUG` default `True`

Search controls:
- `SEARCH_COMBINED_TOP_K` default `200`
- `SEARCH_FUZZY_MIN_SCORE` default `0.45`
- `SEARCH_FULLTEXT_WEIGHT` default `0.60`
- `SEARCH_FUZZY_WEIGHT` default `0.40`
- `SEARCH_CANDIDATE_EXPANSION` default `4`
- `SEARCH_MEDICINE_CACHE_TTL_SECONDS` default `300`
- `SEARCH_LENGTH_PENALTY_ENABLED` default `True`
- `SEARCH_LENGTH_PENALTY_STRENGTH` default `2.2`
- `SEARCH_LENGTH_RATIO_FLOOR` default `0.35`
- `SEARCH_ALIAS_BOOST_WEIGHT` default `0.10`
- `SEARCH_INGREDIENT_BOOST_WEIGHT` default `0.10`
- `SEARCH_COVERAGE_BOOST_WEIGHT` default `0.06`
- `SEARCH_DRUG_CLASS_PENALTY_WEIGHT` default `0.05`

## Behavior Toggles That Change Runtime Results

- `YOLO_MODEL_PATH`: if missing/unloadable/inference failure, OCR falls back to full-image path.
- `OCR_USE_TESSERACT`: enables Tesseract execution in rotation loop.
- `OCR_SKIP_TESSERACT_IF_EASYOCR_CONFIDENT`: skips Tesseract when EasyOCR confidence is high enough.
- `OCR_ROTATION_ANGLES`: controls orientation candidates.
- `OCR_RESULT_FLOOR`: minimum accepted ranked match score.
- `OCR_LOW_CONFIDENCE_MAX_RESULTS`: additional cap applied to low-tier responses.

## Operational Commands

- `python manage.py check`
- `python manage.py migrate --noinput`
- `python manage.py import_medicines --path medicines.csv`
- `python manage.py test -v 2`
- `python manage.py runserver 127.0.0.1:8000`
- `python cli_ocr_search.py sample_medicine.png --catalog medicines.csv --column trade_name`

## Docs Consistency Check (Non-Mutating)

Run the docs check helper:

```bash
bash scripts/check_docs_consistency.sh
```

This validates endpoint coverage anchors, `matched_items` naming, and key runtime-setting references.
