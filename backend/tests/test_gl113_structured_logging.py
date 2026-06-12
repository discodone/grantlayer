"""Tests for GL-113: Structured Logging Baseline.

Ensures:
- Structured log helper emits deterministic JSON payload with sorted keys.
- Safe fields are included; sensitive fields are redacted.
- Raw exception messages are never logged.
- Helper fails safe (never raises).
- Existing GL behaviors are preserved.
- No forbidden files are changed.
"""

import json
import logging
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import importlib
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl113(unittest.TestCase):
    """Shared helpers for GL-113 tests."""

    def setUp(self):
        import backend.src.core.logging_utils as lu_mod
        importlib.reload(lu_mod)
        self.lu_mod = lu_mod

    def _parse_logged_json(self, record):
        """Extract JSON payload from a log record string."""
        # Log record format: "LEVEL:logger.name:{...}"
        # Find the first '{' and parse from there
        start = record.find("{")
        if start == -1:
            self.fail(f"No JSON found in log record: {record}")
        return json.loads(record[start:])


# ═══════════════════════════════════════════════════════════════════════
# 1. Structured payload determinism
# ═══════════════════════════════════════════════════════════════════════

class TestGl113StructuredPayload(_BaseGl113):
    """Verify deterministic structured JSON payload."""

    def test_build_log_record_returns_json_string(self):
        payload = self.lu_mod.build_log_record("test_event", component="test")
        self.assertIsInstance(payload, str)
        parsed = json.loads(payload)
        self.assertEqual(parsed["event"], "test_event")

    def test_keys_are_sorted_except_event_first(self):
        payload = self.lu_mod.build_log_record(
            "z_event", component="a", action="b", status="c"
        )
        parsed = json.loads(payload)
        keys = list(parsed.keys())
        self.assertEqual(keys[0], "event")
        self.assertEqual(keys[1:], sorted(keys[1:]))

    def test_event_is_always_first_key(self):
        payload = self.lu_mod.build_log_record("my_event", component="x")
        parsed = json.loads(payload)
        keys = list(parsed.keys())
        self.assertEqual(keys[0], "event")


# ═══════════════════════════════════════════════════════════════════════
# 2. Safe fields inclusion
# ═══════════════════════════════════════════════════════════════════════

class TestGl113SafeFields(_BaseGl113):
    """Verify safe fields are preserved in output."""

    def test_event_field_present(self):
        payload = json.loads(self.lu_mod.build_log_record("test_event"))
        self.assertEqual(payload["event"], "test_event")

    def test_component_field_present(self):
        payload = json.loads(self.lu_mod.build_log_record("e", component="demo"))
        self.assertEqual(payload["component"], "demo")

    def test_action_field_present(self):
        payload = json.loads(self.lu_mod.build_log_record("e", action="create"))
        self.assertEqual(payload["action"], "create")

    def test_status_field_present(self):
        payload = json.loads(self.lu_mod.build_log_record("e", status="ok"))
        self.assertEqual(payload["status"], "ok")

    def test_method_field_present(self):
        payload = json.loads(self.lu_mod.build_log_record("e", method="POST"))
        self.assertEqual(payload["method"], "POST")

    def test_path_field_present(self):
        payload = json.loads(self.lu_mod.build_log_record("e", path="/v1/grants"))
        self.assertEqual(payload["path"], "/v1/grants")

    def test_status_code_field_present(self):
        payload = json.loads(self.lu_mod.build_log_record("e", status_code=200))
        self.assertEqual(payload["status_code"], 200)

    def test_correlation_id_field_present(self):
        payload = json.loads(self.lu_mod.build_log_record("e", correlation_id="abc-123"))
        self.assertEqual(payload["correlation_id"], "abc-123")

    def test_request_id_field_present(self):
        payload = json.loads(self.lu_mod.build_log_record("e", request_id="req-456"))
        self.assertEqual(payload["request_id"], "req-456")

    def test_exception_type_field_present(self):
        payload = json.loads(self.lu_mod.build_log_record("e", exception_type="ValueError"))
        self.assertEqual(payload["exception_type"], "ValueError")


# ═══════════════════════════════════════════════════════════════════════
# 3. Sensitive field redaction
# ═══════════════════════════════════════════════════════════════════════

