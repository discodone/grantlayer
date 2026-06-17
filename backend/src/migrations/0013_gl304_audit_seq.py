"""Add stable BIGSERIAL tiebreak column to audit_events.

Replaces ctid (PostgreSQL) and rowid (SQLite) with a portable seq column
that provides stable insertion-order tiebreaking for the hash-chain and
enables cursor-based pagination on the /v1/audit-events endpoint.

- SQLite:    seq INTEGER, backfilled with rowid values
- PostgreSQL: seq BIGINT DEFAULT nextval(...), backfilled via sequence
"""

version = "0013_gl304_audit_seq"

_SEQUENCE_NAME = "audit_events_seq_seq"


def _backend(conn) -> str:
    return getattr(conn, "backend", "sqlite")


def _column_exists(conn, table: str, column: str) -> bool:
    if _backend(conn) == "postgres":
        row = conn.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = %s",
            (table, column),
        ).fetchone()
        return row is not None
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def apply(conn) -> None:
    if _column_exists(conn, "audit_events", "seq"):
        return

    backend = _backend(conn)

    if backend == "postgres":
        conn.execute(
            f"CREATE SEQUENCE IF NOT EXISTS {_SEQUENCE_NAME} "
            "START WITH 1 INCREMENT BY 1"
        )
        conn.execute(
            f"ALTER TABLE audit_events ADD COLUMN seq BIGINT "
            f"DEFAULT nextval('{_SEQUENCE_NAME}')"
        )
        # Backfill existing rows in insertion order (ctid is stable within a
        # transaction before any vacuums; order_seq subquery avoids ordering by
        # ctid after this migration runs).
        conn.execute(
            """
            UPDATE audit_events ae
            SET seq = sub.rn
            FROM (
                SELECT id, row_number() OVER (ORDER BY timestamp ASC, ctid ASC) AS rn
                FROM audit_events
            ) sub
            WHERE ae.id = sub.id AND ae.seq IS NULL
            """
        )
        # Advance the sequence past the max backfill value so future inserts
        # don't collide.
        conn.execute(
            f"SELECT setval('{_SEQUENCE_NAME}', COALESCE((SELECT MAX(seq) FROM audit_events), 0) + 1)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_events_seq ON audit_events(seq)"
        )
    else:
        conn.execute("ALTER TABLE audit_events ADD COLUMN seq INTEGER")
        # Use rowid as the initial seq for all existing rows.
        conn.execute("UPDATE audit_events SET seq = rowid WHERE seq IS NULL")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_events_seq ON audit_events(seq)"
        )

    conn.commit()
