"""GL-123 — PostgreSQL Connection Pooling Baseline.

Covers:
1. Pool env var defaults (min=2, max=10)
2. Pool env var overrides are respected
3. ThreadedConnectionPool is initialized lazily on first use
4. Connections are returned to the pool via wrapper.close()
5. SQLite path is completely unchanged
6. Secret safety: DSN/password never exposed in pool failure messages
7. _close_pg_pool() cleans up without error when no pool exists
"""

import os
import sys
import unittest
import importlib
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_fake_psycopg2_module():
    """Build a fake psycopg2 module tree sufficient for get_conn()."""
    fake_pool = MagicMock()
    fake_pool_instance = MagicMock()
    fake_pool_instance.getconn.return_value = MagicMock()
    fake_pool_instance.putconn = MagicMock()
    fake_pool.ThreadedConnectionPool.return_value = fake_pool_instance

    fake_extras = MagicMock()
    fake_extras.RealDictCursor = MagicMock()

    fake_psycopg2 = MagicMock()
    fake_psycopg2.extras = fake_extras
    fake_psycopg2.pool = fake_pool
    fake_psycopg2.OperationalError = Exception

    return fake_psycopg2, fake_pool_instance


def _patch_psycopg2(fake_psycopg2):
    """Return a patch.dict context for all psycopg2 submodules used by db.py."""
    return patch.dict(
        "sys.modules",
        {
            "psycopg2": fake_psycopg2,
            "psycopg2.extras": fake_psycopg2.extras,
            "psycopg2.pool": fake_psycopg2.pool,
        },
        clear=False,
    )


class TestPoolDefaults(unittest.TestCase):
    """GL-123 pool sizing defaults."""

    def test_pool_min_defaults_to_two(self):
        import backend.src.core.db as db_mod
        self.assertEqual(db_mod._db_pool_min, 2)

    def test_pool_max_defaults_to_ten(self):
        import backend.src.core.db as db_mod
        self.assertEqual(db_mod._db_pool_max, 10)


class TestPoolEnvOverrides(unittest.TestCase):
    """GL-123 pool env vars are respected."""

    def test_pool_min_env_override(self):
        orig = os.environ.get("GRANTLAYER_DB_POOL_MIN")
        os.environ["GRANTLAYER_DB_POOL_MIN"] = "4"
        try:
            import backend.src.core.db as db_mod
            importlib.reload(db_mod)
            self.assertEqual(db_mod._db_pool_min, 4)
        finally:
            if orig is not None:
                os.environ["GRANTLAYER_DB_POOL_MIN"] = orig
            else:
                os.environ.pop("GRANTLAYER_DB_POOL_MIN", None)
            importlib.reload(db_mod)

    def test_pool_max_env_override(self):
        orig = os.environ.get("GRANTLAYER_DB_POOL_MAX")
        os.environ["GRANTLAYER_DB_POOL_MAX"] = "20"
        try:
            import backend.src.core.db as db_mod
            importlib.reload(db_mod)
            self.assertEqual(db_mod._db_pool_max, 20)
        finally:
            if orig is not None:
                os.environ["GRANTLAYER_DB_POOL_MAX"] = orig
            else:
                os.environ.pop("GRANTLAYER_DB_POOL_MAX", None)
            importlib.reload(db_mod)


