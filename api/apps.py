from __future__ import annotations

from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self):
        # Ensure drf-spectacular discovers custom auth scheme extensions.
        import api.schema  # noqa: F401
