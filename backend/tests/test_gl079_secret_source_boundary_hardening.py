"""Tests for GL-079 secret source boundary hardening baseline.

These tests validate that the secret source helpers in
backend/src/secret_sources.py behave safely, do not expose raw secret
values, and remain isolated from server/API/auth behavior.
"""

from __future__ import annotations

import sys
import unittest
from typing import Any

sys.path.append("backend")

from backend.src.core.secret_sources import (
    REDACTED_SECRET_VALUE,
    SECRET_SOURCE_ENVIRONMENT,
    SecretConfigurationError,
    describe_secret_source,
    is_secret_key,
    read_optional_secret,
    read_required_secret,
    redact_secret_value,
    validate_required_secrets,
)


class TestIsSecretKey(unittest.TestCase):
    """Validate secret-key detection patterns and safety."""

    def test_detects_password(self) -> None:
        self.assertTrue(is_secret_key("password"))

    def test_detects_secret(self) -> None:
        self.assertTrue(is_secret_key("secret"))

    def test_detects_token(self) -> None:
        self.assertTrue(is_secret_key("token"))

    def test_detects_api_key(self) -> None:
        self.assertTrue(is_secret_key("api_key"))

    def test_detects_private_key(self) -> None:
        self.assertTrue(is_secret_key("private_key"))

    def test_detects_authorization(self) -> None:
        self.assertTrue(is_secret_key("authorization"))

    def test_detects_cookie(self) -> None:
        self.assertTrue(is_secret_key("cookie"))

    def test_detects_database_url(self) -> None:
        self.assertTrue(is_secret_key("database_url"))

    def test_detects_db_url(self) -> None:
        self.assertTrue(is_secret_key("db_url"))

    def test_detects_operator_token(self) -> None:
        self.assertTrue(is_secret_key("operator_token"))

    def test_detects_admin_token(self) -> None:
        self.assertTrue(is_secret_key("admin_token"))

    def test_detects_signing_key(self) -> None:
        self.assertTrue(is_secret_key("signing_key"))

    def test_detects_credential(self) -> None:
        self.assertTrue(is_secret_key("credential"))

    def test_case_insensitive(self) -> None:
        self.assertTrue(is_secret_key("PASSWORD"))
        self.assertTrue(is_secret_key("Secret"))
        self.assertTrue(is_secret_key("API_KEY"))
        self.assertTrue(is_secret_key("Operator_Token"))

    def test_hyphen_variant(self) -> None:
        self.assertTrue(is_secret_key("api-key"))
        self.assertTrue(is_secret_key("private-key"))
        self.assertTrue(is_secret_key("signing-key"))

    def test_none_returns_false(self) -> None:
        self.assertFalse(is_secret_key(None))

    def test_non_string_returns_false(self) -> None:
        self.assertFalse(is_secret_key(123))
        self.assertFalse(is_secret_key(["password"]))

    def test_safe_key_returns_false(self) -> None:
        self.assertFalse(is_secret_key("timeout"))
        self.assertFalse(is_secret_key("port"))
        self.assertFalse(is_secret_key("host"))


class TestRedactSecretValue(unittest.TestCase):
    """Validate redaction behavior without leaking secrets."""

    def test_redacts_non_empty_string(self) -> None:
        result = redact_secret_value("super-secret-value")
        self.assertEqual(result, REDACTED_SECRET_VALUE)

    def test_preserves_none(self) -> None:
        self.assertIsNone(redact_secret_value(None))

    def test_preserves_bool(self) -> None:
        self.assertIs(redact_secret_value(True), True)
        self.assertIs(redact_secret_value(False), False)

    def test_preserves_int(self) -> None:
        self.assertEqual(redact_secret_value(42), 42)

    def test_preserves_float(self) -> None:
        self.assertEqual(redact_secret_value(3.14), 3.14)

    def test_preserves_empty_string(self) -> None:
        self.assertEqual(redact_secret_value(""), "")

    def test_preserves_whitespace_only_string(self) -> None:
        self.assertEqual(redact_secret_value("   "), "   ")

    def test_preserves_already_redacted(self) -> None:
        self.assertEqual(
            redact_secret_value(REDACTED_SECRET_VALUE), REDACTED_SECRET_VALUE
        )


