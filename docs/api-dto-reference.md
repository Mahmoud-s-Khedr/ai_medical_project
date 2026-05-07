# API DTO Reference

Base prefix: `/api/`.

This file documents all actively routed API endpoints and their request/response DTOs as implemented in code.

## Conventions

- Auth modes:
  - `None` = no authentication required.
  - `JWT` = `Authorization: Bearer <access_token>`.
  - `API Key` = `X-API-Key: <raw_api_key>`.
- `required` column applies to the endpoint input/output contract.
- DRF validation errors are represented as field-keyed objects where values are error message arrays/strings.

## Shared DTOs

### `Medicine`

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | read-only |
| trade_name | string | yes | unique |
| active_ingredient | string | yes | may be empty string |
| strength | string | yes | may be empty string |
| dosage_form | string | yes | may be empty string |
| drug_class | string | yes | may be empty string |
| common_side_effects | string | yes | may be empty string |
| serious_warning | string | yes | may be empty string |
| similar_active_ingredients | string | yes | may be empty string |
| similarity_risk_symptoms | string | yes | may be empty string |
| switching_note | string | yes | may be empty string |
| interaction_notes | string | yes | may be empty string |
| created_at | datetime | yes | read-only |
| updated_at | datetime | yes | read-only |

### `MedicineHistoryEntry`

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | read-only |
| user | integer | yes | read-only |
| medicine | integer \| null | yes | read-only |
| medicine_id | integer \| null | no | write-only; maps to `medicine` |
| medicine_details | `Medicine` \| null | yes | read-only |
| medicine_name | string | yes | |
| status | enum(`current`,`past`) | yes | `current` requires `end_date=null` |
| dose | string | yes | may be empty string |
| start_date | date \| null | yes | |
| end_date | date \| null | yes | must be >= `start_date` if both exist |
| notes | string | yes | may be empty string |
| created_at | datetime | yes | read-only |
| updated_at | datetime | yes | read-only |

### `DeveloperApp`

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | read-only |
| name | string | yes | unique per owner |
| description | string | yes | may be empty string |
| is_active | boolean | yes | |
| created_at | datetime | yes | read-only |
| updated_at | datetime | yes | read-only |

### `DeveloperApiKey`

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | read-only |
| app | integer | yes | read-only |
| app_id | integer | no | write-only input field |
| name | string | yes | unique per app |
| key_prefix | string | yes | read-only |
| last_used_at | datetime \| null | yes | read-only |
| revoked_at | datetime \| null | yes | read-only |
| created_at | datetime | yes | read-only |

### `DataAccessRequest`

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | read-only |
| app | integer | yes | |
| app_name | string | yes | read-only |
| requester_username | string | yes | read-only |
| target_user | integer | yes | |
| target_username | string | yes | read-only |
| status | enum(`pending`,`approved`,`rejected`,`revoked`) | yes | |
| purpose | string | yes | may be empty string |
| requested_at | datetime | yes | read-only |
| decided_at | datetime \| null | yes | read-only |
| decision_note | string | yes | may be empty string |

### Paginated Envelope (`StandardPagination`)

| field | type | required | notes |
|---|---|---|---|
| count | integer | yes | total items |
| total_pages | integer | yes | |
| next | string \| null | yes | absolute URL or null |
| previous | string \| null | yes | absolute URL or null |
| results | array | yes | item type depends on endpoint |

## Documentation/Schema Endpoints

### `GET /api/schema/`

- Auth mode: `None`

Request Body DTO: none  
Query DTO: none  
Path DTO: none

Success Response DTO:
- `200`: OpenAPI schema document (`application/json` by default).

Error Response DTO:
- Not explicitly customized in code.

### `GET /api/docs/`

- Auth mode: `None`

Request Body DTO: none  
Query DTO: none  
Path DTO: none

Success Response DTO:
- `200`: Swagger UI HTML page.

Error Response DTO:
- Not explicitly customized in code.

### `GET /api/redoc/`

- Auth mode: `None`

Request Body DTO: none  
Query DTO: none  
Path DTO: none

Success Response DTO:
- `200`: ReDoc HTML page.

Error Response DTO:
- Not explicitly customized in code.

## Auth Endpoints (`/api/auth/`)

### `POST /api/auth/register/`

- Auth mode: `None`

Request Body DTO:

| field | type | required | notes |
|---|---|---|---|
| username | string | yes | |
| email | string (email) | yes | must be unique (case-insensitive) |
| first_name | string | no | |
| last_name | string | no | |
| password | string | yes | Django password validators apply |
| password2 | string | yes | must match `password` |

