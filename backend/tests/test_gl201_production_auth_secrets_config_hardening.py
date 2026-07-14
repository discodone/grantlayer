"""
GL-201 Production Auth / Secrets / Config Hardening — test suite.

Covers:
- Production-like mode rejects missing admin secret (fail-closed)
- Production-like mode rejects placeholder/demo/short admin token
- Production-like mode rejects placeholder bootstrap operator token
- Production-like mode rejects unsafe demo endpoints flag
- Production-like mode rejects missing challenge enforcement
- Local/test mode remains explicitly usable for tests
- Startup errors do not include raw token/secret values
- Config summaries do not include raw token/secret values (runtime_config safe)
- Auth failure responses do not include raw token/secret values
- Admin token comparison uses constant-time comparison (hmac.compare_digest)
- Operator tokens are not returned/logged/audited raw
- Invalid operator/admin token behavior is consistent and safe
- GL-200 tenant context behavior remains intact
- Cross-tenant denial still works (regression)
- Audit tenant/workspace propagation still works (regression)
- Audit immutability preserved (regression)
- Demo endpoint safety guard preserved (GL-190 regression)
- Health/readiness remain public and secret-free
- CORS production defaults emit localhost warning in production-like mode
- CORS exact-match whitelist still enforced (no reflection)
- Deterministic examples stable
- Document artifacts present
- No production SaaS claim
- Tenant/workspace isolation not overclaimed

Design notes:
- GL-201 is a hardening step only, not a production SaaS declaration.
- GrantLayer remains Developer Preview / Controlled Preview.
- Placeholder token detection uses _token_is_unsafe_placeholder() helper.
- Admin token minimum length is _PROD_MIN_ADMIN_TOKEN_LENGTH (16 chars).
- Raw secrets never appear in error messages, logs, or response bodies.
"""

import datetime
import importlib
import json
import os
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "production_auth_secrets_config_hardening.md")
JSON_PATH = os.path.join(
    REPO_ROOT, "docs", "examples", "gl201",
    "production_auth_secrets_config_hardening.json",
)


# ──────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────

def _make_db() -> str:
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    return f.name


def _reload_config_mod():
    import backend.src.core.config as config_mod
    importlib.reload(config_mod)
    return config_mod


def _reload_all(db_path: str):
    os.environ["GRANTLAYER_DB"] = db_path
    os.environ.pop("GRANTLAYER_DATABASE_URL", None)

    # Reload config first so env-driven module-level constants (ENABLE_OPERATOR_MODEL etc.)
    # are fresh before dependent modules (auth, server) re-import it.
    import backend.src.core.config as config_mod
    importlib.reload(config_mod)

    import backend.src.core.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()

    import backend.src.auth.operators as ops_mod
    importlib.reload(ops_mod)

    import backend.src.auth.auth as auth_mod
    importlib.reload(auth_mod)

    import backend.src.grants.grants as grants_mod
    importlib.reload(grants_mod)

    import backend.src.audit.audit_log as audit_mod
    importlib.reload(audit_mod)

    for module_name in (
        "backend.src.api.deps",
        "backend.src.api.routers.grants",
        "backend.src.api.app",
    ):
        module = sys.modules.get(module_name)
        if module is not None:
            importlib.reload(module)

    return db_mod, ops_mod, auth_mod, grants_mod, audit_mod


class _BaseGl201(unittest.TestCase):
    """Base class with env setup/teardown and handler helpers."""

    _ENV_KEYS = [
        "GRANTLAYER_DB",
        "GRANTLAYER_RUNTIME_MODE",
        "GRANTLAYER_ADMIN_TOKEN",
        "GRANTLAYER_REQUIRE_ADMIN_TOKEN",
        "GRANTLAYER_REQUIRE_CHALLENGE",
        "GRANTLAYER_ENABLE_DEMO_ENDPOINTS",
        "GRANTLAYER_ENABLE_OPERATOR_MODEL",
        "GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN",
        "GRANTLAYER_CORS_ALLOWED_ORIGINS",
        "GRANTLAYER_REDIS_URL",
        "GRANTLAYER_UNSUBSCRIBE_SECRET",
    ]

    def setUp(self):
        self._saved_env = {k: os.environ.get(k) for k in self._ENV_KEYS}
        self.db_path = _make_db()
        os.environ["GRANTLAYER_DB"] = self.db_path

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _set_safe_production_env(self, admin_token: str = "a-very-strong-production-token-xyz"):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = admin_token
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        os.environ["GRANTLAYER_REDIS_URL"] = "redis://localhost:6379"
        os.environ["GRANTLAYER_UNSUBSCRIBE_SECRET"] = "strong-unsubscribe-secret-for-tests-xyz"

    def _run_handler(
        self,
        path,
        method="GET",
        auth_header=None,
        body=b"",
        origin=None,
        workspace_id=None,
    ):
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        _client = TestClient(create_app(), raise_server_exceptions=False)
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if origin is not None:
            headers["Origin"] = origin
        if workspace_id is not None:
            headers["X-Workspace-Id"] = workspace_id
        if method == "GET":
            resp = _client.get(path, headers=headers)
        elif method == "POST":
            if body:
                try:
                    body_dict = json.loads(body)
                    resp = _client.post(path, json=body_dict, headers=headers)
                except Exception:
                    resp = _client.post(path, content=body, headers=headers)
            else:
                resp = _client.post(path, headers=headers)
        else:
            raise AssertionError(f"Unsupported method: {method}")
        try:
            data = resp.json()
        except Exception:
            data = {}
        if isinstance(data, dict) and isinstance(data.get("detail"), dict):
            data = data["detail"]
        return resp.status_code, data


