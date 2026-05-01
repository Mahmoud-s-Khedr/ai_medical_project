# Contributor Safe Change Guide

## Common Change Tasks

### Add or modify an API endpoint

1. Update route wiring in `api/urls.py`.
2. Add/update serializer validation.
3. Keep permission model explicit (`IsAuthenticated` or stricter).
4. Add focused tests in `api/tests.py` for success, auth failure, and validation failure.
5. Confirm OpenAPI docs still render (`/api/schema/`, `/api/docs/`).

### Change OCR ranking/confidence behavior

1. Update OCR flow in `api/views.py` and/or OCR engine behavior in `ai/ocr_pipeline.py`.
2. If search heuristics change, update `api/search.py`.
3. Update or add tests in OCR/search sections of `api/tests.py`:
- low-confidence retake path
- token fallback path
- score filtering path
4. Re-run full suite and validate no regression in medicine search ranking tests.

### Change medical-record/reminder data behavior

1. Update model and serializer constraints consistently.
2. If schema changes, create migration and test migration compatibility assumptions.
3. Preserve queryset-level user scoping in viewsets/views.
4. Add tests for cross-user access denial and filter behavior.

### Change auth/password reset behavior

1. Keep throttle scope behavior (`auth`) where appropriate.
2. Preserve non-user-enumerating password reset request response.
3. Re-test login/logout/token refresh/change password/reset confirm flows.

## Minimum Regression Command Set

- `python manage.py check`
- `python manage.py test -v 2`
- `python manage.py migrate --noinput`
- `python manage.py import_medicines --path medicines.csv`

## High-Risk Areas

- OCR endpoint error handling and confidence policy (directly affects user guidance).
- Permission/scoping code in reminders and medical-record resources.
- Search ranking/caching logic (can silently change top results).
