from __future__ import annotations

from django.db import IntegrityError, transaction
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .medical_serializers import (
    AllergySerializer,
    DiagnosisSerializer,
    DoctorVisitSerializer,
    LabResultSerializer,
    MedicalRecordSerializer,
    MedicalSummarySerializer,
    VitalSignSerializer,
)
from .models import Allergy, Diagnosis, DoctorVisit, LabResult, MedicalRecord, VitalSign


def _get_or_create_record(user) -> MedicalRecord:
    try:
        with transaction.atomic():
            record, _ = MedicalRecord.objects.get_or_create(user=user)
            return record
    except IntegrityError:
        return MedicalRecord.objects.get(user=user)


# ── Medical Record (patient info) ─────────────────────────────────────────────

class MedicalRecordView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        record = _get_or_create_record(request.user)
        return Response(MedicalRecordSerializer(record).data)

    def patch(self, request):
        record = _get_or_create_record(request.user)
        serializer = MedicalRecordSerializer(record, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def put(self, request):
        record = _get_or_create_record(request.user)
        serializer = MedicalRecordSerializer(record, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ── Full summary ───────────────────────────────────────────────────────────────

class MedicalSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        record = _get_or_create_record(request.user)
        return Response(MedicalSummarySerializer(record).data)


# ── Base ViewSet — auto-scopes to the user's medical record ───────────────────

class _RecordScopedViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    _related_name: str = ""

    def _record(self):
        return _get_or_create_record(self.request.user)

    def get_queryset(self):
        return getattr(self._record(), self._related_name).all()

    def perform_create(self, serializer):
        serializer.save(record=self._record())


# ── Diagnoses ─────────────────────────────────────────────────────────────────

class DiagnosisViewSet(_RecordScopedViewSet):
    serializer_class = DiagnosisSerializer
    _related_name = "diagnoses"

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        if status_filter in {"active", "chronic", "resolved"}:
            qs = qs.filter(status=status_filter)
        return qs


# ── Allergies ─────────────────────────────────────────────────────────────────

class AllergyViewSet(_RecordScopedViewSet):
    serializer_class = AllergySerializer
    _related_name = "allergies"

    def get_queryset(self):
        qs = super().get_queryset()
        allergen_type = self.request.query_params.get("type")
        if allergen_type in {"drug", "food", "environmental", "other"}:
            qs = qs.filter(allergen_type=allergen_type)
        return qs


# ── Vital Signs ───────────────────────────────────────────────────────────────

class VitalSignViewSet(_RecordScopedViewSet):
    serializer_class = VitalSignSerializer
    _related_name = "vitals"


# ── Lab Results ───────────────────────────────────────────────────────────────

class LabResultViewSet(_RecordScopedViewSet):
    serializer_class = LabResultSerializer
    _related_name = "lab_results"

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("abnormal") == "true":
            qs = qs.filter(is_abnormal=True)
        return qs


# ── Doctor Visits ─────────────────────────────────────────────────────────────

class DoctorVisitViewSet(_RecordScopedViewSet):
    serializer_class = DoctorVisitSerializer
    _related_name = "visits"
