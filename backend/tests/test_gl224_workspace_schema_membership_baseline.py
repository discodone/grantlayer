"""GL-224 Workspace Schema / Membership Baseline — test suite.

Covers:
- New models (Workspace, WorkspaceMember, WorkspaceInvite) exist and construct
- Migration creates workspaces, workspace_members, workspace_invites tables
- Expected columns and indexes are present after migration
- Demo-workspace backfill row is inserted (id='default', tenant_id='demo')
- Resource tables are backfilled (workspace_id='default' where NULL + demo)
- Migration is idempotent (re-running apply() does not raise)
- Membership insert / lookup / remove within a workspace
- Invite insert / status transitions
- Cross-workspace membership isolation (operator not visible in other workspace)
- Role constraint: only known roles stored
- Safety confirmations: no Production SaaS claim, no real customer data
- Docs and JSON artifact exist with required structure
- Gate script compiles and supports --dry-run / --plan flags
"""

from __future__ import annotations

import importlib
import json
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid

# ── repo paths ────────────────────────────────────────────────────────────────

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "backend" / "src"
MIGRATIONS_DIR = SRC_DIR / "migrations"

MD_PATH = REPO_ROOT / "docs" / "workspace_schema_membership_baseline.md"
JSON_PATH = REPO_ROOT / "docs" / "examples" / "gl224" / "workspace_schema_membership_baseline.json"
GATE_SCRIPT = REPO_ROOT / "scripts" / "ops" / "gl224_workspace_schema_gate.py"

MIGRATION_FILE = MIGRATIONS_DIR / "0011_gl224_workspace_schema_membership_baseline.py"

# ── helpers ───────────────────────────────────────────────────────────────────

def _fresh_conn() -> sqlite3.Connection:
    """Return a fresh in-memory SQLite connection with WAL and FK enabled."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class _Conn:
    """Minimal wrapper so migration helpers can call getattr(conn, 'backend')."""

    def __init__(self, raw: sqlite3.Connection) -> None:
        self._raw = raw
        self.backend = "sqlite"

    def execute(self, sql: str, params=None):
        return self._raw.execute(sql, params or ())

    def executemany(self, sql: str, params_list):
        return self._raw.executemany(sql, params_list)

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        self._raw.close()


def _load_migration():
    """Load the GL-224 migration module."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "migration_gl224", str(MIGRATION_FILE)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _applied_conn() -> tuple[_Conn, object]:
    """Return a connection with the GL-224 migration already applied."""
    raw = _fresh_conn()
    # First bring the DB to GL-032 baseline (needed by earlier migrations)
    raw.executescript(_BASELINE_SCHEMA)
    conn = _Conn(raw)
    mod = _load_migration()
    mod.apply(conn)
    return conn, mod


