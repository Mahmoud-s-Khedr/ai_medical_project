from __future__ import annotations

import re

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


class TextToSpeechRequestSerializer(serializers.Serializer):
    text = serializers.CharField(required=True, allow_blank=False, trim_whitespace=True)
    voice = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)
    voice_ar = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)
    voice_en = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)
    rate = serializers.CharField(required=False, allow_blank=False, trim_whitespace=True)
    mixed_mode = serializers.ChoiceField(required=False, choices=["single_voice", "dual_voice"])

    def validate_text(self, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value).strip()
        if not normalized:
            raise serializers.ValidationError("Text must not be empty.")
        return normalized

    def validate_voice(self, value: str) -> str:
        if len(value) > 80:
            raise serializers.ValidationError("Voice is too long.")
        return value

    def validate_voice_ar(self, value: str) -> str:
        if len(value) > 80:
            raise serializers.ValidationError("voice_ar is too long.")
        return value

    def validate_voice_en(self, value: str) -> str:
        if len(value) > 80:
            raise serializers.ValidationError("voice_en is too long.")
        return value

    def validate_rate(self, value: str) -> str:
        if not re.fullmatch(r"[+-]\d{1,3}%", value):
            raise serializers.ValidationError("Rate must be in format like '+0%', '+10%', or '-15%'.")
        return value
