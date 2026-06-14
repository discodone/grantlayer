"""GL-225/226 Workspace Context Resolver + Authorization Enforcement — test suite.

Covers:
- Context resolver: valid operator with single membership → workspace resolved
- Context resolver: operator with explicit workspace_id + membership → accepted
- Context resolver: operator with explicit workspace_id but no membership → 403
- Context resolver: operator with explicit workspace_id in wrong tenant → 403
- Context resolver: operator with no memberships → 403 (fail-closed)
- Context resolver: multiple memberships, no workspace_id → 400 (ambiguous)
- Context resolver: multiple memberships, with workspace_id → resolved
- Context resolver: cross-workspace role (owner) → explicit bypass documented
- Context resolver: legacy/demo mode (no operator model) → demo workspace
- Context resolver: client-supplied workspace_id ignored unless verified
- Context resolver: inactive workspace → 403
- Cross-workspace lookup denial (resource in other workspace, no bypass)
- Cross-workspace mutation denial
- Cross-tenant denial (always, no bypass)
- Admin bypass (cross_workspace_access=True): lookup allowed
- Admin bypass (cross_workspace_access=True): mutation allowed
- Readonly role mutation denial
- Demo/synthetic compatibility
- Safety confirmations: no production SaaS claim, no real customer data
- Docs and JSON artifact exist with required keys
- Gate script (if present) compiles and accepts --dry-run / --plan
"""

from __future__ import annotations

import importlib
import json
import os
import pathlib
import sqlite3
import sys
import tempfile
import unittest
import uuid

# ── repo paths ──────────────────────────────────────────────────────────────────

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "backend" / "src"

MD_PATH = REPO_ROOT / "docs" / "workspace_context_resolver_authorization.md"
JSON_PATH = REPO_ROOT / "docs" / "examples" / "gl225_226" / "workspace_context_resolver_authorization.json"
GATE_SCRIPT = REPO_ROOT / "scripts" / "ops" / "gl225_226_workspace_context_gate.py"

# ── helpers ─────────────────────────────────────────────────────────────────────

def _fresh_conn() -> sqlite3.Connection:
    """Return a fresh in-memory SQLite connection."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _setup_workspace_tables(conn: sqlite3.Connection) -> None:
    """Create the minimal workspace/membership tables needed for resolver tests."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id          TEXT PRIMARY KEY,
            tenant_id   TEXT NOT NULL,
            name        TEXT NOT NULL,
            slug        TEXT NOT NULL,
            owner_id    TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'active',
            description TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS workspace_members (
            id           TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            operator_id  TEXT NOT NULL,
            role         TEXT NOT NULL DEFAULT 'workspace_member',
            invited_by   TEXT,
            joined_at    TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'active'
        );
    """)
    conn.commit()


def _insert_workspace(conn: sqlite3.Connection, ws_id: str, tenant_id: str, status: str = "active") -> None:
    conn.execute(
        "INSERT INTO workspaces (id, tenant_id, name, slug, owner_id, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'system', ?, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')",
        (ws_id, tenant_id, ws_id, ws_id, status),
    )
    conn.commit()


def _insert_member(
    conn: sqlite3.Connection,
    workspace_id: str,
    operator_id: str,
    role: str = "workspace_member",
    status: str = "active",
) -> None:
    conn.execute(
        "INSERT INTO workspace_members (id, workspace_id, operator_id, role, joined_at, status) "
        "VALUES (?, ?, ?, ?, '2026-01-01T00:00:00Z', ?)",
        (str(uuid.uuid4()), workspace_id, operator_id, role, status),
    )
    conn.commit()


class _PatchedDB:
    """Context manager that monkey-patches db.query_one and db.query_all
    to use a provided in-memory SQLite connection.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._orig_one = None
        self._orig_all = None

    def _query_one(self, sql: str, params: tuple = ()) -> dict | None:
        cur = self._conn.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None

    def _query_all(self, sql: str, params: tuple = ()) -> list:
        cur = self._conn.execute(sql, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]

    def __enter__(self) -> "_PatchedDB":
        sys.path.insert(0, str(REPO_ROOT / "backend"))
        import backend.src.auth.auth as auth_mod
        self._auth_mod = auth_mod
        self._orig_one = auth_mod.query_one
        self._orig_all = auth_mod.query_all
        auth_mod.query_one = self._query_one
        auth_mod.query_all = self._query_all
        return self

    def __exit__(self, *args: object) -> None:
        self._auth_mod.query_one = self._orig_one
        self._auth_mod.query_all = self._orig_all


def _make_operator_payload(
    operator_id: str = "op-001",
    tenant_id: str = "t-001",
    role: str = "grant_admin",
) -> dict:
    return {
        "operator": {"operatorId": operator_id, "role": role, "name": "Test Op"},
        "tenant_id": tenant_id,
    }


