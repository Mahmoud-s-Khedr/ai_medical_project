from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Count
from django.test import TestCase

from api.models import DataAccessRequest, DeveloperApiKey, DeveloperApp, Medicine, MedicineHistoryEntry


class SeedDemoDataCommandTests(TestCase):
    def setUp(self):
        super().setUp()
        Medicine.objects.bulk_create(
            [
                Medicine(trade_name="Panadol", active_ingredient="Paracetamol", strength="500mg"),
                Medicine(trade_name="Brufen", active_ingredient="Ibuprofen", strength="400mg"),
                Medicine(trade_name="Augmentin", active_ingredient="Amoxicillin + Clavulanic Acid", strength="1g"),
                Medicine(trade_name="Zyrtec", active_ingredient="Cetirizine", strength="10mg"),
            ]
        )

    def run_seed(self, *args):
        out = StringIO()
        call_command("seed_demo_data", *args, stdout=out)
        return out.getvalue()

    def test_first_run_creates_expected_minimum_for_large_profile(self):
        output = self.run_seed("--profile", "large")

        self.assertIn("Seed completed (profile=large)", output)
        self.assertGreaterEqual(MedicineHistoryEntry.objects.count(), 6)
        self.assertGreaterEqual(DeveloperApp.objects.count(), 3)
        self.assertGreaterEqual(DeveloperApiKey.objects.count(), 3)
        self.assertGreaterEqual(DataAccessRequest.objects.count(), 6)

    def test_second_run_is_idempotent_no_duplicate_rows(self):
        self.run_seed("--profile", "large")
        first_counts = {
            "history": MedicineHistoryEntry.objects.count(),
            "apps": DeveloperApp.objects.count(),
            "keys": DeveloperApiKey.objects.count(),
            "access": DataAccessRequest.objects.count(),
        }

        self.run_seed("--profile", "large")
        second_counts = {
            "history": MedicineHistoryEntry.objects.count(),
            "apps": DeveloperApp.objects.count(),
            "keys": DeveloperApiKey.objects.count(),
            "access": DataAccessRequest.objects.count(),
        }

        self.assertEqual(first_counts, second_counts)

    def test_seeded_history_rows_obey_validation_rules(self):
        self.run_seed("--profile", "large")

        for entry in MedicineHistoryEntry.objects.all():
            entry.full_clean()

        self.assertFalse(MedicineHistoryEntry.objects.filter(status="current", end_date__isnull=False).exists())

    def test_active_access_request_uniqueness_respected_on_rerun(self):
        self.run_seed("--profile", "large")
        self.run_seed("--profile", "large")

        duplicates = (
            DataAccessRequest.objects.filter(status__in=[DataAccessRequest.STATUS_PENDING, DataAccessRequest.STATUS_APPROVED])
            .values("app_id", "target_user_id")
            .annotate(active_count=Count("id"))
            .filter(active_count__gt=1)
        )
        self.assertFalse(duplicates.exists())

    def test_show_credentials_prints_expected_sections(self):
        output = self.run_seed("--profile", "large", "--show-credentials")

        self.assertIn("WARNING: local/dev seed credentials", output)
        self.assertIn("Shared password for seeded users", output)
        self.assertIn("Seeded usernames", output)
        self.assertTrue(
            "Newly created raw API keys (shown once):" in output
            or "Newly created raw API keys: none" in output
        )

    def test_fails_when_catalog_is_empty(self):
        Medicine.objects.all().delete()
        with self.assertRaises(CommandError):
            self.run_seed("--profile", "large")
