# Project Architecture and Improvement Guide

## 1. System Overview

This project is a local-first medicine OCR backend built on Django REST Framework.

Core runtime path:
1. A client uploads a medicine photo to `POST /api/uploads/ocr-search/`.
2. The API validates/decode the image, then optionally detects medicine regions using YOLO (`drug_detector.pt`).
3. OCR runs on each crop (or full image fallback) using EasyOCR and optionally Tesseract.
4. Extracted text/tokens are fuzzy-matched against medicine names in the database.
5. Ranked matches are returned with confidence tier and user action hint.

The repository also includes:
- A CLI OCR search flow for quick local testing without running Django.
- A YOLO training notebook for optional detector model updates.
- Medication reminders and medical record APIs beyond OCR lookup.

---

## 2. Architecture Components

### `medicine_backend/` (Project Configuration)
- `settings.py`: central configuration for auth, DRF, OCR thresholds, upload limits, YOLO model path, cache TTL.
- `urls.py`: root URL routing to API docs/schema and app endpoints.
- `wsgi.py` / `asgi.py`: deployment entrypoints.

### `api/` (Application Layer)
- `models.py`: domain entities (`Medicine`, reminders/events, medical record entities).
- `views.py`: medicine CRUD, interactions endpoint, OCR upload/search endpoint, reminders/events endpoints.
- `medical_views.py`: patient medical-record scoped CRUD/list endpoints.
- `serializers.py`, `medical_serializers.py`, `auth_serializers.py`: input/output and validation rules.
- `auth_views.py`: registration/profile/password/logout/reset endpoints.
- `management/commands/import_medicines.py`: CSV import/update pipeline.
- `tests.py`: auth, medicine, OCR, reminders, and medical-record test coverage.

### `ai/` (OCR Utilities)
- `ocr_pipeline.py` handles:
  - OCR preprocessing (denoise, CLAHE, upscaling),
  - rotation trials,
  - OCR engine execution (EasyOCR and Tesseract fallback),
  - best candidate selection by confidence.

### Data and Tooling Assets
- `medicines.csv`: seed/import catalog.
- `db.sqlite3`: default local database.
- `labeled_images.csv`: small labeled evaluation data reference.
- `tools/evaluate_ocr.py`: helper script for OCR evaluation workflows.
- `postman/`: ready API collection/environment for manual verification.
- `cli_ocr_search.py` and `ocr_medicine_search.py`: local OCR+fuzzy path without Django.
- `mazen_first_(2)_(4).ipynb`: optional YOLO detector training workflow.

---

## 3. End-to-End OCR Request Flow (`POST /api/uploads/ocr-search/`)

Implemented in `api/views.py` (`OCRMedicineSearchView.post`).

1. Authentication and payload
- Endpoint requires JWT-authenticated user.
- Expects multipart field named `image`.
- Optional `top_k` is parsed as integer and clamped to `[1, 20]`.

2. Upload-size protection
- Checks incoming image size against `OCR_MAX_UPLOAD_BYTES` (default 8 MB).
- Oversized uploads return HTTP `413`.

3. Decode and safety checks
- Reads file bytes.
- Uses PIL to decode image with `Image.MAX_IMAGE_PIXELS = 40_000_000` to reduce decompression-bomb risk.
- Decode failures return HTTP `400`.

4. Crop extraction
- Converts image to RGB NumPy array.
- `_extract_crops()` runs YOLO if available:
  - model path from `YOLO_MODEL_PATH`.
  - if model missing/import/inference fails, fallback is full image.
- YOLO boxes are padded slightly before crop.

5. OCR execution
- For each crop, `try_rotations_and_ocr()` from `ai/ocr_pipeline.py`:
  - tests angles `(0, -10, 10, -20, 20, -90, 90)`.
  - preprocesses image (grayscale, denoise, CLAHE, upscale).
  - runs EasyOCR first.
  - runs Tesseract unless EasyOCR confidence exceeds `skip_tesseract_if_easyocr_confident` (default `0.88`).
  - early-exits when confidence reaches `early_exit_confidence` (default `0.92`).
- Returns best text, confidence, angle, and engine used.

6. Tokenization
- OCR text is split into tokens (minimum token length: 2).
- Candidate list includes:
  - full phrase token,
  - individual tokens.
- Duplicates removed while preserving order.

7. Fuzzy ranking
- Medicine index is loaded from DB with in-memory TTL cache (`OCR_MEDICINE_CACHE_TTL_SECONDS`, default 300s).
- `_fuzzy_search_medicines()` uses RapidFuzz `WRatio`:
  - query score cutoff from `OCR_MIN_SCORE` (scaled to 0-100),
  - fetches up to `limit * 3` candidates for ranking.
- Phrase candidate (if multi-word) is weighted higher (`query_weight=1.25`).
- If phrase quality is acceptable (top phrase score >= `OCR_RESULT_FLOOR`), token hits get slight bonus (`query_weight=1.05`).
- Final results are filtered by `OCR_RESULT_FLOOR`, deduplicated by medicine ID, sorted by rank score, and clipped by `top_k`.

