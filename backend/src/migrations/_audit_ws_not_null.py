"""Shared backfill + NOT NULL enforcement for audit_events.workspace_id.

Single source of truth used by BOTH migration systems so they can never drift:
  - the file-based runner migration (0019_...), applied by init_db().
  - the Alembic migration (authoritative on a production deploy).

An earlier change made ``AuditEvent.workspace_id`` a required field in Python
(mypy enforces it), but the DATABASE still permitted NULL. This closes the gap
at the schema level: legacy un-attributable rows are quarantined into the
system-workspace sentinel ('__system__') rather than absorbed into a real
tenant's audit chain, and the column becomes NOT NULL on both backends.

Both provisioning paths must be tolerated, so this logic is ADAPTIVE:
  - A runner-provisioned DB has append-only immutability triggers on
    audit_events (no_update / no_delete). These block a plain backfill UPDATE.
  - An Alembic-provisioned DB has NO such triggers (they were never mirrored
    into Alembic), and no immutability function.
So we capture whatever triggers actually exist, work around them, and restore
exactly those — never assuming a fixed set, never assuming the PG function.

CRITICAL invariants, self-verified before returning:
  - row_hash / prev_hash / seq are preserved byte-identically. The hash payload
    excludes workspace_id, so a correct backfill never rehashes and never
    renumbers. The SQLite rebuild proves this with a set-difference check while
    both tables still exist. The PG path only UPDATEs workspace_id, so those
    columns are untouched by construction.
  - every trigger that existed before exists again afterwards.
  - zero residual NULLs, and the column is declared NOT NULL.

Idempotent: if workspace_id is already NOT NULL the call is a no-op.

The only value written is the fixed sentinel literal, so all statements are
parameter-free — the two call sites can share identical SQL across drivers with
different placeholder styles.

SQL executes through two injected callables so this module is driver-agnostic:
  query(sql)   -> list[tuple]   run a SELECT/PRAGMA, return rows as tuples
  execute(sql) -> None          run a DDL/DML statement
"""

import re

SENTINEL = "__system__"
_TABLE = "audit_events"
_ERR = "audit_events workspace_id enforcement"


def enforce_audit_workspace_not_null(is_postgres, query, execute):
    """Backfill NULLs to the sentinel and make workspace_id NOT NULL.

    is_postgres: True for PostgreSQL, False for SQLite.
    query(sql): execute a query and return rows as a list of tuples.
    execute(sql): execute a DDL/DML statement (no result).
    """
    if is_postgres:
        _apply_postgres(query, execute)
    else:
        _apply_sqlite(query, execute)


# ── SQLite: full table rebuild (SET NOT NULL is unsupported; triggers block UPDATE) ──

def _sqlite_ws_not_null(query) -> bool:
    for r in query(f"PRAGMA table_info({_TABLE})"):
        if r[1] == "workspace_id":
            return int(r[3]) == 1
    return False


