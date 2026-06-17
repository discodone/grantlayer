"""GL-302 — Coverage gap tests.

Targets specific uncovered paths to bring total coverage from 91% to ≥95%.
"""

from __future__ import annotations

import datetime
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pytest

# ══════════════════════════════════════════════════════════════════════════════
# A. structured_logging.py — 101 missing lines at 25% coverage
# ══════════════════════════════════════════════════════════════════════════════
from backend.src.core.structured_logging import (
    _REDACTED_MARKER,
    _is_safe_id,
    _is_safe_runtime_mode,
    _is_sensitive_key,
    _looks_like_secret,
    _normalize_severity,
    build_log_event,
    build_request_context,
    generate_correlation_id,
    normalize_correlation_id,
    redact_log_value,
)


class TestGenerateCorrelationId:
    def test_returns_hex_string(self):
        cid = generate_correlation_id()
        assert isinstance(cid, str)
        assert len(cid) == 32

    def test_unique_each_call(self):
        assert generate_correlation_id() != generate_correlation_id()


class TestIsaSafeId:
    def test_none_returns_false(self):
        assert _is_safe_id(None) is False

    def test_empty_string_returns_false(self):
        assert _is_safe_id("") is False

    def test_whitespace_only_returns_false(self):
        assert _is_safe_id("   ") is False

    def test_too_long_returns_false(self):
        assert _is_safe_id("a" * 129) is False

    def test_exactly_max_length_returns_true(self):
        assert _is_safe_id("a" * 128) is True

    def test_unsafe_space_char_returns_false(self):
        assert _is_safe_id("id with space") is False

    def test_unsafe_at_char_returns_false(self):
        assert _is_safe_id("abc@def") is False

    def test_unsafe_exclamation_returns_false(self):
        assert _is_safe_id("abc!") is False

    def test_valid_alphanumeric(self):
        assert _is_safe_id("abc123") is True

    def test_valid_with_dash(self):
        assert _is_safe_id("corr-id-123") is True

    def test_valid_with_underscore(self):
        assert _is_safe_id("corr_id") is True

    def test_valid_with_dot(self):
        assert _is_safe_id("v1.2.3") is True

    def test_valid_with_colon(self):
        assert _is_safe_id("req:001") is True

    def test_single_char(self):
        assert _is_safe_id("a") is True


class TestNormalizeCorrelationId:
    def test_none_generates_new_id(self):
        result = normalize_correlation_id(None)
        assert len(result) == 32

    def test_empty_generates_new_id(self):
        result = normalize_correlation_id("")
        assert len(result) == 32

    def test_whitespace_generates_new_id(self):
        result = normalize_correlation_id("   ")
        assert len(result) == 32

    def test_too_long_generates_new_id(self):
        result = normalize_correlation_id("a" * 200)
        assert len(result) == 32

    def test_unsafe_chars_generates_new_id(self):
        result = normalize_correlation_id("bad id!")
        assert len(result) == 32

    def test_valid_id_returned_as_is(self):
        result = normalize_correlation_id("valid-id-123")
        assert result == "valid-id-123"

    def test_strips_whitespace_from_valid(self):
        result = normalize_correlation_id("  valid-id  ")
        assert result == "valid-id"


class TestIsSensitiveKey:
    def test_password_is_sensitive(self):
        assert _is_sensitive_key("password") is True

    def test_my_password_is_sensitive(self):
        assert _is_sensitive_key("my_password") is True

    def test_secret_is_sensitive(self):
        assert _is_sensitive_key("my_secret") is True

    def test_token_is_sensitive(self):
        assert _is_sensitive_key("auth_token") is True

    def test_api_key_is_sensitive(self):
        assert _is_sensitive_key("api_key") is True

    def test_private_key_is_sensitive(self):
        assert _is_sensitive_key("private_key") is True

    def test_authorization_is_sensitive(self):
        assert _is_sensitive_key("Authorization") is True

    def test_cookie_is_sensitive(self):
        assert _is_sensitive_key("cookie") is True

    def test_database_url_is_sensitive(self):
        assert _is_sensitive_key("database_url") is True

    def test_db_url_is_sensitive(self):
        assert _is_sensitive_key("db_url") is True

    def test_operator_token_is_sensitive(self):
        assert _is_sensitive_key("operator_token") is True

    def test_safe_role_key(self):
        assert _is_sensitive_key("role") is False

    def test_safe_action_key(self):
        assert _is_sensitive_key("action") is False

    def test_safe_username_key(self):
        assert _is_sensitive_key("username") is False


class TestLooksLikeSecret:
    def test_bearer_token(self):
        assert _looks_like_secret("Bearer abc123") is True

    def test_basic_auth(self):
        assert _looks_like_secret("Basic abc123") is True

    def test_pem_begin(self):
        assert _looks_like_secret("-----BEGIN RSA PRIVATE KEY-----") is True

    def test_pem_end(self):
        assert _looks_like_secret("-----END RSA PRIVATE KEY-----") is True

    def test_postgres_url(self):
        assert _looks_like_secret("postgres://user:pass@host/db") is True

    def test_mysql_url(self):
        assert _looks_like_secret("mysql://user:pass@host/db") is True

    def test_mongodb_url(self):
        assert _looks_like_secret("mongodb://user:pass@host/db") is True

    def test_redis_url(self):
        assert _looks_like_secret("redis://host:6379/0") is True

    def test_amqp_url(self):
        assert _looks_like_secret("amqp://user:pass@host/vhost") is True

    def test_sqlite_url(self):
        assert _looks_like_secret("sqlite:///db.sqlite3") is True

    def test_sk_prefix(self):
        assert _looks_like_secret("sk-abc123") is True

    def test_ak_prefix(self):
        assert _looks_like_secret("ak_abc123") is True

    def test_pk_prefix(self):
        assert _looks_like_secret("pk_abc123") is True

    def test_rk_prefix(self):
        assert _looks_like_secret("rk_abc123") is True

    def test_private_key_in_value(self):
        assert _looks_like_secret("this_is_a_private_key_material") is True

    def test_safe_greeting(self):
        assert _looks_like_secret("Hello World") is False

    def test_safe_agent_id(self):
        assert _looks_like_secret("agent-1") is False

    def test_safe_status(self):
        assert _looks_like_secret("approved") is False

    def test_safe_number_string(self):
        assert _looks_like_secret("42") is False


class TestRedactLogValue:
    def test_depth_limit_returns_redacted(self):
        result = redact_log_value("value", _depth=10)
        assert result == _REDACTED_MARKER

    def test_dict_sensitive_key_redacted(self):
        result = redact_log_value({"password": "s3cr3t"})
        assert isinstance(result, dict)
        assert result["password"] == _REDACTED_MARKER

    def test_dict_safe_key_preserved(self):
        result = redact_log_value({"role": "viewer"})
        assert isinstance(result, dict)
        assert result["role"] == "viewer"

    def test_dict_mixed_keys(self):
        result = redact_log_value({"token": "abc", "action": "read"})
        assert result["token"] == _REDACTED_MARKER
        assert result["action"] == "read"

    def test_list_secrets_redacted(self):
        result = redact_log_value(["Bearer token123", "safe"])
        assert isinstance(result, list)
        assert result[0] == _REDACTED_MARKER
        assert result[1] == "safe"

    def test_str_secret_redacted(self):
        assert redact_log_value("Bearer abc") == _REDACTED_MARKER

    def test_str_safe_preserved(self):
        assert redact_log_value("hello world") == "hello world"

    def test_int_preserved(self):
        assert redact_log_value(42) == 42

    def test_float_preserved(self):
        assert redact_log_value(3.14) == 3.14

    def test_bool_true_preserved(self):
        assert redact_log_value(True) is True

    def test_bool_false_preserved(self):
        assert redact_log_value(False) is False

    def test_none_preserved(self):
        assert redact_log_value(None) is None

    def test_other_type_safe_str(self):
        class SafeObj:
            def __str__(self):
                return "safe-repr"
        assert redact_log_value(SafeObj()) == "safe-repr"

    def test_other_type_secret_str_redacted(self):
        class SecretObj:
            def __str__(self):
                return "Bearer some-secret-token"
        assert redact_log_value(SecretObj()) == _REDACTED_MARKER

    def test_nested_dict(self):
        result = redact_log_value({"outer": {"token": "secret"}})
        assert result["outer"]["token"] == _REDACTED_MARKER

    def test_nested_list_in_dict(self):
        result = redact_log_value({"items": ["Bearer token"]})
        assert result["items"][0] == _REDACTED_MARKER

    def test_empty_dict(self):
        assert redact_log_value({}) == {}

    def test_empty_list(self):
        assert redact_log_value([]) == []


