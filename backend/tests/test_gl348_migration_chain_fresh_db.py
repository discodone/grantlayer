"""GL-348 — Migration chain builds the full schema from an empty database.

The migration modules report 0% coverage in the suite because the shared dev DB
is already migrated, so run_migrations is a no-op in nearly every test. This test
runs the entire forward migration chain against a brand-new empty SQLite database
and asserts the resulting schema — exercising every migration's apply() DDL and
catching a migration that fails, is skipped, or produces the wrong schema.

This is real coverage: a broken or reordered migration fails here.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest


def _fresh_conn() -> sqlite3.Connection:
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    return sqlite3.connect(f.name)


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


class TestMigrationChainFreshDb(unittest.TestCase):
    def setUp(self):
        from backend.src.migrations import runner
        self.runner = runner
        self.conn = _fresh_conn()

    def test_run_migrations_applies_every_discovered_version(self):
        """A fresh DB must end with every discovered migration marked applied."""
        discovered = [v for v, _ in self.runner._discovery()]
        self.assertTrue(discovered, "no migrations discovered")
        self.runner.run_migrations(self.conn)
        applied = set(self.runner.get_applied_versions(self.conn))
        missing = set(discovered) - applied
        self.assertEqual(missing, set(), f"migrations not applied on fresh DB: {sorted(missing)}")

    def test_fresh_schema_contains_core_tables(self):
        """The forward chain must create the full core schema from zero."""
        self.runner.run_migrations(self.conn)
        tables = _tables(self.conn)
        for required in (
            "grants", "audit_events", "operators", "grant_requests",
            "grant_executions", "workspaces", "workspace_members", "api_keys",
            "grant_templates", "webhook_subscriptions", "webhook_deliveries",
            "schema_migrations",
        ):
            self.assertIn(required, tables, f"migration chain did not create {required}")

    def test_fresh_schema_has_evolved_columns(self):
        """Columns added by later migrations must be present after the full chain."""
        self.runner.run_migrations(self.conn)
        # operator token lookup/expiry/rotation + tenant columns
        op_cols = _columns(self.conn, "operators")
        for c in ("token_lookup_hash", "expires_at", "rotated_at", "tenant_id", "workspace_id"):
            self.assertIn(c, op_cols, f"operators missing evolved column {c}")
        # workspace plan tier
        ws_cols = _columns(self.conn, "workspaces")
        for c in ("plan_tier", "rate_limit_override", "tenant_id"):
            self.assertIn(c, ws_cols, f"workspaces missing evolved column {c}")
        # audit sequence tiebreak column
        self.assertIn("seq", _columns(self.conn, "audit_events"), "audit_events missing seq column")

    def test_run_migrations_is_idempotent(self):
        """Re-running on an already-migrated DB applies nothing and stays clean."""
        self.runner.run_migrations(self.conn)
        first = set(self.runner.get_applied_versions(self.conn))
        # No pending after a full run.
        self.assertEqual(self.runner.list_pending_migrations(self.conn), [])
        # Second run is a no-op and must not raise.
        self.runner.run_migrations(self.conn)
        self.assertEqual(set(self.runner.get_applied_versions(self.conn)), first)

    def test_legacy_db_without_tracker_is_marked_applied(self):
        """A pre-migration-runner DB (grants table, no schema_migrations) is
        baselined: all versions marked applied without re-running CREATE DDL."""
        # Build the full schema first, then drop the tracker to simulate a legacy DB.
        self.runner.run_migrations(self.conn)
        self.conn.execute("DROP TABLE schema_migrations")
        self.conn.commit()
        self.runner.run_migrations(self.conn)
        applied = set(self.runner.get_applied_versions(self.conn))
        discovered = {v for v, _ in self.runner._discovery()}
        self.assertEqual(applied, discovered)


if __name__ == "__main__":
    unittest.main()
