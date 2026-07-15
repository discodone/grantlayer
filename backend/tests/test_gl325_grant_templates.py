"""GL-325 — Multi-Workspace Grant Templates.

Covers:
- GrantTemplate ORM model exists with required columns
- grant_templates router importable
- GET /v1/grant-templates requires auth
- POST /v1/grant-templates creates template
- GET /v1/grant-templates/{id} returns template
- GET /v1/grant-templates/public returns public templates (no auth)
- POST /v1/grant-templates/{id}/deactivate deactivates template
- POST /v1/grant-templates/{id}/new-version creates versioned template
- Version increments on new-version
- parent_id set on new-version
- Template has schema_json and default_values
- Migration 0018 exists
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

_TEST_SECRET = "gl325-test-hs256-secret-32chars!!"


def _make_client():
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def _jwt() -> str:
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
    os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)
    from backend.src.api.auth_jwt import encode_token
    return encode_token(
        {"sub": "tmpl-user", "role": "grant_admin", "tenant_id": "t1", "workspace_id": "ws-1",
         "iss": "grantlayer", "aud": "grantlayer-api"},
        _TEST_SECRET,
    )


class TestGrantTemplateOrm(unittest.TestCase):
    def test_grant_template_model_importable(self):
        from backend.src.core.orm import GrantTemplate
        self.assertIsNotNone(GrantTemplate)

    def test_grant_template_has_required_columns(self):
        from backend.src.core.orm import GrantTemplate
        for col in ("id", "workspace_id", "name", "description", "schema_json",
                    "default_values", "version", "parent_id", "is_active", "locked",
                    "created_at", "created_by"):
            self.assertTrue(hasattr(GrantTemplate, col), f"Missing: {col}")


class TestGrantTemplateMigration(unittest.TestCase):
    def test_migration_0018_exists(self):
        migration_dir = Path(__file__).parent.parent / "src" / "migrations"
        files = list(migration_dir.glob("0018_gl325_*.py"))
        self.assertTrue(len(files) >= 1, "Migration 0018 not found")


class TestGrantTemplatesRouter(unittest.TestCase):
    def test_router_importable(self):
        from backend.src.api.routers.grant_templates import router
        self.assertIsNotNone(router)

    def test_router_prefix(self):
        from backend.src.api.routers.grant_templates import router
        self.assertEqual(router.prefix, "/grant-templates")


class TestGrantTemplateCrud(unittest.TestCase):
    def setUp(self):
        # Enter the TestClient context so all requests in this test share one
        # event loop (asyncpg engine is loop-bound; TestClient spins a fresh
        # loop per request otherwise). Test-harness only — production uses a
        # single uvicorn loop.
        self.client = self.enterContext(_make_client())
        self.auth = {"Authorization": f"Bearer {_jwt()}"}

    def test_list_requires_auth(self):
        resp = self.client.get("/v1/grant-templates")
        self.assertEqual(resp.status_code, 401)

    def test_create_template(self):
        resp = self.client.post(
            "/v1/grant-templates",
            json={
                "name": "Standard Grant",
                "description": "Default grant template",
                "template_schema": {"type": "object"},
                "default_values": {"role": "viewer"},
            },
            headers=self.auth,
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        data = resp.json()
        self.assertIn("id", data)
        self.assertEqual(data["name"], "Standard Grant")
        self.assertEqual(data["version"], 1)
        self.assertIsNone(data["parent_id"])

    def test_create_requires_auth(self):
        resp = self.client.post(
            "/v1/grant-templates",
            json={"name": "Test"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_get_template(self):
        create_resp = self.client.post(
            "/v1/grant-templates",
            json={"name": "Gettable Template"},
            headers=self.auth,
        )
        self.assertEqual(create_resp.status_code, 201)
        tmpl_id = create_resp.json()["id"]

        get_resp = self.client.get(f"/v1/grant-templates/{tmpl_id}", headers=self.auth)
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["id"], tmpl_id)

    def test_get_nonexistent_template_404(self):
        resp = self.client.get("/v1/grant-templates/does-not-exist", headers=self.auth)
        self.assertEqual(resp.status_code, 404)

    def test_list_templates(self):
        self.client.post(
            "/v1/grant-templates",
            json={"name": "Listed Template"},
            headers=self.auth,
        )
        resp = self.client.get("/v1/grant-templates", headers=self.auth)
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_deactivate_template(self):
        create_resp = self.client.post(
            "/v1/grant-templates",
            json={"name": "Deactivatable"},
            headers=self.auth,
        )
        self.assertEqual(create_resp.status_code, 201)
        tmpl_id = create_resp.json()["id"]

        deact_resp = self.client.post(
            f"/v1/grant-templates/{tmpl_id}/deactivate",
            headers=self.auth,
        )
        self.assertEqual(deact_resp.status_code, 200)
        self.assertFalse(deact_resp.json()["is_active"])

    def test_new_version_increments_version(self):
        create_resp = self.client.post(
            "/v1/grant-templates",
            json={"name": "Versionable"},
            headers=self.auth,
        )
        self.assertEqual(create_resp.status_code, 201)
        tmpl_id = create_resp.json()["id"]

        v2_resp = self.client.post(
            f"/v1/grant-templates/{tmpl_id}/new-version",
            json={"name": "Versionable v2"},
            headers=self.auth,
        )
        self.assertEqual(v2_resp.status_code, 201)
        v2 = v2_resp.json()
        self.assertEqual(v2["version"], 2)
        self.assertEqual(v2["parent_id"], tmpl_id)

    def test_public_templates_no_auth(self):
        resp = self.client.get("/v1/grant-templates/public")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_template_has_default_values(self):
        resp = self.client.post(
            "/v1/grant-templates",
            json={
                "name": "Defaults Template",
                "default_values": {"role": "viewer", "action": "read"},
            },
            headers=self.auth,
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["default_values"]["role"], "viewer")