# ── Context Resolver Tests ───────────────────────────────────────────────────────

class TestWorkspaceContextResolverLegacy(unittest.TestCase):
    """Legacy/demo mode: no operator in payload → demo workspace resolved."""

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT / "backend"))

    def test_legacy_no_operator_resolves_demo(self):
        from backend.src.auth.auth import resolve_workspace_context
        auth_payload = {"tenant_id": "demo"}  # no "operator" key
        ws_id, status, ctx = resolve_workspace_context(auth_payload)
        self.assertEqual(status, 200)
        self.assertEqual(ws_id, "default")
        self.assertEqual(ctx["workspace_id"], "default")
        self.assertEqual(ctx["tenant_id"], "demo")
        self.assertEqual(ctx["resolution_mode"], "legacy_demo")
        self.assertFalse(ctx["cross_workspace_access"])

    def test_legacy_empty_operator_resolves_demo(self):
        from backend.src.auth.auth import resolve_workspace_context
        auth_payload = {"operator": {}, "tenant_id": "demo"}
        ws_id, status, ctx = resolve_workspace_context(auth_payload)
        self.assertEqual(status, 200)
        self.assertEqual(ctx["resolution_mode"], "legacy_demo")

    def test_legacy_operator_none_resolves_demo(self):
        from backend.src.auth.auth import resolve_workspace_context
        auth_payload = {"operator": None, "tenant_id": "demo"}
        ws_id, status, ctx = resolve_workspace_context(auth_payload)
        self.assertEqual(status, 200)
        self.assertEqual(ws_id, "default")


class TestWorkspaceContextResolverSingleMembership(unittest.TestCase):
    """Single membership auto-resolution."""

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT / "backend"))
        self.conn = _fresh_conn()
        _setup_workspace_tables(self.conn)
        _insert_workspace(self.conn, "ws-alpha", "t-001")
        _insert_member(self.conn, "ws-alpha", "op-001", role="workspace_member")

    def tearDown(self):
        self.conn.close()

    def test_single_membership_auto_resolved(self):
        from backend.src.auth.auth import resolve_workspace_context
        payload = _make_operator_payload("op-001", "t-001", "grant_admin")
        with _PatchedDB(self.conn):
            ws_id, status, ctx = resolve_workspace_context(payload)
        self.assertEqual(status, 200)
        self.assertEqual(ws_id, "ws-alpha")
        self.assertEqual(ctx["workspace_id"], "ws-alpha")
        self.assertEqual(ctx["tenant_id"], "t-001")
        self.assertEqual(ctx["workspace_member_role"], "workspace_member")
        self.assertEqual(ctx["resolution_mode"], "single_membership")
        self.assertFalse(ctx["cross_workspace_access"])

    def test_single_membership_readonly_auto_resolved(self):
        from backend.src.auth.auth import resolve_workspace_context
        conn2 = _fresh_conn()
        _setup_workspace_tables(conn2)
        _insert_workspace(conn2, "ws-ro", "t-001")
        _insert_member(conn2, "ws-ro", "op-002", role="workspace_readonly")
        payload = _make_operator_payload("op-002", "t-001")
        with _PatchedDB(conn2):
            ws_id, status, ctx = resolve_workspace_context(payload)
        self.assertEqual(status, 200)
        self.assertEqual(ws_id, "ws-ro")
        self.assertEqual(ctx["workspace_member_role"], "workspace_readonly")
        conn2.close()


class TestWorkspaceContextResolverNoMembership(unittest.TestCase):
    """Fail-closed: no memberships → 403."""

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT / "backend"))
        self.conn = _fresh_conn()
        _setup_workspace_tables(self.conn)
        _insert_workspace(self.conn, "ws-other", "t-001")

    def tearDown(self):
        self.conn.close()

    def test_no_membership_fails_closed(self):
        from backend.src.auth.auth import resolve_workspace_context
        payload = _make_operator_payload("op-nobody", "t-001")
        with _PatchedDB(self.conn):
            ws_id, status, ctx = resolve_workspace_context(payload)
        self.assertIsNone(ws_id)
        self.assertEqual(status, 403)
        self.assertEqual(ctx["errorCode"], "no_workspace_membership")

    def test_revoked_membership_fails_closed(self):
        from backend.src.auth.auth import resolve_workspace_context
        conn2 = _fresh_conn()
        _setup_workspace_tables(conn2)
        _insert_workspace(conn2, "ws-rev", "t-001")
        _insert_member(conn2, "ws-rev", "op-rev", role="workspace_member", status="removed")
        payload = _make_operator_payload("op-rev", "t-001")
        with _PatchedDB(conn2):
            ws_id, status, ctx = resolve_workspace_context(payload)
        self.assertIsNone(ws_id)
        self.assertEqual(status, 403)
        conn2.close()


