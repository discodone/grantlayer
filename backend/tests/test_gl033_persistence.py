"""GL-033 — Persistent Storage & Deployment Readiness Baseline tests.

Covers:
1. Migration runner creates schema_migrations and marks baseline on fresh DB
2. Migration runner validates and marks baseline on existing legacy DB
3. GRANTLAYER_DATABASE_URL precedence over GRANTLAYER_DB
4. SQLite URL parsing supports common formats
5. PostgreSQL URL parsing safely rejects with clear message
6. DB health probes remain unchanged from GL-032
"""

import os
import sys
import json
import unittest
import tempfile
import sqlite3
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestGL033Persistence(unittest.TestCase):
    """GL-033 persistent storage baseline tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        self._orig_url = os.environ.get("GRANTLAYER_DATABASE_URL")

        # Default to tmp file for most tests
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name
        if self._orig_url is not None:
            os.environ.pop("GRANTLAYER_DATABASE_URL", None)

        import src.db as db_mod
        importlib.reload(db_mod)
        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)
        if self._orig_url is not None:
            os.environ["GRANTLAYER_DATABASE_URL"] = self._orig_url
        else:
            os.environ.pop("GRANTLAYER_DATABASE_URL", None)

    # ──────────────────────────────────────────────
    # 1. Fresh DB: baseline migration applied
    # ──────────────────────────────────────────────
    def test_fresh_db_applies_baseline(self):
        self.db_mod.init_db()
        conn = self.db_mod.get_conn()
        try:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            self.assertIn("grants", tables)
            self.assertIn("audit_events", tables)
            self.assertIn("challenges", tables)
            self.assertIn("operators", tables)
            self.assertIn("grant_requests", tables)
            self.assertIn("grant_executions", tables)
            self.assertIn("schema_migrations", tables)

            versions = [r[0] for r in conn.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()]
            self.assertIn("0001_gl032_baseline", versions)
        finally:
            conn.close()

    # ──────────────────────────────────────────────
    # 2. Existing legacy DB: baseline validated and marked applied
    # ──────────────────────────────────────────────
    def test_existing_db_validates_baseline(self):
        # Manually create an old-style GL-032 schema without schema_migrations
        conn = sqlite3.connect(self.tmp_db.name)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        # Only create partial but enough tables to pass validation
        conn.executescript("""
            CREATE TABLE grants (
                id TEXT PRIMARY KEY, subject_id TEXT NOT NULL, role TEXT NOT NULL,
                action TEXT NOT NULL, resource TEXT NOT NULL, valid_from TEXT NOT NULL,
                valid_until TEXT NOT NULL, created_by TEXT NOT NULL, reason TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0, revoked_by TEXT, revoked_reason TEXT,
                revoked_at TEXT, created_at TEXT NOT NULL,
                signature TEXT, signing_key_id TEXT, payload_hash TEXT,
                max_uses INTEGER, use_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE audit_events (
                id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, subject_id TEXT NOT NULL,
                role TEXT NOT NULL, action TEXT NOT NULL, resource TEXT NOT NULL,
                approved INTEGER NOT NULL, reason TEXT NOT NULL, matched_grant_id TEXT,
                challenge_id TEXT DEFAULT NULL, challenge_present INTEGER DEFAULT 0,
                challenge_result TEXT DEFAULT 'legacy_mode',
                grant_signature_result TEXT DEFAULT 'not_checked'
            );
            CREATE TABLE challenges (
                id TEXT PRIMARY KEY, subject_id TEXT NOT NULL, action TEXT NOT NULL,
                resource TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                used_at TEXT, status TEXT NOT NULL DEFAULT 'active'
            );
            CREATE TABLE operators (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
                token_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE grant_requests (
                id TEXT PRIMARY KEY, subject_id TEXT NOT NULL, role TEXT NOT NULL,
                action TEXT NOT NULL, resource TEXT NOT NULL, valid_from TEXT NOT NULL,
                valid_until TEXT NOT NULL, requested_by TEXT NOT NULL, reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'requested', approved_by TEXT, approved_at TEXT,
                denied_by TEXT, denied_at TEXT, denial_reason TEXT,
                revoked_by TEXT, revoked_at TEXT, revoked_reason TEXT,
                grant_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE grant_executions (
                id TEXT PRIMARY KEY, grant_id TEXT, grant_request_id TEXT,
                operator_id TEXT, action TEXT NOT NULL, resource TEXT NOT NULL,
                challenge_id TEXT, challenge_result TEXT, policy_result TEXT NOT NULL,
                result TEXT NOT NULL, error_code TEXT, executed_at TEXT NOT NULL,
                audit_event_id TEXT, metadata_json TEXT
            );
            CREATE INDEX idx_grant_executions_grant_id ON grant_executions (grant_id);
            CREATE INDEX idx_grant_executions_grant_request_id ON grant_executions (grant_request_id);
            CREATE INDEX idx_grant_executions_operator_id ON grant_executions (operator_id);
            CREATE INDEX idx_grant_executions_executed_at ON grant_executions (executed_at DESC);
        """)
        conn.commit()
        conn.close()

        # Now init_db should validate and mark baseline applied
        self.db_mod.init_db()
        conn = self.db_mod.get_conn()
        try:
            versions = [r[0] for r in conn.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()]
            self.assertIn("0001_gl032_baseline", versions)
        finally:
            conn.close()

    # ──────────────────────────────────────────────
    # 3. GRANTLAYER_DATABASE_URL precedence over GRANTLAYER_DB
    # ──────────────────────────────────────────────
    def test_database_url_precedence_over_db(self):
        tmp2 = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        try:
            os.environ["GRANTLAYER_DATABASE_URL"] = f"sqlite://{tmp2.name}"
            os.environ["GRANTLAYER_DB"] = self.tmp_db.name
            importlib.reload(self.db_mod)
            self.assertEqual(self.db_mod.DB_PATH, tmp2.name)
        finally:
            os.unlink(tmp2.name)

    # ──────────────────────────────────────────────
    # 4. SQLite URL parsing supports common formats
    # ──────────────────────────────────────────────
    def test_sqlite_url_parsing(self):
        paths = {
            "sqlite:///absolute/path.db": "/absolute/path.db",
            "sqlite://relative/path.db": "relative/path.db",
            "sqlite:relative/path.db": "relative/path.db",
            "sqlite::memory:": ":memory:",
            "sqlite:///:memory:": ":memory:",
        }
        for url, expected in paths.items():
            with self.subTest(url=url):
                self.assertEqual(self.db_mod._parse_database_url(url), expected)

    # ──────────────────────────────────────────────
    # 5. PostgreSQL URL parsing safely rejects
    # ──────────────────────────────────────────────
    def test_postgresql_url_rejected(self):
        for url in ["postgres://localhost/db", "postgresql://localhost/db"]:
            with self.subTest(url=url):
                with self.assertRaises(RuntimeError) as ctx:
                    self.db_mod._parse_database_url(url)
                self.assertIn("not supported yet", str(ctx.exception))

    # ──────────────────────────────────────────────
    # 6. GL-032 health probes are intact
    # ──────────────────────────────────────────────
    def test_health_probes_intact(self):
        self.db_mod.init_db()
        health = self.db_mod.get_db_health()
        self.assertIn("dbConnected", health)
        self.assertIn("dbWritable", health)
        self.assertIn("dbFilePresent", health)
        self.assertIn("dbDirectoryWritable", health)
        self.assertIn("dbSizeBytes", health)
        self.assertIn("journalMode", health)
        self.assertIn("dbPathKind", health)

        self.assertTrue(health["dbConnected"])
        self.assertTrue(health["dbWritable"])
        self.assertEqual(health["journalMode"], "wal")
        self.assertEqual(health["dbPathKind"], "file")

    # ──────────────────────────────────────────────
    # 7. dbConfigured reflects DATABASE_URL
    # ──────────────────────────────────────────────
    def test_db_configured_reflects_database_url(self):
        os.environ.pop("GRANTLAYER_DB", None)
        os.environ.pop("GRANTLAYER_DATABASE_URL", None)
        import src.config as config_mod
        importlib.reload(config_mod)
        # Neither set; default is used but dbConfigured should be False
        self.assertFalse(bool(config_mod.GRANTLAYER_DB or config_mod.GRANTLAYER_DATABASE_URL))

        os.environ["GRANTLAYER_DATABASE_URL"] = "sqlite:///:memory:"
        importlib.reload(config_mod)
        self.assertTrue(bool(config_mod.GRANTLAYER_DB or config_mod.GRANTLAYER_DATABASE_URL))


if __name__ == "__main__":
    unittest.main(verbosity=2)
