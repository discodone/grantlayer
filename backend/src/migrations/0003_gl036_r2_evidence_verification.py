"""GrantLayer MVP — Evidence Verification Core Migration.

Adds last_verified_at and last_verification_status to evidence_archives
to track verification results without mutating the immutable bundle data.
"""

version = "0003_gl036_r2_evidence_verification"


def apply(conn) -> None:
    """Add verification tracking columns to evidence_archives."""
    if not hasattr(conn, "backend"):
        backend = "sqlite"
    else:
        backend = conn.backend

    # SQLite: ALTER TABLE ADD COLUMN (nullable, no default)
    # PostgreSQL: same syntax for nullable columns
    def _add_column(table: str, column: str, col_type: str) -> None:
        if backend == "postgres":
            check = conn.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
                """,
                (table, column),
            ).fetchone()
        else:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            check = any(r[1] == column for r in rows)

        if not check:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

    _add_column("evidence_archives", "last_verified_at", "TEXT")
    _add_column("evidence_archives", "last_verification_status", "TEXT")
    conn.commit()
