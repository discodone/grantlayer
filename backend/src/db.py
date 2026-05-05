"""GrantLayer MVP — SQLite database setup."""

import sqlite3
import os

DB_PATH = os.environ.get("GRANTLAYER_DB", os.path.join(os.path.dirname(__file__), "../../data/grantlayer.db"))


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = get_conn()
    try:
        conn.executescript("""
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
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                id               TEXT PRIMARY KEY,
                timestamp        TEXT NOT NULL,
                subject_id       TEXT NOT NULL,
                role             TEXT NOT NULL,
                action           TEXT NOT NULL,
                resource         TEXT NOT NULL,
                approved         INTEGER NOT NULL,
                reason           TEXT NOT NULL,
                matched_grant_id TEXT
            );

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
        """)
        # Migrate: add challenge columns to audit_events if they don't exist yet
        for col, ddl in [
            ("challenge_id", "TEXT DEFAULT NULL"),
            ("challenge_present", "INTEGER DEFAULT 0"),
            ("challenge_result", "TEXT DEFAULT 'legacy_mode'"),
        ]:
            try:
                conn.execute(
                    f"ALTER TABLE audit_events ADD COLUMN {col} {ddl}"
                )
                conn.commit()
            except Exception:
                pass  # column already exists

        # Migrate: add signature columns to grants (Sprint 2B)
        for col, ddl in [
            ("signature", "TEXT"),
            ("signing_key_id", "TEXT"),
            ("payload_hash", "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE grants ADD COLUMN {col} {ddl}")
                conn.commit()
            except Exception:
                pass  # column already exists

        # Migrate: add grant_signature_result to audit_events (Sprint 2B)
        try:
            conn.execute(
                "ALTER TABLE audit_events ADD COLUMN grant_signature_result "
                "TEXT DEFAULT 'not_checked'"
            )
            conn.commit()
        except Exception:
            pass  # column already exists

        # GL-021: Initialize operators table + bootstrap
        from . import operators
        operators.ensure_operators_table()
        
        # GL-022: Initialize grant_requests table
        conn.executescript("""
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
        """)

        # GL-023: Initialize grant_executions table
        conn.executescript("""
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
        """)
    finally:
        conn.close()
