from __future__ import annotations

from django.contrib import admin

from .models import (
    Allergy,
    Diagnosis,
    DoctorVisit,
    LabResult,
    MedicalRecord,
    MedicationReminder,
    Medicine,
    ReminderEvent,
    VitalSign,
)


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ("trade_name", "active_ingredient", "strength", "dosage_form")
    search_fields = ("trade_name", "active_ingredient")


@admin.register(MedicationReminder)
class MedicationReminderAdmin(admin.ModelAdmin):
    list_display = ("medicine_name", "user", "dose", "start_date", "end_date", "is_active")
    list_filter = ("is_active", "timezone", "user")
    search_fields = ("medicine_name", "dose", "user__username", "user__email")
    raw_id_fields = ("user",)


@admin.register(ReminderEvent)
class ReminderEventAdmin(admin.ModelAdmin):
    list_display = ("reminder", "scheduled_at", "status", "taken_at")
    list_filter = ("status",)


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "gender", "blood_type", "date_of_birth")
    search_fields = ("user__username", "user__email")


@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
    list_display = ("condition_name", "status", "diagnosed_date", "diagnosed_by", "record")
    list_filter = ("status",)
    search_fields = ("condition_name", "icd_code")


@admin.register(Allergy)
class AllergyAdmin(admin.ModelAdmin):
    list_display = ("allergen", "allergen_type", "severity", "record")
    list_filter = ("allergen_type", "severity")
    search_fields = ("allergen",)


@admin.register(VitalSign)
class VitalSignAdmin(admin.ModelAdmin):
    list_display = ("record", "recorded_at", "blood_pressure_systolic", "blood_pressure_diastolic", "heart_rate", "weight_kg")
    list_filter = ("recorded_at",)


@admin.register(LabResult)
class LabResultAdmin(admin.ModelAdmin):
    list_display = ("test_name", "result_value", "unit", "is_abnormal", "recorded_at", "record")
    list_filter = ("is_abnormal",)
    search_fields = ("test_name", "lab_name")


@admin.register(DoctorVisit)
class DoctorVisitAdmin(admin.ModelAdmin):
    list_display = ("visit_date", "doctor_name", "specialty", "reason", "record")
    search_fields = ("doctor_name", "specialty")