Query DTO: none  
Path DTO: none

Success Response DTO:
- `201`:

| field | type | required | notes |
|---|---|---|---|
| user | object | yes | user profile DTO |
| access | string | yes | JWT access token |
| refresh | string | yes | JWT refresh token |

`user` object fields:

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | |
| username | string | yes | |
| email | string | yes | |
| first_name | string | yes | may be empty string |
| last_name | string | yes | may be empty string |
| date_joined | datetime | yes | |
| last_login | datetime \| null | yes | |

Error Response DTO:
- `400`: validation object (e.g., duplicate email, password mismatch, password policy).

### `POST /api/auth/token/`

- Auth mode: `None`

Request Body DTO (SimpleJWT default):

| field | type | required | notes |
|---|---|---|---|
| username | string | yes | default auth field |
| password | string | yes | |

Query DTO: none  
Path DTO: none

Success Response DTO:
- `200`:

| field | type | required | notes |
|---|---|---|---|
| access | string | yes | JWT access token |
| refresh | string | yes | JWT refresh token |

Error Response DTO:
- `401`: invalid credentials response.

### `POST /api/auth/token/refresh/`

- Auth mode: `None`

Request Body DTO (SimpleJWT default):

| field | type | required | notes |
|---|---|---|---|
| refresh | string | yes | refresh token |

Query DTO: none  
Path DTO: none

Success Response DTO:
- `200`:

| field | type | required | notes |
|---|---|---|---|
| access | string | yes | new JWT access token |

Error Response DTO:
- `401`: invalid/expired refresh token.

### `POST /api/auth/token/verify/`

- Auth mode: `None`

Request Body DTO (SimpleJWT default):

| field | type | required | notes |
|---|---|---|---|
| token | string | yes | JWT to verify |

Query DTO: none  
Path DTO: none

Success Response DTO:
- `200`: empty object `{}`.

Error Response DTO:
- `401`: invalid/expired token.

### `POST /api/auth/logout/`

- Auth mode: `JWT`

Request Body DTO:

| field | type | required | notes |
|---|---|---|---|
| refresh | string | yes | refresh token to blacklist |

Query DTO: none  
Path DTO: none

Success Response DTO:
- `200`:

| field | type | required | notes |
|---|---|---|---|
| detail | string | yes | `Successfully logged out.` |

Error Response DTO:
- `400`: `{ "detail": "refresh token is required." }` or `{ "detail": "Invalid or expired token." }`.
- `401`: missing/invalid JWT.

### `GET /api/auth/me/`

- Auth mode: `JWT`

Request Body DTO: none  
Query DTO: none  
Path DTO: none

Success Response DTO:
- `200`: user profile DTO (same fields as `register` response `user`).

Error Response DTO:
- `401`: missing/invalid JWT.

### `PATCH /api/auth/me/`

- Auth mode: `JWT`

Request Body DTO:

| field | type | required | notes |
|---|---|---|---|
| email | string (email) | no | unique (case-insensitive), normalized lower-case |
| first_name | string | no | |
| last_name | string | no | |

Query DTO: none  
Path DTO: none

Success Response DTO:
- `200`: user profile DTO.

Error Response DTO:
- `400`: validation object.
- `401`: missing/invalid JWT.

### `POST /api/auth/me/change-password/`

- Auth mode: `JWT`

Request Body DTO:

| field | type | required | notes |
|---|---|---|---|
| old_password | string | yes | must match current password |
| new_password | string | yes | Django password validators apply |
| new_password2 | string | yes | must match `new_password` |

Query DTO: none  
Path DTO: none

Success Response DTO:
- `200`:

| field | type | required | notes |
|---|---|---|---|
| detail | string | yes | `Password changed successfully.` |

Error Response DTO:
- `400`: validation object or `{ "old_password": "Incorrect password." }`.
- `401`: missing/invalid JWT.

### `POST /api/auth/password-reset/`

- Auth mode: `None`

Request Body DTO:

| field | type | required | notes |
|---|---|---|---|
| email | string (email) | yes | |

Query DTO: none  
Path DTO: none

Success Response DTO:
- `200`:

| field | type | required | notes |
|---|---|---|---|
| detail | string | yes | generic success message regardless of account existence |

Error Response DTO:
- `400`: validation object.

### `POST /api/auth/password-reset/confirm/`

- Auth mode: `None`

Request Body DTO:

