from __future__ import annotations

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


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


class DeveloperApp(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="developer_apps",
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="uniq_developer_app_per_owner_name"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.owner})"


class DeveloperApiKey(models.Model):
    app = models.ForeignKey(DeveloperApp, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=120)
    key_prefix = models.CharField(max_length=12, db_index=True)
    key_hash = models.CharField(max_length=64, unique=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["app", "name"], name="uniq_api_key_name_per_app"),
        ]

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def revoke(self) -> None:
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at"])

    def __str__(self) -> str:
        return f"{self.app.name}:{self.name}"


class DataAccessRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_REVOKED = "revoked"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_REVOKED, "Revoked"),
    ]

    app = models.ForeignKey(DeveloperApp, on_delete=models.CASCADE, related_name="access_requests")
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="incoming_access_requests",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    purpose = models.CharField(max_length=255, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["target_user", "status"]),
            models.Index(fields=["app", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["app", "target_user"],
                condition=models.Q(status__in=["pending", "approved"]),
                name="uniq_active_access_request_per_app_user",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.app.name}->{self.target_user} ({self.status})"
