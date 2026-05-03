from __future__ import annotations

from rest_framework import serializers

from .models import Medicine, MedicineHistoryEntry


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


class MedicineHistoryEntrySerializer(serializers.ModelSerializer):
    medicine_details = MedicineSerializer(source="medicine", read_only=True)
    medicine_id = serializers.PrimaryKeyRelatedField(
        source="medicine",
        queryset=Medicine.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = MedicineHistoryEntry
        fields = [
            "id",
            "user",
            "medicine",
            "medicine_id",
            "medicine_details",
            "medicine_name",
            "status",
            "dose",
            "start_date",
            "end_date",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "medicine", "medicine_details", "created_at", "updated_at"]

    def validate(self, attrs):
        status_val = attrs.get("status", getattr(self.instance, "status", "current"))
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))

        if status_val == "current" and end_date is not None:
            raise serializers.ValidationError({"end_date": "end_date must be empty when status is 'current'."})
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "end_date cannot be before start_date."})
        return attrs
