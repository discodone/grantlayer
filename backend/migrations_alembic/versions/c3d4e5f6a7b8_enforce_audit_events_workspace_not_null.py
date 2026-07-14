"""Enforce audit_events.workspace_id NOT NULL (GL-353)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-14 00:00:00.000000

GL-352 made ``AuditEvent.workspace_id`` a required field in Python (mypy enforces
it), but the DATABASE still permitted NULL: audit_events.workspace_id was nullable
on both SQLite and PostgreSQL, so the defect could silently return via any raw
insert or future code path. This is the AUTHORITATIVE (production) half of the
fix — a runner migration (0019) mirrors it for init_db()/SQLite/dev, and both
delegate to the same shared logic in backend.src.migrations._audit_ws_not_null so
they cannot drift.

Supersedes f3b047b5c9bb for this table: that earlier "enforce_workspace_id_not_null"
migration was PostgreSQL-only (SET NOT NULL under a dialect check, a silent no-op
on SQLite) AND it omitted audit_events entirely. This migration enforces on BOTH
backends and covers audit_events specifically:

  - backfill NULL workspace_id -> '__system__' (quarantine un-attributable rows).
  - PostgreSQL: drop any UPDATE-firing immutability trigger (it blocks the
    backfill UPDATE), backfill, ALTER COLUMN workspace_id SET NOT NULL, recreate
    the trigger verbatim via pg_get_triggerdef(); never touches no_delete.
  - SQLite: rebuild audit_events with workspace_id TEXT NOT NULL derived from the
    live CREATE TABLE, copying row_hash/prev_hash/seq verbatim, then restore
    indexes + triggers.

Note the two provisioning paths differ: an Alembic-provisioned database never had
the audit immutability triggers (they are runner-only), so the shared logic is
adaptive — it captures and restores exactly whatever triggers actually exist.

Requires an online migration (a live connection to introspect and rebuild); it
is not expressible as offline SQL generation.
"""
from typing import Sequence, Union

from alembic import context, op

# Alembic prepends the project root to sys.path (see env.py), so the shared
# runtime enforcement logic is importable and shared with runner migration 0019.
from backend.src.migrations._audit_ws_not_null import enforce_audit_workspace_not_null

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError(
            "c3d4e5f6a7b8 enforces audit_events.workspace_id NOT NULL via a live "
            "backfill + table rebuild and cannot run in offline (--sql) mode. "
            "Run `alembic upgrade head` against a live database."
        )

    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    def query(sql):
        return [tuple(r) for r in bind.exec_driver_sql(sql).fetchall()]

    def execute(sql):
        bind.exec_driver_sql(sql)

    enforce_audit_workspace_not_null(is_postgres, query, execute)


def downgrade() -> None:
    # Re-permitting NULL would reopen the attribution defect and, on SQLite, would
    # require another full table rebuild. Intentionally a no-op: the sentinel-backed
    # NOT NULL constraint is a one-way hardening.
    pass