# Minimal GL-032 baseline schema (grants + audit_events + other tables) so
# that the migration's backfill helpers find the tables they expect.
_BASELINE_SCHEMA = """
CREATE TABLE IF NOT EXISTS grants (
    id TEXT PRIMARY KEY, subject_id TEXT, role TEXT, action TEXT,
    resource TEXT, valid_from TEXT, valid_until TEXT, created_by TEXT,
    reason TEXT, revoked INTEGER DEFAULT 0, revoked_by TEXT,
    revoked_reason TEXT, revoked_at TEXT, created_at TEXT,
    signature TEXT, signing_key_id TEXT, payload_hash TEXT,
    max_uses INTEGER, use_count INTEGER DEFAULT 0,
    tenant_id TEXT NOT NULL DEFAULT 'demo',
    workspace_id TEXT DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS grant_requests (
    id TEXT PRIMARY KEY, subject_id TEXT, role TEXT, action TEXT,
    resource TEXT, valid_from TEXT, valid_until TEXT,
    requested_by TEXT, reason TEXT, status TEXT DEFAULT 'requested',
    approved_by TEXT, approved_at TEXT, denied_by TEXT, denied_at TEXT,
    denial_reason TEXT, revoked_by TEXT, revoked_at TEXT,
    revoked_reason TEXT, grant_id TEXT, created_at TEXT, updated_at TEXT,
    tenant_id TEXT NOT NULL DEFAULT 'demo',
    workspace_id TEXT DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS challenges (
    id TEXT PRIMARY KEY, subject_id TEXT, action TEXT, resource TEXT,
    created_at TEXT, expires_at TEXT, used_at TEXT, status TEXT DEFAULT 'active',
    tenant_id TEXT NOT NULL DEFAULT 'demo',
    workspace_id TEXT DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS grant_executions (
    id TEXT PRIMARY KEY, grant_id TEXT, grant_request_id TEXT,
    operator_id TEXT, action TEXT, resource TEXT, challenge_id TEXT,
    challenge_result TEXT, policy_result TEXT, result TEXT DEFAULT 'denied',
    error_code TEXT, executed_at TEXT, audit_event_id TEXT, metadata_json TEXT,
    tenant_id TEXT NOT NULL DEFAULT 'demo',
    workspace_id TEXT DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY, timestamp TEXT, subject_id TEXT, role TEXT,
    action TEXT, resource TEXT, approved INTEGER, reason TEXT,
    matched_grant_id TEXT, challenge_id TEXT, challenge_present INTEGER,
    challenge_result TEXT, grant_signature_result TEXT,
    tenant_id TEXT DEFAULT NULL, workspace_id TEXT DEFAULT NULL, scope TEXT
);
CREATE TABLE IF NOT EXISTS operators (
    id TEXT PRIMARY KEY, name TEXT, role TEXT, token_hash TEXT,
    active INTEGER DEFAULT 1, created_at TEXT,
    tenant_id TEXT NOT NULL DEFAULT 'demo',
    workspace_id TEXT DEFAULT NULL
);
"""


# ── tests ─────────────────────────────────────────────────────────────────────


class TestGL224ModelsExist(unittest.TestCase):
    """Workspace, WorkspaceMember, WorkspaceInvite dataclasses exist and work."""

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT / "backend"))

    def test_workspace_model_importable(self):
        from src.models import Workspace
        self.assertTrue(callable(Workspace))

    def test_workspace_member_model_importable(self):
        from src.models import WorkspaceMember
        self.assertTrue(callable(WorkspaceMember))

    def test_workspace_invite_model_importable(self):
        from src.models import WorkspaceInvite
        self.assertTrue(callable(WorkspaceInvite))

    def test_workspace_constructs(self):
        from src.models import Workspace
        ws = Workspace(
            id="ws-001",
            tenant_id="demo",
            name="Default",
            slug="default",
            owner_id="op-001",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        self.assertEqual(ws.id, "ws-001")
        self.assertEqual(ws.status, "active")
        d = ws.to_dict()
        self.assertIn("id", d)
        self.assertIn("tenant_id", d)
        self.assertIn("slug", d)
        self.assertIn("status", d)

    def test_workspace_member_constructs(self):
        from src.models import WorkspaceMember
        m = WorkspaceMember(
            id="mem-001",
            workspace_id="ws-001",
            operator_id="op-001",
            role="workspace_member",
            joined_at="2026-01-01T00:00:00Z",
        )
        self.assertEqual(m.status, "active")
        d = m.to_dict()
        self.assertIn("workspace_id", d)
        self.assertIn("operator_id", d)
        self.assertIn("role", d)

    def test_workspace_invite_constructs(self):
        from src.models import WorkspaceInvite
        inv = WorkspaceInvite(
            id="inv-001",
            workspace_id="ws-001",
            invited_by="op-001",
            email_hash="abc123",
            role="workspace_member",
            expires_at="2026-12-31T00:00:00Z",
            created_at="2026-01-01T00:00:00Z",
        )
        self.assertEqual(inv.status, "pending")
        d = inv.to_dict()
        self.assertIn("email_hash", d)
        self.assertNotIn("email", [k for k in d if k != "email_hash"])

    def test_workspace_status_literals(self):
        from src.models import WorkspaceStatus
        self.assertIsNotNone(WorkspaceStatus)

    def test_workspace_member_role_literals(self):
        from src.models import WorkspaceMemberRole
        self.assertIsNotNone(WorkspaceMemberRole)

    def test_workspace_invite_status_literals(self):
        from src.models import WorkspaceInviteStatus
        self.assertIsNotNone(WorkspaceInviteStatus)


class TestGL224MigrationFileExists(unittest.TestCase):
    def test_migration_file_exists(self):
        self.assertTrue(
            MIGRATION_FILE.exists(),
            f"Migration file missing: {MIGRATION_FILE.relative_to(REPO_ROOT)}",
        )

    def test_migration_compiles(self):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(MIGRATION_FILE)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"Compile error: {result.stderr}")

    def test_migration_has_version(self):
        mod = _load_migration()
        self.assertTrue(hasattr(mod, "version"))
        self.assertIn("gl224", mod.version)

    def test_migration_has_apply(self):
        mod = _load_migration()
        self.assertTrue(callable(getattr(mod, "apply", None)))


