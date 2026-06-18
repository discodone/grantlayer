"""GL-298: P0 fixes — audit chain advisory lock + JWT strict claims.

Covers:
- append_event() routes to _append_event_postgres_with_conn when DB_BACKEND=postgres
  and a connection is provided (advisory lock always acquired on PostgreSQL)
- append_event() routes to _append_event_postgres when DB_BACKEND=postgres and
  conn=None (existing behavior unchanged)
- append_event() routes to _append_event_sqlite when DB_BACKEND != postgres
  regardless of conn (existing SQLite behavior unchanged)
- JWT strict mode (GRANTLAYER_JWT_STRICT_CLAIMS=true):
    - tokens missing iss are rejected when JWT_ISSUER is configured
    - tokens missing aud are rejected when JWT_AUDIENCE is configured
    - tokens with correct iss+aud are still accepted
    - tokens with wrong iss are still rejected (unchanged)
    - enforcement is skipped when JWT_ISSUER/JWT_AUDIENCE is empty
- JWT non-strict mode (default):
    - tokens without iss/aud still pass (backward compat preserved)
- Startup warnings:
    - default JWT_ISSUER='grantlayer' in non-test mode emits a warning
    - JWT_ISSUER set to non-default value does not emit the default-issuer warning
    - JWT_STRICT_CLAIMS=false + JWT_ISSUER configured in non-local/non-test mode
      emits a warning
    - JWT_STRICT_CLAIMS=true suppresses the strict-claims warning
    - test mode suppresses both JWT warnings
"""

from __future__ import annotations

import contextlib
import importlib
import os
import unittest
from unittest.mock import MagicMock, patch


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

_HS256_SECRET = "gl298-hs256-test-secret-32charsABC"
_ISSUER = "acme-grants"
_AUDIENCE = "acme-grants-api"


