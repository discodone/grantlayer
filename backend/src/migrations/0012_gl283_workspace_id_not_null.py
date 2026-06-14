"""Backfill and enforce non-null workspace_id where supported."""

version = "0012_gl283_workspace_id_not_null"

_DEFAULT_WORKSPACE_ID = "default"
_TABLES = (
    "grants",
    "grant_requests",
    "challenges",
    "grant_executions",
    "evidence_archives",
)


def _backend(conn) -> str:
    return getattr(conn, "backend", "sqlite")


def _table_exists(conn, table: str) -> bool:
    if _backend(conn) == "postgres":
        row = conn.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
            (table,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
    return row is not None


def _column_exists(conn, table: str, column: str) -> bool:
    if _backend(conn) == "postgres":
        row = conn.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
            """,
            (table, column),
        ).fetchone()
        return row is not None
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def apply(conn) -> None:
    backend = _backend(conn)
    for table in _TABLES:
        if not _table_exists(conn, table) or not _column_exists(conn, table, "workspace_id"):
            continue
        conn.execute(
            f"UPDATE {table} SET workspace_id = ? WHERE workspace_id IS NULL",
            (_DEFAULT_WORKSPACE_ID,),
        )
        if backend == "postgres":
            conn.execute(f"ALTER TABLE {table} ALTER COLUMN workspace_id SET NOT NULL")
        row = conn.execute(
            f"SELECT COUNT(*) AS count FROM {table} WHERE workspace_id IS NULL"
        ).fetchone()
        count = row["count"] if isinstance(row, dict) else row[0]
        if int(count) != 0:
            raise RuntimeError(f"{table}.workspace_id still contains NULL values")
    conn.commit()