8. Confidence tier and response shaping
- `top_score` from best match combines with OCR confidence:
  - `combined = (ocr_conf * 0.55) + (top_score * 0.45)`.
- Tier thresholds:
  - `high` >= `OCR_HIGH_CONFIDENCE_THRESHOLD` (default 0.85)
  - `medium` >= `OCR_LOW_CONFIDENCE_THRESHOLD` (default 0.72)
  - otherwise `low`
- Action hint:
  - `low` => `retake_photo`
  - `medium/high` => `show_results`
- For low-confidence responses, result count is capped by `OCR_LOW_CONFIDENCE_MAX_RESULTS` (default 2).

9. Output fields
- `ocr_raw_text`, `ocr_confidence`, `ocr_angle`, `ocr_engine`, `ocr_tokens`
- `matches`
- `match_confidence_tier`
- `action_hint`
- `message`

---

## 4. Data Model and API Map

## 4.1 Key Entities

### Medicine catalog (`api.models.Medicine`)
Main searchable fields:
- `trade_name` (unique)
- `active_ingredient`
- `strength`
- `dosage_form`

Clinical/context fields:
- `drug_class`, `common_side_effects`, `serious_warning`
- `similar_active_ingredients`, `similarity_risk_symptoms`, `switching_note`, `interaction_notes`

### Medication reminder domain
- `MedicationReminder`: per-user reminder with optional link to `Medicine`, schedule (`times` JSON list), date range, timezone.
- `ReminderEvent`: status timeline per reminder (`scheduled`, `taken`, `missed`, `skipped`).

### Medical record domain
- `MedicalRecord` (one-to-one per user)
- related collections:
  - `Diagnosis`
  - `Allergy`
  - `VitalSign`
  - `LabResult`
  - `DoctorVisit`

## 4.2 Endpoint Groups

Authentication:
- `POST /api/auth/register/`
- `POST /api/auth/token/`, `/refresh/`, `/verify/`
- `POST /api/auth/logout/`
- `GET/PATCH /api/auth/me/`
- `POST /api/auth/me/change-password/`
- `POST /api/auth/password-reset/`
- `POST /api/auth/password-reset/confirm/`

Medicines:
- `GET /api/medicines/` (+ `?search=`)
- `GET /api/medicines/{id}/`
- `GET /api/medicines/{id}/interactions/`
- write operations restricted by permission policy (`IsAdminOrReadOnly`).

OCR:
- `POST /api/uploads/ocr-search/`

Reminders:
- `GET/POST /api/reminders/`
- `GET/PATCH/DELETE /api/reminders/{id}/`
- `GET/POST /api/reminders/{id}/events/`

Medical record:
- `GET/PATCH/PUT /api/medical-record/`
- `GET /api/medical-record/summary/`
- `GET/POST` item routes under:
  - `/api/medical-record/diagnoses/`
  - `/api/medical-record/allergies/`
  - `/api/medical-record/vitals/`
  - `/api/medical-record/lab-results/`
  - `/api/medical-record/visits/`

---

## 5. How Accuracy Works Today

Current behavior is a combination of OCR quality and fuzzy match quality.

### OCR engine behavior
- Primary OCR: EasyOCR.
- Secondary OCR: Tesseract (if installed and not skipped by high EasyOCR confidence).
- Rotation trials improve robustness for tilted or vertical packaging text.
- If no YOLO detector is available, the system still runs using full-image OCR.

### Matching behavior
- Matches are based on medicine `trade_name` values loaded from DB.
- Phrase + token fallback means even weak phrase OCR can still recover via a strong single token.
- Score filtering uses:
  - `OCR_MIN_SCORE` for RapidFuzz extraction cutoff,
  - `OCR_RESULT_FLOOR` for final response acceptance.

### Confidence behavior
- Final confidence tier uses weighted OCR confidence + top fuzzy score.
- Low tier triggers retake guidance and stricter output cap.

### Runtime/cache behavior
- Medicine names are cached in-process with TTL to reduce repeated DB reads.
- Cache refresh frequency is controlled by `OCR_MEDICINE_CACHE_TTL_SECONDS`.

---

## 6. Accuracy Improvement Plan (Prioritized)

## Priority 1: Data quality and normalization (highest ROI)
1. Normalize catalog names before import:
- consistent casing,
- remove duplicated whitespace,
- unify punctuation variants (`-`, `/`, dots),
- standardize dosage suffix style.
2. Add alias/synonym coverage:
- include common transliterations, brand spacing variants, and frequent misspellings in a separate alias table or indexed field.
3. Deduplicate near-identical medicines:
- ensure one canonical row per product variant to avoid ranking ambiguity.

## Priority 2: OCR robustness improvements
1. Add configurable image pre-processing variants:
- adaptive threshold path,
- morphology (open/close) path,
- sharpened path.
2. Expand OCR language/model coverage if needed:
- e.g., support mixed Arabic/English packaging where relevant.
3. Tune angle search list using real production samples:
- remove low-yield angles, add high-yield angles.