@contextlib.contextmanager
def _env(**overrides: str):
    saved = {k: os.environ.get(k) for k in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@contextlib.contextmanager
def _clear_jwt_env(**overrides: str):
    _jwt_keys = (
        "GRANTLAYER_JWT_ALGORITHM",
        "GRANTLAYER_JWT_SECRET",
        "GRANTLAYER_JWT_PRIVATE_KEY",
        "GRANTLAYER_JWT_PUBLIC_KEY",
        "GRANTLAYER_JWT_ISSUER",
        "GRANTLAYER_JWT_AUDIENCE",
        "GRANTLAYER_JWT_STRICT_CLAIMS",
    )
    saved = {k: os.environ.get(k) for k in _jwt_keys}
    for k in _jwt_keys:
        os.environ.pop(k, None)
    os.environ.update(overrides)
    try:
        yield
    finally:
        for k in _jwt_keys:
            v = saved[k]
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _make_hs256_token(extra: dict | None = None) -> str:
    from backend.src.api.auth_jwt import encode_token
    payload = {"sub": "op", "tenant_id": "acme"}
    if extra:
        payload.update(extra)
    return encode_token(payload, _HS256_SECRET)


def _call_validate(token: str, issuer: str = _ISSUER, audience: str = _AUDIENCE,
                   strict: str = "") -> tuple:
    env_overrides: dict = dict(
        GRANTLAYER_JWT_ALGORITHM="HS256",
        GRANTLAYER_JWT_SECRET=_HS256_SECRET,
        GRANTLAYER_JWT_ISSUER=issuer,
        GRANTLAYER_JWT_AUDIENCE=audience,
    )
    if strict:
        env_overrides["GRANTLAYER_JWT_STRICT_CLAIMS"] = strict
    with _clear_jwt_env(**env_overrides):
        from backend.src.api import auth_jwt
        importlib.reload(auth_jwt)
        import backend.src.core.config as cfg
        importlib.reload(cfg)
        return auth_jwt.validate_jwt_header(f"Bearer {token}")


# ──────────────────────────────────────────────────────────────
# Part 1: Audit chain dispatch routing
# ──────────────────────────────────────────────────────────────

class TestAuditChainDispatch(unittest.TestCase):
    """append_event() routes to the correct implementation based on backend + conn."""

    def _make_event(self) -> "AuditEvent":
        from backend.src.core.models import AuditEvent
        return AuditEvent(
            subject_id="sys",
            role="system",
            action="test_action",
            resource="resource/test",
            approved=True,
            reason="unit test",
            tenant_id="t1",
        )

    def test_postgres_with_conn_routes_to_postgres_with_conn(self):
        """On postgres backend, providing conn must call _append_event_postgres_with_conn."""
        from backend.src.audit import audit_log
        mock_conn = MagicMock()
        event = self._make_event()
        with patch.object(audit_log, "DB_BACKEND", "postgres"), \
             patch.object(audit_log, "_append_event_postgres_with_conn") as mock_fn:
            audit_log.append_event(event, conn=mock_conn)
        mock_fn.assert_called_once_with(event, mock_conn)

    def test_postgres_no_conn_routes_to_postgres(self):
        """On postgres backend, conn=None must call _append_event_postgres."""
        from backend.src.audit import audit_log
        event = self._make_event()
        with patch.object(audit_log, "DB_BACKEND", "postgres"), \
             patch.object(audit_log, "_append_event_postgres") as mock_fn:
            audit_log.append_event(event, conn=None)
        mock_fn.assert_called_once_with(event)

    def test_sqlite_with_conn_routes_to_sqlite(self):
        """On sqlite backend, conn provided must still call _append_event_sqlite."""
        from backend.src.audit import audit_log
        mock_conn = MagicMock()
        event = self._make_event()
        with patch.object(audit_log, "DB_BACKEND", "sqlite"), \
             patch.object(audit_log, "_append_event_sqlite") as mock_fn:
            audit_log.append_event(event, conn=mock_conn)
        mock_fn.assert_called_once_with(event, mock_conn)

    def test_sqlite_no_conn_routes_to_sqlite(self):
        """On sqlite backend, conn=None must call _append_event_sqlite."""
        from backend.src.audit import audit_log
        event = self._make_event()
        with patch.object(audit_log, "DB_BACKEND", "sqlite"), \
             patch.object(audit_log, "_append_event_sqlite") as mock_fn:
            audit_log.append_event(event, conn=None)
        mock_fn.assert_called_once_with(event, None)

    def test_postgres_with_conn_acquires_advisory_lock(self):
        """_append_event_postgres_with_conn must call pg_advisory_xact_lock."""
        from backend.src.audit import audit_log
        from backend.src.core.models import AuditEvent
        event = AuditEvent(
            subject_id="s", role="r", action="a", resource="res",
            approved=True, reason="x", tenant_id="t",
        )
        mock_conn = MagicMock()
        with patch.object(audit_log, "_get_latest_row_hash", return_value=None), \
             patch.object(audit_log, "_compute_row_hash", return_value="hash123"), \
             patch.object(audit_log, "_build_insert_params", return_value={}):
            audit_log._append_event_postgres_with_conn(event, mock_conn)
        # First execute call must be the advisory lock
        first_call_args = mock_conn.execute.call_args_list[0]
        sql_arg = str(first_call_args[0][0])
        self.assertIn("pg_advisory_xact_lock", sql_arg)

    def test_postgres_with_conn_does_not_commit(self):
        """_append_event_postgres_with_conn must NOT commit — caller owns the transaction."""
        from backend.src.audit import audit_log
        from backend.src.core.models import AuditEvent
        event = AuditEvent(
            subject_id="s", role="r", action="a", resource="res",
            approved=True, reason="x", tenant_id="t",
        )
        mock_conn = MagicMock()
        with patch.object(audit_log, "_get_latest_row_hash", return_value=None), \
             patch.object(audit_log, "_compute_row_hash", return_value="hash456"), \
             patch.object(audit_log, "_build_insert_params", return_value={}):
            audit_log._append_event_postgres_with_conn(event, mock_conn)
        mock_conn.commit.assert_not_called()


# ──────────────────────────────────────────────────────────────
# Part 2: JWT strict claims enforcement
# ──────────────────────────────────────────────────────────────

class TestJwtStrictClaimsHS256(unittest.TestCase):
    """GRANTLAYER_JWT_STRICT_CLAIMS=true rejects tokens missing iss/aud."""

    def test_strict_rejects_token_without_iss(self):
        """Strict mode: token without iss claim → 401 jwt_invalid."""
        token = _make_hs256_token({"aud": _AUDIENCE})  # no iss
        ok, status, payload = _call_validate(token, strict="true")
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self.assertEqual(payload["errorCode"], "jwt_invalid")

    def test_strict_rejects_token_without_aud(self):
        """Strict mode: token without aud claim → 401 jwt_invalid."""
        token = _make_hs256_token({"iss": _ISSUER})  # no aud
        ok, status, payload = _call_validate(token, strict="true")
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self.assertEqual(payload["errorCode"], "jwt_invalid")

    def test_strict_rejects_token_without_iss_and_aud(self):
        """Strict mode: token with neither iss nor aud → 401."""
        token = _make_hs256_token()  # no iss, no aud
        ok, status, payload = _call_validate(token, strict="true")
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self.assertEqual(payload["errorCode"], "jwt_invalid")

    def test_strict_accepts_token_with_correct_iss_and_aud(self):
        """Strict mode: token with correct iss and aud → 200."""
        token = _make_hs256_token({"iss": _ISSUER, "aud": _AUDIENCE})
        ok, status, payload = _call_validate(token, strict="true")
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_strict_still_rejects_wrong_iss(self):
        """Strict mode: token with present but wrong iss → 401 (unchanged)."""
        token = _make_hs256_token({"iss": "evil-corp", "aud": _AUDIENCE})
        ok, status, payload = _call_validate(token, strict="true")
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self.assertEqual(payload["errorCode"], "jwt_invalid")

    def test_strict_skips_iss_check_when_issuer_unconfigured(self):
        """Strict mode with empty JWT_ISSUER: missing iss is not enforced."""
        token = _make_hs256_token({"aud": _AUDIENCE})  # no iss
        ok, status, payload = _call_validate(token, issuer="", strict="true")
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_strict_skips_aud_check_when_audience_unconfigured(self):
        """Strict mode with empty JWT_AUDIENCE: missing aud is not enforced."""
        token = _make_hs256_token({"iss": _ISSUER})  # no aud
        ok, status, payload = _call_validate(token, audience="", strict="true")
        self.assertTrue(ok)
        self.assertEqual(status, 200)


class TestJwtNonStrictBackwardCompat(unittest.TestCase):
    """GRANTLAYER_JWT_STRICT_CLAIMS=false (default) preserves backward compat."""

    def test_non_strict_accepts_token_without_iss_aud(self):
        """Non-strict: old tokens without iss/aud must still pass when strict=false."""
        token = _make_hs256_token()  # no iss, no aud
        ok, status, payload = _call_validate(token, strict="false")
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_non_strict_accepts_token_without_iss(self):
        """Non-strict: token with aud but no iss passes when strict=false."""
        token = _make_hs256_token({"aud": _AUDIENCE})
        ok, status, payload = _call_validate(token, strict="false")
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_non_strict_still_rejects_wrong_iss_when_present(self):
        """Non-strict: when iss IS present, wrong value is still rejected."""
        token = _make_hs256_token({"iss": "wrong-issuer", "aud": _AUDIENCE})
        ok, status, payload = _call_validate(token)
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self.assertEqual(payload["errorCode"], "jwt_invalid")


# ──────────────────────────────────────────────────────────────
# Part 3: Startup warnings
# ──────────────────────────────────────────────────────────────

class TestStartupWarningsJwt(unittest.TestCase):
    """startup_warnings() emits correct JWT-related warnings."""

    def _get_warnings(self, env_overrides: dict) -> list[str]:
        saved = {k: os.environ.get(k) for k in env_overrides}
        os.environ.update(env_overrides)
        try:
            import backend.src.core.config as cfg
            importlib.reload(cfg)
            return cfg.startup_warnings()
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            importlib.reload(cfg)

    def test_default_issuer_warning_in_local_mode(self):
        """Default JWT_ISSUER='grantlayer' in local mode emits a warning."""
        warnings = self._get_warnings({
            "GRANTLAYER_RUNTIME_MODE": "local",
            "GRANTLAYER_JWT_ISSUER": "grantlayer",
        })
        self.assertTrue(any("GRANTLAYER_JWT_ISSUER" in w and "default" in w for w in warnings),
                        f"Expected default-issuer warning, got: {warnings}")

    def test_default_issuer_warning_in_staging_mode(self):
        """Default JWT_ISSUER='grantlayer' in staging mode emits a warning."""
        warnings = self._get_warnings({
            "GRANTLAYER_RUNTIME_MODE": "staging",
            "GRANTLAYER_JWT_ISSUER": "grantlayer",
        })
        self.assertTrue(any("GRANTLAYER_JWT_ISSUER" in w and "default" in w for w in warnings),
                        f"Expected default-issuer warning, got: {warnings}")

    def test_no_default_issuer_warning_when_custom_issuer_set(self):
        """Custom JWT_ISSUER does not trigger the default-issuer warning."""
        warnings = self._get_warnings({
            "GRANTLAYER_RUNTIME_MODE": "staging",
            "GRANTLAYER_JWT_ISSUER": "my-unique-grantlayer-instance",
        })
        self.assertFalse(any("default value" in w and "JWT_ISSUER" in w for w in warnings),
                         f"Unexpected default-issuer warning: {warnings}")

    def test_no_default_issuer_warning_in_test_mode(self):
        """Default JWT_ISSUER in test mode does NOT emit a warning."""
        warnings = self._get_warnings({
            "GRANTLAYER_RUNTIME_MODE": "test",
            "GRANTLAYER_JWT_ISSUER": "grantlayer",
        })
        self.assertFalse(any("default value" in w and "JWT_ISSUER" in w for w in warnings),
                         f"Unexpected JWT_ISSUER warning in test mode: {warnings}")

    def test_strict_claims_warning_in_demo_mode(self):
        """JWT_STRICT_CLAIMS=false + issuer configured in demo mode emits a warning."""
        warnings = self._get_warnings({
            "GRANTLAYER_RUNTIME_MODE": "demo",
            "GRANTLAYER_JWT_ISSUER": "my-grantlayer",
            "GRANTLAYER_JWT_STRICT_CLAIMS": "false",
        })
        self.assertTrue(any("JWT_STRICT_CLAIMS" in w for w in warnings),
                        f"Expected strict-claims warning, got: {warnings}")

    def test_no_strict_claims_warning_when_strict_enabled(self):
        """JWT_STRICT_CLAIMS=true suppresses the strict-claims warning."""
        warnings = self._get_warnings({
            "GRANTLAYER_RUNTIME_MODE": "staging",
            "GRANTLAYER_JWT_ISSUER": "my-grantlayer",
            "GRANTLAYER_JWT_STRICT_CLAIMS": "true",
        })
        self.assertFalse(any("JWT_STRICT_CLAIMS" in w for w in warnings),
                         f"Unexpected JWT_STRICT_CLAIMS warning: {warnings}")

    def test_no_strict_claims_warning_in_test_mode(self):
        """JWT_STRICT_CLAIMS=false in test mode does NOT emit a warning."""
        warnings = self._get_warnings({
            "GRANTLAYER_RUNTIME_MODE": "test",
            "GRANTLAYER_JWT_ISSUER": "my-grantlayer",
            "GRANTLAYER_JWT_STRICT_CLAIMS": "false",
        })
        self.assertFalse(any("JWT_STRICT_CLAIMS" in w for w in warnings),
                         f"Unexpected warning in test mode: {warnings}")

    def test_no_strict_claims_warning_when_issuer_empty(self):
        """JWT_STRICT_CLAIMS=false with empty JWT_ISSUER does NOT emit a warning."""
        warnings = self._get_warnings({
            "GRANTLAYER_RUNTIME_MODE": "staging",
            "GRANTLAYER_JWT_ISSUER": "",
            "GRANTLAYER_JWT_STRICT_CLAIMS": "false",
        })
        self.assertFalse(any("JWT_STRICT_CLAIMS" in w for w in warnings),
                         f"Unexpected warning with empty issuer: {warnings}")


if __name__ == "__main__":
    unittest.main()
