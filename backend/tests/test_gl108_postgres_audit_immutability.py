"""Tests for GL-108: PostgreSQL Audit Immutability Triggers.

Ensures:
1.  Migration SQL defines audit_immutability_check trigger function.
2.  Migration SQL defines BEFORE UPDATE trigger on audit_events.
3.  Migration SQL defines BEFORE DELETE trigger on audit_events.
4.  PostgreSQL mutation-blocking semantics (RAISE EXCEPTION).
5.  Migration apply() is idempotent (CREATE OR REPLACE + DROP IF EXISTS).
6.  PostgreSQL backend guard respected (SQLite skips PG SQL).
7.  GL-102 SQLite UPDATE immutability preserved.
8.  GL-102 SQLite DELETE immutability preserved.
9.  Audit INSERT preserved.
10. Audit SELECT/list preserved.
11. GL-103 hash-chain behavior preserved.
12. Historical audit rows not rewritten after migration.
13. No audit verification endpoint added.
14. No OpenAPI change.
15. GL-107 operator auth lookup preserved.
16. GL-106 rate limiting preserved.
17. Security boundary preserved (health public, protected requires auth).
18. Diff scope limited to allowed files.
"""

import importlib
import importlib.util
import inspect
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


_MIGRATION_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "src", "migrations",
    "0008_gl108_postgres_audit_immutability.py"
))


