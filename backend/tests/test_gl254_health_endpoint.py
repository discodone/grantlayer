"""Tests for GL-254: extended /health endpoint.

Covers:
- /health returns 200 with all required fields
- database field is "ok" when DB is reachable
- signing_key is "present" when GRANTLAYER_JWT_SECRET is set
- signing_key is "absent" when JWT secret is not set
- version field is present and non-empty
- uptime_seconds field is a non-negative integer
- migrations field is present and a string
- status is "ok" under normal conditions
- status is "degraded" when DB is unreachable
- no secrets are exposed in the response
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_client(tmp_db_path: str, jwt_secret: str | None = None):
    """Create a fresh TestClient with an isolated DB and optional JWT secret."""
    os.environ["GRANTLAYER_DB"] = tmp_db_path
    if jwt_secret is not None:
        os.environ["GRANTLAYER_JWT_SECRET"] = jwt_secret
    else:
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)

    import backend.src.core.db as db_mod
    importlib.reload(db_mod)
    db_mod.DB_PATH_OR_URL = tmp_db_path
    db_mod.DB_PATH = tmp_db_path
    db_mod.init_db()

    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


class TestGL254HealthEndpoint(unittest.TestCase):
    """GL-254: Extended /health endpoint tests."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        self._orig_jwt = os.environ.get("GRANTLAYER_JWT_SECRET")
        self.client = _make_client(self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)
        if self._orig_jwt is not None:
            os.environ["GRANTLAYER_JWT_SECRET"] = self._orig_jwt
        else:
            os.environ.pop("GRANTLAYER_JWT_SECRET", None)

    def _get_health(self):
        resp = self.client.get("/health")
        return resp.status_code, resp.json()

    # ── basic contract ──────────────────────────────────────────────────────

    def test_health_returns_200(self):
        status, _ = self._get_health()
        self.assertEqual(status, 200)

    def test_health_status_ok(self):
        _, body = self._get_health()
        self.assertEqual(body.get("status"), "ok")

    def test_health_has_version(self):
        _, body = self._get_health()
        self.assertIn("version", body)
        self.assertIsInstance(body["version"], str)
        self.assertTrue(body["version"])

    def test_health_has_uptime_seconds(self):
        _, body = self._get_health()
        self.assertIn("uptime_seconds", body)
        self.assertIsInstance(body["uptime_seconds"], int)
        self.assertGreaterEqual(body["uptime_seconds"], 0)

    def test_health_has_database_field(self):
        _, body = self._get_health()
        self.assertIn("database", body)

    def test_health_database_ok(self):
        _, body = self._get_health()
        self.assertEqual(body.get("database"), "ok")

    def test_health_has_signing_key_field(self):
        _, body = self._get_health()
        self.assertIn("signing_key", body)

    def test_health_has_migrations_field(self):
        _, body = self._get_health()
        self.assertIn("migrations", body)
        self.assertIsInstance(body["migrations"], str)

    # ── backward compat: existing fields still present ──────────────────────

    def test_health_still_has_service(self):
        _, body = self._get_health()
        self.assertEqual(body.get("service"), "grantlayer")

    def test_health_still_has_check_type(self):
        _, body = self._get_health()
        self.assertEqual(body.get("checkType"), "liveness")

    # ── signing key present / absent ────────────────────────────────────────

    def test_signing_key_absent_when_no_jwt_secret(self):
        client = _make_client(self.tmp.name, jwt_secret=None)
        _, body = client.get("/health"), None
        resp = client.get("/health")
        body = resp.json()
        self.assertEqual(body.get("signing_key"), "absent")

    def test_signing_key_present_when_jwt_secret_set(self):
        client = _make_client(self.tmp.name, jwt_secret="test-secret-32chars-abcdefghijkl")
        resp = client.get("/health")
        body = resp.json()
        self.assertEqual(body.get("signing_key"), "present")

    def test_signing_key_value_not_exposed(self):
        secret = "super-secret-jwt-key-xyz-12345678"
        client = _make_client(self.tmp.name, jwt_secret=secret)
        resp = client.get("/health")
        self.assertNotIn(secret, resp.text)

    # ── degraded status when DB unreachable ─────────────────────────────────

    def test_health_degraded_when_db_missing(self):
        # Point DB at path whose parent dir doesn't exist — SQLite will fail to open
        import backend.src.core.db as db_mod
        orig_path = db_mod.DB_PATH_OR_URL
        orig_backend = db_mod.DB_BACKEND
        bad_path = "/tmp/gl254_no_such_parent_dir_xyz/missing.db"
        db_mod.DB_PATH_OR_URL = bad_path
        db_mod.DB_BACKEND = "sqlite"
        try:
            from fastapi.testclient import TestClient
            from backend.src.api.app import create_app
            client = TestClient(create_app(), raise_server_exceptions=False)
            resp = client.get("/health")
            body = resp.json()
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(body.get("status"), "degraded")
            self.assertTrue(body.get("database", "").startswith("error:"))
        finally:
            db_mod.DB_PATH_OR_URL = orig_path
            db_mod.DB_BACKEND = orig_backend
