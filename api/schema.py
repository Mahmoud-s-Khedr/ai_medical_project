from __future__ import annotations

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class DeveloperApiKeyScheme(OpenApiAuthenticationExtension):
    target_class = "api.integration_auth.DeveloperApiKeyAuthentication"
    name = "ApiKeyAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "External integration API key. Generated once via /api/integrations/keys/.",
        }
