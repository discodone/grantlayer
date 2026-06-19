"""Tests for GL-076 runtime configuration enforcement baseline."""

import unittest

from backend.src.core.runtime_config import (
    DEFAULT_MODE,
    PRODUCTION_LIKE_MODES,
    SUPPORTED_MODES,
    describe_runtime_config,
    get_runtime_mode,
    is_production_like,
)


class TestGetRuntimeMode(unittest.TestCase):
    """Tests for get_runtime_mode env parsing and validation."""

    def test_default_when_env_absent(self):
        """Default runtime mode is production when GRANTLAYER_RUNTIME_MODE is absent (fail-closed)."""
        env = {}
        self.assertEqual(get_runtime_mode(env), "production")

    def test_default_when_env_empty(self):
        """Empty runtime mode defaults to production (fail-closed)."""
        env = {"GRANTLAYER_RUNTIME_MODE": ""}
        self.assertEqual(get_runtime_mode(env), "production")

    def test_default_when_env_whitespace_only(self):
        """Whitespace-only runtime mode defaults to production (fail-closed)."""
        env = {"GRANTLAYER_RUNTIME_MODE": "   "}
        self.assertEqual(get_runtime_mode(env), "production")

    def test_all_supported_modes_accepted(self):
        """All supported modes are accepted."""
        for mode in SUPPORTED_MODES:
            with self.subTest(mode=mode):
                env = {"GRANTLAYER_RUNTIME_MODE": mode}
                self.assertEqual(get_runtime_mode(env), mode)

    def test_whitespace_around_supported_mode_is_stripped(self):
        """Whitespace around supported mode is handled safely."""
        for mode in SUPPORTED_MODES:
            with self.subTest(mode=mode):
                env = {"GRANTLAYER_RUNTIME_MODE": f"  {mode}  "}
                self.assertEqual(get_runtime_mode(env), mode)

    def test_case_insensitive_supported_modes(self):
        """Supported modes are accepted case-insensitively."""
        for mode in SUPPORTED_MODES:
            with self.subTest(mode=mode):
                env_upper = {"GRANTLAYER_RUNTIME_MODE": mode.upper()}
                env_mixed = {"GRANTLAYER_RUNTIME_MODE": mode.capitalize()}
                self.assertEqual(get_runtime_mode(env_upper), mode)
                self.assertEqual(get_runtime_mode(env_mixed), mode)

    def test_unsupported_mode_raises_value_error(self):
        """Unsupported mode raises ValueError."""
        env = {"GRANTLAYER_RUNTIME_MODE": "invalid"}
        with self.assertRaises(ValueError) as ctx:
            get_runtime_mode(env)
        self.assertIn("Unsupported runtime mode", str(ctx.exception))

    def test_error_message_does_not_expose_secret_like_values(self):
        """Error message does not expose secret-like values."""
        env = {"GRANTLAYER_RUNTIME_MODE": "sk-secret-key-12345"}
        with self.assertRaises(ValueError) as ctx:
            get_runtime_mode(env)
        message = str(ctx.exception)
        self.assertNotIn("sk-secret-key-12345", message)
        self.assertIn("Unsupported runtime mode", message)


