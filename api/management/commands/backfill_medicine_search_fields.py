from __future__ import annotations

from django.core.management.base import BaseCommand

from api.medicine_search_enrichment import build_aliases, normalize_text, split_ingredient_tokens
from api.models import Medicine


class Command(BaseCommand):
    help = "Backfill internal medicine search fields (normalized values, aliases, ingredient tokens)."

    def handle(self, *args, **options):
        updated = 0
        for medicine in Medicine.objects.all().iterator():
            trade_name_norm = normalize_text(medicine.trade_name)
            active_ingredient_norm = normalize_text(medicine.active_ingredient)
            drug_class_norm = normalize_text(medicine.drug_class)
            active_ingredient_tokens = "; ".join(split_ingredient_tokens(medicine.active_ingredient))
            search_aliases = build_aliases(
                medicine.trade_name,
                medicine.active_ingredient,
                explicit_aliases=medicine.search_aliases,
            )

            changed = False
            if medicine.trade_name_norm != trade_name_norm:
                medicine.trade_name_norm = trade_name_norm
                changed = True
            if medicine.active_ingredient_norm != active_ingredient_norm:
                medicine.active_ingredient_norm = active_ingredient_norm
                changed = True
            if medicine.drug_class_norm != drug_class_norm:
                medicine.drug_class_norm = drug_class_norm
                changed = True
            if medicine.active_ingredient_tokens != active_ingredient_tokens:
                medicine.active_ingredient_tokens = active_ingredient_tokens
                changed = True
            if medicine.search_aliases != search_aliases:
                medicine.search_aliases = search_aliases
                changed = True

            if changed:
                medicine.save(update_fields=[
                    "trade_name_norm",
                    "active_ingredient_norm",
                    "drug_class_norm",
                    "active_ingredient_tokens",
                    "search_aliases",
                ])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Backfill complete. updated={updated}"))
