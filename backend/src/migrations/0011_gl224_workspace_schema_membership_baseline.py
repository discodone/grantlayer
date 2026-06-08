"""GrantLayer MVP — GL-224 Workspace Schema / Membership Baseline Migration.

Introduces three new tables:
  workspaces       — workspace identity, scoped to a tenant
  workspace_members — operator ↔ workspace membership records
  workspace_invites — pending invites (email stored as hash only)

Backfill strategy:
  - Insert a canonical 'demo' workspace for tenant_id='demo' if not present.
  - Set workspace_id = 'default' on all existing resource rows where
    workspace_id IS NULL AND tenant_id = 'demo'.
  - Backfill is idempotent (re-runnable safely).
  - Production-mode rows with NULL workspace_id are left unchanged (do not
    backfill unknown tenants — that is a data-integrity error to investigate).

Indexes:
  - idx_workspaces_tenant_id
  - idx_workspaces_tenant_slug  (composite, unique enforcement support)
  - idx_workspace_members_workspace_id
  - idx_workspace_members_operator_id
  - idx_workspace_members_workspace_operator  (composite unique)
  - idx_workspace_invites_workspace_id
  - idx_workspace_invites_email_hash

Both SQLite and PostgreSQL are supported.
Migration is idempotent: re-running is safe.
"""

version = "0011_gl224_workspace_schema_membership_baseline"

# Canonical legacy workspace used for 'demo' tenant backfill
_DEMO_WORKSPACE_ID = "default"
_DEMO_TENANT_ID = "demo"
_DEMO_WORKSPACE_NAME = "default"
_DEMO_WORKSPACE_SLUG = "default"
_DEMO_WORKSPACE_OWNER = "system"
_DEMO_WORKSPACE_CREATED = "2024-01-01T00:00:00Z"

# Business resource tables that carry workspace_id (for backfill)
_BACKFILL_TABLES = [
    "grants",
    "grant_requests",
    "challenges",
    "grant_executions",
    "evidence_archives",
]


def _backend(conn) -> str:
    return getattr(conn, "backend", "sqlite")


def _table_exists(conn, table: str) -> bool:
    backend = _backend(conn)
    if backend == "postgres":
        try:
            row = conn.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
                (table,),
            ).fetchone()
            return row is not None
        except Exception:
            return False
    else:
        try:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            return row is not None
        except Exception:
            return False


def _column_exists(conn, table: str, column: str) -> bool:
    backend = _backend(conn)
    if backend == "postgres":
        try:
            row = conn.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
                """,
                (table, column),
            ).fetchone()
            return row is not None
        except Exception:
            return False
    else:
        try:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            return any(r[1] == column for r in rows)
        except Exception:
            return False


def _index_exists(conn, index_name: str) -> bool:
    backend = _backend(conn)
    if backend == "postgres":
        try:
            row = conn.execute(
                "SELECT 1 FROM pg_indexes WHERE indexname = %s",
                (index_name,),
            ).fetchone()
            return row is not None
        except Exception:
            return False
    else:
        try:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
                (index_name,),
            ).fetchone()
            return row is not None
        except Exception:
            return False


def _create_workspaces_table(conn) -> None:
    if _table_exists(conn, "workspaces"):
        return
    conn.execute("""
        CREATE TABLE workspaces (
            id          TEXT PRIMARY KEY,
            tenant_id   TEXT NOT NULL,
            name        TEXT NOT NULL,
            slug        TEXT NOT NULL,
            owner_id    TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'active',
            description TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
    """)


def _create_workspace_members_table(conn) -> None:
    if _table_exists(conn, "workspace_members"):
        return
    conn.execute("""
        CREATE TABLE workspace_members (
            id           TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            operator_id  TEXT NOT NULL,
            role         TEXT NOT NULL DEFAULT 'workspace_member',
            invited_by   TEXT,
            joined_at    TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'active'
        )
    """)


def _create_workspace_invites_table(conn) -> None:
    if _table_exists(conn, "workspace_invites"):
        return
    conn.execute("""
        CREATE TABLE workspace_invites (
            id           TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            invited_by   TEXT NOT NULL,
            email_hash   TEXT NOT NULL,
            role         TEXT NOT NULL DEFAULT 'workspace_member',
            status       TEXT NOT NULL DEFAULT 'pending',
            expires_at   TEXT NOT NULL,
            created_at   TEXT NOT NULL
        )
    """)


def _add_index(conn, index_name: str, table: str, columns: str, unique: bool = False) -> None:
    if _index_exists(conn, index_name):
        return
    if not _table_exists(conn, table):
        return
    unique_kw = "UNIQUE " if unique else ""
    conn.execute(f"CREATE {unique_kw}INDEX {index_name} ON {table}({columns})")


def _backfill_demo_workspace(conn) -> None:
    """Insert the canonical demo workspace if it does not already exist."""
    row = conn.execute(
        "SELECT 1 FROM workspaces WHERE id = ?",
        (_DEMO_WORKSPACE_ID,),
    ).fetchone()
    if row is None:
        conn.execute(
            """
            INSERT INTO workspaces
                (id, tenant_id, name, slug, owner_id, status, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'active', 'Default demo workspace (backfill)', ?, ?)
            """,
            (
                _DEMO_WORKSPACE_ID,
                _DEMO_TENANT_ID,
                _DEMO_WORKSPACE_NAME,
                _DEMO_WORKSPACE_SLUG,
                _DEMO_WORKSPACE_OWNER,
                _DEMO_WORKSPACE_CREATED,
                _DEMO_WORKSPACE_CREATED,
            ),
        )


def _backfill_resource_workspace_ids(conn) -> None:
    """Set workspace_id = 'default' on demo-tenant resource rows with NULL workspace_id."""
    for table in _BACKFILL_TABLES:
        if not _table_exists(conn, table):
            continue
        if not _column_exists(conn, table, "workspace_id"):
            continue
        if not _column_exists(conn, table, "tenant_id"):
            continue
        conn.execute(
            f"""
            UPDATE {table}
            SET workspace_id = ?
            WHERE workspace_id IS NULL AND tenant_id = ?
            """,
            (_DEMO_WORKSPACE_ID, _DEMO_TENANT_ID),
        )


def apply(conn) -> None:
    """Create workspace tables, indexes, and backfill existing demo-tenant data."""

    _create_workspaces_table(conn)
    _create_workspace_members_table(conn)
    _create_workspace_invites_table(conn)

    # Indexes on workspaces
    _add_index(conn, "idx_workspaces_tenant_id", "workspaces", "tenant_id")
    _add_index(conn, "idx_workspaces_tenant_slug", "workspaces", "tenant_id, slug", unique=True)

    # Indexes on workspace_members
    _add_index(conn, "idx_workspace_members_workspace_id", "workspace_members", "workspace_id")
    _add_index(conn, "idx_workspace_members_operator_id", "workspace_members", "operator_id")
    _add_index(
        conn,
        "idx_workspace_members_workspace_operator",
        "workspace_members",
        "workspace_id, operator_id",
        unique=True,
    )

    # Indexes on workspace_invites
    _add_index(conn, "idx_workspace_invites_workspace_id", "workspace_invites", "workspace_id")
    _add_index(conn, "idx_workspace_invites_email_hash", "workspace_invites", "email_hash")

    # Backfill
    _backfill_demo_workspace(conn)
    _backfill_resource_workspace_ids(conn)

    conn.commit()
