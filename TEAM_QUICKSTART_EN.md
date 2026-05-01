# OCR Medicine Backend - Team Quickstart (English)

Language: [English](TEAM_QUICKSTART_EN.md) | [العربية](TEAM_QUICKSTART_AR.md)

This file helps any teammate run the project from scratch, test OCR search, and verify output quickly.

## 1) Prerequisites

- macOS or Linux
- Python 3.11 or 3.12
- `pip`
- `tesseract` (system package)

macOS:

```bash
brew install tesseract
```

## 2) First-Time Environment Setup

From project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3) Database and Seed Data

```bash
python3 manage.py migrate
python3 manage.py import_medicines --path medicines.csv
```

Note: `import_medicines` performs create/update by `trade_name`.

## 4) Run Backend

```bash
python3 manage.py runserver 127.0.0.1:8000
```

API base URL:

```text
http://127.0.0.1:8000/api/
```

## 5) Routing and API Docs

- `GET /` -> `302` redirect to `/api/docs/`
- `GET /api/docs/` Swagger UI
- `GET /api/schema/` OpenAPI schema
- `GET /api/redoc/` ReDoc

## 6) Authentication

Most endpoints are protected and require JWT Bearer auth.

Get token:

```bash
curl -X POST "http://127.0.0.1:8000/api/auth/token/" \
  -H "Content-Type: application/json" \
  -d '{"username":"<username>","password":"<password>"}'
```

Use access token:

```text
Authorization: Bearer <access_token>
```

## 7) Key Endpoints

- `GET /api/medicines/`
- `GET /api/medicines/?search=panadol`
- `GET /api/medicines/{id}/`
- `GET /api/medicines/{id}/interactions/`
- `POST /api/uploads/ocr-search/`
- `GET/POST /api/reminders/`
- `PATCH/DELETE /api/reminders/{id}/`
- `GET/POST /api/reminders/{id}/events/`
- `GET/PATCH/PUT /api/medical-record/`
- `GET /api/medical-record/summary/`

## 8) OCR Search Test from Terminal

```bash
curl -X POST "http://127.0.0.1:8000/api/uploads/ocr-search/" \
  -H "Authorization: Bearer <access_token>" \
  -F "image=@sample_medicine.png" \
  -F "top_k=5"
```

Expected response shape includes:

- `ocr_raw_text`
- `ocr_confidence`
- `ocr_tokens`
- `matches`
- `match_confidence_tier` (`high|medium|low`)
- `action_hint` (`show_results|retake_photo`)

## 9) OCR Behavior Notes

- If `drug_detector.pt` is missing, full-image OCR fallback is used automatically.
- OCR tries phrase and token matching, and token fallback still runs when phrase confidence is weak.

## 10) CLI OCR Without Django

```bash
python3 cli_ocr_search.py sample_medicine.png --catalog medicines.csv --column trade_name
```

Useful for quick OCR/fuzzy checks without starting the server.

## 11) Postman

Import both files:

- `postman/Medicine_OCR_API.postman_collection.json`
- `postman/Medicine_OCR_API.postman_environment.json`

## 12) YOLO (Optional)

If you have a trained model (`drug_detector.pt`):

- Place it in project root next to `manage.py`, or
- Update `YOLO_MODEL_PATH` in `medicine_backend/settings.py`

## 13) Common Issues

1. `ModuleNotFoundError: No module named 'django'`
   - Activate venv: `source .venv/bin/activate`
   - Install deps: `pip install -r requirements.txt`

2. Tesseract not found
   - Install it at system level (`brew install tesseract` on macOS)

3. OCR returns empty `matches`
   - Confirm `medicines.csv` was imported.
   - Use a clearer image.
   - Try higher `top_k` (for example 10).

4. `YOLO model not found`
   - Normal when `drug_detector.pt` is absent.
   - System continues with full-image OCR fallback.

## 14) Quick Delivery Check

```bash
python3 manage.py migrate
python3 manage.py import_medicines --path medicines.csv
python3 manage.py runserver 127.0.0.1:8000
```

Then in another terminal:

```bash
curl -X POST "http://127.0.0.1:8000/api/uploads/ocr-search/" \
  -H "Authorization: Bearer <access_token>" \
  -F "image=@sample_medicine.png" \
  -F "top_k=5"
```
