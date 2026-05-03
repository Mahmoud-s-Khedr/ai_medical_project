# System Architecture

## Purpose and Scope

This service provides medicine OCR lookup, medicine catalog APIs, medicine-history tracking, and consent-gated external integration APIs over Django REST Framework.

## Runtime Components

- `medicine_backend/settings.py`: DRF defaults, auth defaults, throttling, OCR/search tunables.
- `medicine_backend/urls.py`: root routing + schema/docs + demo routes.
- `api/`: models, serializers, auth views, integration views, OCR/medicine/history views, routing.
- `ai/ocr_pipeline.py`: OCR engine orchestration and image preprocessing.

## Request Flows

### 1. OCR Search (`POST /api/uploads/ocr-search/`)

1. JWT-authenticated request with multipart `image`.
2. Upload size is validated against `OCR_MAX_UPLOAD_BYTES`.
3. PIL decode guard prevents malformed image processing.
4. Crop selection:
- YOLO detection path when a valid model can load.
- fallback to full-image OCR on missing model/import/inference/load failure.
5. OCR candidate extraction + ranked medicine search.
6. Response includes confidence tier and action hint.

### 2. Medicines and User History

- `MedicineViewSet`: authenticated read and staff-only writes.
- `MedicineHistoryViewSet`: authenticated user-scoped CRUD with filters for status/date ranges.

### 3. Auth and Identity (JWT)

- Registration returns JWT pair.
- Token obtain/refresh/verify provided by SimpleJWT endpoints.
- Logout blacklists refresh token.
- Profile and password-change endpoints are JWT-protected.
- Password reset request/confirm endpoints are public and throttled.

### 4. External Integrations (API Key + Consent)

1. Developer (JWT user) creates app and API key.
2. External system authenticates via `X-API-Key`.
3. External system submits access request for target `username`.
4. Target user reviews in-app inbox and approves/rejects/revokes.
5. External read endpoint serves medicine history only if an approved request exists for `(app, user)`.
6. External response supports JSON default and XML via `?format=xml`.

### 5. User XML Export

- Authenticated users can export their own medicine history as downloadable XML (`/api/integrations/medicine-history/export.xml`).

## Non-API Supporting Surfaces

- `api/management/commands/import_medicines.py`: CSV import/upsert for medicine catalog.
- `tools/evaluate_ocr.py`: OCR evaluation helper.
- `cli_ocr_search.py`: local OCR + ranking flow without HTTP server.
- `api/templates/demo/index.html` + `api/static/demo/*`: demo UI.