def _apply_sqlite(query, execute) -> None:
    if not query(f"SELECT 1 FROM sqlite_master WHERE type='table' AND name='{_TABLE}'"):
        return
    if _sqlite_ws_not_null(query):
        return  # already enforced — idempotent no-op

    # 1. Capture the exact DDL we must reproduce. Auto-indexes (PRIMARY KEY) have
    #    sql IS NULL and travel with the rename, so only real indexes are copied.
    table_sql = query(
        f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{_TABLE}'"
    )[0][0]
    index_sqls = [
        r[0]
        for r in query(
            f"SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='{_TABLE}' "
            "AND sql IS NOT NULL"
        )
    ]
    triggers = [
        (r[0], r[1])
        for r in query(
            f"SELECT name, sql FROM sqlite_master WHERE type='trigger' AND tbl_name='{_TABLE}' "
            "AND sql IS NOT NULL"
        )
    ]
    cols = [r[1] for r in query(f"PRAGMA table_info({_TABLE})")]
    if "workspace_id" not in cols:
        raise RuntimeError(f"{_ERR}: {_TABLE} has no workspace_id column")

    # 2. Derive the new table's DDL from the LIVE one (never hardcode): rename it
    #    and flip the single workspace_id column to NOT NULL. Nothing else changes.
    new_table_sql = re.sub(
        r'\bCREATE\s+TABLE\s+(["`\[]?)audit_events\1',
        "CREATE TABLE audit_events_new",
        table_sql,
        count=1,
        flags=re.IGNORECASE,
    )
    new_table_sql = re.sub(
        r'(["`\[]?)workspace_id\1\s+TEXT[^,\)]*',
        "workspace_id TEXT NOT NULL",
        new_table_sql,
        count=1,
        flags=re.IGNORECASE,
    )
    if "audit_events_new" not in new_table_sql or "workspace_id TEXT NOT NULL" not in new_table_sql:
        raise RuntimeError(f"{_ERR}: failed to derive audit_events_new schema safely")

    execute("DROP TABLE IF EXISTS audit_events_new")
    execute(new_table_sql)

    # 3. Copy every row verbatim; substitute the sentinel ONLY where NULL.
    #    row_hash / prev_hash / seq flow straight through the SELECT.
    select_exprs = [
        f"COALESCE(workspace_id, '{SENTINEL}')" if c == "workspace_id" else c
        for c in cols
    ]
    execute(
        f"INSERT INTO audit_events_new ({', '.join(cols)}) "
        f"SELECT {', '.join(select_exprs)} FROM {_TABLE}"
    )

    # 4. Prove preservation while BOTH tables still exist: identical row count,
    #    and every tamper-chain tuple carried over unchanged. Only compare chain
    #    columns that actually exist — seq is present on a runner-provisioned DB
    #    but absent on an Alembic-provisioned one.
    old_n = int(query(f"SELECT COUNT(*) FROM {_TABLE}")[0][0])
    new_n = int(query("SELECT COUNT(*) FROM audit_events_new")[0][0])
    if old_n != new_n:
        raise RuntimeError(f"{_ERR}: row count changed during rebuild ({old_n} -> {new_n})")
    chain_cols = ", ".join(c for c in ("id", "row_hash", "prev_hash", "seq") if c in cols)
    drifted = int(
        query(
            "SELECT COUNT(*) FROM ("
            f"  SELECT {chain_cols} FROM {_TABLE}"
            "  EXCEPT"
            f"  SELECT {chain_cols} FROM audit_events_new"
            ")"
        )[0][0]
    )
    if drifted != 0:
        raise RuntimeError(
            f"{_ERR}: tamper-chain columns ({chain_cols}) not preserved verbatim "
            f"({drifted} rows drifted)"
        )

    # 5. Swap. DROP TABLE is DDL — the no_delete trigger does not fire — and no FK
    #    references audit_events, so this is safe.
    execute(f"DROP TABLE {_TABLE}")
    execute(f"ALTER TABLE audit_events_new RENAME TO {_TABLE}")

    # 6. Restore the real indexes and the captured triggers byte-for-byte.
    for sql in index_sqls:
        execute(sql)
    for _name, sql in triggers:
        execute(sql)

    # 7. Self-verify: enforcement, no residual NULLs, and every prior trigger back.
    if not _sqlite_ws_not_null(query):
        raise RuntimeError(f"{_ERR}: workspace_id still nullable after rebuild")
    remaining = int(query(f"SELECT COUNT(*) FROM {_TABLE} WHERE workspace_id IS NULL")[0][0])
    if remaining != 0:
        raise RuntimeError(f"{_ERR}: {remaining} workspace_id NULLs remain after backfill")
    restored = {
        r[0]
        for r in query(
            f"SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='{_TABLE}'"
        )
    }
    for name, _sql in triggers:
        if name not in restored:
            raise RuntimeError(f"{_ERR}: trigger {name} not restored after rebuild")


# ── PostgreSQL: backfill + SET NOT NULL, working around UPDATE-blocking triggers ──

def _pg_ws_not_null(query) -> bool:
    rows = query(
        "SELECT is_nullable FROM information_schema.columns "
        f"WHERE table_name = '{_TABLE}' AND column_name = 'workspace_id'"
    )
    if not rows:
        return False
    return rows[0][0] == "NO"


def _apply_postgres(query, execute) -> None:
    if _pg_ws_not_null(query):
        return  # already enforced — idempotent no-op

    # Capture the row-level triggers that FIRE ON UPDATE (tgtype bit 16) — those,
    # and only those, block the backfill UPDATE. pg_get_triggerdef() yields the
    # exact CREATE TRIGGER text so we can restore each verbatim, including its
    # function reference. A no_delete (BEFORE DELETE) trigger is not selected, so
    # DELETE protection is never lifted. On an Alembic-provisioned DB there are
    # no such triggers and this is simply empty.
    update_triggers = query(
        "SELECT tgname, pg_get_triggerdef(oid) FROM pg_trigger "
        f"WHERE tgrelid = '{_TABLE}'::regclass AND NOT tgisinternal AND (tgtype & 16) <> 0"
    )
    for name, _tdef in update_triggers:
        execute(f'DROP TRIGGER IF EXISTS "{name}" ON {_TABLE}')

    execute(f"UPDATE {_TABLE} SET workspace_id = '{SENTINEL}' WHERE workspace_id IS NULL")
    execute(f"ALTER TABLE {_TABLE} ALTER COLUMN workspace_id SET NOT NULL")

    for _name, tdef in update_triggers:
        execute(tdef)

    # Self-verify: enforcement, no residual NULLs, and every dropped trigger back.
    if not _pg_ws_not_null(query):
        raise RuntimeError(f"{_ERR}: workspace_id still nullable after ALTER")
    remaining = int(
        query(f"SELECT COUNT(*) FROM {_TABLE} WHERE workspace_id IS NULL")[0][0]
    )
    if remaining != 0:
        raise RuntimeError(f"{_ERR}: {remaining} workspace_id NULLs remain after backfill")
    present = {
        r[0]
        for r in query(
            "SELECT tgname FROM pg_trigger "
            f"WHERE tgrelid = '{_TABLE}'::regclass AND NOT tgisinternal"
        )
    }
    for name, _tdef in update_triggers:
        if name not in present:
            raise RuntimeError(f"{_ERR}: trigger {name} not restored after enforcement")
