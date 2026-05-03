from __future__ import annotations

import hashlib
import secrets

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import DataAccessRequest, DeveloperApiKey, DeveloperApp
from .serializers import MedicineHistoryEntrySerializer

User = get_user_model()


class DeveloperAppSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeveloperApp
        fields = ["id", "name", "description", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class DeveloperApiKeySerializer(serializers.ModelSerializer):
    app_id = serializers.PrimaryKeyRelatedField(
        source="app",
        queryset=DeveloperApp.objects.all(),
        write_only=True,
    )

    class Meta:
        model = DeveloperApiKey
        fields = [
            "id",
            "app",
            "app_id",
            "name",
            "key_prefix",
            "last_used_at",
            "revoked_at",
            "created_at",
        ]
        read_only_fields = ["id", "app", "key_prefix", "last_used_at", "revoked_at", "created_at"]

    def validate(self, attrs):
        request = self.context["request"]
        app = attrs["app"]
        if app.owner_id != request.user.id:
            raise serializers.ValidationError("You can only manage keys for your own apps.")
        return attrs

    def create(self, validated_data):
        raw_key = f"dev_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        validated_data["key_hash"] = key_hash
        validated_data["key_prefix"] = raw_key[:12]
        instance = super().create(validated_data)
        instance.raw_key = raw_key
        return instance


class ExternalAccessRequestCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    purpose = serializers.CharField(max_length=255, allow_blank=True, required=False)

    def validate_username(self, value):
        try:
            user = User.objects.get(username=value)
        except User.DoesNotExist as exc:
            raise serializers.ValidationError("Unknown username.") from exc
        self.context["target_user"] = user
        return value


class DataAccessRequestSerializer(serializers.ModelSerializer):
    app_name = serializers.CharField(source="app.name", read_only=True)
    requester_username = serializers.CharField(source="app.owner.username", read_only=True)
    target_username = serializers.CharField(source="target_user.username", read_only=True)

    class Meta:
        model = DataAccessRequest
        fields = [
            "id",
            "app",
            "app_name",
            "requester_username",
            "target_user",
            "target_username",
            "status",
            "purpose",
            "requested_at",
            "decided_at",
            "decision_note",
        ]
        read_only_fields = fields


class DataAccessDecisionSerializer(serializers.Serializer):
    decision_note = serializers.CharField(max_length=255, required=False, allow_blank=True)


class ExternalMedicineHistoryResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    total_pages = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = MedicineHistoryEntrySerializer(many=True)


def set_request_status(request_obj: DataAccessRequest, status: str, note: str = "") -> DataAccessRequest:
    request_obj.status = status
    request_obj.decision_note = note
    request_obj.decided_at = timezone.now()
    request_obj.save(update_fields=["status", "decision_note", "decided_at"])
    return request_obj


def serialize_medicine_history_queryset(queryset):
    return MedicineHistoryEntrySerializer(queryset, many=True).data
