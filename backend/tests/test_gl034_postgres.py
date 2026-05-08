"""GL-034 — PostgreSQL Support via Minimal Connection Factory & Bounded CRUD Query Helper Refactor.

Covers:
1. Placeholder scanner correctly translates ? to %s outside literals/comments/identifiers
2. Connection factory parses postgres:// and postgresql:// URLs
3. CRUD helpers (execute, query_one, query_all, executemany) work with SQLite
4. Lazy-import error when PostgreSQL is configured but psycopg2 is missing
5. Connection wrapper exposes backend attribute
6. Migration runner detects backend correctly
"""

import os
import sys
import unittest
import tempfile
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestPlaceholderScanner(unittest.TestCase):
    """GL-034 placeholder scanner correctness."""

    def setUp(self):
        from src.db import _translate_placeholders
        self.translate = _translate_placeholders

    def test_simple_placeholders(self):
        sql, count = self.translate("SELECT * FROM t WHERE id = ? AND name = ?")
        self.assertEqual(sql, "SELECT * FROM t WHERE id = %s AND name = %s")
        self.assertEqual(count, 2)

    def test_no_placeholders(self):
        sql, count = self.translate("SELECT * FROM t")
        self.assertEqual(sql, "SELECT * FROM t")
        self.assertEqual(count, 0)

    def test_placeholder_in_string_literal_ignored(self):
        sql, count = self.translate("SELECT * FROM t WHERE name = '?' AND id = ?")
        self.assertEqual(sql, "SELECT * FROM t WHERE name = '?' AND id = %s")
        self.assertEqual(count, 1)

    def test_placeholder_in_doubled_quote_ignored(self):
        sql, count = self.translate("SELECT * FROM t WHERE name = 'it''s ?' AND id = ?")
        self.assertEqual(sql, "SELECT * FROM t WHERE name = 'it''s ?' AND id = %s")
        self.assertEqual(count, 1)

    def test_placeholder_in_double_quoted_identifier_ignored(self):
        sql, count = self.translate('SELECT * FROM "?" WHERE id = ?')
        self.assertEqual(sql, 'SELECT * FROM "?" WHERE id = %s')
        self.assertEqual(count, 1)

    def test_placeholder_in_line_comment_ignored(self):
        sql, count = self.translate("SELECT * FROM t WHERE id = ? -- comment with ?\nAND x = ?")
        self.assertEqual(sql, "SELECT * FROM t WHERE id = %s -- comment with ?\nAND x = %s")
        self.assertEqual(count, 2)

    def test_placeholder_in_block_comment_ignored(self):
        sql, count = self.translate("SELECT * FROM t WHERE id = ? /* comment ? */ AND x = ?")
        self.assertEqual(sql, "SELECT * FROM t WHERE id = %s /* comment ? */ AND x = %s")
        self.assertEqual(count, 2)

    def test_unclosed_string_literal(self):
        sql, count = self.translate("SELECT * FROM t WHERE name = '? AND id = ?")
        # The ? after the unclosed string is still inside the string
        self.assertIn("'", sql)
        self.assertEqual(count, 0)

    def test_mixed_comments_and_strings(self):
        sql, count = self.translate(
            "SELECT * FROM t WHERE id = ? /* block ? */ AND name = '?' -- line ?\nAND x = ?"
        )
        expected = (
            "SELECT * FROM t WHERE id = %s /* block ? */ AND name = '?' -- line ?\nAND x = %s"
        )
        self.assertEqual(sql, expected)
        self.assertEqual(count, 2)


class TestConnectionFactory(unittest.TestCase):
    """GL-034 connection factory URL parsing."""

    def setUp(self):
        from src.db import _parse_database_url
        self.parse = _parse_database_url

    def test_sqlite_absolute_path(self):
        backend, path = self.parse("sqlite:///absolute/path.db")
        self.assertEqual(backend, "sqlite")
        self.assertEqual(path, "/absolute/path.db")

    def test_sqlite_relative_path(self):
        backend, path = self.parse("sqlite://relative/path.db")
        self.assertEqual(backend, "sqlite")
        self.assertEqual(path, "relative/path.db")

    def test_sqlite_colon_prefix(self):
        backend, path = self.parse("sqlite:relative/path.db")
        self.assertEqual(backend, "sqlite")
        self.assertEqual(path, "relative/path.db")

    def test_sqlite_memory(self):
        for url in ["sqlite::memory:", "sqlite:///:memory:"]:
            backend, path = self.parse(url)
            self.assertEqual(backend, "sqlite")
            self.assertEqual(path, ":memory:")

    def test_postgres_url(self):
        backend, dsn = self.parse("postgres://user:pass@localhost/db")
        self.assertEqual(backend, "postgres")
        self.assertEqual(dsn, "postgres://user:pass@localhost/db")

    def test_postgresql_url(self):
        backend, dsn = self.parse("postgresql://user:pass@localhost/db")
        self.assertEqual(backend, "postgres")
        self.assertEqual(dsn, "postgresql://user:pass@localhost/db")

    def test_unsupported_scheme_raises(self):
        with self.assertRaises(RuntimeError) as ctx:
            self.parse("mysql://localhost/db")
        self.assertIn("Unsupported", str(ctx.exception))


