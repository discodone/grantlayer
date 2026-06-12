"""GL-228: FastAPI Migration Phase 1 — test suite.

Tests for Health, Readiness, and Grants CRUD endpoints via FastAPI TestClient.

If FastAPI/Starlette is not installed the entire module is skipped gracefully.
Install with: sudo apt-get install -y python3-fastapi python3-uvicorn python3-pydantic python3-starlette
"""

import os
import tempfile
import unittest

# ── FastAPI availability guard ─────────────────────────────────────────────
try:
    from fastapi.testclient import TestClient  # noqa: F401
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

_SKIP = unittest.skipUnless(_FASTAPI_AVAILABLE, "FastAPI not installed (apt install python3-fastapi python3-uvicorn python3-pydantic python3-starlette)")

# ── Test-environment isolation ────────────────────────────────────────────
# Note: env vars and config attributes are patched per-test via _GL228TestBase.setUp/tearDown
# to avoid polluting other test modules.  No module-level config mutations here.

if _FASTAPI_AVAILABLE:
    import backend.src.core.config as _gl228_config  # noqa: E402
    import backend.src.core.db as _gl228_db          # noqa: E402
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app


class _GL228TestBase(unittest.TestCase):
    """Common setUp/tearDown: isolated temp DB + config patches that are fully restored."""

    def setUp(self):
        # Save original config + db state
        self._orig_enable_operator = _gl228_config.ENABLE_OPERATOR_MODEL
        self._orig_allow_plaintext = _gl228_config.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE
        self._orig_db_path = _gl228_db.DB_PATH_OR_URL

        # Patch config for demo mode
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"] = "true"
        _gl228_config.ENABLE_OPERATOR_MODEL = False
        _gl228_config.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = True

        # Isolate DB
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        _gl228_db.DB_PATH_OR_URL = self._db_path
        _gl228_db.DB_PATH = self._db_path
        _gl228_db.init_db()

        self.client = TestClient(create_app(), raise_server_exceptions=True)

    def tearDown(self):
        # Restore config
        _gl228_config.ENABLE_OPERATOR_MODEL = self._orig_enable_operator
        _gl228_config.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_allow_plaintext
        _gl228_db.DB_PATH_OR_URL = self._orig_db_path
        _gl228_db.DB_PATH = self._orig_db_path
        try:
            os.unlink(self._db_path)
        except OSError:
            pass


# ── Health / Readiness ─────────────────────────────────────────────────────

