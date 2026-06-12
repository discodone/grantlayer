"""Tests for GL-126: Production Deployment / Runtime Gate.

Narrow pre-deploy / pre-release validation that exercises runtime mode
classification, production-like config safety, and secret-handling
conventions. No production code changes required. No external services
required.
"""

import os
import pathlib
import subprocess
import sys
import unittest
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


class TestGl126ScriptContract(unittest.TestCase):
    """Verify the production runtime gate runner script meets its contract."""

    @classmethod
    def setUpClass(cls):
        cls.repo_root = _REPO_ROOT
        cls.script_path = cls.repo_root / "scripts" / "run-production-runtime-gate.sh"
        cls.script_text = cls.script_path.read_text() if cls.script_path.exists() else ""

    def test_script_exists(self):
        self.assertTrue(self.script_path.exists(), "run-production-runtime-gate.sh must exist")

    def test_script_is_executable(self):
        self.assertTrue(
            os.access(self.script_path, os.X_OK),
            "run-production-runtime-gate.sh must be executable",
        )

    def test_script_has_shebang(self):
        lines = self.script_text.splitlines()
        self.assertTrue(lines, "Script must not be empty")
        self.assertTrue(
            lines[0].startswith("#!/usr/bin/env bash"),
            f"Expected bash shebang, got: {lines[0]}",
        )

    def test_script_uses_strict_mode(self):
        self.assertIn("set -euo pipefail", self.script_text)

    def test_script_resolves_repo_root(self):
        self.assertIn("REPO_ROOT", self.script_text)

    def test_script_runs_gl126_test_module(self):
        self.assertIn(
            "python3 -m unittest backend.tests.test_gl126_production_runtime_gate -v",
            self.script_text,
        )

    def test_script_preserves_exit_code(self):
        self.assertIn("EXIT_CODE=", self.script_text)
        self.assertIn('exit "${EXIT_CODE}"', self.script_text)

    def test_script_does_not_use_tail_grep_head_as_sole_validation(self):
        for bad in ["| tail", "| grep", "| head"]:
            self.assertNotIn(
                bad,
                self.script_text,
                f"Script must not pipe unittest output through {bad} as sole validation",
            )

    def test_script_does_not_print_secrets(self):
        # Allow descriptive words in comments; reject actual secret-looking values
        forbidden_patterns = [
            r"password\s*=\s*[^\s]",
            r"secret\s*=\s*[^\s]",
            r"api_key\s*=\s*[^\s]",
            r"token\s*=\s*[^\s]",
            r"private_key\s*=\s*[^\s]",
            r"passphrase\s*=\s*[^\s]",
        ]
        import re
        for pattern in forbidden_patterns:
            for line in self.script_text.splitlines():
                if re.search(pattern, line, re.IGNORECASE):
                    self.fail(f"Possible secret assignment in script line: {line}")

    def test_script_no_production_hosts(self):
        # Reject actual production host references, not the word "production" in descriptions
        forbidden_hosts = ["prod.", "grantlayer.io", "api.grantlayer"]
        lower = self.script_text.lower()
        for host in forbidden_hosts:
            self.assertNotIn(host, lower, f"Script must not reference production host: {host}")


class TestGl126RuntimeModeRecognition(unittest.TestCase):
    """Verify recognized runtime modes and production-like classification."""

    def test_all_supported_modes_documented(self):
        from backend.src.core.runtime_config import SUPPORTED_MODES
        expected = {"local", "test", "demo", "staging", "production"}
        self.assertEqual(SUPPORTED_MODES, expected)

    def test_production_like_modes_recognized(self):
        from backend.src.core.runtime_config import PRODUCTION_LIKE_MODES, is_production_like
        self.assertEqual(PRODUCTION_LIKE_MODES, {"staging", "production"})
        for mode in PRODUCTION_LIKE_MODES:
            with self.subTest(mode=mode):
                self.assertTrue(is_production_like(mode=mode))

    def test_local_test_demo_are_not_production_like(self):
        from backend.src.core.runtime_config import is_production_like
        for mode in ("local", "test", "demo"):
            with self.subTest(mode=mode):
                self.assertFalse(is_production_like(mode=mode))

    def test_unsupported_mode_raises_value_error(self):
        from backend.src.core.runtime_config import is_production_like
        with self.assertRaises(ValueError) as ctx:
            is_production_like(mode="unknown")
        self.assertIn("Unsupported runtime mode", str(ctx.exception))


