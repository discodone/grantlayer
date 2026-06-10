"""GrantLayer MVP — Audit Hash Chain / Tamper Evidence Migration.

Adds row_hash and prev_hash columns to audit_events to support
cryptographic chaining of audit entries.

Compatible with SQLite and PostgreSQL backends.
"""

version = "0006_gl103_audit_hash_chain"


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
    """Add row_hash and prev_hash columns to audit_events."""
    for column, col_type in (
        ("row_hash", "TEXT"),
        ("prev_hash", "TEXT"),
    ):
        if not _column_exists(conn, "audit_events", column):
            conn.execute(f"ALTER TABLE audit_events ADD COLUMN {column} {col_type}")
    conn.commit()
