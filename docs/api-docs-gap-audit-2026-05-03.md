# API Documentation Gap Audit (2026-05-03)

## Scope
Code-first audit of API documentation against runtime route surface and endpoint behavior.

## Source of Truth Map
- Route surface: `medicine_backend/urls.py`, `api/urls.py`
- Auth and identity behavior: `api/auth_views.py`, `api/integration_auth.py`
- Endpoint behavior: `api/views.py`, `api/integration_views.py`
- Payload shapes: `api/serializers.py`, `api/integration_serializers.py`
- Pagination and API defaults: `api/pagination.py`, `medicine_backend/settings.py`

## Gap Summary

### 1. Stale Architecture Claims
- `docs/system-architecture.md` still described reminder/event flows that are not in the current `/api/` route surface.
- Purpose/description language referenced reminder functionality as active API scope.

### 2. Incomplete Integration Contract Detail
- `docs/api-contracts.md` listed integration endpoints but lacked concise examples for key generation, consent decisions, and external JSON/XML retrieval.
- Error semantics were present but not consistently mapped by endpoint family and flow step.

### 3. Data Model Documentation Drift
- `docs/data-model.md` did not include integration entities (`DeveloperApp`, `DeveloperApiKey`, `DataAccessRequest`), uniqueness constraints, and consent lifecycle impacts.

### 4. OpenAPI Discoverability Gaps
- Integration endpoints lacked explicit schema-level summaries/examples for request/response and auth mode separation (JWT vs `X-API-Key`).
- Custom API-key authentication was functional but not explicitly described as a security scheme in generated schema.

### 5. Quality-Gate Coverage
- `docs/INDEX.md` quality gates did not explicitly call out external integration auth/consent lifecycle coverage expectations.

## Remediation Plan Applied
- Refresh technical docs (`api-contracts`, `system-architecture`, `data-model`, `INDEX`) to match code.
- Add drf-spectacular schema annotations to integration endpoints.
- Register custom API-key security scheme for OpenAPI.
- Validate schema generation and route-to-doc parity after edits.
