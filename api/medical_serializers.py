from __future__ import annotations

from rest_framework import serializers

from .models import Allergy, Diagnosis, DoctorVisit, LabResult, MedicalRecord, VitalSign


class DiagnosisSerializer(serializers.ModelSerializer):
    class Meta:
        model = Diagnosis
        fields = [
            "id", "condition_name", "icd_code", "diagnosed_date",
            "status", "diagnosed_by", "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AllergySerializer(serializers.ModelSerializer):
    class Meta:
        model = Allergy
        fields = [
            "id", "allergen", "allergen_type", "reaction",
            "severity", "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class VitalSignSerializer(serializers.ModelSerializer):
    blood_pressure = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = VitalSign
        fields = [
            "id", "recorded_at",
            "blood_pressure_systolic", "blood_pressure_diastolic", "blood_pressure",
            "heart_rate", "temperature_celsius",
            "weight_kg", "height_cm",
            "blood_glucose_mg_dl", "oxygen_saturation_pct",
            "notes", "created_at",
        ]
        read_only_fields = ["id", "blood_pressure", "created_at"]

    def get_blood_pressure(self, obj) -> str | None:
        if obj.blood_pressure_systolic and obj.blood_pressure_diastolic:
            return f"{obj.blood_pressure_systolic}/{obj.blood_pressure_diastolic} mmHg"
        return None


class LabResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabResult
        fields = [
            "id", "test_name", "result_value", "unit",
            "reference_range", "is_abnormal", "recorded_at",
            "lab_name", "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class DoctorVisitSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorVisit
        fields = [
            "id", "visit_date", "doctor_name", "specialty",
            "reason", "diagnosis_notes", "prescription_notes",
            "follow_up_date", "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class MedicalRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalRecord
        fields = [
            "id", "date_of_birth", "gender", "blood_type",
            "height_cm", "weight_kg", "phone_number",
            "emergency_contact_name", "emergency_contact_phone",
            "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class MedicalSummarySerializer(serializers.ModelSerializer):
    diagnoses = DiagnosisSerializer(many=True, read_only=True)
    allergies = AllergySerializer(many=True, read_only=True)
    vitals = VitalSignSerializer(many=True, read_only=True)
    lab_results = LabResultSerializer(many=True, read_only=True)
    visits = DoctorVisitSerializer(many=True, read_only=True)
    latest_vitals = serializers.SerializerMethodField()
    active_diagnoses_count = serializers.SerializerMethodField()
    drug_allergies = serializers.SerializerMethodField()

    class Meta:
        model = MedicalRecord
        fields = [
            "id", "date_of_birth", "gender", "blood_type",
            "height_cm", "weight_kg", "phone_number",
            "emergency_contact_name", "emergency_contact_phone",
            "notes", "created_at", "updated_at",
            # nested
            "active_diagnoses_count", "drug_allergies", "latest_vitals",
            "diagnoses", "allergies", "vitals", "lab_results", "visits",
        ]

    def get_latest_vitals(self, obj) -> dict | None:
        latest = obj.vitals.first()
        return VitalSignSerializer(latest).data if latest else None

    def get_active_diagnoses_count(self, obj) -> int:
        return obj.diagnoses.filter(status__in=["active", "chronic"]).count()

    def get_drug_allergies(self, obj) -> list[str]:
        return list(
            obj.allergies.filter(allergen_type="drug").values_list("allergen", flat=True)
        )
