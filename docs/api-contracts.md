# API Contracts

Base prefix: `/api/`
Auth style: `Authorization: Bearer <access_token>` unless endpoint is public.

## Route Surfaces Outside `/api/`

- `GET /` redirects (`302`) to `/api/docs/`.
- `GET /demo/` serves the demo app page.
- `GET /demo/health/` serves demo health JSON.
- `GET /api/schema/` OpenAPI schema.
- `GET /api/docs/` Swagger UI.
- `GET /api/redoc/` ReDoc UI.

## Auth Endpoints (`/api/auth/`)

Public (`AllowAny`):
- `POST /api/auth/register/` throttled (`scope=auth`), returns `user`, `access`, `refresh`.
- `POST /api/auth/token/` returns JWT pair.
- `POST /api/auth/token/refresh/`.
- `POST /api/auth/token/verify/`.
- `POST /api/auth/password-reset/` throttled (`scope=auth`), returns non-enumerating success message.
- `POST /api/auth/password-reset/confirm/` throttled (`scope=auth`).

Authenticated:
- `POST /api/auth/logout/` requires `refresh` field in body.
- `GET /api/auth/me/` returns user profile.
- `PATCH /api/auth/me/` updates mutable profile fields.
- `POST /api/auth/me/change-password/` validates old/new password rules.

Auth error semantics:
- `401` invalid/missing JWT for protected endpoints.
- `400` serializer/validation errors (for example invalid reset token, wrong old password, missing refresh token).
- `429` throttling for endpoints with `scope=auth`.

## Medicines

- `GET /api/medicines/` authenticated list, supports `?search=`.
- `GET /api/medicines/{id}/` authenticated detail.
- `POST /api/medicines/` staff-only.
- `PUT/PATCH/DELETE /api/medicines/{id}/` staff-only.
- `GET /api/medicines/{id}/interactions/` authenticated.

Interactions response fields:
- `medicine`
- `interaction_notes`
- `similarity_risk_symptoms`
- `switching_note`
- `total_conflicts`
- `conflicts[]` with `conflict_type`, `risk_level`, `conflict_reason`, `matched_ingredient`, `medicine`

Medicines error semantics:
- `401` unauthenticated access.
- `403` authenticated non-staff write attempt.

## OCR Search

- `POST /api/uploads/ocr-search/` authenticated, `multipart/form-data`.
- Required field: `image`.
- Optional field: `top_k` integer, clamped to `[1, 20]`.

Success response fields:
- `ocr_confidence`
- `matched_items`
- `match_confidence_tier` (`high|medium|low`)
- `action_hint` (`show_results|retake_photo`)
- `message`
- `processing_time_ms`

Behavior notes:
- If OCR cannot produce candidates, response is `200` with `matched_items: []`, tier=`low`, action=`retake_photo`.
- Low tier results are additionally capped by `OCR_LOW_CONFIDENCE_MAX_RESULTS`.
- YOLO model load/inference failure falls back to full-image OCR.

OCR error semantics:
- `400` missing `image`, invalid `top_k`, or image decode failure.
- `413` upload too large (greater than `OCR_MAX_UPLOAD_BYTES`).
- `500` OCR pipeline exception.

## Medicine History

- `GET /api/medicine-history/` authenticated, user-scoped.
- `POST /api/medicine-history/` authenticated, creates history entry for caller.
- `GET/PATCH/DELETE /api/medicine-history/{id}/` authenticated, owner-scoped by queryset.

Filter params:
- `?status=current|past`
- `?start_date_from=YYYY-MM-DD`
- `?start_date_to=YYYY-MM-DD`
- `?end_date_from=YYYY-MM-DD`
- `?end_date_to=YYYY-MM-DD`

Validation constraints:
- `status=current` requires `end_date` to be null.
- if both dates exist, `end_date` cannot be before `start_date`.

## Pagination

List endpoints use `api.pagination.StandardPagination`:
- `count`
- `total_pages`
- `next`
- `previous`
- `results`

Query support:
- `page`
- `page_size` (max `100`).
