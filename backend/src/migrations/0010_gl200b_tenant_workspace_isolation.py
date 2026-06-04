"""GrantLayer MVP — GL-200B Tenant/Workspace Isolation Baseline Migration.

Adds tenant_id and workspace_id (nullable, reserved for GL-200C) to all
business resource tables. Adds tenant_id to operators table (backfilled 'demo').

Migration is idempotent: re-running is safe; column-existence is checked before
each ALTER TABLE. Both SQLite and PostgreSQL are supported.

Backfill strategy:
  - Business tables:  tenant_id TEXT NOT NULL DEFAULT 'demo' (both for new inserts and backfill)
  - audit_events:     tenant_id TEXT DEFAULT NULL  (nullable — system/legacy events have no tenant)
  - Operators:        tenant_id TEXT NOT NULL DEFAULT 'demo' (consistent with legacy resource default)
  - admin-token auth: resolves to tenant_id='demo' (backward compat with legacy resources)

Indexes:
  - idx_<table>_tenant_id on each scoped table for query performance.
"""

version = "0010_gl200b_tenant_workspace_isolation"

# Tables that receive tenant_id NOT NULL = 'demo' backfill (business resources, excluding audit_events)
_BUSINESS_TABLES = [
    "grants",
    "grant_requests",
    "challenges",
    "grant_executions",
    "evidence_archives",
]

# audit_events uses nullable tenant_id — system/legacy events predate tenant isolation
_AUDIT_TABLE = "audit_events"

# Operators receive tenant_id = 'dev' (admin-token dev/demo mode)
_OPERATOR_TABLE = "operators"


def _column_exists(conn, table: str, column: str) -> bool:
    backend = getattr(conn, "backend", "sqlite")
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


def _table_exists(conn, table: str) -> bool:
    backend = getattr(conn, "backend", "sqlite")
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


def _index_exists(conn, index_name: str) -> bool:
    backend = getattr(conn, "backend", "sqlite")
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


def _add_tenant_columns(conn, table: str, default_tenant: str, nullable: bool = False) -> None:
    """Add tenant_id and workspace_id columns to a table if not present.

    nullable=True uses TEXT DEFAULT NULL (for audit_events which records legacy
    system events without a tenant). nullable=False (default) uses NOT NULL with
    the default_tenant value as both the SQLite DEFAULT and the backfill value so
    that both new inserts and existing rows use the correct tenant.
    """
    if not _table_exists(conn, table):
        return

    if not _column_exists(conn, table, "tenant_id"):
        if nullable:
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN tenant_id TEXT DEFAULT NULL"
            )
            # No backfill for the nullable path (audit_events).
            # Pre-migration events keep tenant_id=NULL intentionally:
            # (a) NULL preserves the hash-chain canonical payload format so
            #     stored row_hash values remain verifiable (GL-103/GL-202).
            # (b) The audit immutability trigger (GL-102) blocks UPDATE, so
            #     a blanket backfill would fail on any DB that already contains
            #     audit events.
            # Legacy events with NULL tenant_id are handled fail-closed by
            # list_events() and do not appear in per-tenant filtered queries.
        else:
            # Use default_tenant directly as the SQLite DEFAULT so future inserts
            # without an explicit tenant_id also land in the correct tenant.
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN tenant_id TEXT NOT NULL DEFAULT '{default_tenant}'"
            )

    if not _column_exists(conn, table, "workspace_id"):
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN workspace_id TEXT DEFAULT NULL"
        )


def _add_scope_column(conn, table: str) -> None:
    """Add scope column to audit_events if not present."""
    if not _column_exists(conn, table, "scope"):
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN scope TEXT DEFAULT NULL"
        )


def _add_index(conn, index_name: str, table: str, columns: str) -> None:
    """Create index if not present."""
    if not _index_exists(conn, index_name):
        conn.execute(
            f"CREATE INDEX {index_name} ON {table}({columns})"
        )


def apply(conn) -> None:
    """Add tenant_id, workspace_id columns and indexes to all business resource tables."""

    # Business resource tables: backfill to 'demo' (NOT NULL)
    for table in _BUSINESS_TABLES:
        _add_tenant_columns(conn, table, "demo")

    # audit_events: nullable tenant_id (system/legacy events have no tenant)
    _add_tenant_columns(conn, _AUDIT_TABLE, "demo", nullable=True)

    # audit_events gets an extra scope column
    _add_scope_column(conn, "audit_events")

    # Operators: backfill to 'demo' (consistent with legacy resource default)
    _add_tenant_columns(conn, _OPERATOR_TABLE, "demo")

    # Add performance indexes (only on tables that exist)
    for table in _BUSINESS_TABLES + [_AUDIT_TABLE]:
        if _table_exists(conn, table):
            _add_index(conn, f"idx_{table}_tenant_id", table, "tenant_id")

    # Composite index for grants (most common query pattern)
    if _table_exists(conn, "grants"):
        _add_index(conn, "idx_grants_tenant_subject", "grants", "tenant_id, subject_id")

    conn.commit()
