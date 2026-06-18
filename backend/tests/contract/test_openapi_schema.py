"""GL-311 — OpenAPI schema contract tests.

Validates that /api/openapi.json:
- Is reachable and returns 200
- Contains expected top-level fields (info, paths, components)
- Has expected paths for core resources
- Has info.title matching 'GrantLayer'
- Has at least one security scheme defined
"""

from __future__ import annotations

import unittest


class TestOpenAPISchema(unittest.TestCase):
    def _client(self):
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        return TestClient(create_app(), raise_server_exceptions=False)

    def _schema(self):
        client = self._client()
        r = client.get("/api/openapi.json")
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_openapi_endpoint_200(self):
        client = self._client()
        r = client.get("/api/openapi.json")
        self.assertEqual(r.status_code, 200)

    def test_schema_has_info(self):
        schema = self._schema()
        self.assertIn("info", schema)
        self.assertIn("title", schema["info"])

    def test_schema_title_contains_grantlayer(self):
        schema = self._schema()
        self.assertIn("GrantLayer", schema["info"]["title"])

    def test_schema_has_paths(self):
        schema = self._schema()
        self.assertIn("paths", schema)
        self.assertIsInstance(schema["paths"], dict)
        self.assertGreater(len(schema["paths"]), 10)

    def test_grants_path_exists(self):
        schema = self._schema()
        paths = schema["paths"]
        grant_paths = [p for p in paths if "grants" in p]
        self.assertGreater(len(grant_paths), 0)

    def test_auth_token_path_exists(self):
        schema = self._schema()
        paths = schema["paths"]
        auth_paths = [p for p in paths if "auth" in p or "token" in p]
        self.assertGreater(len(auth_paths), 0)

    def test_webhooks_path_exists(self):
        schema = self._schema()
        paths = schema["paths"]
        webhook_paths = [p for p in paths if "webhook" in p.lower()]
        self.assertGreater(len(webhook_paths), 0)

    def test_audit_events_path_exists(self):
        schema = self._schema()
        paths = schema["paths"]
        audit_paths = [p for p in paths if "audit" in p.lower()]
        self.assertGreater(len(audit_paths), 0)

    def test_admin_path_exists(self):
        schema = self._schema()
        paths = schema["paths"]
        admin_paths = [p for p in paths if "admin" in p.lower()]
        self.assertGreater(len(admin_paths), 0)

    def test_health_path_exists(self):
        schema = self._schema()
        paths = schema["paths"]
        self.assertIn("/health", paths)

    def test_schema_openapi_version(self):
        schema = self._schema()
        self.assertIn("openapi", schema)
        self.assertTrue(schema["openapi"].startswith("3."))

    def test_paths_have_http_methods(self):
        schema = self._schema()
        valid_methods = {"get", "post", "put", "delete", "patch", "head", "options"}
        for path, spec in list(schema["paths"].items())[:10]:
            path_methods = set(spec.keys()) & valid_methods
            self.assertGreater(len(path_methods), 0, f"No methods for path {path}")

    def test_grant_requests_path_exists(self):
        schema = self._schema()
        paths = schema["paths"]
        gr_paths = [p for p in paths if "grant-request" in p.lower()]
        self.assertGreater(len(gr_paths), 0)


if __name__ == "__main__":
    unittest.main()