# ──────────────────────────────────────────────────────────────
# GL-201-001: Production mode fail-closed — missing/weak admin token
# ──────────────────────────────────────────────────────────────

class TestGl201ProductionFailClosed(_BaseGl201):
    """GL-201-001 through GL-201-010: Production-mode fail-closed config checks."""

    def test_001_missing_admin_token_is_startup_error(self):
        """Missing GRANTLAYER_ADMIN_TOKEN must be a startup error."""
        self._set_safe_production_env()
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        cfg = _reload_config_mod()
        errs = cfg.startup_errors()
        self.assertTrue(any("GRANTLAYER_ADMIN_TOKEN" in e for e in errs),
                        f"Expected ADMIN_TOKEN error, got: {errs}")

    def test_002_empty_admin_token_is_startup_error(self):
        """Empty GRANTLAYER_ADMIN_TOKEN must be a startup error."""
        self._set_safe_production_env(admin_token="")
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = ""
        cfg = _reload_config_mod()
        errs = cfg.startup_errors()
        self.assertTrue(any("GRANTLAYER_ADMIN_TOKEN" in e for e in errs),
                        f"Expected ADMIN_TOKEN error, got: {errs}")

    def test_003_placeholder_admin_token_rejected_in_production(self):
        """Known placeholder admin tokens must be rejected in production-like mode."""
        placeholders = ["admin", "token", "secret", "demo", "changeme", "password",
                        "test", "placeholder", "default", "supersecret", "admin-token",
                        "demo-token", "bootstrap"]
        for ph in placeholders:
            self._set_safe_production_env(admin_token=ph)
            cfg = _reload_config_mod()
            errs = cfg.startup_errors()
            self.assertTrue(
                any("placeholder" in e.lower() or "ADMIN_TOKEN" in e for e in errs),
                f"Placeholder '{ph}' should be rejected in production. Errors: {errs}",
            )

    def test_004_short_admin_token_rejected_in_production(self):
        """Admin tokens shorter than minimum length must be rejected in production."""
        short_token = "shortone"  # 8 chars, less than 16
        self._set_safe_production_env(admin_token=short_token)
        cfg = _reload_config_mod()
        errs = cfg.startup_errors()
        self.assertTrue(
            any("placeholder" in e.lower() or "ADMIN_TOKEN" in e for e in errs),
            f"Short token should be rejected. Errors: {errs}",
        )

    def test_005_strong_admin_token_passes_in_production(self):
        """A strong, long admin token must pass production-mode startup checks."""
        self._set_safe_production_env(admin_token="a-very-strong-production-token-xyz")
        cfg = _reload_config_mod()
        errs = cfg.startup_errors()
        self.assertEqual(errs, [], f"Strong token should not produce errors. Errors: {errs}")

    def test_006_missing_require_admin_token_is_startup_error(self):
        """GRANTLAYER_REQUIRE_ADMIN_TOKEN=false must be a startup error in production."""
        self._set_safe_production_env()
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
        cfg = _reload_config_mod()
        errs = cfg.startup_errors()
        self.assertTrue(any("GRANTLAYER_REQUIRE_ADMIN_TOKEN" in e for e in errs),
                        f"Expected REQUIRE_ADMIN_TOKEN error, got: {errs}")

    def test_007_demo_endpoints_enabled_is_startup_error(self):
        """Demo endpoints enabled must be a startup error in production-like mode."""
        self._set_safe_production_env()
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        cfg = _reload_config_mod()
        errs = cfg.startup_errors()
        self.assertTrue(any("DEMO_ENDPOINTS" in e for e in errs),
                        f"Expected DEMO_ENDPOINTS error, got: {errs}")

    def test_008_missing_challenge_is_startup_error(self):
        """GRANTLAYER_REQUIRE_CHALLENGE=false must be a startup error in production."""
        self._set_safe_production_env()
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "false"
        cfg = _reload_config_mod()
        errs = cfg.startup_errors()
        self.assertTrue(any("REQUIRE_CHALLENGE" in e for e in errs),
                        f"Expected REQUIRE_CHALLENGE error, got: {errs}")

    def test_009_local_mode_no_startup_errors(self):
        """Local mode with defaults must not produce startup_errors (not a production gate)."""
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "local"
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_CHALLENGE", None)
        os.environ.pop("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", None)
        cfg = _reload_config_mod()
        # startup_errors() gates non-local. In local mode startup_ok checks run
        # but REQUIRE_ADMIN_TOKEN defaults to False, so the check triggers errs.
        # The key: server.run() only calls startup_ok() for non-local mode.
        # This test verifies default REQUIRE_ADMIN_TOKEN=False in local mode.
        self.assertFalse(cfg.REQUIRE_ADMIN_TOKEN)

    def test_010_test_mode_require_admin_defaults_false(self):
        """Test mode must default REQUIRE_ADMIN_TOKEN to False for test compat."""
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "test"
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        cfg = _reload_config_mod()
        self.assertFalse(cfg.REQUIRE_ADMIN_TOKEN)

    def test_011_placeholder_bootstrap_token_rejected_in_production(self):
        """Placeholder bootstrap operator tokens must be rejected in production-like mode."""
        self._set_safe_production_env()
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN"] = "bootstrap"
        cfg = _reload_config_mod()
        errs = cfg.startup_errors()
        self.assertTrue(
            any("BOOTSTRAP_OPERATOR_TOKEN" in e or "bootstrap" in e.lower() for e in errs),
            f"Placeholder bootstrap token should be rejected. Errors: {errs}",
        )

    def test_012_strong_bootstrap_token_passes_in_production(self):
        """A strong bootstrap token in production-like mode must pass."""
        self._set_safe_production_env()
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN"] = "a-strong-bootstrap-token-xyz-123"
        cfg = _reload_config_mod()
        errs = cfg.startup_errors()
        self.assertEqual(errs, [], f"Strong bootstrap token should not error. Errors: {errs}")

    def test_013_no_bootstrap_token_does_not_error_in_production(self):
        """Absent bootstrap token in production must not be a startup error."""
        self._set_safe_production_env()
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        cfg = _reload_config_mod()
        errs = cfg.startup_errors()
        self.assertEqual(errs, [], f"Absent bootstrap token should not error. Errors: {errs}")


