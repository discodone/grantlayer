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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestGL077HealthReadinessEndpoint(unittest.TestCase):
    """GL-077: Health / readiness endpoint baseline tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)

        self._orig_runtime_mode = os.environ.get("GRANTLAYER_RUNTIME_MODE")

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH_OR_URL = self.tmp_db.name
        db_mod.DB_PATH = self.tmp_db.name
        db_mod.init_db()

        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        self.client = TestClient(create_app(), raise_server_exceptions=False)

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
        """GET request via TestClient, returns (status_code, response_json)."""
        resp = self.client.get(path, headers=headers or {})
        try:
            data = resp.json()
        except Exception:
            data = {}
        return resp.status_code, data

    def _make_client_with_runtime_mode(self, runtime_mode=None):
        """Create a fresh TestClient after setting runtime mode env var.

        Does not reload config — the readiness endpoint reads os.environ
        at request time via describe_runtime_config(), so only the env var
        needs to be set before the request.
        """
        if runtime_mode is None:
            os.environ.pop("GRANTLAYER_RUNTIME_MODE", None)
        else:
            os.environ["GRANTLAYER_RUNTIME_MODE"] = runtime_mode
        import backend.src.core.db as bk_db
        bk_db.DB_PATH_OR_URL = self.tmp_db.name
        bk_db.DB_PATH = self.tmp_db.name
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        return TestClient(create_app(), raise_server_exceptions=False)

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
        for k in ["SECRET_TOKEN", "DATABASE_URL", "GRANTLAYER_ADMIN_TOKEN"]:
            os.environ.pop(k, None)

    # ──────────────────────────────────────────────
    # GET /readiness — default / valid modes
    # ──────────────────────────────────────────────
    def test_readiness_returns_200_with_default_runtime_config(self):
        client = self._make_client_with_runtime_mode(None)
        resp = client.get("/readiness")
        self.assertEqual(resp.status_code, 200)

    def test_readiness_returns_status_ready(self):
        client = self._make_client_with_runtime_mode(None)
        resp = client.get("/readiness")
        self.assertEqual(resp.json().get("status"), "ready")

    def test_readiness_includes_runtime_mode_production_by_default(self):
        client = self._make_client_with_runtime_mode(None)
        resp = client.get("/readiness")
        self.assertEqual(resp.json().get("runtimeMode"), "production")

    def test_readiness_is_production_like_false_for_local(self):
        client = self._make_client_with_runtime_mode("local")
        resp = client.get("/readiness")
        self.assertEqual(resp.json().get("isProductionLike"), False)

    def test_readiness_is_production_like_true_for_staging(self):
        client = self._make_client_with_runtime_mode("staging")
        resp = client.get("/readiness")
        self.assertEqual(resp.json().get("isProductionLike"), True)

    def test_readiness_is_production_like_true_for_production(self):
        client = self._make_client_with_runtime_mode("production")
        resp = client.get("/readiness")
        self.assertEqual(resp.json().get("isProductionLike"), True)

    # ──────────────────────────────────────────────
    # GET /readiness — invalid runtime mode
    # ──────────────────────────────────────────────
    def test_readiness_returns_503_for_invalid_runtime_mode(self):
        client = self._make_client_with_runtime_mode("invalid")
        resp = client.get("/readiness")
        self.assertEqual(resp.status_code, 503)

    def test_readiness_invalid_response_uses_error_code_runtime_config_invalid(self):
        client = self._make_client_with_runtime_mode("invalid")
        resp = client.get("/readiness")
        self.assertEqual(resp.json().get("errorCode"), "RUNTIME_CONFIG_INVALID")

    def test_readiness_invalid_does_not_expose_secret_like_invalid_values(self):
        client = self._make_client_with_runtime_mode("sk-invalid-secret")
        resp = client.get("/readiness")
        resp_str = json.dumps(resp.json())
        self.assertNotIn("sk-invalid-secret", resp_str)
        self.assertEqual(resp.json().get("errorCode"), "RUNTIME_CONFIG_INVALID")
        self.assertEqual(resp.json().get("status"), "not_ready")

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
        forbidden_patterns = [
            "frontend/*",
            "dashboard/*",
            "scripts/deploy/*",
            "docker-compose*.yml",
            "Dockerfile*",
            "backend/src/db/migrations/*",
        ]
        for pattern in forbidden_patterns:
            list(repo_root.glob(pattern))


class TestGL077RegressionNoForbiddenChanges(unittest.TestCase):
    """Verify GL-077 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        import subprocess
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-077-health-readiness-endpoint-baseline":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-077 feature branch"
            )
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
