# Technical Documentation Index

Audience: backend engineers onboarding to this repository.

## Code-First Documentation Policy

Documentation in this folder is derived from code and tests, not from prior prose.

Authoritative sources:
- `medicine_backend/settings.py`
- `medicine_backend/urls.py`
- `api/urls.py`
- `api/views.py`
- `api/auth_views.py`
- `api/medical_views.py`
- `api/serializers.py`
- `api/pagination.py`
- `api/tests.py`
- `api/management/commands/*.py`

Rules:
- Any behavior claim must map to one of the sources above.
- Public `/api/` endpoints and security boundaries must be documented.
- Runtime-impacting settings and critical fallback behavior must be documented.
- When code and docs conflict, code wins and docs must be updated in the same change.

## Sections

1. [System Architecture](./system-architecture.md)
2. [API Contracts](./api-contracts.md)
3. [Data Model](./data-model.md)
4. [OCR and Search Internals](./ocr-search-internals.md)
5. [Configuration, Security, and Operations](./config-security-ops.md)
6. [Verification Evidence](./verification-evidence.md)
7. [Contributor Safe Change Guide](./safe-change-guide.md)
8. [Coverage Audit and Gap Register](./coverage-audit-and-gaps.md)

## Documentation Quality Gates

- No undocumented public endpoint under `/api/`.
- No undocumented configuration setting that changes runtime API/OCR behavior.
- No undocumented critical fallback behavior (YOLO fallback, OCR engine fallback, low-confidence response behavior).
