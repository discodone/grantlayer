"""catch-up: bring Alembic to full parity with the frozen runner

Adds every object the file-based runner provisions that Alembic lacked, so an
Alembic-provisioned production database is no longer missing anything the
application expects:

  - api_keys and grant_templates tables (+ their indexes)
  - workspaces.plan_tier (NOT NULL DEFAULT 'free') and rate_limit_override
  - the composite workspace_members(workspace_id, operator_id) unique index
  - 19 server-side column defaults the runner declares and Alembic omitted
  - audit_events.seq (sequence + column + insertion-order backfill + index)
  - the audit_events immutability triggers (created LAST, after the backfill)

Every step is idempotent (IF NOT EXISTS / existence-guarded / default-checked)
so the revision is safe to run on an already-deployed, partially-migrated
database and a clean no-op on a second run. The no_update trigger is dropped
only when the seq backfill (an UPDATE) actually runs, and recreated afterwards;
no_delete is never dropped.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SEQUENCE_NAME = "audit_events_seq_seq"

# Server-side defaults the runner declares that Alembic's ORM-generated DDL
# omitted. Values are exact SQL literals (quoted for text, bare for integer):
# on an INSERT that omits the column the database now supplies the same value
# the runner would, instead of NULL. Additive; the application supplies these
# today, but a raw write past the ORM must not silently lose them.
_SERVER_DEFAULTS: dict[str, dict[str, str]] = {
    "audit_events": {
        "challenge_present": "0",
        "challenge_result": "'legacy_mode'",
        "grant_signature_result": "'not_checked'",
    },
    "challenges": {"status": "'active'", "tenant_id": "'demo'"},
    "evidence_archives": {"tenant_id": "'demo'"},
    "grant_executions": {"tenant_id": "'demo'"},
    "grant_requests": {"status": "'requested'", "tenant_id": "'demo'"},
    "grants": {"revoked": "0", "tenant_id": "'demo'", "use_count": "0"},
    "operators": {"active": "1", "tenant_id": "'demo'"},
    "workspace_invites": {"role": "'workspace_member'", "status": "'pending'"},
    "workspace_members": {"role": "'workspace_member'", "status": "'active'"},
    "workspaces": {"status": "'active'"},
}


# ── idempotency helpers ────────────────────────────────────────────
def _has_column(bind, table: str, col: str) -> bool:
    return col in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _has_trigger(bind, name: str) -> bool:
    if bind.dialect.name == "postgresql":
        return bind.execute(
            sa.text("SELECT 1 FROM pg_trigger WHERE tgname = :n AND NOT tgisinternal"),
            {"n": name},
        ).first() is not None
    return bind.execute(
        sa.text("SELECT 1 FROM sqlite_master WHERE type='trigger' AND name = :n"),
        {"n": name},
    ).first() is not None


def _norm_default(d) -> str | None:
    if d is None:
        return None
    s = str(d).strip()
    if s.upper() == "NULL":
        return None
    s = s.split("::", 1)[0].strip().strip("'").strip('"').strip()
    return s.lower() or None


def _current_default(bind, table: str, col: str) -> str | None:
    for c in sa.inspect(bind).get_columns(table):
        if c["name"] == col:
            return _norm_default(c.get("default"))
    return None


# ── steps ──────────────────────────────────────────────────────────
def _create_api_keys() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            key_hash TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            scopes TEXT NOT NULL DEFAULT '[]',
            expires_at TEXT,
            last_used_at TEXT,
            created_at TEXT NOT NULL,
            revoked_at TEXT
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_workspace_id ON api_keys(workspace_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash)")


def _create_grant_templates() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS grant_templates (
            id TEXT PRIMARY KEY,
            workspace_id TEXT,
            name TEXT NOT NULL,
            description TEXT,
            schema_json TEXT NOT NULL DEFAULT '{}',
            default_values TEXT NOT NULL DEFAULT '{}',
            version INTEGER NOT NULL DEFAULT 1,
            parent_id TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            locked INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            created_by TEXT NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_grant_templates_workspace_id ON grant_templates(workspace_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_grant_templates_parent_id ON grant_templates(parent_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_grant_templates_is_active ON grant_templates(is_active)"
    )


def _apply_server_defaults(bind, dialect: str) -> None:
    for table, cols in _SERVER_DEFAULTS.items():
        todo = {
            c: v
            for c, v in cols.items()
            if _current_default(bind, table, c) != _norm_default(v)
        }
        if not todo:
            continue
        if dialect == "postgresql":
            for c, v in todo.items():
                op.execute(f"ALTER TABLE {table} ALTER COLUMN {c} SET DEFAULT {v}")
        else:
            # SQLite cannot ALTER a column default in place; batch rebuilds the
            # table. Reached only when a default is actually missing (first run),
            # and audit_events has no triggers yet at this point, so the rebuild
            # is safe. A second run finds every default already set and skips.
            with op.batch_alter_table(table) as batch:
                for c, v in todo.items():
                    batch.alter_column(c, server_default=sa.text(v))


def _add_seq(bind, dialect: str) -> None:
    if _has_column(bind, "audit_events", "seq"):
        return
    # The backfill is an UPDATE on audit_events; drop the no_update trigger first
    # so it is not blocked. no_delete is never touched. On a fresh / broken-prod
    # Alembic DB no such trigger exists yet, so this is a guarded no-op there.
    if dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_events_no_update ON audit_events")
        op.execute(
            f"CREATE SEQUENCE IF NOT EXISTS {_SEQUENCE_NAME} START WITH 1 INCREMENT BY 1"
        )
        op.execute(
            f"ALTER TABLE audit_events ADD COLUMN seq BIGINT DEFAULT nextval('{_SEQUENCE_NAME}')"
        )
        op.execute(
            """
            UPDATE audit_events ae
            SET seq = sub.rn
            FROM (
                SELECT id, row_number() OVER (ORDER BY timestamp ASC, ctid ASC) AS rn
                FROM audit_events
            ) sub
            WHERE ae.id = sub.id AND ae.seq IS NULL
            """
        )
        op.execute(
            f"SELECT setval('{_SEQUENCE_NAME}', COALESCE((SELECT MAX(seq) FROM audit_events), 0) + 1)"
        )
        op.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_seq ON audit_events(seq)")
    else:
        op.execute("DROP TRIGGER IF EXISTS trg_audit_events_no_update")
        op.execute("ALTER TABLE audit_events ADD COLUMN seq INTEGER")
        op.execute("UPDATE audit_events SET seq = rowid WHERE seq IS NULL")
        op.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_seq ON audit_events(seq)")


def _create_triggers(bind, dialect: str) -> None:
    if dialect == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION audit_immutability_check()
            RETURNS TRIGGER AS $$
            BEGIN
              RAISE EXCEPTION 'audit_events are immutable';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        if not _has_trigger(bind, "audit_events_no_update"):
            op.execute(
                "CREATE TRIGGER audit_events_no_update BEFORE UPDATE ON audit_events "
                "FOR EACH ROW EXECUTE FUNCTION audit_immutability_check()"
            )
        if not _has_trigger(bind, "audit_events_no_delete"):
            op.execute(
                "CREATE TRIGGER audit_events_no_delete BEFORE DELETE ON audit_events "
                "FOR EACH ROW EXECUTE FUNCTION audit_immutability_check()"
            )
    else:
        op.execute(
            "CREATE TRIGGER IF NOT EXISTS trg_audit_events_no_update "
            "BEFORE UPDATE ON audit_events "
            "BEGIN SELECT RAISE(ABORT, 'audit_events is immutable: UPDATE is forbidden'); END"
        )
        op.execute(
            "CREATE TRIGGER IF NOT EXISTS trg_audit_events_no_delete "
            "BEFORE DELETE ON audit_events "
            "BEGIN SELECT RAISE(ABORT, 'audit_events is immutable: DELETE is forbidden'); END"
        )


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    _create_api_keys()
    _create_grant_templates()

    if not _has_column(bind, "workspaces", "plan_tier"):
        op.execute("ALTER TABLE workspaces ADD COLUMN plan_tier TEXT NOT NULL DEFAULT 'free'")
    if not _has_column(bind, "workspaces", "rate_limit_override"):
        op.execute("ALTER TABLE workspaces ADD COLUMN rate_limit_override INTEGER")

    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_workspace_members_workspace_operator "
        "ON workspace_members(workspace_id, operator_id)"
    )

    _apply_server_defaults(bind, dialect)
    _add_seq(bind, dialect)          # drops no_update before the backfill, if any
    _create_triggers(bind, dialect)  # triggers LAST, after the backfill


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_events_no_update ON audit_events")
        op.execute("DROP TRIGGER IF EXISTS audit_events_no_delete ON audit_events")
        op.execute("DROP FUNCTION IF EXISTS audit_immutability_check()")
        op.execute("DROP INDEX IF EXISTS idx_audit_events_seq")
        if _has_column(bind, "audit_events", "seq"):
            op.execute("ALTER TABLE audit_events DROP COLUMN seq")
        op.execute(f"DROP SEQUENCE IF EXISTS {_SEQUENCE_NAME}")
    else:
        op.execute("DROP TRIGGER IF EXISTS trg_audit_events_no_update")
        op.execute("DROP TRIGGER IF EXISTS trg_audit_events_no_delete")
        op.execute("DROP INDEX IF EXISTS idx_audit_events_seq")
        if _has_column(bind, "audit_events", "seq"):
            with op.batch_alter_table("audit_events") as batch:
                batch.drop_column("seq")

    op.execute("DROP INDEX IF EXISTS idx_workspace_members_workspace_operator")
    op.execute("DROP TABLE IF EXISTS grant_templates")
    op.execute("DROP TABLE IF EXISTS api_keys")
    # workspaces.plan_tier / rate_limit_override and the server-side defaults are
    # left in place: they are additive and harmless, and dropping a column on
    # SQLite would force another table rebuild for no operational benefit.
