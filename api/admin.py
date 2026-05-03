from __future__ import annotations

from django.contrib import admin

from .models import Medicine, MedicineHistoryEntry


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
