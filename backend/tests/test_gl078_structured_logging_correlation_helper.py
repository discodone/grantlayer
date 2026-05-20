"""Tests for GL-078 structured logging / correlation ID helper baseline.

Validates:
- generate_correlation_id produces safe, non-empty UUID-style values.
- normalize_correlation_id preserves safe IDs and replaces unsafe ones.
- build_request_context generates correlationId when missing and omits unsafe inputs.
- build_log_event returns required safe fields, validates event types and severity,
  and includes optional IDs only when safe.
- redact_log_value removes secrets, tokens, private keys, bearer tokens, database URLs,
  authorization headers, cookies, and operator tokens recursively.
- The helper is dependency-free and does not change server/API behavior.
- No forbidden files are touched.
"""

import ast
import inspect
import json
import os
import pathlib
import subprocess
import sys
import unittest

# Ensure backend is on path when running the file directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.src.structured_logging import (
    DEFAULT_SERVICE_NAME,
    SUPPORTED_EVENT_TYPES,
    SUPPORTED_SEVERITIES,
    build_log_event,
    build_request_context,
    generate_correlation_id,
    normalize_correlation_id,
    redact_log_value,
)


class TestGenerateCorrelationId(unittest.TestCase):
    """GL-078: generate_correlation_id safety and uniqueness."""

    def test_returns_non_empty_string(self):
        """Correlation ID must be a non-empty string."""
        cid = generate_correlation_id()
        self.assertIsInstance(cid, str)
        self.assertTrue(len(cid) > 0)

    def test_returns_hex_characters_only(self):
        """Correlation ID contains only hexadecimal characters (safe subset)."""
        cid = generate_correlation_id()
        self.assertTrue(all(c in "0123456789abcdef" for c in cid))

    def test_returns_unique_values_across_multiple_calls(self):
        """Multiple calls should produce distinct values."""
        ids = [generate_correlation_id() for _ in range(100)]
        self.assertEqual(len(set(ids)), len(ids), "generate_correlation_id produced duplicate values")

    def test_does_not_include_hostname_or_env(self):
        """Correlation ID must not encode environment-sensitive data."""
        cid = generate_correlation_id()
        hostname = os.environ.get("HOSTNAME", "")
        if hostname:
            self.assertNotIn(hostname, cid)
        user = os.environ.get("USER", "")
        if user:
            self.assertNotIn(user, cid)
        # UUID hex length is 32
        self.assertEqual(len(cid), 32)


class TestNormalizeCorrelationId(unittest.TestCase):
    """GL-078: normalize_correlation_id safety rules."""

    def test_preserves_safe_uuid_hex(self):
        """A safe hex ID is returned unchanged."""
        safe = "abc123def4567890abc123def4567890"
        result = normalize_correlation_id(safe)
        self.assertEqual(result, safe)

    def test_preserves_safe_id_with_allowed_characters(self):
        """Safe characters (underscore, dash, dot, colon) are preserved."""
        safe = "req_123-456.789:abc"
        result = normalize_correlation_id(safe)
        self.assertEqual(result, safe)

    def test_strips_whitespace_from_safe_id(self):
        """Whitespace around a safe ID is stripped."""
        safe = "  safe_id_123  "
        result = normalize_correlation_id(safe)
        self.assertEqual(result, "safe_id_123")

    def test_replaces_none_with_new_id(self):
        """None produces a newly generated correlation ID."""
        result = normalize_correlation_id(None)
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 32)

    def test_replaces_empty_string(self):
        """Empty string produces a newly generated correlation ID."""
        result = normalize_correlation_id("")
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 32)

    def test_replaces_whitespace_only(self):
        """Whitespace-only string produces a newly generated correlation ID."""
        result = normalize_correlation_id("   \t\n  ")
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 32)

    def test_replaces_too_long_id(self):
        """IDs longer than 128 characters are replaced."""
        long_id = "a" * 129
        result = normalize_correlation_id(long_id)
        self.assertNotEqual(result, long_id)
        self.assertEqual(len(result), 32)

    def test_replaces_unsafe_characters(self):
        """IDs containing unsafe characters are replaced."""
        unsafe_inputs = [
            "foo<bar",
            "foo;bar",
            "foo bar",
            "foo/bar/baz",  # slash not in allowed set
            "foo\\bar",
            "foo@bar",
            "foo$bar",
            "foo%bar",
            'foo"bar',
            "foo'bar",
            "foo&bar",
        ]
        for unsafe in unsafe_inputs:
            with self.subTest(value=unsafe):
                result = normalize_correlation_id(unsafe)
                self.assertIsInstance(result, str)
                self.assertEqual(len(result), 32)
                # Raw unsafe input must never be returned
                self.assertNotEqual(result, unsafe)

    def test_error_message_never_exposes_raw_unsafe_input(self):
        """normalize_correlation_id does not raise or expose raw unsafe input."""
        # This function never raises; it silently replaces, so no error message to check.
        result = normalize_correlation_id("<script>alert(1)</script>")
        self.assertNotIn("<script>", result)