class TestPoolInitialization(unittest.TestCase):
    """GL-123 pool is initialized lazily and connections are returned."""

    def test_pool_created_on_first_use(self):
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)

        orig_backend = db_mod.DB_BACKEND
        orig_url = db_mod.DB_PATH_OR_URL
        orig_pool = db_mod._pg_pool

        fake_psycopg2, fake_pool_instance = _make_fake_psycopg2_module()

        try:
            db_mod.DB_BACKEND = "postgres"
            db_mod.DB_PATH_OR_URL = "postgres://user:pass@localhost/db"
            db_mod._pg_pool = None

            with _patch_psycopg2(fake_psycopg2):
                conn = db_mod.get_conn()
                self.assertIsNotNone(conn)
                # Pool should have been created
                fake_psycopg2.pool.ThreadedConnectionPool.assert_called_once()
                call_args = fake_psycopg2.pool.ThreadedConnectionPool.call_args
                self.assertEqual(call_args[0][0], 2)  # min
                self.assertEqual(call_args[0][1], 10)  # max
                self.assertEqual(call_args[1]["cursor_factory"], fake_psycopg2.extras.RealDictCursor)
                # Connection should come from getconn
                fake_pool_instance.getconn.assert_called_once()
                # Wrapper should hold pool reference
                self.assertIs(conn._pool, fake_pool_instance)
        finally:
            db_mod.DB_BACKEND = orig_backend
            db_mod.DB_PATH_OR_URL = orig_url
            db_mod._pg_pool = orig_pool

    def test_connection_returned_to_pool_on_close(self):
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)

        orig_backend = db_mod.DB_BACKEND
        orig_url = db_mod.DB_PATH_OR_URL
        orig_pool = db_mod._pg_pool

        fake_psycopg2, fake_pool_instance = _make_fake_psycopg2_module()
        fake_raw_conn = MagicMock()
        fake_pool_instance.getconn.return_value = fake_raw_conn

        try:
            db_mod.DB_BACKEND = "postgres"
            db_mod.DB_PATH_OR_URL = "postgres://user:pass@localhost/db"
            db_mod._pg_pool = None

            with _patch_psycopg2(fake_psycopg2):
                conn = db_mod.get_conn()
                conn.close()
                fake_pool_instance.putconn.assert_called_once_with(fake_raw_conn)
                fake_raw_conn.close.assert_not_called()
        finally:
            db_mod.DB_BACKEND = orig_backend
            db_mod.DB_PATH_OR_URL = orig_url
            db_mod._pg_pool = orig_pool

    def test_pool_reused_across_calls(self):
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)

        orig_backend = db_mod.DB_BACKEND
        orig_url = db_mod.DB_PATH_OR_URL
        orig_pool = db_mod._pg_pool

        fake_psycopg2, fake_pool_instance = _make_fake_psycopg2_module()

        try:
            db_mod.DB_BACKEND = "postgres"
            db_mod.DB_PATH_OR_URL = "postgres://user:pass@localhost/db"
            db_mod._pg_pool = None

            with _patch_psycopg2(fake_psycopg2):
                conn1 = db_mod.get_conn()
                conn2 = db_mod.get_conn()
                # Pool created only once
                fake_psycopg2.pool.ThreadedConnectionPool.assert_called_once()
                # Two connections fetched
                self.assertEqual(fake_pool_instance.getconn.call_count, 2)
                conn1.close()
                conn2.close()
                self.assertEqual(fake_pool_instance.putconn.call_count, 2)
        finally:
            db_mod.DB_BACKEND = orig_backend
            db_mod.DB_PATH_OR_URL = orig_url
            db_mod._pg_pool = orig_pool

    def test_query_helpers_return_connections(self):
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)

        orig_backend = db_mod.DB_BACKEND
        orig_url = db_mod.DB_PATH_OR_URL
        orig_pool = db_mod._pg_pool

        fake_psycopg2, fake_pool_instance = _make_fake_psycopg2_module()
        fake_cursor = MagicMock()
        fake_cursor.fetchone.return_value = None
        fake_cursor.fetchall.return_value = []
        fake_cursor.rowcount = 0
        fake_raw_conn = MagicMock()
        fake_raw_conn.cursor.return_value = fake_cursor
        fake_pool_instance.getconn.return_value = fake_raw_conn

        try:
            db_mod.DB_BACKEND = "postgres"
            db_mod.DB_PATH_OR_URL = "postgres://user:pass@localhost/db"
            db_mod._pg_pool = None

            with _patch_psycopg2(fake_psycopg2):
                db_mod.execute("SELECT 1")
                db_mod.query_one("SELECT 1")
                db_mod.query_all("SELECT 1")
                db_mod.executemany("SELECT 1", [()])
                # Each helper gets and returns a connection
                self.assertEqual(fake_pool_instance.getconn.call_count, 4)
                self.assertEqual(fake_pool_instance.putconn.call_count, 4)
        finally:
            db_mod.DB_BACKEND = orig_backend
            db_mod.DB_PATH_OR_URL = orig_url
            db_mod._pg_pool = orig_pool