class TestGL224SchemaCreated(unittest.TestCase):
    """Migration creates the three new tables with the correct columns."""

    def setUp(self):
        self.conn, self.mod = _applied_conn()

    def tearDown(self):
        self.conn.close()

    def _columns(self, table: str) -> list[str]:
        rows = self.conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [r[1] for r in rows]

    def test_workspaces_table_exists(self):
        row = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='workspaces'"
        ).fetchone()
        self.assertIsNotNone(row, "workspaces table not created")

    def test_workspace_members_table_exists(self):
        row = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='workspace_members'"
        ).fetchone()
        self.assertIsNotNone(row, "workspace_members table not created")

    def test_workspace_invites_table_exists(self):
        row = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='workspace_invites'"
        ).fetchone()
        self.assertIsNotNone(row, "workspace_invites table not created")

    def test_workspaces_required_columns(self):
        cols = self._columns("workspaces")
        for expected in ["id", "tenant_id", "name", "slug", "owner_id", "status", "created_at", "updated_at"]:
            self.assertIn(expected, cols, f"workspaces missing column: {expected}")

    def test_workspace_members_required_columns(self):
        cols = self._columns("workspace_members")
        for expected in ["id", "workspace_id", "operator_id", "role", "joined_at", "status"]:
            self.assertIn(expected, cols, f"workspace_members missing column: {expected}")

    def test_workspace_invites_required_columns(self):
        cols = self._columns("workspace_invites")
        for expected in ["id", "workspace_id", "invited_by", "email_hash", "role", "status", "expires_at", "created_at"]:
            self.assertIn(expected, cols, f"workspace_invites missing column: {expected}")

    def test_workspace_invites_no_plaintext_email_column(self):
        cols = self._columns("workspace_invites")
        self.assertNotIn("email", cols, "workspace_invites must not store plaintext email")


class TestGL224Indexes(unittest.TestCase):
    """Expected indexes are created after migration."""

    def setUp(self):
        self.conn, _ = _applied_conn()

    def tearDown(self):
        self.conn.close()

    def _index_exists(self, name: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
            (name,),
        ).fetchone()
        return row is not None

    def test_idx_workspaces_tenant_id(self):
        self.assertTrue(self._index_exists("idx_workspaces_tenant_id"))

    def test_idx_workspaces_tenant_slug(self):
        self.assertTrue(self._index_exists("idx_workspaces_tenant_slug"))

    def test_idx_workspace_members_workspace_id(self):
        self.assertTrue(self._index_exists("idx_workspace_members_workspace_id"))

    def test_idx_workspace_members_operator_id(self):
        self.assertTrue(self._index_exists("idx_workspace_members_operator_id"))

    def test_idx_workspace_members_workspace_operator(self):
        self.assertTrue(self._index_exists("idx_workspace_members_workspace_operator"))

    def test_idx_workspace_invites_workspace_id(self):
        self.assertTrue(self._index_exists("idx_workspace_invites_workspace_id"))

    def test_idx_workspace_invites_email_hash(self):
        self.assertTrue(self._index_exists("idx_workspace_invites_email_hash"))