| field | type | required | notes |
|---|---|---|---|
| uid | string | yes | base64 user id |
| token | string | yes | reset token |
| new_password | string | yes | Django password validators apply |
| new_password2 | string | yes | must match `new_password` |

Query DTO: none  
Path DTO: none

Success Response DTO:
- `200`:

| field | type | required | notes |
|---|---|---|---|
| detail | string | yes | `Password reset successfully. You can now log in.` |

Error Response DTO:
- `400`: validation object, `{ "detail": "Invalid reset link." }`, `{ "detail": "Invalid or expired reset link." }`, or `{ "new_password": ["..."] }`.

## Medicines Endpoints

### `GET /api/medicines/`

- Auth mode: `JWT`

Request Body DTO: none

Query DTO:

| field | type | required | notes |
|---|---|---|---|
| search | string | no | ranked search across medicine catalog |

Path DTO: none

Success Response DTO:
- `200`: array of `Medicine`.

Error Response DTO:
- `401`: missing/invalid JWT.

### `POST /api/medicines/`

- Auth mode: `JWT` (staff/admin write permission)

Request Body DTO:
- `Medicine` writable fields:

| field | type | required | notes |
|---|---|---|---|
| trade_name | string | yes | unique |
| active_ingredient | string | no | defaults to empty string |
| strength | string | no | defaults to empty string |
| dosage_form | string | no | defaults to empty string |
| drug_class | string | no | defaults to empty string |
| common_side_effects | string | no | defaults to empty string |
| serious_warning | string | no | defaults to empty string |
| similar_active_ingredients | string | no | defaults to empty string |
| similarity_risk_symptoms | string | no | defaults to empty string |
| switching_note | string | no | defaults to empty string |
| interaction_notes | string | no | defaults to empty string |

Query DTO: none  
Path DTO: none

Success Response DTO:
- `201`: `Medicine`.

Error Response DTO:
- `400`: validation object.
- `401`: missing/invalid JWT.
- `403`: authenticated but not allowed to write.

### `GET /api/medicines/{id}/`

- Auth mode: `JWT`

Request Body DTO: none  
Query DTO: none

Path DTO:

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | medicine id |

Success Response DTO:
- `200`: `Medicine`.

Error Response DTO:
- `401`: missing/invalid JWT.
- `404`: not found.

### `PATCH /api/medicines/{id}/`

- Auth mode: `JWT` (staff/admin write permission)

Request Body DTO:
- Partial `Medicine` writable fields (same as create writable fields).

Query DTO: none

Path DTO:

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | medicine id |

Success Response DTO:
- `200`: `Medicine`.

Error Response DTO:
- `400`: validation object.
- `401`: missing/invalid JWT.
- `403`: authenticated but not allowed to write.
- `404`: not found.

### `PUT /api/medicines/{id}/`

- Auth mode: `JWT` (staff/admin write permission)

Request Body DTO:
- Full `Medicine` writable fields (same shape as create).

Query DTO: none

Path DTO:

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | medicine id |

Success Response DTO:
- `200`: `Medicine`.

Error Response DTO:
- `400`: validation object.
- `401`: missing/invalid JWT.
- `403`: authenticated but not allowed to write.
- `404`: not found.

### `DELETE /api/medicines/{id}/`

- Auth mode: `JWT` (staff/admin write permission)

Request Body DTO: none  
Query DTO: none

Path DTO:

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | medicine id |

Success Response DTO:
- `204`: empty body.

Error Response DTO:
- `401`: missing/invalid JWT.
- `403`: authenticated but not allowed to write.
- `404`: not found.

### `GET /api/medicines/{id}/interactions/`

- Auth mode: `JWT`

Request Body DTO: none  
Query DTO: none

Path DTO:

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | medicine id |

Success Response DTO:
- `200`:

| field | type | required | notes |
|---|---|---|---|
| medicine | `Medicine` | yes | requested medicine |
| interaction_notes | string | yes | copied from medicine |
| similarity_risk_symptoms | string | yes | copied from medicine |
| switching_note | string | yes | copied from medicine |
| total_conflicts | integer | yes | |
| conflicts | array | yes | list of conflict objects |

`conflicts[]` object:

| field | type | required | notes |
|---|---|---|---|
| conflict_type | enum(`same_active_ingredient`,`similar_active_ingredient`) | yes | |
| risk_level | enum(`high`,`medium`) | yes | |
| conflict_reason | string | yes | |
| matched_ingredient | string | yes | |
| medicine | `Medicine` | yes | conflicting medicine |

