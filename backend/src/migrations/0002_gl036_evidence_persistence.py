"""GrantLayer MVP — GL-036 Evidence Persistence Schema Migration.

Adds evidence_archives and evidence_hashes tables for durable bundle storage.
Supports both SQLite and PostgreSQL via the _ConnectionWrapper interface.
"""

version = "0002_gl036_evidence_persistence"


def apply(conn) -> None:
    """Create evidence archive tables and indexes."""
    conn.executescript(
        """
        -- Evidence archives: immutable storage for evidence bundles
        CREATE TABLE IF NOT EXISTS evidence_archives (
            id              TEXT PRIMARY KEY,
            evidence_hash   TEXT NOT NULL,
            canonical_version TEXT NOT NULL,
            hash_algorithm  TEXT NOT NULL,
            bundle_json     TEXT NOT NULL,
            execution_id    TEXT NOT NULL UNIQUE,
            grant_id        TEXT,
            grant_request_id TEXT,
            created_at      TEXT NOT NULL,
            stored_by       TEXT
        );

        -- Evidence hashes: fast hash lookup and deduplication
        CREATE TABLE IF NOT EXISTS evidence_hashes (
            evidence_hash   TEXT PRIMARY KEY,
            archive_id      TEXT NOT NULL,
            created_at      TEXT NOT NULL
        );

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_evidence_archives_grant_id
            ON evidence_archives (grant_id);
        CREATE INDEX IF NOT EXISTS idx_evidence_archives_execution_id
            ON evidence_archives (execution_id);
        CREATE INDEX IF NOT EXISTS idx_evidence_archives_created_at
            ON evidence_archives (created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_evidence_hashes_archive_id
            ON evidence_hashes (archive_id);
        """
    )
    conn.commit()
