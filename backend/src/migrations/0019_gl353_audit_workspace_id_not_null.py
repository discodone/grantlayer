"""Enforce workspace_id NOT NULL on audit_events (backfill + rebuild).

Runner-side entry point. The delicate backfill/rebuild logic lives in the shared
module ``_audit_ws_not_null`` so this runner migration and the authoritative
Alembic migration stay in lockstep — a single source of truth, not two copies
that can drift.

An earlier change made ``AuditEvent.workspace_id`` a required field in Python
(mypy enforces it), but the DATABASE still permitted NULL. This migration closes
that gap: legacy un-attributable rows are quarantined into the system-workspace
sentinel ('__system__'), and the column becomes NOT NULL — enforced by a table
rebuild on SQLite (which cannot ALTER COLUMN SET NOT NULL and whose immutability
triggers block a plain UPDATE) and by ALTER ... SET NOT NULL on PostgreSQL. See
``_audit_ws_not_null`` for the invariants (row_hash/prev_hash/seq preserved
verbatim, triggers restored, zero residual NULLs) and their self-verification.
"""

from backend.src.migrations._audit_ws_not_null import enforce_audit_workspace_not_null

version = "0019_gl353_audit_workspace_id_not_null"


def apply(conn) -> None:
    is_postgres = getattr(conn, "backend", "sqlite") == "postgres"

    def query(sql):
        return [tuple(r) for r in conn.execute(sql).fetchall()]

    def execute(sql):
        conn.execute(sql)

    enforce_audit_workspace_not_null(is_postgres, query, execute)
    conn.commit()