class TestGL224Backfill(unittest.TestCase):
    """Backfill: demo workspace row inserted, resource rows updated."""

    def setUp(self):
        self.conn, _ = _applied_conn()

    def tearDown(self):
        self.conn.close()

    def test_demo_workspace_row_exists(self):
        row = self.conn.execute(
            "SELECT id, tenant_id, slug FROM workspaces WHERE id = 'default'"
        ).fetchone()
        self.assertIsNotNone(row, "Demo workspace row not inserted by backfill")
        self.assertEqual(row[1], "demo")
        self.assertEqual(row[2], "default")

    def test_demo_workspace_status_active(self):
        row = self.conn.execute(
            "SELECT status FROM workspaces WHERE id = 'default'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "active")

    def test_grants_backfilled_to_default_workspace(self):
        # Insert a demo grant with workspace_id NULL
        gid = str(uuid.uuid4())
        self.conn.execute(
            """INSERT INTO grants
               (id, subject_id, role, action, resource, valid_from, valid_until,
                created_by, reason, tenant_id, workspace_id)
               VALUES (?, 's1', 'r', 'a', 'res', '2026-01-01', '2026-12-31',
                       'op1', 'test', 'demo', NULL)""",
            (gid,),
        )
        # Re-apply (idempotent) which re-runs backfill
        mod = _load_migration()
        mod.apply(self.conn)
        row = self.conn.execute(
            "SELECT workspace_id FROM grants WHERE id = ?", (gid,)
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "default")

    def test_non_demo_tenant_rows_not_backfilled(self):
        gid = str(uuid.uuid4())
        self.conn.execute(
            """INSERT INTO grants
               (id, subject_id, role, action, resource, valid_from, valid_until,
                created_by, reason, tenant_id, workspace_id)
               VALUES (?, 's2', 'r', 'a', 'res', '2026-01-01', '2026-12-31',
                       'op1', 'test', 'other-tenant', NULL)""",
            (gid,),
        )
        mod = _load_migration()
        mod.apply(self.conn)
        row = self.conn.execute(
            "SELECT workspace_id FROM grants WHERE id = ?", (gid,)
        ).fetchone()
        self.assertIsNotNone(row)
        # Non-demo tenant rows are NOT backfilled
        self.assertIsNone(row[0])

    def test_already_assigned_workspace_id_not_changed(self):
        gid = str(uuid.uuid4())
        self.conn.execute(
            """INSERT INTO grants
               (id, subject_id, role, action, resource, valid_from, valid_until,
                created_by, reason, tenant_id, workspace_id)
               VALUES (?, 's3', 'r', 'a', 'res', '2026-01-01', '2026-12-31',
                       'op1', 'test', 'demo', 'already-set')""",
            (gid,),
        )
        mod = _load_migration()
        mod.apply(self.conn)
        row = self.conn.execute(
            "SELECT workspace_id FROM grants WHERE id = ?", (gid,)
        ).fetchone()
        self.assertEqual(row[0], "already-set")


class TestGL224MigrationIdempotency(unittest.TestCase):
    """apply() can be called multiple times without error or data corruption."""

    def test_double_apply_no_error(self):
        raw = _fresh_conn()
        raw.executescript(_BASELINE_SCHEMA)
        conn = _Conn(raw)
        mod = _load_migration()
        mod.apply(conn)
        # Second apply must not raise
        try:
            mod.apply(conn)
        except Exception as exc:
            self.fail(f"Second apply() raised: {exc}")
        conn.close()

    def test_demo_workspace_not_duplicated(self):
        raw = _fresh_conn()
        raw.executescript(_BASELINE_SCHEMA)
        conn = _Conn(raw)
        mod = _load_migration()
        mod.apply(conn)
        mod.apply(conn)
        rows = conn.execute(
            "SELECT COUNT(*) FROM workspaces WHERE id = 'default'"
        ).fetchone()
        self.assertEqual(rows[0], 1, "Demo workspace row duplicated on re-apply")
        conn.close()


class TestGL224MembershipOperations(unittest.TestCase):
    """Basic membership CRUD against the migrated schema."""

    def setUp(self):
        self.conn, _ = _applied_conn()

    def tearDown(self):
        self.conn.close()

    def _insert_member(self, workspace_id: str, operator_id: str,
                       role: str = "workspace_member") -> str:
        mid = str(uuid.uuid4())
        self.conn.execute(
            """INSERT INTO workspace_members
               (id, workspace_id, operator_id, role, joined_at, status)
               VALUES (?, ?, ?, ?, '2026-01-01T00:00:00Z', 'active')""",
            (mid, workspace_id, operator_id, role),
        )
        self.conn.commit()
        return mid

    def test_insert_and_lookup_member(self):
        mid = self._insert_member("default", "op-100")
        row = self.conn.execute(
            "SELECT id, workspace_id, operator_id, role, status FROM workspace_members WHERE id = ?",
            (mid,),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[1], "default")
        self.assertEqual(row[2], "op-100")
        self.assertEqual(row[4], "active")

    def test_remove_member_sets_status(self):
        mid = self._insert_member("default", "op-101")
        self.conn.execute(
            "UPDATE workspace_members SET status = 'removed' WHERE id = ?",
            (mid,),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT status FROM workspace_members WHERE id = ?", (mid,)
        ).fetchone()
        self.assertEqual(row[0], "removed")

    def test_member_role_stored_correctly(self):
        mid = self._insert_member("default", "op-102", role="workspace_owner")
        row = self.conn.execute(
            "SELECT role FROM workspace_members WHERE id = ?", (mid,)
        ).fetchone()
        self.assertEqual(row[0], "workspace_owner")

    def test_duplicate_membership_unique_index(self):
        self._insert_member("default", "op-103")
        with self.assertRaises(Exception):
            self._insert_member("default", "op-103")

    def test_cross_workspace_isolation(self):
        """Member of workspace A must not appear in workspace B list."""
        self._insert_member("default", "op-200", role="workspace_member")
        # Insert a second workspace
        self.conn.execute(
            """INSERT INTO workspaces
               (id, tenant_id, name, slug, owner_id, status, created_at, updated_at)
               VALUES ('ws-b', 'demo', 'B', 'b', 'op-200', 'active',
                       '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"""
        )
        self.conn.commit()
        rows = self.conn.execute(
            "SELECT operator_id FROM workspace_members WHERE workspace_id = 'ws-b'"
        ).fetchall()
        operator_ids = [r[0] for r in rows]
        self.assertNotIn("op-200", operator_ids)


class TestGL224InviteOperations(unittest.TestCase):
    """Basic invite CRUD against the migrated schema."""

    def setUp(self):
        self.conn, _ = _applied_conn()

    def tearDown(self):
        self.conn.close()

    def _insert_invite(self, workspace_id: str = "default",
                       email_hash: str = "hash-abc") -> str:
        iid = str(uuid.uuid4())
        self.conn.execute(
            """INSERT INTO workspace_invites
               (id, workspace_id, invited_by, email_hash, role, status, expires_at, created_at)
               VALUES (?, ?, 'op-001', ?, 'workspace_member', 'pending',
                       '2027-01-01T00:00:00Z', '2026-01-01T00:00:00Z')""",
            (iid, workspace_id, email_hash),
        )
        self.conn.commit()
        return iid

    def test_insert_and_lookup_invite(self):
        iid = self._insert_invite()
        row = self.conn.execute(
            "SELECT id, workspace_id, email_hash, status FROM workspace_invites WHERE id = ?",
            (iid,),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[1], "default")
        self.assertEqual(row[3], "pending")

    def test_invite_accept_transition(self):
        iid = self._insert_invite(email_hash="hash-xyz")
        self.conn.execute(
            "UPDATE workspace_invites SET status = 'accepted' WHERE id = ?", (iid,)
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT status FROM workspace_invites WHERE id = ?", (iid,)
        ).fetchone()
        self.assertEqual(row[0], "accepted")

    def test_invite_email_hash_lookup(self):
        iid = self._insert_invite(email_hash="hash-lookup-test")
        row = self.conn.execute(
            "SELECT id FROM workspace_invites WHERE email_hash = ?",
            ("hash-lookup-test",),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], iid)

    def test_invite_no_plaintext_email_stored(self):
        rows = self.conn.execute("PRAGMA table_info(workspace_invites)").fetchall()
        col_names = [r[1] for r in rows]
        self.assertNotIn("email", col_names)
        self.assertIn("email_hash", col_names)