class TestWorkspaceContextResolverMultipleMemberships(unittest.TestCase):
    """Multiple memberships without explicit workspace_id → 400 (ambiguous)."""

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT / "backend"))
        self.conn = _fresh_conn()
        _setup_workspace_tables(self.conn)
        _insert_workspace(self.conn, "ws-a", "t-001")
        _insert_workspace(self.conn, "ws-b", "t-001")
        _insert_member(self.conn, "ws-a", "op-multi", role="workspace_member")
        _insert_member(self.conn, "ws-b", "op-multi", role="workspace_admin")

    def tearDown(self):
        self.conn.close()

    def test_multiple_memberships_no_workspace_id_fails(self):
        from backend.src.auth.auth import resolve_workspace_context
        payload = _make_operator_payload("op-multi", "t-001")
        with _PatchedDB(self.conn):
            ws_id, status, ctx = resolve_workspace_context(payload)
        self.assertIsNone(ws_id)
        self.assertEqual(status, 400)
        self.assertEqual(ctx["errorCode"], "workspace_id_required")

    def test_multiple_memberships_with_workspace_id_resolved(self):
        from backend.src.auth.auth import resolve_workspace_context
        payload = _make_operator_payload("op-multi", "t-001")
        with _PatchedDB(self.conn):
            ws_id, status, ctx = resolve_workspace_context(payload, client_workspace_id="ws-b")
        self.assertEqual(status, 200)
        self.assertEqual(ws_id, "ws-b")
        self.assertEqual(ctx["workspace_member_role"], "workspace_admin")
        self.assertEqual(ctx["resolution_mode"], "membership_verified")


class TestWorkspaceContextResolverExplicitWorkspaceId(unittest.TestCase):
    """Explicit client workspace_id handling."""

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT / "backend"))
        self.conn = _fresh_conn()
        _setup_workspace_tables(self.conn)
        _insert_workspace(self.conn, "ws-mine", "t-001")
        _insert_workspace(self.conn, "ws-other", "t-other")
        _insert_member(self.conn, "ws-mine", "op-001", role="workspace_member")

    def tearDown(self):
        self.conn.close()

    def test_explicit_workspace_id_with_membership_resolved(self):
        from backend.src.auth.auth import resolve_workspace_context
        payload = _make_operator_payload("op-001", "t-001")
        with _PatchedDB(self.conn):
            ws_id, status, ctx = resolve_workspace_context(payload, client_workspace_id="ws-mine")
        self.assertEqual(status, 200)
        self.assertEqual(ws_id, "ws-mine")
        self.assertEqual(ctx["resolution_mode"], "membership_verified")

    def test_explicit_workspace_id_no_membership_denied(self):
        from backend.src.auth.auth import resolve_workspace_context
        # op-001 has no membership in ws-other
        conn2 = _fresh_conn()
        _setup_workspace_tables(conn2)
        _insert_workspace(conn2, "ws-x", "t-001")
        _insert_workspace(conn2, "ws-noac", "t-001")
        _insert_member(conn2, "ws-x", "op-001", role="workspace_member")
        payload = _make_operator_payload("op-001", "t-001")
        with _PatchedDB(conn2):
            ws_id, status, ctx = resolve_workspace_context(payload, client_workspace_id="ws-noac")
        self.assertIsNone(ws_id)
        self.assertEqual(status, 403)
        self.assertEqual(ctx["errorCode"], "workspace_access_denied")
        conn2.close()

    def test_explicit_workspace_id_wrong_tenant_denied(self):
        from backend.src.auth.auth import resolve_workspace_context
        # ws-other belongs to t-other, but caller is t-001
        payload = _make_operator_payload("op-001", "t-001")
        with _PatchedDB(self.conn):
            ws_id, status, ctx = resolve_workspace_context(payload, client_workspace_id="ws-other")
        self.assertIsNone(ws_id)
        self.assertEqual(status, 403)
        self.assertEqual(ctx["errorCode"], "workspace_not_found")

    def test_explicit_workspace_id_nonexistent_denied(self):
        from backend.src.auth.auth import resolve_workspace_context
        payload = _make_operator_payload("op-001", "t-001")
        with _PatchedDB(self.conn):
            ws_id, status, ctx = resolve_workspace_context(payload, client_workspace_id="ws-doesnotexist")
        self.assertIsNone(ws_id)
        self.assertEqual(status, 403)
        self.assertEqual(ctx["errorCode"], "workspace_not_found")

    def test_explicit_workspace_id_empty_string_rejected(self):
        from backend.src.auth.auth import resolve_workspace_context
        payload = _make_operator_payload("op-001", "t-001")
        with _PatchedDB(self.conn):
            ws_id, status, ctx = resolve_workspace_context(payload, client_workspace_id="   ")
        self.assertIsNone(ws_id)
        self.assertEqual(status, 400)
        self.assertEqual(ctx["errorCode"], "invalid_workspace_id")

    def test_explicit_workspace_id_inactive_workspace_denied(self):
        from backend.src.auth.auth import resolve_workspace_context
        conn2 = _fresh_conn()
        _setup_workspace_tables(conn2)
        _insert_workspace(conn2, "ws-inactive", "t-001", status="suspended")
        _insert_member(conn2, "ws-inactive", "op-001", role="workspace_member")
        payload = _make_operator_payload("op-001", "t-001")
        with _PatchedDB(conn2):
            ws_id, status, ctx = resolve_workspace_context(payload, client_workspace_id="ws-inactive")
        self.assertIsNone(ws_id)
        self.assertEqual(status, 403)
        self.assertEqual(ctx["errorCode"], "workspace_inactive")
        conn2.close()

    def test_client_supplied_workspace_id_not_trusted_without_membership(self):
        """Core GL-225 guarantee: client cannot override workspace without membership."""
        from backend.src.auth.auth import resolve_workspace_context
        # op-001 has membership only in ws-mine, NOT in ws-other
        payload = _make_operator_payload("op-001", "t-001")
        with _PatchedDB(self.conn):
            # Attempt: supply ws-other (no membership) — must be denied
            ws_id, status, ctx = resolve_workspace_context(payload, client_workspace_id="ws-other")
        self.assertIsNone(ws_id)
        self.assertNotEqual(status, 200, "Client-supplied workspace_id must NOT be trusted without membership")


