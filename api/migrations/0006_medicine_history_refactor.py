from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def backfill_medicine_history_from_reminders(apps, schema_editor):
    Reminder = apps.get_model("api", "MedicationReminder")
    History = apps.get_model("api", "MedicineHistoryEntry")

    history_rows = []
    for reminder in Reminder.objects.all().iterator():
        status = "current" if reminder.is_active else "past"
        end_date = None if reminder.is_active else reminder.end_date
        history_rows.append(
            History(
                user_id=reminder.user_id,
                medicine_id=reminder.medicine_id,
                medicine_name=reminder.medicine_name,
                status=status,
                dose=reminder.dose or "",
                start_date=reminder.start_date,
                end_date=end_date,
                notes=reminder.notes or "",
                created_at=reminder.created_at,
                updated_at=reminder.updated_at,
            )
        )

    if history_rows:
        History.objects.bulk_create(history_rows, batch_size=500)


def reverse_backfill_medicine_history_to_reminders(apps, schema_editor):
    Reminder = apps.get_model("api", "MedicationReminder")
    History = apps.get_model("api", "MedicineHistoryEntry")

    reminder_rows = []
    for entry in History.objects.all().iterator():
        is_active = entry.status == "current"
        reminder_rows.append(
            Reminder(
                user_id=entry.user_id,
                medicine_id=entry.medicine_id,
                medicine_name=entry.medicine_name,
                dose=entry.dose or "",
                times=["08:00"],
                start_date=entry.start_date,
                end_date=entry.end_date,
                timezone="Africa/Cairo",
                notes=entry.notes or "",
                is_active=is_active,
                created_at=entry.created_at,
                updated_at=entry.updated_at,
            )
        )

    if reminder_rows:
        Reminder.objects.bulk_create(reminder_rows, batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("api", "0005_medicine_active_ingredient_norm_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="MedicineHistoryEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("medicine_name", models.CharField(max_length=255)),
                ("status", models.CharField(choices=[("current", "Current"), ("past", "Past")], default="current", max_length=20)),
                ("dose", models.CharField(blank=True, max_length=120)),
                ("start_date", models.DateField(blank=True, null=True)),
                ("end_date", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("medicine", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="history_entries", to="api.medicine")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="medicine_history_entries", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-updated_at", "medicine_name"],
                "indexes": [
                    models.Index(fields=["user", "status"], name="api_medicin_user_id_8e32bc_idx"),
                    models.Index(fields=["user", "start_date"], name="api_medicin_user_id_717e8e_idx"),
                ],
            },
        ),
        migrations.RunPython(backfill_medicine_history_from_reminders, reverse_backfill_medicine_history_to_reminders),
        migrations.DeleteModel(name="ReminderEvent"),
        migrations.DeleteModel(name="DoctorVisit"),
        migrations.DeleteModel(name="LabResult"),
        migrations.DeleteModel(name="VitalSign"),
        migrations.DeleteModel(name="Allergy"),
        migrations.DeleteModel(name="Diagnosis"),
        migrations.DeleteModel(name="MedicalRecord"),
        migrations.DeleteModel(name="MedicationReminder"),
    ]
