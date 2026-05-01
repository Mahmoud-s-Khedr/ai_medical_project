# Verification Evidence

Verification date: 2026-05-01
Environment: local repo state in `/home/mk/Downloads/ocr_pipeline_share_2026-04-23`

## Baseline Checks

1. `python manage.py check`
- Expected: pass (no Django system check issues).

2. `python manage.py test -v 2`
- Expected: pass.
- Critical coverage areas: auth, medicines, OCR upload, reminders/events validation, medical record resources, search ranking, routing.

3. `python manage.py migrate --noinput`
- Expected: no pending migrations.

4. `python manage.py import_medicines --path medicines.csv`
- Expected: successful upsert by `trade_name`.

## Docs Consistency Checklist (Code-First)

Routes and endpoint coverage:
- `/` redirect to `/api/docs/` documented.
- `/demo/` and `/demo/health/` documented.
- All `/api/auth/*`, `/api/medicines/*`, `/api/reminders/*`, `/api/medical-record/*`, and `/api/uploads/ocr-search/` documented.

OCR response contract:
- Uses `matched_items` (not `matches`) in docs.
- Includes `match_confidence_tier`, `action_hint`, `processing_time_ms`.
- Documents `top_k` clamp to `[1, 20]` and low-tier result cap behavior.

Validation and error constraints:
- Reminders `times` HH:MM and non-empty list constraint documented.
- `end_date < start_date` rejection documented.
- Reminder event `status=taken` requires `taken_at` documented.
- OCR upload and decode failure semantics (`400`, `413`, `500`) documented.

Pagination shape:
- `count`, `total_pages`, `next`, `previous`, `results` documented.
- `page_size` and max `100` documented.

Runtime settings and toggles:
- JWT lifetimes and auth throttles documented.
- Upload size limits documented.
- OCR/search tunables and behavior-changing toggles documented.
- YOLO fallback and OCR engine fallback behavior documented.

## Repeatable Verification Commands

```bash
python manage.py check
python manage.py test -v 2
python manage.py show_urls 2>/dev/null || true
bash scripts/check_docs_consistency.sh
```

`show_urls` is optional (depends on installed tooling); route verification is otherwise taken from `medicine_backend/urls.py` and `api/urls.py`.

## English/Arabic Parity Status

- English docs are the canonical, code-verified baseline for this pass.
- Arabic docs (`README_AR.md`, `TEAM_QUICKSTART_AR.md`) require a follow-up sync pass to mirror finalized English technical claims.