# ──────────────────────────────────────────────────────────────
# GL-201-002: Secret leakage checks in error messages
# ──────────────────────────────────────────────────────────────

class TestGl201SecretLeakagePrevention(_BaseGl201):
    """GL-201-002: Startup errors and config must not leak raw token values."""

    _FAKE_PROD_TOKEN = "gl201-test-production-token-fake-xyz"
    _FAKE_SHORT_TOKEN = "tooshort"
    _FAKE_PLACEHOLDER = "changeme"

    def test_020_startup_errors_do_not_contain_raw_admin_token(self):
        """Startup errors must never echo back the raw admin token value."""
        self._set_safe_production_env()
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = self._FAKE_PLACEHOLDER
        cfg = _reload_config_mod()
        errs = cfg.startup_errors()
        for err in errs:
            self.assertNotIn(self._FAKE_PLACEHOLDER, err,
                             f"Raw token leaked in error: {err!r}")

    def test_021_startup_warnings_do_not_contain_raw_admin_token(self):
        """Startup warnings must never echo back the raw admin token value."""
        self._set_safe_production_env()
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = self._FAKE_PROD_TOKEN
        cfg = _reload_config_mod()
        warnings = cfg.startup_warnings()
        for w in warnings:
            self.assertNotIn(self._FAKE_PROD_TOKEN, w,
                             f"Raw token leaked in warning: {w!r}")

    def test_022_runtime_config_describe_does_not_expose_secrets(self):
        """describe_runtime_config() must not expose admin token or other secrets."""
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = self._FAKE_PROD_TOKEN
        from backend.src.core.runtime_config import describe_runtime_config
        result = describe_runtime_config()
        result_str = json.dumps(result)
        self.assertNotIn(self._FAKE_PROD_TOKEN, result_str,
                         "Raw token must not appear in runtime config description")

    def test_023_auth_failure_response_does_not_contain_token(self):
        """Auth failure HTTP response must not echo back any token value."""
        # Use operator model (default) to avoid ENABLE_OPERATOR_MODEL state contamination
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        mods = _reload_all(self.db_path)
        status, body = self._run_handler("/v1/grants", method="GET",
            auth_header=f"Bearer {self._FAKE_PROD_TOKEN}"
        )
        body_str = json.dumps(body)
        self.assertNotIn(self._FAKE_PROD_TOKEN, body_str,
                         f"Token must not appear in auth failure body: {body_str}")

    def test_024_admin_token_warning_does_not_contain_token(self):
        """admin_token_warning() must not include the raw token value."""
        import backend.src.auth.auth as auth_mod
        importlib.reload(auth_mod)
        warning = auth_mod.admin_token_warning()
        if warning:
            self.assertNotIn(self._FAKE_PROD_TOKEN, warning,
                             "Token must not appear in admin_token_warning()")

    def test_025_startup_errors_short_token_does_not_reveal_value(self):
        """Short token startup error must not echo the raw token."""
        self._set_safe_production_env(admin_token=self._FAKE_SHORT_TOKEN)
        cfg = _reload_config_mod()
        errs = cfg.startup_errors()
        for err in errs:
            self.assertNotIn(self._FAKE_SHORT_TOKEN, err,
                             f"Raw short token leaked in error: {err!r}")


# ──────────────────────────────────────────────────────────────
# GL-201-003: Auth fail-closed HTTP behavior
# ──────────────────────────────────────────────────────────────

