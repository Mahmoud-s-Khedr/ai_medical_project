# Data Model

## Core Entities

### Medicine

Model: `api.models.Medicine`

Key fields:
- `trade_name` (unique)
- `active_ingredient`
- `strength`
- `dosage_form`
- `drug_class`
- safety/context text fields: warnings, interaction/similarity notes

Used by:
- catalog listing/search
- OCR match target
- medicine-history optional foreign key
- interaction analysis endpoint

### MedicineHistoryEntry

Model: `api.models.MedicineHistoryEntry`

Key fields:
- `user` (required FK, cascade delete)
- `medicine` (optional FK, set null)
- `medicine_name` (required snapshot text)
- `status` (`current|past`)
- `dose`, `start_date`, `end_date`, `notes`

Constraints and behavior:
- `status=current` requires `end_date` to be null.
- if both dates are set then `end_date >= start_date`.
- user ownership is enforced in queryset-level scoping.

## Ordering Defaults

- `Medicine`: `trade_name` asc
- `MedicineHistoryEntry`: latest update first, then medicine name

## Migration Notes

Observed migrations in `api/migrations/`:
- `0001_initial.py`
- `0002_medicationreminder_user.py`
- `0003_medical_record.py`
- `0004_reminder_user_non_null.py`
- `0005_medicine_active_ingredient_norm_and_more.py`
- `0006_medicine_history_refactor.py`

Notable behavior verified by tests:
- migration backfills `MedicineHistoryEntry` from `MedicationReminder`, then removes reminder and medical-record tables.