class TestWorkspaceContextResolverCrossWorkspaceRole(unittest.TestCase):
    """Cross-workspace roles (owner/grant_admin_global) bypass documented explicitly."""

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT / "backend"))
        self.conn = _fresh_conn()
        _setup_workspace_tables(self.conn)
        _insert_workspace(self.conn, "ws-a", "t-001")
        _insert_workspace(self.conn, "ws-b", "t-001")
        # owner has no explicit membership in ws-b

    def tearDown(self):
        self.conn.close()

    def test_owner_can_access_any_workspace_with_id(self):
        from backend.src.auth.auth import resolve_workspace_context
        payload = _make_operator_payload("op-owner", "t-001", role="owner")
        with _PatchedDB(self.conn):
            ws_id, status, ctx = resolve_workspace_context(payload, client_workspace_id="ws-b")
        self.assertEqual(status, 200)
        self.assertEqual(ws_id, "ws-b")
        self.assertTrue(ctx["cross_workspace_access"],
                        "Cross-workspace access flag must be set for owner role")
        self.assertEqual(ctx["resolution_mode"], "cross_workspace_role")

    def test_owner_without_workspace_id_in_demo_tenant(self):
        from backend.src.auth.auth import resolve_workspace_context
        conn2 = _fresh_conn()
        _setup_workspace_tables(conn2)
        _insert_workspace(conn2, "default", "demo")
        payload = {"operator": {"operatorId": "op-admin", "role": "owner", "name": "Admin"},
                   "tenant_id": "demo"}
        with _PatchedDB(conn2):
            ws_id, status, ctx = resolve_workspace_context(payload)
        self.assertEqual(status, 200)
        self.assertEqual(ws_id, "default")
        self.assertEqual(ctx["workspace_id"], "default")
        self.assertEqual(ctx["resolution_mode"], "cross_workspace_role_demo_fallback")
        conn2.close()

    def test_owner_without_workspace_id_non_demo_tenant_requires_explicit(self):
        from backend.src.auth.auth import resolve_workspace_context
        payload = _make_operator_payload("op-owner", "t-001", role="owner")
        with _PatchedDB(self.conn):
            ws_id, status, ctx = resolve_workspace_context(payload)
        self.assertIsNone(ws_id)
        self.assertEqual(status, 400)
        self.assertEqual(ctx["errorCode"], "workspace_id_required")

    def test_owner_cross_workspace_access_flag_documented(self):
        """Verify cross_workspace_access is True (not silent bypass)."""
        from backend.src.auth.auth import resolve_workspace_context
        payload = _make_operator_payload("op-owner", "t-001", role="owner")
        with _PatchedDB(self.conn):
            ws_id, status, ctx = resolve_workspace_context(payload, client_workspace_id="ws-a")
        self.assertEqual(status, 200)
        self.assertIn("cross_workspace_access", ctx)
        self.assertTrue(ctx["cross_workspace_access"],
                        "Admin cross-workspace bypass must be explicit in context, not silent")


