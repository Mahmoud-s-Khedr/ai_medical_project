# API Contracts

Base prefix: `/api/`
Auth style: `Authorization: Bearer <access_token>` unless endpoint is public.

## Auth Endpoints

- `POST /api/auth/register/` public, throttled (`scope=auth`), returns `user + access + refresh`.
- `POST /api/auth/token/` public, returns JWT pair.
- `POST /api/auth/token/refresh/` public.
- `POST /api/auth/token/verify/` public.
- `POST /api/auth/logout/` authenticated, requires `refresh` in body.
- `GET /api/auth/me/` authenticated, returns profile.
- `PATCH /api/auth/me/` authenticated, updates mutable user fields.
- `POST /api/auth/me/change-password/` authenticated, requires old/new passwords.
- `POST /api/auth/password-reset/` public, idempotent response for known/unknown email.
- `POST /api/auth/password-reset/confirm/` public, validates `uid + token + new_password`.

## Medicines

- `GET /api/medicines/` authenticated list, supports `?search=`.
- `GET /api/medicines/{id}/` authenticated detail.
- `POST/PUT/PATCH/DELETE /api/medicines/{...}` staff-only.
- `GET /api/medicines/{id}/interactions/` authenticated.

Interactions response fields:
- `medicine`
- `interaction_notes`
- `similarity_risk_symptoms`
- `switching_note`
- `total_conflicts`
- `conflicts[]` with conflict type/risk/reason/ingredient/medicine

## OCR Search

- `POST /api/uploads/ocr-search/` authenticated, multipart form-data.
- Required field: `image`.
- Optional field: `top_k` integer, clamped to range `[1, 20]`.

Error semantics:
- `400` missing image / invalid top_k / decode failure.
- `413` upload too large.
- `500` OCR processing failure.

Success body fields:
- `ocr_raw_text`
- `ocr_confidence`
- `ocr_angle`
- `ocr_engine`
- `ocr_tokens`
- `matches`
- `match_confidence_tier` (`high|medium|low`)
- `action_hint` (`show_results|retake_photo`)
- `message`

## Reminders and Events

- `GET /api/reminders/` authenticated, user-scoped.
- `POST /api/reminders/` authenticated, creates reminder owned by caller.
- `GET/PATCH/DELETE /api/reminders/{id}/` authenticated, owner-only by queryset scope.
- `GET /api/reminders/?is_active=true|false` filter.
- `GET/POST /api/reminders/{id}/events/` authenticated nested resource.

Validation notes:
- `times` must be non-empty list of `HH:MM` strings.
- `end_date` cannot be before `start_date`.
- Event with `status=taken` requires `taken_at`.

## Medical Record

- `GET/PATCH/PUT /api/medical-record/` authenticated.
- `GET /api/medical-record/summary/` authenticated.
- `GET/POST/PATCH/DELETE` scoped resources:
- `/api/medical-record/diagnoses/`
- `/api/medical-record/allergies/`
- `/api/medical-record/vitals/`
- `/api/medical-record/lab-results/`
- `/api/medical-record/visits/`

Filter params:
- Diagnoses: `?status=active|chronic|resolved`
- Allergies: `?type=drug|food|environmental|other`
- Labs: `?abnormal=true`

## Pagination and Response Shape

List endpoints use `StandardPagination`:
- `count`
- `total_pages`
- `next`
- `previous`
- `results`

`page_size` query param is supported; max page size is 100.
