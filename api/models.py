from __future__ import annotations

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError


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


class MedicineHistoryEntry(models.Model):
    STATUS_CHOICES = [
        ("current", "Current"),
        ("past", "Past"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="medicine_history_entries",
    )
    medicine = models.ForeignKey(Medicine, on_delete=models.SET_NULL, null=True, blank=True, related_name="history_entries")
    medicine_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="current")
    dose = models.CharField(max_length=120, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "medicine_name"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "start_date"]),
        ]

    def clean(self):
        if self.status == "current" and self.end_date is not None:
            raise ValidationError({"end_date": "end_date must be empty when status is 'current'."})
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "end_date cannot be before start_date."})

    def __str__(self) -> str:
        return f"{self.medicine_name} ({self.status})"