# ── Cross-workspace authorization enforcement tests ──────────────────────────────

class TestCheckWorkspaceResourceAccessSameWorkspace(unittest.TestCase):
    """Same-workspace access: always allowed (subject to role checks)."""

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT / "backend"))

    def test_same_workspace_lookup_allowed(self):
        from backend.src.auth.auth import check_workspace_resource_access
        ok, status, _ = check_workspace_resource_access(
            resource_workspace_id="ws-a",
            caller_workspace_id="ws-a",
            caller_tenant_id="t-001",
            resource_tenant_id="t-001",
        )
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_same_workspace_mutation_allowed(self):
        from backend.src.auth.auth import check_workspace_resource_access
        ok, status, _ = check_workspace_resource_access(
            resource_workspace_id="ws-a",
            caller_workspace_id="ws-a",
            caller_tenant_id="t-001",
            resource_tenant_id="t-001",
            require_mutation=True,
            workspace_member_role="workspace_member",
        )
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_same_workspace_readonly_lookup_allowed(self):
        from backend.src.auth.auth import check_workspace_resource_access
        ok, status, _ = check_workspace_resource_access(
            resource_workspace_id="ws-a",
            caller_workspace_id="ws-a",
            caller_tenant_id="t-001",
            resource_tenant_id="t-001",
            workspace_member_role="workspace_readonly",
        )
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_same_workspace_readonly_mutation_denied(self):
        from backend.src.auth.auth import check_workspace_resource_access
        ok, status, ctx = check_workspace_resource_access(
            resource_workspace_id="ws-a",
            caller_workspace_id="ws-a",
            caller_tenant_id="t-001",
            resource_tenant_id="t-001",
            require_mutation=True,
            workspace_member_role="workspace_readonly",
        )
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self.assertEqual(ctx["errorCode"], "workspace_role_insufficient")

    def test_unscoped_resource_always_allowed(self):
        from backend.src.auth.auth import check_workspace_resource_access
        ok, status, _ = check_workspace_resource_access(
            resource_workspace_id=None,
            caller_workspace_id="ws-a",
            caller_tenant_id="t-001",
            resource_tenant_id=None,
        )
        self.assertTrue(ok)
        self.assertEqual(status, 200)


class TestCrossWorkspaceLookupDenial(unittest.TestCase):
    """GL-226: Cross-workspace lookup → 403 (without bypass)."""

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT / "backend"))

    def test_cross_workspace_lookup_denied(self):
        from backend.src.auth.auth import check_workspace_resource_access
        ok, status, ctx = check_workspace_resource_access(
            resource_workspace_id="ws-other",
            caller_workspace_id="ws-mine",
            caller_tenant_id="t-001",
            resource_tenant_id="t-001",
            cross_workspace_access=False,
        )
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self.assertEqual(ctx["errorCode"], "cross_workspace_lookup_denied")

    def test_cross_workspace_lookup_denied_without_bypass_flag(self):
        from backend.src.auth.auth import check_workspace_resource_access
        # Default cross_workspace_access=False
        ok, status, ctx = check_workspace_resource_access(
            resource_workspace_id="ws-x",
            caller_workspace_id="ws-y",
            caller_tenant_id="t-001",
            resource_tenant_id="t-001",
        )
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self.assertIn("cross_workspace_lookup_denied", ctx["errorCode"])


class TestCrossWorkspaceMutationDenial(unittest.TestCase):
    """GL-226: Cross-workspace mutation → 403 (without bypass)."""

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT / "backend"))

    def test_cross_workspace_mutation_denied(self):
        from backend.src.auth.auth import check_workspace_resource_access
        ok, status, ctx = check_workspace_resource_access(
            resource_workspace_id="ws-other",
            caller_workspace_id="ws-mine",
            caller_tenant_id="t-001",
            resource_tenant_id="t-001",
            cross_workspace_access=False,
            require_mutation=True,
        )
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self.assertEqual(ctx["errorCode"], "cross_workspace_mutation_denied")

    def test_cross_workspace_mutation_denied_code_distinct_from_lookup(self):
        """Mutation denial has a distinct error code from lookup denial."""
        from backend.src.auth.auth import check_workspace_resource_access
        _, _, ctx_lookup = check_workspace_resource_access(
            resource_workspace_id="ws-other",
            caller_workspace_id="ws-mine",
            caller_tenant_id="t-001",
            resource_tenant_id="t-001",
            cross_workspace_access=False,
            require_mutation=False,
        )
        _, _, ctx_mutation = check_workspace_resource_access(
            resource_workspace_id="ws-other",
            caller_workspace_id="ws-mine",
            caller_tenant_id="t-001",
            resource_tenant_id="t-001",
            cross_workspace_access=False,
            require_mutation=True,
        )
        self.assertNotEqual(ctx_lookup["errorCode"], ctx_mutation["errorCode"])
        self.assertEqual(ctx_lookup["errorCode"], "cross_workspace_lookup_denied")
        self.assertEqual(ctx_mutation["errorCode"], "cross_workspace_mutation_denied")