class TestCRUDHelpersSQLite(unittest.TestCase):
    """GL-034 bounded CRUD helpers on SQLite."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        self._orig_url = os.environ.get("GRANTLAYER_DATABASE_URL")

        os.environ["GRANTLAYER_DB"] = self.tmp_db.name
        if self._orig_url is not None:
            os.environ.pop("GRANTLAYER_DATABASE_URL", None)

        import src.db as db_mod
        importlib.reload(db_mod)
        self.db = db_mod
        self.db.init_db()

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

    def test_execute_insert_and_return_rowcount(self):
        rowcount = self.db.execute(
            "INSERT INTO grants (id, subject_id, role, action, resource, valid_from, valid_until, created_by, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("g1", "s1", "admin", "read", "r1", "2024-01-01", "2025-01-01", "creator", "test", "2024-01-01"),
        )
        self.assertEqual(rowcount, 1)

    def test_query_one_returns_dict(self):
        self.db.execute(
            "INSERT INTO grants (id, subject_id, role, action, resource, valid_from, valid_until, created_by, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("g2", "s2", "admin", "read", "r1", "2024-01-01", "2025-01-01", "creator", "test", "2024-01-01"),
        )
        row = self.db.query_one("SELECT * FROM grants WHERE id = ?", ("g2",))
        self.assertIsNotNone(row)
        self.assertIsInstance(row, dict)
        self.assertEqual(row["id"], "g2")
        self.assertEqual(row["subject_id"], "s2")

    def test_query_one_returns_none_for_missing(self):
        row = self.db.query_one("SELECT * FROM grants WHERE id = ?", ("missing",))
        self.assertIsNone(row)

    def test_query_all_returns_list_of_dicts(self):
        self.db.execute(
            "INSERT INTO grants (id, subject_id, role, action, resource, valid_from, valid_until, created_by, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("g3", "s3", "admin", "read", "r1", "2024-01-01", "2025-01-01", "creator", "test", "2024-01-01"),
        )
        self.db.execute(
            "INSERT INTO grants (id, subject_id, role, action, resource, valid_from, valid_until, created_by, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("g4", "s4", "admin", "read", "r1", "2024-01-01", "2025-01-01", "creator", "test", "2024-01-01"),
        )
        rows = self.db.query_all("SELECT * FROM grants WHERE subject_id IN (?, ?) ORDER BY id", ("s3", "s4"))
        self.assertEqual(len(rows), 2)
        self.assertIsInstance(rows[0], dict)
        self.assertEqual(rows[0]["id"], "g3")
        self.assertEqual(rows[1]["id"], "g4")

    def test_executemany_batch_update(self):
        self.db.execute(
            "INSERT INTO grants (id, subject_id, role, action, resource, valid_from, valid_until, created_by, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("g5", "s5", "admin", "read", "r1", "2024-01-01", "2025-01-01", "creator", "test", "2024-01-01"),
        )
        self.db.execute(
            "INSERT INTO grants (id, subject_id, role, action, resource, valid_from, valid_until, created_by, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("g6", "s6", "admin", "read", "r1", "2024-01-01", "2025-01-01", "creator", "test", "2024-01-01"),
        )
        rowcount = self.db.executemany(
            "UPDATE grants SET role = ? WHERE id = ?",
            [("updated", "g5"), ("updated", "g6")],
        )
        self.assertEqual(rowcount, 2)
        rows = self.db.query_all("SELECT role FROM grants WHERE id IN (?, ?)", ("g5", "g6"))
        self.assertTrue(all(r["role"] == "updated" for r in rows))

    def test_execute_update_returns_rowcount_zero(self):
        rowcount = self.db.execute(
            "UPDATE grants SET role = ? WHERE id = ?",
            ("nope", "nonexistent"),
        )
        self.assertEqual(rowcount, 0)


class TestConnectionWrapper(unittest.TestCase):
    """GL-034 connection wrapper backend exposure."""

    def test_wrapper_exposes_backend_sqlite(self):
        import sqlite3
        from src.db import _ConnectionWrapper
        conn = sqlite3.connect(":memory:")
        wrapper = _ConnectionWrapper(conn, "sqlite")
        self.assertEqual(wrapper.backend, "sqlite")
        wrapper.close()

    def test_wrapper_exposes_backend_postgres(self):
        import sqlite3
        from src.db import _ConnectionWrapper
        conn = sqlite3.connect(":memory:")
        wrapper = _ConnectionWrapper(conn, "postgres")
        self.assertEqual(wrapper.backend, "postgres")
        wrapper.close()


class TestPostgreSQLLazyImport(unittest.TestCase):
    """GL-034 PostgreSQL lazy import behavior when psycopg2 is missing."""

    def test_missing_psycopg2_raises_helpful_error(self):
        """When postgres:// is configured but psycopg2 is not installed,
        get_conn() must raise a RuntimeError with a helpful message."""
        # Simulate psycopg2 not being available by temporarily breaking the import
        import src.db as db_mod
        importlib.reload(db_mod)

        orig_backend = db_mod.DB_BACKEND
        orig_url = db_mod.DB_PATH_OR_URL

        try:
            db_mod.DB_BACKEND = "postgres"
            db_mod.DB_PATH_OR_URL = "postgres://localhost/test"
            with self.assertRaises(RuntimeError) as ctx:
                db_mod.get_conn()
            self.assertIn("psycopg2 is not installed", str(ctx.exception))
        finally:
            db_mod.DB_BACKEND = orig_backend
            db_mod.DB_PATH_OR_URL = orig_url


class TestMigrationRunnerBackendAwareness(unittest.TestCase):
    """GL-034 migration runner backend detection."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        self._orig_url = os.environ.get("GRANTLAYER_DATABASE_URL")

        os.environ["GRANTLAYER_DB"] = self.tmp_db.name
        if self._orig_url is not None:
            os.environ.pop("GRANTLAYER_DATABASE_URL", None)

        import src.db as db_mod
        importlib.reload(db_mod)
        self.db = db_mod

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

    def test_runner_detects_sqlite_backend(self):
        from src.migrations import runner
        conn = self.db.get_conn()
        try:
            self.assertEqual(runner._backend(conn), "sqlite")
        finally:
            conn.close()

    def test_runner_table_exists_sqlite(self):
        from src.migrations import runner
        conn = self.db.get_conn()
        try:
            runner._ensure_migrations_table(conn)
            self.assertTrue(runner._table_exists(conn, "schema_migrations"))
            self.assertFalse(runner._table_exists(conn, "nonexistent_table"))
        finally:
            conn.close()

    def test_runner_column_exists_sqlite(self):
        from src.migrations import runner
        conn = self.db.get_conn()
        try:
            runner._ensure_migrations_table(conn)
            self.assertTrue(runner._column_exists(conn, "schema_migrations", "version"))
            self.assertFalse(runner._column_exists(conn, "schema_migrations", "nope"))
        finally:
            conn.close()