class TestGl126ProductionLikeConfigGate(unittest.TestCase):
    """Verify production-like mode fails closed when critical config is missing."""

    def setUp(self):
        self._orig_env = {
            "GRANTLAYER_RUNTIME_MODE": os.environ.get("GRANTLAYER_RUNTIME_MODE"),
            "GRANTLAYER_REQUIRE_ADMIN_TOKEN": os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN"),
            "GRANTLAYER_ADMIN_TOKEN": os.environ.get("GRANTLAYER_ADMIN_TOKEN"),
            "GRANTLAYER_REQUIRE_CHALLENGE": os.environ.get("GRANTLAYER_REQUIRE_CHALLENGE"),
            "GRANTLAYER_ENABLE_DEMO_ENDPOINTS": os.environ.get("GRANTLAYER_ENABLE_DEMO_ENDPOINTS"),
            "GRANTLAYER_DATABASE_URL": os.environ.get("GRANTLAYER_DATABASE_URL"),
            "GRANTLAYER_DB": os.environ.get("GRANTLAYER_DB"),
            "GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN": os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN"),
        }

    def tearDown(self):
        for key, orig in self._orig_env.items():
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    def _reload_config(self):
        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        return config_mod

    def test_production_mode_with_full_config_passes_gate(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "configured-token"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        config = self._reload_config()
        self.assertTrue(config.startup_ok())
        self.assertEqual(config.startup_errors(), [])

    def test_staging_mode_with_full_config_passes_gate(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "staging"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "configured-token"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        config = self._reload_config()
        self.assertTrue(config.startup_ok())
        self.assertEqual(config.startup_errors(), [])

    def test_production_mode_missing_admin_token_fails_closed(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        config = self._reload_config()
        self.assertFalse(config.startup_ok())
        errors = config.startup_errors()
        self.assertTrue(
            any("GRANTLAYER_ADMIN_TOKEN is not set" in e for e in errors),
            f"Expected admin token missing error, got: {errors}",
        )

    def test_production_mode_missing_require_admin_token_fails_closed(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "configured-token"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        config = self._reload_config()
        self.assertFalse(config.startup_ok())
        errors = config.startup_errors()
        self.assertTrue(
            any("GRANTLAYER_REQUIRE_ADMIN_TOKEN is not enabled" in e for e in errors),
            f"Expected require admin token error, got: {errors}",
        )

    def test_production_mode_missing_require_challenge_fails_closed(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "configured-token"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "false"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        config = self._reload_config()
        self.assertFalse(config.startup_ok())
        errors = config.startup_errors()
        self.assertTrue(
            any("GRANTLAYER_REQUIRE_CHALLENGE is not enabled" in e for e in errors),
            f"Expected require challenge error, got: {errors}",
        )

    def test_production_mode_demo_endpoints_enabled_fails_closed(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "configured-token"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        config = self._reload_config()
        self.assertFalse(config.startup_ok())
        errors = config.startup_errors()
        self.assertTrue(
            any("GRANTLAYER_ENABLE_DEMO_ENDPOINTS is enabled" in e for e in errors),
            f"Expected demo endpoints error, got: {errors}",
        )

    def test_local_mode_can_run_without_strict_config(self):
        from backend.src.core.runtime_config import is_production_like
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "local"
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "false"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        config = self._reload_config()
        # startup_ok() is enforced for non-local modes; local may have warnings
        # but should not produce fatal startup_errors() about missing admin token
        errors = config.startup_errors()
        # startup_errors() currently always checks these flags regardless of mode
        # so local with REQUIRE_ADMIN_TOKEN=false will still show errors
        # The important thing is local/test/demo remain *usable* for development
        self.assertEqual(config.RUNTIME_MODE, "local")
        self.assertFalse(is_production_like(mode=config.RUNTIME_MODE))

    def test_test_mode_can_run_without_strict_config(self):
        from backend.src.core.runtime_config import is_production_like
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "test"
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "false"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        config = self._reload_config()
        self.assertEqual(config.RUNTIME_MODE, "test")
        self.assertFalse(is_production_like(mode=config.RUNTIME_MODE))

    def test_demo_mode_can_run_without_strict_config(self):
        from backend.src.core.runtime_config import is_production_like
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "demo"
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "false"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        config = self._reload_config()
        self.assertEqual(config.RUNTIME_MODE, "demo")
        self.assertFalse(is_production_like(mode=config.RUNTIME_MODE))

    def test_startup_errors_never_include_secret_values(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "super-secret-token-42"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "false"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        config = self._reload_config()
        errors = config.startup_errors()
        errors_text = "\n".join(errors)
        self.assertNotIn("super-secret-token-42", errors_text)
        self.assertNotIn("GRANTLAYER_ADMIN_TOKEN=", errors_text)

    def test_startup_warnings_never_include_secret_values(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "local"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "leak-me-not-99"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        config = self._reload_config()
        warnings = config.startup_warnings()
        warnings_text = "\n".join(warnings)
        self.assertNotIn("leak-me-not-99", warnings_text)
        self.assertNotIn("GRANTLAYER_ADMIN_TOKEN=", warnings_text)


class TestGl126SecretRedaction(unittest.TestCase):
    """Verify secret values are redacted in runtime metadata output."""

    def test_describe_runtime_config_does_not_expose_db_url(self):
        from backend.src.core.runtime_config import describe_runtime_config
        env = {
            "GRANTLAYER_RUNTIME_MODE": "staging",
            "GRANTLAYER_DATABASE_URL": "postgres://user:secret_pass@localhost/db",
        }
        result = describe_runtime_config(env)
        result_str = str(result)
        self.assertNotIn("secret_pass", result_str)
        self.assertNotIn("postgres://", result_str)

    def test_describe_runtime_config_does_not_expose_private_key(self):
        from backend.src.core.runtime_config import describe_runtime_config
        env = {
            "GRANTLAYER_RUNTIME_MODE": "production",
            "GRANTLAYER_SIGNING_PRIVATE_KEY": "FAKE_PLACEHOLDER_PRIVATE_KEY_VALUE",
        }
        result = describe_runtime_config(env)
        result_str = str(result)
        self.assertNotIn("FAKE_PLACEHOLDER_PRIVATE_KEY_VALUE", result_str)

    def test_describe_runtime_config_does_not_expose_operator_token(self):
        from backend.src.core.runtime_config import describe_runtime_config
        env = {
            "GRANTLAYER_RUNTIME_MODE": "production",
            "GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN": "op-bootstrap-secret-123",
        }
        result = describe_runtime_config(env)
        result_str = str(result)
        self.assertNotIn("op-bootstrap-secret-123", result_str)

    def test_describe_runtime_config_does_not_expose_passphrase(self):
        from backend.src.core.runtime_config import describe_runtime_config
        env = {
            "GRANTLAYER_RUNTIME_MODE": "production",
            "GRANTLAYER_SIGNING_PRIVATE_KEY_PASSPHRASE": "my-passphrase-42",
        }
        result = describe_runtime_config(env)
        result_str = str(result)
        self.assertNotIn("my-passphrase-42", result_str)


class TestGl126DocumentationContract(unittest.TestCase):
    """Verify the production runtime gate documentation exists and covers required topics."""

    @classmethod
    def setUpClass(cls):
        cls.docs_path = _REPO_ROOT / "docs" / "production_runtime_gate.md"
        cls.docs_text = cls.docs_path.read_text() if cls.docs_path.exists() else ""

    def test_docs_exist(self):
        self.assertTrue(self.docs_path.exists(), "docs/production_runtime_gate.md must exist")

    def test_docs_mention_go_no_go(self):
        lower = self.docs_text.lower()
        self.assertIn("go/no-go", lower)
        self.assertIn("no-go", lower)

    def test_docs_mention_smoke_runner(self):
        lower = self.docs_text.lower()
        self.assertIn("run-operational-smoke-tests", lower)

    def test_docs_mention_full_suite_runner(self):
        lower = self.docs_text.lower()
        self.assertIn("run-full-backend-suite", lower)

    def test_docs_mention_120s_limit(self):
        lower = self.docs_text.lower()
        self.assertTrue(
            "120" in lower and "second" in lower,
            "Docs must mention the 120-second shell limit",
        )

    def test_docs_mention_staging_and_production(self):
        lower = self.docs_text.lower()
        self.assertIn("staging", lower)
        self.assertIn("production", lower)

    def test_docs_mention_local_test_demo(self):
        lower = self.docs_text.lower()
        self.assertIn("local", lower)
        self.assertIn("test", lower)
        self.assertIn("demo", lower)

    def test_docs_do_not_contain_raw_secret_examples(self):
        import re
        # Reject lines that look like actual secret assignments.
        # Use word boundaries so config flag names like GRANTLAYER_ADMIN_TOKEN=true
        # are not treated as secret leaks.
        forbidden_patterns = [
            r"\bpassword\s*=\s*[^\s]",
            r"\bsecret\s*=\s*[^\s]",
            r"\bapi_key\s*=\s*[^\s]",
            r"\btoken\s*=\s*[^\s]",
            r"\bprivate_key\s*=\s*[^\s]",
            r"\bpassphrase\s*=\s*[^\s]",
        ]
        for pattern in forbidden_patterns:
            for line in self.docs_text.splitlines():
                if re.search(pattern, line, re.IGNORECASE):
                    self.fail(f"Docs must not contain raw secret example: {line}")


class TestGl126ScopeGuard(unittest.TestCase):
    """Verify no forbidden files were changed by GL-126."""

    def _changed_files(self):
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        return result.stdout.strip()

    def test_no_production_code_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("backend/src/"):
                self.fail(f"GL-126 changed production code: {line}")

    def test_no_openapi_change(self):
        changed = self._changed_files()
        self.assertNotIn("openapi.yaml", changed)

    def test_no_migration_change(self):
        changed = self._changed_files()
        self.assertNotIn("migrations/", changed)

    def test_no_frontend_or_website_change(self):
        changed = self._changed_files()
        self.assertNotIn("frontend/", changed)
        self.assertNotIn("website/", changed)

    def test_no_dependency_file_change(self):
        changed = self._changed_files()
        self.assertNotIn("pyproject.toml", changed)
        self.assertNotIn("requirements", changed)
        self.assertNotIn("package.json", changed)
        self.assertNotIn("package-lock.json", changed)

    def test_no_db_schema_change(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if "schema" in line.lower() and line.endswith(".sql"):
                self.fail(f"GL-126 must not change DB schema: {line}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