class TestCrossTenantDenial(unittest.TestCase):
    """GL-226: Cross-tenant access is always 403 — no bypass."""

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT / "backend"))

    def test_cross_tenant_lookup_denied(self):
        from backend.src.auth.auth import check_workspace_resource_access
        ok, status, ctx = check_workspace_resource_access(
            resource_workspace_id="ws-theirs",
            caller_workspace_id="ws-ours",
            caller_tenant_id="t-001",
            resource_tenant_id="t-other",
            cross_workspace_access=False,
        )
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self.assertEqual(ctx["errorCode"], "cross_tenant_access_denied")

    def test_cross_tenant_mutation_denied(self):
        from backend.src.auth.auth import check_workspace_resource_access
        ok, status, ctx = check_workspace_resource_access(
            resource_workspace_id="ws-theirs",
            caller_workspace_id="ws-ours",
            caller_tenant_id="t-001",
            resource_tenant_id="t-other",
            cross_workspace_access=False,
            require_mutation=True,
        )
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self.assertEqual(ctx["errorCode"], "cross_tenant_access_denied")

    def test_cross_tenant_denied_even_with_cross_workspace_role(self):
        """Admin/cross-workspace role does NOT bypass cross-tenant boundary."""
        from backend.src.auth.auth import check_workspace_resource_access
        ok, status, ctx = check_workspace_resource_access(
            resource_workspace_id="ws-theirs",
            caller_workspace_id="ws-ours",
            caller_tenant_id="t-001",
            resource_tenant_id="t-other",
            cross_workspace_access=True,  # cross-workspace admin role
        )
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self.assertEqual(ctx["errorCode"], "cross_tenant_access_denied")


class TestAdminBypassDocumented(unittest.TestCase):
    """GL-226: Admin (cross_workspace_access=True) bypass is explicit and documented."""

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT / "backend"))

    def test_admin_cross_workspace_lookup_allowed(self):
        from backend.src.auth.auth import check_workspace_resource_access
        ok, status, _ = check_workspace_resource_access(
            resource_workspace_id="ws-any",
            caller_workspace_id="ws-admin",
            caller_tenant_id="t-001",
            resource_tenant_id="t-001",
            cross_workspace_access=True,
        )
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_admin_cross_workspace_mutation_allowed(self):
        from backend.src.auth.auth import check_workspace_resource_access
        ok, status, _ = check_workspace_resource_access(
            resource_workspace_id="ws-any",
            caller_workspace_id="ws-admin",
            caller_tenant_id="t-001",
            resource_tenant_id="t-001",
            cross_workspace_access=True,
            require_mutation=True,
            workspace_member_role="workspace_admin",
        )
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_admin_cross_workspace_readonly_mutation_denied(self):
        """Cross-workspace admin with readonly role: mutation still denied."""
        from backend.src.auth.auth import check_workspace_resource_access
        ok, status, ctx = check_workspace_resource_access(
            resource_workspace_id="ws-any",
            caller_workspace_id="ws-admin",
            caller_tenant_id="t-001",
            resource_tenant_id="t-001",
            cross_workspace_access=True,
            require_mutation=True,
            workspace_member_role="workspace_readonly",
        )
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self.assertEqual(ctx["errorCode"], "workspace_role_insufficient")


# ── Role/scope tests ─────────────────────────────────────────────────────────────

