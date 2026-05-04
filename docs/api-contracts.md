# API Contracts

Base prefix: `/api/`

## Route Surfaces Outside `/api/`

- `GET /` redirects (`302`) to `/api/docs/`.
- `GET /demo/` serves demo app page.
- `GET /demo/health/` serves demo health JSON.
- `GET /api/schema/` OpenAPI schema.
- `GET /api/docs/` Swagger UI.
- `GET /api/redoc/` ReDoc UI.

## Auth Modes

- JWT user/developer routes: `Authorization: Bearer <access_token>`.
- External integration routes: `X-API-Key: <raw_api_key>`.

## Auth Endpoints (`/api/auth/`)

Public (`AllowAny`):
- `POST /api/auth/register/` (`scope=auth` throttle).
- `POST /api/auth/token/`.
- `POST /api/auth/token/refresh/`.
- `POST /api/auth/token/verify/`.
- `POST /api/auth/password-reset/` (`scope=auth` throttle).
- `POST /api/auth/password-reset/confirm/` (`scope=auth` throttle).

JWT-protected:
- `POST /api/auth/logout/` body requires `refresh`.
- `GET /api/auth/me/`.
- `PATCH /api/auth/me/`.
- `POST /api/auth/me/change-password/`.

Common errors:
- `400`: validation errors (invalid payload, missing refresh, invalid reset token).
- `401`: missing/invalid JWT.
- `429`: throttled auth endpoints.

## Medicines (`/api/medicines/`)

JWT-protected:
- `GET /api/medicines/` supports `?search=`.
- `GET /api/medicines/{id}/`.
- `GET /api/medicines/{id}/interactions/`.

Staff-only writes:
- `POST /api/medicines/`
- `PUT/PATCH/DELETE /api/medicines/{id}/`

Common errors:
- `401` unauthenticated.
- `403` non-staff write attempt.

## OCR Search (`/api/uploads/ocr-search/`)

JWT-protected multipart endpoint:
- `POST /api/uploads/ocr-search/`
- Required field: `image`
- Optional field: `top_k` (int, clamped `1..20`)

Response fields:
- `ocr_confidence`
- `matched_items`
- `match_confidence_tier` (`high|medium|low`)
- `action_hint` (`show_results|retake_photo`)
- `message`
- `processing_time_ms`

Behavior:
- No OCR candidates still returns `200` with empty `matched_items` and `retake_photo` action.
- YOLO load/inference failures fall back to full-image OCR.

Common errors:
- `400` invalid image/top_k/decode.
- `413` upload too large (`OCR_MAX_UPLOAD_BYTES`).
- `500` OCR pipeline failure.

## Text-to-Speech (`/api/tts/speak/`)

JWT-protected JSON endpoint:
- `POST /api/tts/speak/`

Request body:
- `text` (required, non-empty string)
- `voice` (optional string, e.g. `en-US-JennyNeural`, `ar-EG-SalmaNeural`)
- `voice_ar` (optional, used by `dual_voice` mixed mode)
- `voice_en` (optional, used by `dual_voice` mixed mode)
- `rate` (optional string in format like `+0%`, `+10%`, `-15%`)
- `mixed_mode` (optional: `single_voice` or `dual_voice`, default from `TTS_MIXED_MODE_DEFAULT`)

Response:
- `200` with MP3 bytes (`Content-Type: audio/mpeg`)
- `Content-Disposition: inline; filename="speech.mp3"`

Mixed-language behavior:
- Server detects script profile: `arabic`, `english`, or `mixed`.
- In `mixed_mode=dual_voice`, mixed text is segmented into Arabic/English runs, neutral chars are attached to nearest run, then per-run TTS is stitched into one MP3 with short silence boundaries.
- If `voice` is omitted for single-voice flow:
  - `arabic` -> `TTS_DEFAULT_VOICE_AR`
  - `english` -> `TTS_DEFAULT_VOICE_EN`
  - `mixed` -> `TTS_DEFAULT_VOICE_MIXED` (default Arabic-capable voice)
