# Coverage Audit and Gap Register

## Coverage Checklist

### Public Endpoints

- Auth endpoints documented: yes
- Medicines + interactions documented: yes
- OCR upload search documented: yes
- Reminders + events documented: yes
- Medical record aggregate + child resources documented: yes
- Root/docs/demo routes documented in architecture/ops docs: yes

### Configuration Impacting Runtime Behavior

- Auth/JWT settings documented: yes
- Throttle settings documented: yes
- Upload limits documented: yes
- OCR/search tunables documented: yes
- CORS and host behavior documented: yes

### Critical Fallback Behaviors

- YOLO model missing -> full-image OCR fallback: documented and observed
- EasyOCR/Tesseract orchestration + skip condition: documented
- No OCR tokens -> low-confidence retake response: documented
- Low confidence -> result cap/action hint behavior: documented

## Mismatch Notes vs Existing Top-Level Docs

- `README.md` recommends Python 3.11/3.12, while local venv/test run used Python 3.14 successfully in this environment.
- `README.md` example for OCR response is representative, but live response keys and confidence semantics are now explicitly captured in `docs/api-contracts.md` and `docs/verification-evidence.md`.

## Known Gaps / Follow-up

1. Add explicit API error-code matrix per endpoint (currently documented at group level).
2. Add sequence diagrams for OCR happy path vs fallback path.
3. Add benchmark section for OCR/search latency with and without YOLO model file present.