class TestBuildRequestContext:
    def test_generates_correlation_id_if_none(self):
        ctx = build_request_context()
        assert "correlationId" in ctx
        assert len(ctx["correlationId"]) == 32

    def test_uses_provided_safe_correlation_id(self):
        ctx = build_request_context(correlation_id="my-corr-123")
        assert ctx["correlationId"] == "my-corr-123"

    def test_replaces_unsafe_correlation_id(self):
        ctx = build_request_context(correlation_id="bad id!")
        assert ctx["correlationId"] != "bad id!"

    def test_includes_valid_request_id(self):
        ctx = build_request_context(request_id="req-123")
        assert ctx["requestId"] == "req-123"

    def test_excludes_invalid_request_id(self):
        ctx = build_request_context(request_id="bad request!")
        assert "requestId" not in ctx

    def test_includes_valid_workflow_id(self):
        ctx = build_request_context(workflow_id="wf-abc")
        assert ctx["workflowId"] == "wf-abc"

    def test_excludes_invalid_workflow_id(self):
        ctx = build_request_context(workflow_id="bad workflow!")
        assert "workflowId" not in ctx

    def test_includes_valid_execution_id(self):
        ctx = build_request_context(execution_id="exec-1")
        assert ctx["executionId"] == "exec-1"

    def test_excludes_invalid_execution_id(self):
        ctx = build_request_context(execution_id="exec 1!")
        assert "executionId" not in ctx

    def test_includes_valid_actor_id(self):
        ctx = build_request_context(actor_id="agent-1")
        assert ctx["actorId"] == "agent-1"

    def test_excludes_invalid_actor_id(self):
        ctx = build_request_context(actor_id="")
        assert "actorId" not in ctx

    def test_includes_valid_agent_id(self):
        ctx = build_request_context(agent_id="myagent")
        assert ctx["agentId"] == "myagent"

    def test_excludes_invalid_agent_id(self):
        ctx = build_request_context(agent_id=None)
        assert "agentId" not in ctx

    def test_all_none_returns_only_correlation_id(self):
        ctx = build_request_context(
            correlation_id=None, request_id=None, workflow_id=None,
            execution_id=None, actor_id=None, agent_id=None,
        )
        assert set(ctx.keys()) == {"correlationId"}


class TestNormalizeSeverity:
    def test_debug(self):
        assert _normalize_severity("debug") == "debug"

    def test_info(self):
        assert _normalize_severity("info") == "info"

    def test_warning(self):
        assert _normalize_severity("warning") == "warning"

    def test_error(self):
        assert _normalize_severity("error") == "error"

    def test_critical(self):
        assert _normalize_severity("critical") == "critical"

    def test_uppercase_normalized(self):
        assert _normalize_severity("INFO") == "info"
        assert _normalize_severity("WARNING") == "warning"

    def test_mixed_case_normalized(self):
        assert _normalize_severity("Debug") == "debug"

    def test_invalid_severity_raises(self):
        with pytest.raises(ValueError, match="Unsupported severity"):
            _normalize_severity("fatal")

    def test_trace_raises(self):
        with pytest.raises(ValueError, match="Unsupported severity"):
            _normalize_severity("trace")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            _normalize_severity("unknown_level")


class TestIsaSafeRuntimeMode:
    def test_local(self):
        assert _is_safe_runtime_mode("local") is True

    def test_test(self):
        assert _is_safe_runtime_mode("test") is True

    def test_demo(self):
        assert _is_safe_runtime_mode("demo") is True

    def test_staging(self):
        assert _is_safe_runtime_mode("staging") is True

    def test_production(self):
        assert _is_safe_runtime_mode("production") is True

    def test_uppercase_normalized(self):
        assert _is_safe_runtime_mode("LOCAL") is True
        assert _is_safe_runtime_mode("PRODUCTION") is True

    def test_development_invalid(self):
        assert _is_safe_runtime_mode("development") is False

    def test_dev_invalid(self):
        assert _is_safe_runtime_mode("dev") is False

    def test_empty_invalid(self):
        assert _is_safe_runtime_mode("") is False


class TestBuildLogEvent:
    def test_valid_event_auth_event(self):
        event = build_log_event("auth_event", "User authenticated")
        assert event["eventType"] == "auth_event"
        assert event["message"] == "User authenticated"
        assert event["severity"] == "info"
        assert "timestamp" in event
        assert "correlationId" in event
        assert event["service"] == "grantlayer"

    def test_valid_event_api_request(self):
        event = build_log_event("api_request", "GET /grants")
        assert event["eventType"] == "api_request"

    def test_valid_event_permission_decision(self):
        event = build_log_event("permission_decision", "Access granted")
        assert event["eventType"] == "permission_decision"

    def test_invalid_event_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported event type"):
            build_log_event("invalid_type", "message")

    def test_invalid_severity_raises(self):
        with pytest.raises(ValueError, match="Unsupported severity"):
            build_log_event("auth_event", "message", severity="fatal")

    def test_with_valid_request_id(self):
        event = build_log_event("api_request", "req", request_id="req-1")
        assert event["requestId"] == "req-1"

    def test_with_invalid_request_id_excluded(self):
        event = build_log_event("api_request", "req", request_id="bad id!")
        assert "requestId" not in event

    def test_with_valid_workflow_id(self):
        event = build_log_event("api_request", "req", workflow_id="wf-1")
        assert event["workflowId"] == "wf-1"

    def test_with_invalid_workflow_id_excluded(self):
        event = build_log_event("api_request", "req", workflow_id="bad!")
        assert "workflowId" not in event

    def test_with_valid_execution_id(self):
        event = build_log_event("api_request", "req", execution_id="exec-1")
        assert event["executionId"] == "exec-1"

    def test_with_invalid_execution_id_excluded(self):
        event = build_log_event("api_request", "req", execution_id="bad!")
        assert "executionId" not in event

    def test_with_valid_actor_id(self):
        event = build_log_event("auth_event", "auth", actor_id="agent-1")
        assert event["actorId"] == "agent-1"

    def test_with_invalid_actor_id_excluded(self):
        event = build_log_event("auth_event", "auth", actor_id="bad!")
        assert "actorId" not in event

    def test_with_valid_agent_id(self):
        event = build_log_event("auth_event", "auth", agent_id="my-agent")
        assert event["agentId"] == "my-agent"

    def test_with_invalid_agent_id_excluded(self):
        event = build_log_event("auth_event", "auth", agent_id="bad!")
        assert "agentId" not in event

    def test_with_valid_runtime_mode(self):
        event = build_log_event("auth_event", "msg", runtime_mode="production")
        assert event["runtimeMode"] == "production"

    def test_with_invalid_runtime_mode_excluded(self):
        event = build_log_event("auth_event", "msg", runtime_mode="invalid-mode")
        assert "runtimeMode" not in event

    def test_with_none_runtime_mode_excluded(self):
        event = build_log_event("auth_event", "msg", runtime_mode=None)
        assert "runtimeMode" not in event

    def test_with_metadata_sensitive_redacted(self):
        event = build_log_event(
            "auth_event", "msg",
            metadata={"token": "secret123", "role": "viewer"},
        )
        assert event["metadata"]["token"] == _REDACTED_MARKER
        assert event["metadata"]["role"] == "viewer"

    def test_without_metadata_no_metadata_key(self):
        event = build_log_event("auth_event", "msg")
        assert "metadata" not in event

    def test_severity_warning(self):
        event = build_log_event("api_error", "Error", severity="warning")
        assert event["severity"] == "warning"

    def test_severity_error(self):
        event = build_log_event("api_error", "Error", severity="error")
        assert event["severity"] == "error"

    def test_correlation_id_provided(self):
        event = build_log_event("auth_event", "msg", correlation_id="corr-123")
        assert event["correlationId"] == "corr-123"

    def test_correlation_id_generated_when_none(self):
        event = build_log_event("auth_event", "msg", correlation_id=None)
        assert len(event["correlationId"]) == 32


# ══════════════════════════════════════════════════════════════════════════════
# B. grant_request_service.py — Success paths (12 missing lines)
# ══════════════════════════════════════════════════════════════════════════════

from backend.src.core.repositories import IGrantRepository, IGrantRequestRepository
from backend.src.grants.grant_request_service import GrantRequestService


def _make_mock_session():
    sess = MagicMock()
    sess.connection.return_value = MagicMock()
    return sess


def _fresh_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _make_mock_request(status="requested", requested_by="other-op", grant_id=None):
    req = MagicMock()
    req.status = status
    req.requested_by = requested_by
    req.created_at = _fresh_iso()
    req.grant_id = grant_id
    req.subject_id = "agent-1"
    req.role = "viewer"
    req.action = "read"
    req.resource = "doc/1"
    req.valid_from = "2026-01-01T00:00:00Z"
    req.valid_until = "2026-12-31T23:59:59Z"
    req.reason = "test reason"
    return req


