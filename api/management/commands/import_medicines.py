from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from api.models import Medicine


class Command(BaseCommand):
    help = "Import or update medicines from medicines.csv."

    def add_arguments(self, parser):
        parser.add_argument("--path", default="medicines.csv", help="CSV file path.")

    def handle(self, *args, **options):
        csv_path = Path(options["path"])
        if not csv_path.exists():
            raise CommandError(f"CSV file not found: {csv_path}")

        created = 0
        updated = 0
        with csv_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                trade_name = row.get("trade_name", "").strip()
                if not trade_name:
                    continue

                defaults = {
                    "active_ingredient": row.get("active_ingredient", "").strip(),
                    "strength": row.get("strength", "").strip(),
                    "dosage_form": row.get("dosage_form", "").strip(),
                    "drug_class": row.get("drug_class", "").strip(),
                    "common_side_effects": row.get("common_side_effects", "").strip(),
                    "serious_warning": row.get("serious_warning", "").strip(),
                    "similar_active_ingredients": row.get("similar_active_ingredients", "").strip(),
                    "similarity_risk_symptoms": row.get("similarity_risk_symptoms", "").strip(),
                    "switching_note": row.get("switching_note", "").strip(),
                    "interaction_notes": row.get("interaction_notes", "").strip(),
                }
                _medicine, was_created = Medicine.objects.update_or_create(
                    trade_name=trade_name,
                    defaults=defaults,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(f"Imported medicines. created={created}, updated={updated}"))

