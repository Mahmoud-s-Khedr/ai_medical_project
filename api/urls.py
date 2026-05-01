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
from .medical_views import (
    AllergyViewSet,
    DiagnosisViewSet,
    DoctorVisitViewSet,
    LabResultViewSet,
    MedicalRecordView,
    MedicalSummaryView,
    VitalSignViewSet,
)
from .views import MedicationReminderViewSet, MedicineViewSet, OCRMedicineSearchView

router = DefaultRouter()
router.register("medicines", MedicineViewSet, basename="medicine")
router.register("reminders", MedicationReminderViewSet, basename="reminder")
router.register("medical-record/diagnoses", DiagnosisViewSet, basename="diagnosis")
router.register("medical-record/allergies", AllergyViewSet, basename="allergy")
router.register("medical-record/vitals", VitalSignViewSet, basename="vital")
router.register("medical-record/lab-results", LabResultViewSet, basename="lab-result")
router.register("medical-record/visits", DoctorVisitViewSet, basename="visit")

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
    path("medical-record/", MedicalRecordView.as_view(), name="medical-record"),
    path("medical-record/summary/", MedicalSummaryView.as_view(), name="medical-record-summary"),
    path("", include(router.urls)),
    path("uploads/ocr-search/", OCRMedicineSearchView.as_view(), name="ocr-medicine-search"),
]
