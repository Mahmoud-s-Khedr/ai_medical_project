# External Integration Review Note (Pre-Implementation)

Date: 2026-05-03

## Findings

- Auth stack is JWT-only by default (`REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES`), so external API-key auth should be endpoint-scoped and not change global auth defaults.
- Routing is centralized in `api/urls.py` with DRF router + explicit auth/upload paths; new integration routes can be added cleanly there.
- `MedicineHistoryEntry` already provides the exact v1 data scope we need (user-scoped medicine history).
- Standard pagination is already globally configured and should be reused for external history reads.
- Default renderer is JSON; there is no existing XML renderer/helper in the codebase.
- OpenAPI generation uses drf-spectacular and will include new endpoints automatically when added to URL config.

## Chosen Insertion Points

- Models: extend `api/models.py` with developer app, API key, and consent request models.
- API-key auth: new module `api/integration_auth.py`.
- Integration serializers/views: new modules `api/integration_serializers.py` and `api/integration_views.py`.
- URL surface: extend `api/urls.py` with two route groups:
  - JWT user integration management + request inbox actions.
  - External API-key endpoints for request creation and approved history fetch.
- XML support: new helper module `api/xml_utils.py` for medicine-history XML payload generation and response wrapping.
- Tests: add integration tests in a dedicated test module while preserving existing tests.

## Risks and Mitigations

- Key leakage risk: store only hashed API keys, return raw key once, and support revocation.
- Cross-tenant data exposure risk: enforce app+user approved-consent gate before all external reads.
- Username targeting risk: reject unknown users and avoid leaking extra user profile details in error payloads.
- Duplicate request ambiguity: enforce one active (`pending`/`approved`) app-user request to avoid inconsistent consent state.
- XML parity risk: validate response parity via integration tests for JSON vs XML payload content.

## Compatibility Notes

- Existing JWT-protected user APIs remain unchanged.
- Global REST framework defaults remain unchanged (endpoint-level auth/format handling only).
- New models require one additive migration.