class TestWorkspaceRoleChecks(unittest.TestCase):
    """Role/scope checks at the workspace level."""

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT / "backend"))

    def test_workspace_owner_can_mutate(self):
        from backend.src.auth.auth import check_workspace_resource_access
        ok, status, _ = check_workspace_resource_access(
            resource_workspace_id="ws-a",
            caller_workspace_id="ws-a",
            caller_tenant_id="t-001",
            resource_tenant_id="t-001",
            require_mutation=True,
            workspace_member_role="workspace_owner",
        )
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_workspace_admin_can_mutate(self):
        from backend.src.auth.auth import check_workspace_resource_access
        ok, status, _ = check_workspace_resource_access(
            resource_workspace_id="ws-a",
            caller_workspace_id="ws-a",
            caller_tenant_id="t-001",
            resource_tenant_id="t-001",
            require_mutation=True,
            workspace_member_role="workspace_admin",
        )
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_workspace_member_can_mutate(self):
        from backend.src.auth.auth import check_workspace_resource_access
        ok, status, _ = check_workspace_resource_access(
            resource_workspace_id="ws-a",
            caller_workspace_id="ws-a",
            caller_tenant_id="t-001",
            resource_tenant_id="t-001",
            require_mutation=True,
            workspace_member_role="workspace_member",
        )
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_workspace_readonly_cannot_mutate(self):
        from backend.src.auth.auth import check_workspace_resource_access
        ok, status, ctx = check_workspace_resource_access(
            resource_workspace_id="ws-a",
            caller_workspace_id="ws-a",
            caller_tenant_id="t-001",
            resource_tenant_id="t-001",
            require_mutation=True,
            workspace_member_role="workspace_readonly",
        )
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self.assertEqual(ctx["errorCode"], "workspace_role_insufficient")

    def test_context_resolver_returns_member_role(self):
        from backend.src.auth.auth import resolve_workspace_context
        conn = _fresh_conn()
        _setup_workspace_tables(conn)
        _insert_workspace(conn, "ws-role-test", "t-001")
        _insert_member(conn, "ws-role-test", "op-role", role="workspace_admin")
        payload = _make_operator_payload("op-role", "t-001")
        with _PatchedDB(conn):
            ws_id, status, ctx = resolve_workspace_context(payload)
        self.assertEqual(status, 200)
        self.assertEqual(ctx["workspace_member_role"], "workspace_admin")
        conn.close()


# ── Demo/synthetic compatibility ─────────────────────────────────────────────────

class TestDemoSyntheticCompatibility(unittest.TestCase):
    """GL-225/226 must not break demo/synthetic mode."""

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT / "backend"))

    def test_demo_mode_no_operator_payload(self):
        from backend.src.auth.auth import resolve_workspace_context
        ws_id, status, ctx = resolve_workspace_context({})
        self.assertEqual(status, 200)
        self.assertEqual(ws_id, "default")

    def test_demo_mode_tenant_id_missing(self):
        from backend.src.auth.auth import resolve_workspace_context
        ws_id, status, ctx = resolve_workspace_context({"tenant_id": None})
        self.assertEqual(status, 200)
        self.assertEqual(ws_id, "default")

    def test_check_access_no_resource_workspace_id(self):
        from backend.src.auth.auth import check_workspace_resource_access
        # Unscoped resource (pre-GL-224 backfill rows) must always pass.
        ok, status, _ = check_workspace_resource_access(
            resource_workspace_id=None,
            caller_workspace_id="default",
            caller_tenant_id="demo",
            resource_tenant_id=None,
        )
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_same_tenant_no_resource_tenant_id(self):
        from backend.src.auth.auth import check_workspace_resource_access
        # resource_tenant_id=None → no tenant check, same workspace
        ok, status, _ = check_workspace_resource_access(
            resource_workspace_id="default",
            caller_workspace_id="default",
            caller_tenant_id="demo",
            resource_tenant_id=None,
        )
        self.assertTrue(ok)
        self.assertEqual(status, 200)


# ── Module importability ─────────────────────────────────────────────────────────

class TestAuthModuleImportable(unittest.TestCase):
    """auth.py exports the new GL-225/226 functions."""

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT / "backend"))

    def test_resolve_workspace_context_importable(self):
        from backend.src.auth.auth import resolve_workspace_context
        self.assertTrue(callable(resolve_workspace_context))

    def test_check_workspace_resource_access_importable(self):
        from backend.src.auth.auth import check_workspace_resource_access
        self.assertTrue(callable(check_workspace_resource_access))

    def test_existing_check_auth_still_works(self):
        from backend.src.auth.auth import check_auth
        self.assertTrue(callable(check_auth))

    def test_existing_check_admin_token_still_works(self):
        from backend.src.auth.auth import check_admin_token
        self.assertTrue(callable(check_admin_token))


# ── Documentation and artifact tests ──────────────────────────────────────────────