Error Response DTO:
- `401`: missing/invalid JWT.
- `404`: medicine not found.

## OCR Endpoint

### `POST /api/uploads/ocr-search/`

- Auth mode: `JWT`

Request Body DTO (`multipart/form-data`):

| field | type | required | notes |
|---|---|---|---|
| image | file | yes | image upload |
| top_k | integer | no | clamped to `1..20`; default from settings |

Query DTO: none  
Path DTO: none

Success Response DTO:
- `200`:

| field | type | required | notes |
|---|---|---|---|
| ocr_confidence | number | yes | OCR confidence |
| matched_items | array | yes | list of medicine matches (possibly empty) |
| match_confidence_tier | enum(`high`,`medium`,`low`) | yes | |
| action_hint | enum(`show_results`,`retake_photo`) | yes | |
| message | string | yes | empty or retake guidance |
| processing_time_ms | number | yes | |

`matched_items[]` object:
- Includes `Medicine` fields plus:

| field | type | required | notes |
|---|---|---|---|
| name | string | yes | same as `trade_name` |
| score | number | yes | ranking score |
| _rank_score | number | conditional | present when debug enabled |
| matched_query | string | conditional | present when debug enabled |
| debug_length_factor | number | conditional | present when debug enabled |
| debug_length_ratio | number | conditional | present when debug enabled |
| debug_query_length | integer | conditional | present when debug enabled |
| debug_matched_length | integer | conditional | present when debug enabled |

Error Response DTO:
- `400`: `{ "error": "No image provided..." }`, `{ "error": "top_k must be an integer." }`, or decode error message.
- `401`: missing/invalid JWT.
- `413`: `{ "error": "Uploaded image exceeds size limit (...) bytes." }`.
- `500`: `{ "error": "OCR processing failed. Please try again." }`.

## Text-to-Speech Endpoint

### `POST /api/tts/speak/`

- Auth mode: `JWT`

Request Body DTO:

| field | type | required | notes |
|---|---|---|---|
| text | string | yes | trimmed + normalized; must be non-empty; max length `TTS_MAX_CHARS` |
| voice | string | no | max 80 chars; when provided, forces `mixed_mode=single_voice` |
| voice_ar | string | no | max 80 chars; used for Arabic runs when `mixed_mode=dual_voice` |
| voice_en | string | no | max 80 chars; used for English runs when `mixed_mode=dual_voice` |
| rate | string | no | format: `[+-]\d{1,3}%` (e.g., `+10%`, `-5%`) |
| mixed_mode | enum(`single_voice`,`dual_voice`) | no | default from `TTS_MIXED_MODE_DEFAULT` |

Query DTO: none  
Path DTO: none

Success Response DTO:
- `200`: MP3 audio bytes (`Content-Type: audio/mpeg`)

Response Headers:
- `Content-Disposition: inline; filename="speech.mp3"`
- `Cache-Control: no-store`

Error Response DTO:
- `400`: validation object (e.g., invalid `rate`, `mixed_mode`, text too long, or too many mixed segments).
- `401`: missing/invalid JWT.
- `503`: `{ "detail": "Text-to-speech service is temporarily unavailable." }` or `{ "detail": "Text-to-speech service returned empty audio." }`.

## Medicine History Endpoints

### `GET /api/medicine-history/`

- Auth mode: `JWT`

Request Body DTO: none

Query DTO:

| field | type | required | notes |
|---|---|---|---|
| status | enum(`current`,`past`) | no | if provided and valid, filter applied |
| start_date_from | date | no | filter `start_date >= value` |
| start_date_to | date | no | filter `start_date <= value` |
| end_date_from | date | no | filter `end_date >= value` |
| end_date_to | date | no | filter `end_date <= value` |

Path DTO: none

Success Response DTO:
- `200`: array of `MedicineHistoryEntry` (user-scoped).

Error Response DTO:
- `401`: missing/invalid JWT.

### `POST /api/medicine-history/`

- Auth mode: `JWT`

Request Body DTO (`MedicineHistoryEntry` writable fields):

| field | type | required | notes |
|---|---|---|---|
| medicine_id | integer \| null | no | links to medicine |
| medicine_name | string | yes | |
| status | enum(`current`,`past`) | no | defaults to `current` |
| dose | string | no | defaults to empty string |
| start_date | date \| null | no | |
| end_date | date \| null | no | invalid when `status=current` |
| notes | string | no | defaults to empty string |

