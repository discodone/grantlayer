"""Runner refuses to baseline-mark an Alembic-provisioned database.

The runner has a legacy-baseline shortcut: if the application schema already
exists (``grants`` table) but the runner's ``schema_migrations`` tracker is
empty, it marks every discovered migration as applied WITHOUT executing it.

On a database that Alembic provisioned, that shortcut is a silent corruption:
it records the runner's migrations as done while their effects are absent
(the runner adds objects Alembic's revisions do not). This suite pins the
fail-closed guard: the shortcut must refuse — loudly — when an
``alembic_version`` table is present, and must be otherwise unchanged.

Guard truth table (only the first case raises):
  grants + empty tracker + alembic_version   -> RAISE (two systems collide)
  grants + empty tracker + no alembic_version -> baseline-mark (legacy runner DB)
  no grants (fresh/empty DB)                  -> migrate normally
  populated tracker (+ alembic_version)       -> untouched (shortcut not reached)
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest


def _fresh_conn() -> sqlite3.Connection:
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    return sqlite3.connect(f.name)


class TestRunnerAlembicCollisionGuard(unittest.TestCase):
    def setUp(self):
        from backend.src.migrations import runner

        self.runner = runner
        self.conn = _fresh_conn()

    def _applied(self):
        return set(self.runner.get_applied_versions(self.conn))

    # 1. The collision case must raise and mark nothing.
    def test_guard_raises_on_alembic_provisioned_db(self):
        # Simulate an Alembic-provisioned DB: schema present + alembic_version,
        # but the runner's tracker was never populated.
        self.conn.execute("CREATE TABLE grants (id TEXT PRIMARY KEY)")
        self.conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        self.conn.execute("INSERT INTO alembic_version VALUES ('c3d4e5f6a7b8')")
        self.conn.commit()

        with self.assertRaises(RuntimeError) as ctx:
            self.runner.run_migrations(self.conn)

        msg = str(ctx.exception)
        # The operator must be told what happened and what to do.
        self.assertIn("Two migration systems detected", msg)
        self.assertIn("Alembic-provisioned database", msg)
        self.assertIn("Make Alembic authoritative", msg)
        self.assertIn("Provision this database with the runner", msg)

        # Refused: nothing was marked applied.
        self.assertEqual(self._applied(), set())

    # 2. A genuine legacy runner DB (no Alembic) must still be baseline-marked.
    def test_legacy_db_without_alembic_is_baseline_marked(self):
        # Provision fully via the runner, then drop the tracker to simulate a
        # pre-tracker legacy DB. No alembic_version is ever created.
        self.runner.run_migrations(self.conn)
        self.conn.execute("DROP TABLE schema_migrations")
        self.conn.commit()

        # Must NOT raise, and must re-mark every discovered version.
        self.runner.run_migrations(self.conn)
        discovered = {v for v, _ in self.runner._discovery()}
        self.assertEqual(self._applied(), discovered)

    # 3. A fresh/empty DB (no grants) must migrate normally regardless of the guard.
    def test_fresh_empty_db_migrates_normally(self):
        self.runner.run_migrations(self.conn)
        discovered = {v for v, _ in self.runner._discovery()}
        self.assertEqual(self._applied(), discovered)
        tables = {
            r[0]
            for r in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("grants", tables)
        self.assertIn("audit_events", tables)

    # 4. A populated tracker must be untouched even when alembic_version coexists —
    #    the guard fires only inside the empty-tracker shortcut, never on every DB
    #    that happens to carry an alembic_version table.
    def test_populated_tracker_with_alembic_version_is_untouched(self):
        self.runner.run_migrations(self.conn)
        before = self._applied()
        # Someone later stamps Alembic alongside the runner-owned schema.
        self.conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        self.conn.execute("INSERT INTO alembic_version VALUES ('c3d4e5f6a7b8')")
        self.conn.commit()

        # Tracker is populated -> shortcut not reached -> no raise, no change.
        self.runner.run_migrations(self.conn)
        self.assertEqual(self._applied(), before)


if __name__ == "__main__":
    unittest.main()