class TestGL225226Docs(unittest.TestCase):
    """Docs and JSON artifact exist with required keys."""

    def test_markdown_doc_exists(self):
        self.assertTrue(
            MD_PATH.exists(),
            f"Missing documentation: {MD_PATH}",
        )

    def test_json_artifact_exists(self):
        self.assertTrue(
            JSON_PATH.exists(),
            f"Missing JSON artifact: {JSON_PATH}",
        )

    def test_json_artifact_parseable(self):
        with open(JSON_PATH) as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)

    def test_json_artifact_required_keys(self):
        with open(JSON_PATH) as f:
            data = json.load(f)
        required = [
            "issue_id",
            "title",
            "result",
            "workspace_context_resolver",
            "authorization_enforcement",
            "safety_confirmations",
        ]
        for key in required:
            self.assertIn(key, data, f"JSON artifact missing required key: {key}")

    def test_json_safety_confirmations(self):
        with open(JSON_PATH) as f:
            data = json.load(f)
        sc = data.get("safety_confirmations", {})
        required_flags = [
            "production_saas_no_go",
            "no_real_customer_data",
            "no_real_secrets",
            "no_network_calls",
            "no_destructive_ops",
            "local_only",
        ]
        for flag in required_flags:
            self.assertIn(flag, sc, f"safety_confirmations missing: {flag}")
            self.assertTrue(sc[flag], f"safety_confirmations.{flag} must be true")

    def test_json_issue_id(self):
        with open(JSON_PATH) as f:
            data = json.load(f)
        self.assertIn("GL-225", data["issue_id"])

    def test_no_production_saas_claim(self):
        with open(JSON_PATH) as f:
            content = f.read()
        self.assertNotIn("production_saas_ready: true", content.lower())
        self.assertNotIn('"production_saas_ready": true', content.lower())

    def test_no_real_customer_data_in_json(self):
        with open(JSON_PATH) as f:
            content = f.read()
        # Check for PII / private key markers
        self.assertNotIn("-----BEGIN", content)
        self.assertNotIn("AKIA", content)


# ── Gate script tests ────────────────────────────────────────────────────────────

class TestGL225226GateScript(unittest.TestCase):
    """Gate script (optional) compiles and supports --dry-run / --plan."""

    def test_gate_script_compiles(self):
        if not GATE_SCRIPT.exists():
            self.skipTest("Gate script not present (optional)")
        import py_compile
        try:
            py_compile.compile(str(GATE_SCRIPT), doraise=True)
        except py_compile.PyCompileError as e:
            self.fail(f"Gate script has syntax error: {e}")

    def test_gate_script_dry_run(self):
        if not GATE_SCRIPT.exists():
            self.skipTest("Gate script not present (optional)")
        import subprocess
        result = subprocess.run(
            [sys.executable, str(GATE_SCRIPT), "--dry-run"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, f"--dry-run failed:\n{result.stdout}\n{result.stderr}")

    def test_gate_script_plan(self):
        if not GATE_SCRIPT.exists():
            self.skipTest("Gate script not present (optional)")
        import subprocess
        result = subprocess.run(
            [sys.executable, str(GATE_SCRIPT), "--plan"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, f"--plan failed:\n{result.stdout}\n{result.stderr}")


# ── Safety confirmations ─────────────────────────────────────────────────────────

class TestSafetyConfirmations(unittest.TestCase):
    """Static safety checks: no forbidden patterns in new/changed files."""

    def test_no_production_saas_claim_in_auth_py(self):
        auth_path = SRC_DIR / "auth" / "auth.py"
        content = auth_path.read_text()
        self.assertNotIn("production_saas_ready = True", content)
        self.assertNotIn("real_customer_private_data_ready = True", content)

    def test_no_private_key_material_in_auth_py(self):
        auth_path = SRC_DIR / "auth" / "auth.py"
        content = auth_path.read_text()
        self.assertNotIn("-----BEGIN", content)

    def test_no_network_calls_in_auth_py(self):
        auth_path = SRC_DIR / "auth" / "auth.py"
        content = auth_path.read_text()
        # No stdlib http/urllib/socket calls should be added (only db helpers)
        self.assertNotIn("urllib.request", content)
        self.assertNotIn("http.client.HTTPConnection", content)
        self.assertNotIn("socket.connect(", content)

    def test_no_migration_files_modified(self):
        """No new migration files should be created for this GL."""
        migrations_dir = SRC_DIR / "migrations"
        # GL-225 should NOT have a migration file
        for f in migrations_dir.iterdir():
            self.assertNotIn("gl225", f.name.lower(), f"Unexpected migration file for GL-225: {f.name}")
            self.assertNotIn("gl226", f.name.lower(), f"Unexpected migration file for GL-226: {f.name}")

    def test_fail_closed_no_workspace_is_rejection(self):
        """resolve_workspace_context never returns workspace_id for operators without access."""
        from backend.src.auth.auth import resolve_workspace_context
        # Operator with no payload operator id → demo fallback (legacy/demo)
        # is acceptable. But operator with explicit id and no workspace → 403 or 400.
        sys.path.insert(0, str(REPO_ROOT / "backend"))
        conn = _fresh_conn()
        _setup_workspace_tables(conn)
        # No workspaces, no memberships for op-orphan
        payload = _make_operator_payload("op-orphan", "t-real")
        with _PatchedDB(conn):
            ws_id, status, ctx = resolve_workspace_context(payload)
        self.assertIsNone(ws_id, "Operator with no memberships must not receive a workspace_id")
        self.assertNotEqual(status, 200, "Fail-closed: no workspace → must not return 200")
        conn.close()


if __name__ == "__main__":
    unittest.main()