- Text is preserved as-is (no transliteration/splitting).

Common errors:
- `400` invalid payload (empty text, invalid rate, over max chars).
- `401` unauthenticated.
- `503` TTS provider failure or timeout.

## Medicine History (`/api/medicine-history/`)

JWT-protected, user-scoped:
- `GET /api/medicine-history/`
- `POST /api/medicine-history/`
- `GET /api/medicine-history/{id}/`
- `PATCH /api/medicine-history/{id}/`
- `DELETE /api/medicine-history/{id}/`

Filters:
- `status=current|past`
- `start_date_from`, `start_date_to`
- `end_date_from`, `end_date_to`

Validation:
- `status=current` requires `end_date` null.
- If both dates are present: `end_date >= start_date`.

## Integration Management (JWT) (`/api/integrations/...`)

Developer app management:
- `GET /api/integrations/apps/`
- `POST /api/integrations/apps/`
- `GET /api/integrations/apps/{id}/`
- `PATCH /api/integrations/apps/{id}/`
- `DELETE /api/integrations/apps/{id}/`

API key management:
- `GET /api/integrations/keys/`
- `POST /api/integrations/keys/`
- `POST /api/integrations/keys/{id}/revoke/`

Consent inbox and decisions:
- `GET /api/integrations/access-requests/inbox/`
- `POST /api/integrations/access-requests/{id}/approve/`
- `POST /api/integrations/access-requests/{id}/reject/`
- `POST /api/integrations/access-requests/{id}/revoke/`

User export:
- `GET /api/integrations/medicine-history/export.xml`

Key semantics:
- `POST /api/integrations/keys/` returns generated `api_key` **once**.
- Stored key material is hashed; only prefix is persisted for display.

Example key-create response:
```json
{
  "id": 7,
  "app": 2,
  "name": "primary",
  "key_prefix": "dev_Gk2...",
  "last_used_at": null,
  "revoked_at": null,
  "created_at": "2026-05-03T18:58:10Z",
  "api_key": "dev_Gk2h...raw-secret..."
}
```

Common errors:
- `400` payload validation.
- `401` missing/invalid JWT.
- `404` key or request not found for current user.

## External Integration APIs (API Key) (`/api/external/...`)

- `POST /api/external/access-requests/`
- `GET /api/external/medicine-history/{username}/`

Access-request creation body:
- `username` (required)
- `purpose` (optional)

Example request:
```json
{
  "username": "patient1",
  "purpose": "Care coordination"
}
```

Consent lifecycle:
- `pending` -> `approved` or `rejected`
- `approved` -> `revoked`

Active-request constraint:
- only one active (`pending` or `approved`) request per `(app, user)`.
- duplicate active request returns `409`.

History fetch format:
- JSON default
- XML when `?format=xml`

Example JSON history response (paginated):
```json
{
  "count": 2,
  "total_pages": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 11,
      "medicine_name": "Panadol",
      "status": "current",
      "dose": "500mg",
      "start_date": null,
      "end_date": null,
      "notes": "",
      "created_at": "2026-05-03T19:05:00Z",
      "updated_at": "2026-05-03T19:05:00Z"
    }
  ]
}
```

Example XML response shape:
```xml
<?xml version="1.0" encoding="utf-8"?>
<medicine_history_response>
  <meta>
    <count>2</count>
    <total_pages>1</total_pages>
    <next />
    <previous />
  </meta>
  <results>
    <entry>
      <medicine_name>Panadol</medicine_name>
      <status>current</status>
    </entry>
  </results>
</medicine_history_response>
```

Common errors:
- `400` invalid body (`username` unknown, bad payload).
- `401` missing/invalid/revoked API key.
- `403` no approved access for `(app, user)`.
- `409` duplicate active access request.

## Pagination

List endpoints using `api.pagination.StandardPagination` return:
- `count`
- `total_pages`
- `next`
- `previous`
- `results`

Query parameters:
- `page`
- `page_size` (max `100`)