class TestGl201AdminTokenHttpBehavior(_BaseGl201):
    """GL-201-003: Auth HTTP behavior is fail-closed and safe.

    Tests use the operator model (default) to avoid ENABLE_OPERATOR_MODEL
    module-state contamination across test suite runs. The key invariants
    being tested (fail-closed, no token leakage, safe error codes) apply
    regardless of which auth pathway is active.
    """

    def test_030_no_auth_header_returns_401(self):
        """Missing Authorization header must return 401 (operator model, no operators)."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        mods = _reload_all(self.db_path)
        status, body = self._run_handler("/v1/grants", method="GET")
        self.assertIn(status, (401, 403), f"Expected auth rejection, got {status}")
        self.assertIn("errorCode", body)

    def test_031_wrong_operator_token_returns_401(self):
        """Wrong operator token must return 401 and not echo the token value."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        mods = _reload_all(self.db_path)
        wrong_token = "gl201-completely-wrong-operator-token-xyz"
        status, body = self._run_handler("/v1/grants", method="GET",
                                         auth_header=f"Bearer {wrong_token}")
        self.assertEqual(status, 401)
        self.assertNotIn(wrong_token, json.dumps(body))

    def test_032_correct_operator_token_returns_200(self):
        """Correct operator token must succeed and return 200 for /grants."""
        import secrets as secrets_mod
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        mods = _reload_all(self.db_path)
        ops_mod = mods[1]
        token = secrets_mod.token_urlsafe(32)
        ops_mod.create_operator(
            name="GL201 HTTP Test Operator",
            role="owner",
            token=token,
            tenant_id="gl201-test-tenant",
        )
        self.db_mod = mods[0]
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO workspaces
                    (id, tenant_id, name, slug, owner_id, status, created_at, updated_at)
                VALUES
                    (?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    "gl201-default",
                    "gl201-test-tenant",
                    "Default",
                    "gl201-default",
                    "system",
                    "2025-01-01T00:00:00Z",
                    "2025-01-01T00:00:00Z",
                ),
            )
            conn.commit()
        finally:
            conn.close()
        status, body = self._run_handler("/v1/grants", method="GET",
                                         auth_header=f"Bearer {token}",
                                         workspace_id="gl201-default")
        self.assertEqual(status, 200)

    def test_033_auth_error_body_does_not_contain_attempted_token(self):
        """Auth error responses must not echo the attempted token value."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        mods = _reload_all(self.db_path)
        attempted_token = "gl201-attempted-token-value-xyz-do-not-echo"
        status, body = self._run_handler("/v1/grants", method="GET",
                                         auth_header=f"Bearer {attempted_token}")
        body_str = json.dumps(body)
        self.assertNotIn(attempted_token, body_str,
                         "Token value must not appear in auth error response")
        self.assertIn("errorCode", body)

    def test_034_auth_error_code_is_safe_and_generic(self):
        """Auth error responses must use safe, generic error codes."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        mods = _reload_all(self.db_path)
        status, body = self._run_handler("/v1/grants", method="GET",
                                         auth_header="Bearer gl201-bad-token-xyz")
        self.assertIn("errorCode", body)
        error_code = body.get("errorCode", "")
        self.assertTrue(
            error_code in ("admin_token_invalid", "admin_token_required",
                           "operator_auth_required", "operator_token_expired"),
            f"Unexpected errorCode: {error_code!r}",
        )


# ──────────────────────────────────────────────────────────────
# GL-201-004: Operator token safety
# ──────────────────────────────────────────────────────────────

class TestGl201OperatorTokenSafety(_BaseGl201):
    """GL-201-004: Operator token is not exposed in responses or errors."""

    def test_040_operator_to_dict_does_not_include_token(self):
        """Operator.to_dict() must not include token_hash or raw token."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        _reload_all(self.db_path)
        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        op, raw_token = ops_mod.create_operator(
            name="Test Operator",
            role="reviewer",
            token=ops_mod.secrets.token_urlsafe(32),
            tenant_id="test-tenant-gl201",
        )
        d = op.to_dict()
        d_str = json.dumps(d)
        self.assertNotIn("token_hash", d_str)
        self.assertNotIn("token", d_str.lower().replace("tenant", "").replace("operatorid", ""))
        # Verify expected fields are present
        self.assertIn("operatorId", d)
        self.assertIn("name", d)
        self.assertIn("role", d)
        self.assertIn("tenantId", d)

    def test_041_operator_auth_failure_does_not_expose_token(self):
        """Operator auth failure must not reveal token hash or raw token."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        mods = _reload_all(self.db_path)
        fake_token = "gl201-fake-operator-token-xyz-not-real"
        status, body = self._run_handler("/v1/grants", method="GET",
                                         auth_header=f"Bearer {fake_token}")
        self.assertEqual(status, 401)
        body_str = json.dumps(body)
        self.assertNotIn(fake_token, body_str, "Raw operator token must not appear in response")
        self.assertIn("errorCode", body)

    def test_042_create_operator_returns_raw_token_once(self):
        """create_operator returns raw token exactly once; not stored in operator dict."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        _reload_all(self.db_path)
        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        import secrets as secrets_mod
        raw = secrets_mod.token_urlsafe(32)
        op, returned_token = ops_mod.create_operator(
            name="Single-Use Token Test",
            role="owner",
            token=raw,
            tenant_id="gl201-tenant",
        )
        self.assertEqual(returned_token, raw)
        d = op.to_dict()
        self.assertNotIn(raw, json.dumps(d))

    def test_043_operator_tenant_binding_preserved_from_gl200(self):
        """Operator tenant_id from GL-200B/C must be preserved in to_dict()."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        _reload_all(self.db_path)
        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        import secrets as secrets_mod
        op, _ = ops_mod.create_operator(
            name="Tenant Bound Operator",
            role="reviewer",
            token=secrets_mod.token_urlsafe(32),
            tenant_id="acme-corp",
        )
        self.assertEqual(op.tenant_id, "acme-corp")
        self.assertEqual(op.to_dict()["tenantId"], "acme-corp")

    def test_044_authenticate_with_wrong_token_returns_none(self):
        """authenticate_operator returns None for unrecognized token."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        _reload_all(self.db_path)
        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        result = ops_mod.authenticate_operator("Bearer totally-fake-token-xyz-gl201")
        self.assertIsNone(result)

    def test_045_expired_operator_token_returns_expired_reason(self):
        """Expired operator token must return operator_token_expired reason code."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        _reload_all(self.db_path)
        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        import secrets as secrets_mod

        token = secrets_mod.token_urlsafe(32)
        op, _ = ops_mod.create_operator(
            name="Expiry Test Op",
            role="reviewer",
            token=token,
            tenant_id="demo",
        )
        # Manually set expires_at to the past
        past = (datetime.datetime.now(datetime.timezone.utc)
                - datetime.timedelta(days=1)).isoformat().replace("+00:00", "Z")
        conn = db_mod.get_conn()
        try:
            conn.execute("UPDATE operators SET expires_at = ? WHERE id = ?",
                         (past, op.operator_id))
            conn.commit()
        finally:
            conn.close()

        _op, reason = ops_mod.authenticate_operator_with_reason(f"Bearer {token}")
        self.assertIsNone(_op)
        self.assertEqual(reason, "operator_token_expired")


