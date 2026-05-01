# Technical Documentation Index

Audience: backend engineers onboarding to this repository.

## Sections

1. [System Architecture](./system-architecture.md)
2. [API Contracts](./api-contracts.md)
3. [Data Model](./data-model.md)
4. [OCR and Search Internals](./ocr-search-internals.md)
5. [Configuration, Security, and Operations](./config-security-ops.md)
6. [Verification Evidence](./verification-evidence.md)
7. [Contributor Safe Change Guide](./safe-change-guide.md)
8. [Coverage Audit and Gap Register](./coverage-audit-and-gaps.md)

## Source-of-Truth Code Boundaries

- Project/runtime config: `medicine_backend/`
- Application API/domain logic: `api/`
- OCR runtime logic: `ai/`
- Operational tooling: `tools/`
- Local non-Django OCR flow: `cli_ocr_search.py`, `ocr_medicine_search.py`

## Documentation Quality Gates

- No undocumented public endpoint under `/api/`.
- No undocumented configuration setting that changes runtime API/OCR behavior.
- No undocumented critical fallback behavior (YOLO fallback, OCR engine fallback, low-confidence response behavior).
