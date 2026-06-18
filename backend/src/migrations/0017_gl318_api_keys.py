"""Add api_keys table for long-lived API key management."""

version = "0017_gl318_api_keys"


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
    if _table_exists(conn, "api_keys"):
        return

    conn.execute(
        """
        CREATE TABLE api_keys (
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

    backend = _backend(conn)
    idx_prefix = "IF NOT EXISTS " if backend != "postgres" else ""
    conn.execute(
        f"CREATE INDEX {idx_prefix}idx_api_keys_workspace_id ON api_keys(workspace_id)"
    )
    conn.execute(
        f"CREATE INDEX {idx_prefix}idx_api_keys_user_id ON api_keys(user_id)"
    )
    conn.execute(
        f"CREATE INDEX {idx_prefix}idx_api_keys_key_hash ON api_keys(key_hash)"
    )
    conn.commit()