class TestHealthProbesBackendAware(unittest.TestCase):
    """GL-034 health probes reflect backend correctly."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        self._orig_url = os.environ.get("GRANTLAYER_DATABASE_URL")

        os.environ["GRANTLAYER_DB"] = self.tmp_db.name
        if self._orig_url is not None:
            os.environ.pop("GRANTLAYER_DATABASE_URL", None)

        import src.db as db_mod
        importlib.reload(db_mod)
        self.db = db_mod
        self.db.init_db()

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

    def test_health_sqlite_file_kind(self):
        health = self.db.get_db_health()
        self.assertEqual(health["dbPathKind"], "file")
        self.assertTrue(health["dbConnected"])
        self.assertTrue(health["dbWritable"])
        self.assertTrue(health["dbFilePresent"])
        self.assertIsNotNone(health["dbSizeBytes"])
        self.assertEqual(health["journalMode"], "wal")

    def test_health_memory_kind(self):
        orig_path = self.db.DB_PATH_OR_URL
        orig_backend = self.db.DB_BACKEND
        try:
            self.db.DB_PATH_OR_URL = ":memory:"
            self.db.DB_BACKEND = "sqlite"
            health = self.db.get_db_health()
            self.assertEqual(health["dbPathKind"], "memory")
        finally:
            self.db.DB_PATH_OR_URL = orig_path
            self.db.DB_BACKEND = orig_backend

    def test_health_postgres_kind(self):
        orig_backend = self.db.DB_BACKEND
        orig_url = self.db.DB_PATH_OR_URL
        try:
            self.db.DB_BACKEND = "postgres"
            self.db.DB_PATH_OR_URL = "postgres://localhost/test"
            health = self.db.get_db_health()
            self.assertEqual(health["dbPathKind"], "postgres")
            # Cannot connect without real PostgreSQL, so these stay False
            self.assertFalse(health["dbConnected"])
            self.assertFalse(health["dbWritable"])
        finally:
            self.db.DB_BACKEND = orig_backend
            self.db.DB_PATH_OR_URL = orig_url


if __name__ == "__main__":
    unittest.main(verbosity=2)
