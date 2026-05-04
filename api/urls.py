from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

from .auth_views import (
    ChangePasswordView,
    LogoutView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
)
from .integration_views import (
    AccessRequestDecisionView,
    DeveloperApiKeyViewSet,
    DeveloperAppViewSet,
    ExternalCreateAccessRequestView,
    ExternalMedicineHistoryView,
    MedicineHistoryExportXmlView,
    RevokeDeveloperApiKeyView,
    UserAccessRequestInboxView,
)
from .views import MedicineHistoryViewSet, MedicineViewSet, OCRMedicineSearchView, TextToSpeechView

router = DefaultRouter()
router.register("medicines", MedicineViewSet, basename="medicine")
router.register("medicine-history", MedicineHistoryViewSet, basename="medicine-history")
router.register("integrations/apps", DeveloperAppViewSet, basename="integration-app")
router.register("integrations/keys", DeveloperApiKeyViewSet, basename="integration-key")

auth_urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("token/", TokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token-verify"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("me/change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
]

urlpatterns = [
    path("auth/", include(auth_urlpatterns)),
    path("", include(router.urls)),
    path("uploads/ocr-search/", OCRMedicineSearchView.as_view(), name="ocr-medicine-search"),
    path("tts/speak/", TextToSpeechView.as_view(), name="tts-speak"),
    path("integrations/keys/<int:key_id>/revoke/", RevokeDeveloperApiKeyView.as_view(), name="integration-key-revoke"),
    path("integrations/access-requests/inbox/", UserAccessRequestInboxView.as_view(), name="integration-inbox"),
    path(
        "integrations/access-requests/<int:request_id>/<str:decision>/",
        AccessRequestDecisionView.as_view(),
        name="integration-access-request-decision",
    ),
    path("integrations/medicine-history/export.xml", MedicineHistoryExportXmlView.as_view(), name="medicine-history-export-xml"),
    path("external/access-requests/", ExternalCreateAccessRequestView.as_view(), name="external-access-request-create"),
    path("external/medicine-history/<str:username>/", ExternalMedicineHistoryView.as_view(), name="external-medicine-history"),
]
