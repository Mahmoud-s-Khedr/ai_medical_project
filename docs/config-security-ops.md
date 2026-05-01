# Configuration, Security, and Operations

## Configuration Interface

Primary source: `medicine_backend/settings.py`.

### Core Runtime

- `DEBUG`
- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `DATABASE_URL`
- `TIME_ZONE` (default `Africa/Cairo`)

### CORS

- `CORS_ALLOWED_ORIGINS`
- `CORS_ALLOW_ALL_ORIGINS`
- `CORS_ALLOW_CREDENTIALS`

### Upload and Request Guards

- `DATA_UPLOAD_MAX_MEMORY_SIZE`
- `FILE_UPLOAD_MAX_MEMORY_SIZE`
- `OCR_MAX_UPLOAD_BYTES`

### Auth/JWT

- SimpleJWT access lifetime: 1 hour
- SimpleJWT refresh lifetime: 30 days
- Refresh rotation and blacklisting enabled
- Password reset timeout: 24h (`PASSWORD_RESET_TIMEOUT`)

### DRF Runtime Defaults

- Default permission class: authenticated
- Throttle classes: anon + user
- Throttle rates:
- `anon: 30/hour`
- `user: 1000/day`
- `auth: 10/hour` (scope used by register/password reset views)
- Pagination class: `api.pagination.StandardPagination`

### OCR/Search Tuning

- OCR thresholds/caps:
- `OCR_MAX_CANDIDATES`
- `OCR_MIN_SCORE`
- `OCR_RESULT_FLOOR`
- `OCR_LOW_CONFIDENCE_THRESHOLD`
- `OCR_HIGH_CONFIDENCE_THRESHOLD`
- `OCR_LOW_CONFIDENCE_MAX_RESULTS`
- `OCR_MEDICINE_CACHE_TTL_SECONDS`
- `YOLO_MODEL_PATH`
- Search tuning:
- `SEARCH_COMBINED_TOP_K`
- `SEARCH_FUZZY_MIN_SCORE`
- `SEARCH_FULLTEXT_WEIGHT`
- `SEARCH_FUZZY_WEIGHT`
- `SEARCH_CANDIDATE_EXPANSION`
- `SEARCH_MEDICINE_CACHE_TTL_SECONDS`

## Security and Access Model

- API defaults to authenticated-only access.
- Medicine writes are admin/staff only (`IsAdminOrReadOnly`).
- Reminders and medical-record resources are user-scoped by queryset.
- Logout blacklists refresh tokens to invalidate future refresh use.
- Password reset request response is intentionally non-enumerating.
- OCR upload includes size checks and PIL decode safety guard.

## Operational Commands

- Migrate DB: `python manage.py migrate`
- Import catalog: `python manage.py import_medicines --path medicines.csv`
- Test suite: `python manage.py test -v 2`
- Run server: `python manage.py runserver 127.0.0.1:8000`
- CLI OCR test: `python cli_ocr_search.py sample_medicine.png --catalog medicines.csv --column trade_name`

## Troubleshooting

- If YOLO model is missing, OCR still works via full-image fallback (warning logged).
- If Tesseract binary is missing, EasyOCR remains active and Tesseract is skipped.
- `400 Bad Request` on local scripted calls can be caused by `ALLOWED_HOSTS` mismatch (use allowed host).