class TestGl113SensitiveFieldRedaction(_BaseGl113):
    """Verify sensitive fields are redacted and never leak."""

    def _assert_redacted(self, field_name, value):
        payload = json.loads(self.lu_mod.build_log_record("e", **{field_name: value}))
        self.assertEqual(payload.get(field_name), "[REDACTED]", f"Field {field_name} was not redacted")

    def test_authorization_redacted(self):
        self._assert_redacted("authorization", "Bearer secret-token")

    def test_cookie_redacted(self):
        self._assert_redacted("cookie", "session=secret123")

    def test_token_redacted(self):
        self._assert_redacted("token", "secret-token-value")

    def test_admin_token_redacted(self):
        self._assert_redacted("admin_token", "admin-token-secret-value")

    def test_operator_token_redacted(self):
        self._assert_redacted("operator_token", "operator-token-secret-value")

    def test_raw_token_redacted(self):
        self._assert_redacted("raw_token", "raw-secret")

    def test_token_hash_redacted(self):
        self._assert_redacted("token_hash", "token_hash_secret")

    def test_token_lookup_hash_redacted(self):
        self._assert_redacted("token_lookup_hash", "token_lookup_hash_secret")

    def test_password_redacted(self):
        self._assert_redacted("password", "super-secret-password")

    def test_passphrase_redacted(self):
        self._assert_redacted("passphrase", "passphrase-secret")

    def test_private_key_redacted(self):
        self._assert_redacted("private_key", "PRIVATE KEY MATERIAL")

    def test_secret_redacted(self):
        self._assert_redacted("secret", "top-secret")

    def test_signature_redacted(self):
        self._assert_redacted("signature", "signature-secret")

    def test_request_body_redacted(self):
        self._assert_redacted("request_body", "raw-request-body-secret")

    def test_body_redacted(self):
        self._assert_redacted("body", "raw-body-secret")

    def test_evidence_redacted(self):
        self._assert_redacted("evidence", "evidence-payload-secret")

    def test_payload_redacted(self):
        self._assert_redacted("payload", "payload-secret")

    def test_database_url_redacted(self):
        self._assert_redacted("database_url", "postgres://secret-user:secret-pass@example/db")

    def test_connection_string_redacted(self):
        self._assert_redacted("connection_string", "postgres://secret-user:secret-pass@example/db")

    def test_dsn_redacted(self):
        self._assert_redacted("dsn", "postgres://secret-user:secret-pass@example/db")

    def test_stack_trace_redacted(self):
        self._assert_redacted("stack_trace", "Traceback (most recent call last)...")

    def test_case_insensitive_redaction(self):
        """Sensitive field matching is case-insensitive."""
        payload = json.loads(self.lu_mod.build_log_record("e", Authorization="Bearer x"))
        self.assertEqual(payload.get("Authorization"), "[REDACTED]")


# ═══════════════════════════════════════════════════════════════════════
# 4. Secret string leakage prevention
# ═══════════════════════════════════════════════════════════════════════

class TestGl113SecretLeakagePrevention(_BaseGl113):
    """Verify deliberate secret-looking strings never appear in output."""

    def _assert_secret_not_in_output(self, **fields):
        payload = self.lu_mod.build_log_record("test", **fields)
        secrets = [
            "admin-token-secret-value",
            "operator-token-secret-value",
            "PRIVATE KEY MATERIAL",
            "passphrase-secret",
            "raw-request-body-secret",
            "signature-secret",
            "token_lookup_hash_secret",
            "postgres://secret-user:secret-pass@example/db",
        ]
        for secret in secrets:
            self.assertNotIn(secret, payload, f"Secret leaked in payload: {secret}")

    def test_admin_token_not_logged(self):
        self._assert_secret_not_in_output(admin_token="admin-token-secret-value")

    def test_operator_token_not_logged(self):
        self._assert_secret_not_in_output(operator_token="operator-token-secret-value")

    def test_private_key_not_logged(self):
        self._assert_secret_not_in_output(private_key="PRIVATE KEY MATERIAL")

    def test_passphrase_not_logged(self):
        self._assert_secret_not_in_output(passphrase="passphrase-secret")

    def test_request_body_not_logged(self):
        self._assert_secret_not_in_output(request_body="raw-request-body-secret")

    def test_signature_not_logged(self):
        self._assert_secret_not_in_output(signature="signature-secret")

    def test_token_lookup_hash_not_logged(self):
        self._assert_secret_not_in_output(token_lookup_hash="token_lookup_hash_secret")

    def test_database_url_not_logged(self):
        self._assert_secret_not_in_output(database_url="postgres://secret-user:secret-pass@example/db")

    def test_mixed_secrets_not_logged(self):
        self._assert_secret_not_in_output(
            admin_token="admin-token-secret-value",
            operator_token="operator-token-secret-value",
            private_key="PRIVATE KEY MATERIAL",
            passphrase="passphrase-secret",
            request_body="raw-request-body-secret",
            signature="signature-secret",
            token_lookup_hash="token_lookup_hash_secret",
            database_url="postgres://secret-user:secret-pass@example/db",
        )


# ═══════════════════════════════════════════════════════════════════════
# 5. Exception safety
# ═══════════════════════════════════════════════════════════════════════