class TestBuildRequestContext(unittest.TestCase):
    """GL-078: build_request_context safe field construction."""

    def test_generates_correlation_id_when_missing(self):
        """Missing correlationId is auto-generated."""
        ctx = build_request_context()
        self.assertIn("correlationId", ctx)
        self.assertEqual(len(ctx["correlationId"]), 32)

    def test_preserves_safe_request_id(self):
        """Safe requestId is included."""
        ctx = build_request_context(request_id="req_123")
        self.assertEqual(ctx.get("requestId"), "req_123")

    def test_preserves_safe_workflow_id(self):
        """Safe workflowId is included."""
        ctx = build_request_context(workflow_id="wf_456")
        self.assertEqual(ctx.get("workflowId"), "wf_456")

    def test_preserves_safe_execution_id(self):
        """Safe executionId is included."""
        ctx = build_request_context(execution_id="exec_789")
        self.assertEqual(ctx.get("executionId"), "exec_789")

    def test_preserves_safe_actor_id(self):
        """Safe actorId is included."""
        ctx = build_request_context(actor_id="actor_001")
        self.assertEqual(ctx.get("actorId"), "actor_001")

    def test_preserves_safe_agent_id(self):
        """Safe agentId is included."""
        ctx = build_request_context(agent_id="agent_002")
        self.assertEqual(ctx.get("agentId"), "agent_002")

    def test_omits_unsafe_request_id(self):
        """Unsafe requestId is omitted, not exposed."""
        ctx = build_request_context(request_id="<unsafe>")
        self.assertNotIn("requestId", ctx)

    def test_omits_unsafe_workflow_id(self):
        """Unsafe workflowId is omitted."""
        ctx = build_request_context(workflow_id="bad id")
        self.assertNotIn("workflowId", ctx)

    def test_omits_unsafe_execution_id(self):
        """Unsafe executionId is omitted."""
        ctx = build_request_context(execution_id="exec;drop")
        self.assertNotIn("executionId", ctx)

    def test_omits_unsafe_actor_id(self):
        """Unsafe actorId is omitted."""
        ctx = build_request_context(actor_id="actor$bad")
        self.assertNotIn("actorId", ctx)

    def test_omits_unsafe_agent_id(self):
        """Unsafe agentId is omitted."""
        ctx = build_request_context(agent_id="agent@bad")
        self.assertNotIn("agentId", ctx)

    def test_includes_all_safe_ids_together(self):
        """Multiple safe optional IDs appear together."""
        ctx = build_request_context(
            correlation_id="corr_001",
            request_id="req_001",
            workflow_id="wf_001",
            execution_id="exec_001",
            actor_id="actor_001",
            agent_id="agent_001",
        )
        self.assertEqual(ctx["correlationId"], "corr_001")
        self.assertEqual(ctx["requestId"], "req_001")
        self.assertEqual(ctx["workflowId"], "wf_001")
        self.assertEqual(ctx["executionId"], "exec_001")
        self.assertEqual(ctx["actorId"], "actor_001")
        self.assertEqual(ctx["agentId"], "agent_001")

    def test_does_not_expose_raw_unsafe_inputs(self):
        """Raw unsafe values must never appear in the output."""
        raw = "<script>alert(1)</script>"
        ctx = build_request_context(
            correlation_id=raw,
            request_id=raw,
            workflow_id=raw,
            execution_id=raw,
            actor_id=raw,
            agent_id=raw,
        )
        for key in ("requestId", "workflowId", "executionId", "actorId", "agentId"):
            self.assertNotIn(key, ctx)
        # correlationId is generated anew because raw is unsafe
        self.assertNotEqual(ctx["correlationId"], raw)


