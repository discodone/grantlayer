"""GrantLayer MVP — GL-119 Operator Token Expiry and Rotation Baseline.

Adds expires_at and rotated_at columns to the operators table for
operator token expiry and rotation support.

Compatible with SQLite and PostgreSQL backends.
"""

import sqlite3

version = "0009_gl119_operator_token_expiry_rotation"


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


def apply(conn) -> None:
    """Add expires_at and rotated_at columns to operators table."""
    if not _column_exists(conn, "operators", "expires_at"):
        conn.execute("ALTER TABLE operators ADD COLUMN expires_at TEXT")

    if not _column_exists(conn, "operators", "rotated_at"):
        conn.execute("ALTER TABLE operators ADD COLUMN rotated_at TEXT")

    conn.commit()
