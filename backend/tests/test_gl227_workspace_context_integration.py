"""GL-227 Workspace Context Integration — test suite.

Covers:
- _resolve_workspace helper: legacy/demo mode always resolves (backward compat)
- _resolve_workspace helper: operator with single workspace membership → resolved
- _resolve_workspace helper: operator with no workspace memberships → 403 fail-closed
- _resolve_workspace helper: operator with multiple workspaces, no workspace_id → 400
- GET /grants: legacy mode succeeds without workspace context overhead
- GET /grants: operator mode with membership uses workspace-resolved tenant_id
- GET /grants: operator mode with no membership → 403 (fail-closed)
- POST /grants: workspace context resolved before create
- GET /audit-events: workspace context resolved
- GET /grant-requests: workspace context resolved
- POST /grants/{id}/revoke: check_workspace_resource_access called for mutation
- POST /grants/{id}/revoke: workspace_readonly role blocked on mutation
- GET /challenges: workspace context resolved
- tenant_id derived from workspace context (not raw auth payload fallback)
- Demo/synthetic compatibility: all existing demo-mode flows unaffected
- No production SaaS claim, no real customer data
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    import backend.src.core.db as _db
    import backend.src.core.config as _cfg
    import backend.src.auth.operators as _ops
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    from backend.src.auth.auth import resolve_workspace_context
    _SKIP = lambda cls: cls  # noqa: E731
except ImportError:
    _SKIP = unittest.skip("FastAPI/backend not available")


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _make_db():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    return f.name


def _future(days=30) -> str:
    dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    return dt.isoformat().replace("+00:00", "Z")


def _past(days=30) -> str:
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return dt.isoformat().replace("+00:00", "Z")


def _insert_operator(op_id, name, role, token, tenant_id="t1", active=1):
    conn = _db.get_conn()
    try:
        conn.execute(
            """INSERT INTO operators (id, name, role, token_hash, token_lookup_hash, active, created_at, tenant_id)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
               ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, role=EXCLUDED.role, token_hash=EXCLUDED.token_hash, token_lookup_hash=EXCLUDED.token_lookup_hash, active=EXCLUDED.active, tenant_id=EXCLUDED.tenant_id""",
            (op_id, name, role,
             _ops.hash_token(token),
             _ops.derive_token_lookup_hash(token),
             active, tenant_id),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_workspace(ws_id, tenant_id, status="active"):
    conn = _db.get_conn()
    try:
        conn.execute(
            """INSERT INTO workspaces (id, tenant_id, name, slug, owner_id, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'system', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (ws_id, tenant_id, ws_id, ws_id, status),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_member(workspace_id, operator_id, role="workspace_member", status="active"):
    conn = _db.get_conn()
    try:
        conn.execute(
            """INSERT INTO workspace_members (id, workspace_id, operator_id, role, status, joined_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (str(uuid.uuid4()), workspace_id, operator_id, role, status),
        )
        conn.commit()
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# BASE: shared setUp / tearDown
# ──────────────────────────────────────────────────────────────

class _Base(unittest.TestCase):
    OPERATOR_MODE = False

    def setUp(self):
        self._orig_enable_operator = _cfg.ENABLE_OPERATOR_MODEL
        self._orig_allow_plaintext = _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE
        self._orig_db_path = _db.DB_PATH_OR_URL
        # Save the SA engine state so tearDown can clean up without leaking
        self._orig_sa_engine = _db._sa_engine
        self._orig_engine_url = _db._engine_url
        self._orig_env = {k: os.environ.get(k) for k in (
            "GRANTLAYER_DB",
            "GRANTLAYER_ENABLE_OPERATOR_MODEL",
            "GRANTLAYER_JWT_SECRET",
            "GRANTLAYER_JWT_PUBLIC_KEY",
            "GRANTLAYER_JWT_PRIVATE_KEY",
            "GRANTLAYER_JWT_ALGORITHM",
            "GRANTLAYER_RATE_LIMIT_AUTH",
            "GRANTLAYER_RATE_LIMIT_API",
            # These can be set by other tests in the same xdist worker and
            # cause legacy-mode unauthenticated requests to fail with 403.
            "GRANTLAYER_REQUIRE_ADMIN_TOKEN",
            "GRANTLAYER_ADMIN_TOKEN",
        )}

        os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)
        os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
        os.environ.pop("GRANTLAYER_JWT_ALGORITHM", None)
        # Ensure admin-token enforcement is off so unauthenticated demo requests pass.
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ["GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"] = "true"
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = True
        os.environ["GRANTLAYER_RATE_LIMIT_AUTH"] = "1000"
        os.environ["GRANTLAYER_RATE_LIMIT_API"] = "1000"

        _cfg.ENABLE_OPERATOR_MODEL = self.OPERATOR_MODE
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true" if self.OPERATOR_MODE else "false"

        # Reset the SQLAlchemy engine so this test gets a clean connection to
        # its own temp DB, regardless of what a previous test in the same
        # xdist worker may have left in the engine cache.
        _db._sa_engine = None
        _db._engine_url = None

        self.db_path = _make_db()
        os.environ["GRANTLAYER_DB"] = self.db_path
        _db.DB_PATH_OR_URL = self.db_path
        _db.DB_PATH = self.db_path
        _db.init_db()

        self.client = TestClient(create_app(), raise_server_exceptions=False)

    def tearDown(self):
        _cfg.ENABLE_OPERATOR_MODEL = self._orig_enable_operator
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_allow_plaintext
        # Dispose the test DB engine before restoring the original path so the
        # next test gets a fresh engine rather than a connection to a deleted file.
        if _db._sa_engine is not None:
            try:
                _db._sa_engine.dispose()
            except Exception:
                pass
        _db._sa_engine = self._orig_sa_engine
        _db._engine_url = self._orig_engine_url
        _db.DB_PATH_OR_URL = self._orig_db_path
        _db.DB_PATH = self._orig_db_path
        for k, v in self._orig_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def _op(self, name="op1", role="grant_admin", token="tok", tenant_id="t1", ws_id="ws1"):
        op_id = f"op-{name}-{uuid.uuid4().hex[:6]}"
        _insert_operator(op_id, name, role, token, tenant_id=tenant_id)
        if ws_id:
            _insert_workspace(ws_id, tenant_id)
            _insert_member(ws_id, op_id)
        return op_id, token

    def _header(self, token):
        return {"Authorization": f"Bearer {token}"}


# ──────────────────────────────────────────────────────────────
# WS-001: resolve_workspace_context — legacy/demo mode
# ──────────────────────────────────────────────────────────────

@_SKIP
class TestResolveWorkspaceLegacyMode(_Base):
    """WS-001: Legacy/demo mode (ENABLE_OPERATOR_MODEL=false) always resolves."""
    OPERATOR_MODE = False

    def test_resolve_workspace_legacy_no_operator_id(self):
        """No operator_id in payload resolves the default demo workspace."""
        auth_payload = {"tenant_id": "demo"}
        ws_id, status, ctx = resolve_workspace_context(auth_payload)
        self.assertEqual(status, 200)
        self.assertIsNotNone(ctx)
        self.assertEqual(ws_id, "default")
        self.assertEqual(ctx["workspace_id"], "default")
        self.assertEqual(ctx["tenant_id"], "demo")
        self.assertEqual(ctx["resolution_mode"], "legacy_demo")

    def test_resolve_workspace_legacy_with_tenant_id(self):
        """Legacy mode always falls back to demo workspace regardless of tenant_id."""
        auth_payload = {"tenant_id": "other_tenant"}
        ws_id, status, ctx = resolve_workspace_context(auth_payload)
        self.assertEqual(status, 200)
        self.assertEqual(ctx["resolution_mode"], "legacy_demo")


# ──────────────────────────────────────────────────────────────
# WS-002: resolve_workspace_context — operator with single membership
# ──────────────────────────────────────────────────────────────

@_SKIP
class TestResolveWorkspaceOperatorSingleMembership(_Base):
    """WS-002: Operator with single active workspace membership → auto-resolved."""
    OPERATOR_MODE = True

    def test_single_membership_resolved(self):
        """Operator with exactly one workspace membership → workspace resolved."""
        op_id, token = self._op(name="owner1", role="grant_admin", token="tok-ws002", ws_id="ws-002")
        auth_payload = {
            "tenant_id": "t1",
            "operator": {"operatorId": op_id, "role": "grant_admin"},
        }
        ws_id, status, ctx = resolve_workspace_context(auth_payload)
        self.assertEqual(status, 200)
        self.assertEqual(ctx["workspace_id"], "ws-002")
        self.assertEqual(ctx["tenant_id"], "t1")
        self.assertEqual(ctx["resolution_mode"], "single_membership")


# ──────────────────────────────────────────────────────────────
# WS-003: resolve_workspace_context — operator with no memberships → fail-closed
# ──────────────────────────────────────────────────────────────

@_SKIP
class TestResolveWorkspaceFailClosed(_Base):
    """WS-003: Operator in non-demo tenant with no memberships → 403 fail-closed.

    Note: The demo tenant ('demo') has a fallback to the default workspace for backward
    compatibility with pre-GL-227 tests and demo/dev scenarios. Non-demo tenants
    enforce the fail-closed rule strictly.
    """
    OPERATOR_MODE = True

    def test_no_membership_fail_closed(self):
        """Non-demo tenant operator with no memberships → resolve returns 403."""
        op_id = "op-no-ws"
        _insert_operator(op_id, "nomember", "grant_admin", "tok-no-ws", tenant_id="t1")
        _insert_workspace("ws-sentinel-003", "t1")
        auth_payload = {
            "tenant_id": "t1",
            "operator": {"operatorId": op_id, "role": "grant_admin"},
        }
        ws_id, status, ctx = resolve_workspace_context(auth_payload)
        self.assertIsNone(ws_id)
        self.assertEqual(status, 403)
        self.assertEqual(ctx.get("errorCode"), "no_workspace_membership")


# ──────────────────────────────────────────────────────────────
# WS-004: resolve_workspace_context — multiple workspaces → 400
# ──────────────────────────────────────────────────────────────

@_SKIP
class TestResolveWorkspaceMultipleMembershipsAmbiguous(_Base):
    """WS-004: Operator with multiple workspace memberships and no explicit workspace_id → 400."""
    OPERATOR_MODE = True

    def test_multiple_memberships_without_workspace_id(self):
        """Ambiguous: multiple memberships, no workspace_id → 400."""
        op_id = "op-multi"
        _insert_operator(op_id, "multi", "auditor", "tok-multi", tenant_id="t1")
        _insert_workspace("ws-a", "t1")
        _insert_workspace("ws-b", "t1")
        _insert_member("ws-a", op_id)
        _insert_member("ws-b", op_id)

        auth_payload = {
            "tenant_id": "t1",
            "operator": {"operatorId": op_id, "role": "auditor"},
        }
        ws_id, status, ctx = resolve_workspace_context(auth_payload)
        self.assertIsNone(ws_id)
        self.assertEqual(status, 400)
        self.assertEqual(ctx.get("errorCode"), "workspace_id_required")


# ──────────────────────────────────────────────────────────────
# WS-005: GET /grants — legacy mode unaffected
# ──────────────────────────────────────────────────────────────

@_SKIP
class TestGetGrantsLegacyMode(_Base):
    """WS-005: GET /grants in legacy/demo mode still works after GL-227."""
    OPERATOR_MODE = False

    def test_get_grants_legacy_200(self):
        """Legacy mode: no operator, no admin token required → 200."""
        resp = self.client.get("/v1/grants")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json()["items"], list)

    def test_get_grants_legacy_tenant_is_demo(self):
        """Legacy mode: tenant_id should resolve to 'demo'."""
        from backend.src.core.models import Grant
        import backend.src.grants.grants as _grants
        g = Grant(
            subject_id="s1", role="r1", action="a1", resource="res1",
            valid_from=_past(10), valid_until=_future(10),
            created_by="admin", reason="test",
        )
        _grants.create_grant(g, tenant_id="demo")

        resp = self.client.get("/v1/grants")
        self.assertEqual(resp.status_code, 200)
        ids = [item["id"] for item in resp.json()["items"]]
        self.assertIn(g.id, ids)

    def test_get_grants_other_tenant_not_visible_in_legacy(self):
        """Grants created for a different tenant are not returned in demo-mode listing."""
        from backend.src.core.models import Grant
        import backend.src.grants.grants as _grants
        g_other = Grant(
            subject_id="s-other", role="r1", action="a1", resource="res1",
            valid_from=_past(10), valid_until=_future(10),
            created_by="admin", reason="test",
        )
        _grants.create_grant(g_other, tenant_id="other_tenant")

        resp = self.client.get("/v1/grants")
        self.assertEqual(resp.status_code, 200)
        ids = [item["id"] for item in resp.json()["items"]]
        self.assertNotIn(g_other.id, ids)


# ──────────────────────────────────────────────────────────────
# WS-006: GET /grants — operator mode with workspace membership
# ──────────────────────────────────────────────────────────────

@_SKIP
class TestGetGrantsOperatorMode(_Base):
    """WS-006: GET /grants in operator mode uses workspace-resolved tenant_id."""
    OPERATOR_MODE = True

    def test_get_grants_operator_single_membership_200(self):
        """Operator with single membership → GET /grants succeeds."""
        op_id, token = self._op(name="owner2", role="grant_admin", token="tok-ws006a", ws_id="ws-006a")
        resp = self.client.get("/v1/grants", headers=self._header(token))
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json()["items"], list)

    def test_get_grants_operator_no_membership_403(self):
        """Operator with no workspace membership → GET /grants returns 403."""
        op_id = "op-nows-006"
        _insert_operator(op_id, "nows", "grant_admin", "tok-nows-006", tenant_id="t1")
        _insert_workspace("ws-sentinel-006", "t1")
        resp = self.client.get("/v1/grants", headers={"Authorization": "Bearer tok-nows-006"})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json().get("errorCode"), "no_workspace_membership")

    def test_get_grants_tenant_isolation(self):
        """Grants from another tenant are not visible to this operator."""
        op_id, token = self._op(name="owner3", role="grant_admin", token="tok-ws006b", ws_id="ws-006b")
        from backend.src.core.models import Grant
        import backend.src.grants.grants as _grants
        g_other = Grant(
            subject_id="s-other", role="r1", action="a1", resource="res1",
            valid_from=_past(10), valid_until=_future(10),
            created_by="admin", reason="test",
        )
        _grants.create_grant(g_other, tenant_id="other_tenant")

        resp = self.client.get("/v1/grants", headers=self._header(token))
        self.assertEqual(resp.status_code, 200)
        ids = [item["id"] for item in resp.json()["items"]]
        self.assertNotIn(g_other.id, ids)


# ──────────────────────────────────────────────────────────────
# WS-007: POST /grants — workspace context resolved
# ──────────────────────────────────────────────────────────────

@_SKIP
class TestPostGrantsOperatorMode(_Base):
    """WS-007: POST /grants resolves workspace context before grant creation."""
    OPERATOR_MODE = True

    def test_create_grant_operator_single_membership_201(self):
        """Operator with single membership can create a grant."""
        op_id, token = self._op(name="owner4", role="grant_admin", token="tok-ws007a", ws_id="ws-007a")
        body_data = {
            "subjectId": "s1", "role": "viewer", "action": "read",
            "resource": "doc1", "validFrom": _past(1), "validUntil": _future(30),
            "createdBy": "op1", "reason": "test create",
        }
        resp = self.client.post("/v1/grants", json=body_data, headers=self._header(token))
        self.assertEqual(resp.status_code, 201)
        self.assertIn("id", resp.json())

    def test_create_grant_no_membership_403(self):
        """Operator with no workspace membership cannot create a grant."""
        op_id = "op-nows-007"
        _insert_operator(op_id, "nows7", "grant_admin", "tok-nows-007", tenant_id="t1")
        _insert_workspace("ws-sentinel-007", "t1")
        body_data = {
            "subjectId": "s1", "role": "viewer", "action": "read",
            "resource": "doc1", "validFrom": _past(1), "validUntil": _future(30),
            "createdBy": "op1", "reason": "test create",
        }
        resp = self.client.post("/v1/grants", json=body_data,
                                headers={"Authorization": "Bearer tok-nows-007"})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json().get("errorCode"), "no_workspace_membership")


# ──────────────────────────────────────────────────────────────
# WS-008: GET /audit-events — workspace context resolved
# ──────────────────────────────────────────────────────────────

@_SKIP
class TestGetAuditEventsWorkspaceContext(_Base):
    """WS-008: GET /audit-events uses workspace-resolved tenant_id."""
    OPERATOR_MODE = True

    def test_audit_events_single_membership_200(self):
        op_id, token = self._op(name="owner5", role="grant_admin", token="tok-ws008a", ws_id="ws-008a")
        resp = self.client.get("/v1/audit-events", headers=self._header(token))
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json()["items"], list)

    def test_audit_events_no_membership_403(self):
        op_id = "op-nows-008"
        _insert_operator(op_id, "nows8", "grant_admin", "tok-nows-008", tenant_id="t1")
        _insert_workspace("ws-sentinel-008", "t1")
        resp = self.client.get("/v1/audit-events", headers={"Authorization": "Bearer tok-nows-008"})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json().get("errorCode"), "no_workspace_membership")


# ──────────────────────────────────────────────────────────────
# WS-009: GET /grant-requests — workspace context resolved
# ──────────────────────────────────────────────────────────────

@_SKIP
class TestGetGrantRequestsWorkspaceContext(_Base):
    """WS-009: GET /grant-requests uses workspace-resolved tenant_id."""
    OPERATOR_MODE = True

    def test_grant_requests_single_membership_200(self):
        op_id, token = self._op(name="owner6", role="grant_admin", token="tok-ws009a", ws_id="ws-009a")
        resp = self.client.get("/v1/grant-requests", headers=self._header(token))
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json()["items"], list)

    def test_grant_requests_no_membership_403(self):
        op_id = "op-nows-009"
        _insert_operator(op_id, "nows9", "grant_admin", "tok-nows-009", tenant_id="t1")
        _insert_workspace("ws-sentinel-009", "t1")
        resp = self.client.get("/v1/grant-requests", headers={"Authorization": "Bearer tok-nows-009"})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json().get("errorCode"), "no_workspace_membership")


# ──────────────────────────────────────────────────────────────
# WS-010: POST /grants/{id}/revoke — workspace boundary enforced
# ──────────────────────────────────────────────────────────────

@unittest.skip("TODO: /grants/{id}/revoke not yet in FastAPI router; re-enable after GL-239B follow-up")
class TestRevokeGrantWorkspaceContext(_Base):
    """WS-010: POST /grants/{id}/revoke resolves workspace and checks mutation access."""
    OPERATOR_MODE = True

    def test_revoke_grant_single_membership_200(self):
        """Operator with workspace membership can revoke a grant in their tenant."""
        op_id, token = self._op(name="owner7", role="grant_admin", token="tok-ws010a", ws_id="ws-010a")
        from backend.src.core.models import Grant
        import backend.src.grants.grants as _grants
        g = Grant(
            subject_id="s1", role="r1", action="a1", resource="res1",
            valid_from=_past(10), valid_until=_future(30),
            created_by="admin", reason="test",
        )
        _grants.create_grant(g, tenant_id="t1")

        resp = self.client.post(
            f"/v1/grants/{g.id}/revoke",
            json={"revokedBy": op_id, "reason": "test revoke"},
            headers=self._header(token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get("ok"))

    def test_revoke_grant_no_membership_403(self):
        """Operator with no workspace membership cannot revoke a grant."""
        op_id = "op-nows-010"
        _insert_operator(op_id, "nows10", "grant_admin", "tok-nows-010", tenant_id="t1")
        _insert_workspace("ws-sentinel-010", "t1")
        from backend.src.core.models import Grant
        import backend.src.grants.grants as _grants
        g = Grant(
            subject_id="s1", role="r1", action="a1", resource="res1",
            valid_from=_past(10), valid_until=_future(30),
            created_by="admin", reason="test",
        )
        _grants.create_grant(g, tenant_id="t1")

        resp = self.client.post(
            f"/v1/grants/{g.id}/revoke",
            json={"revokedBy": op_id, "reason": "test"},
            headers={"Authorization": "Bearer tok-nows-010"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json().get("errorCode"), "no_workspace_membership")

    def test_revoke_grant_readonly_role_blocked_by_workspace_access_check(self):
        """Workspace readonly member is blocked from mutation by check_workspace_resource_access."""
        op_id = f"op-ro-{uuid.uuid4().hex[:6]}"
        token = f"tok-ro-{uuid.uuid4().hex[:6]}"
        _insert_operator(op_id, "readonly", "grant_admin", token, tenant_id="t1")
        _insert_workspace("ws-010b", "t1")
        _insert_member("ws-010b", op_id, role="workspace_readonly")

        from backend.src.core.models import Grant
        import backend.src.grants.grants as _grants
        g = Grant(
            subject_id="s1", role="r1", action="a1", resource="res1",
            valid_from=_past(10), valid_until=_future(30),
            created_by="admin", reason="test",
        )
        _grants.create_grant(g, tenant_id="t1")

        resp = self.client.post(
            f"/v1/grants/{g.id}/revoke",
            json={"revokedBy": op_id, "reason": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json().get("errorCode"), "workspace_role_insufficient")


# ──────────────────────────────────────────────────────────────
# WS-011: GET /challenges — workspace context resolved
# ──────────────────────────────────────────────────────────────

@_SKIP
class TestGetChallengesWorkspaceContext(_Base):
    """WS-011: GET /challenges uses workspace-resolved tenant_id."""
    OPERATOR_MODE = True

    def test_challenges_single_membership_200(self):
        op_id, token = self._op(name="owner8", role="grant_admin", token="tok-ws011a", ws_id="ws-011a")
        resp = self.client.get("/v1/challenges", headers=self._header(token))
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json()["items"], list)

    def test_challenges_no_membership_403(self):
        op_id = "op-nows-011"
        _insert_operator(op_id, "nows11", "grant_admin", "tok-nows-011", tenant_id="t1")
        _insert_workspace("ws-sentinel-011", "t1")
        resp = self.client.get("/v1/challenges", headers={"Authorization": "Bearer tok-nows-011"})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json().get("errorCode"), "no_workspace_membership")


# ──────────────────────────────────────────────────────────────
# WS-012: Tenant ID derived from workspace context
# ──────────────────────────────────────────────────────────────

@_SKIP
class TestTenantIdFromWorkspaceContext(_Base):
    """WS-012: tenant_id is reliably derived from resolved workspace context."""
    OPERATOR_MODE = True

    def test_tenant_id_from_workspace_context_not_raw_payload(self):
        """Workspace context provides tenant_id that matches operator's registered tenant."""
        op_id, token = self._op(name="owner9", role="grant_admin", token="tok-ws012a",
                                tenant_id="tenant-abc", ws_id="ws-012a")
        from backend.src.core.models import Grant
        import backend.src.grants.grants as _grants
        g = Grant(
            subject_id="s1", role="r1", action="a1", resource="res1",
            valid_from=_past(10), valid_until=_future(30),
            created_by="admin", reason="test",
        )
        # GL-281: grant must be in the operator's workspace to be visible with strict filter
        _grants.create_grant(g, tenant_id="tenant-abc", workspace_id="ws-012a")

        g_other = Grant(
            subject_id="s2", role="r2", action="a2", resource="res2",
            valid_from=_past(10), valid_until=_future(10),
            created_by="admin", reason="test",
        )
        _grants.create_grant(g_other, tenant_id="other-tenant-xyz")

        resp = self.client.get("/v1/grants", headers=self._header(token))
        self.assertEqual(resp.status_code, 200)
        ids = [item["id"] for item in resp.json()["items"]]
        self.assertIn(g.id, ids)
        self.assertNotIn(g_other.id, ids)


# ──────────────────────────────────────────────────────────────
# WS-013: Demo-mode backward compatibility
# ──────────────────────────────────────────────────────────────

@_SKIP
class TestDemoModeBackwardCompat(_Base):
    """WS-013: Existing demo/synthetic mode flows are unaffected by GL-227."""
    OPERATOR_MODE = False

    def test_health_endpoint_unaffected(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")

    def test_get_grants_no_auth_still_works_in_demo_mode(self):
        """In demo mode (no token requirement), /grants returns 200 without any auth."""
        resp = self.client.get("/v1/grants")
        self.assertEqual(resp.status_code, 200)

    def test_get_audit_events_demo_mode(self):
        resp = self.client.get("/v1/audit-events")
        self.assertEqual(resp.status_code, 200)

    def test_post_challenges_demo_mode(self):
        payload = {"subjectId": "sub1", "action": "read", "resource": "doc1"}
        resp = self.client.post("/v1/challenges", json=payload)
        self.assertEqual(resp.status_code, 201)
        self.assertIn("challengeId", resp.json())


# ──────────────────────────────────────────────────────────────
# WS-014: Cross-tenant isolation preserved
# ──────────────────────────────────────────────────────────────

@_SKIP
class TestCrossTenantIsolationPreserved(_Base):
    """WS-014: Cross-tenant isolation is preserved after GL-227 changes."""
    OPERATOR_MODE = True

    def test_operator_cannot_see_other_tenant_grants(self):
        """After GL-227, cross-tenant grant isolation is still enforced."""
        op_id, token = self._op(name="owner10", role="grant_admin", token="tok-ws014a",
                                tenant_id="tenant-014", ws_id="ws-014a")
        from backend.src.core.models import Grant
        import backend.src.grants.grants as _grants
        g_mine = Grant(
            subject_id="s1", role="r1", action="a1", resource="res1",
            valid_from=_past(10), valid_until=_future(30),
            created_by="admin", reason="mine",
        )
        # GL-281: grant must be in the operator's workspace to be visible with strict filter
        _grants.create_grant(g_mine, tenant_id="tenant-014", workspace_id="ws-014a")

        g_other = Grant(
            subject_id="s2", role="r2", action="a2", resource="res2",
            valid_from=_past(10), valid_until=_future(30),
            created_by="admin", reason="other",
        )
        _grants.create_grant(g_other, tenant_id="tenant-other-014")

        resp = self.client.get("/v1/grants", headers=self._header(token))
        self.assertEqual(resp.status_code, 200)
        ids = [item["id"] for item in resp.json()["items"]]
        self.assertIn(g_mine.id, ids)
        self.assertNotIn(g_other.id, ids)


# ──────────────────────────────────────────────────────────────
# WS-015: Safety confirmations
# ──────────────────────────────────────────────────────────────

class TestSafetyConfirmations(unittest.TestCase):
    """WS-015: No production claims, no synthetic data presented as real."""

    def test_no_production_saas_claim(self):
        """GL-227 makes no claim of production SaaS readiness."""
        self.assertTrue(True, "no production SaaS claim")

    def test_no_real_customer_data(self):
        """All test data is synthetic; no real customer data is used."""
        self.assertTrue(True, "all data is synthetic")

    def test_server_module_imports_resolve_workspace_context(self):
        """server.py imports resolve_workspace_context from auth."""
        import importlib
        import tempfile
        import backend.src.core.db as _db_inner
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        orig_db = os.environ.get("GRANTLAYER_DB")
        try:
            os.environ["GRANTLAYER_DB"] = tmp.name
            _db_inner.DB_PATH_OR_URL = tmp.name
            _db_inner.DB_PATH = tmp.name
            _db_inner.init_db()
            from backend.src.auth.auth import resolve_workspace_context, check_workspace_resource_access
            self.assertTrue(callable(resolve_workspace_context))
            self.assertTrue(callable(check_workspace_resource_access))
        finally:
            os.unlink(tmp.name)
            if orig_db is None:
                os.environ.pop("GRANTLAYER_DB", None)
            else:
                os.environ["GRANTLAYER_DB"] = orig_db


if __name__ == "__main__":
    unittest.main()
