from __future__ import annotations

import io
from datetime import date
from unittest.mock import AsyncMock, patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Medicine, MedicineHistoryEntry
from .search import _SEARCH_CACHE, search_medicines_ranked
from . import views as api_views

User = get_user_model()


def make_user(username="testuser", email="test@example.com", password="StrongPass123!", **kwargs):
    return User.objects.create_user(username=username, email=email, password=password, **kwargs)


def auth_header(user):
    refresh = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}


def make_medicine(**kwargs):
    defaults = {"trade_name": "TestMed", "active_ingredient": "Paracetamol", "strength": "500mg"}
    defaults.update(kwargs)
    return Medicine.objects.create(**defaults)


def make_png_image_bytes():
    img = Image.new("RGB", (100, 50), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


class MedicineTests(APITestCase):
    URL = "/api/medicines/"

    def setUp(self):
        self.user = make_user()
        self.admin = make_user(username="admin", email="admin@example.com", is_staff=True)
        self.med = make_medicine()

    def test_list_authenticated(self):
        resp = self.client.get(self.URL, **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("results", resp.data)

    def test_search_medicines_fuzzy_typo(self):
        Medicine.objects.create(trade_name="Panadol", active_ingredient="Paracetamol", drug_class="Analgesic")
        with self.settings(SEARCH_FUZZY_MIN_SCORE=0.3):
            resp = self.client.get(f"{self.URL}?search=Panadool", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [row["trade_name"] for row in resp.data["results"]]
        self.assertIn("Panadol", names)

    def test_write_permissions(self):
        resp_user = self.client.post(self.URL, {"trade_name": "Aspirin"}, **auth_header(self.user))
        self.assertEqual(resp_user.status_code, status.HTTP_403_FORBIDDEN)
        resp_admin = self.client.post(self.URL, {"trade_name": "Aspirin"}, **auth_header(self.admin))
        self.assertEqual(resp_admin.status_code, status.HTTP_201_CREATED)


class OCRSearchTests(APITestCase):
    URL = "/api/uploads/ocr-search/"

    def setUp(self):
        self.user = make_user()
        make_medicine(trade_name="Panadol", active_ingredient="Paracetamol", strength="500mg")

    def test_ocr_requires_auth(self):
        resp = self.client.post(self.URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ocr_with_image(self):
        img_bytes = make_png_image_bytes()
        resp = self.client.post(self.URL, {"image": img_bytes, "top_k": 3}, format="multipart", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("matched_items", resp.data)

    @patch("api.views._fuzzy_search_medicines", return_value=[])
    @patch("api.views._ocr_tokens_from_image", return_value=(["Unreadable"], {"confidence": 0.25, "angle": 0, "engine": "mock"}))
    def test_ocr_low_confidence_triggers_retake(self, _mock_ocr, _fuzzy):
        img_bytes = make_png_image_bytes()
        resp = self.client.post(self.URL, {"image": img_bytes}, format="multipart", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["match_confidence_tier"], "low")
        self.assertEqual(resp.data["action_hint"], "retake_photo")


class TextToSpeechTests(APITestCase):
    URL = "/api/tts/speak/"

    def setUp(self):
        self.user = make_user()

    def test_tts_requires_auth(self):
        resp = self.client.post(self.URL, {"text": "hello"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tts_rejects_empty_text(self):
        resp = self.client.post(self.URL, {"text": "   "}, format="json", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_tts_rejects_too_long_text(self):
        with self.settings(TTS_MAX_CHARS=10):
            resp = self.client.post(self.URL, {"text": "a" * 20}, format="json", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("text", resp.data)

    @patch("api.views._generate_tts_mp3_bytes", new_callable=AsyncMock)
    def test_tts_english_text_returns_mp3(self, mock_generate):
        mock_generate.return_value = b"ID3-en"
        resp = self.client.post(self.URL, {"text": "Panadol 500 mg after meal"}, format="json", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp["Content-Type"], "audio/mpeg")
        self.assertEqual(resp.content, b"ID3-en")

    @patch("api.views._generate_tts_mp3_bytes", new_callable=AsyncMock)
    def test_tts_arabic_text_returns_mp3(self, mock_generate):
        mock_generate.return_value = b"ID3-ar"
        resp = self.client.post(self.URL, {"text": "بانادول ٥٠٠ مجم بعد الأكل"}, format="json", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp["Content-Type"], "audio/mpeg")
        self.assertEqual(resp.content, b"ID3-ar")

    @patch("api.views._stitch_mp3_segments_with_silence")
    @patch("api.views._generate_tts_mp3_bytes", new_callable=AsyncMock)
    def test_tts_mixed_text_defaults_to_dual_voice(self, mock_generate, mock_stitch):
        mock_generate.return_value = b"seg"
        mock_stitch.return_value = b"ID3-mixed"
        with self.settings(TTS_DEFAULT_VOICE_AR="ar-EG-SalmaNeural", TTS_DEFAULT_VOICE_EN="en-US-JennyNeural"):
            resp = self.client.post(
                self.URL,
                {"text": "Panadol 500 mg مرتين يوميا"},
                format="json",
                **auth_header(self.user),
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(mock_generate.await_count, 2)
        calls = [call.kwargs["voice"] for call in mock_generate.await_args_list]
        self.assertIn("ar-EG-SalmaNeural", calls)
        self.assertIn("en-US-JennyNeural", calls)
        mock_stitch.assert_called_once()

    @patch("api.views._generate_tts_mp3_bytes", new_callable=AsyncMock)
    def test_tts_voice_override_is_used(self, mock_generate):
        mock_generate.return_value = b"ID3-override"
        resp = self.client.post(
            self.URL,
            {"text": "Panadol 500 mg مرتين يوميا", "voice": "en-US-JennyNeural"},
            format="json",
            **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        kwargs = mock_generate.call_args.kwargs
        self.assertEqual(kwargs["voice"], "en-US-JennyNeural")

    @patch("api.views._stitch_mp3_segments_with_silence")
    @patch("api.views._generate_tts_mp3_bytes", new_callable=AsyncMock)
    def test_tts_dual_voice_overrides_are_used(self, mock_generate, mock_stitch):
        mock_generate.return_value = b"seg"
        mock_stitch.return_value = b"stitched"
        resp = self.client.post(
            self.URL,
            {
                "text": "Panadol 500 mg مرتين يوميا",
                "mixed_mode": "dual_voice",
                "voice_ar": "ar-EG-SalmaNeural",
                "voice_en": "en-US-JennyNeural",
            },
            format="json",
            **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        calls = [call.kwargs["voice"] for call in mock_generate.await_args_list]
        self.assertIn("ar-EG-SalmaNeural", calls)
        self.assertIn("en-US-JennyNeural", calls)

    @patch("api.views._generate_tts_mp3_bytes", new_callable=AsyncMock)
    def test_tts_invalid_mixed_mode_rejected(self, mock_generate):
        resp = self.client.post(
            self.URL,
            {"text": "hello", "mixed_mode": "bad_mode"},
            format="json",
            **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        mock_generate.assert_not_called()

    def test_tts_rejects_segment_overflow(self):
        mixed_text = " ".join(["A ب"] * 20)
        with self.settings(TTS_MAX_SEGMENTS=2):
            resp = self.client.post(self.URL, {"text": mixed_text}, format="json", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("text", resp.data)

    @patch("api.views._generate_tts_mp3_bytes", new_callable=AsyncMock, side_effect=RuntimeError("provider down"))
    def test_tts_provider_failure_returns_503(self, _mock_generate):
        resp = self.client.post(self.URL, {"text": "hello"}, format="json", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)


class TextToSpeechSegmentationTests(APITestCase):
    def test_neutral_tokens_attach_to_nearest_language(self):
        segments = api_views._resolve_mixed_segments("خذ Panadol 500 mg بعد الأكل")
        self.assertGreaterEqual(len(segments), 2)
        self.assertEqual(segments[0]["language"], "arabic")
        self.assertEqual(segments[1]["language"], "english")


class MedicineHistoryModelTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.med = make_medicine()

    def test_current_rejects_end_date(self):
        entry = MedicineHistoryEntry(
            user=self.user,
            medicine=self.med,
            medicine_name="TestMed",
            status="current",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 15),
        )
        with self.assertRaises(Exception):
            entry.full_clean()

    def test_past_accepts_valid_date_range(self):
        entry = MedicineHistoryEntry(
            user=self.user,
            medicine=self.med,
            medicine_name="TestMed",
            status="past",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 15),
        )
        entry.full_clean()

    def test_past_rejects_invalid_date_range(self):
        entry = MedicineHistoryEntry(
            user=self.user,
            medicine=self.med,
            medicine_name="TestMed",
            status="past",
            start_date=date(2026, 1, 20),
            end_date=date(2026, 1, 15),
        )
        with self.assertRaises(Exception):
            entry.full_clean()


class MedicineHistoryApiTests(APITestCase):
    URL = "/api/medicine-history/"

    def setUp(self):
        self.user = make_user()
        self.other_user = make_user(username="other", email="other@example.com")
        self.med = make_medicine()

    def test_auth_required(self):
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_crud_and_user_scoping(self):
        create_resp = self.client.post(
            self.URL,
            {
                "medicine_id": self.med.pk,
                "medicine_name": "TestMed",
                "status": "current",
                "dose": "1 tablet",
                "start_date": "2026-01-01",
            },
            format="json",
            **auth_header(self.user),
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        entry_id = create_resp.data["id"]

        own_detail = self.client.get(f"{self.URL}{entry_id}/", **auth_header(self.user))
        self.assertEqual(own_detail.status_code, status.HTTP_200_OK)

        other_detail = self.client.get(f"{self.URL}{entry_id}/", **auth_header(self.other_user))
        self.assertEqual(other_detail.status_code, status.HTTP_404_NOT_FOUND)

        patch_resp = self.client.patch(
            f"{self.URL}{entry_id}/",
            {"status": "past", "end_date": "2026-02-01"},
            format="json",
            **auth_header(self.user),
        )
        self.assertEqual(patch_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_resp.data["status"], "past")

        delete_resp = self.client.delete(f"{self.URL}{entry_id}/", **auth_header(self.user))
        self.assertEqual(delete_resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_status_filter(self):
        MedicineHistoryEntry.objects.create(user=self.user, medicine_name="A", status="current")
        MedicineHistoryEntry.objects.create(user=self.user, medicine_name="B", status="past")
        resp = self.client.get(f"{self.URL}?status=current", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [r["medicine_name"] for r in resp.data["results"]]
        self.assertIn("A", names)
        self.assertNotIn("B", names)


class CombinedSearchServiceTests(APITestCase):
    def setUp(self):
        make_medicine(trade_name="Panadol", active_ingredient="Paracetamol", drug_class="Analgesic")
        make_medicine(trade_name="Panadol Extra", active_ingredient="Paracetamol", drug_class="Analgesic")
        make_medicine(trade_name="Brufen", active_ingredient="Ibuprofen", drug_class="NSAID")
        _SEARCH_CACHE["items"] = []
        _SEARCH_CACHE["loaded_at"] = 0.0

    def test_ranked_search_returns_typo_match(self):
        rows = search_medicines_ranked("Panadool", limit=5)
        names = [row["medicine"].trade_name for row in rows]
        self.assertIn("Panadol", names)


class MedicineHistoryMigrationTests(TransactionTestCase):
    migrate_from = ("api", "0005_medicine_active_ingredient_norm_and_more")
    migrate_to = ("api", "0006_medicine_history_refactor")
    reset_sequences = True

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps

        UserModel = old_apps.get_model("auth", "User")
        MedicineModel = old_apps.get_model("api", "Medicine")
        ReminderModel = old_apps.get_model("api", "MedicationReminder")

        user = UserModel.objects.create_user(username="mig_user", email="mig@example.com", password="StrongPass123!")
        med = MedicineModel.objects.create(trade_name="MigMed")

        ReminderModel.objects.create(
            user_id=user.id,
            medicine_id=med.id,
            medicine_name="CurrentReminder",
            dose="1 tablet",
            times=["08:00"],
            start_date="2026-01-01",
            is_active=True,
        )
        ReminderModel.objects.create(
            user_id=user.id,
            medicine_id=med.id,
            medicine_name="PastReminder",
            dose="2 tablets",
            times=["09:00"],
            start_date="2026-01-10",
            end_date="2026-02-01",
            is_active=False,
        )

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        self.apps = executor.loader.project_state([self.migrate_to]).apps

    def test_backfills_history_and_drops_old_tables(self):
        HistoryModel = self.apps.get_model("api", "MedicineHistoryEntry")
        rows = list(HistoryModel.objects.values_list("medicine_name", "status", "end_date"))
        self.assertEqual(len(rows), 2)
        self.assertIn(("CurrentReminder", "current", None), rows)
        self.assertIn(("PastReminder", "past", date(2026, 2, 1)), rows)

        tables = connection.introspection.table_names()
        self.assertNotIn("api_medicationreminder", tables)
        self.assertNotIn("api_medicalrecord", tables)