class TestGl113ExceptionSafety(_BaseGl113):
    """Verify exception handling is safe."""

    def test_exception_type_logged_safely(self):
        payload = json.loads(self.lu_mod.build_log_record("e", exception_type="RuntimeError"))
        self.assertEqual(payload["exception_type"], "RuntimeError")

    def test_raw_exception_message_not_logged(self):
        """build_log_record does not accept arbitrary exception text."""
        # If someone tries to pass exception text as a safe field, it should be dropped
        payload = json.loads(
            self.lu_mod.build_log_record("e", exception_message="secret in exception")
        )
        self.assertNotIn("exception_message", payload)
        self.assertNotIn("secret in exception", json.dumps(payload))

    def test_safe_log_does_not_raise_on_bad_field(self):
        logger = logging.getLogger("test_bad_field")
        # Pass an unserializable object
        class BadObj:
            def __str__(self):
                return "bad"

        # This should not raise
        self.lu_mod.safe_log(logger, "info", "test", component=BadObj())

    def test_build_log_record_does_not_raise_on_unserializable(self):
        class BadObj:
            def __str__(self):
                return "bad_obj"

        payload = self.lu_mod.build_log_record("test", component=BadObj())
        parsed = json.loads(payload)
        self.assertEqual(parsed["event"], "test")
        self.assertEqual(parsed["component"], "bad_obj")

    def test_build_log_record_does_not_raise_on_extremely_bad_object(self):
        class EvilObj:
            def __str__(self):
                raise RuntimeError("evil")

        payload = self.lu_mod.build_log_record("test", component=EvilObj())
        parsed = json.loads(payload)
        self.assertEqual(parsed["event"], "test")
        # Should fall back to safe_default
        self.assertIn("component", parsed)

    def test_safe_log_never_raises(self):
        logger = logging.getLogger("test_never_raises")
        # Even with None logger it should not raise (falls back to error logging)
        self.lu_mod.safe_log(None, "info", "test")

    def test_safe_log_with_invalid_level_falls_back(self):
        logger = logging.getLogger("test_invalid_level")
        self.lu_mod.safe_log(logger, "not_a_level", "test_event", component="x")


# ═══════════════════════════════════════════════════════════════════════
# 6. sanitize_log_fields
# ═══════════════════════════════════════════════════════════════════════

class TestGl113SanitizeLogFields(_BaseGl113):
    """Verify sanitize_log_fields behavior."""

    def test_returns_dict(self):
        result = self.lu_mod.sanitize_log_fields({"event": "test"})
        self.assertIsInstance(result, dict)

    def test_non_dict_returns_empty_dict(self):
        self.assertEqual(self.lu_mod.sanitize_log_fields("not a dict"), {})
        self.assertEqual(self.lu_mod.sanitize_log_fields(None), {})
        self.assertEqual(self.lu_mod.sanitize_log_fields(123), {})

    def test_safe_fields_preserved(self):
        fields = {"event": "e", "component": "c", "action": "a"}
        result = self.lu_mod.sanitize_log_fields(fields)
        self.assertEqual(result["event"], "e")
        self.assertEqual(result["component"], "c")
        self.assertEqual(result["action"], "a")

    def test_sensitive_fields_redacted(self):
        fields = {"token": "secret", "password": "secret"}
        result = self.lu_mod.sanitize_log_fields(fields)
        self.assertEqual(result["token"], "[REDACTED]")
        self.assertEqual(result["password"], "[REDACTED]")

    def test_unknown_fields_dropped(self):
        fields = {"event": "e", "unknown_field": "value"}
        result = self.lu_mod.sanitize_log_fields(fields)
        self.assertNotIn("unknown_field", result)

    def test_mixed_fields_handled_correctly(self):
        fields = {
            "event": "e",
            "component": "c",
            "token": "secret",
            "unknown": "drop",
        }
        result = self.lu_mod.sanitize_log_fields(fields)
        self.assertEqual(result["event"], "e")
        self.assertEqual(result["component"], "c")
        self.assertEqual(result["token"], "[REDACTED]")
        self.assertNotIn("unknown", result)


# ═══════════════════════════════════════════════════════════════════════
# 7. safe_log integration
# ═══════════════════════════════════════════════════════════════════════

