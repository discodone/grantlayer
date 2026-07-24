"""Add nullable subject_id column to api_keys.

Binds an API key to the single subject identity it may exercise as on
/v1/exercise. STRICTLY ADDITIVE AND FORWARD-ONLY:

  * the column is nullable with no default, so existing rows keep NULL and are
    not rewritten;
  * a NULL binding does NOT grandfather the old permissive behaviour — the
    exercise path refuses unbound keys (403 api_key_subject_unbound), so
    existing keys fail CLOSED until an operator explicitly binds them.
"""

version = "0021_api_key_subject"


def _backend(conn) -> str:
    return getattr(conn, "backend", "sqlite")


def _column_exists(conn, table: str, column: str) -> bool:
    if _backend(conn) == "postgres":
        row = conn.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s",
            (table, column),
        ).fetchone()
        return row is not None
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def apply(conn) -> None:
    if not _column_exists(conn, "api_keys", "subject_id"):
        conn.execute("ALTER TABLE api_keys ADD COLUMN subject_id TEXT")
    conn.commit()
