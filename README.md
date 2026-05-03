# Medicine OCR Search Pipeline

Language: [English](README.md) | [العربية](README_AR.md)

## Overview

This repository provides a Django REST backend for:
- medicine catalog and search
- OCR-based medicine lookup from uploaded images
- medicine history tracking (current/past usage)

It also includes:
- a demo web UI at `/demo/`
- a local CLI OCR flow (`cli_ocr_search.py`)
- optional YOLO training assets (`mazen_first_(2)_(4).ipynb`)

## Canonical Technical Docs (Code-First)

Use the `docs/` set as source of truth for technical behavior:
- [Docs Index](docs/INDEX.md)
- [API Contracts](docs/api-contracts.md)
- [System Architecture](docs/system-architecture.md)
- [OCR/Search Internals](docs/ocr-search-internals.md)
- [Config/Security/Ops](docs/config-security-ops.md)
- [Verification Evidence](docs/verification-evidence.md)

Top-level README content is intentionally operational and brief to reduce drift.

## Quick Start

Prerequisites:
- macOS or Linux
- Python 3.11 or 3.12
- `pip`
- `tesseract` system binary

macOS install:

```bash
brew install tesseract
```

Setup and run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py import_medicines --path medicines.csv
python manage.py runserver 127.0.0.1:8000
```

Base URL: `http://127.0.0.1:8000`

## API and Demo Entrypoints

- `GET /` -> redirect to `/api/docs/`
- `GET /api/docs/` Swagger UI
- `GET /api/schema/` OpenAPI schema
- `GET /api/redoc/` ReDoc
- `GET /demo/` demo app
- `GET /demo/health/` demo health JSON

For full endpoint contracts, see [docs/api-contracts.md](docs/api-contracts.md).

## OCR Smoke Test

```bash
curl -X POST "http://127.0.0.1:8000/api/uploads/ocr-search/" \
  -H "Authorization: Bearer <access_token>" \
  -F "image=@sample_medicine.png" \
  -F "top_k=5"
```

For exact response contract and error semantics, see [docs/api-contracts.md](docs/api-contracts.md#ocr-search).

## Additional Assets

- Team quickstart (English): [TEAM_QUICKSTART_EN.md](TEAM_QUICKSTART_EN.md)
- Team quickstart (Arabic): [TEAM_QUICKSTART_AR.md](TEAM_QUICKSTART_AR.md)
- Postman collection: `postman/Medicine_OCR_API.postman_collection.json`
- Postman environment: `postman/Medicine_OCR_API.postman_environment.json`

## Follow-up

Arabic docs are not yet synced with this English code-first refresh. Track sync for:
- `README_AR.md`
- `TEAM_QUICKSTART_AR.md`
