from __future__ import annotations

import hashlib

from django.utils import timezone
from rest_framework import authentication
from rest_framework import exceptions

from .models import DeveloperApiKey


class DeveloperApiKeyAuthentication(authentication.BaseAuthentication):
    header_name = "HTTP_X_API_KEY"

    def authenticate(self, request):
        raw_key = request.META.get(self.header_name, "").strip()
        if not raw_key:
            return None

        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        try:
            api_key = DeveloperApiKey.objects.select_related("app", "app__owner").get(key_hash=key_hash)
        except DeveloperApiKey.DoesNotExist as exc:
            raise exceptions.AuthenticationFailed("Invalid API key.") from exc

        if api_key.revoked_at is not None:
            raise exceptions.AuthenticationFailed("API key revoked.")
        if not api_key.app.is_active:
            raise exceptions.AuthenticationFailed("Developer app is inactive.")

        api_key.last_used_at = timezone.now()
        api_key.save(update_fields=["last_used_at"])

        # request.user should be a Django user for DRF IsAuthenticated semantics.
        return (api_key.app.owner, api_key)

    def authenticate_header(self, request):
        return "X-API-Key"
