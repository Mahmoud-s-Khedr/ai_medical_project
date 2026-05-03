# Data Model

## Core Entities

### Medicine

Model: `api.models.Medicine`

Key fields:
- `trade_name` (unique)
- `active_ingredient`, `strength`, `dosage_form`, `drug_class`
- search and safety/context fields (aliases, warning/interaction/similarity notes)

Used by:
- catalog listing/search
- OCR match target
- medicine-history optional FK
- interaction analysis endpoint

### MedicineHistoryEntry

Model: `api.models.MedicineHistoryEntry`

Key fields:
- `user` (required FK)
- `medicine` (optional FK)
- `medicine_name` (required snapshot text)
- `status` (`current|past`)
- `dose`, `start_date`, `end_date`, `notes`

Validation and indexing:
- `status=current` requires `end_date` null.
- if both dates exist, `end_date >= start_date`.
- indexed by `user+status` and `user+start_date`.

### DeveloperApp

Model: `api.models.DeveloperApp`

Key fields:
- `owner` (JWT user)
- `name`, `description`, `is_active`

Constraints:
- unique `(owner, name)`.

Purpose:
- ownership boundary for external integrations and API keys.

### DeveloperApiKey

Model: `api.models.DeveloperApiKey`

Key fields:
- `app`
- `name`
- `key_prefix` (display/debug)
- `key_hash` (stored secret hash)
- `last_used_at`, `revoked_at`

Constraints:
- unique `key_hash`
- unique `(app, name)`

Behavior:
- raw key returned once on creation; only hash persists.
- revoked keys are denied by API-key auth backend.

### DataAccessRequest

Model: `api.models.DataAccessRequest`

Key fields:
- `app`
- `target_user`
- `status`: `pending|approved|rejected|revoked`
- `purpose`, `requested_at`, `decided_at`, `decision_note`

Constraints and lifecycle impact:
- partial unique constraint allows at most one active (`pending` or `approved`) request per `(app, target_user)`.
- user decision drives external read authorization gate.

## Relationship Summary

- `User 1..N DeveloperApp`
- `DeveloperApp 1..N DeveloperApiKey`
- `DeveloperApp 1..N DataAccessRequest`
- `User 1..N DataAccessRequest` (as `target_user`)
- `User 1..N MedicineHistoryEntry`
- `Medicine 1..N MedicineHistoryEntry` (nullable)

## Migration Notes

Current migration chain includes integration additions:
- `0007_developerapp_developerapikey_dataaccessrequest_and_more.py`

Earlier reminder-era tables were removed during medicine-history refactor; current API route surface is based on `Medicine` + `MedicineHistoryEntry` + integration entities above.
