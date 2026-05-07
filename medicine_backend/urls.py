from __future__ import annotations

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import (
    SpectacularJSONAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from api.demo_views import DemoAppView, demo_health

urlpatterns = [
    path("", RedirectView.as_view(url="/api/docs/", permanent=False), name="root-redirect"),
    path("demo/", DemoAppView.as_view(), name="demo-app"),
    path("demo/health/", demo_health, name="demo-health"),
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    # OpenAPI schema + interactive docs (no auth required)
    path("api/schema/", SpectacularJSONAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
