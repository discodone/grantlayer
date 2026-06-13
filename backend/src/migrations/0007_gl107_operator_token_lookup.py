"""GrantLayer MVP — Operator Auth Token Lookup Hardening.

Adds token_lookup_hash column to operators table for deterministic
O(1) narrowing before PBKDF2 verification.  Also creates an index on
the new column.

Compatible with SQLite and PostgreSQL backends.
"""


version = "0007_gl107_operator_token_lookup"


def _column_exists(conn, table: str, column: str) -> bool:
    backend = getattr(conn, "backend", "sqlite")
    if backend == "postgres":
        try:
            row = conn.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
                """,
                (table, column),
            ).fetchone()
            return row is not None
        except Exception:
            return False
    else:
        try:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            return any(r[1] == column for r in rows)
        except Exception:
            return False


def _index_exists(conn, index_name: str) -> bool:
    backend = getattr(conn, "backend", "sqlite")
    if backend == "postgres":
        try:
            row = conn.execute(
                "SELECT 1 FROM pg_indexes WHERE indexname = %s",
                (index_name,),
            ).fetchone()
            return row is not None
        except Exception:
            return False
    else:
        try:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
                (index_name,),
            ).fetchone()
            return row is not None
        except Exception:
            return False


def apply(conn) -> None:
    """Add token_lookup_hash column and index to operators table."""
    if not _column_exists(conn, "operators", "token_lookup_hash"):
        conn.execute("ALTER TABLE operators ADD COLUMN token_lookup_hash TEXT")

    if not _index_exists(conn, "idx_operators_token_lookup_hash"):
        conn.execute(
            "CREATE INDEX idx_operators_token_lookup_hash ON operators (token_lookup_hash)"
        )

    conn.commit()