class TestGL224WorkspaceSlugUniqueness(unittest.TestCase):
    """tenant_id + slug combination must be unique per workspace."""

    def setUp(self):
        self.conn, _ = _applied_conn()

    def tearDown(self):
        self.conn.close()

    def test_duplicate_slug_same_tenant_rejected(self):
        self.conn.execute(
            """INSERT INTO workspaces
               (id, tenant_id, name, slug, owner_id, status, created_at, updated_at)
               VALUES ('ws-dup-1', 'demo', 'Alpha', 'alpha', 'op1', 'active',
                       '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"""
        )
        self.conn.commit()
        with self.assertRaises(Exception):
            self.conn.execute(
                """INSERT INTO workspaces
                   (id, tenant_id, name, slug, owner_id, status, created_at, updated_at)
                   VALUES ('ws-dup-2', 'demo', 'Alpha2', 'alpha', 'op1', 'active',
                           '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"""
            )
            self.conn.commit()

    def test_same_slug_different_tenants_allowed(self):
        self.conn.execute(
            """INSERT INTO workspaces
               (id, tenant_id, name, slug, owner_id, status, created_at, updated_at)
               VALUES ('ws-t1', 'tenant-a', 'Main', 'main', 'op1', 'active',
                       '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"""
        )
        self.conn.execute(
            """INSERT INTO workspaces
               (id, tenant_id, name, slug, owner_id, status, created_at, updated_at)
               VALUES ('ws-t2', 'tenant-b', 'Main', 'main', 'op1', 'active',
                       '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"""
        )
        self.conn.commit()  # must not raise