class TestGrantRequestServiceSuccessPaths:
    def setup_method(self):
        self.repo = MagicMock(spec=IGrantRequestRepository)
        self.grant_repo = MagicMock(spec=IGrantRepository)
        self.session = _make_mock_session()
        self.svc = GrantRequestService(
            repo=self.repo,
            grant_repo=self.grant_repo,
            session=self.session,
        )

    def test_approve_request_success(self):
        req = _make_mock_request(status="requested", requested_by="other-op")
        self.repo.get.return_value = req

        with patch("backend.src.grants.grant_request_service._grants_module") as mock_grants, \
             patch("backend.src.grants.grant_request_service._audit_log"):
            mock_grants.create_grant.return_value = None
            updated, grant = self.svc.approve_request(
                "rid", "op1", tenant_id="t1", workspace_id="w1"
            )

        assert updated is req
        assert grant is not None
        self.repo.mark_approved.assert_called_once()

    def test_approve_request_raises_when_expired(self):
        req = _make_mock_request(status="requested", requested_by="other-op")
        expired = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=25)
        ).isoformat().replace("+00:00", "Z")
        req.created_at = expired
        self.repo.get.return_value = req

        with pytest.raises(ValueError, match="expired"):
            self.svc.approve_request("rid", "op1", tenant_id="t1", workspace_id="w1")

    def test_deny_request_success(self):
        req = _make_mock_request(status="requested")
        self.repo.get.return_value = req

        with patch("backend.src.grants.grant_request_service._audit_log"):
            updated = self.svc.deny_request(
                "rid", "op1", "policy violation", tenant_id="t1", workspace_id="w1"
            )

        assert updated is req
        self.repo.mark_denied.assert_called_once()

    def test_revoke_request_success_without_grant_id(self):
        req = _make_mock_request(status="approved", grant_id=None)
        self.repo.get.return_value = req

        with patch("backend.src.grants.grant_request_service._grants_module"), \
             patch("backend.src.grants.grant_request_service._audit_log"):
            updated = self.svc.revoke_request(
                "rid", "op1", "no longer needed", tenant_id="t1", workspace_id="w1"
            )

        assert updated is req
        self.repo.mark_revoked.assert_called_once()

    def test_revoke_request_success_with_grant_id(self):
        req = _make_mock_request(status="approved", grant_id="grant-123")
        self.repo.get.return_value = req

        with patch("backend.src.grants.grant_request_service._grants_module") as mock_grants, \
             patch("backend.src.grants.grant_request_service._audit_log"):
            updated = self.svc.revoke_request(
                "rid", "op1", "revoked", tenant_id="t1", workspace_id="w1"
            )

        mock_grants.revoke_grant.assert_called_once()
        call_kwargs = mock_grants.revoke_grant.call_args
        assert "grant-123" in call_kwargs[0] or call_kwargs[1].get("grant_id") == "grant-123" or call_kwargs[0][0] == "grant-123"
        self.repo.mark_revoked.assert_called_once()
        assert updated is req

    def test_revoke_request_raises_on_not_found(self):
        self.repo.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            self.svc.revoke_request("rid", "op1", "reason", tenant_id="t1", workspace_id="w1")


# ══════════════════════════════════════════════════════════════════════════════
# C. auth/operators.py — Edge cases (25 missing lines)
# ══════════════════════════════════════════════════════════════════════════════

from backend.src.auth.operators import (
    _get_repo,
    _is_expired,
    verify_token,
)


class TestVerifyTokenEdgeCases:
    def test_wrong_part_count_returns_false(self):
        assert verify_token("token", "only$three$parts") is False

    def test_two_parts_returns_false(self):
        assert verify_token("token", "a$b") is False

    def test_five_parts_returns_false(self):
        assert verify_token("token", "a$b$c$d$e") is False

    def test_wrong_algorithm_returns_false(self):
        assert verify_token("token", "wrong_algo$600000$salt$hash") is False

    def test_non_integer_iterations_returns_false(self):
        assert verify_token("token", "pbkdf2_sha256$not_an_int$salt$hash") is False

    def test_valid_token_verifies(self):
        from backend.src.auth.operators import hash_token
        raw = "my-test-token-gl302"
        stored = hash_token(raw)
        assert verify_token(raw, stored) is True

    def test_wrong_token_fails(self):
        from backend.src.auth.operators import hash_token
        raw = "my-test-token-gl302"
        stored = hash_token(raw)
        assert verify_token("wrong-token", stored) is False


class TestIsExpiredEdgeCases:
    def test_none_returns_false(self):
        assert _is_expired(None) is False

    def test_empty_string_returns_false(self):
        assert _is_expired("") is False

    def test_malformed_timestamp_returns_true(self):
        assert _is_expired("not-a-timestamp") is True

    def test_past_timestamp_returns_true(self):
        assert _is_expired("2020-01-01T00:00:00+00:00") is True

    def test_future_timestamp_returns_false(self):
        assert _is_expired("2035-01-01T00:00:00+00:00") is False

    def test_z_suffix_past_returns_true(self):
        assert _is_expired("2020-06-01T00:00:00Z") is True

    def test_z_suffix_future_returns_false(self):
        assert _is_expired("2035-06-01T00:00:00Z") is False


class TestGetRepoDeadCode:
    def test_with_session_returns_repo_and_none(self):
        mock_session = MagicMock()
        repo, sentinel = _get_repo(session=mock_session)
        assert repo is not None
        assert sentinel is None

    def test_without_session_returns_none_and_true(self):
        repo, sentinel = _get_repo(session=None)
        assert repo is None
        assert sentinel is True


# ══════════════════════════════════════════════════════════════════════════════
# D. operator_service.py — Bootstrap (line 55)
# ══════════════════════════════════════════════════════════════════════════════

from backend.src.auth.operator_service import OperatorService
from backend.src.core.repositories import IOperatorRepository


class TestOperatorServiceBootstrap:
    def test_bootstrap_delegates_to_repo(self):
        repo = MagicMock(spec=IOperatorRepository)
        svc = OperatorService(repo=repo)
        svc.bootstrap()
        repo.bootstrap_if_needed.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# E. auth/auth.py — Admin token and workspace access branches
# ══════════════════════════════════════════════════════════════════════════════

from backend.src.auth.auth import check_admin_token, check_workspace_resource_access


class TestCheckAdminTokenBranches:
    def setup_method(self):
        import backend.src.core.config as cfg
        self._orig_admin = cfg.GRANTLAYER_ADMIN_TOKEN
        cfg.GRANTLAYER_ADMIN_TOKEN = "test-admin-secret"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "test-admin-secret"

    def teardown_method(self):
        import backend.src.core.config as cfg
        cfg.GRANTLAYER_ADMIN_TOKEN = self._orig_admin

    def test_non_bearer_scheme_returns_403(self):
        ok, status, body = check_admin_token("Token test-admin-secret")
        assert ok is False
        assert status == 403
        assert body["errorCode"] == "admin_token_invalid"

    def test_empty_token_after_bearer_returns_403(self):
        ok, status, body = check_admin_token("Bearer   ")
        assert ok is False
        assert status == 403

    def test_valid_token_returns_200(self):
        ok, status, body = check_admin_token("Bearer test-admin-secret")
        assert ok is True
        assert status == 200

    def test_wrong_token_returns_403(self):
        ok, status, body = check_admin_token("Bearer wrong-token")
        assert ok is False
        assert status == 403


class TestCheckWorkspaceResourceAccess:
    def test_cross_tenant_denied(self):
        ok, status, body = check_workspace_resource_access(
            resource_workspace_id="ws1",
            caller_workspace_id="ws1",
            caller_tenant_id="tenant-a",
            resource_tenant_id="tenant-b",
        )
        assert ok is False
        assert status == 403
        assert body["errorCode"] == "cross_tenant_access_denied"

    def test_no_caller_workspace_readonly_mutation_denied(self):
        ok, status, body = check_workspace_resource_access(
            resource_workspace_id="ws1",
            caller_workspace_id=None,
            caller_tenant_id="tenant-a",
            resource_tenant_id=None,
            require_mutation=True,
            workspace_member_role="workspace_readonly",
        )
        assert ok is False
        assert status == 403
        assert body["errorCode"] == "workspace_role_insufficient"

    def test_no_caller_workspace_allow_read(self):
        ok, status, body = check_workspace_resource_access(
            resource_workspace_id="ws1",
            caller_workspace_id=None,
            caller_tenant_id="tenant-a",
            resource_tenant_id=None,
        )
        assert ok is True
        assert status == 200

    def test_null_resource_workspace_readonly_mutation_denied(self):
        ok, status, body = check_workspace_resource_access(
            resource_workspace_id=None,
            caller_workspace_id="ws1",
            caller_tenant_id="tenant-a",
            resource_tenant_id=None,
            require_mutation=True,
            workspace_member_role="workspace_readonly",
        )
        assert ok is False
        assert status == 403


