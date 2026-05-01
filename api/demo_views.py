from __future__ import annotations

from django.http import JsonResponse
from django.views.generic import TemplateView


class DemoAppView(TemplateView):
    template_name = "demo/index.html"


def demo_health(_request):
    return JsonResponse({"status": "ok", "service": "medicine-ocr-demo-ui", "version": "1.0.0"})
