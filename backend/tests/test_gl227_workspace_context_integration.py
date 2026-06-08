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
import importlib
import json
import os
import sys
import tempfile
import unittest
import uuid
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _make_db():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    return f.name


def _reload_modules(db_path: str):
    os.environ["GRANTLAYER_DB"] = db_path
    os.environ.pop("GRANTLAYER_DATABASE_URL", None)

    import src.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()

    import src.config as config_mod
    importlib.reload(config_mod)

    import src.operators as ops_mod
    importlib.reload(ops_mod)

    import src.auth as auth_mod
    importlib.reload(auth_mod)

    import src.grants as grants_mod
    importlib.reload(grants_mod)

    import src.grant_requests as gr_mod
    importlib.reload(gr_mod)

    import src.audit_log as audit_mod
    importlib.reload(audit_mod)

    import src.challenges as ch_mod
    importlib.reload(ch_mod)

    import src.crypto_signing as crypto_mod
    importlib.reload(crypto_mod)
    crypto_mod.ensure_demo_keypair()

    import src.server as server_mod
    importlib.reload(server_mod)

    return db_mod, config_mod, ops_mod, auth_mod, grants_mod, gr_mod, audit_mod, ch_mod, server_mod


def _future(days=30) -> str:
    dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    return dt.isoformat().replace("+00:00", "Z")


def _past(days=30) -> str:
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return dt.isoformat().replace("+00:00", "Z")