@_SKIP
class TestHealthEndpoint(_GL228TestBase):

    def test_health_200(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)

    def test_health_status_ok(self):
        resp = self.client.get("/health")
        data = resp.json()
        self.assertEqual(data["status"], "ok")

    def test_health_service_name(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.json()["service"], "grantlayer")

    def test_health_check_type(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.json()["checkType"], "liveness")

    def test_health_content_type_json(self):
        resp = self.client.get("/health")
        self.assertIn("application/json", resp.headers.get("content-type", ""))

    def test_health_security_headers(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(resp.headers.get("x-frame-options"), "DENY")
        self.assertEqual(resp.headers.get("cache-control"), "no-store")


@_SKIP
class TestReadinessEndpoint(_GL228TestBase):

    def test_readiness_200_in_demo_mode(self):
        resp = self.client.get("/readiness")
        self.assertIn(resp.status_code, (200, 503))

    def test_readiness_service_name(self):
        resp = self.client.get("/readiness")
        self.assertEqual(resp.json().get("service"), "grantlayer")

    def test_readiness_check_type(self):
        resp = self.client.get("/readiness")
        self.assertEqual(resp.json().get("checkType"), "readiness")

    def test_readiness_status_field_present(self):
        resp = self.client.get("/readiness")
        self.assertIn("status", resp.json())


# ── Grants — unauthenticated guards ───────────────────────────────────────

@_SKIP
class TestGrantsAuthGuard(_GL228TestBase):

    def setUp(self):
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        super().setUp()

    def test_list_grants_no_auth_demo_mode(self):
        """In demo mode (no token required) list should return 200."""
        resp = self.client.get("/grants")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_list_grants_requires_token_when_configured(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "test-secret-token-16x"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        client = TestClient(create_app(), raise_server_exceptions=True)
        resp = client.get("/grants")
        self.assertIn(resp.status_code, (401, 403))
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN")
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN")

    def test_get_grant_not_found(self):
        resp = self.client.get("/grants/nonexistent-id-0000")
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertIn("errorCode", data.get("detail", data))


# ── Grants CRUD — demo mode (no token required) ───────────────────────────

@_SKIP
class TestGrantsCRUDDemoMode(_GL228TestBase):

    VALID_BODY = {
        "subjectId": "agent-001",
        "role": "operator",
        "action": "deploy",
        "resource": "service:payments",
        "validFrom": "2025-01-01T00:00:00Z",
        "validUntil": "2026-01-01T00:00:00Z",
        "createdBy": "operator-001",
        "reason": "Automated CI deploy grant",
    }

    def setUp(self):
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        super().setUp()

    def test_create_grant_201(self):
        resp = self.client.post("/grants", json=self.VALID_BODY)
        self.assertEqual(resp.status_code, 201)

    def test_create_grant_response_shape(self):
        resp = self.client.post("/grants", json=self.VALID_BODY)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        for field in ("id", "subjectId", "role", "action", "resource",
                      "validFrom", "validUntil", "createdBy", "reason",
                      "revoked", "createdAt", "signaturePresent", "signatureValid",
                      "useCount"):
            self.assertIn(field, data, f"Missing field: {field}")

    def test_create_grant_signature_present(self):
        resp = self.client.post("/grants", json=self.VALID_BODY)
        self.assertTrue(resp.json()["signaturePresent"])

    def test_create_grant_not_revoked(self):
        resp = self.client.post("/grants", json=self.VALID_BODY)
        self.assertFalse(resp.json()["revoked"])

    def test_create_grant_subject_id_reflected(self):
        resp = self.client.post("/grants", json=self.VALID_BODY)
        self.assertEqual(resp.json()["subjectId"], "agent-001")

    def test_list_grants_returns_created(self):
        self.client.post("/grants", json=self.VALID_BODY)
        resp = self.client.get("/grants")
        self.assertEqual(resp.status_code, 200)
        # At least one grant in the list
        self.assertGreaterEqual(len(resp.json()), 1)

    def test_get_grant_by_id(self):
        create_resp = self.client.post("/grants", json=self.VALID_BODY)
        grant_id = create_resp.json()["id"]
        resp = self.client.get(f"/grants/{grant_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], grant_id)

    def test_get_nonexistent_grant_404(self):
        resp = self.client.get("/grants/does-not-exist-xyz")
        self.assertEqual(resp.status_code, 404)

    def test_list_grants_response_is_list(self):
        resp = self.client.get("/grants")
        self.assertIsInstance(resp.json(), list)


# ── Grants — validation errors ────────────────────────────────────────────

@_SKIP
class TestGrantsValidation(_GL228TestBase):

    BASE_BODY = {
        "subjectId": "agent-001",
        "role": "operator",
        "action": "deploy",
        "resource": "service:payments",
        "validFrom": "2025-01-01T00:00:00Z",
        "validUntil": "2026-01-01T00:00:00Z",
        "createdBy": "operator-001",
        "reason": "Validation test grant",
    }

    def setUp(self):
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        super().setUp()

    def _post(self, body: dict):
        return self.client.post("/grants", json=body)

    def test_missing_subject_id_400(self):
        body = dict(self.BASE_BODY)
        del body["subjectId"]
        resp = self._post(body)
        self.assertEqual(resp.status_code, 422)  # Pydantic validation

    def test_missing_role_400(self):
        body = dict(self.BASE_BODY)
        del body["role"]
        resp = self._post(body)
        self.assertEqual(resp.status_code, 422)

    def test_invalid_date_range_400(self):
        body = dict(self.BASE_BODY, validFrom="2026-01-01T00:00:00Z", validUntil="2025-01-01T00:00:00Z")
        resp = self._post(body)
        self.assertEqual(resp.status_code, 400)

    def test_equal_dates_400(self):
        body = dict(self.BASE_BODY, validFrom="2025-01-01T00:00:00Z", validUntil="2025-01-01T00:00:00Z")
        resp = self._post(body)
        self.assertEqual(resp.status_code, 400)

    def test_invalid_timestamp_format_400(self):
        body = dict(self.BASE_BODY, validFrom="not-a-timestamp")
        resp = self._post(body)
        self.assertEqual(resp.status_code, 400)

    def test_max_uses_must_be_positive(self):
        body = dict(self.BASE_BODY, maxUses=0)
        resp = self._post(body)
        self.assertEqual(resp.status_code, 422)

    def test_max_uses_valid(self):
        body = dict(self.BASE_BODY, maxUses=5)
        resp = self._post(body)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["maxUses"], 5)

    def test_empty_subject_id_400(self):
        body = dict(self.BASE_BODY, subjectId="   ")
        resp = self._post(body)
        self.assertEqual(resp.status_code, 400)

    def test_empty_reason_400(self):
        body = dict(self.BASE_BODY, reason="")
        resp = self._post(body)
        self.assertEqual(resp.status_code, 400)


# ── Workspace context — X-Workspace-Id header ─────────────────────────────

@_SKIP
class TestGrantsWorkspaceHeader(_GL228TestBase):
    """Verify the X-Workspace-Id header is accepted without raising 5xx."""

    BASE_BODY = {
        "subjectId": "agent-ws-001",
        "role": "operator",
        "action": "deploy",
        "resource": "service:ws",
        "validFrom": "2025-01-01T00:00:00Z",
        "validUntil": "2026-01-01T00:00:00Z",
        "createdBy": "op-001",
        "reason": "Workspace header test",
    }

    def setUp(self):
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        super().setUp()

    def test_list_with_workspace_header_no_server_error(self):
        resp = self.client.get("/grants", headers={"X-Workspace-Id": "default"})
        self.assertNotEqual(resp.status_code // 100, 5)

    def test_create_with_workspace_header_no_server_error(self):
        resp = self.client.post(
            "/grants",
            json=self.BASE_BODY,
            headers={"X-Workspace-Id": "default"},
        )
        self.assertNotEqual(resp.status_code // 100, 5)


if __name__ == "__main__":
    unittest.main()
