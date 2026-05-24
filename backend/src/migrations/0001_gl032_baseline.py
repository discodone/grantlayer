"""GrantLayer MVP — Baseline migration representing the full GL-032 schema.

When applied to a fresh database this migration creates every table,
column, and index that existed at the end of GL-032.
"""

import sqlite3

version = "0001_gl032_baseline"


def apply(conn: sqlite3.Connection) -> None:
    """Create the complete GL-032 schema on a fresh SQLite database."""
    conn.executescript(
        """
        -- Grants
        CREATE TABLE IF NOT EXISTS grants (
            id          TEXT PRIMARY KEY,
            subject_id  TEXT NOT NULL,
            role        TEXT NOT NULL,
            action      TEXT NOT NULL,
            resource    TEXT NOT NULL,
            valid_from  TEXT NOT NULL,
            valid_until TEXT NOT NULL,
            created_by  TEXT NOT NULL,
            reason      TEXT NOT NULL,
            revoked     INTEGER NOT NULL DEFAULT 0,
            revoked_by  TEXT,
            revoked_reason TEXT,
            revoked_at  TEXT,
            created_at  TEXT NOT NULL,
            signature   TEXT,
            signing_key_id TEXT,
            payload_hash TEXT,
            max_uses    INTEGER,
            use_count   INTEGER NOT NULL DEFAULT 0
        );

        -- Audit events
        CREATE TABLE IF NOT EXISTS audit_events (
            id               TEXT PRIMARY KEY,
            timestamp        TEXT NOT NULL,
            subject_id       TEXT NOT NULL,
            role             TEXT NOT NULL,
            action           TEXT NOT NULL,
            resource         TEXT NOT NULL,
            approved         INTEGER NOT NULL,
            reason           TEXT NOT NULL,
            matched_grant_id TEXT,
            challenge_id     TEXT DEFAULT NULL,
            challenge_present INTEGER DEFAULT 0,
            challenge_result TEXT DEFAULT 'legacy_mode',
            grant_signature_result TEXT DEFAULT 'not_checked',
            row_hash         TEXT,
            prev_hash        TEXT
        );

        -- Challenges
        CREATE TABLE IF NOT EXISTS challenges (
            id         TEXT PRIMARY KEY,
            subject_id TEXT NOT NULL,
            action     TEXT NOT NULL,
            resource   TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_at    TEXT,
            status     TEXT NOT NULL DEFAULT 'active'
        );

        -- Operators
        CREATE TABLE IF NOT EXISTS operators (
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            role       TEXT NOT NULL,
            token_hash TEXT NOT NULL,
            active     INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        -- Grant requests
        CREATE TABLE IF NOT EXISTS grant_requests (
            id              TEXT PRIMARY KEY,
            subject_id      TEXT NOT NULL,
            role            TEXT NOT NULL,
            action          TEXT NOT NULL,
            resource        TEXT NOT NULL,
            valid_from      TEXT NOT NULL,
            valid_until     TEXT NOT NULL,
            requested_by    TEXT NOT NULL,
            reason          TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'requested',
            approved_by     TEXT,
            approved_at     TEXT,
            denied_by       TEXT,
            denied_at       TEXT,
            denial_reason   TEXT,
            revoked_by      TEXT,
            revoked_at      TEXT,
            revoked_reason  TEXT,
            grant_id        TEXT,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );

        -- Grant executions
        CREATE TABLE IF NOT EXISTS grant_executions (
            id              TEXT PRIMARY KEY,
            grant_id        TEXT,
            grant_request_id TEXT,
            operator_id     TEXT,
            action          TEXT NOT NULL,
            resource        TEXT NOT NULL,
            challenge_id    TEXT,
            challenge_result TEXT,
            policy_result   TEXT NOT NULL,
            result          TEXT NOT NULL,
            error_code      TEXT,
            executed_at     TEXT NOT NULL,
            audit_event_id  TEXT,
            metadata_json   TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_grant_executions_grant_id ON grant_executions (grant_id);
        CREATE INDEX IF NOT EXISTS idx_grant_executions_grant_request_id ON grant_executions (grant_request_id);
        CREATE INDEX IF NOT EXISTS idx_grant_executions_operator_id ON grant_executions (operator_id);
        CREATE INDEX IF NOT EXISTS idx_grant_executions_executed_at ON grant_executions (executed_at DESC);
        """
    )
    conn.commit()