class TestPoolRetryBehavior(unittest.TestCase):
    """GL-123 pool creation retries on transient failures."""

    def test_pool_creation_retries_then_raises(self):
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)

        orig_backend = db_mod.DB_BACKEND
        orig_url = db_mod.DB_PATH_OR_URL
        orig_max = db_mod._db_retry_max
        orig_pool = db_mod._pg_pool

        fake_psycopg2 = MagicMock()
        fake_psycopg2.extras = MagicMock()
        fake_psycopg2.extras.RealDictCursor = MagicMock()
        fake_psycopg2.pool = MagicMock()
        fake_psycopg2.pool.ThreadedConnectionPool.side_effect = Exception("connection refused")
        fake_psycopg2.OperationalError = Exception

        try:
            db_mod.DB_BACKEND = "postgres"
            db_mod.DB_PATH_OR_URL = "postgres://user:pass@localhost:19999/db"
            db_mod._pg_pool = None
            db_mod._db_retry_max = 2
            db_mod._db_retry_delay = 0.01

            with _patch_psycopg2(fake_psycopg2):
                with self.assertRaises(RuntimeError) as ctx:
                    db_mod.get_conn()
                msg = str(ctx.exception)
                self.assertIn("PostgreSQL connection failed after 2 attempt(s)", msg)
                self.assertNotIn("postgres://", msg)
                self.assertNotIn("user", msg)
                self.assertNotIn("pass", msg)
                # Pool creation attempted twice
                self.assertEqual(fake_psycopg2.pool.ThreadedConnectionPool.call_count, 2)
        finally:
            db_mod.DB_BACKEND = orig_backend
            db_mod.DB_PATH_OR_URL = orig_url
            db_mod._db_retry_max = orig_max
            db_mod._db_retry_delay = 1.0
            db_mod._pg_pool = orig_pool


class TestSQLiteUnchanged(unittest.TestCase):
    """GL-123 SQLite path is completely unaffected by pooling."""

    def test_sqlite_still_uses_direct_connection(self):
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        self.assertEqual(db_mod.DB_BACKEND, "sqlite")
        conn = db_mod.get_conn()
        try:
            self.assertEqual(conn.backend, "sqlite")
            self.assertIsNone(conn._pool)
        finally:
            conn.close()

    def test_sqlite_wrapper_close_calls_raw_close(self):
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        import sqlite3

        conn = db_mod.get_conn()
        raw = conn._conn
        self.assertIsInstance(raw, sqlite3.Connection)
        conn.close()
        # After close, further use should fail
        with self.assertRaises(sqlite3.ProgrammingError):
            raw.execute("SELECT 1")


class TestClosePoolHelper(unittest.TestCase):
    """GL-123 _close_pg_pool() is safe and effective."""

    def test_close_pool_when_no_pool_is_safe(self):
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        orig_pool = db_mod._pg_pool
        try:
            db_mod._pg_pool = None
            db_mod._close_pg_pool()  # should not raise
        finally:
            db_mod._pg_pool = orig_pool

    def test_close_pool_closes_and_clears(self):
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        orig_pool = db_mod._pg_pool

        fake_pool = MagicMock()
        try:
            db_mod._pg_pool = fake_pool
            db_mod._close_pg_pool()
            fake_pool.closeall.assert_called_once()
            self.assertIsNone(db_mod._pg_pool)
        finally:
            db_mod._pg_pool = orig_pool


class TestPoolMinMaxClamped(unittest.TestCase):
    """GL-123 pool min/max are clamped to at least 1."""

    def test_pool_min_clamped_to_one(self):
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)

        orig_backend = db_mod.DB_BACKEND
        orig_url = db_mod.DB_PATH_OR_URL
        orig_pool = db_mod._pg_pool
        orig_min = db_mod._db_pool_min

        fake_psycopg2, fake_pool_instance = _make_fake_psycopg2_module()

        try:
            db_mod.DB_BACKEND = "postgres"
            db_mod.DB_PATH_OR_URL = "postgres://user:pass@localhost/db"
            db_mod._pg_pool = None
            db_mod._db_pool_min = 0

            with _patch_psycopg2(fake_psycopg2):
                db_mod.get_conn()
                call_args = fake_psycopg2.pool.ThreadedConnectionPool.call_args
                self.assertEqual(call_args[0][0], 1)  # clamped to 1
        finally:
            db_mod.DB_BACKEND = orig_backend
            db_mod.DB_PATH_OR_URL = orig_url
            db_mod._pg_pool = orig_pool
            db_mod._db_pool_min = orig_min


if __name__ == "__main__":
    unittest.main(verbosity=2)