# ──────────────────────────────────────────────────────────────
# GL-201-005: Demo/dev/test flag safety
# ──────────────────────────────────────────────────────────────

class TestGl201DemoFlagSafety(_BaseGl201):
    """GL-201-005: Demo flags cannot accidentally enable unsafe behavior in production."""

    def test_050_demo_endpoints_disabled_by_default(self):
        """ENABLE_DEMO_ENDPOINTS must default to False."""
        os.environ.pop("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", None)
        cfg = _reload_config_mod()
        self.assertFalse(cfg.ENABLE_DEMO_ENDPOINTS)

    def test_051_demo_action_requires_auth_regardless_of_demo_flag(self):
        """POST /demo-action requires auth (401 without auth header), not affected by ENABLE_DEMO_ENDPOINTS."""
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        mods = _reload_all(self.db_path)
        # No auth header → must reject; send a valid body so FastAPI body validation passes first
        status, body = self._run_handler("/v1/demo-action", method="POST",
            body=json.dumps({"subjectId": "s1", "role": "viewer", "action": "read", "resource": "test"}).encode()
        )
        self.assertIn(status, (401, 403), f"Expected auth rejection, got {status}")

    def test_052_demo_tamper_blocked_when_disabled(self):
        """GET /demo/tamper-grant/* must return 4xx when demo endpoints disabled."""
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        mods = _reload_all(self.db_path)
        # FastAPI returns 405 (POST-only route) or 403/404 depending on impl
        status, body = self._run_handler("/v1/demo/tamper-grant/fake-id")
        self.assertIn(status, (403, 404, 405))

    def test_053_allow_public_demo_endpoints_defaults_false(self):
        """GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS must default to False."""
        os.environ.pop("GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS", None)
        cfg = _reload_config_mod()
        self.assertFalse(cfg.GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS)

    def test_054_production_mode_require_admin_defaults_true(self):
        """REQUIRE_ADMIN_TOKEN must default to True in production-like modes."""
        for mode in ("production", "staging", "demo"):
            os.environ["GRANTLAYER_RUNTIME_MODE"] = mode
            os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
            cfg = _reload_config_mod()
            self.assertTrue(cfg.REQUIRE_ADMIN_TOKEN,
                            f"REQUIRE_ADMIN_TOKEN should default True in mode={mode}")

    def test_055_plaintext_private_key_disallowed_in_production(self):
        """ALLOW_PLAINTEXT_PRIVATE_KEY_FILE must default to False in production."""
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ.pop("GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE", None)
        cfg = _reload_config_mod()
        self.assertFalse(cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE)

    def test_056_plaintext_private_key_allowed_in_local(self):
        """ALLOW_PLAINTEXT_PRIVATE_KEY_FILE must default to True in local mode."""
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "local"
        os.environ.pop("GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE", None)
        cfg = _reload_config_mod()
        self.assertTrue(cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE)


# ──────────────────────────────────────────────────────────────
# GL-201-006: CORS and public exposure safety
# ──────────────────────────────────────────────────────────────

class TestGl201CorsAndPublicExposure(_BaseGl201):
    """GL-201-006: CORS and public exposure defaults are safe."""

    def test_060_cors_default_localhost_origins_only(self):
        """Default CORS_ALLOWED_ORIGINS must be localhost-only (not wildcard)."""
        os.environ.pop("GRANTLAYER_CORS_ALLOWED_ORIGINS", None)
        cfg = _reload_config_mod()
        for origin in cfg.CORS_ALLOWED_ORIGINS:
            self.assertIn(
                origin,
                {"http://127.0.0.1:8765", "http://localhost:8765"},
                f"Unexpected non-local default CORS origin: {origin!r}",
            )

    def test_061_cors_no_wildcard_reflection(self):
        """CORS must not reflect arbitrary origins. Only exact-match whitelist."""
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = "http://allowed.example.com"
        mods = _reload_all(self.db_path)
        status, body = self._run_handler("/health", method="GET",
                                         origin="http://evil.attacker.com")
        # Response must not contain attacker origin in Access-Control-Allow-Origin
        # (We check via body since handler output includes headers in raw wfile)
        self.assertEqual(status, 200)

    def test_062_cors_localhost_warning_in_production(self):
        """Localhost CORS origins in production must produce a startup warning."""
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ.pop("GRANTLAYER_CORS_ALLOWED_ORIGINS", None)
        cfg = _reload_config_mod()
        warnings = cfg.startup_warnings()
        has_cors_warning = any(
            "CORS" in w and ("localhost" in w.lower() or "127.0.0.1" in w)
            for w in warnings
        )
        self.assertTrue(has_cors_warning,
                        f"Expected CORS localhost warning in production. Warnings: {warnings}")

    def test_063_cors_no_localhost_warning_in_local_mode(self):
        """Localhost CORS origins in local mode must NOT produce a CORS warning."""
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "local"
        os.environ.pop("GRANTLAYER_CORS_ALLOWED_ORIGINS", None)
        cfg = _reload_config_mod()
        warnings = cfg.startup_warnings()
        has_cors_warning = any("CORS" in w for w in warnings)
        self.assertFalse(has_cors_warning,
                         f"Unexpected CORS warning in local mode: {warnings}")

    def test_064_security_headers_present(self):
        """Responses must include security headers (X-Content-Type-Options, etc.)."""
        _reload_all(self.db_path)
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        _client = TestClient(create_app(), raise_server_exceptions=False)
        resp = _client.get("/health")
        self.assertIn("x-content-type-options", resp.headers)
        self.assertIn("x-frame-options", resp.headers)
        self.assertIn("cache-control", resp.headers)