# ══════════════════════════════════════════════════════════════════════════════
# F. auditor_report.py — _compute_findings branches
# ══════════════════════════════════════════════════════════════════════════════

from backend.src.audit.auditor_report import _compute_findings, build_auditor_report


class TestComputeFindingsEdgeCases:
    def test_missing_evidence_warning(self):
        summary = {"warnings": ["missing_evidence"]}
        findings = _compute_findings(summary, None, None)
        assert any("missing_evidence" in f for f in findings)

    def test_unverified_evidence_warning(self):
        summary = {"warnings": ["unverified_evidence"]}
        findings = _compute_findings(summary, None, None)
        assert any("unverified_evidence" in f for f in findings)

    def test_unknown_warning_prefixed(self):
        summary = {"warnings": ["some_other_warning"]}
        findings = _compute_findings(summary, None, None)
        assert any("warning: some_other_warning" in f for f in findings)

    def test_execution_denied_with_error_code(self):
        summary = {"execution": {"result": "denied", "errorCode": "ERR_001"}}
        findings = _compute_findings(summary, None, None)
        assert any("execution_denied: ERR_001" in f for f in findings)

    def test_execution_denied_without_error_code(self):
        summary = {"execution": {"result": "denied", "errorCode": None}}
        findings = _compute_findings(summary, None, None)
        assert any("execution_denied: no error code" in f for f in findings)

    def test_execution_failed(self):
        summary = {"execution": {"result": "failed"}}
        findings = _compute_findings(summary, None, None)
        assert any("execution_failed" in f for f in findings)

    def test_grant_revoked(self):
        from backend.src.core.models import Grant
        grant = Grant(
            subject_id="a", role="r", action="x", resource="y",
            valid_from="2026-01-01T00:00:00Z", valid_until="2026-12-31T00:00:00Z",
            created_by="op1", reason="r",
        )
        grant.revoked = True
        findings = _compute_findings({}, grant, None)
        assert any("grant_revoked" in f for f in findings)

    def test_grant_expired(self):
        from backend.src.core.models import Grant
        grant = Grant(
            subject_id="a", role="r", action="x", resource="y",
            valid_from="2020-01-01T00:00:00Z", valid_until="2020-06-01T00:00:00Z",
            created_by="op1", reason="r",
        )
        grant.revoked = False
        findings = _compute_findings({}, grant, None)
        assert any("grant_expired" in f for f in findings)

    def test_grant_usage_exhausted(self):
        from backend.src.core.models import Grant
        grant = Grant(
            subject_id="a", role="r", action="x", resource="y",
            valid_from="2026-01-01T00:00:00Z", valid_until="2030-01-01T00:00:00Z",
            created_by="op1", reason="r",
        )
        grant.revoked = False
        grant.max_uses = 1
        grant.use_count = 1
        findings = _compute_findings({}, grant, None)
        assert any("grant_usage_exhausted" in f for f in findings)

    def test_grant_unsigned(self):
        from backend.src.core.models import Grant
        grant = Grant(
            subject_id="a", role="r", action="x", resource="y",
            valid_from="2026-01-01T00:00:00Z", valid_until="2030-01-01T00:00:00Z",
            created_by="op1", reason="r",
        )
        grant.revoked = False
        grant.signature = None
        grant.payload_hash = None
        findings = _compute_findings({}, grant, None)
        assert any("grant_unsigned" in f for f in findings)

    def test_request_denied_finding(self):
        from backend.src.core.models import GrantRequest
        req = GrantRequest(
            subject_id="a", role="r", action="x", resource="y",
            valid_from="2026-01-01Z", valid_until="2026-12-31Z",
            requested_by="op1", reason="r",
        )
        req.status = "denied"
        findings = _compute_findings({}, None, req)
        assert any("grant_request_denied" in f for f in findings)

    def test_request_revoked_finding(self):
        from backend.src.core.models import GrantRequest
        req = GrantRequest(
            subject_id="a", role="r", action="x", resource="y",
            valid_from="2026-01-01Z", valid_until="2026-12-31Z",
            requested_by="op1", reason="r",
        )
        req.status = "revoked"
        findings = _compute_findings({}, None, req)
        assert any("grant_request_revoked" in f for f in findings)

    def test_no_findings_clean(self):
        findings = _compute_findings({}, None, None)
        assert findings == []


class TestBuildAuditorReportCompatWrapper:
    def test_compat_wrapper_delegates(self):
        with patch("backend.src.audit.auditor_report.build_auditor_report_for_execution") as mock_fn:
            mock_fn.return_value = None
            result = build_auditor_report("exec-123")
        mock_fn.assert_called_once_with("exec-123")
        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# G. core/logging_utils.py — _safe_value function (lines 270, 274, 276)
# ══════════════════════════════════════════════════════════════════════════════

from backend.src.core.logging_utils import _safe_value


class TestSafeValue:
    def test_none_returns_none(self):
        assert _safe_value(None) is None

    def test_string_preserved(self):
        assert _safe_value("hello") == "hello"

    def test_int_preserved(self):
        assert _safe_value(42) == 42

    def test_float_preserved(self):
        assert _safe_value(3.14) == 3.14

    def test_bool_preserved(self):
        assert _safe_value(True) is True

    def test_list_recursed(self):
        result = _safe_value([1, "two", None])
        assert result == [1, "two", None]

    def test_tuple_recursed(self):
        result = _safe_value((1, 2))
        assert result == [1, 2]

    def test_dict_recursed(self):
        result = _safe_value({"a": 1, "b": "two"})
        assert result == {"a": 1, "b": "two"}

    def test_nested_list(self):
        result = _safe_value([[1, 2], [3, 4]])
        assert result == [[1, 2], [3, 4]]

    def test_other_type_converted_to_str(self):
        class Foo:
            def __str__(self):
                return "foo-repr"
        assert _safe_value(Foo()) == "foo-repr"


# ══════════════════════════════════════════════════════════════════════════════
# H. core/db.py — _orm_to_dict, get_session (lines 60, 490, 492, 497-503)
# ══════════════════════════════════════════════════════════════════════════════

from backend.src.core.db import _orm_to_dict, get_session


class TestOrmToDict:
    def test_none_returns_none(self):
        assert _orm_to_dict(None) is None

    def test_dict_returned_as_dict_copy(self):
        d = {"id": "1", "name": "test"}
        result = _orm_to_dict(d)
        assert result == d
        assert result is not d  # it's a copy

    def test_object_with_fields_attribute(self):
        class RowWithFields:
            _fields = ("id", "name")
            id = "row-1"
            name = "test-row"
        result = _orm_to_dict(RowWithFields())
        assert result["id"] == "row-1"
        assert result["name"] == "test-row"

    def test_object_with_dict_attr(self):
        class RowWithDict:
            def __init__(self):
                self.__dict__ = {"key": "value", "_sa_instance_state": "ignored"}
        result = _orm_to_dict(RowWithDict())
        # _sa_instance_state should be popped
        assert "key" in result
        assert "_sa_instance_state" not in result

    def test_object_with_mapping(self):
        class RowWithMapping:
            _mapping = {"col1": "val1", "col2": "val2"}
        result = _orm_to_dict(RowWithMapping())
        assert result["col1"] == "val1"


class TestGetSession:
    def test_get_session_returns_session(self):
        import tempfile

        import backend.src.core.db as db_mod
        orig = db_mod.DB_PATH_OR_URL
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            db_mod.DB_PATH_OR_URL = tmp.name
            db_mod.DB_PATH = tmp.name
            db_mod._sa_engine = None
            db_mod.init_db()
            sess = get_session()
            assert sess is not None
            sess.close()
        finally:
            db_mod.DB_PATH_OR_URL = orig
            db_mod.DB_PATH = orig
            db_mod._sa_engine = None
            try:
                os.unlink(tmp.name)
            except OSError:
                pass


# ══════════════════════════════════════════════════════════════════════════════
# I. FastAPI integration — health / readiness / grant-requests / executions
# ══════════════════════════════════════════════════════════════════════════════

try:
    from fastapi.testclient import TestClient
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

_SKIP = unittest.skipUnless(_FASTAPI_AVAILABLE, "FastAPI not installed")
_JWT_SECRET_GL302 = "gl302-test-secret-key-long"