class TestBuildLogEvent(unittest.TestCase):
    """GL-078: build_log_event structured event construction."""

    def test_returns_required_fields(self):
        """All required top-level fields must be present."""
        event = build_log_event("api_request", "Request received")
        self.assertEqual(event["eventType"], "api_request")
        self.assertEqual(event["message"], "Request received")
        self.assertEqual(event["severity"], "info")
        self.assertEqual(event["service"], DEFAULT_SERVICE_NAME)
        self.assertIn("correlationId", event)
        self.assertIn("timestamp", event)
        # timestamp should be a non-empty string
        self.assertIsInstance(event["timestamp"], str)
        self.assertTrue(len(event["timestamp"]) > 0)

    def test_validates_supported_event_types(self):
        """All supported event types are accepted."""
        for etype in SUPPORTED_EVENT_TYPES:
            with self.subTest(event_type=etype):
                event = build_log_event(etype, "test message")
                self.assertEqual(event["eventType"], etype)

    def test_rejects_unsupported_event_type(self):
        """Unsupported event type raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            build_log_event("unknown_event", "test")
        self.assertIn("Unsupported event type", str(ctx.exception))

    def test_rejects_empty_event_type(self):
        """Empty event type raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            build_log_event("", "test")
        self.assertIn("Unsupported event type", str(ctx.exception))

    def test_includes_correlation_id_when_missing(self):
        """Missing correlationId is auto-generated."""
        event = build_log_event("api_request", "test")
        self.assertIn("correlationId", event)
        self.assertEqual(len(event["correlationId"]), 32)

    def test_includes_safe_correlation_id(self):
        """Safe correlationId is preserved."""
        event = build_log_event("api_request", "test", correlation_id="corr_123")
        self.assertEqual(event["correlationId"], "corr_123")

    def test_includes_safe_request_id(self):
        """Safe requestId is included."""
        event = build_log_event("api_request", "test", request_id="req_123")
        self.assertEqual(event["requestId"], "req_123")

    def test_omits_unsafe_request_id(self):
        """Unsafe requestId is omitted."""
        event = build_log_event("api_request", "test", request_id="bad id")
        self.assertNotIn("requestId", event)

    def test_includes_safe_workflow_id(self):
        """Safe workflowId is included."""
        event = build_log_event("api_request", "test", workflow_id="wf_123")
        self.assertEqual(event["workflowId"], "wf_123")

    def test_omits_unsafe_workflow_id(self):
        """Unsafe workflowId is omitted."""
        event = build_log_event("api_request", "test", workflow_id="bad;wf")
        self.assertNotIn("workflowId", event)

    def test_includes_safe_execution_id(self):
        """Safe executionId is included."""
        event = build_log_event("api_request", "test", execution_id="exec_123")
        self.assertEqual(event["executionId"], "exec_123")

    def test_omits_unsafe_execution_id(self):
        """Unsafe executionId is omitted."""
        event = build_log_event("api_request", "test", execution_id="exec<bad>")
        self.assertNotIn("executionId", event)

    def test_includes_safe_actor_id(self):
        """Safe actorId is included."""
        event = build_log_event("api_request", "test", actor_id="actor_123")
        self.assertEqual(event["actorId"], "actor_123")

    def test_omits_unsafe_actor_id(self):
        """Unsafe actorId is omitted."""
        event = build_log_event("api_request", "test", actor_id="actor@bad")
        self.assertNotIn("actorId", event)

    def test_includes_safe_agent_id(self):
        """Safe agentId is included."""
        event = build_log_event("api_request", "test", agent_id="agent_123")
        self.assertEqual(event["agentId"], "agent_123")

    def test_omits_unsafe_agent_id(self):
        """Unsafe agentId is omitted."""
        event = build_log_event("api_request", "test", agent_id="agent bad")
        self.assertNotIn("agentId", event)

    def test_includes_safe_runtime_mode(self):
        """Safe runtimeMode is included."""
        event = build_log_event("api_request", "test", runtime_mode="staging")
        self.assertEqual(event["runtimeMode"], "staging")

    def test_omits_unsafe_runtime_mode(self):
        """Unsafe runtimeMode is omitted."""
        event = build_log_event("api_request", "test", runtime_mode="hack_mode")
        self.assertNotIn("runtimeMode", event)

    def test_omits_empty_runtime_mode(self):
        """Empty runtimeMode is omitted."""
        event = build_log_event("api_request", "test", runtime_mode="")
        self.assertNotIn("runtimeMode", event)

    def test_includes_metadata_when_provided(self):
        """Metadata is included after redaction."""
        meta = {"path": "/health", "status_code": 200}
        event = build_log_event("api_request", "test", metadata=meta)
        self.assertIn("metadata", event)
        self.assertEqual(event["metadata"]["path"], "/health")
        self.assertEqual(event["metadata"]["status_code"], 200)

    def test_redacts_metadata_values(self):
        """Secret metadata values are redacted."""
        meta = {
            "path": "/api",
            "password": "supersecret",
            "api_key": "ak_live_12345",
            "authorization": "Bearer tok_abc",
            "database_url": "postgres://user:pass@localhost/db",
            "operator_token": "op_tok_xyz",
            "cookie": "session=abc123",
            "private_key": "-----BEGIN PRIVATE KEY-----\nkey\n-----END PRIVATE KEY-----",
        }
        event = build_log_event("api_request", "test", metadata=meta)
        m = event["metadata"]
        self.assertEqual(m["path"], "/api")
        self.assertEqual(m["password"], "[REDACTED]")
        self.assertEqual(m["api_key"], "[REDACTED]")
        self.assertEqual(m["authorization"], "[REDACTED]")
        self.assertEqual(m["database_url"], "[REDACTED]")
        self.assertEqual(m["operator_token"], "[REDACTED]")
        self.assertEqual(m["cookie"], "[REDACTED]")
        self.assertEqual(m["private_key"], "[REDACTED]")

    def test_event_is_json_serializable(self):
        """The returned event must be JSON-serializable."""
        event = build_log_event(
            "api_request",
            "test",
            correlation_id="corr_001",
            request_id="req_001",
            workflow_id="wf_001",
            execution_id="exec_001",
            actor_id="actor_001",
            agent_id="agent_001",
            runtime_mode="local",
            severity="info",
            metadata={"count": 42},
        )
        # Should not raise
        serialized = json.dumps(event)
        self.assertIsInstance(serialized, str)


