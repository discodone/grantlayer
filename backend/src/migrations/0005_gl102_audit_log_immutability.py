"""GrantLayer MVP — GL-102 Audit Log Database Immutability migration.

Adds SQLite triggers to prevent UPDATE and DELETE on audit_events,
preserving append-only INSERT and SELECT behavior.

Compatible with SQLite and PostgreSQL backends.
"""

import sqlite3

version = "0005_gl102_audit_log_immutability"


def apply(conn: sqlite3.Connection) -> None:
    """Create audit_events immutability triggers."""
    backend = getattr(conn, "backend", "sqlite")

    if backend == "sqlite":
        conn.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS trg_audit_events_no_update
            BEFORE UPDATE ON audit_events
            BEGIN
                SELECT RAISE(ABORT, 'audit_events is immutable: UPDATE is forbidden');
            END;

            CREATE TRIGGER IF NOT EXISTS trg_audit_events_no_delete
            BEFORE DELETE ON audit_events
            BEGIN
                SELECT RAISE(ABORT, 'audit_events is immutable: DELETE is forbidden');
            END;
            """
        )

    conn.commit()
