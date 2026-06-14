"""GL-233: Critical Quickstart Fixes — test suite.

Covers:
- BUG 1: docker-compose.yml publishes port 8765 to the host (not just expose)
- BUG 2: GRANTLAYER_ENABLE_OPERATOR_MODEL defaults to true in docker-compose.yml
- BUG 3: POST /grants creates an audit event visible in GET /audit-events
- BUG 4: POST /auth/token returns a valid JWT given correct credentials
- /auth/token returns 501 when JWT is not configured
- /auth/token returns 401 for wrong secret
- Audit event has correct fields after grant creation
- QUICKSTART.md documents http://localhost:8765/health
- QUICKSTART.md documents /auth/token as primary token path
"""

from __future__ import annotations

import os
import pathlib
import tempfile
import unittest

# ── FastAPI availability guard ─────────────────────────────────────────────
try:
    from fastapi.testclient import TestClient  # noqa: F401
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

_SKIP = unittest.skipUnless(
    _FASTAPI_AVAILABLE,
    "FastAPI not installed (apt install python3-fastapi python3-uvicorn python3-pydantic python3-starlette)",
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

if _FASTAPI_AVAILABLE:
    import backend.src.core.config as _cfg
    import backend.src.core.db as _db
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app

_JWT_SECRET = "gl233-test-secret-xxxxxxxxxxxxxxxx"
_ADMIN_TOKEN = "gl233-admin-token-test"

_GRANT_BODY = {
    "subjectId": "agent-gl233",
    "role": "viewer",
    "action": "read",
    "resource": "reports",
    "validFrom": "2025-01-01T00:00:00Z",
    "validUntil": "2025-12-31T23:59:59Z",
    "createdBy": "test-operator",
    "reason": "gl233 quickstart test",
}


# ── Shared test base ───────────────────────────────────────────────────────

class _GL233TestBase(unittest.TestCase):
    """Isolated temp DB + config; JWT + admin token configured."""

    def setUp(self):
        self._orig_enable_operator = _cfg.ENABLE_OPERATOR_MODEL
        self._orig_allow_plaintext = _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE
        self._orig_db_path = _db.DB_PATH_OR_URL

        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"] = "true"
        os.environ["GRANTLAYER_JWT_SECRET"] = _JWT_SECRET
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = _ADMIN_TOKEN
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        _cfg.ENABLE_OPERATOR_MODEL = False
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = True

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        _db.DB_PATH_OR_URL = self._db_path
        _db.DB_PATH = self._db_path
        _db.init_db()

        self.client = TestClient(create_app(), raise_server_exceptions=True)

    def tearDown(self):
        _cfg.ENABLE_OPERATOR_MODEL = self._orig_enable_operator
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_allow_plaintext
        _db.DB_PATH_OR_URL = self._orig_db_path
        _db.DB_PATH = self._orig_db_path
        for key in ("GRANTLAYER_JWT_SECRET", "GRANTLAYER_ADMIN_TOKEN",
                    "GRANTLAYER_REQUIRE_ADMIN_TOKEN", "GRANTLAYER_ENABLE_OPERATOR_MODEL",
                    "GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"):
            os.environ.pop(key, None)
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def _jwt_header(self) -> dict:
        from backend.src.api.auth_jwt import create_dev_token
        token = create_dev_token(secret=_JWT_SECRET)
        return {"Authorization": f"Bearer {token}"}


# ── BUG 1: docker-compose.yml port published ──────────────────────────────

class TestDockerComposePortPublished(unittest.TestCase):
    """BUG 1: Port 8765 must be published (ports:) not just expose:."""

    def _load_compose(self) -> dict:
        import yaml
        compose_path = REPO_ROOT / "docker-compose.yml"
        with open(compose_path) as f:
            return yaml.safe_load(f)

    def test_compose_file_exists(self):
        self.assertTrue((REPO_ROOT / "docker-compose.yml").exists())

    @unittest.skipUnless(__import__("importlib").util.find_spec("yaml") is not None, "PyYAML not installed")
    def test_api_service_has_ports_not_just_expose(self):
        data = self._load_compose()
        api_service = data["services"]["api"]
        self.assertIn("ports", api_service, "api service must have 'ports:' to publish to host")

    @unittest.skipUnless(__import__("importlib").util.find_spec("yaml") is not None, "PyYAML not installed")
    def test_api_service_publishes_8765(self):
        data = self._load_compose()
        api_service = data["services"]["api"]
        ports = api_service.get("ports", [])
        # Accept "8765:8765" or {"target": 8765, "published": 8765}
        ports_str = str(ports)
        self.assertIn("8765", ports_str, "Port 8765 must be published to the host")

    @unittest.skipUnless(__import__("importlib").util.find_spec("yaml") is not None, "PyYAML not installed")
    def test_api_service_no_expose_only(self):
        """Ensure 'expose' without 'ports' is not the only binding."""
        data = self._load_compose()
        api_service = data["services"]["api"]
        # It's fine to have 'expose' in addition to 'ports', but not instead of
        has_ports = "ports" in api_service
        self.assertTrue(has_ports, "api service must have 'ports:' so curl http://localhost:8765 works")


# ── BUG 2: Operator model default in docker-compose ───────────────────────

class TestOperatorModelDefault(unittest.TestCase):
    """BUG 2: GRANTLAYER_ENABLE_OPERATOR_MODEL should default to true."""

    @unittest.skipUnless(__import__("importlib").util.find_spec("yaml") is not None, "PyYAML not installed")
    def test_operator_model_defaults_true_in_compose(self):
        import yaml
        compose_path = REPO_ROOT / "docker-compose.yml"
        with open(compose_path) as f:
            data = yaml.safe_load(f)
        api_service = data["services"]["api"]
        env_list = api_service.get("environment", [])
        env_str = str(env_list)
        # The default value in the compose template should be 'true'
        self.assertIn("GRANTLAYER_ENABLE_OPERATOR_MODEL", env_str)
        # Verify it uses 'true' as the default fallback (not 'false')
        self.assertNotIn("OPERATOR_MODEL:-false}", env_str,
                         "GRANTLAYER_ENABLE_OPERATOR_MODEL must not default to false")
        self.assertIn("OPERATOR_MODEL:-true}", env_str,
                      "GRANTLAYER_ENABLE_OPERATOR_MODEL must default to true")


# ── BUG 3: Audit event after grant creation ───────────────────────────────

@_SKIP
class TestAuditEventAfterGrantCreate(_GL233TestBase):
    """BUG 3: POST /grants must produce an audit event in GET /audit-events."""

    def test_audit_events_empty_before_grant(self):
        resp = self.client.get("/v1/audit-events", headers=self._jwt_header())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["items"], [])

    def test_audit_event_created_after_grant(self):
        self.client.post(
            "/v1/grants",
            json=_GRANT_BODY,
            headers={**self._jwt_header(), "Content-Type": "application/json"},
        )
        resp = self.client.get("/v1/audit-events", headers=self._jwt_header())
        self.assertEqual(resp.status_code, 200)
        events = resp.json()["items"]
        self.assertGreater(len(events), 0, "Audit events must not be empty after creating a grant")

    def test_audit_event_has_correct_subject_id(self):
        self.client.post(
            "/v1/grants",
            json=_GRANT_BODY,
            headers={**self._jwt_header(), "Content-Type": "application/json"},
        )
        events = self.client.get("/v1/audit-events", headers=self._jwt_header()).json()["items"]
        subjects = [e.get("subjectId") or e.get("subject_id") for e in events]
        self.assertIn("agent-gl233", subjects)

    def test_audit_event_is_approved(self):
        self.client.post(
            "/v1/grants",
            json=_GRANT_BODY,
            headers={**self._jwt_header(), "Content-Type": "application/json"},
        )
        events = self.client.get("/v1/audit-events", headers=self._jwt_header()).json()["items"]
        self.assertTrue(any(e.get("approved") for e in events),
                        "Grant-create audit event must have approved=true")

    def test_audit_event_has_matched_grant_id(self):
        create_resp = self.client.post(
            "/v1/grants",
            json=_GRANT_BODY,
            headers={**self._jwt_header(), "Content-Type": "application/json"},
        )
        grant_id = create_resp.json().get("id")
        events = self.client.get("/v1/audit-events", headers=self._jwt_header()).json()["items"]
        matched_ids = [e.get("matchedGrantId") or e.get("matched_grant_id") for e in events]
        self.assertIn(grant_id, matched_ids,
                      "Audit event must reference the created grant's ID")

    def test_multiple_grants_produce_multiple_events(self):
        for i in range(3):
            body = {**_GRANT_BODY, "subjectId": f"agent-{i:03d}"}
            self.client.post(
                "/v1/grants",
                json=body,
                headers={**self._jwt_header(), "Content-Type": "application/json"},
            )
        events = self.client.get("/v1/audit-events", headers=self._jwt_header()).json()["items"]
        self.assertGreaterEqual(len(events), 3)

    def test_grant_create_returns_201(self):
        resp = self.client.post(
            "/v1/grants",
            json=_GRANT_BODY,
            headers={**self._jwt_header(), "Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 201)


# ── BUG 4: /auth/token endpoint ──────────────────────────────────────────

@_SKIP
class TestAuthTokenEndpoint(_GL233TestBase):
    """BUG 4: POST /auth/token must issue a valid JWT."""

    def test_token_endpoint_returns_200_with_valid_credentials(self):
        resp = self.client.post(
            "/v1/auth/token",
            json={"operator_id": "dev", "secret": _ADMIN_TOKEN},
        )
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_token_response_has_access_token(self):
        resp = self.client.post(
            "/v1/auth/token",
            json={"operator_id": "dev", "secret": _ADMIN_TOKEN},
        )
        data = resp.json()
        self.assertIn("access_token", data)
        self.assertTrue(data["access_token"], "access_token must not be empty")

    def test_token_response_type_is_bearer(self):
        resp = self.client.post(
            "/v1/auth/token",
            json={"operator_id": "dev", "secret": _ADMIN_TOKEN},
        )
        self.assertEqual(resp.json()["token_type"], "bearer")

    def test_token_response_expires_in_3600(self):
        resp = self.client.post(
            "/v1/auth/token",
            json={"operator_id": "dev", "secret": _ADMIN_TOKEN},
        )
        self.assertEqual(resp.json()["expires_in"], 3600)

    def test_issued_jwt_is_valid(self):
        resp = self.client.post(
            "/v1/auth/token",
            json={"operator_id": "dev", "secret": _ADMIN_TOKEN},
        )
        token = resp.json()["access_token"]
        from backend.src.api.auth_jwt import decode_token
        payload = decode_token(token, _JWT_SECRET)
        self.assertEqual(payload["sub"], "dev")

    def test_token_works_for_authenticated_endpoints(self):
        resp = self.client.post(
            "/v1/auth/token",
            json={"operator_id": "dev", "secret": _ADMIN_TOKEN},
        )
        token = resp.json()["access_token"]
        grants_resp = self.client.get(
            "/v1/grants",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(grants_resp.status_code, 200)

    def test_wrong_secret_returns_401(self):
        resp = self.client.post(
            "/v1/auth/token",
            json={"operator_id": "dev", "secret": "wrong-secret"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_wrong_secret_error_code(self):
        resp = self.client.post(
            "/v1/auth/token",
            json={"operator_id": "dev", "secret": "wrong-secret"},
        )
        self.assertEqual(resp.json().get("errorCode"), "invalid_credentials")

    def test_token_endpoint_without_jwt_secret_returns_501(self):
        """When GRANTLAYER_JWT_SECRET is not set, /auth/token must return 501."""
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        client = TestClient(create_app(), raise_server_exceptions=True)
        resp = client.post(
            "/v1/auth/token",
            json={"operator_id": "dev", "secret": _ADMIN_TOKEN},
        )
        self.assertEqual(resp.status_code, 501)
        self.assertEqual(resp.json().get("errorCode"), "jwt_not_configured")
        # Restore
        os.environ["GRANTLAYER_JWT_SECRET"] = _JWT_SECRET


# ── End-to-end flow: token → grant → audit ────────────────────────────────

@_SKIP
class TestEndToEndQuickstartFlow(_GL233TestBase):
    """Full quickstart flow: /auth/token → POST /grants → GET /audit-events."""

    def test_full_quickstart_flow(self):
        # Step 1: get token
        token_resp = self.client.post(
            "/v1/auth/token",
            json={"operator_id": "dev", "secret": _ADMIN_TOKEN},
        )
        self.assertEqual(token_resp.status_code, 200)
        token = token_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Step 2: create grant
        grant_resp = self.client.post("/v1/grants", json=_GRANT_BODY, headers=headers)
        self.assertEqual(grant_resp.status_code, 201)
        grant_id = grant_resp.json()["id"]

        # Step 3: verify audit events
        audit_resp = self.client.get("/v1/audit-events", headers=headers)
        self.assertEqual(audit_resp.status_code, 200)
        events = audit_resp.json()["items"]
        self.assertGreater(len(events), 0, "Audit events must not be empty")
        grant_ids = [e.get("matchedGrantId") or e.get("matched_grant_id") for e in events]
        self.assertIn(grant_id, grant_ids, "Created grant must appear in audit events")


# ── QUICKSTART.md content checks ──────────────────────────────────────────

class TestQuickstartMdContent(unittest.TestCase):
    """QUICKSTART.md must document the corrected access patterns."""

    def _read_quickstart(self) -> str:
        path = REPO_ROOT / "QUICKSTART.md"
        return path.read_text(encoding="utf-8")

    def test_quickstart_exists(self):
        self.assertTrue((REPO_ROOT / "QUICKSTART.md").exists())

    def test_quickstart_documents_direct_port_health(self):
        content = self._read_quickstart()
        self.assertIn("localhost:8765", content,
                      "QUICKSTART.md must document direct http://localhost:8765 access")

    def test_quickstart_documents_auth_token_endpoint(self):
        content = self._read_quickstart()
        self.assertIn("/v1/auth/token", content,
                      "QUICKSTART.md must document the /auth/token endpoint")

    def test_quickstart_operator_model_doc_corrected(self):
        content = self._read_quickstart()
        # The old incorrect claim "it is the default" referring to an external default
        # should be replaced with accurate language
        self.assertNotIn(
            "it is the default",
            content,
            "QUICKSTART.md must not claim ENABLE_OPERATOR_MODEL=true is an implicit default",
        )


if __name__ == "__main__":
    unittest.main()