class TestSeverityHandling(unittest.TestCase):
    """GL-078: Severity normalization and validation."""

    def test_default_severity_is_info(self):
        """Default severity when omitted is info."""
        event = build_log_event("health_check", "health ok")
        self.assertEqual(event["severity"], "info")

    def test_accepts_all_supported_severities(self):
        """All supported severities are accepted."""
        for sev in SUPPORTED_SEVERITIES:
            with self.subTest(severity=sev):
                event = build_log_event("health_check", "test", severity=sev)
                self.assertEqual(event["severity"], sev)

    def test_normalizes_case(self):
        """Severity is normalized to lowercase."""
        event = build_log_event("health_check", "test", severity="INFO")
        self.assertEqual(event["severity"], "info")
        event = build_log_event("health_check", "test", severity="Warning")
        self.assertEqual(event["severity"], "warning")

    def test_rejects_empty_severity(self):
        """Empty severity raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            build_log_event("health_check", "test", severity="")
        self.assertIn("Unsupported severity", str(ctx.exception))

    def test_rejects_unsupported_severity(self):
        """Unknown severity raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            build_log_event("health_check", "test", severity="catastrophic")
        self.assertIn("Unsupported severity", str(ctx.exception))

    def test_error_message_does_not_expose_secret_like_values(self):
        """Severity error message does not include unsafe raw input."""
        with self.assertRaises(ValueError) as ctx:
            build_log_event("health_check", "test", severity="sk-secret-12345")
        msg = str(ctx.exception)
        self.assertNotIn("sk-secret-12345", msg)
        self.assertIn("Unsupported severity", msg)


