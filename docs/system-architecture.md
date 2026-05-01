# System Architecture

## Purpose and Scope

This service provides medicine OCR lookup, medicine catalog APIs, medication reminders, and user medical-record APIs over Django REST Framework with JWT authentication.

## Runtime Components

- `medicine_backend/settings.py`: global configuration, DRF defaults, throttling, auth, OCR/search tunables.
- `medicine_backend/urls.py`: root routing, schema/docs, demo routes.
- `api/`: models, serializers, auth views, business views, medical views, routing.
- `ai/ocr_pipeline.py`: image preprocessing, rotation strategy, OCR engine orchestration.

## Request Flows

### 1. OCR Search (`POST /api/uploads/ocr-search/`)

1. Request requires JWT (`IsAuthenticated`) and multipart `image`.
2. Upload size checked against `OCR_MAX_UPLOAD_BYTES`.
3. PIL decode/safety guard (`Image.MAX_IMAGE_PIXELS=40_000_000`).
4. Crop selection:
- YOLO path if `drug_detector.pt` exists and loads.
- Full-image fallback on missing model/import/inference failure.
5. OCR path per crop:
- Try rotations `(0, -10, 10, -20, 20, -90, 90)`.
- Run EasyOCR first.
- Run Tesseract unless EasyOCR is already highly confident.
6. Candidate generation and fuzzy ranking against medicine catalog.
7. Response shaping with confidence tier + action hint.

### 2. Medicines API

- `MedicineViewSet` supports list/detail CRUD with `IsAdminOrReadOnly`.
- Read allowed to authenticated users.
- Write operations restricted to `is_staff=True` users.
- List search uses hybrid ranker from `api/search.py`.

### 3. Reminders and Events

- `MedicationReminderViewSet` is user-scoped (`filter(user=request.user)`).
- Reminder events are nested under reminder route and inherit reminder ownership checks.

### 4. Medical Record

- One medical record per user (`OneToOneField`).
- `_get_or_create_record()` auto-creates record on first access.
- Child resources (diagnoses/allergies/vitals/labs/visits) are viewset-scoped to current user’s record.

### 5. Auth and Identity

- Registration returns JWT pair.
- JWT lifecycle handled by SimpleJWT endpoints (obtain/refresh/verify).
- Logout blacklists refresh token.
- Password reset flow uses tokenized link generation and confirmation endpoint.

## Non-API Supporting Surfaces

- `api/management/commands/import_medicines.py`: CSV upsert into `Medicine`.
- `cli_ocr_search.py`: local OCR + fuzzy flow without Django server.
- `tools/evaluate_ocr.py`: labeled-set offline precision evaluator.
- `api/templates/demo/index.html` + `api/static/demo/*`: demo UI integrated with API.
