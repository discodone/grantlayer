"""GL-319 — GDPR Compliance Tooling.

Covers:
- gdpr router importable
- POST /v1/users/{id}/export-data returns 202 with job_id
- POST /v1/users/{id}/erase returns 202 with job_id
- Non-admin cannot erase other users (403)
- Self-erasure allowed (same sub)
- Admin can erase any user
- Erasure response includes anonymized fields
- Erasure revokes API keys
- Export requires auth
- Erase requires auth
- gdpr_erasure_completed audit action in response
"""

from __future__ import annotations

import os
import unittest


_TEST_SECRET = "gl319-test-hs256-secret-32chars!!"


def _make_client():
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def _jwt(sub: str, role: str = "viewer") -> str:
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
    os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)
    from backend.src.api.auth_jwt import encode_token
    return encode_token(
        {"sub": sub, "role": role, "tenant_id": "t1",
         "iss": "grantlayer", "aud": "grantlayer-api"},
        _TEST_SECRET,
    )


class TestGdprRouterImport(unittest.TestCase):
    def test_gdpr_router_importable(self):
        from backend.src.api.routers.gdpr import router
        self.assertIsNotNone(router)

    def test_gdpr_router_prefix(self):
        from backend.src.api.routers.gdpr import router
        self.assertEqual(router.prefix, "/users")


class TestGdprExportData(unittest.TestCase):
    def setUp(self):
        self.client = _make_client()

    def test_export_data_requires_auth(self):
        resp = self.client.post("/v1/users/user-123/export-data")
        self.assertEqual(resp.status_code, 401)

    def test_export_data_self_allowed(self):
        resp = self.client.post(
            "/v1/users/self-user/export-data",
            headers={"Authorization": f"Bearer {_jwt('self-user', 'viewer')}"},
        )
        self.assertEqual(resp.status_code, 202)
        data = resp.json()
        self.assertIn("job_id", data)
        self.assertEqual(data["user_id"], "self-user")
        self.assertEqual(data["status"], "queued")

    def test_export_data_admin_can_export_any(self):
        resp = self.client.post(
            "/v1/users/other-user/export-data",
            headers={"Authorization": f"Bearer {_jwt('admin-user', 'grant_admin')}"},
        )
        self.assertEqual(resp.status_code, 202)

    def test_export_data_non_admin_cannot_export_other(self):
        resp = self.client.post(
            "/v1/users/someone-else/export-data",
            headers={"Authorization": f"Bearer {_jwt('user-a', 'viewer')}"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_export_data_returns_data_field(self):
        resp = self.client.post(
            "/v1/users/export-test-user/export-data",
            headers={"Authorization": f"Bearer {_jwt('export-test-user', 'viewer')}"},
        )
        self.assertEqual(resp.status_code, 202)
        self.assertIn("data", resp.json())


class TestGdprErase(unittest.TestCase):
    def setUp(self):
        self.client = _make_client()

    def test_erase_requires_auth(self):
        resp = self.client.post("/v1/users/user-123/erase")
        self.assertEqual(resp.status_code, 401)

    def test_erase_self_allowed(self):
        resp = self.client.post(
            "/v1/users/erase-self/erase",
            headers={"Authorization": f"Bearer {_jwt('erase-self', 'viewer')}"},
        )
        self.assertEqual(resp.status_code, 202)
        data = resp.json()
        self.assertIn("job_id", data)
        self.assertEqual(data["user_id"], "erase-self")

    def test_erase_admin_can_erase_any(self):
        resp = self.client.post(
            "/v1/users/target-user/erase",
            headers={"Authorization": f"Bearer {_jwt('admin-user', 'owner')}"},
        )
        self.assertEqual(resp.status_code, 202)

    def test_erase_non_admin_cannot_erase_other(self):
        resp = self.client.post(
            "/v1/users/other-target/erase",
            headers={"Authorization": f"Bearer {_jwt('user-b', 'viewer')}"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_erase_response_has_anonymized_fields(self):
        resp = self.client.post(
            "/v1/users/anon-user/erase",
            headers={"Authorization": f"Bearer {_jwt('anon-user', 'viewer')}"},
        )
        self.assertEqual(resp.status_code, 202)
        data = resp.json()
        self.assertIn("anonymized_name", data)
        self.assertIn("anonymized_email", data)
        self.assertTrue(data["anonymized_name"].startswith("DELETED_"))
        self.assertTrue(data["anonymized_email"].endswith("@gdpr.invalid"))

    def test_erase_api_keys_revoked(self):
        resp = self.client.post(
            "/v1/users/key-user/erase",
            headers={"Authorization": f"Bearer {_jwt('key-user', 'viewer')}"},
        )
        self.assertEqual(resp.status_code, 202)
        self.assertTrue(resp.json()["api_keys_revoked"])

    def test_erase_status_completed(self):
        resp = self.client.post(
            "/v1/users/status-user/erase",
            headers={"Authorization": f"Bearer {_jwt('status-user', 'viewer')}"},
        )
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.json()["status"], "completed")
