"""Runner refuses to execute against PostgreSQL — fail-closed at entry.

The file-based migration runner is frozen for local/SQLite development and test
only. Alembic is the authoritative provisioner for PostgreSQL. The runner must
never execute against a PostgreSQL database: doing so risks a partial or
divergent schema (its per-dialect SQL is unmaintained for Postgres).

This suite pins a hard guard at ``run_migrations`` entry: when the connection's
backend is ``postgres`` — which ``db.py`` sets from a ``postgres://`` or
``postgresql://`` URL scheme (either variant) — the runner raises immediately,
before it touches ``schema_migrations`` or reaches the legacy-baseline shortcut.
SQLite behaviour is unchanged.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest


class _PostgresSpyConn:
    """Stands in for a connection opened from a ``postgresql://`` URL.

    ``db.py`` resolves both ``postgres://`` and ``postgresql://`` schemes to
    ``backend == "postgres"`` on the connection wrapper, so ``backend`` is
    exactly the "URL scheme is postgresql (any variant)" signal the runner sees.
    Every ``execute``/``commit`` is fatal: if the runner reaches the database at
    all, the guard did not fire early enough.
    """

    backend = "postgres"

    def __init__(self) -> None:
        self.touched = False

    def execute(self, *args, **kwargs):
        self.touched = True
        raise AssertionError(
            "runner reached the database before the PostgreSQL guard fired"
        )

    def commit(self):
        self.touched = True
        raise AssertionError(
            "runner committed before the PostgreSQL guard fired"
        )


class TestRunnerPostgresGuard(unittest.TestCase):
    def setUp(self):
        from backend.src.migrations import runner

        self.runner = runner

    def test_run_migrations_refuses_postgres_before_touching_db(self):
        conn = _PostgresSpyConn()

        with self.assertRaises(RuntimeError) as ctx:
            self.runner.run_migrations(conn)

        # It must fail closed BEFORE any DB access: no schema_migrations table
        # creation, no baseline shortcut, no marking.
        self.assertFalse(
            conn.touched,
            "runner must raise before executing anything against PostgreSQL",
        )

        msg = str(ctx.exception)
        # The operator must be pointed at the authoritative Alembic path.
        self.assertIn("PostgreSQL", msg)
        self.assertIn("Alembic", msg)
        self.assertIn("make migrate", msg)
        self.assertIn("docs/architecture.md", msg)

    def test_sqlite_is_unaffected_by_the_guard(self):
        # A real SQLite connection (backend defaults to "sqlite") must still
        # provision the full schema exactly as before.
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        f.close()
        conn = sqlite3.connect(f.name)

        self.runner.run_migrations(conn)

        discovered = {v for v, _ in self.runner._discovery()}
        self.assertEqual(set(self.runner.get_applied_versions(conn)), discovered)
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("grants", tables)
        self.assertIn("audit_events", tables)


if __name__ == "__main__":
    unittest.main()
