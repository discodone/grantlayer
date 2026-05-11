"""GrantLayer MVP — GL-037-A Provenance Event Persistence migration.

Creates the provenance_events table for append-only event tracing.
Compatible with SQLite and PostgreSQL.
"""

import sqlite3

version = "0004_gl037a_provenance_events"


def apply(conn: sqlite3.Connection) -> None:
    """Create the provenance_events table."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS provenance_events (
            id                 TEXT PRIMARY KEY,
            event_type         TEXT NOT NULL,
            actor_type         TEXT NOT NULL,
            actor_id           TEXT NOT NULL,
            action             TEXT NOT NULL,
            occurred_at        TEXT NOT NULL,
            created_at         TEXT NOT NULL,
            resource_type      TEXT,
            resource_id        TEXT,
            execution_id       TEXT,
            grant_id           TEXT,
            evidence_hash      TEXT,
            verification_status TEXT,
            metadata_json      TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_provenance_events_execution_id
            ON provenance_events (execution_id);
        CREATE INDEX IF NOT EXISTS idx_provenance_events_grant_id
            ON provenance_events (grant_id);
        CREATE INDEX IF NOT EXISTS idx_provenance_events_actor_type
            ON provenance_events (actor_type);
        CREATE INDEX IF NOT EXISTS idx_provenance_events_occurred_at
            ON provenance_events (occurred_at);
        CREATE INDEX IF NOT EXISTS idx_provenance_events_resource_type_resource_id
            ON provenance_events (resource_type, resource_id);
        """
    )
    conn.commit()
