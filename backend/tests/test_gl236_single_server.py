"""GL-236: Single-server unification — validation tests.

Verifies:
- __main__.py starts uvicorn (not legacy server.py)
- Root Dockerfile CMD uses uvicorn, not python3 -m backend
- Root Dockerfile installs requirements.txt (full deps, not just cryptography)
- README "Running locally without Docker" references FastAPI/uvicorn
- /auth/token is reachable via FastAPI test client
- POST /grants works end-to-end
- GET /audit-events returns audit records after grant creation
"""

from __future__ import annotations

import os
import pathlib
import re
import unittest

try:
    from fastapi.testclient import TestClient
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

_SKIP = unittest.skipUnless(
    _FASTAPI_AVAILABLE,
    "FastAPI not installed",
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

if _FASTAPI_AVAILABLE:
    import tempfile
    import backend.src.core.config as _cfg
    import backend.src.core.db as _db
    from backend.src.api.app import create_app

_JWT_SECRET = "gl236-test-secret-xxxxxxxxxxxxxxxx"
_ADMIN_TOKEN = "gl236-admin-token-test"


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


# ── Static source checks ───────────────────────────────────────────────────

class TestMainPyUsesUvicorn(unittest.TestCase):
    """__main__.py must drive uvicorn, not legacy server.py."""

    def setUp(self):
        self.src = _read("backend/__main__.py")

    def test_imports_uvicorn(self):
        self.assertIn("import uvicorn", self.src,
                      "__main__.py must import uvicorn")

    def test_calls_uvicorn_run(self):
        self.assertIn("uvicorn.run(", self.src,
                      "__main__.py must call uvicorn.run()")

    def test_does_not_import_legacy_server(self):
        self.assertNotIn("from backend.src.server import", self.src,
                         "__main__.py must not import legacy server.py")

    def test_targets_fastapi_app(self):
        self.assertIn("backend.src.api.app", self.src,
                      "__main__.py must reference the FastAPI app module")


class TestRootDockerfileUsesUvicorn(unittest.TestCase):
    """Root Dockerfile CMD must use uvicorn."""

    def setUp(self):
        self.src = _read("Dockerfile")

    def test_cmd_uses_uvicorn(self):
        self.assertIn("uvicorn", self.src,
                      "Root Dockerfile CMD must use uvicorn")

    def test_cmd_does_not_use_legacy_main(self):
        # CMD should not be `python3 -m backend` (which was the legacy entry)
        # Look for CMD lines only
        cmd_lines = [l for l in self.src.splitlines() if l.strip().startswith("CMD")]
        for line in cmd_lines:
            self.assertNotIn('"-m", "backend"', line,
                             "Root Dockerfile CMD must not use python3 -m backend (legacy)")

    def test_installs_requirements_txt(self):
        self.assertIn("requirements.txt", self.src,
                      "Root Dockerfile must install requirements.txt (full deps)")

    def test_does_not_install_only_cryptography(self):
        # Old Dockerfile only installed cryptography==43.0.0 — that was insufficient
        lines = self.src.splitlines()
        cryptography_only_pip = any(
            "pip install" in l and "cryptography" in l and "requirements.txt" not in l
            for l in lines
        )
        self.assertFalse(cryptography_only_pip,
                         "Root Dockerfile must not install only cryptography; use requirements.txt")

    def test_pythonpath_set(self):
        self.assertIn("PYTHONPATH", self.src,
                      "Root Dockerfile must set PYTHONPATH=/app")


class TestReadmeLocalRunSection(unittest.TestCase):
    """README must describe the FastAPI/uvicorn local run path."""

    def setUp(self):
        self.src = _read("README.md")

    def test_local_section_present(self):
        self.assertIn("Running locally without Docker", self.src)

    def test_uvicorn_mentioned(self):
        self.assertIn("uvicorn", self.src,
                      "README must mention uvicorn in local run instructions")

    def test_python_m_backend_still_present(self):
        # python3 -m backend is kept as the primary shorthand (now uvicorn-backed)
        self.assertIn("python3 -m backend", self.src,
                      "README must still document python3 -m backend shorthand")

    def test_no_server_py_reference_in_local_section(self):
        # Locate the local-run section and check it doesn't point to server.py
        local_start = self.src.find("## Running locally without Docker")
        next_section = self.src.find("\n## ", local_start + 1)
        section = self.src[local_start:next_section]
        self.assertNotIn("server.py", section,
                         "Local run section must not reference legacy server.py")


# ── Functional tests via FastAPI TestClient ───────────────────────────────

class _GL236TestBase(unittest.TestCase):
    """Shared setup: isolated temp DB + JWT + admin token."""

    def setUp(self):
        import importlib, sys as _sys
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "test"
        os.environ["GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"] = "true"
        for _mod_name in list(_sys.modules.keys()):
            if "backend.src.core.config" in _mod_name or "backend.src.core.crypto" in _mod_name:
                importlib.reload(_sys.modules[_mod_name])

        self._orig_db_path = _db.DB_PATH_OR_URL
        self._orig_enable_operator = _cfg.ENABLE_OPERATOR_MODEL
        self._orig_allow_plaintext = _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE

        os.environ["GRANTLAYER_JWT_SECRET"] = _JWT_SECRET
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = _ADMIN_TOKEN
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"

        _cfg.ENABLE_OPERATOR_MODEL = False
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = True

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_file = tmp.name
        _db.DB_PATH_OR_URL = self._db_file
        _db.DB_PATH = self._db_file
        _db.init_db()

        self.client = TestClient(create_app(), raise_server_exceptions=True)

    def tearDown(self):
        _db.DB_PATH_OR_URL = self._orig_db_path
        _db.DB_PATH = self._orig_db_path
        _cfg.ENABLE_OPERATOR_MODEL = self._orig_enable_operator
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_allow_plaintext
        for key in ("GRANTLAYER_JWT_SECRET", "GRANTLAYER_ADMIN_TOKEN",
                    "GRANTLAYER_REQUIRE_ADMIN_TOKEN", "GRANTLAYER_ENABLE_OPERATOR_MODEL",
                    "GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE",
                    "GRANTLAYER_RUNTIME_MODE"):
            os.environ.pop(key, None)
        try:
            os.unlink(self._db_file)
        except OSError:
            pass


@_SKIP
class TestAuthTokenEndpoint(_GL236TestBase):
    """/auth/token must work when JWT is configured — same as Docker environment."""

    def test_auth_token_returns_200(self):
        resp = self.client.post(
            "/auth/token", json={"operator_id": "gl236-agent", "secret": _ADMIN_TOKEN}
        )
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_auth_token_returns_access_token_field(self):
        resp = self.client.post(
            "/auth/token", json={"operator_id": "gl236-agent", "secret": _ADMIN_TOKEN}
        )
        data = resp.json()
        self.assertIn("access_token", data, "Response must have 'access_token' field")
        self.assertTrue(data["access_token"], "access_token must be non-empty")

    def test_auth_token_501_when_no_secret(self):
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        resp = self.client.post(
            "/auth/token", json={"operator_id": "gl236-agent", "secret": _ADMIN_TOKEN}
        )
        self.assertEqual(resp.status_code, 501, resp.text)


@_SKIP
class TestGrantsEndpoint(_GL236TestBase):
    """POST /grants must work via FastAPI — parity with Docker run."""

    def _get_jwt(self, operator_id: str = "gl236-agent") -> str:
        resp = self.client.post(
            "/auth/token", json={"operator_id": operator_id, "secret": _ADMIN_TOKEN}
        )
        return resp.json()["access_token"]

    def test_post_grant_returns_201(self):
        token = self._get_jwt()
        resp = self.client.post(
            "/grants",
            json={
                "subjectId": "agent-gl236",
                "role": "viewer",
                "action": "read",
                "resource": "reports",
                "validFrom": "2025-01-01T00:00:00Z",
                "validUntil": "2025-12-31T23:59:59Z",
                "createdBy": "gl236-operator",
                "reason": "gl236 single-server test",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(resp.status_code, 201, resp.text)

    def test_post_grant_has_id_field(self):
        token = self._get_jwt()
        resp = self.client.post(
            "/grants",
            json={
                "subjectId": "agent-gl236b",
                "role": "viewer",
                "action": "read",
                "resource": "files",
                "validFrom": "2025-01-01T00:00:00Z",
                "validUntil": "2025-12-31T23:59:59Z",
                "createdBy": "gl236-operator",
                "reason": "gl236 id check",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertIn("id", resp.json(), "Grant response must include 'id'")


@_SKIP
class TestAuditEventsAfterGrant(_GL236TestBase):
    """GET /audit-events must return events created by POST /grants."""

    def test_audit_event_created_after_grant(self):
        token = self.client.post(
            "/auth/token", json={"operator_id": "gl236-auditor", "secret": _ADMIN_TOKEN}
        ).json()["access_token"]
        self.client.post(
            "/grants",
            json={
                "subjectId": "agent-audit",
                "role": "viewer",
                "action": "write",
                "resource": "reports",
                "validFrom": "2025-01-01T00:00:00Z",
                "validUntil": "2025-12-31T23:59:59Z",
                "createdBy": "gl236-operator",
                "reason": "audit trail test",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = self.client.get(
            "/audit-events",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        events = resp.json()
        self.assertTrue(events, "Expected at least one audit event after grant creation")
        reasons = [e.get("reason", "") for e in events]
        grant_reasons = [r for r in reasons if "grant" in r.lower()]
        self.assertTrue(grant_reasons, f"Expected grant audit event in reasons; got: {reasons}")


@_SKIP
class TestHealthEndpoint(_GL236TestBase):
    """GET /health must respond — confirms FastAPI is serving."""

    def test_health_returns_200(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200, resp.text)


if __name__ == "__main__":
    unittest.main()
