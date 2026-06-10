"""Tests for GL-089 Auth Default / Production Fail-Closed Startup Gate.

Ensures:
- Auth protection defaults are secure in non-local / production-like modes.
- Missing admin token is detected as unsafe.
- startup_ok() and startup_errors() return correct results.
- Non-local / production-like unsafe startup is blocked.
- Failure messages are safe and deterministic.
- Explicit local/test mode remains possible.
- Prior GL protections remain intact.
"""

import json
import os
import pathlib
import subprocess
import tempfile
import unittest
import importlib


class _BaseGl089(unittest.TestCase):
    """Shared helpers for GL-089 tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_require_challenge = os.environ.get("GRANTLAYER_REQUIRE_CHALLENGE")
        self._orig_enable_demo = os.environ.get("GRANTLAYER_ENABLE_DEMO_ENDPOINTS")
        self._orig_runtime_mode = os.environ.get("GRANTLAYER_RUNTIME_MODE")

        import backend.src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        import backend.src.server as server_mod
        importlib.reload(server_mod)
        self.server_mod = server_mod

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, orig in [
            ("GRANTLAYER_DB", self._orig_db),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_REQUIRE_CHALLENGE", self._orig_require_challenge),
            ("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", self._orig_enable_demo),
            ("GRANTLAYER_RUNTIME_MODE", self._orig_runtime_mode),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    def _reload_config(self):
        importlib.reload(self.config_mod)

    def _run_handler(self, path, method="GET", auth_header=None, body=b""):
        """Make an HTTP request via FastAPI TestClient."""
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        import backend.src.db as bk_db
        bk_db.DB_PATH_OR_URL = self.tmp_db.name
        bk_db.DB_PATH = self.tmp_db.name
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        client = TestClient(create_app(), raise_server_exceptions=False)
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if method == "GET":
            resp = client.get(path, headers=headers)
        else:
            resp = client.post(path, content=body, headers=headers)
        try:
            body_out = resp.json()
        except Exception:
            body_out = {}
        return resp.status_code, body_out


class TestGl089ConfigDefaults(_BaseGl089):
    """Verify secure defaults for REQUIRE_ADMIN_TOKEN based on runtime mode."""

    def test_require_admin_token_defaults_true_in_production(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        self._reload_config()
        self.assertTrue(self.config_mod.REQUIRE_ADMIN_TOKEN)

    def test_require_admin_token_defaults_true_in_staging(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "staging"
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        self._reload_config()
        self.assertTrue(self.config_mod.REQUIRE_ADMIN_TOKEN)

    def test_require_admin_token_defaults_true_in_demo(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "demo"
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        self._reload_config()
        self.assertTrue(self.config_mod.REQUIRE_ADMIN_TOKEN)

    def test_require_admin_token_defaults_false_in_local(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "local"
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        self._reload_config()
        self.assertFalse(self.config_mod.REQUIRE_ADMIN_TOKEN)

    def test_require_admin_token_defaults_false_in_test(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "test"
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        self._reload_config()
        self.assertFalse(self.config_mod.REQUIRE_ADMIN_TOKEN)

    def test_require_admin_token_explicit_false_overrides_production(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        self._reload_config()
        self.assertFalse(self.config_mod.REQUIRE_ADMIN_TOKEN)

    def test_require_admin_token_explicit_true_overrides_local(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "local"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        self._reload_config()
        self.assertTrue(self.config_mod.REQUIRE_ADMIN_TOKEN)


class TestGl089StartupOkAndErrors(_BaseGl089):
    """Validate startup_ok() and startup_errors() behavior."""

    def test_startup_ok_true_when_all_safe(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "super-secret-token"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        self._reload_config()
        self.assertTrue(self.config_mod.startup_ok())
        self.assertEqual(self.config_mod.startup_errors(), [])

    def test_startup_ok_false_when_require_admin_missing(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "token"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        self._reload_config()
        self.assertFalse(self.config_mod.startup_ok())
        errs = self.config_mod.startup_errors()
        self.assertTrue(any("GRANTLAYER_REQUIRE_ADMIN_TOKEN" in e for e in errs))

    def test_startup_ok_false_when_admin_token_missing(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        self._reload_config()
        self.assertFalse(self.config_mod.startup_ok())
        errs = self.config_mod.startup_errors()
        self.assertTrue(any("GRANTLAYER_ADMIN_TOKEN" in e for e in errs))

    def test_startup_ok_false_when_require_challenge_missing(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "token"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "false"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        self._reload_config()
        self.assertFalse(self.config_mod.startup_ok())
        errs = self.config_mod.startup_errors()
        self.assertTrue(any("GRANTLAYER_REQUIRE_CHALLENGE" in e for e in errs))

    def test_startup_ok_false_when_demo_endpoints_enabled(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "token"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        self._reload_config()
        self.assertFalse(self.config_mod.startup_ok())
        errs = self.config_mod.startup_errors()
        self.assertTrue(any("GRANTLAYER_ENABLE_DEMO_ENDPOINTS" in e for e in errs))

    def test_startup_errors_safe_no_secret_exposure(self):
        # GL-201: token must be >= 16 chars and not a placeholder to avoid triggering
        # the new placeholder/length check. The test verifies the raw VALUE never appears.
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "gl089-must-not-appear-in-errors"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        self._reload_config()
        errs = "\n".join(self.config_mod.startup_errors())
        # The raw secret VALUE must never appear in error output
        self.assertNotIn("gl089-must-not-appear-in-errors", errs)

    def test_startup_errors_deterministic(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "staging"
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_CHALLENGE", None)
        os.environ.pop("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", None)
        self._reload_config()
        errs1 = self.config_mod.startup_errors()
        errs2 = self.config_mod.startup_errors()
        self.assertEqual(errs1, errs2)


class TestGl089StartupGate(_BaseGl089):
    """Verify startup gate blocks unsafe non-local configurations."""

    def test_run_raises_system_exit_in_production_unsafe(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_CHALLENGE", None)
        os.environ.pop("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", None)
        self._reload_config()
        # reload server_mod to pick up new startup behavior
        importlib.reload(self.server_mod)
        with self.assertRaises(SystemExit) as ctx:
            self.server_mod.run(host="127.0.0.1", port=0)
        self.assertEqual(ctx.exception.code, 1)

    def test_run_raises_system_exit_in_staging_unsafe(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "staging"
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_CHALLENGE", None)
        os.environ.pop("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", None)
        self._reload_config()
        importlib.reload(self.server_mod)
        with self.assertRaises(SystemExit) as ctx:
            self.server_mod.run(host="127.0.0.1", port=0)
        self.assertEqual(ctx.exception.code, 1)

    def test_run_does_not_exit_in_local_unsafe(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "local"
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_CHALLENGE", None)
        os.environ.pop("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", None)
        self._reload_config()
        importlib.reload(self.server_mod)
        # run() will try to serve_forever; call it in a thread with a timeout
        import threading
        exc = None
        def _run():
            nonlocal exc
            try:
                self.server_mod.run(host="127.0.0.1", port=0)
            except SystemExit as e:
                exc = e
            except OSError:
                # port 0 may behave differently; expected
                pass
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=1.0)
        if isinstance(exc, SystemExit):
            self.fail("Local unsafe startup should NOT raise SystemExit")

    def test_run_does_not_exit_in_test_unsafe(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "test"
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_CHALLENGE", None)
        os.environ.pop("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", None)
        self._reload_config()
        importlib.reload(self.server_mod)
        import threading
        exc = None
        def _run():
            nonlocal exc
            try:
                self.server_mod.run(host="127.0.0.1", port=0)
            except SystemExit as e:
                exc = e
            except OSError:
                pass
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=1.0)
        if isinstance(exc, SystemExit):
            self.fail("Test unsafe startup should NOT raise SystemExit")

    def test_run_succeeds_in_production_safe(self):
        # GL-201: token must be >= 16 chars and not a known placeholder
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "gl089-safe-production-token-xyz"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        self._reload_config()
        importlib.reload(self.server_mod)
        import threading
        exc = None
        def _run():
            nonlocal exc
            try:
                self.server_mod.run(host="127.0.0.1", port=0)
            except SystemExit as e:
                exc = e
            except OSError:
                pass
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=1.0)
        if isinstance(exc, SystemExit):
            self.fail("Safe production startup should NOT raise SystemExit")


class TestGl089LegacyEndpointProtections(_BaseGl089):
    """Ensure protected endpoints do not become open because admin token is absent."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = ""
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        self._reload_config()
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server

    def test_get_grants_requires_auth_even_if_admin_token_unset(self):
        status, body = self._run_handler("/grants")
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "admin_token_required")

    def test_post_challenges_requires_auth_even_if_admin_token_unset(self):
        body_data = json.dumps({"subjectId": "sub-1", "action": "read", "resource": "repo-a"}).encode()
        status, body = self._run_handler("/challenges", method="POST", body=body_data)
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "admin_token_required")

    def test_get_audit_events_requires_auth_even_if_admin_token_unset(self):
        status, body = self._run_handler("/audit-events")
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "admin_token_required")

    def test_post_demo_action_requires_auth_even_if_admin_token_unset(self):
        body_data = json.dumps({"subjectId": "sub-1", "role": "eng", "action": "read", "resource": "repo-a"}).encode()
        status, body = self._run_handler("/demo-action", method="POST", body=body_data)
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "admin_token_required")

    def test_health_remains_public(self):
        status, body = self._run_handler("/health")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")

    def test_readiness_remains_public(self):
        status, body = self._run_handler("/readiness")
        self.assertIn(status, (200, 503))


class TestGl089LocalExplicitBehavior(_BaseGl089):
    """Verify explicit local/test unsafe mode is still permitted."""

    def test_local_unsafe_startup_does_not_block(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "local"
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_CHALLENGE", None)
        os.environ.pop("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", None)
        self._reload_config()
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.assertTrue(self.config_mod.RUNTIME_MODE in ("local", "test"))
        self.assertFalse(self.config_mod.startup_ok())
        # Since local mode, server run() should not call SystemExit.
        import threading
        exc = None
        def _run():
            nonlocal exc
            try:
                self.server_mod.run(host="127.0.0.1", port=0)
            except SystemExit as e:
                exc = e
            except OSError:
                pass
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=1.0)
        if isinstance(exc, SystemExit):
            self.fail("Explicit local unsafe startup should be allowed")


class TestGl089NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-089 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-089-auth-default-fail-closed-startup":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-089 feature branch"
            )
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/config.py",
            "backend/src/server.py",
            "backend/tests/test_gl089_auth_default_fail_closed.py",
            "docs/openapi.yaml",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-089 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