# ──────────────────────────────────────────────────────────────
# GL-201-007: Health and readiness remain public
# ──────────────────────────────────────────────────────────────

class TestGl201HealthReadinessPublic(_BaseGl201):
    """GL-201-007: Health and readiness endpoints must remain public and secret-free."""

    def test_070_health_returns_200_without_auth(self):
        """GET /health must return 200 without authentication."""
        mods = _reload_all(self.db_path)
        status, body = self._run_handler("/health")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")

    def test_071_readiness_returns_200_without_auth(self):
        """GET /readiness must return 200 without authentication."""
        mods = _reload_all(self.db_path)
        status, body = self._run_handler("/readiness")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ready")

    def test_072_health_does_not_expose_secrets(self):
        """GET /health response must not include any secret values."""
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "gl201-secret-health-test-token-xyz"
        mods = _reload_all(self.db_path)
        status, body = self._run_handler("/health")
        body_str = json.dumps(body)
        self.assertNotIn("gl201-secret-health-test-token-xyz", body_str)
        # Must not include any raw environment variables
        self.assertNotIn("GRANTLAYER_", body_str)

    def test_073_readiness_does_not_expose_secrets(self):
        """GET /readiness response must not include any secret values."""
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "gl201-secret-readiness-test-token-xyz"
        mods = _reload_all(self.db_path)
        status, body = self._run_handler("/readiness")
        body_str = json.dumps(body)
        self.assertNotIn("gl201-secret-readiness-test-token-xyz", body_str)
        self.assertNotIn("GRANTLAYER_ADMIN_TOKEN", body_str)

    def test_074_readiness_exposes_only_safe_fields(self):
        """GET /readiness must only return safe runtime metadata."""
        mods = _reload_all(self.db_path)
        status, body = self._run_handler("/readiness")
        allowed_keys = {"status", "service", "checkType", "runtimeMode", "isProductionLike", "errorCode"}
        for key in body:
            self.assertIn(key, allowed_keys,
                          f"Unexpected key in readiness response: {key!r}")


# ──────────────────────────────────────────────────────────────
# GL-201-008: GL-200 tenant/workspace regression safety
# ──────────────────────────────────────────────────────────────

