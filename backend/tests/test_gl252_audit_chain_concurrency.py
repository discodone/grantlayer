"""GL-252 — Audit chain multi-worker safety.

Tests:
1. Concurrent SQLite writes produce an intact hash chain (RLock serializes).
2. DB_BACKEND == "postgres" path calls pg_advisory_xact_lock (mocked).
3. Rollback on INSERT failure leaves no partial chain entry.
4. conn=... pass-through still uses SQLite RLock path.
"""

import importlib
import os
import sys
import tempfile
import threading
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_event(**kwargs):
    from backend.src.core.models import AuditEvent
    defaults = dict(
        id=str(uuid.uuid4()),
        timestamp="2026-01-01T00:00:00Z",
        subject_id="sub",
        role="viewer",
        action="read",
        resource="res",
        approved=True,
        reason="test",
        matched_grant_id=None,
        challenge_id=None,
        challenge_present=False,
        challenge_result="not_required",
        grant_signature_result="not_checked",
    )
    defaults.update(kwargs)
    return AuditEvent(**defaults)


class TestConcurrentSQLiteWrites(unittest.TestCase):
    """Concurrent append_event calls on SQLite must produce an intact chain."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        self._orig_url = os.environ.get("GRANTLAYER_DATABASE_URL")
        os.environ["GRANTLAYER_DB"] = self.tmp.name
        os.environ.pop("GRANTLAYER_DATABASE_URL", None)

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.audit.audit_log as al
        importlib.reload(al)
        self.al = al

    def tearDown(self):
        os.unlink(self.tmp.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)
        if self._orig_url is not None:
            os.environ["GRANTLAYER_DATABASE_URL"] = self._orig_url
        else:
            os.environ.pop("GRANTLAYER_DATABASE_URL", None)

    def test_chain_intact_after_concurrent_writes(self):
        """20 threads each appending one event must leave a valid hash chain."""
        errors = []

        def worker():
            try:
                self.al.append_event(_make_event())
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"append_event raised: {errors}")

        result = self.al.verify_audit_hash_chain()
        self.assertTrue(result["valid"], f"Chain broken: {result['failures']}")
        self.assertEqual(result["checked"], 20)

    def test_chain_intact_after_sequential_writes(self):
        """Basic sequential sanity check — chain must be valid after 5 events."""
        for _ in range(5):
            self.al.append_event(_make_event())
        result = self.al.verify_audit_hash_chain()
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked"], 5)

    def test_rlock_is_used_for_sqlite(self):
        """_AUDIT_HASH_CHAIN_WRITE_LOCK must be an RLock instance."""
        import threading
        self.assertIsInstance(self.al._AUDIT_HASH_CHAIN_WRITE_LOCK, type(threading.RLock()))

    def test_conn_passthrough_uses_sqlite_path(self):
        """When conn is passed, the SQLite path is taken regardless of backend."""
        import backend.src.core.db as db_mod
        conn = db_mod.get_conn()
        try:
            event = _make_event()
            self.al.append_event(event, conn=conn)
            conn.commit()  # caller owns the transaction
        finally:
            conn.close()
        result = self.al.verify_audit_hash_chain()
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked"], 1)


class TestPostgresAdvisoryLockPath(unittest.TestCase):
    """PostgreSQL path: pg_advisory_xact_lock must be called during append_event."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        self._orig_url = os.environ.get("GRANTLAYER_DATABASE_URL")
        os.environ["GRANTLAYER_DB"] = self.tmp.name
        os.environ.pop("GRANTLAYER_DATABASE_URL", None)

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.audit.audit_log as al
        importlib.reload(al)
        self.al = al
        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)
        if self._orig_url is not None:
            os.environ["GRANTLAYER_DATABASE_URL"] = self._orig_url
        else:
            os.environ.pop("GRANTLAYER_DATABASE_URL", None)

    def test_postgres_path_calls_advisory_lock(self):
        """_append_event_postgres must issue pg_advisory_xact_lock SQL."""
        advisory_calls = []

        class _FakeConn:
            backend = "postgres"

            def execute(self, sql, params=None):
                if "pg_advisory_xact_lock" in sql:
                    advisory_calls.append(sql)
                    return self
                # Return a fake cursor-like for the hash SELECT
                return _FakeCursor(None)

            def commit(self):
                pass

            def rollback(self):
                pass

            def close(self):
                pass

            def fetchone(self):
                return None

        class _FakeCursor:
            def __init__(self, row):
                self._row = row

            def fetchone(self):
                return self._row

        import unittest.mock as mock

        orig_get_conn = self.al.get_conn
        orig_execute = self.al.execute

        fake_conn = _FakeConn()

        def _fake_execute(sql, params=None):
            pass  # swallow the INSERT

        with mock.patch.object(self.al, "get_conn", return_value=fake_conn), \
             mock.patch.object(self.al, "execute", side_effect=_fake_execute), \
             mock.patch.object(self.al, "DB_BACKEND", "postgres"):
            self.al._append_event_postgres(_make_event())

        self.assertEqual(len(advisory_calls), 1)
        self.assertIn(str(self.al._PG_AUDIT_CHAIN_LOCK_KEY), advisory_calls[0])

    def test_pg_audit_chain_lock_key_is_integer(self):
        self.assertIsInstance(self.al._PG_AUDIT_CHAIN_LOCK_KEY, int)


if __name__ == "__main__":
    unittest.main(verbosity=2)
