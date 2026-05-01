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
- reminder optional foreign key
- interaction analysis endpoint

### MedicationReminder

Model: `api.models.MedicationReminder`

Key fields:
- `user` (required FK, cascade delete)
- `medicine` (optional FK, set null)
- `medicine_name`, `dose`, `times` (JSON list), date range, timezone, active flag

Constraints and behavior:
- DB-level user non-null (see migrations).
- user ownership is enforced in queryset-level scoping.

### ReminderEvent

Model: `api.models.ReminderEvent`

Key fields:
- `reminder` FK
- `scheduled_at`
- `status`: `scheduled|taken|missed|skipped`
- `taken_at` optional but required by serializer when `status=taken`

### MedicalRecord Family

Root model: `MedicalRecord` (one-to-one with user).

Child collections:
- `Diagnosis`
- `Allergy`
- `VitalSign`
- `LabResult`
- `DoctorVisit`

All children are linked to `MedicalRecord` and accessed only through record-scoped viewsets.

## Ordering Defaults

- `Medicine`: `trade_name` asc
- `MedicationReminder`: active first, then `start_date`, then name
- `ReminderEvent`: latest scheduled first
- `Diagnosis`: latest diagnosis date first
- `VitalSign`: latest recorded first
- `LabResult`: latest date first
- `DoctorVisit`: latest visit first

## Migration Notes

Observed migrations in `api/migrations/`:
- `0001_initial.py`
- `0002_medicationreminder_user.py`
- `0003_medical_record.py`
- `0004_reminder_user_non_null.py`

Notable behavior verified by tests:
- migration path handles orphan reminders before enforcing non-null reminder user.
