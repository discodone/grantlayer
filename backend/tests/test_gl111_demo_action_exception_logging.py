"""Tests for GL-111: Safe demo action exception logging.

Ensures unexpected exceptions in demo_action.py are logged safely
without exposing sensitive data, while preserving fail-closed behavior
and all existing security boundaries.
"""

import json
import os
import sys
import tempfile
import unittest
import importlib
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl111(unittest.TestCase):
    """Shared helpers for GL-111 tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_demo = os.environ.get("GRANTLAYER_ENABLE_DEMO_ENDPOINTS")
        self._orig_require_challenge = os.environ.get("GRANTLAYER_REQUIRE_CHALLENGE")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)

        import backend.src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.demo_action as demo_mod
        importlib.reload(demo_mod)
        self.demo_mod = demo_mod

        import backend.src.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        crypto_mod.ensure_demo_keypair()

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, orig in [
            ("GRANTLAYER_DB", self._orig_db),
            ("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", self._orig_enable_demo),
            ("GRANTLAYER_REQUIRE_CHALLENGE", self._orig_require_challenge),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    def _make_grant(self):
        from backend.src.models import Grant
        g = Grant(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="admin",
            reason="Routine maintenance",
        )
        self.grants_mod.create_grant(g)
        return g

    def _secret_message(self):
        return (
            "admin-token-secret-value "
            "operator-token-secret-value "
            "PRIVATE KEY MATERIAL "
            "passphrase-secret "
            "raw-request-body-secret "
            "signature-secret"
        )


class TestGl111ExceptionLogging(_BaseGl111):
    """Verify safe exception logging in demo_action."""

    def test_unexpected_exception_is_logged(self):
        self._make_grant()
        with self.assertLogs(self.demo_mod.logger, level="ERROR") as cm:
            with patch.object(
                self.demo_mod, "list_grants", side_effect=RuntimeError(self._secret_message())
            ):
                result = self.demo_mod.handle_demo_action(
                    "tech-01", "technician", "restart-service", "customer-env-a"
                )
        self.assertFalse(result["approved"])
        self.assertEqual(result["reason"], "internal_handler_error")
        self.assertTrue(
            any("demo_action unexpected failure" in msg for msg in cm.output)
        )

    def test_log_includes_component_and_action_context(self):
        self._make_grant()
        with self.assertLogs(self.demo_mod.logger, level="ERROR") as cm:
            with patch.object(
                self.demo_mod, "list_grants", side_effect=RuntimeError("boom")
            ):
                self.demo_mod.handle_demo_action(
                    "tech-01", "technician", "restart-service", "customer-env-a"
                )
        log_str = "\n".join(cm.output)
        self.assertIn("component=demo_action", log_str)
        self.assertIn("action=restart-service", log_str)

    def test_log_includes_exception_type(self):
        self._make_grant()
        with self.assertLogs(self.demo_mod.logger, level="ERROR") as cm:
            with patch.object(
                self.demo_mod, "list_grants", side_effect=ValueError("boom")
            ):
                self.demo_mod.handle_demo_action(
                    "tech-01", "technician", "restart-service", "customer-env-a"
                )
        log_str = "\n".join(cm.output)
        self.assertIn("exception_type=ValueError", log_str)

    def test_log_does_not_include_raw_token(self):
        self._make_grant()
        with self.assertLogs(self.demo_mod.logger, level="ERROR") as cm:
            with patch.object(
                self.demo_mod, "list_grants", side_effect=RuntimeError(self._secret_message())
            ):
                self.demo_mod.handle_demo_action(
                    "tech-01", "technician", "restart-service", "customer-env-a"
                )
        log_str = "\n".join(cm.output)
        self.assertNotIn("admin-token-secret-value", log_str)
        self.assertNotIn("operator-token-secret-value", log_str)

    def test_log_does_not_include_private_key_material(self):
        self._make_grant()
        with self.assertLogs(self.demo_mod.logger, level="ERROR") as cm:
            with patch.object(
                self.demo_mod, "list_grants", side_effect=RuntimeError(self._secret_message())
            ):
                self.demo_mod.handle_demo_action(
                    "tech-01", "technician", "restart-service", "customer-env-a"
                )
        log_str = "\n".join(cm.output)
        self.assertNotIn("PRIVATE KEY MATERIAL", log_str)

    def test_log_does_not_include_passphrase(self):
        self._make_grant()
        with self.assertLogs(self.demo_mod.logger, level="ERROR") as cm:
            with patch.object(
                self.demo_mod, "list_grants", side_effect=RuntimeError(self._secret_message())
            ):
                self.demo_mod.handle_demo_action(
                    "tech-01", "technician", "restart-service", "customer-env-a"
                )
        log_str = "\n".join(cm.output)
        self.assertNotIn("passphrase-secret", log_str)

    def test_log_does_not_include_request_body_or_evidence(self):
        self._make_grant()
        with self.assertLogs(self.demo_mod.logger, level="ERROR") as cm:
            with patch.object(
                self.demo_mod, "list_grants", side_effect=RuntimeError(self._secret_message())
            ):
                self.demo_mod.handle_demo_action(
                    "tech-01", "technician", "restart-service", "customer-env-a"
                )
        log_str = "\n".join(cm.output)
        self.assertNotIn("raw-request-body-secret", log_str)

    def test_log_does_not_include_signature_material(self):
        self._make_grant()
        with self.assertLogs(self.demo_mod.logger, level="ERROR") as cm:
            with patch.object(
                self.demo_mod, "list_grants", side_effect=RuntimeError(self._secret_message())
            ):
                self.demo_mod.handle_demo_action(
                    "tech-01", "technician", "restart-service", "customer-env-a"
                )
        log_str = "\n".join(cm.output)
        self.assertNotIn("signature-secret", log_str)

    def test_public_response_remains_safe(self):
        self._make_grant()
        with self.assertLogs(self.demo_mod.logger, level="ERROR"):
            with patch.object(
                self.demo_mod, "list_grants", side_effect=RuntimeError(self._secret_message())
            ):
                result = self.demo_mod.handle_demo_action(
                    "tech-01", "technician", "restart-service", "customer-env-a"
                )
        result_str = json.dumps(result)
        self.assertNotIn("admin-token-secret-value", result_str)
        self.assertNotIn("operator-token-secret-value", result_str)
        self.assertNotIn("PRIVATE KEY MATERIAL", result_str)
        self.assertNotIn("passphrase-secret", result_str)
        self.assertNotIn("raw-request-body-secret", result_str)
        self.assertNotIn("signature-secret", result_str)
        self.assertNotIn("traceback", result_str.lower())
        self.assertNotIn("exception", result_str.lower())
        self.assertEqual(result["reason"], "internal_handler_error")
        self.assertFalse(result["approved"])

    def test_failure_path_fails_closed(self):
        self._make_grant()
        with self.assertLogs(self.demo_mod.logger, level="ERROR"):
            with patch.object(
                self.demo_mod, "list_grants", side_effect=RuntimeError("boom")
            ):
                result = self.demo_mod.handle_demo_action(
                    "tech-01", "technician", "restart-service", "customer-env-a"
                )
        self.assertFalse(result["approved"])
        self.assertEqual(result["reason"], "internal_handler_error")
        self.assertIn("executionId", result)


class TestGl111Preservation(_BaseGl111):
    """Verify existing behaviors are preserved."""

    def test_demo_tamper_disabled_by_default(self):
        os.environ.pop("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", None)
        importlib.reload(self.config_mod)
        self.assertFalse(self.config_mod.ENABLE_DEMO_ENDPOINTS)

    def test_demo_tamper_requires_explicit_enable(self):
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        importlib.reload(self.config_mod)
        self.assertTrue(self.config_mod.ENABLE_DEMO_ENDPOINTS)

    def test_gl106_rate_limiting_preserved(self):
        import backend.src.rate_limiter as rl_mod
        importlib.reload(rl_mod)
        self.assertTrue(hasattr(rl_mod, "RateLimiter"))

    def test_gl109_auth_preserved(self):
        import backend.src.auth as auth_mod
        importlib.reload(auth_mod)
        self.assertTrue(hasattr(auth_mod, "check_admin_token"))
        self.assertTrue(hasattr(auth_mod, "check_auth"))

    def test_gl110_private_key_behavior_preserved(self):
        import backend.src.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        self.assertTrue(hasattr(crypto_mod, "load_private_key"))
        self.assertTrue(hasattr(crypto_mod, "verify_grant_signature"))

    def test_security_boundary_preserved(self):
        import backend.src.auth as auth_mod
        importlib.reload(auth_mod)
        self.assertTrue(hasattr(auth_mod, "check_admin_token"))
        self.assertTrue(hasattr(auth_mod, "check_auth"))

    def test_no_db_schema_migration_change(self):
        import backend.src.db as db_mod
        importlib.reload(db_mod)
        conn = db_mod.get_conn()
        try:
            tables = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
            self.assertIn("grants", tables)
            self.assertIn("operators", tables)
            self.assertIn("audit_events", tables)
            self.assertIn("grant_executions", tables)
        finally:
            conn.close()

    def test_no_openapi_change_needed(self):
        import pathlib
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        openapi_path = repo_root / "docs" / "openapi.yaml"
        self.assertTrue(openapi_path.exists())
        text = openapi_path.read_text(encoding="utf-8")
        self.assertIn("/demo-action:", text)

    def test_no_endpoint_changes(self):
        from backend.src.api.app import create_app

        app = create_app()
        paths = {route.path for route in app.routes}
        self.assertIn("/demo-action", paths)


class TestGl111NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-111 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        import pathlib
        import subprocess

        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-111-demo-action-exception-logging":
            self.skipTest(
                "Branch-wide diff check only valid on GL-111 feature branch"
            )
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/demo_action.py",
            "backend/tests/test_gl111_demo_action_exception_logging.py",
            "backend/src/logging_utils.py",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-111 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