Query DTO: none  
Path DTO: none

Success Response DTO:
- `201`: `MedicineHistoryEntry`.

Error Response DTO:
- `400`: validation object.
- `401`: missing/invalid JWT.

### `GET /api/medicine-history/{id}/`

- Auth mode: `JWT`

Request Body DTO: none  
Query DTO: none

Path DTO:

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | history entry id (must belong to current user) |

Success Response DTO:
- `200`: `MedicineHistoryEntry`.

Error Response DTO:
- `401`: missing/invalid JWT.
- `404`: not found for current user.

### `PATCH /api/medicine-history/{id}/`

- Auth mode: `JWT`

Request Body DTO:
- Partial `MedicineHistoryEntry` writable fields.

Query DTO: none

Path DTO:

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | history entry id |

Success Response DTO:
- `200`: `MedicineHistoryEntry`.

Error Response DTO:
- `400`: validation object.
- `401`: missing/invalid JWT.
- `404`: not found for current user.

### `PUT /api/medicine-history/{id}/`

- Auth mode: `JWT`

Request Body DTO:
- Full `MedicineHistoryEntry` writable fields.

Query DTO: none

Path DTO:

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | history entry id |

Success Response DTO:
- `200`: `MedicineHistoryEntry`.

Error Response DTO:
- `400`: validation object.
- `401`: missing/invalid JWT.
- `404`: not found for current user.

### `DELETE /api/medicine-history/{id}/`

- Auth mode: `JWT`

Request Body DTO: none  
Query DTO: none

Path DTO:

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | history entry id |

Success Response DTO:
- `204`: empty body.

Error Response DTO:
- `401`: missing/invalid JWT.
- `404`: not found for current user.

## Integration Management Endpoints (`/api/integrations/...`)

### `GET /api/integrations/apps/`

- Auth mode: `JWT`

Request Body DTO: none  
Query DTO: none  
Path DTO: none

Success Response DTO:
- `200`: array of `DeveloperApp` (owned by current user).

Error Response DTO:
- `401`: missing/invalid JWT.

### `POST /api/integrations/apps/`

- Auth mode: `JWT`

Request Body DTO (`DeveloperApp` writable fields):

| field | type | required | notes |
|---|---|---|---|
| name | string | yes | unique per current user |
| description | string | no | defaults to empty string |
| is_active | boolean | no | defaults to `true` |

Query DTO: none  
Path DTO: none

Success Response DTO:
- `201`: `DeveloperApp`.

Error Response DTO:
- `400`: validation object.
- `401`: missing/invalid JWT.

### `GET /api/integrations/apps/{id}/`

- Auth mode: `JWT`

Request Body DTO: none  
Query DTO: none

Path DTO:

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | app id owned by current user |

Success Response DTO:
- `200`: `DeveloperApp`.

Error Response DTO:
- `401`: missing/invalid JWT.
- `404`: not found.

### `PATCH /api/integrations/apps/{id}/`

- Auth mode: `JWT`

Request Body DTO:
- Partial `DeveloperApp` writable fields.

Query DTO: none

Path DTO:

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | app id |

Success Response DTO:
- `200`: `DeveloperApp`.

Error Response DTO:
- `400`: validation object.
- `401`: missing/invalid JWT.
- `404`: not found.

### `PUT /api/integrations/apps/{id}/`

- Auth mode: `JWT`

Request Body DTO:
- Full `DeveloperApp` writable fields.

Query DTO: none

Path DTO:

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | app id |

Success Response DTO:
- `200`: `DeveloperApp`.

Error Response DTO:
- `400`: validation object.
- `401`: missing/invalid JWT.
- `404`: not found.

### `DELETE /api/integrations/apps/{id}/`

- Auth mode: `JWT`

Request Body DTO: none  
Query DTO: none

Path DTO:

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | app id |

Success Response DTO:
- `204`: empty body.

Error Response DTO:
- `401`: missing/invalid JWT.
- `404`: not found.

### `GET /api/integrations/keys/`

- Auth mode: `JWT`

Request Body DTO: none  
Query DTO: none  
Path DTO: none

Success Response DTO:
- `200`: array of `DeveloperApiKey` for apps owned by current user.

Error Response DTO:
- `401`: missing/invalid JWT.

### `POST /api/integrations/keys/`

- Auth mode: `JWT`

Request Body DTO:

| field | type | required | notes |
|---|---|---|---|
| app_id | integer | yes | must be owned by current user |
| name | string | yes | unique per app |

Query DTO: none  
Path DTO: none

