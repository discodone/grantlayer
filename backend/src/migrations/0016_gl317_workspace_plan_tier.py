"""Add plan_tier and rate_limit_override to workspaces table."""

version = "0016_gl317_workspace_plan_tier"


def _backend(conn) -> str:
    return getattr(conn, "backend", "sqlite")


def _column_exists(conn, table: str, column: str) -> bool:
    backend = _backend(conn)
    if backend == "postgres":
        row = conn.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s",
            (table, column),
        ).fetchone()
        return row is not None
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def apply(conn) -> None:
    if not _column_exists(conn, "workspaces", "plan_tier"):
        conn.execute(
            "ALTER TABLE workspaces ADD COLUMN plan_tier TEXT NOT NULL DEFAULT 'free'"
        )
    if not _column_exists(conn, "workspaces", "rate_limit_override"):
        conn.execute(
            "ALTER TABLE workspaces ADD COLUMN rate_limit_override INTEGER"
        )
    conn.commit()
