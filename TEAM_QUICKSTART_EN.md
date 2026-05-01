# OCR Medicine Backend - Team Quickstart (English)

Language: [English](TEAM_QUICKSTART_EN.md) | [العربية](TEAM_QUICKSTART_AR.md)

This quickstart is operational only. For exact behavior/contracts, use:
- [docs/api-contracts.md](docs/api-contracts.md)
- [docs/config-security-ops.md](docs/config-security-ops.md)
- [docs/system-architecture.md](docs/system-architecture.md)

## 1) Prerequisites

- macOS or Linux
- Python 3.11 or 3.12
- `pip`
- `tesseract` (system package)

macOS:

```bash
brew install tesseract
```

## 2) Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3) Database + Seed

```bash
python3 manage.py migrate
python3 manage.py import_medicines --path medicines.csv
```

## 4) Run Server

```bash
python3 manage.py runserver 127.0.0.1:8000
```

Optional helper scripts:

```bash
bash scripts/run_app.sh
bash scripts/stop_app.sh
```

## 5) Main Entrypoints

- `GET /` -> `302` to `/api/docs/`
- `GET /api/docs/`
- `GET /api/schema/`
- `GET /api/redoc/`
- `GET /demo/`

## 6) Get JWT Token

```bash
curl -X POST "http://127.0.0.1:8000/api/auth/token/" \
  -H "Content-Type: application/json" \
  -d '{"username":"<username>","password":"<password>"}'
```

Use token:

`Authorization: Bearer <access_token>`

## 7) OCR Upload Smoke Test

```bash
curl -X POST "http://127.0.0.1:8000/api/uploads/ocr-search/" \
  -H "Authorization: Bearer <access_token>" \
  -F "image=@sample_medicine.png" \
  -F "top_k=5"
```

Expected contract keys include:
- `ocr_confidence`
- `matched_items`
- `match_confidence_tier`
- `action_hint`
- `message`
- `processing_time_ms`

## 8) Local CLI OCR (No Django)

```bash
python3 cli_ocr_search.py sample_medicine.png --catalog medicines.csv --column trade_name
```

## 9) Validation Commands

```bash
python3 manage.py check
python3 manage.py test -v 2
bash scripts/check_docs_consistency.sh
```

## 10) Reference

Use this data source to find more medicines:
`http://eservices.edaegypt.gov.eg/EDASearch/SearchRegDrugs.aspx`

Arabic quickstart sync is pending this English refresh.