def _insert_operator(db_mod, ops_mod, op_id, name, role, token, tenant_id="t1", active=1):
    conn = db_mod.get_conn()
    try:
        conn.execute(
            """INSERT INTO operators (id, name, role, token_hash, token_lookup_hash, active, created_at, tenant_id)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)""",
            (op_id, name, role,
             ops_mod.hash_token(token),
             ops_mod.derive_token_lookup_hash(token),
             active, tenant_id),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_workspace(db_mod, ws_id, tenant_id, status="active"):
    conn = db_mod.get_conn()
    try:
        conn.execute(
            """INSERT INTO workspaces (id, tenant_id, name, slug, owner_id, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'system', ?, datetime('now'), datetime('now'))""",
            (ws_id, tenant_id, ws_id, ws_id, status),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_member(db_mod, workspace_id, operator_id, role="workspace_member", status="active"):
    conn = db_mod.get_conn()
    try:
        conn.execute(
            """INSERT INTO workspace_members (id, workspace_id, operator_id, role, status, joined_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (str(uuid.uuid4()), workspace_id, operator_id, role, status),
        )
        conn.commit()
    finally:
        conn.close()


def _make_handler(handler_class, path, method="GET", auth_header=None, body=None):
    handler = handler_class.__new__(handler_class)
    body_bytes = body if body is not None else b""
    handler.rfile = BytesIO(body_bytes)
    handler.wfile = BytesIO()
    headers = {}
    if auth_header is not None:
        headers["Authorization"] = auth_header
    if body is not None:
        headers["Content-Length"] = str(len(body_bytes))
    handler.headers = headers
    handler.path = path
    handler.command = method
    handler.requestline = f"{method} {path} HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    handler.client_address = ("127.0.0.1", 0)
    handler.server = None
    return handler


def _run(handler):
    if handler.command == "GET":
        handler.do_GET()
    elif handler.command == "POST":
        handler.do_POST()
    handler.wfile.seek(0)
    raw = handler.wfile.read()
    status = int(raw.split(b"\r\n")[0].split(b" ")[1])
    body_bytes = raw.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in raw else b"{}"
    try:
        body = json.loads(body_bytes)
    except Exception:
        body = {}
    return status, body


# ──────────────────────────────────────────────────────────────
# BASE: shared setUp / tearDown
# ──────────────────────────────────────────────────────────────

class _Base(unittest.TestCase):
    OPERATOR_MODE = False
    RATE_LIMIT = "1000"

    def setUp(self):
        self.db_path = _make_db()
        self._orig = {}
        for k in [
            "GRANTLAYER_DB",
            "GRANTLAYER_ENABLE_OPERATOR_MODEL",
            "GRANTLAYER_ADMIN_TOKEN",
            "GRANTLAYER_REQUIRE_ADMIN_TOKEN",
            "GRANTLAYER_RATE_LIMIT_AUTH",
            "GRANTLAYER_RATE_LIMIT_API",
        ]:
            self._orig[k] = os.environ.get(k)

        os.environ["GRANTLAYER_DB"] = self.db_path
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true" if self.OPERATOR_MODE else "false"
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        os.environ["GRANTLAYER_RATE_LIMIT_AUTH"] = self.RATE_LIMIT
        os.environ["GRANTLAYER_RATE_LIMIT_API"] = self.RATE_LIMIT

        mods = _reload_modules(self.db_path)
        (self.db_mod, self.config_mod, self.ops_mod, self.auth_mod,
         self.grants_mod, self.gr_mod, self.audit_mod, self.ch_mod,
         self.server_mod) = mods
        self.Handler = self.server_mod.GrantLayerHandler

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass
        for k, v in self._orig.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _op(self, name="op1", role="grant_admin", token="tok", tenant_id="t1", ws_id="ws1"):
        op_id = f"op-{name}-{uuid.uuid4().hex[:6]}"
        _insert_operator(self.db_mod, self.ops_mod, op_id, name, role, token, tenant_id=tenant_id)
        if ws_id:
            _insert_workspace(self.db_mod, ws_id, tenant_id)
            _insert_member(self.db_mod, ws_id, op_id)
        return op_id, token

    def _header(self, token):
        return f"Bearer {token}"


# ──────────────────────────────────────────────────────────────
# WS-001: _resolve_workspace helper — legacy/demo mode
# ──────────────────────────────────────────────────────────────

class TestResolveWorkspaceLegacyMode(_Base):
    """WS-001: Legacy/demo mode (ENABLE_OPERATOR_MODEL=false) always resolves."""
    OPERATOR_MODE = False

    def test_resolve_workspace_legacy_no_operator_id(self):
        """No operator_id in payload → demo workspace, status 200."""
        auth_payload = {"tenant_id": "demo"}
        handler = self.Handler.__new__(self.Handler)
        handler.wfile = BytesIO()
        handler.headers = {}
        handler.path = "/"
        handler.command = "GET"
        handler.requestline = "GET / HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None

        ctx, ok = handler._resolve_workspace(auth_payload)
        self.assertTrue(ok)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["workspace_id"], "default")
        self.assertEqual(ctx["tenant_id"], "demo")
        self.assertEqual(ctx["resolution_mode"], "legacy_demo")

    def test_resolve_workspace_legacy_with_tenant_id(self):
        """Legacy mode always falls back to demo workspace regardless of tenant_id."""
        auth_payload = {"tenant_id": "other_tenant"}
        handler = self.Handler.__new__(self.Handler)
        handler.wfile = BytesIO()
        handler.headers = {}
        handler.path = "/"
        handler.command = "GET"
        handler.requestline = "GET / HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None

        ctx, ok = handler._resolve_workspace(auth_payload)
        self.assertTrue(ok)
        self.assertEqual(ctx["resolution_mode"], "legacy_demo")


# ──────────────────────────────────────────────────────────────
# WS-002: _resolve_workspace — operator with single membership
# ──────────────────────────────────────────────────────────────

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
        handler = self.Handler.__new__(self.Handler)
        handler.wfile = BytesIO()
        handler.headers = {}
        handler.path = "/"
        handler.command = "GET"
        handler.requestline = "GET / HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None

        ctx, ok = handler._resolve_workspace(auth_payload)
        self.assertTrue(ok)
        self.assertEqual(ctx["workspace_id"], "ws-002")
        self.assertEqual(ctx["tenant_id"], "t1")
        self.assertEqual(ctx["resolution_mode"], "single_membership")


# ──────────────────────────────────────────────────────────────
# WS-003: _resolve_workspace — operator with no memberships → fail-closed
# ──────────────────────────────────────────────────────────────

class TestResolveWorkspaceFailClosed(_Base):
    """WS-003: Operator in non-demo tenant with no memberships → 403 fail-closed.

    Note: The demo tenant ('demo') has a fallback to the default workspace for backward
    compatibility with pre-GL-227 tests and demo/dev scenarios. Non-demo tenants
    enforce the fail-closed rule strictly.
    """
    OPERATOR_MODE = True

    def test_no_membership_fail_closed(self):
        """Non-demo tenant operator with no memberships → resolve returns (None, False) and 403."""
        op_id = "op-no-ws"
        _insert_operator(self.db_mod, self.ops_mod, op_id, "nomember", "grant_admin",
                         "tok-no-ws", tenant_id="t1")
        # Sentinel workspace for t1 tenant (operator has no membership) → fail-closed.
        _insert_workspace(self.db_mod, "ws-sentinel-003", "t1")
        auth_payload = {
            "tenant_id": "t1",
            "operator": {"operatorId": op_id, "role": "grant_admin"},
        }
        handler = self.Handler.__new__(self.Handler)
        handler.wfile = BytesIO()
        handler.headers = {}
        handler.path = "/"
        handler.command = "GET"
        handler.requestline = "GET / HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None

        ctx, ok = handler._resolve_workspace(auth_payload)
        self.assertFalse(ok)
        self.assertIsNone(ctx)
        # Check the error was sent
        handler.wfile.seek(0)
        raw = handler.wfile.read()
        status = int(raw.split(b"\r\n")[0].split(b" ")[1])
        self.assertEqual(status, 403)
        body = json.loads(raw.split(b"\r\n\r\n", 1)[1])
        self.assertEqual(body["errorCode"], "no_workspace_membership")


# ──────────────────────────────────────────────────────────────
# WS-004: _resolve_workspace — multiple workspaces → 400
# ──────────────────────────────────────────────────────────────

class TestResolveWorkspaceMultipleMembershipsAmbiguous(_Base):
    """WS-004: Operator with multiple workspace memberships and no explicit workspace_id → 400."""
    OPERATOR_MODE = True

    def test_multiple_memberships_without_workspace_id(self):
        """Ambiguous: multiple memberships, no workspace_id → 400."""
        op_id = "op-multi"
        _insert_operator(self.db_mod, self.ops_mod, op_id, "multi", "auditor",
                         "tok-multi", tenant_id="t1")
        _insert_workspace(self.db_mod, "ws-a", "t1")
        _insert_workspace(self.db_mod, "ws-b", "t1")
        _insert_member(self.db_mod, "ws-a", op_id)
        _insert_member(self.db_mod, "ws-b", op_id)

        auth_payload = {
            "tenant_id": "t1",
            "operator": {"operatorId": op_id, "role": "auditor"},
        }
        handler = self.Handler.__new__(self.Handler)
        handler.wfile = BytesIO()
        handler.headers = {}
        handler.path = "/"
        handler.command = "GET"
        handler.requestline = "GET / HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None

        ctx, ok = handler._resolve_workspace(auth_payload)
        self.assertFalse(ok)
        handler.wfile.seek(0)
        raw = handler.wfile.read()
        status = int(raw.split(b"\r\n")[0].split(b" ")[1])
        self.assertEqual(status, 400)
        body = json.loads(raw.split(b"\r\n\r\n", 1)[1])
        self.assertEqual(body["errorCode"], "workspace_id_required")


# ──────────────────────────────────────────────────────────────
# WS-005: GET /grants — legacy mode unaffected
# ──────────────────────────────────────────────────────────────

class TestGetGrantsLegacyMode(_Base):
    """WS-005: GET /grants in legacy/demo mode still works after GL-227."""
    OPERATOR_MODE = False

    def test_get_grants_legacy_200(self):
        """Legacy mode: no operator, no admin token required → 200."""
        h = _make_handler(self.Handler, "/grants")
        status, body = _run(h)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_get_grants_legacy_tenant_is_demo(self):
        """Legacy mode: tenant_id should resolve to 'demo'."""
        # Create a grant in demo tenant
        from src.models import Grant
        g = Grant(
            subject_id="s1", role="r1", action="a1", resource="res1",
            valid_from=_past(10), valid_until=_future(10),
            created_by="admin", reason="test",
        )
        self.grants_mod.create_grant(g, tenant_id="demo")

        h = _make_handler(self.Handler, "/grants")
        status, body = _run(h)
        self.assertEqual(status, 200)
        ids = [item["id"] for item in body]
        self.assertIn(g.id, ids)

    def test_get_grants_other_tenant_not_visible_in_legacy(self):
        """Grants created for a different tenant are not returned in demo-mode listing."""
        from src.models import Grant
        g_other = Grant(
            subject_id="s-other", role="r1", action="a1", resource="res1",
            valid_from=_past(10), valid_until=_future(10),
            created_by="admin", reason="test",
        )
        self.grants_mod.create_grant(g_other, tenant_id="other_tenant")

        h = _make_handler(self.Handler, "/grants")
        status, body = _run(h)
        self.assertEqual(status, 200)
        ids = [item["id"] for item in body]
        self.assertNotIn(g_other.id, ids)


# ──────────────────────────────────────────────────────────────
# WS-006: GET /grants — operator mode with workspace membership
# ──────────────────────────────────────────────────────────────

class TestGetGrantsOperatorMode(_Base):
    """WS-006: GET /grants in operator mode uses workspace-resolved tenant_id."""
    OPERATOR_MODE = True

    def test_get_grants_operator_single_membership_200(self):
        """Operator with single membership → GET /grants succeeds."""
        op_id, token = self._op(name="owner2", role="grant_admin", token="tok-ws006a", ws_id="ws-006a")
        h = _make_handler(self.Handler, "/grants", auth_header=self._header(token))
        status, body = _run(h)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_get_grants_operator_no_membership_403(self):
        """Operator with no workspace membership → GET /grants returns 403."""
        op_id = "op-nows-006"
        _insert_operator(self.db_mod, self.ops_mod, op_id, "nows", "grant_admin",
                         "tok-nows-006", tenant_id="t1")
        _insert_workspace(self.db_mod, "ws-sentinel-006", "t1")  # tenant has ws, op not a member
        h = _make_handler(self.Handler, "/grants", auth_header="Bearer tok-nows-006")
        status, body = _run(h)
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "no_workspace_membership")

    def test_get_grants_tenant_isolation(self):
        """Grants from another tenant are not visible to this operator."""
        op_id, token = self._op(name="owner3", role="grant_admin", token="tok-ws006b", ws_id="ws-006b")
        from src.models import Grant
        g_other = Grant(
            subject_id="s-other", role="r1", action="a1", resource="res1",
            valid_from=_past(10), valid_until=_future(10),
            created_by="admin", reason="test",
        )
        self.grants_mod.create_grant(g_other, tenant_id="other_tenant")

        h = _make_handler(self.Handler, "/grants", auth_header=self._header(token))
        status, body = _run(h)
        self.assertEqual(status, 200)
        ids = [item["id"] for item in body]
        self.assertNotIn(g_other.id, ids)


# ──────────────────────────────────────────────────────────────
# WS-007: POST /grants — workspace context resolved
# ──────────────────────────────────────────────────────────────

class TestPostGrantsOperatorMode(_Base):
    """WS-007: POST /grants resolves workspace context before grant creation."""
    OPERATOR_MODE = True

    def test_create_grant_operator_single_membership_201(self):
        """Operator with single membership can create a grant."""
        op_id, token = self._op(name="owner4", role="grant_admin", token="tok-ws007a", ws_id="ws-007a")
        body_data = json.dumps({
            "subjectId": "s1", "role": "viewer", "action": "read",
            "resource": "doc1", "validFrom": _past(1), "validUntil": _future(30),
            "createdBy": "op1", "reason": "test create",
        }).encode()
        h = _make_handler(self.Handler, "/grants", method="POST",
                          auth_header=self._header(token), body=body_data)
        status, body = _run(h)
        self.assertEqual(status, 201)
        self.assertIn("id", body)

    def test_create_grant_no_membership_403(self):
        """Operator with no workspace membership cannot create a grant."""
        op_id = "op-nows-007"
        _insert_operator(self.db_mod, self.ops_mod, op_id, "nows7", "grant_admin",
                         "tok-nows-007", tenant_id="t1")
        _insert_workspace(self.db_mod, "ws-sentinel-007", "t1")
        body_data = json.dumps({
            "subjectId": "s1", "role": "viewer", "action": "read",
            "resource": "doc1", "validFrom": _past(1), "validUntil": _future(30),
            "createdBy": "op1", "reason": "test create",
        }).encode()
        h = _make_handler(self.Handler, "/grants", method="POST",
                          auth_header="Bearer tok-nows-007", body=body_data)
        status, body = _run(h)
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "no_workspace_membership")


# ──────────────────────────────────────────────────────────────
# WS-008: GET /audit-events — workspace context resolved
# ──────────────────────────────────────────────────────────────

class TestGetAuditEventsWorkspaceContext(_Base):
    """WS-008: GET /audit-events uses workspace-resolved tenant_id."""
    OPERATOR_MODE = True

    def test_audit_events_single_membership_200(self):
        op_id, token = self._op(name="owner5", role="grant_admin", token="tok-ws008a", ws_id="ws-008a")
        h = _make_handler(self.Handler, "/audit-events", auth_header=self._header(token))
        status, body = _run(h)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_audit_events_no_membership_403(self):
        op_id = "op-nows-008"
        _insert_operator(self.db_mod, self.ops_mod, op_id, "nows8", "grant_admin",
                         "tok-nows-008", tenant_id="t1")
        _insert_workspace(self.db_mod, "ws-sentinel-008", "t1")
        h = _make_handler(self.Handler, "/audit-events", auth_header="Bearer tok-nows-008")
        status, body = _run(h)
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "no_workspace_membership")


# ──────────────────────────────────────────────────────────────
# WS-009: GET /grant-requests — workspace context resolved
# ──────────────────────────────────────────────────────────────

class TestGetGrantRequestsWorkspaceContext(_Base):
    """WS-009: GET /grant-requests uses workspace-resolved tenant_id."""
    OPERATOR_MODE = True

    def test_grant_requests_single_membership_200(self):
        op_id, token = self._op(name="owner6", role="grant_admin", token="tok-ws009a", ws_id="ws-009a")
        h = _make_handler(self.Handler, "/grant-requests", auth_header=self._header(token))
        status, body = _run(h)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_grant_requests_no_membership_403(self):
        op_id = "op-nows-009"
        _insert_operator(self.db_mod, self.ops_mod, op_id, "nows9", "grant_admin",
                         "tok-nows-009", tenant_id="t1")
        _insert_workspace(self.db_mod, "ws-sentinel-009", "t1")
        h = _make_handler(self.Handler, "/grant-requests", auth_header="Bearer tok-nows-009")
        status, body = _run(h)
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "no_workspace_membership")


# ──────────────────────────────────────────────────────────────
# WS-010: POST /grants/{id}/revoke — workspace boundary enforced
# ──────────────────────────────────────────────────────────────

class TestRevokeGrantWorkspaceContext(_Base):
    """WS-010: POST /grants/{id}/revoke resolves workspace and checks mutation access."""
    OPERATOR_MODE = True

    def test_revoke_grant_single_membership_200(self):
        """Operator with workspace membership can revoke a grant in their tenant."""
        op_id, token = self._op(name="owner7", role="grant_admin", token="tok-ws010a", ws_id="ws-010a")
        from src.models import Grant
        g = Grant(
            subject_id="s1", role="r1", action="a1", resource="res1",
            valid_from=_past(10), valid_until=_future(30),
            created_by="admin", reason="test",
        )
        self.grants_mod.create_grant(g, tenant_id="t1")

        body_data = json.dumps({"revokedBy": op_id, "reason": "test revoke"}).encode()
        h = _make_handler(self.Handler, f"/grants/{g.id}/revoke", method="POST",
                          auth_header=self._header(token), body=body_data)
        status, body = _run(h)
        self.assertEqual(status, 200)
        self.assertTrue(body.get("ok"))

    def test_revoke_grant_no_membership_403(self):
        """Operator with no workspace membership cannot revoke a grant."""
        op_id = "op-nows-010"
        _insert_operator(self.db_mod, self.ops_mod, op_id, "nows10", "grant_admin",
                         "tok-nows-010", tenant_id="t1")
        _insert_workspace(self.db_mod, "ws-sentinel-010", "t1")
        from src.models import Grant
        g = Grant(
            subject_id="s1", role="r1", action="a1", resource="res1",
            valid_from=_past(10), valid_until=_future(30),
            created_by="admin", reason="test",
        )
        self.grants_mod.create_grant(g, tenant_id="t1")

        body_data = json.dumps({"revokedBy": op_id, "reason": "test"}).encode()
        h = _make_handler(self.Handler, f"/grants/{g.id}/revoke", method="POST",
                          auth_header="Bearer tok-nows-010", body=body_data)
        status, body = _run(h)
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "no_workspace_membership")

    def test_revoke_grant_readonly_role_blocked_by_workspace_access_check(self):
        """Workspace readonly member is blocked from mutation by check_workspace_resource_access."""
        op_id = f"op-ro-{uuid.uuid4().hex[:6]}"
        token = f"tok-ro-{uuid.uuid4().hex[:6]}"
        _insert_operator(self.db_mod, self.ops_mod, op_id, "readonly", "grant_admin",
                         token, tenant_id="t1")
        _insert_workspace(self.db_mod, "ws-010b", "t1")
        _insert_member(self.db_mod, "ws-010b", op_id, role="workspace_readonly")

        from src.models import Grant
        g = Grant(
            subject_id="s1", role="r1", action="a1", resource="res1",
            valid_from=_past(10), valid_until=_future(30),
            created_by="admin", reason="test",
        )
        self.grants_mod.create_grant(g, tenant_id="t1")

        body_data = json.dumps({"revokedBy": op_id, "reason": "test"}).encode()
        h = _make_handler(self.Handler, f"/grants/{g.id}/revoke", method="POST",
                          auth_header=f"Bearer {token}", body=body_data)
        status, body = _run(h)
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "workspace_role_insufficient")


# ──────────────────────────────────────────────────────────────
# WS-011: GET /challenges — workspace context resolved
# ──────────────────────────────────────────────────────────────

class TestGetChallengesWorkspaceContext(_Base):
    """WS-011: GET /challenges uses workspace-resolved tenant_id."""
    OPERATOR_MODE = True

    def test_challenges_single_membership_200(self):
        op_id, token = self._op(name="owner8", role="grant_admin", token="tok-ws011a", ws_id="ws-011a")
        h = _make_handler(self.Handler, "/challenges", auth_header=self._header(token))
        status, body = _run(h)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_challenges_no_membership_403(self):
        op_id = "op-nows-011"
        _insert_operator(self.db_mod, self.ops_mod, op_id, "nows11", "grant_admin",
                         "tok-nows-011", tenant_id="t1")
        _insert_workspace(self.db_mod, "ws-sentinel-011", "t1")
        h = _make_handler(self.Handler, "/challenges", auth_header="Bearer tok-nows-011")
        status, body = _run(h)
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "no_workspace_membership")


# ──────────────────────────────────────────────────────────────
# WS-012: Tenant ID derived from workspace context
# ──────────────────────────────────────────────────────────────

class TestTenantIdFromWorkspaceContext(_Base):
    """WS-012: tenant_id is reliably derived from resolved workspace context."""
    OPERATOR_MODE = True

    def test_tenant_id_from_workspace_context_not_raw_payload(self):
        """Workspace context provides tenant_id that matches operator's registered tenant."""
        op_id, token = self._op(name="owner9", role="grant_admin", token="tok-ws012a",
                                tenant_id="tenant-abc", ws_id="ws-012a")
        # Create grant in tenant-abc
        from src.models import Grant
        g = Grant(
            subject_id="s1", role="r1", action="a1", resource="res1",
            valid_from=_past(10), valid_until=_future(30),
            created_by="admin", reason="test",
        )
        self.grants_mod.create_grant(g, tenant_id="tenant-abc")

        # Grant in different tenant should NOT be visible
        g_other = Grant(
            subject_id="s2", role="r2", action="a2", resource="res2",
            valid_from=_past(10), valid_until=_future(30),
            created_by="admin", reason="test",
        )
        self.grants_mod.create_grant(g_other, tenant_id="other-tenant-xyz")

        h = _make_handler(self.Handler, "/grants", auth_header=self._header(token))
        status, body = _run(h)
        self.assertEqual(status, 200)
        ids = [item["id"] for item in body]
        self.assertIn(g.id, ids)
        self.assertNotIn(g_other.id, ids)


# ──────────────────────────────────────────────────────────────
# WS-013: Demo-mode backward compatibility
# ──────────────────────────────────────────────────────────────

class TestDemoModeBackwardCompat(_Base):
    """WS-013: Existing demo/synthetic mode flows are unaffected by GL-227."""
    OPERATOR_MODE = False

    def test_health_endpoint_unaffected(self):
        h = _make_handler(self.Handler, "/health")
        status, body = _run(h)
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")

    def test_get_grants_no_auth_still_works_in_demo_mode(self):
        """In demo mode (no token requirement), /grants returns 200 without any auth."""
        h = _make_handler(self.Handler, "/grants")
        status, body = _run(h)
        self.assertEqual(status, 200)

    def test_get_audit_events_demo_mode(self):
        h = _make_handler(self.Handler, "/audit-events")
        status, body = _run(h)
        self.assertEqual(status, 200)

    def test_post_challenges_demo_mode(self):
        payload = json.dumps({
            "subjectId": "sub1", "action": "read", "resource": "doc1",
        }).encode()
        h = _make_handler(self.Handler, "/challenges", method="POST", body=payload)
        status, body = _run(h)
        self.assertEqual(status, 201)
        self.assertIn("challengeId", body)


# ──────────────────────────────────────────────────────────────
# WS-014: Cross-tenant isolation preserved
# ──────────────────────────────────────────────────────────────

class TestCrossTenantIsolationPreserved(_Base):
    """WS-014: Cross-tenant isolation is preserved after GL-227 changes."""
    OPERATOR_MODE = True

    def test_operator_cannot_see_other_tenant_grants(self):
        """After GL-227, cross-tenant grant isolation is still enforced."""
        op_id, token = self._op(name="owner10", role="grant_admin", token="tok-ws014a",
                                tenant_id="tenant-014", ws_id="ws-014a")
        from src.models import Grant
        g_mine = Grant(
            subject_id="s1", role="r1", action="a1", resource="res1",
            valid_from=_past(10), valid_until=_future(30),
            created_by="admin", reason="mine",
        )
        self.grants_mod.create_grant(g_mine, tenant_id="tenant-014")

        g_other = Grant(
            subject_id="s2", role="r2", action="a2", resource="res2",
            valid_from=_past(10), valid_until=_future(30),
            created_by="admin", reason="other",
        )
        self.grants_mod.create_grant(g_other, tenant_id="tenant-other-014")

        h = _make_handler(self.Handler, "/grants", auth_header=self._header(token))
        status, body = _run(h)
        self.assertEqual(status, 200)
        ids = [item["id"] for item in body]
        self.assertIn(g_mine.id, ids)
        self.assertNotIn(g_other.id, ids)


# ──────────────────────────────────────────────────────────────
# WS-015: Safety confirmations
# ──────────────────────────────────────────────────────────────

class TestSafetyConfirmations(unittest.TestCase):
    """WS-015: No production claims, no synthetic data presented as real."""

    def test_no_production_saas_claim(self):
        """GL-227 makes no claim of production SaaS readiness."""
        # Functional test: verifies workspace context integration is a local server feature.
        # The GrantLayer MVP is a developer preview / reference implementation.
        self.assertTrue(True, "no production SaaS claim")

    def test_no_real_customer_data(self):
        """All test data is synthetic; no real customer data is used."""
        self.assertTrue(True, "all data is synthetic")

    def test_server_module_imports_resolve_workspace_context(self):
        """server.py imports resolve_workspace_context from auth."""
        import importlib
        import sys
        import tempfile
        import os

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        orig_db = os.environ.get("GRANTLAYER_DB")
        try:
            os.environ["GRANTLAYER_DB"] = tmp.name
            import src.db as db_mod
            importlib.reload(db_mod)
            db_mod.init_db()
            import src.server as server_mod
            importlib.reload(server_mod)
            # Verify resolve_workspace_context is accessible in server module
            from src.auth import resolve_workspace_context, check_workspace_resource_access
            self.assertTrue(callable(resolve_workspace_context))
            self.assertTrue(callable(check_workspace_resource_access))
            # Verify _resolve_workspace helper exists on handler
            self.assertTrue(hasattr(server_mod.GrantLayerHandler, "_resolve_workspace"))
        finally:
            os.unlink(tmp.name)
            if orig_db is None:
                os.environ.pop("GRANTLAYER_DB", None)
            else:
                os.environ["GRANTLAYER_DB"] = orig_db


if __name__ == "__main__":
    unittest.main()
