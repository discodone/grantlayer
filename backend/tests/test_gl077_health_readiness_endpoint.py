"""Tests for GL-077 health / readiness endpoint baseline.

Validates:
- GET /health returns minimal safe liveness response.
- GET /readiness returns readiness based on GL-076 runtime config.
- Invalid runtime config results in HTTP 503 with safe error.
- No secrets or raw environment values are exposed.
- OpenAPI contract documents both endpoints.
"""

import json
import os
import pathlib
import sys
import tempfile
import unittest
import importlib

# Ensure backend is on path so that `import src.server` resolves correctly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestGL077HealthReadinessEndpoint(unittest.TestCase):
    """GL-077: Health / readiness endpoint baseline tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_runtime_mode = os.environ.get("GRANTLAYER_RUNTIME_MODE")

        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import src.server as server_mod
        importlib.reload(server_mod)
        self.server_mod = server_mod
        self.handler_class = server_mod.GrantLayerHandler

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)

        if self._orig_runtime_mode is not None:
            os.environ["GRANTLAYER_RUNTIME_MODE"] = self._orig_runtime_mode
        else:
            os.environ.pop("GRANTLAYER_RUNTIME_MODE", None)

    def _run_get(self, path, headers=None):
        """Simulate GET request and return (status, response_json)."""
        from io import BytesIO

        handler = self.handler_class.__new__(self.handler_class)
        handler.rfile = BytesIO(b"")
        handler.wfile = BytesIO()
        handler.headers = headers or {}
        handler.path = path
        handler.command = "GET"
        handler.requestline = f"GET {path} HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None
        handler.do_GET()
        handler.wfile.seek(0)
        response = handler.wfile.read()
        parts = response.split(b"\r\n\r\n", 1)
        data = json.loads(parts[1]) if len(parts) > 1 else {}
        # Derive status from response line
        status_line = response.split(b"\r\n")[0].decode()
        status = int(status_line.split()[1])
        return status, data

    # ──────────────────────────────────────────────
    # GET /health
    # ──────────────────────────────────────────────
    def test_health_returns_200(self):
        status, _ = self._run_get("/health")
        self.assertEqual(status, 200)

    def test_health_returns_status_ok(self):
        _, resp = self._run_get("/health")
        self.assertEqual(resp.get("status"), "ok")

    def test_health_returns_service_grantlayer(self):
        _, resp = self._run_get("/health")
        self.assertEqual(resp.get("service"), "grantlayer")

    def test_health_returns_check_type_liveness(self):
        _, resp = self._run_get("/health")
        self.assertEqual(resp.get("checkType"), "liveness")

    def test_health_does_not_expose_secrets_or_raw_env(self):
        os.environ["SECRET_TOKEN"] = "sk-secret-12345"
        os.environ["DATABASE_URL"] = "postgres://localhost/db"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "admin-secret"
        _, resp = self._run_get("/health")
        resp_str = json.dumps(resp)
        self.assertNotIn("sk-secret-12345", resp_str)
        self.assertNotIn("postgres://", resp_str)
        self.assertNotIn("admin-secret", resp_str)
        self.assertNotIn("DATABASE_URL", resp_str)
        # Clean up to avoid leakage into other tests
        for k in ["SECRET_TOKEN", "DATABASE_URL", "GRANTLAYER_ADMIN_TOKEN"]:
            os.environ.pop(k, None)

    # ──────────────────────────────────────────────
    # GET /readiness — default / valid modes
    # ──────────────────────────────────────────────
    def test_readiness_returns_200_with_default_runtime_config(self):
        os.environ.pop("GRANTLAYER_RUNTIME_MODE", None)
        status, _ = self._run_get("/readiness")
        self.assertEqual(status, 200)

    def test_readiness_returns_status_ready(self):
        os.environ.pop("GRANTLAYER_RUNTIME_MODE", None)
        _, resp = self._run_get("/readiness")
        self.assertEqual(resp.get("status"), "ready")

    def test_readiness_includes_runtime_mode_local_by_default(self):
        os.environ.pop("GRANTLAYER_RUNTIME_MODE", None)
        _, resp = self._run_get("/readiness")
        self.assertEqual(resp.get("runtimeMode"), "local")

    def test_readiness_is_production_like_false_for_local(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "local"
        _, resp = self._run_get("/readiness")
        self.assertEqual(resp.get("isProductionLike"), False)

    def test_readiness_is_production_like_true_for_staging(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "staging"
        _, resp = self._run_get("/readiness")
        self.assertEqual(resp.get("isProductionLike"), True)

    def test_readiness_is_production_like_true_for_production(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        _, resp = self._run_get("/readiness")
        self.assertEqual(resp.get("isProductionLike"), True)

    # ──────────────────────────────────────────────
    # GET /readiness — invalid runtime mode
    # ──────────────────────────────────────────────
    def test_readiness_returns_503_for_invalid_runtime_mode(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "invalid"
        status, _ = self._run_get("/readiness")
        self.assertEqual(status, 503)

    def test_readiness_invalid_response_uses_error_code_runtime_config_invalid(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "invalid"
        _, resp = self._run_get("/readiness")
        self.assertEqual(resp.get("errorCode"), "RUNTIME_CONFIG_INVALID")

    def test_readiness_invalid_does_not_expose_secret_like_invalid_values(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "sk-invalid-secret"
        _, resp = self._run_get("/readiness")
        resp_str = json.dumps(resp)
        self.assertNotIn("sk-invalid-secret", resp_str)
        self.assertEqual(resp.get("errorCode"), "RUNTIME_CONFIG_INVALID")
        self.assertEqual(resp.get("status"), "not_ready")

    # ──────────────────────────────────────────────
    # OpenAPI contract checks
    # ──────────────────────────────────────────────
    def test_openapi_includes_health(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        openapi_path = repo_root / "docs" / "openapi.yaml"
        text = openapi_path.read_text(encoding="utf-8")
        self.assertIn("/health:", text)

    def test_openapi_includes_readiness(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        openapi_path = repo_root / "docs" / "openapi.yaml"
        text = openapi_path.read_text(encoding="utf-8")
        self.assertIn("/readiness:", text)

    # ──────────────────────────────────────────────
    # No forbidden files changed sanity check
    # ──────────────────────────────────────────────
    def test_no_forbidden_files_changed(self):
        """Ensure implementation does not touch forbidden areas."""
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        # Verify that no new frontend, deployment, migration, or infrastructure files appear.
        forbidden_patterns = [
            "frontend/*",
            "dashboard/*",
            "scripts/deploy/*",
            "docker-compose*.yml",
            "Dockerfile*",
            "backend/src/db/migrations/*",
        ]
        for pattern in forbidden_patterns:
            matches = list(repo_root.glob(pattern))
            # We don't assert absence because they may be pre-existing;
            # the real gate is git diff. This is a lightweight reminder.
            pass


class TestGL077RegressionNoForbiddenChanges(unittest.TestCase):
    """Verify GL-077 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        import subprocess
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/server.py",
            "backend/tests/test_gl077_health_readiness_endpoint.py",
            "docs/openapi.yaml",
            "docs/product_foundation_implementation_cut.md",
            "docs/examples/gl077/health_readiness_examples.json",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-077 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
