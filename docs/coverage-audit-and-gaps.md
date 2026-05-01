# Coverage Audit and Gap Register

## Coverage Checklist

### Public Endpoints

- Auth endpoints documented: yes
- Medicines + interactions documented: yes
- OCR upload search documented (with `matched_items` contract): yes
- Reminders + events documented: yes
- Medical record aggregate + child resources documented: yes
- Root/docs/demo routes documented: yes

### Configuration Impacting Runtime Behavior

- Auth/JWT settings documented: yes
- Throttle settings documented: yes
- Upload limits documented: yes
- OCR/search tunables documented: yes
- CORS and host behavior documented: yes
- Behavior-changing OCR toggles documented: yes

### Critical Fallback Behaviors

- YOLO model missing/import/inference fail -> full-image OCR fallback: documented
- EasyOCR/Tesseract orchestration + skip condition: documented
- No OCR tokens -> low-confidence retake response: documented
- Low confidence -> response cap/action hint behavior: documented

## Anti-Drift Controls Added

- Code-first policy and authoritative source list in `docs/INDEX.md`.
- `scripts/check_docs_consistency.sh` for repeatable non-mutating docs checks.
- Verification checklist in `docs/verification-evidence.md`.

## Known Gaps / Follow-up

1. Arabic documentation parity update is pending (`README_AR.md`, `TEAM_QUICKSTART_AR.md`).
2. Endpoint-by-endpoint error-code table can be expanded beyond group-level semantics.
3. OCR/search latency benchmark table is still not documented.
