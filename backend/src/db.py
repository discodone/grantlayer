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
    with get_conn() as conn:
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
        """)
