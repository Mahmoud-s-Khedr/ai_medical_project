# Verification Evidence

Verification date: 2026-05-01
Environment: local repo state in `/home/mk/Downloads/ocr_pipeline_share_2026-04-23`

## Baseline Checks Run

1. `python manage.py check`
- Result: pass
- Notes: Django system check reported no issues.

2. `python manage.py test -v 2`
- Result: pass
- Evidence summary:
- test count: 82
- status: `OK`
- runtime: ~62.9s
- coverage includes auth, medicines, OCR, reminders, medical record, search ranking, migrations, routing.

3. `python manage.py migrate --noinput`
- Result: pass
- Notes: no pending migrations.

4. `python manage.py import_medicines --path medicines.csv`
- Result: pass
- Output observed: `created=0, updated=51`.

## Runtime Smoke Validation (Programmatic APIClient)

Executed representative requests using allowed host `127.0.0.1`.

Observed statuses:
- Auth token obtain: `200`
- Medicines list: `200`
- Medical record get: `200`
- Reminder create: `201`
- Reminder list: `200`
- Medicine interactions: `200`
- OCR search upload: `200`

Observed OCR response contract keys:
- `action_hint`
- `match_confidence_tier`
- `matches`
- `message`
- `ocr_angle`
- `ocr_confidence`
- `ocr_engine`
- `ocr_raw_text`
- `ocr_tokens`

Observed OCR tier for synthetic blank image sample:
- `match_confidence_tier = low`

## Verified Runtime Notes

- On startup/checks, service logs warning when `drug_detector.pt` is absent and confirms full-image OCR fallback.
- Test logs show OCR confidence and oversize upload paths are actively exercised.
