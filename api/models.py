from __future__ import annotations

from django.conf import settings
from django.db import models


# ─────────────────────────────────────────────────────────────────────────────
# MEDICINE
# ─────────────────────────────────────────────────────────────────────────────

class Medicine(models.Model):
    trade_name = models.CharField(max_length=255, unique=True)
    active_ingredient = models.CharField(max_length=255, blank=True)
    strength = models.CharField(max_length=100, blank=True)
    dosage_form = models.CharField(max_length=100, blank=True)
    drug_class = models.CharField(max_length=160, blank=True)
    search_aliases = models.TextField(blank=True)
    trade_name_norm = models.CharField(max_length=255, blank=True, db_index=True)
    active_ingredient_norm = models.CharField(max_length=255, blank=True, db_index=True)
    drug_class_norm = models.CharField(max_length=255, blank=True, db_index=True)
    active_ingredient_tokens = models.TextField(blank=True)
    common_side_effects = models.TextField(blank=True)
    serious_warning = models.TextField(blank=True)
    similar_active_ingredients = models.TextField(blank=True)
    similarity_risk_symptoms = models.TextField(blank=True)
    switching_note = models.TextField(blank=True)
    interaction_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["trade_name"]

    def __str__(self) -> str:
        return self.trade_name


class MedicationReminder(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reminders",
    )
    medicine = models.ForeignKey(Medicine, on_delete=models.SET_NULL, null=True, blank=True, related_name="reminders")
    medicine_name = models.CharField(max_length=255)
    dose = models.CharField(max_length=120)
    times = models.JSONField(default=list)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    timezone = models.CharField(max_length=80, default="Africa/Cairo")
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_active", "start_date", "medicine_name"]

    def __str__(self) -> str:
        return f"{self.medicine_name} reminder"


class ReminderEvent(models.Model):
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("taken", "Taken"),
        ("missed", "Missed"),
        ("skipped", "Skipped"),
    ]

    reminder = models.ForeignKey(MedicationReminder, on_delete=models.CASCADE, related_name="events")
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")
    taken_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scheduled_at"]

    def __str__(self) -> str:
        return f"{self.reminder_id} {self.status} at {self.scheduled_at}"


# ─────────────────────────────────────────────────────────────────────────────
# MEDICAL RECORD
# ─────────────────────────────────────────────────────────────────────────────

class MedicalRecord(models.Model):
    GENDER_CHOICES = [("M", "Male"), ("F", "Female"), ("other", "Other")]
    BLOOD_TYPE_CHOICES = [
        ("A+", "A+"), ("A-", "A-"),
        ("B+", "B+"), ("B-", "B-"),
        ("AB+", "AB+"), ("AB-", "AB-"),
        ("O+", "O+"), ("O-", "O-"),
        ("unknown", "Unknown"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="medical_record",
    )
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    blood_type = models.CharField(max_length=10, choices=BLOOD_TYPE_CHOICES, blank=True)
    height_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    phone_number = models.CharField(max_length=30, blank=True)
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Medical record — {self.user}"


class Diagnosis(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("chronic", "Chronic"),
        ("resolved", "Resolved"),
    ]

    record = models.ForeignKey(MedicalRecord, on_delete=models.CASCADE, related_name="diagnoses")
    condition_name = models.CharField(max_length=255)
    icd_code = models.CharField(max_length=20, blank=True)
    diagnosed_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    diagnosed_by = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-diagnosed_date", "condition_name"]

    def __str__(self) -> str:
        return f"{self.condition_name} ({self.status})"


class Allergy(models.Model):
    TYPE_CHOICES = [
        ("drug", "Drug"),
        ("food", "Food"),
        ("environmental", "Environmental"),
        ("other", "Other"),
    ]
    SEVERITY_CHOICES = [
        ("mild", "Mild"),
        ("moderate", "Moderate"),
        ("severe", "Severe"),
    ]

    record = models.ForeignKey(MedicalRecord, on_delete=models.CASCADE, related_name="allergies")
    allergen = models.CharField(max_length=255)
    allergen_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="drug")
    reaction = models.TextField(blank=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="mild")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-severity", "allergen"]

    def __str__(self) -> str:
        return f"{self.allergen} ({self.severity})"


class VitalSign(models.Model):
    record = models.ForeignKey(MedicalRecord, on_delete=models.CASCADE, related_name="vitals")
    recorded_at = models.DateTimeField()
    blood_pressure_systolic = models.PositiveSmallIntegerField(null=True, blank=True, help_text="mmHg")
    blood_pressure_diastolic = models.PositiveSmallIntegerField(null=True, blank=True, help_text="mmHg")
    heart_rate = models.PositiveSmallIntegerField(null=True, blank=True, help_text="bpm")
    temperature_celsius = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    height_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    blood_glucose_mg_dl = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    oxygen_saturation_pct = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self) -> str:
        return f"Vitals @ {self.recorded_at:%Y-%m-%d %H:%M}"


class LabResult(models.Model):
    record = models.ForeignKey(MedicalRecord, on_delete=models.CASCADE, related_name="lab_results")
    test_name = models.CharField(max_length=255)
    result_value = models.CharField(max_length=100)
    unit = models.CharField(max_length=50, blank=True)
    reference_range = models.CharField(max_length=100, blank=True)
    is_abnormal = models.BooleanField(default=False)
    recorded_at = models.DateField()
    lab_name = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-recorded_at", "test_name"]

    def __str__(self) -> str:
        return f"{self.test_name}: {self.result_value} {self.unit}"


class DoctorVisit(models.Model):
    record = models.ForeignKey(MedicalRecord, on_delete=models.CASCADE, related_name="visits")
    visit_date = models.DateField()
    doctor_name = models.CharField(max_length=150, blank=True)
    specialty = models.CharField(max_length=100, blank=True)
    reason = models.TextField()
    diagnosis_notes = models.TextField(blank=True)
    prescription_notes = models.TextField(blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-visit_date"]

    def __str__(self) -> str:
        return f"Visit {self.visit_date} — {self.doctor_name or 'Unknown doctor'}"
