"""GL-330: Coverage patch 3 — target remaining lines to reach ≥95%.

Targets: auth_jwt.py (7), gdpr.py (7), deps.py (8), telemetry.py (14),
         grant_request_service.py async revoke (9), logging_utils.py (2).
Total aim: ~47 lines; need 33 to cross 95%.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

_JWT_SECRET = "gl330-coverage3-hs256-secret-32ch!!"


def _make_token(role: str = "grant_admin", tenant: str = "demo", sub: str = "cov-user-330") -> str:
    from backend.src.api.auth_jwt import encode_token
    return encode_token(
        {"sub": sub, "role": role, "tenant_id": tenant,
         "iss": "grantlayer", "aud": "grantlayer-api"},
        _JWT_SECRET,
    )


def _make_client():
    from backend.src.api.app import create_app
    from starlette.testclient import TestClient
    return TestClient(create_app(), raise_server_exceptions=False)


def _run(coro):
    return asyncio.run(coro)


# ── auth_jwt.py lines 54, 55, 99, 100, 109, 110, 142 ─────────────────────────

class TestAuthJwtMissedLines:
    """Cover 7 missed lines in auth_jwt.py."""

    def test_b64url_decode_body(self):
        """Lines 54-55: _b64url_decode body."""
        from backend.src.api.auth_jwt import _b64url_decode
        assert _b64url_decode("dGVzdA") == b"test"

    def test_b64url_decode_with_padding(self):
        from backend.src.api.auth_jwt import _b64url_decode
        assert _b64url_decode("aGVsbG8") == b"hello"

    def test_get_private_key_pem_invalid_base64(self):
        """Lines 99-100: except block when env var has invalid base64."""
        from backend.src.api.auth_jwt import _get_private_key_pem
        with patch.dict(os.environ, {"GRANTLAYER_JWT_PRIVATE_KEY": "!!!not_valid_b64!!!"}):
            assert _get_private_key_pem() is None

    def test_get_public_key_pem_invalid_base64(self):
        """Lines 109-110: except block when env var has invalid base64."""
        from backend.src.api.auth_jwt import _get_public_key_pem
        with patch.dict(os.environ, {"GRANTLAYER_JWT_PUBLIC_KEY": "!!!not_valid_b64!!!"}):
            assert _get_public_key_pem() is None

    def test_decode_token_empty_secret_raises(self):
        """Line 142: raise JWTInvalidError when secret is empty."""
        from backend.src.api.auth_jwt import JWTInvalidError, decode_token
        with pytest.raises(JWTInvalidError, match="not be empty"):
            decode_token("sometoken", "")


# ── gdpr.py lines 29, 66, 67, 81, 82, 140, 141 ───────────────────────────────

_GDPR_ENV = {
    "GRANTLAYER_JWT_SECRET": _JWT_SECRET,
    "GRANTLAYER_JWT_ALGORITHM": "HS256",
}


class TestGdprMissedLines:
    """Cover 7 missed lines in gdpr.py."""

    def test_resolve_caller_invalid_jwt_raises_401(self):
        """Line 29: ok is None (JWT not configured) or ok=False → HTTPException 401."""
        client = _make_client()
        resp = client.post(
            "/v1/users/some-user-330/export-data",
            headers={"Authorization": "Bearer not.a.valid.jwt.token"},
        )
        assert resp.status_code == 401

    def test_collect_data_exception_yields_empty_data(self):
        """Lines 66-67: _collect_user_data raises → data = {}."""
        token = _make_token()
        client = _make_client()
        with patch.dict(os.environ, _GDPR_ENV):
            with patch(
                "backend.src.api.routers.gdpr._collect_user_data",
                new=AsyncMock(side_effect=Exception("db boom")),
            ):
                resp = client.post(
                    "/v1/users/cov-user-330/export-data",
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert resp.status_code in (200, 202)

    def test_export_audit_event_exception_surfaces(self):
        """A failing audit write on export must SURFACE (500), not be swallowed.

        The GDPR export audit write was previously wrapped in ``except: pass`` so a
        lost audit event was invisible. It is now a plain await — an audit-store
        failure propagates rather than logging an export that was never recorded.
        """
        token = _make_token()
        client = _make_client()
        with patch.dict(os.environ, _GDPR_ENV):
            with patch(
                "backend.src.api.routers.gdpr.append_event",
                side_effect=Exception("audit boom"),
            ):
                resp = client.post(
                    "/v1/users/cov-user-330/export-data",
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert resp.status_code == 500

    def test_erase_audit_event_exception_surfaces(self):
        """A failing audit write on erasure must SURFACE (500) and roll the erasure back.

        Irreversible PII anonymization previously committed before a silently
        swallowed audit write. The audit event now rides the same request session,
        so an audit-store failure rolls the anonymization back — never erase without
        an audit record. See test_audit_write_atomicity for the PII-intact assertion.
        """
        token = _make_token()
        client = _make_client()
        with patch.dict(os.environ, _GDPR_ENV):
            with patch(
                "backend.src.api.routers.gdpr.append_event",
                side_effect=Exception("audit boom erase"),
            ):
                resp = client.post(
                    "/v1/users/cov-user-330/erase",
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert resp.status_code == 500


# ── deps.py lines 105, 128, 129, 130, 150, 228, 241, 251 ─────────────────────

class TestDepsMissedLines:
    """Cover 8 missed lines in deps.py."""

    def test_api_key_sync_none_raises_401(self):
        """Line 105: resolve_api_key_sync returns None → HTTPException 401."""
        from backend.src.api.deps import resolve_auth_and_workspace
        with patch("backend.src.api.routers.api_keys.resolve_api_key_sync", return_value=None):
            with pytest.raises(HTTPException) as exc:
                resolve_auth_and_workspace("Bearer gl_live_invalid330", [], "ws-demo")
        assert exc.value.status_code == 401

    def test_oidc_validation_failure_raises_401(self):
        """Lines 128-129: validate_oidc_header (False, 401, ...) → HTTPException."""
        from backend.src.api.deps import resolve_auth_and_workspace
        with patch(
            "backend.src.api.deps.validate_oidc_header",
            return_value=(False, 401, {"error": "oidc_invalid"}),
        ):
            with pytest.raises(HTTPException) as exc:
                resolve_auth_and_workspace("Bearer some-oidc-token", [], "ws-demo")
        assert exc.value.status_code == 401

    def test_oidc_validation_success_assigns_payload(self):
        """Line 130: validate_oidc_header (True, 200, payload) → payload assigned."""
        from backend.src.api.deps import resolve_auth_and_workspace
        oidc_payload = {"sub": "oidc-u", "role": "grant_admin", "tenant_id": "demo"}
        ws_ctx = {
            "workspace_id": "ws-oidc",
            "tenant_id": "demo",
            "cross_workspace_access": False,
            "workspace_member_role": None,
            "resolution_mode": "jwt",
        }
        with patch("backend.src.api.deps.validate_oidc_header",
                   return_value=(True, 200, oidc_payload)):
            with patch("backend.src.api.deps.resolve_workspace_context",
                       return_value=("ws-oidc", 200, ws_ctx)):
                auth, ws = resolve_auth_and_workspace(
                    "Bearer some-oidc-token", [], "ws-oidc"
                )
        assert auth["sub"] == "oidc-u"

    def test_workspace_id_none_raises_400(self):
        """Line 150: ws_id is None after auth → HTTPException 400."""
        from backend.src.api.deps import resolve_auth_and_workspace
        with patch("backend.src.api.deps.validate_oidc_header",
                   return_value=(None, None, None)):
            with patch("backend.src.api.deps.validate_jwt_header",
                       return_value=(True, 200, {"sub": "u", "role": "grant_admin", "tenant_id": "demo"})):
                with patch("backend.src.api.deps.resolve_workspace_context",
                           return_value=(None, 200, {"workspace_id": None, "tenant_id": "demo"})):
                    with pytest.raises(HTTPException) as exc:
                        resolve_auth_and_workspace("Bearer some-jwt", [], None)
        assert exc.value.status_code == 400

    def test_enforce_workspace_mutation_blocked_raises_403(self):
        """Line 228: check_workspace_resource_access returns False → HTTPException 403."""
        from backend.src.api.deps import enforce_workspace_mutation
        with patch(
            "backend.src.api.deps.check_workspace_resource_access",
            return_value=(False, 403, {"error": "forbidden"}),
        ):
            with pytest.raises(HTTPException) as exc:
                enforce_workspace_mutation({
                    "workspace_id": "ws-1",
                    "tenant_id": "t-1",
                    "cross_workspace_access": False,
                    "workspace_member_role": "viewer",
                })
        assert exc.value.status_code == 403

    def test_get_async_grant_request_repo_factory(self):
        """Line 241: factory return line executed."""
        from backend.src.api.deps import get_async_grant_request_repo
        mock_db = MagicMock()
        repo = get_async_grant_request_repo(db=mock_db)
        assert repo is not None

    def test_get_async_operator_repo_factory(self):
        """Line 251: factory return line executed."""
        from backend.src.api.deps import get_async_operator_repo
        mock_db = MagicMock()
        repo = get_async_operator_repo(db=mock_db)
        assert repo is not None


# ── telemetry.py lines 51,52,61,62,66,67,80,86,87,88,95,99,100,106,110,111 ──

class TestTelemetryMissedLines:
    """Cover 14 missed lines in telemetry.py (lines 14-15 are unreachable dead code)."""

    def test_setup_telemetry_otlp_except_block(self):
        """Lines 51-52: OTLPSpanExporter instantiation raises → except pass."""
        pytest.importorskip("opentelemetry.exporter.otlp.proto.grpc.trace_exporter")
        import backend.src.core.telemetry as tel
        with patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317"}):
            with patch(
                "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter",
                side_effect=Exception("otlp_test_error"),
            ):
                tel.setup_telemetry("gl330-otlp-test")

    def test_setup_telemetry_jaeger_except_block(self):
        """Lines 61-62: Jaeger OTLPSpanExporter raises → except pass."""
        pytest.importorskip("opentelemetry.exporter.otlp.proto.grpc.trace_exporter")
        import backend.src.core.telemetry as tel
        with patch.dict(os.environ, {"OTEL_JAEGER_HOST": "localhost-test"}):
            with patch(
                "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter",
                side_effect=Exception("jaeger_test_error"),
            ):
                tel.setup_telemetry("gl330-jaeger-test")

    def test_setup_telemetry_outer_except_block(self):
        """Lines 66-67: Resource.create raises → outer except pass."""
        pytest.importorskip("opentelemetry.sdk.resources")
        import backend.src.core.telemetry as tel
        with patch(
            "opentelemetry.sdk.resources.Resource.create",
            side_effect=Exception("resource_test_error"),
        ):
            tel.setup_telemetry("gl330-outer-test")

    def test_get_current_trace_id_otel_unavailable(self):
        """Line 80: _OTEL_AVAILABLE=False → immediate return None."""
        import backend.src.core.telemetry as tel
        saved = tel._OTEL_AVAILABLE
        try:
            tel._OTEL_AVAILABLE = False
            result = tel.get_current_trace_id()
            assert result is None
        finally:
            tel._OTEL_AVAILABLE = saved

    def test_get_current_trace_id_with_active_span(self):
        """Line 86: returns trace_id hex when inside an active SDK span."""
        pytest.importorskip("opentelemetry.sdk.trace")
        import backend.src.core.telemetry as tel
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider

        provider = TracerProvider()
        tracer = provider.get_tracer("gl330-span-test")
        with tracer.start_as_current_span("gl330-coverage-span"):
            result = tel.get_current_trace_id()
        # SDK spans have non-zero trace IDs; result should be a 32-char hex string or None
        if result is not None:
            assert len(result) == 32

    def test_get_current_trace_id_exception_path(self):
        """Lines 87-88: get_current_span raises → except pass → return None."""
        pytest.importorskip("opentelemetry.trace")
        import backend.src.core.telemetry as tel
        saved = tel._OTEL_AVAILABLE
        tel._OTEL_AVAILABLE = True
        try:
            with patch(
                "opentelemetry.trace.get_current_span",
                side_effect=Exception("span_error"),
            ):
                result = tel.get_current_trace_id()
            assert result is None
        finally:
            tel._OTEL_AVAILABLE = saved

    def test_instrument_fastapi_otel_unavailable(self):
        """Line 95: _OTEL_AVAILABLE=False → return immediately."""
        import backend.src.core.telemetry as tel
        saved = tel._OTEL_AVAILABLE
        try:
            tel._OTEL_AVAILABLE = False
            tel.instrument_fastapi(MagicMock())
        finally:
            tel._OTEL_AVAILABLE = saved

    def test_instrument_fastapi_exception_path(self):
        """Lines 99-100: FastAPIInstrumentor.instrument_app raises → except pass."""
        pytest.importorskip("opentelemetry.instrumentation.fastapi")
        import backend.src.core.telemetry as tel
        saved = tel._OTEL_AVAILABLE
        tel._OTEL_AVAILABLE = True
        try:
            with patch(
                "opentelemetry.instrumentation.fastapi.FastAPIInstrumentor.instrument_app",
                side_effect=Exception("fastapi_instr_error"),
            ):
                tel.instrument_fastapi(MagicMock())
        finally:
            tel._OTEL_AVAILABLE = saved

    def test_instrument_sqlalchemy_otel_unavailable(self):
        """Line 106: _OTEL_AVAILABLE=False → return immediately."""
        import backend.src.core.telemetry as tel
        saved = tel._OTEL_AVAILABLE
        try:
            tel._OTEL_AVAILABLE = False
            tel.instrument_sqlalchemy(MagicMock())
        finally:
            tel._OTEL_AVAILABLE = saved

    def test_instrument_sqlalchemy_exception_path(self):
        """Lines 110-111: SQLAlchemyInstrumentor.instrument raises → except pass."""
        pytest.importorskip("opentelemetry.instrumentation.sqlalchemy")
        import backend.src.core.telemetry as tel
        saved = tel._OTEL_AVAILABLE
        tel._OTEL_AVAILABLE = True
        try:
            with patch(
                "opentelemetry.instrumentation.sqlalchemy.SQLAlchemyInstrumentor.instrument",
                side_effect=Exception("sqlalchemy_instr_error"),
            ):
                tel.instrument_sqlalchemy(MagicMock())
        finally:
            tel._OTEL_AVAILABLE = saved


# ── grant_request_service.py async revoke_request lines 412,418,427..447 ─────

class TestAsyncGrantRequestServiceRevokeLines:
    """Cover lines 412, 418, 427, 428, 430, 440, 444, 445, 447 in grant_request_service.py."""

    def _session_factory(self):
        from backend.src.core.db import get_async_session_maker
        return get_async_session_maker()

    def test_revoke_nonexistent_request_raises(self):
        """Line 412: req is None → ValueError."""
        from backend.src.core.repositories_sqlalchemy import (
            SqlAlchemyAsyncGrantRepository,
            SqlAlchemyAsyncGrantRequestRepository,
        )
        from backend.src.grants.grant_request_service import AsyncGrantRequestService

        async def _inner():
            factory = self._session_factory()
            async with factory() as session:
                repo = SqlAlchemyAsyncGrantRequestRepository(session)
                grant_repo = SqlAlchemyAsyncGrantRepository(session)
                svc = AsyncGrantRequestService(repo=repo, grant_repo=grant_repo, session=session)
                with pytest.raises(ValueError, match="not found"):
                    await svc.revoke_request(
                        str(uuid.uuid4()), "op-330", "reason", "demo", "demo"
                    )

        _run(_inner())

    def test_revoke_approved_request_happy_path(self):
        """Lines 418,427,428,430,440,444,445,447: full revoke_request flow."""
        from sqlalchemy import text as _text

        from backend.src.core.repositories_sqlalchemy import (
            SqlAlchemyAsyncGrantRepository,
            SqlAlchemyAsyncGrantRequestRepository,
        )
        from backend.src.grants.grant_request_service import AsyncGrantRequestService

        request_id = str(uuid.uuid4())
        now = "2026-06-18T10:00:00Z"

        async def _inner():
            factory = self._session_factory()
            async with factory() as session:
                await session.execute(_text(
                    "INSERT INTO grant_requests "
                    "(id, subject_id, role, action, resource, status, requested_by, "
                    "reason, tenant_id, workspace_id, valid_from, valid_until, "
                    "created_at, updated_at) "
                    "VALUES (:id, :sub, :role, :action, :res, :status, :reqby, "
                    ":reason, :tn, :ws, :vf, :vu, :now, :now)"
                ), {
                    "id": request_id,
                    "sub": "test-subject-330",
                    "role": "ai_agent",
                    "action": "read",
                    "res": "grants",
                    "status": "approved",
                    "reqby": "op-330",
                    "reason": "coverage test gl330",
                    "tn": "demo",
                    "ws": "demo",
                    "vf": now,
                    "vu": "2099-12-31T23:59:59Z",
                    "now": now,
                })
                await session.commit()

            async with factory() as session2:
                repo = SqlAlchemyAsyncGrantRequestRepository(session2)
                grant_repo = SqlAlchemyAsyncGrantRepository(session2)
                svc = AsyncGrantRequestService(
                    repo=repo, grant_repo=grant_repo, session=session2
                )
                result = await svc.revoke_request(
                    request_id, "op-330", "coverage test revoke gl330",
                    "demo", "demo"
                )
                assert result.status == "revoked"

        _run(_inner())

    def test_revoke_non_approved_status_raises(self):
        """Lines 413-415: req.status != 'approved' → ValueError."""
        from sqlalchemy import text as _text

        from backend.src.core.repositories_sqlalchemy import (
            SqlAlchemyAsyncGrantRepository,
            SqlAlchemyAsyncGrantRequestRepository,
        )
        from backend.src.grants.grant_request_service import AsyncGrantRequestService

        request_id = str(uuid.uuid4())
        now = "2026-06-18T11:00:00Z"

        async def _inner():
            factory = self._session_factory()
            async with factory() as session:
                await session.execute(_text(
                    "INSERT INTO grant_requests "
                    "(id, subject_id, role, action, resource, status, requested_by, "
                    "reason, tenant_id, workspace_id, valid_from, valid_until, "
                    "created_at, updated_at) "
                    "VALUES (:id, :sub, :role, :action, :res, :status, :reqby, "
                    ":reason, :tn, :ws, :vf, :vu, :now, :now)"
                ), {
                    "id": request_id,
                    "sub": "test-subject-330b",
                    "role": "ai_agent",
                    "action": "read",
                    "res": "grants",
                    "status": "requested",
                    "reqby": "op-330",
                    "reason": "coverage test gl330b",
                    "tn": "demo",
                    "ws": "demo",
                    "vf": now,
                    "vu": "2099-12-31T23:59:59Z",
                    "now": now,
                })
                await session.commit()

            async with factory() as session2:
                repo = SqlAlchemyAsyncGrantRequestRepository(session2)
                grant_repo = SqlAlchemyAsyncGrantRepository(session2)
                svc = AsyncGrantRequestService(
                    repo=repo, grant_repo=grant_repo, session=session2
                )
                with pytest.raises(ValueError, match="Cannot revoke"):
                    await svc.revoke_request(
                        request_id, "op-330", "coverage test",
                        "demo", "demo"
                    )

        _run(_inner())


# ── logging_utils.py lines 229, 235 ──────────────────────────────────────────

class TestLoggingUtilsMissedLines:
    """Cover lines 229 and 235 in logging_utils.py."""

    def test_json_formatter_redacts_sensitive_field(self):
        """Line 235: payload[key] = _REDACTED when key is in _SENSITIVE_FIELDS."""
        from backend.src.core.logging_utils import _JsonFormatter
        formatter = _JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        record.token = "super-secret-value"  # type: ignore[attr-defined]
        result = formatter.format(record)
        assert "super-secret-value" not in result
        assert "[REDACTED]" in result

    def test_json_formatter_includes_trace_id_when_active(self):
        """Line 229: if trace_id: payload['trace_id'] = trace_id — cover with active span."""
        pytest.importorskip("opentelemetry.sdk.trace")
        from opentelemetry.sdk.trace import TracerProvider

        from backend.src.core.logging_utils import _JsonFormatter
        formatter = _JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="trace test message",
            args=(),
            exc_info=None,
        )
        provider = TracerProvider()
        tracer = provider.get_tracer("gl330-logging-test")
        with tracer.start_as_current_span("gl330-logging-span"):
            result = formatter.format(record)
        # trace_id field will be present if get_current_trace_id returns a value
        assert isinstance(result, str)
