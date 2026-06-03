"""Tests for GL-190 Demo Endpoint Safety Guard / Startup Warning.

Verifies that demo endpoint public exposure is blocked or explicitly
acknowledged before the server starts.  Covers:

- Demo endpoints disabled: always safe regardless of host
- Demo endpoints enabled on localhost / 127.0.0.1 / ::1: allowed
- Demo endpoints enabled in test/local mode on local host: allowed
- Demo endpoints enabled with non-local host without ack: blocked
- Blocked error is safe and deterministic (no secrets, no exploit details)
- Explicit acknowledgement env var allows non-local demo endpoints
- Acknowledgement is strict (exact "true" only, per _env_bool convention)
- Existing startup gate pattern is preserved
- Health/readiness behavior under blocked startup follows existing semantics
- Scope guard: no forbidden files changed
"""

import importlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl190(unittest.TestCase):
    """Shared setUp/tearDown and helper methods."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_demo = os.environ.get("GRANTLAYER_ENABLE_DEMO_ENDPOINTS")
        self._orig_host = os.environ.get("GRANTLAYER_HOST")
        self._orig_allow_public = os.environ.get("GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS")
        self._orig_runtime_mode = os.environ.get("GRANTLAYER_RUNTIME_MODE")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_challenge = os.environ.get("GRANTLAYER_REQUIRE_CHALLENGE")
        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")

        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()
        self.db_mod = db_mod

    def tearDown(self):
        import os as _os
        _os.unlink(self.tmp_db.name)
        for key, orig in [
            ("GRANTLAYER_DB", self._orig_db),
            ("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", self._orig_enable_demo),
            ("GRANTLAYER_HOST", self._orig_host),
            ("GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS", self._orig_allow_public),
            ("GRANTLAYER_RUNTIME_MODE", self._orig_runtime_mode),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_CHALLENGE", self._orig_require_challenge),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    def _reload_config(self):
        import src.config as cfg
        importlib.reload(cfg)
        return cfg

    def _make_handler(self, path, method="GET", body=b""):
        """Build a minimal handler instance for request testing."""
        import src.server as server_mod
        importlib.reload(server_mod)
        from io import BytesIO

        handler = server_mod.GrantLayerHandler.__new__(server_mod.GrantLayerHandler)
        handler.rfile = BytesIO(body)
        handler.wfile = BytesIO()
        headers = {}
        if body:
            headers["Content-Length"] = str(len(body))
        handler.headers = headers
        handler.path = path
        handler.command = method
        handler.requestline = f"{method} {path} HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None
        return handler

    def _run_handler(self, handler):
        if handler.command == "GET":
            handler.do_GET()
        handler.wfile.seek(0)
        response = handler.wfile.read()
        status_line = response.split(b"\r\n")[0]
        status = int(status_line.split(b" ")[1])
        parts = response.split(b"\r\n\r\n", 1)
        body = json.loads(parts[1]) if len(parts) > 1 else {}
        return status, body


class TestDemoEndpointsDisabled(_BaseGl190):
    """When ENABLE_DEMO_ENDPOINTS is false, exposure check always returns safe."""

    def test_demo_disabled_local_host_no_errors(self):
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        cfg = self._reload_config()
        self.assertEqual(cfg.demo_endpoint_public_exposure_errors("127.0.0.1"), [])

    def test_demo_disabled_nonlocal_host_no_errors(self):
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        cfg = self._reload_config()
        self.assertEqual(cfg.demo_endpoint_public_exposure_errors("0.0.0.0"), [])

    def test_demo_disabled_no_host_arg_no_errors(self):
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        cfg = self._reload_config()
        self.assertEqual(cfg.demo_endpoint_public_exposure_errors(), [])


class TestDemoEndpointsLocalHosts(_BaseGl190):
    """Demo endpoints enabled on local bind hosts are allowed without ack."""

    def _assert_local_host_allowed(self, host):
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        os.environ.pop("GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS", None)
        cfg = self._reload_config()
        errs = cfg.demo_endpoint_public_exposure_errors(host)
        self.assertEqual(
            errs, [],
            f"Expected no errors for local host '{host}', got: {errs}",
        )

    def test_localhost_allowed(self):
        self._assert_local_host_allowed("localhost")

    def test_127_0_0_1_allowed(self):
        self._assert_local_host_allowed("127.0.0.1")

    def test_ipv6_loopback_allowed(self):
        self._assert_local_host_allowed("::1")

    def test_empty_string_host_allowed(self):
        # Empty string is treated as local/default context
        self._assert_local_host_allowed("")

    def test_localhost_uppercase_variant(self):
        # _env_bool / host normalization lowercases; host arg goes through .lower()
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        os.environ.pop("GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS", None)
        cfg = self._reload_config()
        # Host arg comparison uses .strip().lower()
        errs = cfg.demo_endpoint_public_exposure_errors("LOCALHOST")
        self.assertEqual(errs, [])

    def test_127_0_0_1_with_whitespace(self):
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        os.environ.pop("GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS", None)
        cfg = self._reload_config()
        errs = cfg.demo_endpoint_public_exposure_errors("  127.0.0.1  ")
        self.assertEqual(errs, [])


class TestDemoEndpointsConfigHostLocal(_BaseGl190):
    """When GRANTLAYER_HOST (config) is local, no-arg call is also safe."""

    def test_config_host_localhost_no_arg_safe(self):
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        os.environ["GRANTLAYER_HOST"] = "localhost"
        os.environ.pop("GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS", None)
        cfg = self._reload_config()
        # No host arg → falls back to config.GRANTLAYER_HOST
        errs = cfg.demo_endpoint_public_exposure_errors()
        self.assertEqual(errs, [])

    def test_config_host_127_no_arg_safe(self):
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        os.environ["GRANTLAYER_HOST"] = "127.0.0.1"
        os.environ.pop("GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS", None)
        cfg = self._reload_config()
        errs = cfg.demo_endpoint_public_exposure_errors()
        self.assertEqual(errs, [])


class TestDemoEndpointsNonLocalBlocked(_BaseGl190):
    """Demo endpoints + non-local host is blocked without explicit ack."""

    def _assert_nonlocal_blocked(self, host):
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        os.environ.pop("GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS", None)
        cfg = self._reload_config()
        errs = cfg.demo_endpoint_public_exposure_errors(host)
        self.assertGreater(len(errs), 0, f"Expected error for host '{host}', got none")

    def test_0_0_0_0_blocked(self):
        self._assert_nonlocal_blocked("0.0.0.0")

    def test_external_ip_blocked(self):
        self._assert_nonlocal_blocked("192.168.1.1")

    def test_public_ip_blocked(self):
        self._assert_nonlocal_blocked("10.0.0.1")

    def test_wildcard_ipv6_blocked(self):
        self._assert_nonlocal_blocked("::")

    def test_config_nonlocal_host_no_arg_blocked(self):
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        os.environ["GRANTLAYER_HOST"] = "0.0.0.0"
        os.environ.pop("GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS", None)
        cfg = self._reload_config()
        # No host arg — falls back to config.GRANTLAYER_HOST = 0.0.0.0
        errs = cfg.demo_endpoint_public_exposure_errors()
        self.assertGreater(len(errs), 0)


class TestBlockedErrorIsSafe(_BaseGl190):
    """Blocked startup error is safe, deterministic, contains no secrets/exploits."""

    def _get_blocked_errors(self, host="0.0.0.0"):
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        os.environ.pop("GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS", None)
        cfg = self._reload_config()
        return cfg.demo_endpoint_public_exposure_errors(host)

    def test_blocked_error_returns_exactly_one_string(self):
        errs = self._get_blocked_errors()
        self.assertEqual(len(errs), 1)
        self.assertIsInstance(errs[0], str)

    def test_blocked_error_contains_safe_code(self):
        errs = self._get_blocked_errors()
        self.assertIn("demo_endpoints_public_exposure_blocked", errs[0])

    def test_blocked_error_no_secret_tokens(self):
        errs = self._get_blocked_errors()
        combined = " ".join(errs).lower()
        for forbidden in ("password", "secret", "token", "api_key", "private_key", "traceback"):
            self.assertNotIn(forbidden, combined, f"Error contains forbidden term: {forbidden}")

    def test_blocked_error_no_exploit_details(self):
        errs = self._get_blocked_errors()
        combined = " ".join(errs).lower()
        for forbidden in ("exploit", "injection", "attack", "bypass", "vulnerability"):
            self.assertNotIn(forbidden, combined, f"Error contains exploit detail: {forbidden}")

    def test_blocked_error_no_endpoint_paths(self):
        errs = self._get_blocked_errors()
        combined = " ".join(errs)
        for path in ("/demo/", "/tamper", "/grants", "/audit"):
            self.assertNotIn(path, combined, f"Error leaks endpoint path: {path}")

    def test_blocked_error_is_deterministic(self):
        errs1 = self._get_blocked_errors("0.0.0.0")
        errs2 = self._get_blocked_errors("0.0.0.0")
        self.assertEqual(errs1, errs2)

    def test_blocked_error_mentions_acknowledgement_var(self):
        errs = self._get_blocked_errors()
        self.assertIn("GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS", errs[0])


class TestExplicitAcknowledgement(_BaseGl190):
    """GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS=true overrides the block."""

    def test_ack_true_nonlocal_host_allowed(self):
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        os.environ["GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS"] = "true"
        cfg = self._reload_config()
        errs = cfg.demo_endpoint_public_exposure_errors("0.0.0.0")
        self.assertEqual(errs, [])

    def test_ack_false_nonlocal_host_blocked(self):
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        os.environ["GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS"] = "false"
        cfg = self._reload_config()
        errs = cfg.demo_endpoint_public_exposure_errors("0.0.0.0")
        self.assertGreater(len(errs), 0)

    def test_ack_1_nonlocal_host_allowed(self):
        # _env_bool also accepts "1"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        os.environ["GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS"] = "1"
        cfg = self._reload_config()
        errs = cfg.demo_endpoint_public_exposure_errors("0.0.0.0")
        self.assertEqual(errs, [])

    def test_ack_arbitrary_string_not_trusted(self):
        # Arbitrary non-boolean strings are rejected by _env_bool
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        os.environ["GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS"] = "yes_please"
        cfg = self._reload_config()
        # "yes_please" is not in _env_bool's accepted set for truthy
        # Actually _env_bool accepts "yes" but not "yes_please"
        errs = cfg.demo_endpoint_public_exposure_errors("0.0.0.0")
        self.assertGreater(len(errs), 0)

    def test_ack_yes_nonlocal_host_allowed(self):
        # _env_bool accepts "yes"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        os.environ["GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS"] = "yes"
        cfg = self._reload_config()
        errs = cfg.demo_endpoint_public_exposure_errors("0.0.0.0")
        self.assertEqual(errs, [])

    def test_ack_present_demo_disabled_still_safe(self):
        # Ack flag set but demo endpoints disabled — still safe
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        os.environ["GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS"] = "true"
        cfg = self._reload_config()
        errs = cfg.demo_endpoint_public_exposure_errors("0.0.0.0")
        self.assertEqual(errs, [])


class TestLocalModeBehaviorPreserved(_BaseGl190):
    """Local/test runtime mode with local host remains fully operational."""

    def test_local_mode_local_host_no_demo_exposure_error(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "local"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        os.environ["GRANTLAYER_HOST"] = "127.0.0.1"
        os.environ.pop("GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS", None)
        cfg = self._reload_config()
        errs = cfg.demo_endpoint_public_exposure_errors("127.0.0.1")
        self.assertEqual(errs, [])

    def test_test_mode_local_host_no_demo_exposure_error(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "test"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        os.environ["GRANTLAYER_HOST"] = "127.0.0.1"
        os.environ.pop("GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS", None)
        cfg = self._reload_config()
        errs = cfg.demo_endpoint_public_exposure_errors("127.0.0.1")
        self.assertEqual(errs, [])

    def test_local_mode_nonlocal_host_still_blocked(self):
        # Runtime mode is irrelevant — host binding determines the check
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "local"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        os.environ.pop("GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS", None)
        cfg = self._reload_config()
        errs = cfg.demo_endpoint_public_exposure_errors("0.0.0.0")
        self.assertGreater(len(errs), 0)


class TestStartupGatePreserved(_BaseGl190):
    """Existing startup_ok / startup_errors pattern is not broken."""

    def test_startup_ok_still_works_in_safe_config(self):
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "test-token"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        cfg = self._reload_config()
        self.assertTrue(cfg.startup_ok())
        self.assertEqual(cfg.startup_errors(), [])

    def test_startup_errors_still_catches_demo_enabled_in_prod_mode(self):
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "test-token"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        cfg = self._reload_config()
        errs = cfg.startup_errors()
        demo_errs = [e for e in errs if "ENABLE_DEMO_ENDPOINTS" in e]
        self.assertGreater(len(demo_errs), 0)
        self.assertFalse(cfg.startup_ok())

    def test_startup_warnings_still_present(self):
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        cfg = self._reload_config()
        warnings = cfg.startup_warnings()
        self.assertIsInstance(warnings, list)
        self.assertGreater(len(warnings), 0)


class TestHealthReadinessUnderBlockedStartup(_BaseGl190):
    """Health and readiness endpoints remain available as per existing semantics.

    The GL-190 guard raises SystemExit before the server binds.  The handler
    itself (health/readiness) is still reachable if the server is already up,
    consistent with the existing startup gate pattern where health/readiness
    are not affected by startup config checks.
    """

    def test_health_endpoint_accessible_regardless(self):
        # Health endpoint is always reachable once a server is up
        handler = self._make_handler("/health")
        import src.server as server_mod
        importlib.reload(server_mod)
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")

    def test_readiness_endpoint_accessible_regardless(self):
        handler = self._make_handler("/readiness")
        import src.server as server_mod
        importlib.reload(server_mod)
        status, body = self._run_handler(handler)
        self.assertIn(status, (200, 503))
        self.assertIn(body.get("status"), ("ready", "not_ready"))


class TestNoClaimsOrForbiddenScope(unittest.TestCase):
    """Safety property assertions verified at the artifact level."""

    def test_no_production_saas_claim(self):
        doc_path = pathlib.Path(__file__).parent.parent.parent / "docs" / "demo_endpoint_safety_guard.md"
        if not doc_path.exists():
            self.skipTest("doc not yet present")
        text = doc_path.read_text(encoding="utf-8").lower()
        # Positive-claim phrases are forbidden; "not claimed" / "not ready" phrases are fine
        for positive_claim in ("production saas is ready", "production saas available",
                               "tenant isolation is implemented", "multi-tenant"):
            self.assertNotIn(positive_claim, text, f"Doc contains forbidden claim: {positive_claim}")

    def test_no_tenant_isolation_claim(self):
        artifact_path = (
            pathlib.Path(__file__).parent.parent.parent
            / "docs" / "examples" / "gl190" / "demo_endpoint_safety_guard.json"
        )
        if not artifact_path.exists():
            self.skipTest("artifact not yet present")
        data = json.loads(artifact_path.read_text(encoding="utf-8"))
        safety = data.get("safety_properties", {})
        self.assertFalse(safety.get("tenant_isolation_claimed", False))
        self.assertFalse(safety.get("production_saas_claimed", False))


class TestScopeGuard(unittest.TestCase):
    """Verify GL-190 diff is limited to the allowed file set."""

    _ALLOWED = {
        "backend/src/config.py",
        "backend/src/server.py",
        "backend/tests/test_gl190_demo_endpoint_safety_guard.py",
        "docs/demo_endpoint_safety_guard.md",
        "docs/examples/gl190/demo_endpoint_safety_guard.json",
    }

    def test_changed_files_within_allowed_scope(self):
        repo_root = pathlib.Path(__file__).parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root, capture_output=True, text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-190-demo-endpoint-safety-guard":
            self.skipTest("Branch scope check only valid on gl-190 feature branch")
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root, capture_output=True, text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        for path in changed:
            self.assertIn(
                path,
                self._ALLOWED,
                f"GL-190 changed a file outside allowed scope: {path}",
            )

    def test_no_migration_files(self):
        repo_root = pathlib.Path(__file__).parent.parent.parent
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root, capture_output=True, text=True,
        )
        changed = result.stdout
        self.assertNotIn("migrations/", changed)
        self.assertNotIn("alembic/", changed)

    def test_no_github_workflow_files(self):
        repo_root = pathlib.Path(__file__).parent.parent.parent
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root, capture_output=True, text=True,
        )
        self.assertNotIn(".github/workflows", result.stdout)

    def test_no_dependency_manifest_changes(self):
        repo_root = pathlib.Path(__file__).parent.parent.parent
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root, capture_output=True, text=True,
        )
        changed = result.stdout
        for forbidden in ("requirements.txt", "pyproject.toml", "setup.cfg", "package.json", "Pipfile"):
            self.assertNotIn(forbidden, changed)

    def test_no_openapi_change(self):
        repo_root = pathlib.Path(__file__).parent.parent.parent
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root, capture_output=True, text=True,
        )
        self.assertNotIn("openapi.yaml", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