Success Response DTO:
- `201` (`DeveloperApiKey` + one-time secret):

| field | type | required | notes |
|---|---|---|---|
| id | integer | yes | |
| app | integer | yes | |
| name | string | yes | |
| key_prefix | string | yes | |
| last_used_at | datetime \| null | yes | |
| revoked_at | datetime \| null | yes | |
| created_at | datetime | yes | |
| api_key | string | yes | raw key returned once only |

Error Response DTO:
- `400`: validation object (including ownership check failure).
- `401`: missing/invalid JWT.

### `POST /api/integrations/keys/{key_id}/revoke/`

- Auth mode: `JWT`

Request Body DTO: none  
Query DTO: none

Path DTO:

| field | type | required | notes |
|---|---|---|---|
| key_id | integer | yes | key id belonging to current user |

Success Response DTO:
- `200`:

| field | type | required | notes |
|---|---|---|---|
| detail | string | yes | `API key revoked.` |

Error Response DTO:
- `401`: missing/invalid JWT.
- `404`: `{ "detail": "Not found." }`.

### `GET /api/integrations/access-requests/inbox/`

- Auth mode: `JWT`

Request Body DTO: none  
Query DTO: none  
Path DTO: none

Success Response DTO:
- `200`: array of `DataAccessRequest` where `target_user` is current user.

Error Response DTO:
- `401`: missing/invalid JWT.

### `POST /api/integrations/access-requests/{request_id}/{decision}/`

- Auth mode: `JWT`

Request Body DTO:

| field | type | required | notes |
|---|---|---|---|
| decision_note | string | no | max length 255 |

Query DTO: none

Path DTO:

| field | type | required | notes |
|---|---|---|---|
| request_id | integer | yes | request targeting current user |
| decision | enum(`approve`,`reject`,`revoke`) | yes | other values return 400 |

Success Response DTO:
- `200`: `DataAccessRequest` (updated status and decision metadata).

Error Response DTO:
- `400`: validation object or `{ "detail": "Invalid decision." }`.
- `401`: missing/invalid JWT.
- `404`: `{ "detail": "Not found." }`.

### `GET /api/integrations/medicine-history/export.xml`

- Auth mode: `JWT`

Request Body DTO: none  
Query DTO: none  
Path DTO: none

Success Response DTO:
- `200`: XML attachment (`application/xml; charset=utf-8`) containing current user's medicine history.

Error Response DTO:
- `401`: missing/invalid JWT.

## External API-Key Endpoints (`/api/external/...`)

### `POST /api/external/access-requests/`

- Auth mode: `API Key`

Request Body DTO:

| field | type | required | notes |
|---|---|---|---|
| username | string | yes | target username must exist |
| purpose | string | no | max length 255; may be empty |

Query DTO: none  
Path DTO: none

Success Response DTO:
- `201`: `DataAccessRequest`.

Error Response DTO:
- `400`: validation object (e.g., unknown username).
- `401`: missing/invalid/revoked API key.
- `409`: `{ "detail": "An active request already exists for this user and app." }`.

### `GET /api/external/medicine-history/{username}/`

- Auth mode: `API Key`

Request Body DTO: none

Query DTO:

| field | type | required | notes |
|---|---|---|---|
| format | enum(`json`,`xml`) | no | default `json` |
| page | integer | no | pagination page |
| page_size | integer | no | max 100 |

Path DTO:

| field | type | required | notes |
|---|---|---|---|
| username | string | yes | target username |

Success Response DTO:
- `200` JSON (default): paginated envelope with `results: MedicineHistoryEntry[]`.
- `200` XML (`format=xml`): XML document containing same paginated data shape.

Error Response DTO:
- `401`: missing/invalid/revoked API key.
- `403`: `{ "detail": "No approved access request for this user." }`.

## Route Coverage Checklist

All actively routed `/api/` endpoints from `medicine_backend/urls.py` and `api/urls.py` are covered in this file:

- `/api/schema/`, `/api/docs/`, `/api/redoc/`
- `/api/auth/*`
- `/api/medicines/*` (+ `/interactions/`)
- `/api/medicine-history/*`
- `/api/uploads/ocr-search/`
- `/api/tts/speak/`
- `/api/integrations/apps/*`
- `/api/integrations/keys/*` (+ revoke)
- `/api/integrations/access-requests/*`
- `/api/integrations/medicine-history/export.xml`
- `/api/external/access-requests/`
- `/api/external/medicine-history/{username}/`