class TestReadOptionalSecret(unittest.TestCase):
    """Validate optional secret reading from custom env mapping."""

    def test_returns_none_when_absent(self) -> None:
        self.assertIsNone(read_optional_secret("MISSING_SECRET", env={}))

    def test_returns_none_for_empty_string(self) -> None:
        self.assertIsNone(read_optional_secret("EMPTY_SECRET", env={"EMPTY_SECRET": ""}))

    def test_returns_none_for_whitespace_only(self) -> None:
        self.assertIsNone(
            read_optional_secret("SPACE_SECRET", env={"SPACE_SECRET": "   "})
        )

    def test_returns_raw_value_when_present(self) -> None:
        env = {"MY_SECRET": "raw-secret-value"}
        self.assertEqual(read_optional_secret("MY_SECRET", env=env), "raw-secret-value")

    def test_uses_os_environ_when_env_none(self) -> None:
        import os

        os.environ["GL079_TEST_OPTIONAL"] = "from-os"
        try:
            self.assertEqual(
                read_optional_secret("GL079_TEST_OPTIONAL"), "from-os"
            )
        finally:
            del os.environ["GL079_TEST_OPTIONAL"]

    def test_invalid_name_raises_safe_valueerror(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            read_optional_secret("")
        msg = str(ctx.exception).lower()
        # The error should be about the parameter, not expose any raw value.
        # We allow "secret name" as a parameter description.
        self.assertIn("name", msg)
        self.assertIn("empty", msg)

    def test_invalid_name_whitespace_raises_safe_valueerror(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            read_optional_secret("  ")
        msg = str(ctx.exception).lower()
        self.assertIn("name", msg)
        self.assertIn("empty", msg)


class TestReadRequiredSecret(unittest.TestCase):
    """Validate required secret reading and safe error messages."""

    def test_returns_raw_value_when_present(self) -> None:
        env = {"REQ_SECRET": "required-value"}
        self.assertEqual(
            read_required_secret("REQ_SECRET", env=env), "required-value"
        )

    def test_raises_secret_configuration_error_when_missing(self) -> None:
        with self.assertRaises(SecretConfigurationError) as ctx:
            read_required_secret("MISSING_REQ", env={})
        msg = str(ctx.exception)
        self.assertIn("MISSING_REQ", msg)
        # Must not leak a raw value because there isn't one.
        # Must not dump the environment.
        self.assertNotIn("os.environ", msg)

    def test_raises_secret_configuration_error_when_empty(self) -> None:
        with self.assertRaises(SecretConfigurationError) as ctx:
            read_required_secret("EMPTY_REQ", env={"EMPTY_REQ": ""})
        self.assertIn("EMPTY_REQ", str(ctx.exception))

    def test_error_does_not_expose_secret_values(self) -> None:
        env = {"REQ_SECRET": "leaked?"}
        try:
            read_required_secret("REQ_MISSING", env=env)
        except SecretConfigurationError as exc:
            self.assertNotIn("leaked", str(exc))
            self.assertNotIn("leaked", repr(exc))

    def test_secret_configuration_error_safe_repr(self) -> None:
        exc = SecretConfigurationError("some error")
        self.assertIn("SecretConfigurationError", repr(exc))
        self.assertIn("some error", repr(exc))

    def test_secret_configuration_error_safe_str(self) -> None:
        exc = SecretConfigurationError("some error")
        self.assertEqual(str(exc), "some error")

    def test_invalid_name_raises_safe_valueerror(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            read_required_secret("")
        msg = str(ctx.exception).lower()
        self.assertIn("name", msg)
        self.assertIn("empty", msg)


class TestDescribeSecretSource(unittest.TestCase):
    """Validate describe output never leaks raw secrets."""

    def test_absent_secret(self) -> None:
        result = describe_secret_source("NOT_PRESENT", env={})
        self.assertEqual(result["name"], "NOT_PRESENT")
        self.assertEqual(result["source"], SECRET_SOURCE_ENVIRONMENT)
        self.assertFalse(result["present"])
        self.assertIsNone(result["valuePreview"])

    def test_present_secret_redacted(self) -> None:
        result = describe_secret_source("HAS_SECRET", env={"HAS_SECRET": "s3cr3t"})
        self.assertEqual(result["name"], "HAS_SECRET")
        self.assertEqual(result["source"], SECRET_SOURCE_ENVIRONMENT)
        self.assertTrue(result["present"])
        self.assertEqual(result["valuePreview"], REDACTED_SECRET_VALUE)
        self.assertNotIn("s3cr3t", str(result))

    def test_present_secret_raw_not_included(self) -> None:
        result = describe_secret_source("HAS_SECRET", env={"HAS_SECRET": "s3cr3t"})
        for value in result.values():
            self.assertNotEqual(value, "s3cr3t")


class TestValidateRequiredSecrets(unittest.TestCase):
    """Validate safe validation summary without secret exposure."""

    def test_all_present(self) -> None:
        env = {"A": "1", "B": "2"}
        result = validate_required_secrets(["A", "B"], env=env)
        self.assertTrue(result["valid"])
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["present"], ["A", "B"])
        self.assertEqual(result["source"], SECRET_SOURCE_ENVIRONMENT)
        self.assertNotIn("1", str(result))
        self.assertNotIn("2", str(result))

    def test_some_missing(self) -> None:
        env = {"A": "1"}
        result = validate_required_secrets(["A", "B"], env=env)
        self.assertFalse(result["valid"])
        self.assertEqual(result["missing"], ["B"])
        self.assertEqual(result["present"], ["A"])
        self.assertNotIn("1", str(result))

    def test_all_missing(self) -> None:
        result = validate_required_secrets(["X", "Y"], env={})
        self.assertFalse(result["valid"])
        self.assertEqual(result["missing"], ["X", "Y"])
        self.assertEqual(result["present"], [])

    def test_deterministic_ordering(self) -> None:
        env = {"Z": "9", "A": "1", "M": "5"}
        result = validate_required_secrets(["Z", "A", "M"], env=env)
        self.assertEqual(result["present"], ["Z", "A", "M"])

    def test_empty_names(self) -> None:
        result = validate_required_secrets([], env={})
        self.assertTrue(result["valid"])
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["present"], [])

    def test_invalid_name_in_sequence_raises(self) -> None:
        with self.assertRaises(ValueError):
            validate_required_secrets(["A", ""])


class TestIsolationAndDependencies(unittest.TestCase):
    """Validate helper isolation and lack of forbidden changes."""

    def test_no_external_dependencies(self) -> None:
        # The module uses only the Python standard library.
        # Verify by importing it and checking its source file is not pulling
        # third-party packages.
        import importlib.util
        import pathlib

        spec = importlib.util.find_spec("backend.src.core.secret_sources")
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.origin)
        source = pathlib.Path(spec.origin).read_text(encoding="utf-8")
        # Should not import known third-party packages (requests, boto3, etc.)
        third_party_imports = [
            "import requests",
            "import boto3",
            "import botocore",
            "import hvac",
            "import azure",
            "import google.cloud",
            "import jwt",
            "import cryptography",
        ]
        for imp in third_party_imports:
            self.assertNotIn(imp, source, f"Found third-party import: {imp}")

    @unittest.skip("server.py deleted in GL-240")
    def test_server_py_not_changed(self) -> None:
        with open("backend/src/server.py", "r") as fh:
            content = fh.read()
        self.assertNotIn("secret_sources", content)
        self.assertNotIn("read_optional_secret", content)
        self.assertNotIn("read_required_secret", content)

    def test_openapi_yaml_not_changed_by_gl079(self) -> None:
        with open("docs/openapi.yaml", "r") as fh:
            content = fh.read()
        # GL-079 does not modify openapi.yaml.
        self.assertNotIn("secret_sources", content)
        self.assertNotIn("read_optional_secret", content)
        self.assertNotIn("read_required_secret", content)
        self.assertNotIn("describe_secret_source", content)
        self.assertNotIn("validate_required_secrets", content)

    def test_no_persistence_files_changed(self) -> None:
        import os

        for root, _dirs, files in os.walk("backend/src"):
            for f in files:
                if f.endswith(".py") and f not in ("secret_sources.py",):
                    path = os.path.join(root, f)
                    with open(path, "r", encoding="utf-8") as fh:
                        content = fh.read()
                    self.assertNotIn(
                        "secret_sources",
                        content,
                        f"{path} references secret_sources",
                    )


class TestSafetyEdgeCases(unittest.TestCase):
    """Additional safety edge cases for robustness."""

    def test_redact_secret_value_preserve_tuple(self) -> None:
        # tuples and lists should be returned as-is because they are not
        # credential-like primitive strings.
        data: list[Any] = [1, 2, 3]
        self.assertEqual(redact_secret_value(data), data)

    def test_read_optional_secret_with_mapping(self) -> None:
        env = {"KEY": "value"}
        self.assertEqual(read_optional_secret("KEY", env=env), "value")

    def test_read_required_secret_with_mapping(self) -> None:
        env = {"KEY": "value"}
        self.assertEqual(read_required_secret("KEY", env=env), "value")

    def test_validate_required_secrets_with_none_names_raises(self) -> None:
        with self.assertRaises(ValueError):
            validate_required_secrets(None)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
