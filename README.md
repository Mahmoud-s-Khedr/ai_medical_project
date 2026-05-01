# Medicine OCR Search Pipeline

Language: [English](README.md) | [العربية](README_AR.md)

## Overview

This repository contains a complete local backend setup for medicine OCR lookup and medication tracking, plus optional model training assets.

It includes four practical tracks:

1. Django REST API for medicine catalog, OCR search, reminders, and medical record endpoints.
2. Demo web UI (`/demo/`) built with Django templates + vanilla JS for end-to-end product walkthrough.
3. YOLO training notebook (`mazen_first_(2)_(4).ipynb`) for medicine-box detection.
4. Local CLI OCR + fuzzy search flow for fast testing without running Django.

## Docs Map

- Team quickstart (English): [TEAM_QUICKSTART_EN.md](TEAM_QUICKSTART_EN.md)
- Team quickstart (Arabic): [TEAM_QUICKSTART_AR.md](TEAM_QUICKSTART_AR.md)
- README (Arabic): [README_AR.md](README_AR.md)

## Important Files

- `manage.py`: Django project entrypoint.
- `api/`: Django app for auth, medicines, OCR search, reminders, and medical records.
- `medicine_backend/`: Django project settings and URL configuration.
- `api/templates/demo/index.html`: demo UI page shell.
- `api/static/demo/app.js`: demo UI logic and API integration.
- `api/static/demo/app.css`: demo UI styling.
- `api/demo_views.py`: demo page and health endpoints.
- `ai/ocr_pipeline.py`: image preprocessing + OCR utilities (EasyOCR/Tesseract + rotation trials).
- `cli_ocr_search.py`: standalone OCR + fuzzy search using local CSV.
- `medicines.csv`: sample medicine catalog used for import/testing.
- `postman/Medicine_OCR_API.postman_collection.json`: ready Postman collection.
- `postman/Medicine_OCR_API.postman_environment.json`: local environment values for Postman.
- `mazen_first_(2)_(4).ipynb`: YOLO training workflow.

## Prerequisites

- macOS or Linux
- Python 3.11 or 3.12 (recommended for OCR/computer-vision package compatibility)
- `pip`
- `tesseract` system binary

macOS install:

```bash
brew install tesseract
```

## Environment Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional minimal setup (without Django backend):

```bash
pip install -r requirements-minimal.txt
```

## Run Django Backend

```bash
source .venv/bin/activate
python manage.py migrate
python manage.py import_medicines --path medicines.csv
python manage.py runserver 127.0.0.1:8000
```

Base URL:

```text
http://127.0.0.1:8000
```

## Routing and Docs Endpoints

- `GET /` returns `302` redirect to `/api/docs/`.
- `GET /demo/` Demo UI entrypoint.
- `GET /demo/health/` Lightweight demo health JSON.
- `GET /api/docs/` Swagger UI.
- `GET /api/schema/` OpenAPI schema.
- `GET /api/redoc/` ReDoc UI.

## Demo Web UI

Open:

```text
http://127.0.0.1:8000/demo/
```

The demo UI covers:

- Register/login/logout with real JWT auth.
- OCR upload search with confidence tier and action hint display.
- Medicine list/search/details/interactions.
- Reminder create/list/update/delete and events.
- Medical record profile + diagnoses/allergies/vitals/labs/visits creation.

Demo UI notes:

- Tokens are stored in browser local storage for the session.
- If access token expires, the UI auto-refreshes once using refresh token.
- If refresh fails, UI clears auth state and requires login again.

## Authentication Note

Most API endpoints are protected and require JWT Bearer authentication.

Typical auth flow:

1. `POST /api/auth/token/` to get `access` and `refresh`.
2. Use `Authorization: Bearer <access_token>` for protected endpoints.
3. Use `POST /api/auth/token/refresh/` when access expires.

## Main API Endpoints

Auth:

- `POST /api/auth/register/`
- `POST /api/auth/token/`
- `POST /api/auth/token/refresh/`
- `POST /api/auth/token/verify/`
- `POST /api/auth/logout/`
- `GET/PATCH /api/auth/me/`
- `POST /api/auth/me/change-password/`
- `POST /api/auth/password-reset/`
- `POST /api/auth/password-reset/confirm/`

Medicines:

- `GET /api/medicines/`
- `GET /api/medicines/?search=panadol`
- `GET /api/medicines/{id}/`
- `GET /api/medicines/{id}/interactions/`

OCR:

- `POST /api/uploads/ocr-search/`

Reminders:

- `GET/POST /api/reminders/`
- `GET/PATCH/DELETE /api/reminders/{id}/`
- `GET/POST /api/reminders/{id}/events/`

Medical record:

- `GET/PATCH/PUT /api/medical-record/`
- `GET /api/medical-record/summary/`
- `GET/POST /api/medical-record/diagnoses/`
- `GET/POST /api/medical-record/allergies/`
- `GET/POST /api/medical-record/vitals/`
- `GET/POST /api/medical-record/lab-results/`
- `GET/POST /api/medical-record/visits/`

## OCR Search Behavior Notes

- If `drug_detector.pt` is missing, the API automatically falls back to full-image OCR.
- OCR extracts phrase/token candidates, then fuzzy-matches against medicine names.
- Token fallback is still evaluated even if the phrase match is weak.
- Response includes:
  - `match_confidence_tier`: `high`, `medium`, or `low`
  - `action_hint`: `show_results` or `retake_photo`

## OCR Search Example (API)

```bash
curl -X POST "http://127.0.0.1:8000/api/uploads/ocr-search/" \
  -H "Authorization: Bearer <access_token>" \
  -F "image=@sample_medicine.png" \
  -F "top_k=5"
```

Example response:

```json
{
  "ocr_raw_text": "Panadol Extra",
  "ocr_confidence": 0.82,
  "ocr_angle": 0,
  "ocr_engine": "easyocr",
  "ocr_tokens": ["Panadol Extra", "Panadol", "Extra"],
  "matches": [
    {
      "id": 2,
      "trade_name": "Panadol Extra",
      "active_ingredient": "Paracetamol + Caffeine",
      "strength": "500 mg + 65 mg",
      "dosage_form": "tablet",
      "name": "Panadol Extra",
      "score": 0.95,
      "matched_query": "Panadol Extra"
    }
  ],
  "match_confidence_tier": "high",
  "action_hint": "show_results",
  "message": ""
}
```

## Local CLI Without Django

Use local OCR + fuzzy search directly on an image and CSV:

```bash
python cli_ocr_search.py sample_medicine.png --catalog medicines.csv --column trade_name
```

## YOLO (Optional)

- Train using `mazen_first_(2)_(4).ipynb`.
- Store Roboflow key in env var instead of hardcoding:

```bash
export ROBOFLOW_API_KEY="your_key_here"
```

- Place trained `drug_detector.pt` in project root (or update `YOLO_MODEL_PATH` in settings).

## Postman

Import:

- `postman/Medicine_OCR_API.postman_collection.json`
- `postman/Medicine_OCR_API.postman_environment.json`

## Common Issues

1. `ModuleNotFoundError: No module named 'django'`
   - Activate venv: `source .venv/bin/activate`
   - Install deps: `pip install -r requirements.txt`

2. Tesseract missing
   - Install system package (macOS: `brew install tesseract`)

3. OCR returns empty matches
   - Ensure medicines are imported.
   - Use a clearer image.
   - Try higher `top_k`.

4. `YOLO model not found` warning
   - Normal when `drug_detector.pt` is unavailable.
   - Full-image OCR fallback is used automatically.
