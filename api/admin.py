from __future__ import annotations

from django.contrib import admin

from .models import DataAccessRequest, DeveloperApiKey, DeveloperApp, Medicine, MedicineHistoryEntry


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ("trade_name", "active_ingredient", "strength", "dosage_form")
    search_fields = ("trade_name", "active_ingredient", "search_aliases")


@admin.register(MedicineHistoryEntry)
class MedicineHistoryEntryAdmin(admin.ModelAdmin):
    list_display = ("medicine_name", "user", "status", "dose", "start_date", "end_date")
    list_filter = ("status", "user")
    search_fields = ("medicine_name", "dose", "user__username", "user__email")
    raw_id_fields = ("user",)


@admin.register(DeveloperApp)
class DeveloperAppAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "owner__username", "owner__email")
    raw_id_fields = ("owner",)


@admin.register(DeveloperApiKey)
class DeveloperApiKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "app", "key_prefix", "created_at", "last_used_at", "revoked_at")
    list_filter = ("revoked_at",)
    search_fields = ("name", "app__name", "key_prefix")
    raw_id_fields = ("app",)


@admin.register(DataAccessRequest)
class DataAccessRequestAdmin(admin.ModelAdmin):
    list_display = ("app", "target_user", "status", "requested_at", "decided_at")
    list_filter = ("status",)
    search_fields = ("app__name", "target_user__username", "target_user__email", "purpose")
    raw_id_fields = ("app", "target_user")