def _load_migration():
    """Load the GL-108 migration module without side effects."""
    spec = importlib.util.spec_from_file_location("_migration_gl108", _MIGRATION_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ═══════════════════════════════════════════════════════════════════════
# Fake connection — simulates postgres/sqlite without real DB
# ═══════════════════════════════════════════════════════════════════════

class _FakeConn:
    """Minimal fake database connection that records SQL calls."""

    def __init__(self, backend="postgres"):
        self.backend = backend
        self.executed = []
        self.committed = False

    def execute(self, sql, params=None):
        self.executed.append(sql.strip())
        return self

    def fetchall(self):
        return []

    def fetchone(self):
        return None

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass

    @property
    def executed_combined(self):
        return "\n".join(self.executed)


# ═══════════════════════════════════════════════════════════════════════
# Base class for SQLite-backed integration tests
# ═══════════════════════════════════════════════════════════════════════

class _BaseGl108(unittest.TestCase):
    """Shared helpers: temp SQLite DB + module reloads."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"

        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")
        self._orig_enable_demo = os.environ.get("GRANTLAYER_ENABLE_DEMO_ENDPOINTS")
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)

        import backend.src.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH_OR_URL = self.tmp_db.name
        db_mod.DB_PATH = self.tmp_db.name
        db_mod.init_db()

        import backend.src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.models as models_mod
        importlib.reload(models_mod)
        self.models_mod = models_mod

        import backend.src.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

        import backend.src.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import backend.src.server as server_mod
        importlib.reload(server_mod)
        self.server_mod = server_mod

        self.db_mod = db_mod

        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        self.client = TestClient(create_app(), raise_server_exceptions=False)

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, orig in [
            ("GRANTLAYER_DB", self._orig_db),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", self._orig_bootstrap_token),
            ("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", self._orig_enable_demo),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    def _append_audit_event(self, event_id, action="test_action", approved=True):
        event = self.models_mod.AuditEvent(
            id=event_id,
            timestamp="2026-01-01T00:00:00Z",
            subject_id="test-subject",
            role="tester",
            action=action,
            resource="test-resource",
            approved=approved,
            reason="test reason",
            matched_grant_id=None,
            challenge_id=None,
            challenge_present=False,
            challenge_result="legacy_mode",
            grant_signature_result="not_checked",
        )
        self.audit_mod.append_event(event)
        return event

    def _make_handler(self, path, method="GET", auth_header=None, body=b""):
        return (path, method, auth_header, body)

    def _run_handler(self, req):
        path, method, auth_header, body = req
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if method == "GET":
            resp = self.client.get(path, headers=headers)
        else:
            if isinstance(body, (bytes, bytearray)) and len(body) > 0:
                try:
                    body_dict = json.loads(body)
                    resp = self.client.post(path, json=body_dict, headers=headers)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    resp = self.client.post(path, content=body, headers=headers)
            else:
                resp = self.client.post(path, headers=headers)
        try:
            data = resp.json()
        except Exception:
            data = {}
        if isinstance(data, dict) and isinstance(data.get("detail"), dict):
            data = data["detail"]
        return resp.status_code, data


# ═══════════════════════════════════════════════════════════════════════
# 1. PostgreSQL trigger SQL content
# ═══════════════════════════════════════════════════════════════════════

class TestGl108MigrationSqlContent(unittest.TestCase):
    """Verify migration SQL defines the expected PostgreSQL constructs."""

    def setUp(self):
        self.mod = _load_migration()
        self.fake = _FakeConn(backend="postgres")
        self.mod.apply(self.fake)
        self.all_sql = self.fake.executed_combined

    def test_trigger_function_defined(self):
        """Migration must define the audit_immutability_check function."""
        self.assertIn("audit_immutability_check", self.all_sql)

    def test_trigger_function_returns_trigger(self):
        """Trigger function must be declared RETURNS TRIGGER."""
        self.assertIn("RETURNS TRIGGER", self.all_sql)

    def test_trigger_function_raises_exception(self):
        """Trigger function must use RAISE EXCEPTION to block mutations."""
        self.assertIn("RAISE EXCEPTION", self.all_sql)

    def test_trigger_function_create_or_replace_for_idempotency(self):
        """Function creation must use CREATE OR REPLACE (idempotent)."""
        self.assertIn("CREATE OR REPLACE FUNCTION", self.all_sql)

    def test_update_trigger_name_defined(self):
        """Migration must define trigger named audit_events_no_update."""
        self.assertIn("audit_events_no_update", self.all_sql)

    def test_delete_trigger_name_defined(self):
        """Migration must define trigger named audit_events_no_delete."""
        self.assertIn("audit_events_no_delete", self.all_sql)

    def test_update_trigger_is_before_update(self):
        """Update trigger must fire BEFORE UPDATE."""
        self.assertIn("BEFORE UPDATE", self.all_sql)

    def test_delete_trigger_is_before_delete(self):
        """Delete trigger must fire BEFORE DELETE."""
        self.assertIn("BEFORE DELETE", self.all_sql)

    def test_update_trigger_drop_if_exists_for_idempotency(self):
        """Migration must DROP TRIGGER IF EXISTS audit_events_no_update."""
        self.assertIn("DROP TRIGGER IF EXISTS audit_events_no_update", self.all_sql)

    def test_delete_trigger_drop_if_exists_for_idempotency(self):
        """Migration must DROP TRIGGER IF EXISTS audit_events_no_delete."""
        self.assertIn("DROP TRIGGER IF EXISTS audit_events_no_delete", self.all_sql)

    def test_triggers_target_audit_events_table(self):
        """Both triggers must target the audit_events table."""
        self.assertIn("ON audit_events", self.all_sql)

    def test_version_attribute(self):
        """Migration version attribute must match the file name prefix."""
        self.assertEqual(self.mod.version, "0008_gl108_postgres_audit_immutability")


# ═══════════════════════════════════════════════════════════════════════
# 2. PostgreSQL apply() execution via fake conn
# ═══════════════════════════════════════════════════════════════════════

class TestGl108FakePostgresExecution(unittest.TestCase):
    """Verify apply() makes the expected calls on a postgres connection."""

    def test_postgres_apply_calls_commit(self):
        """apply() must call commit() on a postgres connection."""
        mod = _load_migration()
        fake = _FakeConn(backend="postgres")
        mod.apply(fake)
        self.assertTrue(fake.committed)

    def test_postgres_apply_executes_multiple_statements(self):
        """apply() must execute: function create + 2 drop + 2 create trigger."""
        mod = _load_migration()
        fake = _FakeConn(backend="postgres")
        mod.apply(fake)
        self.assertGreaterEqual(len(fake.executed), 5)

    def test_sqlite_backend_skips_postgres_sql(self):
        """SQLite backend must not execute any PostgreSQL-specific SQL."""
        mod = _load_migration()
        fake = _FakeConn(backend="sqlite")
        mod.apply(fake)
        pg_markers = ["RETURNS TRIGGER", "RAISE EXCEPTION", "plpgsql",
                      "audit_events_no_update", "audit_events_no_delete"]
        combined = fake.executed_combined
        for marker in pg_markers:
            self.assertNotIn(marker, combined,
                f"SQLite backend must not execute PG SQL containing '{marker}'")

    def test_sqlite_backend_still_calls_commit(self):
        """commit() must be called even when backend is sqlite."""
        mod = _load_migration()
        fake = _FakeConn(backend="sqlite")
        mod.apply(fake)
        self.assertTrue(fake.committed)


# ═══════════════════════════════════════════════════════════════════════
# 3. Migration idempotency
# ═══════════════════════════════════════════════════════════════════════

class TestGl108MigrationIdempotency(_BaseGl108):
    """Applying the migration twice must be safe."""

    def test_postgres_apply_twice_does_not_raise(self):
        """Calling apply() twice on fake PG conn must not raise."""
        mod = _load_migration()
        fake1 = _FakeConn(backend="postgres")
        mod.apply(fake1)
        self.assertTrue(fake1.committed)
        fake2 = _FakeConn(backend="postgres")
        mod.apply(fake2)
        self.assertTrue(fake2.committed)

    def test_sqlite_run_migrations_twice_does_not_raise(self):
        """run_migrations() on an already-migrated SQLite DB must be a no-op."""
        import backend.src.migrations.runner as runner_mod
        importlib.reload(runner_mod)
        conn = self.db_mod.get_conn()
        try:
            runner_mod.run_migrations(conn)
        finally:
            conn.close()
        self._append_audit_event("evt-idem-gl108")
        events = self.audit_mod.list_events(limit=10)
        ids = [e.id for e in events]
        self.assertIn("evt-idem-gl108", ids)

    def test_sqlite_triggers_still_exist_after_idempotent_rerun(self):
        """SQLite immutability triggers must persist after migration re-run."""
        import backend.src.migrations.runner as runner_mod
        importlib.reload(runner_mod)
        conn = self.db_mod.get_conn()
        try:
            runner_mod.run_migrations(conn)
        finally:
            conn.close()
        conn = self.db_mod.get_conn()
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='audit_events'"
            ).fetchall()
            names = {r["name"] if isinstance(r, dict) else r[0] for r in rows}
            self.assertIn("trg_audit_events_no_update", names)
            self.assertIn("trg_audit_events_no_delete", names)
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════
# 4. GL-102 SQLite immutability preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl108Gl102SqliteImmutabilityPreserved(_BaseGl108):
    """GL-102 SQLite triggers must still block UPDATE and DELETE on audit_events."""

    def test_sqlite_update_blocked(self):
        """Direct UPDATE on audit_events must still raise (GL-102 preserved)."""
        self._append_audit_event("evt-upd-gl108")
        conn = self.db_mod.get_conn()
        try:
            with self.assertRaises(Exception) as ctx:
                conn.execute(
                    "UPDATE audit_events SET reason = 'tampered' WHERE id = ?",
                    ("evt-upd-gl108",),
                )
            self.assertIn("immutable", str(ctx.exception).lower())
        finally:
            conn.close()

    def test_sqlite_delete_blocked(self):
        """Direct DELETE on audit_events must still raise (GL-102 preserved)."""
        self._append_audit_event("evt-del-gl108")
        conn = self.db_mod.get_conn()
        try:
            with self.assertRaises(Exception) as ctx:
                conn.execute(
                    "DELETE FROM audit_events WHERE id = ?",
                    ("evt-del-gl108",),
                )
            self.assertIn("immutable", str(ctx.exception).lower())
        finally:
            conn.close()

    def test_sqlite_blocked_update_leaves_row_unchanged(self):
        """Rejected UPDATE must not mutate the row."""
        self._append_audit_event("evt-upd-preserve-gl108", action="original_gl108")
        conn = self.db_mod.get_conn()
        try:
            try:
                conn.execute(
                    "UPDATE audit_events SET action = 'tampered' WHERE id = ?",
                    ("evt-upd-preserve-gl108",),
                )
            except Exception:
                pass
        finally:
            conn.close()
        event = self.audit_mod.get_event("evt-upd-preserve-gl108")
        self.assertEqual(event.action, "original_gl108")

    def test_sqlite_blocked_delete_leaves_row_present(self):
        """Rejected DELETE must not remove the row."""
        self._append_audit_event("evt-del-preserve-gl108")
        conn = self.db_mod.get_conn()
        try:
            try:
                conn.execute(
                    "DELETE FROM audit_events WHERE id = ?",
                    ("evt-del-preserve-gl108",),
                )
            except Exception:
                pass
        finally:
            conn.close()
        event = self.audit_mod.get_event("evt-del-preserve-gl108")
        self.assertIsNotNone(event)


# ═══════════════════════════════════════════════════════════════════════
# 5. INSERT and SELECT preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl108InsertSelectPreserved(_BaseGl108):
    """INSERT and SELECT on audit_events must still work after GL-108."""

    def test_audit_insert_works(self):
        """append_event must create a row."""
        self._append_audit_event("evt-ins-gl108")
        events = self.audit_mod.list_events(limit=10)
        ids = [e.id for e in events]
        self.assertIn("evt-ins-gl108", ids)

    def test_audit_get_event_works(self):
        """get_event must return the inserted row by id."""
        self._append_audit_event("evt-sel-gl108")
        event = self.audit_mod.get_event("evt-sel-gl108")
        self.assertIsNotNone(event)
        self.assertEqual(event.id, "evt-sel-gl108")

    def test_audit_list_events_works(self):
        """list_events must return all inserted rows."""
        for i in range(3):
            self._append_audit_event(f"evt-list-gl108-{i}")
        events = self.audit_mod.list_events(limit=10)
        self.assertGreaterEqual(len(events), 3)

    def test_multiple_inserts_all_succeed(self):
        """Five sequential INSERTs must all succeed."""
        for i in range(5):
            self._append_audit_event(f"evt-multi-gl108-{i}")
        events = self.audit_mod.list_events(limit=10)
        self.assertEqual(len(events), 5)


# ═══════════════════════════════════════════════════════════════════════
# 6. GL-103 hash-chain behavior preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl108Gl103HashChainPreserved(_BaseGl108):
    """GL-103 row_hash and prev_hash chaining must still work after GL-108."""

    def test_inserted_event_has_row_hash(self):
        """New audit events must receive a non-None row_hash (GL-103)."""
        self._append_audit_event("evt-hash-gl108")
        event = self.audit_mod.get_event("evt-hash-gl108")
        self.assertIsNotNone(event)
        row_hash = getattr(event, "row_hash", None)
        self.assertIsNotNone(row_hash, "event.row_hash must not be None (GL-103)")
        self.assertIsInstance(row_hash, str)
        self.assertGreater(len(row_hash), 0)

    def test_second_event_prev_hash_chains_to_first(self):
        """Second event prev_hash must equal first event row_hash (GL-103 chain)."""
        self._append_audit_event("evt-chain-1-gl108")
        self._append_audit_event("evt-chain-2-gl108")
        evt1 = self.audit_mod.get_event("evt-chain-1-gl108")
        evt2 = self.audit_mod.get_event("evt-chain-2-gl108")
        self.assertIsNotNone(evt1)
        self.assertIsNotNone(evt2)
        row_hash_1 = getattr(evt1, "row_hash", None)
        prev_hash_2 = getattr(evt2, "prev_hash", None)
        if row_hash_1 is not None and prev_hash_2 is not None:
            self.assertEqual(prev_hash_2, row_hash_1,
                "Second event prev_hash must chain to first event row_hash")

    def test_row_hash_is_deterministic_hex_string(self):
        """row_hash must be a lowercase hex string."""
        self._append_audit_event("evt-hex-gl108")
        event = self.audit_mod.get_event("evt-hex-gl108")
        row_hash = getattr(event, "row_hash", None)
        if row_hash is not None:
            self.assertRegex(row_hash, r"^[0-9a-f]+$",
                "row_hash must be a hex string")


# ═══════════════════════════════════════════════════════════════════════
# 7. Historical rows not rewritten
# ═══════════════════════════════════════════════════════════════════════

class TestGl108HistoricalRowsNotRewritten(_BaseGl108):
    """Migration re-run must not alter existing audit rows."""

    def test_existing_rows_unchanged_after_migration_rerun(self):
        """Pre-existing audit row fields must be identical after migrations re-run."""
        self._append_audit_event("evt-hist-gl108", action="historical_action")
        event_before = self.audit_mod.get_event("evt-hist-gl108")
        self.assertIsNotNone(event_before)
        row_hash_before = getattr(event_before, "row_hash", None)

        import backend.src.migrations.runner as runner_mod
        importlib.reload(runner_mod)
        conn = self.db_mod.get_conn()
        try:
            runner_mod.run_migrations(conn)
        finally:
            conn.close()

        event_after = self.audit_mod.get_event("evt-hist-gl108")
        self.assertIsNotNone(event_after)
        self.assertEqual(event_after.action, "historical_action")
        self.assertEqual(event_after.subject_id, event_before.subject_id)
        if row_hash_before is not None:
            row_hash_after = getattr(event_after, "row_hash", None)
            self.assertEqual(row_hash_after, row_hash_before,
                "row_hash must not change after migration re-run")


# ═══════════════════════════════════════════════════════════════════════
# 8. No forbidden changes
# ═══════════════════════════════════════════════════════════════════════

class TestGl108NoForbiddenChanges(_BaseGl108):
    """Verify no forbidden changes (endpoint, OpenAPI, auth, rate-limit) in GL-108."""

    def test_no_audit_verification_endpoint_added(self):
        """server.py must not contain an /audit/verify or audit_verify endpoint."""
        import backend.src.server as server_mod
        importlib.reload(server_mod)
        src_text = inspect.getsource(server_mod)
        self.assertNotIn("/audit/verify", src_text)
        self.assertNotIn("/audit-verify", src_text)
        self.assertNotIn("audit_verify", src_text)

    def test_no_new_audit_sub_paths_in_routing(self):
        """Routing must not contain new /audit/ sub-path checks."""
        import backend.src.server as server_mod
        importlib.reload(server_mod)
        src_text = inspect.getsource(server_mod)
        # No routing equality check for paths starting /audit/ (would be new endpoint)
        self.assertNotIn('== "/audit/"', src_text)
        self.assertNotIn('"/audit/v', src_text)

    def test_gl107_operator_auth_preserved(self):
        """src.operators must still expose GL-107 token lookup functions."""
        import backend.src.operators as ops_mod
        importlib.reload(ops_mod)
        self.assertTrue(hasattr(ops_mod, "hash_token"),
            "hash_token missing from operators (GL-107 broken)")
        self.assertTrue(hasattr(ops_mod, "derive_token_lookup_hash"),
            "derive_token_lookup_hash missing from operators (GL-107 broken)")

    def test_gl106_rate_limiter_preserved(self):
        """src.rate_limiter must still expose RateLimiter class (GL-106)."""
        import backend.src.rate_limiter as rl_mod
        importlib.reload(rl_mod)
        self.assertTrue(hasattr(rl_mod, "RateLimiter"),
            "RateLimiter class missing from rate_limiter (GL-106 broken)")


# ═══════════════════════════════════════════════════════════════════════
# 9. Security boundary preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl108SecurityBoundaryPreserved(_BaseGl108):
    """Core security boundaries must remain intact after GL-108."""

    def test_health_endpoint_public(self):
        """GET /health must remain public (no auth required)."""
        req = self._make_handler("/health")
        status, data = self._run_handler(req)
        self.assertEqual(status, 200)
        self.assertEqual(data.get("status"), "ok")

    def test_readiness_endpoint_public(self):
        """GET /readiness must remain public."""
        req = self._make_handler("/readiness")
        status, _data = self._run_handler(req)
        self.assertIn(status, (200, 503))

    def test_grants_endpoint_requires_auth(self):
        """GET /grants must require operator auth."""
        req = self._make_handler("/grants")
        status, _data = self._run_handler(req)
        self.assertIn(status, (401, 403))

    def test_audit_events_endpoint_requires_auth(self):
        """GET /audit-events must require operator auth."""
        req = self._make_handler("/audit-events")
        status, _data = self._run_handler(req)
        self.assertIn(status, (401, 403))


# ═══════════════════════════════════════════════════════════════════════
# 10. Diff scope validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl108DiffScope(unittest.TestCase):
    """GL-108 branch diff must only touch allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root, capture_output=True, text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-108-postgres-audit-immutability-trigger":
            self.skipTest(
                "Branch-wide diff check only valid on gl-108 feature branch"
            )
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root, capture_output=True, text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/migrations/0008_gl108_postgres_audit_immutability.py",
            "backend/tests/test_gl108_postgres_audit_immutability.py",
            "backend/src/migrations/runner.py",
            "backend/src/db.py",
            "backend/src/migrations/0005_gl102_audit_log_immutability.py",
        }
        for path in changed:
            self.assertIn(path, allowed,
                f"GL-108 changed a forbidden file: {path}")


