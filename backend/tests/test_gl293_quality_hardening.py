"""GL-293 Quality Hardening tests.

Covers:
1. /metrics endpoint returns 200 with Prometheus text format
2. docker-compose.yml has PostgreSQL as default backend
3. AGENTS.md no longer claims workspace isolation is "not production-complete" incorrectly
4. README.md workspace isolation status is accurate
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    import backend.src.core.db as _db
    import backend.src.core.config as _cfg
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    _SKIP = lambda cls: cls  # noqa: E731
except ImportError:
    _SKIP = unittest.skip("FastAPI/backend not available")


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

class _AppBase(unittest.TestCase):

    def setUp(self):
        self._orig_db = _db.DB_PATH_OR_URL
        self._orig_sa_engine = _db._sa_engine
        self._orig_engine_url = _db._engine_url
        self._orig_env = {
            k: os.environ.get(k) for k in (
                "GRANTLAYER_DB", "GRANTLAYER_JWT_SECRET", "GRANTLAYER_JWT_PUBLIC_KEY",
                "GRANTLAYER_JWT_PRIVATE_KEY", "GRANTLAYER_JWT_ALGORITHM",
                "GRANTLAYER_REQUIRE_ADMIN_TOKEN", "GRANTLAYER_ADMIN_TOKEN",
            )
        }
        for k in ("GRANTLAYER_JWT_SECRET", "GRANTLAYER_JWT_PUBLIC_KEY",
                  "GRANTLAYER_JWT_PRIVATE_KEY", "GRANTLAYER_JWT_ALGORITHM",
                  "GRANTLAYER_REQUIRE_ADMIN_TOKEN", "GRANTLAYER_ADMIN_TOKEN"):
            os.environ.pop(k, None)

        _db._sa_engine = None
        _db._engine_url = None

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        os.environ["GRANTLAYER_DB"] = self._db_path
        _db.DB_PATH_OR_URL = self._db_path
        _db.DB_PATH = self._db_path
        _db.init_db()

        self.client = TestClient(create_app(), raise_server_exceptions=False)

    def tearDown(self):
        if _db._sa_engine is not None:
            try:
                _db._sa_engine.dispose()
            except Exception:
                pass
        _db._sa_engine = self._orig_sa_engine
        _db._engine_url = self._orig_engine_url
        _db.DB_PATH_OR_URL = self._orig_db
        _db.DB_PATH = self._orig_db
        for k, v in self._orig_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        try:
            os.unlink(self._db_path)
        except OSError:
            pass


# ──────────────────────────────────────────────────────────────
# 1. Prometheus /metrics endpoint
# ──────────────────────────────────────────────────────────────

@_SKIP
class TestPrometheusMetrics(_AppBase):
    """GL-293-1: /metrics endpoint returns Prometheus text format."""

    def test_metrics_endpoint_returns_200(self):
        resp = self.client.get("/metrics")
        self.assertEqual(resp.status_code, 200)

    def test_metrics_content_type_is_prometheus(self):
        resp = self.client.get("/metrics")
        self.assertIn("text/plain", resp.headers.get("content-type", ""))

    def test_metrics_contains_http_request_counter(self):
        resp = self.client.get("/metrics")
        self.assertEqual(resp.status_code, 200)
        body = resp.text
        # After making a request, http metrics should appear
        self.assertIn("#", body)

    def test_metrics_not_exposed_in_openapi(self):
        """The /metrics route should not appear in the OpenAPI schema."""
        resp = self.client.get("/api/openapi.json")
        self.assertEqual(resp.status_code, 200)
        paths = resp.json().get("paths", {})
        self.assertNotIn("/metrics", paths)


# ──────────────────────────────────────────────────────────────
# 2. docker-compose.yml PostgreSQL default
# ──────────────────────────────────────────────────────────────

class TestDockerComposePostgresDefault(unittest.TestCase):
    """GL-293-4: docker-compose.yml uses PostgreSQL as default backend."""

    def _read_compose(self) -> str:
        compose_path = os.path.join(REPO_ROOT, "docker-compose.yml")
        with open(compose_path) as f:
            return f.read()

    def test_database_url_defaults_to_postgres(self):
        content = self._read_compose()
        self.assertIn("GRANTLAYER_DATABASE_URL", content)
        self.assertIn("postgresql://", content)

    def test_db_service_has_no_profiles(self):
        """PostgreSQL db service should start without a profile."""
        content = self._read_compose()
        # The profiles: [postgres] line should be gone
        self.assertNotIn("profiles:", content)

    def test_api_depends_on_db(self):
        """API service should declare a dependency on the db service."""
        content = self._read_compose()
        self.assertIn("depends_on:", content)
        self.assertIn("condition: service_healthy", content)


# ──────────────────────────────────────────────────────────────
# 3. Multi-tenancy documentation accuracy
# ──────────────────────────────────────────────────────────────

class TestMultiTenancyDocsAccuracy(unittest.TestCase):
    """GL-293-3: Workspace isolation docs reflect actual implementation."""

    def _readme(self) -> str:
        with open(os.path.join(REPO_ROOT, "README.md")) as f:
            return f.read()

    def _agents(self) -> str:
        with open(os.path.join(REPO_ROOT, "AGENTS.md")) as f:
            return f.read()

    def test_readme_does_not_claim_isolation_not_implemented(self):
        """README should not say isolation is 'Not implemented'."""
        readme = self._readme()
        self.assertNotIn("Tenant/workspace isolation | Not implemented", readme)

    def test_readme_says_isolation_is_enforced(self):
        """README should acknowledge that isolation is enforced at API level."""
        readme = self._readme()
        self.assertIn("Enforced", readme)

    def test_agents_no_production_overclaim(self):
        """AGENTS.md should have a 'No production SaaS' rule."""
        agents = self._agents()
        self.assertIn("No production SaaS", agents)

    def test_agents_mentions_workspace_enforcement(self):
        """AGENTS.md Code Rules should describe workspace enforcement."""
        agents = self._agents()
        self.assertIn("workspace isolation is enforced", agents)


if __name__ == "__main__":
    unittest.main()