class TestIsProductionLike(unittest.TestCase):
    """Tests for is_production_like evaluation."""

    def test_true_for_staging_and_production(self):
        """is_production_like returns true for staging and production."""
        for mode in PRODUCTION_LIKE_MODES:
            with self.subTest(mode=mode):
                env = {"GRANTLAYER_RUNTIME_MODE": mode}
                self.assertTrue(is_production_like(env=env))
                self.assertTrue(is_production_like(mode=mode))

    def test_false_for_local_test_demo(self):
        """is_production_like returns false for local, test, demo."""
        non_production = {"local", "test", "demo"}
        for mode in non_production:
            with self.subTest(mode=mode):
                env = {"GRANTLAYER_RUNTIME_MODE": mode}
                self.assertFalse(is_production_like(env=env))
                self.assertFalse(is_production_like(mode=mode))

    def test_explicit_unsupported_mode_raises_value_error(self):
        """Explicit unsupported mode raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            is_production_like(mode="unknown")
        self.assertIn("Unsupported runtime mode", str(ctx.exception))

    def test_auto_resolve_from_env_when_mode_none(self):
        """When mode is None, resolves from env."""
        env = {"GRANTLAYER_RUNTIME_MODE": "production"}
        self.assertTrue(is_production_like(mode=None, env=env))


class TestDescribeRuntimeConfig(unittest.TestCase):
    """Tests for describe_runtime_config safe metadata output."""

    def test_returns_runtime_mode(self):
        """describe_runtime_config returns runtimeMode."""
        env = {"GRANTLAYER_RUNTIME_MODE": "test"}
        result = describe_runtime_config(env)
        self.assertEqual(result["runtimeMode"], "test")

    def test_returns_is_production_like(self):
        """describe_runtime_config returns isProductionLike."""
        env_prod = {"GRANTLAYER_RUNTIME_MODE": "production"}
        env_local = {"GRANTLAYER_RUNTIME_MODE": "local"}
        self.assertTrue(describe_runtime_config(env_prod)["isProductionLike"])
        self.assertFalse(describe_runtime_config(env_local)["isProductionLike"])

    def test_returns_supported_modes(self):
        """describe_runtime_config returns supportedModes."""
        result = describe_runtime_config({})
        self.assertEqual(result["supportedModes"], sorted(SUPPORTED_MODES))

    def test_returns_config_source_default(self):
        """describe_runtime_config returns configSource 'default' when env absent."""
        result = describe_runtime_config({})
        self.assertEqual(result["configSource"], "default")

    def test_returns_config_source_environment(self):
        """describe_runtime_config returns configSource 'environment' when env set."""
        env = {"GRANTLAYER_RUNTIME_MODE": "demo"}
        result = describe_runtime_config(env)
        self.assertEqual(result["configSource"], "environment")

    def test_does_not_expose_raw_env_values(self):
        """describe_runtime_config does not expose raw env values."""
        env = {
            "GRANTLAYER_RUNTIME_MODE": "test",
            "SECRET_TOKEN": "should-not-appear",
            "DATABASE_URL": "postgres://localhost/db",
        }
        result = describe_runtime_config(env)
        for value in result.values():
            self.assertNotIn("should-not-appear", str(value))
            self.assertNotIn("postgres://", str(value))

    def test_does_not_expose_secrets_tokens_private_keys(self):
        """describe_runtime_config does not expose secrets, tokens, private keys."""
        env = {
            "GRANTLAYER_RUNTIME_MODE": "staging",
            "PRIVATE_KEY": "FAKE_PLACEHOLDER_PRIVATE_KEY_VALUE",
            "API_KEY": "ak_live_12345",
            "OPERATOR_TOKEN": "op_token_xyz",
        }
        result = describe_runtime_config(env)
        for value in result.values():
            self.assertNotIn("FAKE_PLACEHOLDER_PRIVATE_KEY_VALUE", str(value))
            self.assertNotIn("ak_live_12345", str(value))
            self.assertNotIn("op_token_xyz", str(value))

    def test_default_mode_when_env_absent(self):
        """Default mode metadata is production when env absent (fail-closed)."""
        result = describe_runtime_config({})
        self.assertEqual(result["runtimeMode"], DEFAULT_MODE)
        self.assertTrue(result["isProductionLike"])


class TestNoForbiddenFilesChanged(unittest.TestCase):
    """Sanity check that GL-076 does not depend on forbidden files being changed."""

    def test_module_is_dependency_free(self):
        """The runtime_config module imports only stdlib."""
        import importlib
        import sys

        # Ensure we have a fresh import
        for _key in list(sys.modules):
            if "backend.src.core.runtime_config" in _key or _key in ("backend", "backend.src", "backend.src.core"):
                del sys.modules[_key]

        # Track imports by running the module in a limited way
        import backend.src.core.runtime_config as rc
        import ast
        import inspect

        source = inspect.getsource(rc)
        tree = ast.parse(source)

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module)

        # Only os and typing are expected
        allowed = {"os", "typing"}
        actual = set(imports)
        self.assertEqual(actual, allowed)


if __name__ == "__main__":
    unittest.main()