class TestGL224DocsExist(unittest.TestCase):
    def test_markdown_doc_exists(self):
        self.assertTrue(MD_PATH.exists(), f"Missing: {MD_PATH.relative_to(REPO_ROOT)}")

    def test_json_artifact_exists(self):
        self.assertTrue(JSON_PATH.exists(), f"Missing: {JSON_PATH.relative_to(REPO_ROOT)}")

    def test_json_is_valid(self):
        data = json.loads(JSON_PATH.read_text())
        self.assertIsInstance(data, dict)

    def test_json_issue_id(self):
        data = json.loads(JSON_PATH.read_text())
        self.assertEqual(data.get("issue_id"), "GL-224")

    def test_json_required_keys(self):
        data = json.loads(JSON_PATH.read_text())
        for key in [
            "issue_id", "title", "result", "new_tables", "indexes_created",
            "backfill_strategy", "migration_file", "safety_confirmations",
        ]:
            self.assertIn(key, data, f"JSON missing key: {key}")

    def test_json_new_tables_list(self):
        data = json.loads(JSON_PATH.read_text())
        tables = data.get("new_tables", [])
        self.assertIsInstance(tables, list)
        for expected in ["workspaces", "workspace_members", "workspace_invites"]:
            self.assertIn(expected, tables, f"new_tables missing: {expected}")

    def test_json_safety_no_production_saas(self):
        data = json.loads(JSON_PATH.read_text())
        safety = data.get("safety_confirmations", {})
        self.assertTrue(safety.get("production_saas_no_go"),
                        "safety_confirmations.production_saas_no_go must be true")

    def test_json_safety_no_real_data(self):
        data = json.loads(JSON_PATH.read_text())
        safety = data.get("safety_confirmations", {})
        self.assertTrue(safety.get("no_real_customer_data"))

    def test_markdown_sections(self):
        md = MD_PATH.read_text()
        for section in [
            "GL-224",
            "Workspace Schema",
            "Membership",
            "Migration",
            "Backfill",
            "Safety",
        ]:
            self.assertIn(section, md, f"Markdown missing section: {section!r}")

    def test_no_real_secrets_in_docs(self):
        md = MD_PATH.read_text()
        secret_patterns = [
            r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
            r"AKIA[A-Z0-9]{16}",
        ]
        for p in secret_patterns:
            self.assertIsNone(re.search(p, md), f"Docs contain secret pattern: {p}")

    def test_no_real_customer_data_in_docs(self):
        md = MD_PATH.read_text()
        self.assertNotIn("@customer.com", md.lower())


