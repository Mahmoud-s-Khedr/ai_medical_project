from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import DataAccessRequest, DeveloperApiKey, DeveloperApp, Medicine, MedicineHistoryEntry

User = get_user_model()
DEFAULT_PASSWORD = "StrongPass123!"


@dataclass(frozen=True)
class SeedUser:
    username: str
    email: str
    first_name: str
    last_name: str
    is_staff: bool = False
    is_superuser: bool = False


class Command(BaseCommand):
    help = "Seed demo users and relational data for local/dev testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--profile",
            choices=["core", "integration", "large"],
            default="large",
            help="Seed profile (default: large).",
        )
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help="Password assigned to seeded users (default: StrongPass123!).",
        )
        parser.add_argument(
            "--show-credentials",
            action="store_true",
            help="Print seeded usernames/password and newly generated API keys.",
        )

    def handle(self, *args, **options):
        profile = options["profile"]
        password = options["password"]
        show_credentials = options["show_credentials"]

        counters = {
            "users_created": 0,
            "users_updated": 0,
            "history_created": 0,
            "history_updated": 0,
            "apps_created": 0,
            "apps_updated": 0,
            "keys_created": 0,
            "keys_updated": 0,
            "access_created": 0,
            "access_updated": 0,
        }
        created_raw_keys: list[tuple[str, str, str]] = []

        with transaction.atomic():
            users = self._seed_users(profile, password, counters)
            medicines = self._get_imported_medicines()
            self._seed_history(profile, users, medicines, counters)

            if profile in {"integration", "large"}:
                apps = self._seed_apps(profile, users, counters)
                created_raw_keys.extend(self._seed_api_keys(apps, counters))
                self._seed_access_requests(profile, users, apps, counters)

        self._print_summary(profile, counters)

        if show_credentials:
            self._print_credentials(password, users, created_raw_keys)

    def _seed_users(self, profile: str, password: str, counters: dict[str, int]) -> dict[str, User]:
        base_users = [
            SeedUser("seed_admin", "seed_admin@example.com", "Seed", "Admin", is_staff=True, is_superuser=True),
            SeedUser("seed_patient_1", "seed_patient_1@example.com", "Amina", "Hassan"),
            SeedUser("seed_patient_2", "seed_patient_2@example.com", "Omar", "Farouk"),
        ]

        if profile in {"integration", "large"}:
            base_users.extend(
                [
                    SeedUser("seed_dev_1", "seed_dev_1@example.com", "Nora", "Sami"),
                    SeedUser("seed_dev_2", "seed_dev_2@example.com", "Karim", "Adel"),
                ]
            )

        if profile == "large":
            base_users.extend(
                [
                    SeedUser("seed_patient_3", "seed_patient_3@example.com", "Layla", "Mahmoud"),
                    SeedUser("seed_patient_4", "seed_patient_4@example.com", "Youssef", "Nabil"),
                    SeedUser("seed_patient_5", "seed_patient_5@example.com", "Mariam", "Fady"),
                    SeedUser("seed_dev_3", "seed_dev_3@example.com", "Hana", "Mina"),
                ]
            )

        seeded: dict[str, User] = {}
        for row in base_users:
            user, created = User.objects.get_or_create(
                username=row.username,
                defaults={
                    "email": row.email.lower(),
                    "first_name": row.first_name,
                    "last_name": row.last_name,
                    "is_staff": row.is_staff,
                    "is_superuser": row.is_superuser,
                    "is_active": True,
                },
            )

            changed_fields: list[str] = []
            if user.email != row.email.lower():
                user.email = row.email.lower()
                changed_fields.append("email")
            if user.first_name != row.first_name:
                user.first_name = row.first_name
                changed_fields.append("first_name")
            if user.last_name != row.last_name:
                user.last_name = row.last_name
                changed_fields.append("last_name")
            if user.is_staff != row.is_staff:
                user.is_staff = row.is_staff
                changed_fields.append("is_staff")
            if user.is_superuser != row.is_superuser:
                user.is_superuser = row.is_superuser
                changed_fields.append("is_superuser")
            if not user.is_active:
                user.is_active = True
                changed_fields.append("is_active")

            if not user.check_password(password):
                user.set_password(password)
                changed_fields.append("password")

            if changed_fields:
                user.save(update_fields=changed_fields)

            if created:
                counters["users_created"] += 1
            else:
                counters["users_updated"] += 1
            seeded[row.username] = user

        return seeded

    def _get_imported_medicines(self) -> list[Medicine]:
        existing = list(Medicine.objects.order_by("id")[:8])
        if existing:
            return existing

        raise CommandError(
            "No medicines found. Import the catalog first using: "
            "python manage.py import_medicines --path medicines.csv"
        )

    def _seed_history(self, profile: str, users: dict[str, User], medicines: list[Medicine], counters: dict[str, int]) -> None:
        if not medicines:
            raise CommandError("No medicines are available for history seeding.")

        rows = [
            {
                "username": "seed_patient_1",
                "medicine": medicines[0],
                "medicine_name": medicines[0].trade_name,
                "status": "current",
                "dose": "1 tablet daily",
                "start_date": date(2026, 1, 2),
                "end_date": None,
                "notes": "Primary pain management",
            },
            {
                "username": "seed_patient_1",
                "medicine": medicines[min(1, len(medicines) - 1)],
                "medicine_name": medicines[min(1, len(medicines) - 1)].trade_name,
                "status": "past",
                "dose": "1 tablet twice daily",
                "start_date": date(2025, 10, 1),
                "end_date": date(2025, 10, 14),
                "notes": "Completed short course",
            },
            {
                "username": "seed_patient_2",
                "medicine": medicines[min(2, len(medicines) - 1)],
                "medicine_name": medicines[min(2, len(medicines) - 1)].trade_name,
                "status": "current",
                "dose": "5ml every 8h",
                "start_date": date(2026, 2, 5),
                "end_date": None,
                "notes": "Monitored by physician",
            },
        ]

        if profile == "large":
            rows.extend(
                [
                    {
                        "username": "seed_patient_3",
                        "medicine": medicines[min(3, len(medicines) - 1)],
                        "medicine_name": medicines[min(3, len(medicines) - 1)].trade_name,
                        "status": "past",
                        "dose": "10mg daily",
                        "start_date": date(2025, 11, 1),
                        "end_date": date(2025, 12, 1),
                        "notes": "Seasonal treatment",
                    },
                    {
                        "username": "seed_patient_4",
                        "medicine": medicines[min(1, len(medicines) - 1)],
                        "medicine_name": medicines[min(1, len(medicines) - 1)].trade_name,
                        "status": "current",
                        "dose": "1 tablet as needed",
                        "start_date": date(2026, 3, 12),
                        "end_date": None,
                        "notes": "PRN usage",
                    },
                    {
                        "username": "seed_patient_5",
                        "medicine": medicines[0],
                        "medicine_name": medicines[0].trade_name,
                        "status": "past",
                        "dose": "2 tablets daily",
                        "start_date": date(2025, 8, 20),
                        "end_date": date(2025, 9, 3),
                        "notes": "Post-operative cycle",
                    },
                ]
            )

        for row in rows:
            user = users.get(row["username"])
            if not user:
                continue

            entry, created = MedicineHistoryEntry.objects.update_or_create(
                user=user,
                medicine_name=row["medicine_name"],
                status=row["status"],
                start_date=row["start_date"],
                defaults={
                    "medicine": row["medicine"],
                    "dose": row["dose"],
                    "end_date": row["end_date"],
                    "notes": row["notes"],
                },
            )
            entry.full_clean()

            if created:
                counters["history_created"] += 1
            else:
                counters["history_updated"] += 1

    def _seed_apps(self, profile: str, users: dict[str, User], counters: dict[str, int]) -> dict[str, DeveloperApp]:
        rows = [
            ("seed_dev_1", "seed-dev-app-primary", "Primary integration app for QA."),
            ("seed_dev_2", "seed-dev-app-secondary", "Secondary integration app for access testing."),
        ]
        if profile == "large":
            rows.append(("seed_dev_3", "seed-dev-app-analytics", "Analytics consumer app for pagination tests."))

        apps: dict[str, DeveloperApp] = {}
        for username, app_name, description in rows:
            owner = users.get(username)
            if not owner:
                continue

            app, created = DeveloperApp.objects.update_or_create(
                owner=owner,
                name=app_name,
                defaults={"description": description, "is_active": True},
            )
            if created:
                counters["apps_created"] += 1
            else:
                counters["apps_updated"] += 1
            apps[app_name] = app

        return apps

    def _seed_api_keys(self, apps: dict[str, DeveloperApp], counters: dict[str, int]) -> list[tuple[str, str, str]]:
        rows = [
            ("seed-dev-app-primary", "primary-key"),
            ("seed-dev-app-secondary", "secondary-key"),
            ("seed-dev-app-analytics", "analytics-key"),
        ]

        raw_keys: list[tuple[str, str, str]] = []
        for app_name, key_name in rows:
            app = apps.get(app_name)
            if not app:
                continue

            existing = DeveloperApiKey.objects.filter(app=app, name=key_name).first()
            if existing is None:
                raw_key = f"dev_{secrets.token_urlsafe(32)}"
                key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
                key = DeveloperApiKey.objects.create(
                    app=app,
                    name=key_name,
                    key_prefix=raw_key[:12],
                    key_hash=key_hash,
                )
                counters["keys_created"] += 1
                raw_keys.append((app.name, key.name, raw_key))
            else:
                if existing.revoked_at is not None:
                    existing.revoked_at = None
                    existing.save(update_fields=["revoked_at"])
                counters["keys_updated"] += 1

        return raw_keys

    def _seed_access_requests(
        self,
        profile: str,
        users: dict[str, User],
        apps: dict[str, DeveloperApp],
        counters: dict[str, int],
    ) -> None:
        rows = [
            {
                "app": "seed-dev-app-primary",
                "target": "seed_patient_1",
                "status": DataAccessRequest.STATUS_APPROVED,
                "purpose": "seed-approved-history-share",
                "decision_note": "Approved for integration QA",
            },
            {
                "app": "seed-dev-app-primary",
                "target": "seed_patient_2",
                "status": DataAccessRequest.STATUS_PENDING,
                "purpose": "seed-pending-history-share",
                "decision_note": "",
            },
            {
                "app": "seed-dev-app-secondary",
                "target": "seed_patient_1",
                "status": DataAccessRequest.STATUS_REJECTED,
                "purpose": "seed-rejected-history-share",
                "decision_note": "Rejected during consent demo",
            },
            {
                "app": "seed-dev-app-secondary",
                "target": "seed_patient_2",
                "status": DataAccessRequest.STATUS_REVOKED,
                "purpose": "seed-revoked-history-share",
                "decision_note": "Revoked after trial period",
            },
        ]

        if profile == "large":
            rows.extend(
                [
                    {
                        "app": "seed-dev-app-analytics",
                        "target": "seed_patient_3",
                        "status": DataAccessRequest.STATUS_APPROVED,
                        "purpose": "seed-approved-analytics",
                        "decision_note": "Approved for analytics demo",
                    },
                    {
                        "app": "seed-dev-app-analytics",
                        "target": "seed_patient_4",
                        "status": DataAccessRequest.STATUS_PENDING,
                        "purpose": "seed-pending-analytics",
                        "decision_note": "",
                    },
                ]
            )

        for row in rows:
            app = apps.get(row["app"])
            target = users.get(row["target"])
            if not app or not target:
                continue

            request_obj, created = DataAccessRequest.objects.update_or_create(
                app=app,
                target_user=target,
                purpose=row["purpose"],
                defaults={
                    "status": row["status"],
                    "decision_note": row["decision_note"],
                },
            )

            if request_obj.status in {DataAccessRequest.STATUS_APPROVED, DataAccessRequest.STATUS_REJECTED, DataAccessRequest.STATUS_REVOKED}:
                if request_obj.decided_at is None:
                    request_obj.decided_at = request_obj.requested_at
                    request_obj.save(update_fields=["decided_at"])
            else:
                if request_obj.decided_at is not None:
                    request_obj.decided_at = None
                    request_obj.save(update_fields=["decided_at"])

            if created:
                counters["access_created"] += 1
            else:
                counters["access_updated"] += 1

    def _print_summary(self, profile: str, counters: dict[str, int]) -> None:
        self.stdout.write(self.style.SUCCESS(f"Seed completed (profile={profile})."))
        self.stdout.write("\nSummary:")
        self.stdout.write("- Users: created={users_created}, updated={users_updated}".format(**counters))
        self.stdout.write("- Medicines: using existing imported catalog rows")
        self.stdout.write("- History entries: created={history_created}, updated={history_updated}".format(**counters))
        self.stdout.write("- Developer apps: created={apps_created}, updated={apps_updated}".format(**counters))
        self.stdout.write("- API keys: created={keys_created}, updated={keys_updated}".format(**counters))
        self.stdout.write("- Access requests: created={access_created}, updated={access_updated}".format(**counters))

    def _print_credentials(self, password: str, users: dict[str, User], raw_keys: list[tuple[str, str, str]]) -> None:
        self.stdout.write("\nWARNING: local/dev seed credentials and one-time raw API keys follow.")
        self.stdout.write(f"- Shared password for seeded users: {password}")
        self.stdout.write("- Seeded usernames:")
        for username in sorted(users.keys()):
            self.stdout.write(f"  - {username}")

        if raw_keys:
            self.stdout.write("- Newly created raw API keys (shown once):")
            for app_name, key_name, raw_key in raw_keys:
                self.stdout.write(f"  - app={app_name} key_name={key_name} api_key={raw_key}")
        else:
            self.stdout.write("- Newly created raw API keys: none (all seed keys already existed).")