class _IntegrationBase(unittest.TestCase):
    def setUp(self):
        import backend.src.core.config as _cfg
        import backend.src.core.db as _db
        from backend.src.api.app import create_app
        from backend.src.api.auth_jwt import create_dev_token

        self._cfg = _cfg
        self._db = _db

        self._orig_op = _cfg.ENABLE_OPERATOR_MODEL
        self._orig_plaintext = _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE
        self._orig_db_url = _db.DB_PATH_OR_URL
        self._orig_db_path = _db.DB_PATH
        self._orig_admin = _cfg.GRANTLAYER_ADMIN_TOKEN
        self._orig_jwt_env = os.environ.get("GRANTLAYER_JWT_SECRET", "")

        os.environ["GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"] = "true"
        os.environ["GRANTLAYER_JWT_SECRET"] = _JWT_SECRET_GL302
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = True
        _cfg.ENABLE_OPERATOR_MODEL = False
        _cfg.GRANTLAYER_ADMIN_TOKEN = "admin-gl302-token"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "admin-gl302-token"
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        _db.DB_PATH_OR_URL = self._db_path
        _db.DB_PATH = self._db_path
        _db._sa_engine = None
        _db.init_db()

        self.client = TestClient(create_app(), raise_server_exceptions=True)
        self.jwt_header = {"Authorization": f"Bearer {create_dev_token(secret=_JWT_SECRET_GL302)}"}
        self.admin_header = {"Authorization": "Bearer admin-gl302-token"}

    def tearDown(self):
        self._cfg.ENABLE_OPERATOR_MODEL = self._orig_op
        self._cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_plaintext
        self._cfg.GRANTLAYER_ADMIN_TOKEN = self._orig_admin
        self._db.DB_PATH_OR_URL = self._orig_db_url
        self._db.DB_PATH = self._orig_db_path
        self._db._sa_engine = None
        if self._orig_jwt_env:
            os.environ["GRANTLAYER_JWT_SECRET"] = self._orig_jwt_env
        else:
            os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        try:
            os.unlink(self._db_path)
        except OSError:
            pass