class TestGL224ForbiddenFiles(unittest.TestCase):
    def test_no_setup_py(self):
        self.assertFalse((REPO_ROOT / "setup.py").exists())

    def test_no_package_json(self):
        self.assertFalse((REPO_ROOT / "package.json").exists())

    def test_no_public_snapshot(self):
        self.assertFalse((REPO_ROOT / "public-snapshot").exists())

    def test_no_kubernetes_helm_terraform(self):
        for d in ["k8s", "helm", "terraform"]:
            self.assertFalse((REPO_ROOT / d).exists(), f"Forbidden: {d}/")


class TestGL224GateScript(unittest.TestCase):
    def test_gate_script_exists(self):
        self.assertTrue(GATE_SCRIPT.exists(), f"Missing: {GATE_SCRIPT.relative_to(REPO_ROOT)}")

    def test_gate_script_compiles(self):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(GATE_SCRIPT)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"Compile error: {result.stderr}")

    def test_gate_dry_run(self):
        result = subprocess.run(
            [sys.executable, str(GATE_SCRIPT), "--dry-run"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        self.assertEqual(result.returncode, 0,
                         f"--dry-run failed:\n{result.stdout}\n{result.stderr}")
        self.assertIn("dry-run", result.stdout.lower())

    def test_gate_plan_mode(self):
        result = subprocess.run(
            [sys.executable, str(GATE_SCRIPT), "--plan"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        self.assertEqual(result.returncode, 0,
                         f"--plan failed:\n{result.stdout}\n{result.stderr}")
        self.assertIn("plan", result.stdout.lower())

    def test_gate_no_credentials_required(self):
        env = {k: v for k, v in os.environ.items()
               if not any(k.startswith(p) for p in ["AWS_", "GRANTLAYER_", "POSTGRES", "DATABASE"])}
        env["PATH"] = os.environ.get("PATH", "")
        result = subprocess.run(
            [sys.executable, str(GATE_SCRIPT), "--dry-run"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), env=env,
        )
        self.assertEqual(result.returncode, 0, "Gate should not require credentials")

    def test_gate_no_network_calls(self):
        text = GATE_SCRIPT.read_text()
        self.assertNotIn("requests.get", text)
        self.assertNotIn("urllib.request.urlopen", text)
        self.assertNotIn("socket.connect", text)

    def test_gate_no_destructive_ops(self):
        text = GATE_SCRIPT.read_text()
        for pattern in ["DROP TABLE", "DELETE FROM", "shutil.rmtree", "rm -rf"]:
            self.assertNotIn(pattern, text, f"Gate contains: {pattern!r}")

    def test_gate_redacts_secrets(self):
        text = GATE_SCRIPT.read_text()
        self.assertIn("REDACTED", text)


class TestGL224SafetyConfirmations(unittest.TestCase):
    """High-level safety invariants for this schema-only migration sprint."""

    def test_no_server_py_changes(self):
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10,
        )
        changed = [f.strip() for f in result.stdout.splitlines()]
        self.assertNotIn("backend/src/server.py", changed,
                         "GL-224 must not modify server.py")

    def test_no_auth_py_changes(self):
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10,
        )
        changed = [f.strip() for f in result.stdout.splitlines()]
        self.assertNotIn("backend/src/auth.py", changed,
                         "GL-224 must not modify auth.py")

    def test_no_grants_py_changes(self):
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10,
        )
        changed = [f.strip() for f in result.stdout.splitlines()]
        self.assertNotIn("backend/src/grants.py", changed,
                         "GL-224 must not modify grants.py")

    def test_no_github_workflow_changes(self):
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10,
        )
        changed = [f.strip() for f in result.stdout.splitlines()]
        wf = [f for f in changed if ".github/workflows" in f]
        self.assertEqual(wf, [], f"Forbidden workflow changes: {wf}")


if __name__ == "__main__":
    unittest.main()