class TestRedactLogValue(unittest.TestCase):
    """GL-078: Metadata redaction determinism and coverage."""

    def test_preserves_safe_scalar_string(self):
        self.assertEqual(redact_log_value("hello"), "hello")

    def test_preserves_safe_int(self):
        self.assertEqual(redact_log_value(42), 42)

    def test_preserves_safe_float(self):
        self.assertEqual(redact_log_value(3.14), 3.14)

    def test_preserves_safe_bool(self):
        self.assertEqual(redact_log_value(True), True)
        self.assertEqual(redact_log_value(False), False)

    def test_preserves_none(self):
        self.assertIsNone(redact_log_value(None))

    def test_redacts_bearer_token(self):
        self.assertEqual(redact_log_value("Bearer tok_12345"), "[REDACTED]")

    def test_redacts_basic_auth(self):
        self.assertEqual(redact_log_value("Basic dXNlcjpwYXNz"), "[REDACTED]")

    def test_redacts_private_key(self):
        self.assertEqual(
            redact_log_value("-----BEGIN PRIVATE KEY-----\nMII...\n-----END PRIVATE KEY-----"),
            "[REDACTED]",
        )

    def test_redacts_database_url(self):
        self.assertEqual(
            redact_log_value("postgres://user:pass@localhost:5432/db"),
            "[REDACTED]",
        )
        self.assertEqual(
            redact_log_value("mysql://user:pass@host/db"),
            "[REDACTED]",
        )
        self.assertEqual(
            redact_log_value("mongodb://user:pass@host/db"),
            "[REDACTED]",
        )

    def test_redacts_api_key_pattern(self):
        self.assertEqual(redact_log_value("ak_live_12345"), "[REDACTED]")
        self.assertEqual(redact_log_value("sk-12345"), "[REDACTED]")
        self.assertEqual(redact_log_value("pk_test_abc"), "[REDACTED]")
        self.assertEqual(redact_log_value("rk_123"), "[REDACTED]")

    def test_redacts_sensitive_key_password(self):
        self.assertEqual(redact_log_value({"password": "secret123"}), {"password": "[REDACTED]"})

    def test_redacts_sensitive_key_secret(self):
        self.assertEqual(redact_log_value({"secret": "hidden"}), {"secret": "[REDACTED]"})

    def test_redacts_sensitive_key_token(self):
        self.assertEqual(redact_log_value({"token": "tok_123"}), {"token": "[REDACTED]"})

    def test_redacts_sensitive_key_api_key(self):
        self.assertEqual(redact_log_value({"api_key": "ak_123"}), {"api_key": "[REDACTED]"})

    def test_redacts_sensitive_key_private_key(self):
        self.assertEqual(
            redact_log_value({"private_key": "-----BEGIN..."}),
            {"private_key": "[REDACTED]"},
        )

    def test_redacts_sensitive_key_authorization(self):
        self.assertEqual(
            redact_log_value({"authorization": "Bearer abc"}),
            {"authorization": "[REDACTED]"},
        )

    def test_redacts_sensitive_key_cookie(self):
        self.assertEqual(
            redact_log_value({"cookie": "session=abc"}),
            {"cookie": "[REDACTED]"},
        )

    def test_redacts_sensitive_key_database_url(self):
        self.assertEqual(
            redact_log_value({"database_url": "postgres://localhost/db"}),
            {"database_url": "[REDACTED]"},
        )

    def test_redacts_sensitive_key_db_url(self):
        self.assertEqual(
            redact_log_value({"db_url": "mysql://localhost/db"}),
            {"db_url": "[REDACTED]"},
        )

    def test_redacts_sensitive_key_operator_token(self):
        self.assertEqual(
            redact_log_value({"operator_token": "op_tok_123"}),
            {"operator_token": "[REDACTED]"},
        )

    def test_redacts_nested_dict_with_sensitive_key(self):
        nested = {"outer": {"inner": {"password": "secret"}}}
        result = redact_log_value(nested)
        self.assertEqual(result["outer"]["inner"]["password"], "[REDACTED]")

    def test_preserves_nested_safe_dict(self):
        nested = {"outer": {"inner": {"count": 42, "name": "safe"}}}
        result = redact_log_value(nested)
        self.assertEqual(result, nested)

    def test_redacts_list_with_secret_value(self):
        result = redact_log_value(["Bearer abc", "safe_value"])
        self.assertEqual(result, ["[REDACTED]", "safe_value"])

    def test_redacts_deeply_nested_secret(self):
        nested = {"a": {"b": {"c": {"d": {"e": {"password": "deep"}}}}}}
        result = redact_log_value(nested)
        self.assertEqual(result["a"]["b"]["c"]["d"]["e"]["password"], "[REDACTED]")

    def test_returns_redaction_marker_at_max_depth(self):
        """Beyond max depth, the entire subtree is replaced with a redaction marker."""
        # Build a dict nested 11 levels deep so the leaf is processed at depth 11 (>10)
        deep = "value"
        for _ in range(11):
            deep = {"level": deep}
        result = redact_log_value(deep)
        # The fully serialized result must not contain the original leaf value
        result_str = str(result)
        self.assertNotIn("'value'", result_str)
        self.assertIn("'[REDACTED]'", result_str)
        # Walk down 10 levels; the 11th should be the redacted marker
        current = result
        for _ in range(10):
            self.assertIsInstance(current, dict)
            current = current["level"]
        self.assertEqual(current, "[REDACTED]")

    def test_redacts_evidence_payload_when_key_is_sensitive(self):
        """Full evidence payloads are not exposed when the key indicates sensitivity."""
        payload = {"evidence_secret": "<large binary or json payload>"}
        result = redact_log_value(payload)
        self.assertEqual(result, {"evidence_secret": "[REDACTED]"})

    def test_does_not_modify_original_dict(self):
        """redact_log_value must not mutate the original input."""
        original = {"password": "secret", "safe": "ok"}
        result = redact_log_value(original)
        self.assertEqual(original["password"], "secret")
        self.assertEqual(result["password"], "[REDACTED]")
        self.assertEqual(result["safe"], "ok")

    def test_redaction_is_deterministic(self):
        """Same input must always produce same output."""
        data = {"password": "secret", "list": ["Bearer abc", 42]}
        first = redact_log_value(data)
        second = redact_log_value(data)
        self.assertEqual(first, second)


class TestNoExternalDependencies(unittest.TestCase):
    """GL-078: structured_logging.py must import only standard library modules."""

    def test_module_imports_only_stdlib(self):
        import backend.src.structured_logging as sl

        source = inspect.getsource(sl)
        tree = ast.parse(source)

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module)

        # Expected stdlib imports
        allowed = {"datetime", "re", "uuid", "typing"}
        actual = set(imports)
        self.assertEqual(
            actual,
            allowed,
            f"Unexpected imports in structured_logging.py: {actual - allowed}",
        )


class TestGL078RegressionNoForbiddenChanges(unittest.TestCase):
    """Verify GL-078 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-078-structured-logging-correlation-helper-baseline":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-078 feature branch"
            )
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/structured_logging.py",
            "backend/tests/test_gl078_structured_logging_correlation_helper.py",
            "docs/observability_structured_logging_baseline_design.md",
            "docs/product_foundation_implementation_cut.md",
            "docs/examples/gl078/structured_logging_examples.json",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-078 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