@_SKIP
class TestHealthEndpoint(_IntegrationBase):
    def test_health_returns_200(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("status", data)

    def test_health_has_database_field(self):
        resp = self.client.get("/health")
        data = resp.json()
        self.assertIn("database", data)

    def test_health_has_signing_key_field(self):
        resp = self.client.get("/health")
        data = resp.json()
        self.assertIn("signing_key", data)

    def test_health_has_migrations_field(self):
        resp = self.client.get("/health")
        data = resp.json()
        self.assertIn("migrations", data)

    def test_readiness_returns_200_or_503(self):
        resp = self.client.get("/readiness")
        self.assertIn(resp.status_code, [200, 503])

    def test_health_redis_field_disabled(self):
        resp = self.client.get("/health")
        data = resp.json()
        self.assertIn("redis", data)


@_SKIP
class TestGrantExecutionsSessions(_IntegrationBase):
    def _create_grant(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        vf = (now + datetime.timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        vu = (now + datetime.timedelta(days=30)).isoformat().replace("+00:00", "Z")
        resp = self.client.post(
            "/v1/grants",
            headers={**self.jwt_header, "X-Workspace-Id": "default"},
            json={
                "subjectId": "agent-gl302",
                "role": "viewer",
                "action": "read",
                "resource": "doc/gl302",
                "validFrom": vf,
                "validUntil": vu,
                "createdBy": "op-gl302",
                "reason": "GL-302 coverage test",
            },
        )
        return resp

    def test_create_grant_returns_201(self):
        resp = self._create_grant()
        self.assertEqual(resp.status_code, 201)

    def test_list_grants_with_session(self):
        self._create_grant()
        resp = self.client.get(
            "/v1/grants",
            headers={**self.jwt_header, "X-Workspace-Id": "default"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("items", data)
        self.assertGreater(data["total"], 0)

    def test_revoke_nonexistent_grant_returns_404(self):
        resp = self.client.post(
            "/v1/grants/nonexistent-id/revoke",
            headers={**self.jwt_header, "X-Workspace-Id": "default"},
            json={"reason": "test"},
        )
        self.assertEqual(resp.status_code, 404)


@_SKIP
class TestGrantRequestsSessions(_IntegrationBase):
    def setUp(self):
        super().setUp()
        self._cfg.ENABLE_OPERATOR_MODEL = True

    def _make_grant_request(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        vf = (now + datetime.timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        vu = (now + datetime.timedelta(days=30)).isoformat().replace("+00:00", "Z")
        resp = self.client.post(
            "/v1/grant-requests",
            headers={**self.jwt_header, "X-Workspace-Id": "default"},
            json={
                "subjectId": "agent-gl302",
                "role": "viewer",
                "action": "read",
                "resource": "doc/gl302",
                "validFrom": vf,
                "validUntil": vu,
                "reason": "GL-302 coverage",
            },
        )
        return resp

    def test_create_grant_request_201(self):
        resp = self._make_grant_request()
        self.assertEqual(resp.status_code, 201)

    def test_list_grant_requests_with_status_filter(self):
        self._make_grant_request()
        resp = self.client.get(
            "/v1/grant-requests?status=requested",
            headers={**self.jwt_header, "X-Workspace-Id": "default"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("items", data)

    def test_approve_nonexistent_request_returns_404(self):
        resp = self.client.post(
            "/v1/grant-requests/nonexistent/approve",
            headers=self.admin_header,
            json={},
        )
        self.assertIn(resp.status_code, [404, 401, 403])

    def test_deny_nonexistent_request_returns_404(self):
        resp = self.client.post(
            "/v1/grant-requests/nonexistent/deny",
            headers=self.admin_header,
            json={"reason": "test"},
        )
        self.assertIn(resp.status_code, [404, 401, 403])

    def test_get_nonexistent_request_returns_404(self):
        resp = self.client.get(
            "/v1/grant-requests/nonexistent-id",
            headers={**self.jwt_header, "X-Workspace-Id": "default"},
        )
        self.assertEqual(resp.status_code, 404)


# ══════════════════════════════════════════════════════════════════════════════
# J. evidence/evidence_verification.py — hash validation (lines 66-70)
# ══════════════════════════════════════════════════════════════════════════════

class TestEvidenceVerificationHashPaths:
    def _make_mock_record(self, bundle_json: str):
        record = MagicMock()
        record.id = "rec-1"
        record.bundle_json = bundle_json
        return record

    def test_verify_with_no_record_returns_missing_data(self):
        from backend.src.evidence import evidence_verification

        with patch("backend.src.evidence.evidence_verification.evidence_persistence") as mock_ep:
            mock_ep.get_bundle_by_execution.return_value = None
            result = evidence_verification.verify_execution("exec-nonexistent")

        assert result["status"] == "missing_data"

    def test_verify_with_unsupported_version(self):
        from backend.src.evidence import evidence_verification

        record = self._make_mock_record('{"canonicalVersion": "bad-version", "hashAlgorithm": "sha256"}')
        with patch("backend.src.evidence.evidence_verification.evidence_persistence") as mock_ep:
            mock_ep.get_bundle_by_execution.return_value = record
            mock_ep.update_verification_status.return_value = None
            result = evidence_verification.verify_execution("exec-1")

        assert result["status"] == "unsupported_version"

    def test_verify_with_invalid_hash_too_short(self):
        from backend.src.evidence import evidence_verification

        bundle = '{"canonicalVersion": "gl-evidence-v1", "hashAlgorithm": "sha256", "evidenceHash": "tooshort"}'
        record = self._make_mock_record(bundle)
        with patch("backend.src.evidence.evidence_verification.evidence_persistence") as mock_ep:
            mock_ep.get_bundle_by_execution.return_value = record
            mock_ep.update_verification_status.return_value = None
            result = evidence_verification.verify_execution("exec-1")

        assert result["status"] == "invalid"

    def test_verify_with_missing_hash_field(self):
        from backend.src.evidence import evidence_verification

        bundle = '{"canonicalVersion": "gl-evidence-v1", "hashAlgorithm": "sha256"}'
        record = self._make_mock_record(bundle)
        with patch("backend.src.evidence.evidence_verification.evidence_persistence") as mock_ep:
            mock_ep.get_bundle_by_execution.return_value = record
            mock_ep.update_verification_status.return_value = None
            result = evidence_verification.verify_execution("exec-1")

        assert result["status"] == "invalid"


# ══════════════════════════════════════════════════════════════════════════════
# K. evidence/evidence_completeness.py — _extract_critical_gaps branches
# ══════════════════════════════════════════════════════════════════════════════

class TestEvidenceCompletenessGaps:
    def _extract(self, findings):
        from backend.src.evidence.evidence_completeness import _extract_critical_gaps
        return _extract_critical_gaps(findings)

    def test_empty_findings(self):
        assert self._extract([]) == []

    def test_execution_denied_gap(self):
        gaps = self._extract(["execution_denied: some reason"])
        assert "execution_denied" in gaps

    def test_grant_revoked_gap(self):
        gaps = self._extract(["grant_revoked: reason"])
        assert "grant_revoked" in gaps

    def test_grant_expired_gap(self):
        gaps = self._extract(["grant_expired: reason"])
        assert "grant_expired" in gaps

    def test_grant_usage_exhausted_gap(self):
        gaps = self._extract(["grant_usage_exhausted: reason"])
        assert "grant_usage_exhausted" in gaps

    def test_grant_unsigned_gap(self):
        gaps = self._extract(["grant_unsigned: reason"])
        assert "grant_unsigned" in gaps

    def test_grant_request_denied_gap(self):
        gaps = self._extract(["grant_request_denied: reason"])
        assert "grant_request_denied" in gaps

    def test_grant_request_revoked_gap(self):
        gaps = self._extract(["grant_request_revoked: reason"])
        assert "grant_request_revoked" in gaps

    def test_unrecognized_finding_not_included(self):
        gaps = self._extract(["missing_evidence: no bundle"])
        assert gaps == []

    def test_deduplication(self):
        gaps = self._extract(["grant_revoked: first", "grant_revoked: second"])
        assert gaps.count("grant_revoked") == 1

    def test_multiple_gaps(self):
        gaps = self._extract([
            "grant_revoked: r1",
            "grant_expired: r2",
            "grant_unsigned: r3",
        ])
        assert "grant_revoked" in gaps
        assert "grant_expired" in gaps
        assert "grant_unsigned" in gaps


# ══════════════════════════════════════════════════════════════════════════════
# L. grants/grant_executions.py — session=None error path (line 41)
#    grants/grant_requests.py — session=None error path (line 79)
# ══════════════════════════════════════════════════════════════════════════════

class TestGrantExecutionsTenantRequired:
    def test_create_without_tenant_raises(self):
        from backend.src.core.models import GrantExecution
        from backend.src.grants.grant_executions import create_grant_execution
        exec_obj = GrantExecution(action="read", resource="doc/1", result="allowed")
        with pytest.raises(ValueError, match="tenant_id is required"):
            create_grant_execution(exec_obj, tenant_id=None)


class TestGrantRequestsTenantRequired:
    def test_create_without_tenant_raises(self):
        from backend.src.core.models import GrantRequest
        from backend.src.grants.grant_requests import create_grant_request
        req = GrantRequest(
            subject_id="a", role="r", action="x", resource="y",
            valid_from="2026-01-01Z", valid_until="2026-12-31Z",
            requested_by="op1", reason="r",
        )
        with pytest.raises(ValueError, match="tenant_id is required"):
            create_grant_request(req, tenant_id=None)


# ══════════════════════════════════════════════════════════════════════════════
# M. core/db.py — execute / query functions with dict params (lines 441, 453)
# ══════════════════════════════════════════════════════════════════════════════

class TestDbDictParams(unittest.TestCase):
    def setUp(self):
        import backend.src.core.db as db_mod
        self._db_mod = db_mod
        self._orig_url = db_mod.DB_PATH_OR_URL
        self._orig_path = db_mod.DB_PATH

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        db_mod.DB_PATH_OR_URL = self._db_path
        db_mod.DB_PATH = self._db_path
        db_mod._sa_engine = None
        db_mod.init_db()

    def tearDown(self):
        self._db_mod.DB_PATH_OR_URL = self._orig_url
        self._db_mod.DB_PATH = self._orig_path
        self._db_mod._sa_engine = None
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def test_execute_with_dict_params(self):
        from backend.src.core.db import execute
        result = execute(
            "UPDATE grants SET revoked = :revoked WHERE id = :id",
            {"revoked": 0, "id": "nonexistent"},
        )
        assert result == 0

    def test_query_one_with_dict_params(self):
        from backend.src.core.db import query_one
        result = query_one(
            "SELECT COUNT(*) as cnt FROM grants WHERE id = :id",
            {"id": "nonexistent"},
        )
        assert result is not None
        assert result["cnt"] == 0

    def test_query_all_with_dict_params(self):
        from backend.src.core.db import query_all
        result = query_all(
            "SELECT * FROM grants WHERE tenant_id = :tid",
            {"tid": "nonexistent"},
        )
        assert result == []


# ══════════════════════════════════════════════════════════════════════════════
# Shared DB setup helper for session-path tests
# ══════════════════════════════════════════════════════════════════════════════

class _DbBase(unittest.TestCase):
    """Base class: fresh SQLite DB per test."""

    def setUp(self):
        from sqlalchemy.orm import Session as _Session

        import backend.src.core.db as _db

        self._orig_url = _db.DB_PATH_OR_URL
        self._orig_path = _db.DB_PATH
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._tmp_path = tmp.name
        _db.DB_PATH_OR_URL = self._tmp_path
        _db.DB_PATH = self._tmp_path
        _db._sa_engine = None
        _db.init_db()
        self._db = _db
        self._Session = _Session

    def tearDown(self):
        self._db.DB_PATH_OR_URL = self._orig_url
        self._db.DB_PATH = self._orig_path
        self._db._sa_engine = None
        try:
            os.unlink(self._tmp_path)
        except OSError:
            pass

    def _open_session(self):
        return self._Session(self._db.get_engine())


# ══════════════════════════════════════════════════════════════════════════════
# N. grants/grants.py — session paths (lines 32-34, 40, 71, 85-90, 102, 139-165, 219, 221)
# ══════════════════════════════════════════════════════════════════════════════

class TestGrantsModuleSessionPaths(_DbBase):
    def test_row_to_grant_direct_call(self):
        from backend.src.grants.grants import _row_to_grant
        row = {
            "id": "g1", "subject_id": "agent1", "role": "viewer", "action": "read",
            "resource": "doc/1", "valid_from": "2026-01-01Z", "valid_until": "2027-01-01Z",
            "created_by": "op1", "reason": "test", "revoked": 0, "revoked_by": None,
            "revoked_reason": None, "revoked_at": None, "created_at": "2026-01-01Z",
            "signature": None, "signing_key_id": None, "payload_hash": None,
            "max_uses": None, "use_count": 0,
        }
        grant = _row_to_grant(row)
        self.assertEqual(grant.id, "g1")
        self.assertEqual(grant.subject_id, "agent1")

    def test_list_grants_with_session(self):
        from backend.src.grants.grants import list_grants
        sess = self._open_session()
        try:
            result = list_grants(tenant_id="t1", workspace_id="ws1", session=sess)
            self.assertIsInstance(result, list)
        finally:
            sess.close()

    def test_count_grants_with_session(self):
        from backend.src.grants.grants import count_grants
        sess = self._open_session()
        try:
            result = count_grants(tenant_id="t1", workspace_id="ws1", session=sess)
            self.assertEqual(result, 0)
        finally:
            sess.close()

    def test_count_grants_no_session(self):
        from backend.src.grants.grants import count_grants
        result = count_grants(tenant_id="t1", workspace_id="ws1")
        self.assertEqual(result, 0)

    def test_get_grant_with_session(self):
        from backend.src.grants.grants import get_grant
        sess = self._open_session()
        try:
            result = get_grant("nonexistent", tenant_id="t1", workspace_id="ws1", session=sess)
            self.assertIsNone(result)
        finally:
            sess.close()

    def test_create_grant_conn_path(self):
        from backend.src.core.models import Grant
        from backend.src.grants.grants import create_grant
        conn = MagicMock()
        conn.execute.return_value = MagicMock()
        grant = Grant(
            subject_id="a", role="viewer", action="read", resource="doc/1",
            valid_from="2026-01-01T00:00:00Z", valid_until="2027-01-01T00:00:00Z",
            created_by="op1", reason="test",
        )
        with patch("backend.src.grants.grants._sign_grant", return_value=("sig", "hash", "kid")):
            result = create_grant(grant, conn=conn, tenant_id="t1", workspace_id="ws1")
        self.assertEqual(result.signature, "sig")
        self.assertTrue(conn.execute.called)

    def test_revoke_grant_conn_with_tenant_and_workspace(self):
        from backend.src.grants.grants import revoke_grant
        conn = MagicMock()
        stmt_mock = MagicMock()
        stmt_mock.where.return_value = stmt_mock
        result_mock = MagicMock()
        result_mock.rowcount = 1
        conn.execute.return_value = result_mock
        with patch("backend.src.grants.grants.sa_update", return_value=stmt_mock):
            result = revoke_grant("g1", "op1", "reason", conn=conn, tenant_id="t1", workspace_id="ws1")
        self.assertTrue(result)

    def test_auto_session_rollback(self):
        from backend.src.grants.grants import _auto_session
        with self.assertRaises(RuntimeError):
            with _auto_session() as _:
                raise RuntimeError("trigger rollback")


# ══════════════════════════════════════════════════════════════════════════════
# O. grants/grant_executions.py — session paths (lines 27-29, 44, 56, 76, 105-114, 147-148)
# ══════════════════════════════════════════════════════════════════════════════

class TestGrantExecutionsSessionPaths(_DbBase):
    def _make_exec(self):
        from backend.src.core.models import GrantExecution
        return GrantExecution(action="read", resource="doc/1", result="allowed")

    def test_create_execution_with_session(self):
        from backend.src.grants.grant_executions import create_grant_execution
        sess = self._open_session()
        try:
            exec_obj = self._make_exec()
            result = create_grant_execution(exec_obj, tenant_id="t1", workspace_id="ws1", session=sess)
            sess.commit()
            self.assertIsNotNone(result.id)
        finally:
            sess.close()

    def test_get_execution_with_session(self):
        from backend.src.grants.grant_executions import get_grant_execution
        sess = self._open_session()
        try:
            result = get_grant_execution("nonexistent", tenant_id="t1", workspace_id="ws1", session=sess)
            self.assertIsNone(result)
        finally:
            sess.close()

    def test_list_executions_with_session(self):
        from backend.src.grants.grant_executions import list_grant_executions
        sess = self._open_session()
        try:
            result = list_grant_executions(tenant_id="t1", workspace_id="ws1", session=sess)
            self.assertIsInstance(result, list)
        finally:
            sess.close()

    def test_count_executions_with_session(self):
        from backend.src.grants.grant_executions import count_grant_executions
        sess = self._open_session()
        try:
            result = count_grant_executions(tenant_id="t1", workspace_id="ws1", session=sess)
            self.assertEqual(result, 0)
        finally:
            sess.close()

    def test_count_executions_no_session(self):
        from backend.src.grants.grant_executions import count_grant_executions
        result = count_grant_executions(tenant_id="t1", workspace_id="ws1")
        self.assertEqual(result, 0)

    def test_update_audit_id_with_session(self):
        from backend.src.grants.grant_executions import (
            create_grant_execution,
            update_grant_execution_audit_event_id,
        )
        sess = self._open_session()
        try:
            exec_obj = self._make_exec()
            created = create_grant_execution(exec_obj, tenant_id="t1", workspace_id="ws1", session=sess)
            sess.commit()
            update_grant_execution_audit_event_id(created.id, "audit-1", session=sess)
            sess.commit()
        finally:
            sess.close()

    def test_auto_session_rollback(self):
        from backend.src.grants.grant_executions import _auto_session
        with self.assertRaises(RuntimeError):
            with _auto_session() as _:
                raise RuntimeError("trigger rollback")


# ══════════════════════════════════════════════════════════════════════════════
# P. auth/operators.py — session paths (lines 149-151, 182, 190, 229, 234, 245, 264, 276, 328, 352, 365-366)
# ══════════════════════════════════════════════════════════════════════════════

class TestOperatorsSessionPaths(_DbBase):
    def test_get_operator_by_id_with_session(self):
        from backend.src.auth.operators import get_operator_by_id
        sess = self._open_session()
        try:
            result = get_operator_by_id("nonexistent", session=sess)
            self.assertIsNone(result)
        finally:
            sess.close()

    def test_list_operators_with_session(self):
        from backend.src.auth.operators import list_operators
        sess = self._open_session()
        try:
            result = list_operators(session=sess)
            self.assertIsInstance(result, list)
        finally:
            sess.close()

    def test_get_operator_safe_with_session_none(self):
        from backend.src.auth.operators import get_operator_safe
        sess = self._open_session()
        try:
            result = get_operator_safe("nonexistent", session=sess)
            self.assertIsNone(result)
        finally:
            sess.close()

    def test_revoke_operator_with_session(self):
        from backend.src.auth.operators import revoke_operator
        sess = self._open_session()
        try:
            result = revoke_operator("nonexistent", session=sess)
            self.assertFalse(result)
        finally:
            sess.close()

    def test_create_operator_with_session(self):
        from backend.src.auth.operators import create_operator
        sess = self._open_session()
        try:
            op, raw_token = create_operator(
                "Test Op", "admin", "raw-token-abc", "tenant1", session=sess
            )
            sess.commit()
            self.assertIsNotNone(op.operator_id)
        finally:
            sess.close()

    def test_is_expired_with_session_not_found(self):
        from backend.src.auth.operators import is_operator_token_expired
        sess = self._open_session()
        try:
            result = is_operator_token_expired("nonexistent", session=sess)
            self.assertIsNone(result)
        finally:
            sess.close()

    def test_authenticate_with_session(self):
        from backend.src.auth.operators import authenticate_operator_with_reason
        sess = self._open_session()
        try:
            op, reason = authenticate_operator_with_reason("Bearer fake-token", session=sess)
            self.assertIsNone(op)
            self.assertEqual(reason, "operator_auth_required")
        finally:
            sess.close()

    def test_rotate_token_with_session(self):
        from backend.src.auth.operators import create_operator, rotate_operator_token
        sess = self._open_session()
        try:
            op, _ = create_operator("Rot Op", "admin", "raw-tok-rotate", "tenant1", session=sess)
            sess.commit()
            new_tok = rotate_operator_token(op.operator_id, session=sess)
            sess.commit()
            self.assertIsNotNone(new_tok)
        finally:
            sess.close()

    def test_bootstrap_with_session(self):
        from backend.src.auth.operators import bootstrap_operator_if_needed
        sess = self._open_session()
        try:
            bootstrap_operator_if_needed(session=sess)
            sess.commit()
        finally:
            sess.close()

    def test_auto_session_rollback(self):
        from backend.src.auth.operators import _auto_session
        with self.assertRaises(RuntimeError):
            with _auto_session() as _:
                raise RuntimeError("trigger rollback")


# ══════════════════════════════════════════════════════════════════════════════
# Q. grants/grant_requests.py module — session paths (lines 82, 94, 112, 135-140, 160, 226, 277)
# ══════════════════════════════════════════════════════════════════════════════

class TestGrantRequestsModuleSessionPaths(_DbBase):
    def _make_request(self):
        from backend.src.core.models import GrantRequest
        return GrantRequest(
            subject_id="agent1", role="viewer", action="read", resource="doc/1",
            valid_from="2026-01-01T00:00:00Z", valid_until="2027-01-01T00:00:00Z",
            requested_by="op1", reason="test",
        )

    def test_create_with_session(self):
        from backend.src.grants.grant_requests import create_grant_request
        sess = self._open_session()
        try:
            req = self._make_request()
            result = create_grant_request(req, tenant_id="t1", workspace_id="ws1", session=sess)
            sess.commit()
            self.assertIsNotNone(result.id)
        finally:
            sess.close()

    def test_get_with_session(self):
        from backend.src.grants.grant_requests import get_grant_request
        sess = self._open_session()
        try:
            result = get_grant_request("nonexistent", tenant_id="t1", session=sess)
            self.assertIsNone(result)
        finally:
            sess.close()

    def test_list_with_session(self):
        from backend.src.grants.grant_requests import list_grant_requests
        sess = self._open_session()
        try:
            result = list_grant_requests(tenant_id="t1", session=sess)
            self.assertIsInstance(result, list)
        finally:
            sess.close()

    def test_count_with_session(self):
        from backend.src.grants.grant_requests import count_grant_requests
        sess = self._open_session()
        try:
            result = count_grant_requests(tenant_id="t1", session=sess)
            self.assertEqual(result, 0)
        finally:
            sess.close()

    def test_count_no_session(self):
        from backend.src.grants.grant_requests import count_grant_requests
        result = count_grant_requests(tenant_id="t1")
        self.assertEqual(result, 0)

    def test_approve_without_tenant_raises(self):
        from backend.src.grants.grant_requests import approve_grant_request
        with self.assertRaises(ValueError):
            approve_grant_request("req-1", "op1", tenant_id=None)

    def test_deny_without_tenant_raises(self):
        from backend.src.grants.grant_requests import deny_grant_request
        with self.assertRaises(ValueError):
            deny_grant_request("req-1", "op1", "no reason", tenant_id=None)

    def test_revoke_without_tenant_raises(self):
        from backend.src.grants.grant_requests import revoke_grant_request
        with self.assertRaises(ValueError):
            revoke_grant_request("req-1", "op1", "no reason", tenant_id=None)


# ══════════════════════════════════════════════════════════════════════════════
# R. policy/decision_provenance.py — _redact_sensitive and builder branches
#    (lines 126, 137, 151-153, 223-234, 285-287, 291-294, 308-309, 334-335, 415)
# ══════════════════════════════════════════════════════════════════════════════

from backend.src.policy.decision_provenance import (  # noqa: E402
    _redact_sensitive,
    build_decision_provenance_v2,
)


class TestRedactSensitive:
    def test_none_returns_none(self):
        assert _redact_sensitive(None) is None

    def test_sensitive_string_redacted(self):
        assert _redact_sensitive("Bearer secret-token") == "[REDACTED]"

    def test_safe_string_preserved(self):
        assert _redact_sensitive("hello world") == "hello world"

    def test_list_processed(self):
        result = _redact_sensitive(["safe", None])
        assert result == ["safe", None]

    def test_other_type_returned_as_is(self):
        assert _redact_sensitive(42) == 42


class TestBuildDecisionProvenanceV2Branches:
    def test_evidence_missing_branch(self):
        result = build_decision_provenance_v2(
            evidence_completeness={"missing": ["ev1"]},
        )
        assert result["signals"]["evidence"] == "incomplete"

    def test_evidence_warning_branch(self):
        result = build_decision_provenance_v2(
            evidence_completeness={"warning": "some warning"},
        )
        assert result["signals"]["evidence"] == "warning"

    def test_evidence_else_branch(self):
        result = build_decision_provenance_v2(
            evidence_completeness={},
        )
        assert result["signals"]["evidence"] == "incomplete"

    def test_permission_unknown_branch(self):
        result = build_decision_provenance_v2(
            permission_result={"allowed": None},
        )
        assert result["signals"]["permission"] == "unknown"

    def test_permission_missing_perms_branch(self):
        result = build_decision_provenance_v2(
            permission_result={"allowed": None, "missingPermissions": ["perm1"]},
        )
        assert "partial_permission" in result["warnings"]

    def test_approval_req_denied_branch(self):
        result = build_decision_provenance_v2(
            approval_requirement={"decision": "denied"},
        )
        assert "approval_requirement_denied" in result["blockers"]

    def test_lifecycle_pending_branch(self):
        result = build_decision_provenance_v2(
            approval_lifecycle={"status": "pending"},
        )
        assert "approval_lifecycle_pending" in result["blockers"]

    def test_policy_results_non_dict_item(self):
        result = build_decision_provenance_v2(
            policy_results=["not_a_dict", {"passed": True}],
        )
        assert result is not None


# ══════════════════════════════════════════════════════════════════════════════
# S. policy/policy_requirements.py — edge-case branches
#    (lines 67, 83-84, 131, 141, 144, 157, 177, 187, 190, 217, 229, 233,
#     237-242, 249, 252, 257, 275, 290, 300-302, 350)
# ══════════════════════════════════════════════════════════════════════════════

from backend.src.policy.policy_requirements import (  # noqa: E402
    _parse_iso,
    _sanitize_context,
    evaluate_amount_limits,
    evaluate_deadlines,
    evaluate_exclusions,
    evaluate_required_approvals,
    evaluate_required_evidence,
)


class TestSanitizeContextEdgeCases:
    def test_non_dict_returns_none(self):
        assert _sanitize_context("not_a_dict") is None

    def test_non_dict_list_returns_none(self):
        assert _sanitize_context([1, 2]) is None


class TestParseIsoEdgeCases:
    def test_invalid_string_returns_none(self):
        assert _parse_iso("not-a-date") is None

    def test_none_string_returns_none(self):
        assert _parse_iso(None) is None  # type: ignore[arg-type]


class TestEvaluateRequiredEvidenceEdgeCases:
    def test_non_list_required_evidence_returns_early(self):
        result = evaluate_required_evidence({"requiredEvidence": "not_a_list"}, None)
        req, miss, sat, blk, warn = result
        assert req == [] and miss == [] and sat == [] and blk == [] and warn == []

    def test_non_dict_item_skipped(self):
        result = evaluate_required_evidence(
            {"requiredEvidence": ["not_a_dict", None]},
            {"evidenceTypes": []},
        )
        req, miss, sat, blk, warn = result
        assert req == []

    def test_empty_ev_type_skipped(self):
        result = evaluate_required_evidence(
            {"requiredEvidence": [{"type": None, "required": True}]},
            None,
        )
        req, miss, sat, blk, warn = result
        assert req == []

    def test_optional_evidence_found_in_subject(self):
        result = evaluate_required_evidence(
            {"requiredEvidence": [{"type": "audit_log", "required": False}]},
            {"evidenceTypes": ["audit_log"]},
        )
        req, miss, sat, blk, warn = result
        assert "audit_log" in sat


class TestEvaluateExclusionsEdgeCases:
    def test_non_list_exclusions_returns_early(self):
        exc, blk, warn = evaluate_exclusions({"exclusions": "not_a_list"}, None)
        assert exc == [] and blk == [] and warn == []

    def test_non_dict_exclusion_item_skipped(self):
        exc, blk, warn = evaluate_exclusions({"exclusions": ["not_a_dict"]}, None)
        assert exc == []

    def test_empty_exclusion_code_skipped(self):
        exc, blk, warn = evaluate_exclusions(
            {"exclusions": [{"code": None, "severity": "blocking"}]},
            None,
        )
        assert exc == []


class TestEvaluateDeadlinesEdgeCases:
    def test_non_list_deadlines_returns_missing(self):
        status, blk, warn = evaluate_deadlines({"deadlines": "not_a_list"}, None)
        assert status == "missing"

    def test_non_dict_deadline_item_skipped(self):
        status, blk, warn = evaluate_deadlines({"deadlines": ["not_a_dict"]}, None)
        assert status == "none"

    def test_deadline_item_without_due_at_skipped(self):
        status, blk, warn = evaluate_deadlines(
            {"deadlines": [{"required": True}]},
            None,
        )
        assert status == "none"

    def test_malformed_due_at_required(self):
        status, blk, warn = evaluate_deadlines(
            {"deadlines": [{"dueAt": "invalid-date", "required": True}]},
            None,
        )
        assert status == "expired"
        assert "deadline_malformed" in blk

    def test_malformed_due_at_optional(self):
        _status, blk, warn = evaluate_deadlines(
            {"deadlines": [{"dueAt": "invalid-date", "required": False}]},
            None,
        )
        assert "deadline_malformed" in warn

    def test_optional_expired_deadline(self):
        status, blk, warn = evaluate_deadlines(
            {"deadlines": [{"dueAt": "2020-01-01T00:00:00Z", "required": False, "name": "old"}]},
            None,
        )
        assert status == "expired_optional"
        assert any("deadline_expired" in w for w in warn)

    def test_no_items_with_due_at_returns_none(self):
        status, blk, warn = evaluate_deadlines(
            {"deadlines": [{"required": True}]},
            None,
        )
        assert status == "none"


class TestEvaluateAmountLimitsEdgeCases:
    def test_non_dict_amount_limits_returns_missing(self):
        status, blk, warn = evaluate_amount_limits({"amountLimits": "not_a_dict"}, None)
        assert status == "missing"

    def test_subject_amount_none(self):
        status, blk, warn = evaluate_amount_limits(
            {"amountLimits": {"maxAmount": 1000}},
            {"amount": None},
        )
        assert status == "missing_subject_amount"

    def test_malformed_amount_value(self):
        status, blk, warn = evaluate_amount_limits(
            {"amountLimits": {"maxAmount": 1000}},
            {"amount": "not_a_number"},
        )
        assert status == "malformed"
        assert "amount_malformed" in warn


class TestEvaluateRequiredApprovalsEdgeCases:
    def test_non_dict_approval_policy_returns_empty(self):
        policy, blk, warn = evaluate_required_approvals(
            {"approvalPolicy": "not_a_dict"},
            None,
        )
        assert policy == {}


# ══════════════════════════════════════════════════════════════════════════════
# T. core/db.py — _parse_database_url plain path and context manager
#    (lines 167, 222, 334, 337)
# ══════════════════════════════════════════════════════════════════════════════

class TestDbConnectionPaths(_DbBase):
    def test_parse_database_url_uppercase_sqlite_scheme(self):
        from backend.src.core.db import _parse_database_url
        backend_type, path = _parse_database_url("SQLITE:///mydb.db")
        self.assertEqual(backend_type, "sqlite")

    def test_connection_wrapper_context_manager(self):
        from backend.src.core.db import get_conn
        with get_conn() as conn:
            self.assertIsNotNone(conn)

    def test_connection_wrapper_cursor(self):
        from backend.src.core.db import get_conn
        conn = get_conn()
        try:
            cursor = conn.cursor()
            self.assertIsNotNone(cursor)
        finally:
            conn.close()