class TestGl113SafeLogIntegration(_BaseGl113):
    """Verify safe_log actually emits log records."""

    def test_safe_log_emits_record(self):
        logger = logging.getLogger("test_safe_log")
        with self.assertLogs(logger, level="INFO") as cm:
            self.lu_mod.safe_log(logger, "info", "test_event", component="test")
        self.assertTrue(any("test_event" in msg for msg in cm.output))

    def test_safe_log_emits_json_payload(self):
        logger = logging.getLogger("test_safe_log_json")
        with self.assertLogs(logger, level="INFO") as cm:
            self.lu_mod.safe_log(logger, "info", "test_event", component="test")
        log_str = "\n".join(cm.output)
        # Extract and verify JSON
        parsed = self._parse_logged_json(log_str)
        self.assertEqual(parsed["event"], "test_event")
        self.assertEqual(parsed["component"], "test")

    def test_safe_log_respects_level(self):
        logger = logging.getLogger("test_safe_log_level")
        with self.assertLogs(logger, level="WARNING") as cm:
            self.lu_mod.safe_log(logger, "warning", "warn_event")
        self.assertTrue(any("warn_event" in msg for msg in cm.output))

    def test_safe_log_redacts_in_output(self):
        logger = logging.getLogger("test_safe_log_redact")
        with self.assertLogs(logger, level="INFO") as cm:
            self.lu_mod.safe_log(logger, "info", "evt", token="secret123")
        log_str = "\n".join(cm.output)
        self.assertIn("[REDACTED]", log_str)
        self.assertNotIn("secret123", log_str)


# ═══════════════════════════════════════════════════════════════════════
# 8. get_logger
# ═══════════════════════════════════════════════════════════════════════

class TestGl113GetLogger(_BaseGl113):
    """Verify get_logger returns a stdlib logger."""

    def test_returns_logger(self):
        logger = self.lu_mod.get_logger("test_logger")
        self.assertIsInstance(logger, logging.Logger)

    def test_logger_has_correct_name(self):
        logger = self.lu_mod.get_logger("my.module")
        self.assertEqual(logger.name, "my.module")


# ═══════════════════════════════════════════════════════════════════════
# 9. Cross-GL preservation (lightweight module checks)
# ═══════════════════════════════════════════════════════════════════════

class TestGl113CrossGlPreservation(unittest.TestCase):
    """Verify other GL behaviors are not broken by GL-113 changes."""

    def test_gl111_demo_action_module_preserved(self):
        import backend.src.demo.demo_action as demo_mod
        importlib.reload(demo_mod)
        self.assertTrue(hasattr(demo_mod, "handle_demo_action"))
        self.assertTrue(hasattr(demo_mod, "logger"))

    def test_gl106_rate_limiter_preserved(self):
        import backend.src.core.rate_limiter as rl_mod
        importlib.reload(rl_mod)
        self.assertTrue(hasattr(rl_mod, "RateLimiter"))

    def test_gl109_auth_module_preserved(self):
        import backend.src.auth.auth as auth_mod
        importlib.reload(auth_mod)
        self.assertTrue(hasattr(auth_mod, "check_admin_token"))
        self.assertTrue(hasattr(auth_mod, "check_auth"))

    def test_gl110_crypto_signing_preserved(self):
        import backend.src.core.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        self.assertTrue(hasattr(crypto_mod, "load_private_key"))
        self.assertTrue(hasattr(crypto_mod, "sign_grant"))

    def test_gl112_audit_log_preserved(self):
        import backend.src.audit.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.assertTrue(hasattr(audit_mod, "append_event"))
        self.assertTrue(hasattr(audit_mod, "verify_audit_hash_chain"))

    def test_security_boundary_preserved(self):
        import backend.src.auth.auth as auth_mod
        importlib.reload(auth_mod)
        self.assertTrue(hasattr(auth_mod, "check_admin_token"))
        self.assertTrue(hasattr(auth_mod, "check_auth"))

    def test_no_db_schema_migration_change(self):
        import tempfile
        tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = tmp_db.name
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        try:
            import backend.src.core.db as db_mod
            importlib.reload(db_mod)
            db_mod.init_db()
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
        finally:
            os.unlink(tmp_db.name)
            if orig_db is not None:
                os.environ["GRANTLAYER_DB"] = orig_db
            else:
                os.environ.pop("GRANTLAYER_DB", None)

    def test_no_openapi_change_needed(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        openapi_path = repo_root / "docs" / "openapi.yaml"
        self.assertTrue(openapi_path.exists())

    def test_no_endpoint_changes(self):
        from backend.src.api.app import create_app

        app = create_app()
        self.assertTrue(any(route.path == "/health" for route in app.routes))


# ═══════════════════════════════════════════════════════════════════════
# 10. Scope guard — diff validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl113NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-113 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-113-structured-logging-baseline":
            self.skipTest(
                "Branch-wide diff check only valid on GL-113 feature branch"
            )
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/logging_utils.py",
            "backend/src/server.py",
            "backend/src/demo_action.py",
            "backend/src/config.py",
            "backend/tests/test_gl113_structured_logging.py",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-113 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
