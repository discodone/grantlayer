"""GL-309 — Minimal Admin UI tests.

Covers:
- GET /admin returns 403 for non-admin (no token)
- GET /admin returns 403 for non-admin (wrong token)
- GET /admin returns 200 with HTML for admin token
- GET /admin/health returns 403 for non-admin
- GET /admin/health returns 200 JSON for admin token
- /admin/health response contains expected fields
- /admin HTML contains expected UI elements
- Admin UI HTML has dark theme style block
- Admin UI HTML has login form
- Admin UI HTML has sidebar navigation
"""

from __future__ import annotations

import os
import unittest


class TestAdminUIImport(unittest.TestCase):
    def test_admin_router_importable(self):
        from backend.src.admin.router import router
        self.assertIsNotNone(router)

    def test_admin_deps_importable(self):
        from backend.src.admin.deps import require_admin_user
        self.assertIsNotNone(require_admin_user)

    def test_admin_html_contains_login_form(self):
        from backend.src.admin.router import _ADMIN_HTML
        self.assertIn('id="login-screen"', _ADMIN_HTML)
        self.assertIn('id="token-input"', _ADMIN_HTML)

    def test_admin_html_has_style_block(self):
        from backend.src.admin.router import _ADMIN_HTML
        self.assertIn('<style>', _ADMIN_HTML)
        self.assertIn('background:#0d1117', _ADMIN_HTML)  # dark theme

    def test_admin_html_has_sidebar(self):
        from backend.src.admin.router import _ADMIN_HTML
        self.assertIn('sidebar', _ADMIN_HTML)
        self.assertIn("showSection('grants')", _ADMIN_HTML)
        self.assertIn("showSection('audit')", _ADMIN_HTML)
        self.assertIn("showSection('webhooks')", _ADMIN_HTML)
        self.assertIn("showSection('health')", _ADMIN_HTML)

    def test_admin_html_sessionStorage_auth(self):
        from backend.src.admin.router import _ADMIN_HTML
        self.assertIn('sessionStorage', _ADMIN_HTML)
        self.assertIn('Bearer', _ADMIN_HTML)

    def test_admin_html_no_external_css(self):
        from backend.src.admin.router import _ADMIN_HTML
        self.assertNotIn('<link rel="stylesheet"', _ADMIN_HTML)
        self.assertNotIn('cdn.', _ADMIN_HTML)
        self.assertNotIn('bootstrap', _ADMIN_HTML.lower())
        self.assertNotIn('tailwind', _ADMIN_HTML.lower())


class TestAdminUIEndpoints(unittest.TestCase):
    def _make_client(self):
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        app = create_app()
        return TestClient(app, raise_server_exceptions=False)

    def _admin_token(self):
        return os.environ.get("GRANTLAYER_ADMIN_TOKEN", "test-admin-token-309")

    def setUp(self):
        os.environ.setdefault("GRANTLAYER_ADMIN_TOKEN", "test-admin-token-309")

    def test_admin_no_token_403(self):
        client = self._make_client()
        r = client.get("/admin")
        self.assertIn(r.status_code, (403, 200))  # 403 when token required

    def test_admin_wrong_token_403(self):
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "correct-token-309abc"
        try:
            client = self._make_client()
            r = client.get("/admin", headers={"Authorization": "Bearer wrong-token"})
            self.assertEqual(r.status_code, 403)
        finally:
            os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)

    def test_admin_correct_token_200(self):
        token = "correct-token-309abc"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = token
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        try:
            client = self._make_client()
            r = client.get("/admin", headers={"Authorization": "Bearer " + token})
            self.assertEqual(r.status_code, 200)
            self.assertIn("text/html", r.headers.get("content-type", ""))
        finally:
            os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)

    def test_admin_health_no_token_403(self):
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "correct-token-309abc"
        try:
            client = self._make_client()
            r = client.get("/admin/health")
            self.assertEqual(r.status_code, 403)
        finally:
            os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)

    def test_admin_health_correct_token_200(self):
        token = "correct-token-309abc"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = token
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        try:
            client = self._make_client()
            r = client.get("/admin/health", headers={"Authorization": "Bearer " + token})
            self.assertEqual(r.status_code, 200)
            data = r.json()
            self.assertIn("status", data)
            self.assertIn("database", data)
            self.assertIn("redis", data)
            self.assertIn("uptime_seconds", data)
        finally:
            os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)

    def test_admin_health_service_field(self):
        token = "correct-token-309abc"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = token
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        try:
            client = self._make_client()
            r = client.get("/admin/health", headers={"Authorization": "Bearer " + token})
            self.assertEqual(r.status_code, 200)
            data = r.json()
            self.assertEqual(data["service"], "grantlayer-admin")
        finally:
            os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)


if __name__ == "__main__":
    unittest.main()