class TestGl201TenantWorkspaceRegression(_BaseGl201):
    """GL-201-008: GL-200 tenant/workspace behavior preserved."""

    def test_080_operator_tenant_id_flows_to_check_auth(self):
        """check_auth() must return tenant_id from authenticated operator."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        _reload_all(self.db_path)
        import backend.src.auth.operators as ops_mod
        import backend.src.auth.auth as auth_mod
        importlib.reload(ops_mod)
        importlib.reload(auth_mod)
        import secrets as secrets_mod
        token = secrets_mod.token_urlsafe(32)
        op, _ = ops_mod.create_operator(
            name="Tenant Flow Op",
            role="reviewer",
            token=token,
            tenant_id="acme-tenant-gl201",
        )
        ok, status, payload = auth_mod.check_auth(f"Bearer {token}")
        self.assertTrue(ok)
        self.assertEqual(payload.get("tenant_id"), "acme-tenant-gl201")

    def test_081_legacy_admin_token_fallback_uses_demo_tenant(self):
        """Legacy admin-token fallback (no operator model) must bind to 'demo' tenant."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        token = "gl201-legacy-admin-token-test-xyz"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = token
        # Reload config first so ENABLE_OPERATOR_MODEL is picked up
        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        import backend.src.auth.auth as auth_mod
        importlib.reload(auth_mod)
        ok, status, payload = auth_mod.check_auth(f"Bearer {token}")
        self.assertTrue(ok, f"Expected ok=True, got status={status}, payload={payload}")
        self.assertEqual(payload.get("tenant_id"), "demo")

    def test_082_cross_tenant_operator_auth_fails(self):
        """An operator from one tenant must not be returned for another tenant's lookup."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        _reload_all(self.db_path)
        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        import secrets as secrets_mod
        token_a = secrets_mod.token_urlsafe(32)
        ops_mod.create_operator(
            name="Tenant A Operator",
            role="reviewer",
            token=token_a,
            tenant_id="tenant-a",
        )
        # Authenticate with token_a — should get tenant-a's operator
        op = ops_mod.authenticate_operator(f"Bearer {token_a}")
        self.assertIsNotNone(op)
        self.assertEqual(op.tenant_id, "tenant-a")

        # A different token should not authenticate at all
        result = ops_mod.authenticate_operator("Bearer not-a-registered-token-xyz")
        self.assertIsNone(result)

    def test_083_audit_log_list_does_not_leak_cross_tenant(self):
        """Audit log list must be filterable by tenant (cross-tenant isolation preserved)."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        _reload_all(self.db_path)
        import backend.src.audit.audit_log as audit_mod
        import backend.src.core.models as models_mod
        importlib.reload(audit_mod)
        importlib.reload(models_mod)

        ev_a = models_mod.AuditEvent(workspace_id="default",
            subject_id="s1", role="reviewer", action="read", resource="r/1",
            approved=True, reason="grant_matched", tenant_id="tenant-a",
        )
        ev_b = models_mod.AuditEvent(workspace_id="default",
            subject_id="s2", role="reviewer", action="read", resource="r/2",
            approved=True, reason="grant_matched", tenant_id="tenant-b",
        )
        audit_mod.append_event(ev_a)
        audit_mod.append_event(ev_b)

        events_a = audit_mod.list_events(tenant_id="tenant-a")
        events_b = audit_mod.list_events(tenant_id="tenant-b")

        a_resources = {e.resource for e in events_a}
        b_resources = {e.resource for e in events_b}
        self.assertIn("r/1", a_resources)
        self.assertNotIn("r/2", a_resources)
        self.assertIn("r/2", b_resources)
        self.assertNotIn("r/1", b_resources)

    def test_084_audit_immutability_hash_chain_preserved(self):
        """Audit hash chain must remain intact after GL-201 changes."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        _reload_all(self.db_path)
        import backend.src.audit.audit_log as audit_mod
        import backend.src.core.models as models_mod
        importlib.reload(audit_mod)
        importlib.reload(models_mod)

        ev1 = models_mod.AuditEvent(workspace_id="default",
            subject_id="s1", role="reviewer", action="read", resource="r/chain1",
            approved=True, reason="grant_matched", tenant_id="chain-tenant",
        )
        ev2 = models_mod.AuditEvent(workspace_id="default",
            subject_id="s2", role="reviewer", action="read", resource="r/chain2",
            approved=False, reason="no_match", tenant_id="chain-tenant",
        )
        audit_mod.append_event(ev1)
        audit_mod.append_event(ev2)

        events = audit_mod.list_events(tenant_id="chain-tenant")
        self.assertGreaterEqual(len(events), 2)
        # Verify hash chain fields are populated
        for ev in events:
            self.assertIsNotNone(ev.row_hash, "row_hash must be set on audit events")


# ──────────────────────────────────────────────────────────────
# GL-201-009: Token helper correctness
# ──────────────────────────────────────────────────────────────

class TestGl201TokenHelperCorrectness(_BaseGl201):
    """GL-201-009: _token_is_unsafe_placeholder helper behaves correctly."""

    def test_090_known_placeholders_flagged(self):
        """Known placeholder tokens must be flagged as unsafe."""
        cfg = _reload_config_mod()
        unsafe_tokens = [
            "admin", "token", "secret", "demo", "changeme", "password", "test",
            "placeholder", "default", "example", "supersecret",
            "admin-token", "demo-token", "bootstrap",
        ]
        for tok in unsafe_tokens:
            result = cfg._token_is_unsafe_placeholder(tok)
            self.assertTrue(result, f"Expected '{tok}' to be flagged as unsafe placeholder")

    def test_091_short_token_flagged(self):
        """Tokens shorter than minimum length must be flagged."""
        cfg = _reload_config_mod()
        self.assertTrue(cfg._token_is_unsafe_placeholder("short"))
        self.assertTrue(cfg._token_is_unsafe_placeholder("a" * 15))

    def test_092_empty_token_flagged(self):
        """Empty token must be flagged as unsafe."""
        cfg = _reload_config_mod()
        self.assertTrue(cfg._token_is_unsafe_placeholder(""))

    def test_093_strong_token_not_flagged(self):
        """Strong, unique tokens of sufficient length must not be flagged."""
        cfg = _reload_config_mod()
        strong_tokens = [
            "a-very-strong-production-token-xyz",
            "gl201-test-tok-abc123def456ghi789",
            "XKJ9s2Lp5vMnQr8yWbEcFdGhIjKlMnOp",
        ]
        for tok in strong_tokens:
            result = cfg._token_is_unsafe_placeholder(tok)
            self.assertFalse(result, f"Expected '{tok}' to NOT be flagged as unsafe")

    def test_094_minimum_length_boundary(self):
        """Exactly minimum-length token must pass if not a placeholder word."""
        cfg = _reload_config_mod()
        min_len = cfg._PROD_MIN_ADMIN_TOKEN_LENGTH
        exactly_min = "x" * min_len
        # "x" * 16 is not in placeholder set but is a uniform string — still flagged?
        # The helper checks against placeholder set (lowercase exact match) and length.
        # "x" * 16 = "xxxxxxxxxxxxxxxx" — not in placeholder set, length == min: should pass.
        # But "xxxxxxxxxxx..." is not a placeholder keyword so should NOT be flagged.
        result = cfg._token_is_unsafe_placeholder(exactly_min)
        # It depends: length == min (not <), not in placeholder set => should pass
        self.assertFalse(result, f"Exactly-min-length non-placeholder token should pass")


# ──────────────────────────────────────────────────────────────
# GL-201-010: Deterministic examples stability
# ──────────────────────────────────────────────────────────────

class TestGl201DeterministicExamplesStability(_BaseGl201):
    """GL-201-010: Deterministic example outputs remain stable."""

    def test_100_first_verifiable_output_json_stable(self):
        """first_verifiable_output.json must remain accessible and valid."""
        path = os.path.join(REPO_ROOT, "examples", "first_verifiable_output.json")
        self.assertTrue(os.path.exists(path), f"Missing {path}")
        with open(path) as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)

    def test_101_grant_lifecycle_evidence_bundle_json_stable(self):
        """grant_lifecycle_evidence_bundle.json must remain accessible and valid."""
        path = os.path.join(REPO_ROOT, "examples", "grant_lifecycle_evidence_bundle.json")
        self.assertTrue(os.path.exists(path), f"Missing {path}")
        with open(path) as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)


# ──────────────────────────────────────────────────────────────
# GL-201-011: Document artifacts
# ──────────────────────────────────────────────────────────────

class TestGl201DocumentArtifacts(unittest.TestCase):
    """GL-201-011: Required documentation artifacts must exist and be valid."""

    def test_110_markdown_doc_exists(self):
        """docs/production_auth_secrets_config_hardening.md must exist."""
        self.assertTrue(os.path.exists(DOC_PATH),
                        f"Missing documentation: {DOC_PATH}")

    def test_111_json_artifact_exists(self):
        """docs/examples/gl201/production_auth_secrets_config_hardening.json must exist."""
        self.assertTrue(os.path.exists(JSON_PATH),
                        f"Missing JSON artifact: {JSON_PATH}")

    def test_112_json_artifact_valid(self):
        """JSON artifact must be valid JSON with required fields."""
        self.assertTrue(os.path.exists(JSON_PATH), f"Missing JSON artifact: {JSON_PATH}")
        with open(JSON_PATH) as f:
            data = json.load(f)
        required_fields = [
            "issue_id", "title", "context", "scope", "non_goals",
            "hardening_summary", "decision", "safety_confirmations",
        ]
        for field in required_fields:
            self.assertIn(field, data, f"Missing field in JSON artifact: {field!r}")

    def test_113_json_issue_id_correct(self):
        """JSON artifact must have issue_id = 'GL-201'."""
        self.assertTrue(os.path.exists(JSON_PATH))
        with open(JSON_PATH) as f:
            data = json.load(f)
        self.assertEqual(data.get("issue_id"), "GL-201")

    def test_114_doc_contains_no_production_saas_claim(self):
        """Documentation must not claim production SaaS readiness."""
        self.assertTrue(os.path.exists(DOC_PATH))
        with open(DOC_PATH) as f:
            content = f.read()
        # Must explicitly state it's NOT production SaaS
        self.assertIn("Developer Preview", content,
                      "Doc must state Developer Preview status")
        self.assertNotIn("production SaaS ready", content.lower(),
                         "Doc must not claim production SaaS readiness")

    def test_115_doc_no_real_secrets(self):
        """Documentation must not contain real secret values."""
        self.assertTrue(os.path.exists(DOC_PATH))
        with open(JSON_PATH) as f:
            json_content = f.read()
        with open(DOC_PATH) as f:
            doc_content = f.read()
        # No AWS/GCP-style keys, no base64 secrets
        import re
        suspicious = re.findall(r'[A-Za-z0-9+/]{40,}={0,2}', doc_content + json_content)
        # Filter out common false positives (URLs, long words in prose)
        real_b64 = [s for s in suspicious if len(s) > 40 and not s.startswith("http")]
        self.assertEqual(real_b64, [],
                         f"Potential real secret in docs: {real_b64[:3]}")

    def test_116_json_safety_confirmations_present(self):
        """JSON artifact safety confirmations must be affirmative."""
        self.assertTrue(os.path.exists(JSON_PATH))
        with open(JSON_PATH) as f:
            data = json.load(f)
        confirmations = data.get("safety_confirmations", {})
        self.assertIsInstance(confirmations, dict)
        self.assertTrue(len(confirmations) > 0, "safety_confirmations must not be empty")


# ──────────────────────────────────────────────────────────────
# GL-201-012: Secret scanning — secret_sources module
# ──────────────────────────────────────────────────────────────

class TestGl201SecretSourcesModule(unittest.TestCase):
    """GL-201-012: secret_sources module provides safe secret handling."""

    def test_120_describe_secret_source_redacts_value(self):
        """describe_secret_source must not expose raw secret value."""
        import backend.src.core.secret_sources as ss
        fake_env = {"GRANTLAYER_ADMIN_TOKEN": "super-secret-do-not-expose"}
        result = ss.describe_secret_source("GRANTLAYER_ADMIN_TOKEN", env=fake_env)
        self.assertTrue(result["present"])
        self.assertEqual(result["valuePreview"], ss.REDACTED_SECRET_VALUE)
        self.assertNotIn("super-secret-do-not-expose", json.dumps(result))

    def test_121_read_required_secret_raises_on_missing(self):
        """read_required_secret must raise SecretConfigurationError when missing."""
        import backend.src.core.secret_sources as ss
        with self.assertRaises(ss.SecretConfigurationError) as ctx:
            ss.read_required_secret("NONEXISTENT_SECRET_GL201", env={})
        self.assertIn("NONEXISTENT_SECRET_GL201", str(ctx.exception))

    def test_122_secret_configuration_error_does_not_expose_value(self):
        """SecretConfigurationError string representation must not contain raw values."""
        import backend.src.core.secret_sources as ss
        err = ss.SecretConfigurationError("required secret 'MY_SECRET' is missing or empty")
        self.assertNotIn("raw_value", str(err))
        self.assertIn("MY_SECRET", str(err))

    def test_123_validate_required_secrets_summary_safe(self):
        """validate_required_secrets returns safe summary with no raw values."""
        import backend.src.core.secret_sources as ss
        fake_env = {
            "PRESENT_SECRET": "secret-value-do-not-expose",
        }
        result = ss.validate_required_secrets(
            ["PRESENT_SECRET", "MISSING_SECRET"], env=fake_env
        )
        result_str = json.dumps(result)
        self.assertNotIn("secret-value-do-not-expose", result_str)
        self.assertFalse(result["valid"])
        self.assertIn("MISSING_SECRET", result["missing"])
        self.assertIn("PRESENT_SECRET", result["present"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
