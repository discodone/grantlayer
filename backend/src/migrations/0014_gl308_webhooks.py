"""Add webhook_subscriptions table for the webhook notification system.

Stores per-tenant webhook endpoint registrations with HMAC secrets.
Events field holds a JSON array of subscribed event types.
"""

version = "0014_gl308_webhooks"


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
    if _table_exists(conn, "webhook_subscriptions"):
        return

    backend = _backend(conn)
    if backend == "postgres":
        conn.execute(
            """
            CREATE TABLE webhook_subscriptions (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                workspace_id TEXT,
                url TEXT NOT NULL,
                events TEXT NOT NULL,
                secret TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX idx_webhook_subscriptions_tenant_id ON webhook_subscriptions(tenant_id)"
        )
        conn.execute(
            "CREATE INDEX idx_webhook_subscriptions_active ON webhook_subscriptions(tenant_id, active)"
        )
    else:
        conn.execute(
            """
            CREATE TABLE webhook_subscriptions (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                workspace_id TEXT,
                url TEXT NOT NULL,
                events TEXT NOT NULL,
                secret TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_webhook_subscriptions_tenant_id ON webhook_subscriptions(tenant_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_webhook_subscriptions_active ON webhook_subscriptions(tenant_id, active)"
        )

    conn.commit()
