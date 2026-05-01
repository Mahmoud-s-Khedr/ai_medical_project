from __future__ import annotations

from rest_framework import serializers

from .models import MedicationReminder, Medicine, ReminderEvent


class MedicineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medicine
        fields = [
            "id",
            "trade_name",
            "active_ingredient",
            "strength",
            "dosage_form",
            "drug_class",
            "common_side_effects",
            "serious_warning",
            "similar_active_ingredients",
            "similarity_risk_symptoms",
            "switching_note",
            "interaction_notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class MedicationReminderSerializer(serializers.ModelSerializer):
    medicine_details = MedicineSerializer(source="medicine", read_only=True)
    medicine_id = serializers.PrimaryKeyRelatedField(
        source="medicine",
        queryset=Medicine.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = MedicationReminder
        fields = [
            "id",
            "user",
            "medicine",
            "medicine_id",
            "medicine_details",
            "medicine_name",
            "dose",
            "times",
            "start_date",
            "end_date",
            "timezone",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "medicine", "medicine_details", "created_at", "updated_at"]

    def validate_times(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError("times must be a non-empty list like ['09:00', '21:00'].")
        for item in value:
            if not isinstance(item, str) or len(item) != 5 or item[2] != ":":
                raise serializers.ValidationError("Each time must use HH:MM format.")
            try:
                hour, minute = int(item[:2]), int(item[3:])
            except ValueError:
                raise serializers.ValidationError(f"'{item}' is not a valid HH:MM time.")
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise serializers.ValidationError(f"'{item}' is out of range — hours 00-23, minutes 00-59.")
        return value

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "end_date cannot be before start_date."})
        return attrs


class ReminderEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReminderEvent
        fields = ["id", "reminder", "scheduled_at", "status", "taken_at", "notes", "created_at"]
        read_only_fields = ["id", "reminder", "created_at"]

    def validate(self, attrs):
        event_status = attrs.get("status", getattr(self.instance, "status", None))
        taken_at = attrs.get("taken_at", getattr(self.instance, "taken_at", None))
        if event_status == "taken" and not taken_at:
            raise serializers.ValidationError({"taken_at": "taken_at is required when status is 'taken'."})
        return attrs