## Priority 3: Ranking/scoring calibration
1. Build an evaluation set from real images (`image -> expected medicine`).
2. Sweep thresholds (`OCR_MIN_SCORE`, `OCR_RESULT_FLOOR`, confidence thresholds) and compare precision/recall/top-1 accuracy.
3. Add multi-field candidate scoring:
- keep `trade_name` primary,
- add weighted backing from `active_ingredient` for disambiguation.
4. Consider score penalties for very short tokens to reduce false positives.

## Priority 4: Detector and crop quality
1. Retrain/refresh YOLO detector with harder examples:
- glare, blur, angled boxes, partial occlusion.
2. Add confidence/size filtering for YOLO boxes to reduce bad crops.
3. Evaluate full-image + crop ensemble voting for unstable cases.

## Priority 5: Observability and feedback loop
1. Persist anonymized OCR telemetry:
- OCR text, chosen tokens, top candidates, final pick, confidence tier.
2. Collect user correction signal ("wrong medicine") to create hard-negative datasets.
3. Run scheduled offline evaluation (weekly/monthly) and track trend metrics.

---

## 7. How To Add More Medicines

This section describes the current supported ingestion path through CSV import.

## 7.1 Required workflow
1. Prepare CSV file (UTF-8/UTF-8-SIG) with header row.
2. Ensure `trade_name` exists for every valid row.
3. Run import command:

```bash
python manage.py import_medicines --path medicines.csv
```

or with custom file:

```bash
python manage.py import_medicines --path /path/to/new_medicines.csv
```

4. Verify output summary (`created`, `updated`).
5. Run API query checks (`/api/medicines/?search=`) and OCR smoke tests.

## 7.2 CSV schema used by current importer
The importer reads these columns (missing columns default to blank strings):
- `trade_name` (required for processing row)
- `active_ingredient`
- `strength`
- `dosage_form`
- `drug_class`
- `common_side_effects`
- `serious_warning`
- `similar_active_ingredients`
- `similarity_risk_symptoms`
- `switching_note`
- `interaction_notes`

Implementation note:
- import uses `update_or_create(trade_name=...)`, so existing rows with same `trade_name` are updated.

## 7.3 Data quality checklist before import
1. Remove exact duplicates by `trade_name`.
2. Normalize brand spelling and spacing consistently.
3. Keep `active_ingredient` medically consistent (same naming convention across rows).
4. Standardize strength formatting (e.g., `500 mg`, `500 mg + 65 mg`).
5. Avoid placeholder garbage text in clinical warning fields.

## 7.4 Verification checklist after import
1. Search test:
- call `GET /api/medicines/?search=<name_fragment>` for newly added rows.
2. OCR test:
- run OCR endpoint with known package images for sampled new medicines.
3. Interaction test:
- check `/api/medicines/{id}/interactions/` for medicines using `similar_active_ingredients`.

## 7.5 Rollback and safe update strategy
1. Keep source CSV under version control (or immutable archive with date stamp).
2. Before large imports, back up DB (`db.sqlite3` copy for local env or DB dump in production).
3. If import quality is bad:
- restore backup,
- fix CSV normalization,
- re-import.
4. Prefer staged rollout:
- import subset,
- run OCR validation,
- then import full batch.

---

## 8. Operational Recommendations

1. Logging and monitoring
- Keep structured logs around OCR confidence, match count, and retake rates.
- Add dashboard metrics:
  - low-confidence ratio,
  - no-match ratio,
  - top-1 acceptance/correction rate.

2. Regression tests
- Extend `api/tests.py` with:
  - threshold edge tests,
  - ambiguous-name ranking tests,
  - OCR token fallback cases for new catalog patterns.

3. Evaluation workflow
- Maintain labeled set (`labeled_images.csv` + images).
- Periodically run evaluation script (`tools/evaluate_ocr.py`) to measure trends.
- Re-tune thresholds only based on tracked precision/recall impact, not anecdotal cases.

4. Configuration governance
- Treat OCR settings in `settings.py` as environment-tunable parameters.
- Document current production values and change history when tuning.

---

## 9. Current Tunable Settings Reference

From `medicine_backend/settings.py`:
- `OCR_MAX_CANDIDATES` (default `5`)
- `OCR_MIN_SCORE` (default `0.55`)
- `OCR_RESULT_FLOOR` (default `0.60`)
- `OCR_LOW_CONFIDENCE_THRESHOLD` (default `0.72`)
- `OCR_HIGH_CONFIDENCE_THRESHOLD` (default `0.85`)
- `OCR_LOW_CONFIDENCE_MAX_RESULTS` (default `2`)
- `OCR_MEDICINE_NAME_FIELD` (currently `trade_name`)
- `YOLO_MODEL_PATH` (default `<BASE_DIR>/drug_detector.pt`)
- `OCR_MAX_UPLOAD_BYTES` (default `8 * 1024 * 1024`)
- `OCR_MEDICINE_CACHE_TTL_SECONDS` (default `300`)

These settings should be reviewed together whenever OCR behavior is tuned.
