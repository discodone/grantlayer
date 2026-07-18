"""Grant role 'agent' — accepted by the create endpoints' role validation.

Agent-subject grants (an automated agent exercising a scoped permission) are
first-class: the policy engine has always matched them by plain string
compare, but the router-side ALLOWED_GRANT_ROLES enum rejected creation with
422, forcing service-layer workarounds. These tests pin 'agent' as a valid
role at BOTH create endpoints while garbage roles remain rejected.

Self-provisions SQLite (listed in _sqlite_only_modules.py).
"""

import os
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

_SKIP = unittest.skipUnless(_FASTAPI_AVAILABLE, "FastAPI not installed")

if _FASTAPI_AVAILABLE:
    import backend.src.core.config as _cfg
    import backend.src.core.db as _db
    from backend.src.api.app import create_app

_JWT_SECRET = "test-secret-agent-role"


class _Base(unittest.TestCase):
    def setUp(self):
        self._orig_op = _cfg.ENABLE_OPERATOR_MODEL
        self._orig_plaintext = _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE
        self._orig_db = _db.DB_PATH_OR_URL
        self._orig_admin = _cfg.GRANTLAYER_ADMIN_TOKEN
        self._orig_jwt_secret_env = os.environ.get("GRANTLAYER_JWT_SECRET", "")

        os.environ["GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"] = "true"
        os.environ["GRANTLAYER_JWT_SECRET"] = _JWT_SECRET
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = True
        _cfg.ENABLE_OPERATOR_MODEL = True
        _cfg.GRANTLAYER_ADMIN_TOKEN = ""
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        _db.DB_PATH_OR_URL = self._db_path
        _db.DB_PATH = self._db_path
        _db.init_db()

        self.client = TestClient(create_app(), raise_server_exceptions=True)

    def tearDown(self):
        _cfg.ENABLE_OPERATOR_MODEL = self._orig_op
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_plaintext
        _cfg.GRANTLAYER_ADMIN_TOKEN = self._orig_admin
        if self._orig_jwt_secret_env:
            os.environ["GRANTLAYER_JWT_SECRET"] = self._orig_jwt_secret_env
        else:
            os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        _db.DB_PATH_OR_URL = self._orig_db
        _db.DB_PATH = self._orig_db
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def _auth(self) -> dict:
        from backend.src.api.auth_jwt import create_dev_token
        return {"Authorization": f"Bearer {create_dev_token(secret=_JWT_SECRET)}"}

    def _grant_body(self, role: str) -> dict:
        return {
            "subjectId": "backup-agent",
            "role": role,
            "action": "pg_dump",
            "resource": "db/grantlayer-postgres",
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2026-12-31T23:59:59Z",
            "createdBy": "test-op",
            "reason": "agent role acceptance test",
        }

    def _request_body(self, role: str) -> dict:
        return {
            "subjectId": "backup-agent",
            "role": role,
            "action": "pg_dump",
            "resource": "db/grantlayer-postgres",
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2026-12-31T23:59:59Z",
            "reason": "agent role acceptance test",
        }


@_SKIP
class TestAgentRoleInEnum(unittest.TestCase):
    def test_agent_in_allowed_grant_roles(self):
        from backend.src.grants.grant_requests import ALLOWED_GRANT_ROLES
        self.assertIn("agent", ALLOWED_GRANT_ROLES)


@_SKIP
class TestAgentRoleGrantsEndpoint(_Base):
    def test_agent_role_accepted_201(self):
        r = self.client.post("/v1/grants", json=self._grant_body("agent"),
                             headers=self._auth())
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["role"], "agent")

    def test_garbage_role_still_422(self):
        r = self.client.post("/v1/grants", json=self._grant_body("fake-admin"),
                             headers=self._auth())
        self.assertEqual(r.status_code, 422)

    def test_agent_listed_in_rejection_reason(self):
        r = self.client.post("/v1/grants", json=self._grant_body("nonsense"),
                             headers=self._auth())
        self.assertIn("agent", r.json().get("reason", ""))


@_SKIP
class TestAgentRoleGrantRequestsEndpoint(_Base):
    def test_agent_role_accepted_201(self):
        r = self.client.post("/v1/grant-requests", json=self._request_body("agent"),
                             headers=self._auth())
        self.assertEqual(r.status_code, 201, r.text)

    def test_garbage_role_still_rejected(self):
        # This endpoint's long-standing contract is 400 for a bad role
        # (invalid_field), unlike /v1/grants which uses 422 (invalid_role).
        r = self.client.post("/v1/grant-requests", json=self._request_body("fake-admin"),
                             headers=self._auth())
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
