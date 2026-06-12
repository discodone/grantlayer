"""GL-242: API versioning — all endpoints under /v1/ prefix.

Covers:
  1. Health/readiness remain at top-level (no /v1/)
  2. All API routes are served under /v1/
  3. Backward-compat: unversioned paths return 307 redirect to /v1/
  4. OpenAPI schema reflects /v1/ paths
  5. Route count sanity check
"""

import os
import pathlib
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

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_JWT_SECRET = "test-secret-gl242"


class _Base(unittest.TestCase):
    def setUp(self):
        self._orig_op = _cfg.ENABLE_OPERATOR_MODEL
        self._orig_plaintext = _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE
        self._orig_db = _db.DB_PATH_OR_URL
        self._orig_admin = _cfg.GRANTLAYER_ADMIN_TOKEN
        self._orig_jwt = os.environ.get("GRANTLAYER_JWT_SECRET", "")

        os.environ["GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"] = "true"
        os.environ["GRANTLAYER_JWT_SECRET"] = _JWT_SECRET
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = True
        _cfg.ENABLE_OPERATOR_MODEL = True
        _cfg.GRANTLAYER_ADMIN_TOKEN = ""

        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        _db.DB_PATH_OR_URL = self._tmp.name
        _db.init_db()

        self.app = create_app()
        self.client = TestClient(self.app, raise_server_exceptions=True)

    def tearDown(self):
        _cfg.ENABLE_OPERATOR_MODEL = self._orig_op
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_plaintext
        _db.DB_PATH_OR_URL = self._orig_db
        _cfg.GRANTLAYER_ADMIN_TOKEN = self._orig_admin
        os.environ["GRANTLAYER_JWT_SECRET"] = self._orig_jwt
        os.unlink(self._tmp.name)


@_SKIP
class TestHealthRemainsAtRoot(_Base):
    """Health and readiness must NOT be prefixed with /v1/."""

    def test_health_at_root(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")

    def test_readiness_at_root(self):
        resp = self.client.get("/readiness")
        self.assertIn(resp.status_code, (200, 503))

    def test_health_not_under_v1(self):
        resp = self.client.get("/v1/health")
        self.assertEqual(resp.status_code, 404)

    def test_readiness_not_under_v1(self):
        resp = self.client.get("/v1/readiness")
        self.assertEqual(resp.status_code, 404)


@_SKIP
class TestV1RoutesServed(_Base):
    """Core API routes are accessible under /v1/."""

    def test_v1_grants_requires_auth(self):
        resp = self.client.get("/v1/grants")
        self.assertIn(resp.status_code, (200, 401))

    def test_v1_auth_token_exists(self):
        resp = self.client.post("/v1/auth/token", json={"operator_id": "x", "secret": "y"})
        self.assertIn(resp.status_code, (200, 401, 403))

    def test_v1_audit_events_requires_auth(self):
        resp = self.client.get("/v1/audit-events")
        self.assertIn(resp.status_code, (200, 401))

    def test_v1_grant_requests_requires_auth(self):
        resp = self.client.get("/v1/grant-requests")
        self.assertIn(resp.status_code, (200, 401))

    def test_v1_operators_me_requires_auth(self):
        resp = self.client.get("/v1/operators/me")
        self.assertIn(resp.status_code, (200, 401))

    def test_v1_challenges_exists(self):
        resp = self.client.get("/v1/challenges")
        self.assertIn(resp.status_code, (200, 401))

    def test_v1_approvals_exists(self):
        resp = self.client.post("/v1/approvals/evaluate", json={})
        self.assertIn(resp.status_code, (200, 401, 422))

    def test_v1_admin_requires_auth(self):
        resp = self.client.get("/v1/admin/operators")
        self.assertIn(resp.status_code, (200, 401))

    def test_v1_grant_executions_exists(self):
        resp = self.client.get("/v1/grant-executions")
        self.assertIn(resp.status_code, (200, 401))


@_SKIP
class TestBackwardCompatRedirects(_Base):
    """Old unversioned paths return 307 redirect to /v1/ equivalent."""

    def _assert_redirects_to_v1(self, path: str, method: str = "GET"):
        resp = self.client.request(method, path, follow_redirects=False)
        self.assertEqual(resp.status_code, 307, f"Expected 307 for {method} {path}, got {resp.status_code}")
        location = resp.headers.get("location", "")
        self.assertTrue(
            location.startswith("/v1") or "/v1/" in location,
            f"Redirect location should point to /v1/, got: {location}",
        )

    def test_grants_redirects(self):
        self._assert_redirects_to_v1("/grants")

    def test_grants_subpath_redirects(self):
        self._assert_redirects_to_v1("/grants/some-id")

    def test_auth_token_redirects(self):
        self._assert_redirects_to_v1("/auth/token", method="POST")

    def test_audit_events_redirects(self):
        self._assert_redirects_to_v1("/audit-events")

    def test_grant_requests_redirects(self):
        self._assert_redirects_to_v1("/grant-requests")

    def test_operators_redirects(self):
        self._assert_redirects_to_v1("/operators/me")

    def test_admin_redirects(self):
        self._assert_redirects_to_v1("/admin/operators")

    def test_challenges_redirects(self):
        self._assert_redirects_to_v1("/challenges")

    def test_demo_action_redirects(self):
        self._assert_redirects_to_v1("/demo-action", method="POST")

    def test_grant_executions_redirects(self):
        self._assert_redirects_to_v1("/grant-executions")


@_SKIP
class TestOpenApiSchema(_Base):
    """OpenAPI schema must expose /v1/ paths."""

    def test_openapi_has_v1_grants(self):
        resp = self.client.get("/api/openapi.json")
        self.assertEqual(resp.status_code, 200)
        schema = resp.json()
        paths = list(schema.get("paths", {}).keys())
        v1_paths = [p for p in paths if p.startswith("/v1/")]
        self.assertGreater(len(v1_paths), 5, f"Expected >5 /v1/ paths in schema, got: {v1_paths}")

    def test_openapi_no_top_level_api_paths(self):
        resp = self.client.get("/api/openapi.json")
        self.assertEqual(resp.status_code, 200)
        schema = resp.json()
        paths = list(schema.get("paths", {}).keys())
        # Backward-compat redirects are not in schema (include_in_schema=False)
        bad = [p for p in paths if p in ("/grants", "/auth/token", "/audit-events", "/grant-requests")]
        self.assertEqual(bad, [], f"Unversioned paths should not appear in schema: {bad}")


@_SKIP
class TestRouteCountSanity(_Base):
    """Sanity-check that enough routes were wired under /v1/."""

    def test_minimum_v1_route_count(self):
        routes = [r.path for r in self.app.routes if r.path.startswith("/v1/")]
        self.assertGreater(len(routes), 30, f"Expected >30 /v1/ routes, got {len(routes)}: {routes[:5]}...")


if __name__ == "__main__":
    unittest.main()
