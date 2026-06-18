"""Add grant_templates table for multi-workspace grant templates."""

version = "0018_gl325_grant_templates"


def _backend(conn) -> str:
    return getattr(conn, "backend", "sqlite")


def _table_exists(conn, table: str) -> bool:
    backend = _backend(conn)
    if backend == "postgres":
        row = conn.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
            (table,),
        ).fetchone()
        return row is not None
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def apply(conn) -> None:
    if _table_exists(conn, "grant_templates"):
        return

    conn.execute(
        """
        CREATE TABLE grant_templates (
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

    backend = _backend(conn)
    idx_prefix = "IF NOT EXISTS " if backend != "postgres" else ""
    conn.execute(
        f"CREATE INDEX {idx_prefix}idx_grant_templates_workspace_id ON grant_templates(workspace_id)"
    )
    conn.execute(
        f"CREATE INDEX {idx_prefix}idx_grant_templates_parent_id ON grant_templates(parent_id)"
    )
    conn.execute(
        f"CREATE INDEX {idx_prefix}idx_grant_templates_is_active ON grant_templates(is_active)"
    )
    conn.commit()
