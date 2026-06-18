"""Add webhook_deliveries table for tracking individual delivery attempts.

Records the outcome of each webhook dispatch: HTTP status, error message,
attempt number, and timestamps — giving operators visibility into failures.
"""

version = "0015_gl308_webhook_deliveries"


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
    if _table_exists(conn, "webhook_deliveries"):
        return

    backend = _backend(conn)
    if backend == "postgres":
        conn.execute(
            """
            CREATE TABLE webhook_deliveries (
                id TEXT PRIMARY KEY,
                webhook_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL,
                http_status INTEGER,
                error TEXT,
                attempt INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                delivered_at TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX idx_webhook_deliveries_webhook_id ON webhook_deliveries(webhook_id)"
        )
        conn.execute(
            "CREATE INDEX idx_webhook_deliveries_tenant_id ON webhook_deliveries(tenant_id)"
        )
        conn.execute(
            "CREATE INDEX idx_webhook_deliveries_created_at ON webhook_deliveries(created_at)"
        )
    else:
        conn.execute(
            """
            CREATE TABLE webhook_deliveries (
                id TEXT PRIMARY KEY,
                webhook_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL,
                http_status INTEGER,
                error TEXT,
                attempt INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                delivered_at TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_webhook_id ON webhook_deliveries(webhook_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_tenant_id ON webhook_deliveries(tenant_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_created_at ON webhook_deliveries(created_at)"
        )

    conn.commit()
