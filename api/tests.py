from __future__ import annotations

import io
import tempfile
from datetime import date
from unittest.mock import patch

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db import IntegrityError, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    Allergy,
    Diagnosis,
    DoctorVisit,
    LabResult,
    MedicalRecord,
    MedicationReminder,
    Medicine,
    ReminderEvent,
    VitalSign,
)
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


def make_reminder(user, medicine=None, **kwargs):
    defaults = {
        "medicine_name": "TestMed",
        "dose": "1 tablet",
        "times": ["08:00", "20:00"],
        "start_date": date.today(),
        "user": user,
    }
    if medicine:
        defaults["medicine"] = medicine
    defaults.update(kwargs)
    return MedicationReminder.objects.create(**defaults)


def make_png_image_bytes():
    img = Image.new("RGB", (100, 50), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────────────────
# AUTH TESTS
# ─────────────────────────────────────────────────────────────

class RegisterTests(APITestCase):
    URL = "/api/auth/register/"

    def test_register_success(self):
        resp = self.client.post(self.URL, {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "StrongPass123!",
            "password2": "StrongPass123!",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)
        self.assertEqual(resp.data["user"]["email"], "newuser@example.com")

    def test_register_duplicate_email(self):
        make_user()
        resp = self.client.post(self.URL, {
            "username": "other",
            "email": "test@example.com",
            "password": "StrongPass123!",
            "password2": "StrongPass123!",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_password_mismatch(self):
        resp = self.client.post(self.URL, {
            "username": "mismatch",
            "email": "mismatch@example.com",
            "password": "StrongPass123!",
            "password2": "WrongPass999!",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_weak_password(self):
        resp = self.client.post(self.URL, {
            "username": "weakpass",
            "email": "weakpass@example.com",
            "password": "123",
            "password2": "123",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class LoginTests(APITestCase):
    URL = "/api/auth/token/"

    def setUp(self):
        self.user = make_user()

    def test_login_success(self):
        resp = self.client.post(self.URL, {"username": "testuser", "password": "StrongPass123!"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)

    def test_login_wrong_password(self):
        resp = self.client.post(self.URL, {"username": "testuser", "password": "wrongpassword"})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh(self):
        login = self.client.post(self.URL, {"username": "testuser", "password": "StrongPass123!"})
        resp = self.client.post("/api/auth/token/refresh/", {"refresh": login.data["refresh"]})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)

    def test_token_verify(self):
        login = self.client.post(self.URL, {"username": "testuser", "password": "StrongPass123!"})
        resp = self.client.post("/api/auth/token/verify/", {"token": login.data["access"]})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class MeTests(APITestCase):
    def setUp(self):
        self.user = make_user()

    def test_get_me(self):
        resp = self.client.get("/api/auth/me/", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["username"], "testuser")

    def test_get_me_unauthenticated(self):
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_me(self):
        resp = self.client.patch(
            "/api/auth/me/",
            {"first_name": "Ahmed"},
            **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["first_name"], "Ahmed")


class ChangePasswordTests(APITestCase):
    URL = "/api/auth/me/change-password/"

    def setUp(self):
        self.user = make_user()

    def test_change_password_success(self):
        resp = self.client.post(self.URL, {
            "old_password": "StrongPass123!",
            "new_password": "NewStrongPass456!",
            "new_password2": "NewStrongPass456!",
        }, **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewStrongPass456!"))

    def test_change_password_wrong_old(self):
        resp = self.client.post(self.URL, {
            "old_password": "wrongpassword",
            "new_password": "NewStrongPass456!",
            "new_password2": "NewStrongPass456!",
        }, **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class LogoutTests(APITestCase):
    def setUp(self):
        self.user = make_user()

    def test_logout_blacklists_refresh_token(self):
        login = self.client.post("/api/auth/token/", {"username": "testuser", "password": "StrongPass123!"})
        refresh = login.data["refresh"]
        resp = self.client.post("/api/auth/logout/", {"refresh": refresh}, **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Blacklisted token should fail to refresh
        resp2 = self.client.post("/api/auth/token/refresh/", {"refresh": refresh})
        self.assertEqual(resp2.status_code, status.HTTP_401_UNAUTHORIZED)


class PasswordResetTests(APITestCase):
    def setUp(self):
        self.user = make_user()

    def test_reset_request_known_email(self):
        resp = self.client.post("/api/auth/password-reset/", {"email": "test@example.com"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_reset_request_unknown_email(self):
        # Should still return 200 (don't reveal existence)
        resp = self.client.post("/api/auth/password-reset/", {"email": "nobody@example.com"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_reset_confirm_success(self):
        token_gen = PasswordResetTokenGenerator()
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = token_gen.make_token(self.user)
        resp = self.client.post("/api/auth/password-reset/confirm/", {
            "uid": uid,
            "token": token,
            "new_password": "BrandNewPass789!",
            "new_password2": "BrandNewPass789!",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNewPass789!"))

    def test_reset_confirm_invalid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        resp = self.client.post("/api/auth/password-reset/confirm/", {
            "uid": uid,
            "token": "invalid-token",
            "new_password": "BrandNewPass789!",
            "new_password2": "BrandNewPass789!",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────
# MEDICINE TESTS
# ─────────────────────────────────────────────────────────────

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

    def test_list_unauthenticated(self):
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_search_medicines(self):
        resp = self.client.get(f"{self.URL}?search=TestMed", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["results"][0]["trade_name"], "TestMed")

    def test_search_medicines_fuzzy_typo(self):
        Medicine.objects.create(trade_name="Panadol", active_ingredient="Paracetamol", drug_class="Analgesic")
        with self.settings(SEARCH_FUZZY_MIN_SCORE=0.3):
            resp = self.client.get(f"{self.URL}?search=Panadool", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [row["trade_name"] for row in resp.data["results"]]
        self.assertIn("Panadol", names)

    def test_search_medicines_exact_ranks_above_partial(self):
        Medicine.objects.create(trade_name="Panadol", active_ingredient="Paracetamol")
        Medicine.objects.create(trade_name="Panadol Extra", active_ingredient="Paracetamol")
        resp = self.client.get(f"{self.URL}?search=Panadol", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data["results"]), 2)
        self.assertEqual(resp.data["results"][0]["trade_name"], "Panadol")

    def test_get_medicine(self):
        resp = self.client.get(f"{self.URL}{self.med.pk}/", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["trade_name"], "TestMed")

    def test_create_medicine_as_admin(self):
        resp = self.client.post(self.URL, {"trade_name": "Aspirin"}, **auth_header(self.admin))
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_create_medicine_as_regular_user_forbidden(self):
        resp = self.client.post(self.URL, {"trade_name": "Aspirin"}, **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_medicine_as_admin(self):
        resp = self.client.delete(f"{self.URL}{self.med.pk}/", **auth_header(self.admin))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_medicine_as_regular_user_forbidden(self):
        resp = self.client.delete(f"{self.URL}{self.med.pk}/", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_pagination(self):
        for i in range(25):
            Medicine.objects.create(trade_name=f"Med{i:03d}")
        resp = self.client.get(self.URL, **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total_pages", resp.data)
        self.assertLessEqual(len(resp.data["results"]), 20)


class MedicineInteractionsTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.panadol = Medicine.objects.create(
            trade_name="Panadol",
            active_ingredient="Paracetamol",
            similar_active_ingredients="Ibuprofen, Aspirin",
            interaction_notes="Avoid with other NSAIDs",
            similarity_risk_symptoms="GI bleeding, kidney stress",
        )
        self.panadol_extra = Medicine.objects.create(
            trade_name="Panadol Extra",
            active_ingredient="Paracetamol",
        )
        self.brufen = Medicine.objects.create(
            trade_name="Brufen",
            active_ingredient="Ibuprofen",
        )
        self.unrelated = Medicine.objects.create(
            trade_name="Amoxil",
            active_ingredient="Amoxicillin",
        )

    def _url(self, pk):
        return f"/api/medicines/{pk}/interactions/"

    def test_interactions_requires_auth(self):
        resp = self.client.get(self._url(self.panadol.pk))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_same_active_ingredient_is_high_risk(self):
        resp = self.client.get(self._url(self.panadol.pk), **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        high = [c for c in resp.data["conflicts"] if c["conflict_type"] == "same_active_ingredient"]
        names = [c["medicine"]["trade_name"] for c in high]
        self.assertIn("Panadol Extra", names)
        self.assertTrue(all(c["risk_level"] == "high" for c in high))

    def test_similar_ingredient_is_medium_risk(self):
        resp = self.client.get(self._url(self.panadol.pk), **auth_header(self.user))
        medium = [c for c in resp.data["conflicts"] if c["conflict_type"] == "similar_active_ingredient"]
        names = [c["medicine"]["trade_name"] for c in medium]
        self.assertIn("Brufen", names)
        self.assertTrue(all(c["risk_level"] == "medium" for c in medium))

    def test_unrelated_medicine_not_in_conflicts(self):
        resp = self.client.get(self._url(self.panadol.pk), **auth_header(self.user))
        all_names = [c["medicine"]["trade_name"] for c in resp.data["conflicts"]]
        self.assertNotIn("Amoxil", all_names)

    def test_response_has_interaction_fields(self):
        resp = self.client.get(self._url(self.panadol.pk), **auth_header(self.user))
        for field in ["interaction_notes", "similarity_risk_symptoms", "switching_note", "total_conflicts", "conflicts"]:
            self.assertIn(field, resp.data)

    def test_no_conflicts_for_unrelated_medicine(self):
        resp = self.client.get(self._url(self.unrelated.pk), **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["total_conflicts"], 0)


# ─────────────────────────────────────────────────────────────
# REMINDER TESTS
# ─────────────────────────────────────────────────────────────

class ReminderTests(APITestCase):
    URL = "/api/reminders/"

    def setUp(self):
        self.user = make_user()
        self.other_user = make_user(username="other", email="other@example.com")
        self.med = make_medicine()

    def test_create_reminder(self):
        resp = self.client.post(self.URL, {
            "medicine_id": self.med.pk,
            "medicine_name": "TestMed",
            "dose": "1 tablet",
            "times": ["08:00", "20:00"],
            "start_date": str(date.today()),
        }, format="json", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["medicine_name"], "TestMed")

    def test_list_reminders_scoped_to_user(self):
        make_reminder(self.user)
        make_reminder(self.other_user, medicine_name="OtherMed")
        resp = self.client.get(self.URL, **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [r["medicine_name"] for r in resp.data["results"]]
        self.assertIn("TestMed", names)
        self.assertNotIn("OtherMed", names)

    def test_cannot_access_other_users_reminder(self):
        reminder = make_reminder(self.other_user)
        resp = self.client.get(f"{self.URL}{reminder.pk}/", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_filter_active_reminders(self):
        make_reminder(self.user)
        make_reminder(self.user, medicine_name="InactiveMed", is_active=False)
        resp = self.client.get(f"{self.URL}?is_active=true", **auth_header(self.user))
        names = [r["medicine_name"] for r in resp.data["results"]]
        self.assertNotIn("InactiveMed", names)

    def test_validate_times_format(self):
        resp = self.client.post(self.URL, {
            "medicine_name": "BadTime",
            "dose": "1 tablet",
            "times": ["8:00", "bad"],
            "start_date": str(date.today()),
        }, format="json", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_end_date_before_start_date(self):
        resp = self.client.post(self.URL, {
            "medicine_name": "DateMed",
            "dose": "1 tablet",
            "times": ["08:00"],
            "start_date": "2025-01-10",
            "end_date": "2025-01-05",
        }, format="json", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_reminder(self):
        reminder = make_reminder(self.user)
        resp = self.client.delete(f"{self.URL}{reminder.pk}/", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_reminder_user_is_required_at_db_level(self):
        with self.assertRaises(IntegrityError):
            MedicationReminder.objects.create(
                user=None,
                medicine_name="OrphanReminder",
                dose="1 tablet",
                times=["08:00"],
                start_date=date.today(),
            )


class ReminderEventTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.reminder = make_reminder(self.user)

    def test_create_event(self):
        resp = self.client.post(
            f"/api/reminders/{self.reminder.pk}/events/",
            {
                "scheduled_at": "2025-06-01T08:00:00Z",
                "status": "taken",
                "taken_at": "2025-06-01T08:10:00Z",
            },
            format="json",
            **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_create_taken_event_without_taken_at_is_invalid(self):
        resp = self.client.post(
            f"/api/reminders/{self.reminder.pk}/events/",
            {"scheduled_at": "2025-06-01T08:00:00Z", "status": "taken"},
            format="json",
            **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_events(self):
        ReminderEvent.objects.create(
            reminder=self.reminder,
            scheduled_at="2025-06-01T08:00:00Z",
            status="scheduled",
        )
        resp = self.client.get(
            f"/api/reminders/{self.reminder.pk}/events/",
            **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)


# ─────────────────────────────────────────────────────────────
# OCR TESTS
# ─────────────────────────────────────────────────────────────

class OCRSearchTests(APITestCase):
    URL = "/api/uploads/ocr-search/"

    def setUp(self):
        self.user = make_user()
        make_medicine(trade_name="Panadol", active_ingredient="Paracetamol", strength="500mg")

    def test_ocr_requires_auth(self):
        resp = self.client.post(self.URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ocr_no_image(self):
        resp = self.client.post(self.URL, **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_ocr_with_image(self):
        img_bytes = make_png_image_bytes()
        resp = self.client.post(
            self.URL,
            {"image": img_bytes, "top_k": 3},
            format="multipart",
            **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("matched_items", resp.data)
        self.assertIn("match_confidence_tier", resp.data)
        self.assertIn("action_hint", resp.data)
        self.assertIn("message", resp.data)
        self.assertIn("processing_time_ms", resp.data)

    def test_ocr_invalid_top_k(self):
        img_bytes = make_png_image_bytes()
        resp = self.client.post(
            self.URL,
            {"image": img_bytes, "top_k": "abc"},
            format="multipart",
            **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("api.views._ocr_tokens_from_image", return_value=(["Panadol"], {"confidence": 0.9, "angle": 0, "engine": "mock"}))
    def test_ocr_oversized_upload_returns_413(self, _mock_ocr):
        img_bytes = make_png_image_bytes()
        with self.settings(OCR_MAX_UPLOAD_BYTES=100):
            resp = self.client.post(
                self.URL,
                {"image": img_bytes, "top_k": 3},
                format="multipart",
                **auth_header(self.user),
            )
        self.assertEqual(resp.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        self.assertIn("error", resp.data)

    @patch("api.views._fuzzy_search_medicines")
    @patch("api.views._ocr_tokens_from_image", return_value=(["Extra Panadol", "Extra", "Panadol"], {"confidence": 0.95, "angle": 0, "engine": "mock"}))
    def test_ocr_filters_low_score_matches(self, _mock_ocr, fuzzy_mock):
        fuzzy_mock.side_effect = [
            [
                {"id": 1, "name": "Panadol Extra", "score": 0.95, "_rank_score": 1.19},
                {"id": 2, "name": "Amoxil", "score": 0.42, "_rank_score": 0.52},
            ],
            [
                {"id": 3, "name": "Panadol", "score": 0.78, "_rank_score": 0.78},
            ],
            [
                {"id": 4, "name": "RandomMed", "score": 0.39, "_rank_score": 0.39},
            ],
        ]
        img_bytes = make_png_image_bytes()
        with self.settings(OCR_RESULT_FLOOR=0.6):
            resp = self.client.post(self.URL, {"image": img_bytes}, format="multipart", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [row["name"] for row in resp.data["matched_items"]]
        self.assertIn("Panadol Extra", names)
        self.assertIn("Panadol", names)
        self.assertNotIn("Amoxil", names)
        self.assertNotIn("RandomMed", names)
        self.assertTrue(all("_rank_score" in row for row in resp.data["matched_items"]))

    @patch("api.views._fuzzy_search_medicines", return_value=[])
    @patch("api.views._ocr_tokens_from_image", return_value=(["Unreadable"], {"confidence": 0.25, "angle": 0, "engine": "mock"}))
    def test_ocr_low_confidence_triggers_retake(self, _mock_ocr, _fuzzy):
        img_bytes = make_png_image_bytes()
        resp = self.client.post(self.URL, {"image": img_bytes}, format="multipart", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["match_confidence_tier"], "low")
        self.assertEqual(resp.data["action_hint"], "retake_photo")
        self.assertTrue("retake" in resp.data["message"].lower())

    @patch("api.views._fuzzy_search_medicines")
    @patch("api.views._ocr_tokens_from_image", return_value=(["Noisy Phrase", "Panadol"], {"confidence": 0.82, "angle": 0, "engine": "mock"}))
    def test_ocr_fallback_tokens_run_when_phrase_is_weak(self, _mock_ocr, fuzzy_mock):
        fuzzy_mock.side_effect = [
            [{"id": 99, "name": "Noise", "score": 0.41, "_rank_score": 0.51}],
            [{"id": 1, "name": "Panadol", "score": 0.91, "_rank_score": 0.91}],
        ]
        img_bytes = make_png_image_bytes()
        with self.settings(OCR_RESULT_FLOOR=0.6):
            resp = self.client.post(self.URL, {"image": img_bytes}, format="multipart", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [row["name"] for row in resp.data["matched_items"]]
        self.assertIn("Panadol", names)

    def test_prepare_ocr_candidates_filters_short_stopwords_and_numbers(self):
        with self.settings(OCR_MIN_TOKEN_LENGTH=3, OCR_TOKEN_STOPWORDS="of,for,and,the"):
            candidates = api_views._prepare_ocr_candidates("Miconaz of FOR 20 and gel")
        self.assertTrue(candidates)
        self.assertEqual(candidates[0], "miconaz of for 20 and gel")
        self.assertIn("miconaz", candidates)
        self.assertIn("gel", candidates)
        self.assertNotIn("of", candidates)
        self.assertNotIn("for", candidates)
        self.assertNotIn("20", candidates)

    def test_ocr_includes_debug_fields_when_enabled(self):
        with self.settings(OCR_INCLUDE_MATCH_DEBUG=True):
            rows = api_views._fuzzy_search_medicines("Panadol", limit=3)
        self.assertTrue(rows)
        first = rows[0]
        self.assertIn("debug_length_factor", first)
        self.assertIn("debug_length_ratio", first)
        self.assertIn("debug_query_length", first)
        self.assertIn("debug_matched_length", first)


class OCRMedicineCacheTests(APITestCase):
    def setUp(self):
        make_medicine(trade_name="Panadol", active_ingredient="Paracetamol", strength="500mg")
        make_medicine(trade_name="Brufen", active_ingredient="Ibuprofen", strength="400mg")
        api_views._MEDICINE_CACHE["items"] = []
        api_views._MEDICINE_CACHE["loaded_at"] = 0.0

    def test_cache_loader_hits_db_once_within_ttl(self):
        with patch.object(Medicine.objects, "values_list", wraps=Medicine.objects.values_list) as values_list_mock:
            with self.settings(OCR_MEDICINE_CACHE_TTL_SECONDS=300):
                first = api_views._load_medicine_index()
                second = api_views._load_medicine_index()
        self.assertTrue(first)
        self.assertEqual(first, second)
        self.assertEqual(values_list_mock.call_count, 1)


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

    def test_ranked_search_includes_ingredient_hits(self):
        rows = search_medicines_ranked("Ibuprofen", limit=5)
        names = [row["medicine"].trade_name for row in rows]
        self.assertIn("Brufen", names)

    def test_ranked_search_dedupes_medicine_ids(self):
        rows = search_medicines_ranked("Panadol", limit=10)
        ids = [row["medicine"].id for row in rows]
        self.assertEqual(len(ids), len(set(ids)))

    def test_ranked_search_empty_query_returns_empty(self):
        rows = search_medicines_ranked("   ", limit=5)
        self.assertEqual(rows, [])

    def test_length_penalty_reduces_short_token_rank_score(self):
        with self.settings(SEARCH_LENGTH_PENALTY_ENABLED=True, SEARCH_LENGTH_PENALTY_STRENGTH=1.6):
            rows = search_medicines_ranked("of", limit=5)
        self.assertTrue(rows)
        self.assertTrue(all(row["_rank_score"] <= row["score"] for row in rows))

    def test_disable_length_penalty_preserves_ranking_signal(self):
        with self.settings(SEARCH_LENGTH_PENALTY_ENABLED=False):
            rows = search_medicines_ranked("Panadol", limit=5)
        self.assertTrue(rows)
        self.assertTrue(all("_debug_length_factor" in row for row in rows))
        self.assertTrue(all(row["_debug_length_factor"] == 1.0 for row in rows))

    def test_alias_query_improves_recall(self):
        target = make_medicine(
            trade_name="Miconaz Oral Gel",
            active_ingredient="Miconazole nitrate",
            search_aliases="miconazole gel; miconaz",
            trade_name_norm="miconaz oral gel",
            active_ingredient_norm="miconazole nitrate",
            drug_class_norm="topical oral antifungal",
            active_ingredient_tokens="miconazole nitrate; miconazole",
        )
        rows = search_medicines_ranked("miconaz", limit=5)
        self.assertTrue(rows)
        ids = [row["medicine"].id for row in rows]
        self.assertIn(target.id, ids)

    def test_ingredient_token_query_matches_brand(self):
        target = make_medicine(
            trade_name="Augmentin",
            active_ingredient="Amoxicillin + Clavulanic acid",
            search_aliases="co amoxiclav",
            trade_name_norm="augmentin",
            active_ingredient_norm="amoxicillin clavulanic acid",
            drug_class_norm="penicillin antibiotic",
            active_ingredient_tokens="amoxicillin; clavulanic acid",
        )
        rows = search_medicines_ranked("clavulanic acid", limit=5)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["medicine"].id, target.id)


class MedicineImportEnrichmentTests(APITestCase):
    def test_import_medicines_derives_search_fields_for_legacy_csv(self):
        csv_content = (
            "trade_name,active_ingredient,strength,dosage_form,drug_class,common_side_effects,serious_warning,"
            "similar_active_ingredients,similarity_risk_symptoms,switching_note,interaction_notes\n"
            "TestBrand,Alpha + Beta,10 mg,tablet,test class,,,,,,\n"
        )
        with tempfile.NamedTemporaryFile("w+", suffix=".csv", encoding="utf-8", delete=False) as handle:
            handle.write(csv_content)
            handle.flush()
            call_command("import_medicines", path=handle.name)

        med = Medicine.objects.get(trade_name="TestBrand")
        self.assertEqual(med.trade_name_norm, "testbrand")
        self.assertEqual(med.active_ingredient_norm, "alpha beta")
        self.assertEqual(med.drug_class_norm, "test class")
        self.assertIn("alpha", med.active_ingredient_tokens)
        self.assertIn("testbrand", med.search_aliases)

    def test_backfill_command_populates_missing_search_fields(self):
        med = make_medicine(
            trade_name="BackfillMed",
            active_ingredient="Gamma / Delta",
            drug_class="Sample Class",
            search_aliases="",
            trade_name_norm="",
            active_ingredient_norm="",
            drug_class_norm="",
            active_ingredient_tokens="",
        )
        call_command("backfill_medicine_search_fields")
        med.refresh_from_db()
        self.assertEqual(med.trade_name_norm, "backfillmed")
        self.assertEqual(med.active_ingredient_norm, "gamma delta")
        self.assertEqual(med.drug_class_norm, "sample class")
        self.assertIn("gamma", med.active_ingredient_tokens)


# ─────────────────────────────────────────────────────────────
# MEDICAL RECORD TESTS
# ─────────────────────────────────────────────────────────────

class MedicalRecordViewTests(APITestCase):
    URL = "/api/medical-record/"

    def setUp(self):
        self.user = make_user()
        self.other = make_user(username="other2", email="other2@example.com")

    def test_get_creates_record_automatically(self):
        resp = self.client.get(self.URL, **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(MedicalRecord.objects.filter(user=self.user).exists())

    def test_patch_updates_record(self):
        resp = self.client.patch(self.URL, {
            "blood_type": "O+",
            "gender": "M",
            "height_cm": "175.0",
            "weight_kg": "80.0",
            "phone_number": "+20100000000",
        }, format="json", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["blood_type"], "O+")
        self.assertEqual(resp.data["gender"], "M")

    def test_requires_auth(self):
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("api.medical_views.MedicalRecord.objects.get_or_create")
    def test_get_record_handles_integrity_error_race(self, get_or_create_mock):
        get_or_create_mock.side_effect = [IntegrityError("duplicate key value violates unique constraint")]
        MedicalRecord.objects.create(user=self.user)
        resp = self.client.get(self.URL, **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(MedicalRecord.objects.filter(user=self.user).count(), 1)


class MedicalSummaryTests(APITestCase):
    URL = "/api/medical-record/summary/"

    def setUp(self):
        self.user = make_user()
        self.record, _ = MedicalRecord.objects.get_or_create(user=self.user)

    def test_summary_contains_all_sections(self):
        resp = self.client.get(self.URL, **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ["diagnoses", "allergies", "vitals", "lab_results", "visits",
                      "latest_vitals", "active_diagnoses_count", "drug_allergies"]:
            self.assertIn(field, resp.data)

    def test_summary_counts_active_diagnoses(self):
        Diagnosis.objects.create(record=self.record, condition_name="Diabetes", status="chronic")
        Diagnosis.objects.create(record=self.record, condition_name="Cold", status="resolved")
        resp = self.client.get(self.URL, **auth_header(self.user))
        self.assertEqual(resp.data["active_diagnoses_count"], 1)

    def test_summary_lists_drug_allergies(self):
        Allergy.objects.create(record=self.record, allergen="Penicillin", allergen_type="drug", severity="severe")
        resp = self.client.get(self.URL, **auth_header(self.user))
        self.assertIn("Penicillin", resp.data["drug_allergies"])

    def test_latest_vitals_returned(self):
        VitalSign.objects.create(record=self.record, recorded_at="2025-01-01T08:00:00Z", heart_rate=72)
        resp = self.client.get(self.URL, **auth_header(self.user))
        self.assertIsNotNone(resp.data["latest_vitals"])
        self.assertEqual(resp.data["latest_vitals"]["heart_rate"], 72)


class DiagnosisTests(APITestCase):
    URL = "/api/medical-record/diagnoses/"

    def setUp(self):
        self.user = make_user()
        self.other = make_user(username="other3", email="other3@example.com")

    def test_create_diagnosis(self):
        resp = self.client.post(self.URL, {
            "condition_name": "Type 2 Diabetes",
            "status": "chronic",
            "diagnosed_date": "2020-03-15",
            "diagnosed_by": "Dr. Ahmed",
        }, format="json", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["condition_name"], "Type 2 Diabetes")

    def test_list_diagnoses_scoped_to_user(self):
        other_record, _ = MedicalRecord.objects.get_or_create(user=self.other)
        Diagnosis.objects.create(record=other_record, condition_name="OtherCondition")
        self.client.post(self.URL, {"condition_name": "MyCondition", "status": "active"},
                         format="json", **auth_header(self.user))
        resp = self.client.get(self.URL, **auth_header(self.user))
        names = [d["condition_name"] for d in resp.data["results"]]
        self.assertIn("MyCondition", names)
        self.assertNotIn("OtherCondition", names)

    def test_filter_by_status(self):
        record, _ = MedicalRecord.objects.get_or_create(user=self.user)
        Diagnosis.objects.create(record=record, condition_name="Active", status="active")
        Diagnosis.objects.create(record=record, condition_name="Resolved", status="resolved")
        resp = self.client.get(f"{self.URL}?status=active", **auth_header(self.user))
        names = [d["condition_name"] for d in resp.data["results"]]
        self.assertIn("Active", names)
        self.assertNotIn("Resolved", names)


class AllergyTests(APITestCase):
    URL = "/api/medical-record/allergies/"

    def setUp(self):
        self.user = make_user()

    def test_create_allergy(self):
        resp = self.client.post(self.URL, {
            "allergen": "Penicillin",
            "allergen_type": "drug",
            "reaction": "Anaphylaxis",
            "severity": "severe",
        }, format="json", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["severity"], "severe")

    def test_filter_by_type(self):
        record, _ = MedicalRecord.objects.get_or_create(user=self.user)
        Allergy.objects.create(record=record, allergen="Peanuts", allergen_type="food", severity="moderate")
        Allergy.objects.create(record=record, allergen="Aspirin", allergen_type="drug", severity="mild")
        resp = self.client.get(f"{self.URL}?type=food", **auth_header(self.user))
        names = [a["allergen"] for a in resp.data["results"]]
        self.assertIn("Peanuts", names)
        self.assertNotIn("Aspirin", names)


class VitalSignTests(APITestCase):
    URL = "/api/medical-record/vitals/"

    def setUp(self):
        self.user = make_user()

    def test_create_vitals(self):
        resp = self.client.post(self.URL, {
            "recorded_at": "2025-05-01T08:00:00Z",
            "blood_pressure_systolic": 120,
            "blood_pressure_diastolic": 80,
            "heart_rate": 72,
            "temperature_celsius": "36.6",
            "weight_kg": "75.0",
        }, format="json", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["blood_pressure"], "120/80 mmHg")

    def test_list_vitals(self):
        record, _ = MedicalRecord.objects.get_or_create(user=self.user)
        VitalSign.objects.create(record=record, recorded_at="2025-01-01T08:00:00Z", heart_rate=70)
        resp = self.client.get(self.URL, **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data["results"]), 1)


class LabResultTests(APITestCase):
    URL = "/api/medical-record/lab-results/"

    def setUp(self):
        self.user = make_user()

    def test_create_lab_result(self):
        resp = self.client.post(self.URL, {
            "test_name": "HbA1c",
            "result_value": "7.2",
            "unit": "%",
            "reference_range": "< 5.7",
            "is_abnormal": True,
            "recorded_at": "2025-04-01",
            "lab_name": "Cairo Lab",
        }, format="json", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data["is_abnormal"])

    def test_filter_abnormal(self):
        record, _ = MedicalRecord.objects.get_or_create(user=self.user)
        LabResult.objects.create(record=record, test_name="Normal Test", result_value="5.0",
                                  recorded_at="2025-01-01", is_abnormal=False)
        LabResult.objects.create(record=record, test_name="Abnormal Test", result_value="9.0",
                                  recorded_at="2025-01-01", is_abnormal=True)
        resp = self.client.get(f"{self.URL}?abnormal=true", **auth_header(self.user))
        names = [r["test_name"] for r in resp.data["results"]]
        self.assertIn("Abnormal Test", names)
        self.assertNotIn("Normal Test", names)


class DoctorVisitTests(APITestCase):
    URL = "/api/medical-record/visits/"

    def setUp(self):
        self.user = make_user()

    def test_create_visit(self):
        resp = self.client.post(self.URL, {
            "visit_date": "2025-04-20",
            "doctor_name": "Dr. Sara",
            "specialty": "Endocrinology",
            "reason": "Diabetes follow-up",
            "diagnosis_notes": "Good control",
            "prescription_notes": "Continue Metformin 500mg",
            "follow_up_date": "2025-07-20",
        }, format="json", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["doctor_name"], "Dr. Sara")

    def test_list_visits(self):
        record, _ = MedicalRecord.objects.get_or_create(user=self.user)
        DoctorVisit.objects.create(record=record, visit_date="2025-01-01", reason="Checkup")
        resp = self.client.get(self.URL, **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data["results"]), 1)


class RootRoutingTests(APITestCase):
    def test_root_redirects_to_api_docs(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, status.HTTP_302_FOUND)
        self.assertEqual(resp["Location"], "/api/docs/")

    def test_demo_page_loads(self):
        resp = self.client.get("/demo/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn(b"Clinical Demo Console", resp.content)

    def test_demo_health(self):
        resp = self.client.get("/demo/health/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["status"], "ok")


class ReminderMigrationTests(TransactionTestCase):
    migrate_from = ("api", "0003_medical_record")
    migrate_to = ("api", "0004_reminder_user_non_null")
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
            medicine_name="ValidReminder",
            dose="1 tablet",
            times=["08:00"],
            start_date="2026-01-01",
        )
        ReminderModel.objects.create(
            user_id=None,
            medicine_id=med.id,
            medicine_name="OrphanReminder",
            dose="1 tablet",
            times=["08:00"],
            start_date="2026-01-01",
        )

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        self.apps = executor.loader.project_state([self.migrate_to]).apps

    def test_orphan_reminders_are_deleted_before_non_null_constraint(self):
        ReminderModel = self.apps.get_model("api", "MedicationReminder")
        names = sorted(ReminderModel.objects.values_list("medicine_name", flat=True))
        self.assertEqual(names, ["ValidReminder"])
