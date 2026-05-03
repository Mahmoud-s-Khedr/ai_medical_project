from __future__ import annotations

import xml.etree.ElementTree as ET

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import DataAccessRequest, DeveloperApiKey, DeveloperApp, MedicineHistoryEntry

User = get_user_model()


def make_user(username="testuser", email="test@example.com", password="StrongPass123!", **kwargs):
    return User.objects.create_user(username=username, email=email, password=password, **kwargs)


def auth_header(user):
    refresh = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}


class ExternalIntegrationFlowTests(APITestCase):
    def setUp(self):
        self.developer = make_user(username="dev", email="dev@example.com")
        self.target_user = make_user(username="patient1", email="patient1@example.com")

        MedicineHistoryEntry.objects.create(user=self.target_user, medicine_name="Panadol", status="current", dose="500mg")
        MedicineHistoryEntry.objects.create(user=self.target_user, medicine_name="Brufen", status="past", dose="400mg")

    def _create_app_and_key(self):
        app_resp = self.client.post(
            "/api/integrations/apps/",
            {"name": "Partner System", "description": "Integration client"},
            format="json",
            **auth_header(self.developer),
        )
        self.assertEqual(app_resp.status_code, status.HTTP_201_CREATED)

        key_resp = self.client.post(
            "/api/integrations/keys/",
            {"app_id": app_resp.data["id"], "name": "primary"},
            format="json",
            **auth_header(self.developer),
        )
        self.assertEqual(key_resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("api_key", key_resp.data)
        return app_resp.data, key_resp.data["api_key"]

    def test_end_to_end_approval_and_fetch_json_xml(self):
        app_data, api_key = self._create_app_and_key()

        request_resp = self.client.post(
            "/api/external/access-requests/",
            {"username": self.target_user.username, "purpose": "Care coordination"},
            format="json",
            HTTP_X_API_KEY=api_key,
        )
        self.assertEqual(request_resp.status_code, status.HTTP_201_CREATED)
        request_id = request_resp.data["id"]

        inbox_resp = self.client.get("/api/integrations/access-requests/inbox/", **auth_header(self.target_user))
        self.assertEqual(inbox_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(inbox_resp.data), 1)

        approve_resp = self.client.post(
            f"/api/integrations/access-requests/{request_id}/approve/",
            {"decision_note": "Approved"},
            format="json",
            **auth_header(self.target_user),
        )
        self.assertEqual(approve_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(approve_resp.data["status"], "approved")

        json_fetch = self.client.get(f"/api/external/medicine-history/{self.target_user.username}/", HTTP_X_API_KEY=api_key)
        self.assertEqual(json_fetch.status_code, status.HTTP_200_OK)
        self.assertEqual(json_fetch.data["count"], 2)

        xml_fetch = self.client.get(
            f"/api/external/medicine-history/{self.target_user.username}/?format=xml",
            HTTP_X_API_KEY=api_key,
        )
        self.assertEqual(xml_fetch.status_code, status.HTTP_200_OK)
        self.assertIn("application/xml", xml_fetch["Content-Type"])

        xml_root = ET.fromstring(xml_fetch.content)
        xml_names = [node.text for node in xml_root.findall("./results/entry/medicine_name")]
        json_names = [row["medicine_name"] for row in json_fetch.data["results"]]
        self.assertEqual(sorted(xml_names), sorted(json_names))

        revoke_resp = self.client.post(
            f"/api/integrations/access-requests/{request_id}/revoke/",
            {"decision_note": "Revoked"},
            format="json",
            **auth_header(self.target_user),
        )
        self.assertEqual(revoke_resp.status_code, status.HTTP_200_OK)

        denied_fetch = self.client.get(f"/api/external/medicine-history/{self.target_user.username}/", HTTP_X_API_KEY=api_key)
        self.assertEqual(denied_fetch.status_code, status.HTTP_403_FORBIDDEN)

        self.assertEqual(app_data["name"], "Partner System")

    def test_rejection_invalid_key_unknown_username_duplicate_request_and_key_revocation(self):
        app_data, api_key = self._create_app_and_key()

        unknown_user = self.client.post(
            "/api/external/access-requests/",
            {"username": "missing-user", "purpose": "Test"},
            format="json",
            HTTP_X_API_KEY=api_key,
        )
        self.assertEqual(unknown_user.status_code, status.HTTP_400_BAD_REQUEST)

        first_req = self.client.post(
            "/api/external/access-requests/",
            {"username": self.target_user.username, "purpose": "Access history"},
            format="json",
            HTTP_X_API_KEY=api_key,
        )
        self.assertEqual(first_req.status_code, status.HTTP_201_CREATED)

        dup_req = self.client.post(
            "/api/external/access-requests/",
            {"username": self.target_user.username, "purpose": "Access history"},
            format="json",
            HTTP_X_API_KEY=api_key,
        )
        self.assertEqual(dup_req.status_code, status.HTTP_409_CONFLICT)

        reject_resp = self.client.post(
            f"/api/integrations/access-requests/{first_req.data['id']}/reject/",
            {"decision_note": "Rejected"},
            format="json",
            **auth_header(self.target_user),
        )
        self.assertEqual(reject_resp.status_code, status.HTTP_200_OK)

        denied = self.client.get(f"/api/external/medicine-history/{self.target_user.username}/", HTTP_X_API_KEY=api_key)
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        invalid_key_resp = self.client.get(
            f"/api/external/medicine-history/{self.target_user.username}/",
            HTTP_X_API_KEY="invalid_key",
        )
        self.assertEqual(invalid_key_resp.status_code, status.HTTP_401_UNAUTHORIZED)

        keys_list = self.client.get("/api/integrations/keys/", **auth_header(self.developer))
        self.assertEqual(keys_list.status_code, status.HTTP_200_OK)
        key_id = keys_list.data["results"][0]["id"]

        revoke_key = self.client.post(f"/api/integrations/keys/{key_id}/revoke/", **auth_header(self.developer))
        self.assertEqual(revoke_key.status_code, status.HTTP_200_OK)

        revoked_key_request = self.client.post(
            "/api/external/access-requests/",
            {"username": self.target_user.username},
            format="json",
            HTTP_X_API_KEY=api_key,
        )
        self.assertEqual(revoked_key_request.status_code, status.HTTP_401_UNAUTHORIZED)

        self.assertEqual(DeveloperApp.objects.filter(id=app_data["id"]).count(), 1)
        self.assertTrue(DeveloperApiKey.objects.filter(id=key_id, revoked_at__isnull=False).exists())


class MedicineHistoryExportXmlTests(APITestCase):
    def setUp(self):
        self.user = make_user(username="xmluser", email="xml@example.com")
        MedicineHistoryEntry.objects.create(user=self.user, medicine_name="TestMed", status="current")

    def test_export_xml_download(self):
        resp = self.client.get("/api/integrations/medicine-history/export.xml", **auth_header(self.user))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("application/xml", resp["Content-Type"])
        self.assertIn("attachment; filename=\"medicine_history.xml\"", resp["Content-Disposition"])

        root = ET.fromstring(resp.content)
        names = [n.text for n in root.findall("./entries/entry/medicine_name")]
        self.assertIn("TestMed", names)


class RegressionJwtMedicineHistoryTests(APITestCase):
    def setUp(self):
        self.user = make_user(username="reguser", email="reg@example.com")

    def test_existing_medicine_history_jwt_flow_still_works(self):
        create_resp = self.client.post(
            "/api/medicine-history/",
            {"medicine_name": "RegressionMed", "status": "current"},
            format="json",
            **auth_header(self.user),
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)

        list_resp = self.client.get("/api/medicine-history/", **auth_header(self.user))
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(list_resp.data["count"], 1)


class ExternalVisibilityIsolationTests(APITestCase):
    def setUp(self):
        self.developer = make_user(username="dev2", email="dev2@example.com")
        self.other_developer = make_user(username="dev3", email="dev3@example.com")
        self.target = make_user(username="patient2", email="patient2@example.com")
        MedicineHistoryEntry.objects.create(user=self.target, medicine_name="IsoMed", status="current")

    def _issue_key_for(self, user, app_name):
        app = DeveloperApp.objects.create(owner=user, name=app_name)
        key_resp = self.client.post(
            "/api/integrations/keys/",
            {"app_id": app.id, "name": "primary"},
            format="json",
            **auth_header(user),
        )
        return app, key_resp.data["api_key"]

    def test_no_cross_app_visibility_without_own_approval(self):
        app1, key1 = self._issue_key_for(self.developer, "App1")
        app2, key2 = self._issue_key_for(self.other_developer, "App2")

        req1 = self.client.post(
            "/api/external/access-requests/",
            {"username": self.target.username},
            format="json",
            HTTP_X_API_KEY=key1,
        )
        self.assertEqual(req1.status_code, status.HTTP_201_CREATED)

        self.client.post(
            f"/api/integrations/access-requests/{req1.data['id']}/approve/",
            format="json",
            **auth_header(self.target),
        )

        allowed = self.client.get(f"/api/external/medicine-history/{self.target.username}/", HTTP_X_API_KEY=key1)
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)

        denied = self.client.get(f"/api/external/medicine-history/{self.target.username}/", HTTP_X_API_KEY=key2)
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self.assertTrue(DataAccessRequest.objects.filter(app=app1, target_user=self.target, status="approved").exists())
        self.assertFalse(DataAccessRequest.objects.filter(app=app2, target_user=self.target, status="approved").exists())