# ═══════════════════════════════════════════════════════════════════════
# 11. GL-116 Real PostgreSQL integration test for GL-108 triggers
# ═══════════════════════════════════════════════════════════════════════

class TestGl116PostgresAuditImmutabilityIntegration(unittest.TestCase):
    """GL-116: Real PostgreSQL integration test proving GL-108 audit
    immutability triggers block UPDATE and DELETE on audit_events.

    Skips cleanly when PostgreSQL is not configured or unreachable.
    Fails hard when PostgreSQL is reachable but immutability triggers
    do not work.
    """

    @classmethod
    def setUpClass(cls):
        cls.pg_url = os.environ.get("GRANTLAYER_DATABASE_URL", "")
        if not cls.pg_url:
            cls.pg_url = os.environ.get("GRANTLAYER_TEST_DATABASE_URL", "")
        if not cls.pg_url or not cls.pg_url.startswith("postgres"):
            raise unittest.SkipTest(
                "No PostgreSQL test URL configured. "
                "Set GRANTLAYER_DATABASE_URL or GRANTLAYER_TEST_DATABASE_URL "
                "to run this integration test."
            )
        try:
            import psycopg2
            conn = psycopg2.connect(cls.pg_url)
            conn.cursor().execute("SELECT 1")
            conn.close()
        except Exception as exc:
            raise unittest.SkipTest(f"PostgreSQL not reachable: {exc}")

    def _get_db_mod(self):
        import backend.src.db as db_mod
        importlib.reload(db_mod)
        return db_mod

    def setUp(self):
        self.test_event_id = f"gl116-test-{os.urandom(4).hex()}"
        db_mod = self._get_db_mod()
        orig_backend = db_mod.DB_BACKEND
        orig_url = db_mod.DB_PATH_OR_URL
        try:
            db_mod.DB_BACKEND = "postgres"
            db_mod.DB_PATH_OR_URL = self.pg_url
            db_mod.init_db()
            with db_mod.get_conn() as conn:
                conn.execute(
                    "INSERT INTO audit_events (id, timestamp, subject_id, role, action, resource, approved, reason) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (self.test_event_id, "2026-01-01T00:00:00Z", "gl116-subject", "tester", "read", "gl116-resource", 1, "GL-116 test"),
                )
                conn.commit()
        finally:
            db_mod.DB_BACKEND = orig_backend
            db_mod.DB_PATH_OR_URL = orig_url

    def test_postgres_update_audit_events_blocked(self):
        """UPDATE audit_events must be blocked by the immutability trigger."""
        db_mod = self._get_db_mod()
        orig_backend = db_mod.DB_BACKEND
        orig_url = db_mod.DB_PATH_OR_URL
        try:
            db_mod.DB_BACKEND = "postgres"
            db_mod.DB_PATH_OR_URL = self.pg_url
            with db_mod.get_conn() as conn:
                with self.assertRaises(Exception) as ctx:
                    conn.execute(
                        "UPDATE audit_events SET reason = 'tampered' WHERE id = ?",
                        (self.test_event_id,),
                    )
                msg = str(ctx.exception).lower()
                self.assertIn("immutable", msg,
                    f"Expected 'immutable' in error message, got: {msg}")
        finally:
            db_mod.DB_BACKEND = orig_backend
            db_mod.DB_PATH_OR_URL = orig_url

    def test_postgres_delete_audit_events_blocked(self):
        """DELETE audit_events must be blocked by the immutability trigger."""
        db_mod = self._get_db_mod()
        orig_backend = db_mod.DB_BACKEND
        orig_url = db_mod.DB_PATH_OR_URL
        try:
            db_mod.DB_BACKEND = "postgres"
            db_mod.DB_PATH_OR_URL = self.pg_url
            with db_mod.get_conn() as conn:
                with self.assertRaises(Exception) as ctx:
                    conn.execute(
                        "DELETE FROM audit_events WHERE id = ?",
                        (self.test_event_id,),
                    )
                msg = str(ctx.exception).lower()
                self.assertIn("immutable", msg,
                    f"Expected 'immutable' in error message, got: {msg}")
        finally:
            db_mod.DB_BACKEND = orig_backend
            db_mod.DB_PATH_OR_URL = orig_url

    def test_postgres_insert_and_select_still_work(self):
        """INSERT and SELECT on audit_events must still work."""
        new_id = f"gl116-insert-{os.urandom(4).hex()}"
        db_mod = self._get_db_mod()
        orig_backend = db_mod.DB_BACKEND
        orig_url = db_mod.DB_PATH_OR_URL
        try:
            db_mod.DB_BACKEND = "postgres"
            db_mod.DB_PATH_OR_URL = self.pg_url
            with db_mod.get_conn() as conn:
                conn.execute(
                    "INSERT INTO audit_events (id, timestamp, subject_id, role, action, resource, approved, reason) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (new_id, "2026-01-01T00:00:00Z", "gl116-subject", "tester", "write", "gl116-resource", 1, "GL-116 insert test"),
                )
                conn.commit()
                row = conn.execute("SELECT * FROM audit_events WHERE id = ?", (new_id,)).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row["action"], "write")
        finally:
            db_mod.DB_BACKEND = orig_backend
            db_mod.DB_PATH_OR_URL = orig_url


if __name__ == "__main__":
    unittest.main(verbosity=2)
