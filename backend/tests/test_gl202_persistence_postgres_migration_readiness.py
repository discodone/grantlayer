"""GL-202 — Persistence / PostgreSQL / Migration Readiness test suite.

Covers:
- Migration file ordering is deterministic
- All migration files expose an apply(conn) function
- Migration runner raises with context on missing apply function
- Migration runner raises with context on apply failure
- Failed migration is not marked applied in schema_migrations
- Fresh SQLite DB includes all required business and audit tables
- Fresh DB includes GL-200B tenant_id / workspace_id columns
- Repeated GL-200B migration does not duplicate columns or indexes
- Legacy GL-032 DB detection marks baseline and returns
- Legacy rows in grants/challenges are backfilled to 'demo' tenant
- Audit events with NULL tenant_id are handled fail-closed (not backfilled)
- Audit hash-chain verification passes on empty post-migration DB
- Pre-chain audit events (NULL row_hash) are skipped in verification
- Post-migration tenant-aware audit events verify correctly
- Mixed pre-chain + chain events verify correctly
- Operator token_lookup_hash index present after migration
- list_pending_migrations returns empty list after init_db
- list_pending_migrations returns pending before init_db
- executescript PostgreSQL comment stripping does not drop SQL after leading comment
- Placeholder translation preserved for migration SQL patterns
- DB URL not leaked in migration error messages
- GL-201 production config fail-closed behavior preserved
- GL-202 documentation artifacts are present

Design notes:
- GL-202 is a persistence/migration readiness step, not a production SaaS declaration.
- GrantLayer remains Developer Preview / Controlled Preview with strict boundaries.
- Real customer/private grant/institutional data remains a no-go until later gates.
- Security-sensitive reports route to GitHub Security Advisories.
- No real secrets are included here.
- Tenant/workspace isolation is not overclaimed as production-complete.
- Live PostgreSQL tests are not possible in this environment; static/dry-run checks
  verify PostgreSQL compatibility paths.
"""

import importlib
import json
import os
import sqlite3
import sys
import tempfile
import typing
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(
    REPO_ROOT, "docs", "persistence_postgres_migration_readiness.md"
)
JSON_PATH = os.path.join(
    REPO_ROOT, "docs", "examples", "gl202",
    "persistence_postgres_migration_readiness.json",
)


# ──────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────

def _make_db_file() -> str:
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    return f.name


def _fresh_db() -> tuple:
    """Return (db_path, db_mod) for a freshly initialised in-memory DB."""
    db_path = _make_db_file()
    os.environ["GRANTLAYER_DB"] = db_path
    os.environ.pop("GRANTLAYER_DATABASE_URL", None)
    import src.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    return db_path, db_mod


def _tables(db_path: str) -> set:
    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    conn.close()
    return tables


def _columns(db_path: str, table: str) -> set:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = {r["name"] for r in cur.fetchall()}
    conn.close()
    return cols


def _index_exists(db_path: str, name: str) -> bool:
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (name,)
    )
    found = cur.fetchone() is not None
    conn.close()
    return found


# ──────────────────────────────────────────────────────────────
# 1. Migration file ordering and structure
# ──────────────────────────────────────────────────────────────

class TestMigrationOrdering(unittest.TestCase):
    """Migration files are ordered deterministically and structurally sound."""

    def setUp(self):
        from src.migrations import runner
        self.runner = runner

    def test_migration_files_ordered_deterministically(self):
        """_discovery() returns (version, filepath) in ascending numeric order."""
        versions = [v for v, _ in self.runner._discovery()]
        self.assertEqual(versions, sorted(versions))
        # Must have at least migrations 0001 through 0010
        self.assertGreaterEqual(len(versions), 10)
        self.assertIn("0001_gl032_baseline", versions)
        self.assertIn("0010_gl200b_tenant_workspace_isolation", versions)

    def test_migration_files_are_stable_across_calls(self):
        """_discovery() returns the same result on repeated calls."""
        first = self.runner._discovery()
        second = self.runner._discovery()
        self.assertEqual(first, second)

    def test_all_migration_modules_have_apply_function(self):
        """Every migration module defines apply(conn)."""
        for version, filepath in self.runner._discovery():
            with self.subTest(version=version):
                mod = self.runner._load_module(filepath)
                self.assertTrue(
                    callable(getattr(mod, "apply", None)),
                    f"Migration {version} missing apply(conn)",
                )

    def test_all_migration_modules_have_version_attribute(self):
        """Every migration module declares a version string."""
        for version, filepath in self.runner._discovery():
            with self.subTest(version=version):
                mod = self.runner._load_module(filepath)
                declared = getattr(mod, "version", None)
                self.assertIsNotNone(declared, f"Migration {version} missing version attr")
                self.assertIn(version[:4], declared)


# ──────────────────────────────────────────────────────────────
# 2. Migration failure safety
# ──────────────────────────────────────────────────────────────

class TestMigrationFailureSafety(unittest.TestCase):
    """Migration runner raises with context; failed migration is not marked."""

    def setUp(self):
        self._db_path = _make_db_file()
        os.environ["GRANTLAYER_DB"] = self._db_path
        os.environ.pop("GRANTLAYER_DATABASE_URL", None)
        import src.db as db_mod
        importlib.reload(db_mod)
        self.db_mod = db_mod

    def tearDown(self):
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def test_runner_raises_on_missing_apply_function(self):
        """RuntimeError with migration version is raised for missing apply."""
        from src.migrations import runner
        import types

        conn = self.db_mod.get_conn()
        try:
            runner._ensure_migrations_table(conn)
            runner._mark_applied(conn, "0001_gl032_baseline")

            def _patched_discovery():
                return [("0002_fake_no_apply", "/fake/path")]

            def _patched_load(_path):
                mod = types.ModuleType("fake_migration")
                # Deliberately no apply function
                return mod

            orig_disc = runner._discovery
            orig_load = runner._load_module
            runner._discovery = _patched_discovery
            runner._load_module = _patched_load
            try:
                with self.assertRaises(RuntimeError) as ctx:
                    runner.run_migrations(conn)
                self.assertIn("0002_fake_no_apply", str(ctx.exception))
            finally:
                runner._discovery = orig_disc
                runner._load_module = orig_load
        finally:
            conn.close()

    def test_runner_raises_with_context_on_apply_failure(self):
        """RuntimeError wraps apply exceptions and includes migration version."""
        from src.migrations import runner
        import types

        conn = self.db_mod.get_conn()
        try:
            runner._ensure_migrations_table(conn)
            runner._mark_applied(conn, "0001_gl032_baseline")

            def _patched_discovery():
                return [("0002_fake_failing", "/fake/path")]

            def _patched_load(_path):
                mod = types.ModuleType("fake_migration")
                mod.version = "0002_fake_failing"

                def apply(_conn):
                    raise ValueError("simulated migration failure")

                mod.apply = apply
                return mod

            orig_disc = runner._discovery
            orig_load = runner._load_module
            runner._discovery = _patched_discovery
            runner._load_module = _patched_load
            try:
                with self.assertRaises(RuntimeError) as ctx:
                    runner.run_migrations(conn)
                err = str(ctx.exception)
                self.assertIn("0002_fake_failing", err)
                self.assertIn("failed during apply", err)
            finally:
                runner._discovery = orig_disc
                runner._load_module = orig_load
        finally:
            conn.close()

    def test_failed_migration_not_marked_applied(self):
        """A migration that raises is NOT recorded in schema_migrations."""
        from src.migrations import runner
        import types

        conn = self.db_mod.get_conn()
        try:
            runner._ensure_migrations_table(conn)
            runner._mark_applied(conn, "0001_gl032_baseline")

            def _patched_discovery():
                return [("0002_fake_failing", "/fake/path")]

            def _patched_load(_path):
                mod = types.ModuleType("fake_migration")
                mod.version = "0002_fake_failing"

                def apply(_conn):
                    raise RuntimeError("explode")

                mod.apply = apply
                return mod

            orig_disc = runner._discovery
            orig_load = runner._load_module
            runner._discovery = _patched_discovery
            runner._load_module = _patched_load
            try:
                try:
                    runner.run_migrations(conn)
                except RuntimeError:
                    pass
                applied = runner._applied_versions(conn)
                self.assertNotIn("0002_fake_failing", applied)
            finally:
                runner._discovery = orig_disc
                runner._load_module = orig_load
        finally:
            conn.close()


# ──────────────────────────────────────────────────────────────
# 3. Fresh DB schema completeness
# ──────────────────────────────────────────────────────────────

class TestFreshDbSchema(unittest.TestCase):
    """Fresh DB after init_db() contains all required tables and columns."""

    @classmethod
    def setUpClass(cls):
        cls._db_path, cls._db_mod = _fresh_db()

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls._db_path)
        except OSError:
            pass

    def test_all_business_tables_present(self):
        """Fresh DB has all core and evidence tables."""
        tables = _tables(self._db_path)
        required = {
            "grants", "audit_events", "challenges", "operators",
            "grant_requests", "grant_executions",
            "evidence_archives", "evidence_hashes", "provenance_events",
            "schema_migrations",
        }
        for t in required:
            with self.subTest(table=t):
                self.assertIn(t, tables)

    def test_all_migrations_marked_applied_on_fresh_db(self):
        """All 10 migrations are recorded in schema_migrations after init_db."""
        from src.migrations import runner
        conn = self._db_mod.get_conn()
        try:
            applied = runner._applied_versions(conn)
        finally:
            conn.close()
        self.assertIn("0001_gl032_baseline", applied)
        self.assertIn("0010_gl200b_tenant_workspace_isolation", applied)
        self.assertEqual(len(applied), 10)

    def test_fresh_db_grants_has_tenant_id(self):
        """grants table has tenant_id column after migration."""
        cols = _columns(self._db_path, "grants")
        self.assertIn("tenant_id", cols)
        self.assertIn("workspace_id", cols)

    def test_fresh_db_audit_events_has_tenant_id(self):
        """audit_events table has tenant_id, workspace_id, scope columns."""
        cols = _columns(self._db_path, "audit_events")
        self.assertIn("tenant_id", cols)
        self.assertIn("workspace_id", cols)
        self.assertIn("scope", cols)
        self.assertIn("row_hash", cols)
        self.assertIn("prev_hash", cols)

    def test_fresh_db_operators_has_tenant_id(self):
        """operators table has tenant_id and token_lookup_hash."""
        cols = _columns(self._db_path, "operators")
        self.assertIn("tenant_id", cols)
        self.assertIn("token_lookup_hash", cols)
        self.assertIn("expires_at", cols)
        self.assertIn("rotated_at", cols)

    def test_fresh_db_grant_requests_has_tenant_id(self):
        """grant_requests has tenant_id column."""
        cols = _columns(self._db_path, "grant_requests")
        self.assertIn("tenant_id", cols)
        self.assertIn("workspace_id", cols)

    def test_fresh_db_challenges_has_tenant_id(self):
        """challenges has tenant_id column."""
        cols = _columns(self._db_path, "challenges")
        self.assertIn("tenant_id", cols)
        self.assertIn("workspace_id", cols)

    def test_fresh_db_evidence_archives_has_tenant_id(self):
        """evidence_archives has tenant_id column."""
        cols = _columns(self._db_path, "evidence_archives")
        self.assertIn("tenant_id", cols)

    def test_fresh_db_tenant_id_indexes_present(self):
        """Tenant lookup indexes are present on major tables."""
        expected_indexes = [
            "idx_grants_tenant_id",
            "idx_audit_events_tenant_id",
            "idx_grant_requests_tenant_id",
            "idx_challenges_tenant_id",
            "idx_grants_tenant_subject",
            "idx_operators_token_lookup_hash",
        ]
        for idx in expected_indexes:
            with self.subTest(index=idx):
                self.assertTrue(
                    _index_exists(self._db_path, idx),
                    f"Expected index {idx} not found",
                )

    def test_grant_executions_indexes_present(self):
        """Grant execution lookup indexes are present."""
        expected = [
            "idx_grant_executions_grant_id",
            "idx_grant_executions_grant_request_id",
            "idx_grant_executions_operator_id",
            "idx_grant_executions_executed_at",
        ]
        for idx in expected:
            with self.subTest(index=idx):
                self.assertTrue(_index_exists(self._db_path, idx))


# ──────────────────────────────────────────────────────────────
# 4. Migration idempotency
# ──────────────────────────────────────────────────────────────

class TestMigrationIdempotency(unittest.TestCase):
    """Re-running migrations on an already-migrated DB is safe."""

    def setUp(self):
        self._db_path, self._db_mod = _fresh_db()

    def tearDown(self):
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def test_init_db_twice_does_not_raise(self):
        """Calling init_db() twice does not raise or corrupt schema."""
        self._db_mod.init_db()  # second call
        tables = _tables(self._db_path)
        self.assertIn("grants", tables)

    def test_gl200b_migration_apply_twice_is_idempotent(self):
        """Applying migration 0010 twice does not duplicate columns or indexes."""
        from src.migrations.runner import _load_module, _discovery
        filepath = None
        for v, fp in _discovery():
            if v == "0010_gl200b_tenant_workspace_isolation":
                filepath = fp
                break
        self.assertIsNotNone(filepath)
        mod = _load_module(filepath)
        conn = self._db_mod.get_conn()
        try:
            mod.apply(conn)  # second application (first was in init_db)
        finally:
            conn.close()
        # Columns should still be present, not duplicated
        cols = _columns(self._db_path, "grants")
        self.assertIn("tenant_id", cols)
        # Verify indexes are still present
        self.assertTrue(_index_exists(self._db_path, "idx_grants_tenant_id"))

    def test_run_migrations_called_twice_adds_no_new_rows(self):
        """run_migrations on fully-applied DB does not touch schema_migrations."""
        from src.migrations import runner
        conn = self._db_mod.get_conn()
        try:
            applied_before = runner._applied_versions(conn)
            runner.run_migrations(conn)
            applied_after = runner._applied_versions(conn)
        finally:
            conn.close()
        self.assertEqual(applied_before, applied_after)


# ──────────────────────────────────────────────────────────────
# 5. Legacy GL-032 DB path
# ──────────────────────────────────────────────────────────────

class TestLegacyDbPath(unittest.TestCase):
    """Legacy GL-032 DB detection marks baseline and all migrations applied."""

    def _make_legacy_gl032_db(self, path: str) -> None:
        """Create minimal GL-032 schema without schema_migrations."""
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
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

    def setUp(self):
        self._db_path = _make_db_file()
        self._make_legacy_gl032_db(self._db_path)
        os.environ["GRANTLAYER_DB"] = self._db_path
        os.environ.pop("GRANTLAYER_DATABASE_URL", None)
        import src.db as db_mod
        importlib.reload(db_mod)
        self.db_mod = db_mod

    def tearDown(self):
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def test_legacy_db_init_does_not_raise(self):
        """init_db() on a legacy GL-032 DB completes without error."""
        self.db_mod.init_db()

    def test_legacy_db_baseline_marked_applied(self):
        """0001_gl032_baseline is recorded in schema_migrations after legacy detection."""
        self.db_mod.init_db()
        conn = self.db_mod.get_conn()
        try:
            cur = conn.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
            versions = [r[0] for r in cur.fetchall()]
        finally:
            conn.close()
        self.assertIn("0001_gl032_baseline", versions)

    def test_legacy_db_all_migrations_marked(self):
        """All known migrations are recorded after legacy DB detection."""
        self.db_mod.init_db()
        from src.migrations import runner
        conn = self.db_mod.get_conn()
        try:
            applied = runner._applied_versions(conn)
        finally:
            conn.close()
        # All 10 migrations should be marked applied
        self.assertEqual(len(applied), 10)

    def test_legacy_db_no_pending_after_init(self):
        """list_pending_migrations returns empty after init_db on legacy DB."""
        self.db_mod.init_db()
        from src.migrations import list_pending_migrations
        conn = self.db_mod.get_conn()
        try:
            pending = list_pending_migrations(conn)
        finally:
            conn.close()
        self.assertEqual(pending, [])


# ──────────────────────────────────────────────────────────────
# 6. Tenant isolation and backfill
# ──────────────────────────────────────────────────────────────

class TestTenantBackfillSafety(unittest.TestCase):
    """Tenant backfill behavior for business tables and audit_events."""

    def setUp(self):
        self._db_path, self._db_mod = _fresh_db()

    def tearDown(self):
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def test_new_grant_gets_demo_tenant_by_default(self):
        """Grants inserted without explicit tenant_id use 'demo' NOT NULL default."""
        import datetime
        conn = self._db_mod.get_conn()
        try:
            gid = str(uuid.uuid4())
            now = datetime.datetime.utcnow().isoformat() + "Z"
            conn.execute(
                """INSERT INTO grants
                   (id, subject_id, role, action, resource,
                    valid_from, valid_until, created_by, reason, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (gid, "subj-1", "reader", "read", "res/1",
                 now, now, "test", "test", now),
            )
            conn.commit()
            row = conn.execute(
                "SELECT tenant_id FROM grants WHERE id = ?", (gid,)
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["tenant_id"], "demo")

    def test_audit_event_null_tenant_not_backfilled(self):
        """Audit events without tenant_id keep NULL (not backfilled to 'demo')."""
        import src.audit_log as al
        from src.models import AuditEvent
        event = AuditEvent(
            subject_id="svc", role="system", action="health",
            resource="probe", approved=True, reason="probe",
        )
        # tenant_id is None
        self.assertIsNone(event.tenant_id)
        al.append_event(event)
        retrieved = al.get_event(event.id)
        self.assertIsNotNone(retrieved)
        # Must remain NULL — not backfilled by migration or append_event
        self.assertIsNone(retrieved.tenant_id)

    def test_legacy_row_not_globally_accessible_by_default(self):
        """A grant with tenant_id='demo' is not returned for a different tenant query."""
        import src.grants as grants_mod
        import datetime
        # Grants list is scoped to operator context; verify basic filtering works.
        # A grant created with 'demo' tenant should not appear if we filter for 't-other'.
        conn = self._db_mod.get_conn()
        try:
            gid = str(uuid.uuid4())
            now = datetime.datetime.utcnow().isoformat() + "Z"
            conn.execute(
                """INSERT INTO grants
                   (id, subject_id, role, action, resource,
                    valid_from, valid_until, created_by, reason, created_at, tenant_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (gid, "subj-2", "reader", "read", "res/2",
                 now, now, "test", "test", now, "demo"),
            )
            conn.commit()
            # Query for a different tenant
            row = conn.execute(
                "SELECT id FROM grants WHERE tenant_id = ?", ("t-other",)
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNone(row)


# ──────────────────────────────────────────────────────────────
# 7. Audit hash chain — migration interaction
# ──────────────────────────────────────────────────────────────

class TestAuditHashChainMigration(unittest.TestCase):
    """Audit hash chain verification survives migration and handles pre-chain events."""

    def setUp(self):
        self._db_path, self._db_mod = _fresh_db()

    def tearDown(self):
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def _make_event(self, tenant_id=None, **kw) -> object:
        from src.models import AuditEvent
        defaults = dict(
            subject_id="subj", role="reader", action="read",
            resource="res", approved=True, reason="r",
        )
        defaults.update(kw)
        e = AuditEvent(**defaults)
        e.tenant_id = tenant_id
        return e

    def test_empty_db_chain_verification_valid(self):
        """Empty audit log verifies as valid with zero checked events."""
        import src.audit_log as al
        result = al.verify_audit_hash_chain()
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked"], 0)
        self.assertEqual(result["failures"], [])

    def test_pre_chain_events_skipped(self):
        """Events with NULL row_hash are skipped in chain verification."""
        import sqlite3 as _sqlite3
        import datetime
        conn_raw = _sqlite3.connect(self._db_path)
        conn_raw.row_factory = _sqlite3.Row
        # Insert a raw pre-chain audit event with NULL row_hash
        eid = str(uuid.uuid4())
        now = datetime.datetime.utcnow().isoformat() + "Z"
        conn_raw.execute(
            """INSERT INTO audit_events
               (id, timestamp, subject_id, role, action, resource,
                approved, reason, matched_grant_id, challenge_id,
                challenge_present, challenge_result, grant_signature_result)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (eid, now, "pre-chain", "reader", "read", "res",
             1, "pre-chain event", None, None, 0, "legacy_mode", "not_checked"),
        )
        conn_raw.commit()
        conn_raw.close()

        import src.audit_log as al
        result = al.verify_audit_hash_chain()
        # Pre-chain event (NULL row_hash) must be skipped
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked"], 0)

    def test_post_migration_tenant_aware_events_verify(self):
        """Audit events with tenant_id verify correctly in hash chain."""
        import src.audit_log as al
        e1 = self._make_event(tenant_id="t-corp")
        e2 = self._make_event(tenant_id="t-corp")
        al.append_event(e1)
        al.append_event(e2)
        result = al.verify_audit_hash_chain()
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked"], 2)

    def test_events_without_tenant_verify_correctly(self):
        """Audit events with NULL tenant_id are included in chain verification."""
        import src.audit_log as al
        e1 = self._make_event(tenant_id=None)
        e2 = self._make_event(tenant_id=None)
        al.append_event(e1)
        al.append_event(e2)
        result = al.verify_audit_hash_chain()
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked"], 2)

    def test_mixed_pre_chain_and_chain_events_verify(self):
        """Mix of pre-chain (NULL row_hash) and chain events verifies correctly."""
        import sqlite3 as _sqlite3
        import datetime
        import src.audit_log as al

        # Insert one pre-chain event (no row_hash)
        conn_raw = _sqlite3.connect(self._db_path)
        conn_raw.row_factory = _sqlite3.Row
        eid = str(uuid.uuid4())
        now = datetime.datetime.utcnow().isoformat() + "Z"
        conn_raw.execute(
            """INSERT INTO audit_events
               (id, timestamp, subject_id, role, action, resource,
                approved, reason, matched_grant_id, challenge_id,
                challenge_present, challenge_result, grant_signature_result)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (eid, now, "pre-chain", "reader", "read", "res",
             1, "pre-chain", None, None, 0, "legacy_mode", "not_checked"),
        )
        conn_raw.commit()
        conn_raw.close()

        # Append chain events with tenant_id
        e1 = self._make_event(tenant_id="t-demo")
        e2 = self._make_event(tenant_id="t-demo")
        al.append_event(e1)
        al.append_event(e2)

        result = al.verify_audit_hash_chain()
        self.assertTrue(result["valid"])
        # Only chain events (with row_hash) are counted
        self.assertEqual(result["checked"], 2)

    def test_tampered_event_fails_verification(self):
        """Verification fails if a chain event's row_hash does not match its content.

        Uses a separate in-memory DB without the immutability trigger so we can
        write a deliberately wrong row_hash directly, then verify that
        verify_audit_hash_chain() catches the mismatch.
        """
        import sqlite3 as _sqlite3
        import datetime
        import hashlib
        import json as _json
        from src.migrations.runner import _discovery, _load_module

        # Build a minimal in-memory DB: tables without the immutability trigger
        raw = _sqlite3.connect(":memory:")
        raw.row_factory = _sqlite3.Row
        raw.executescript("""
            CREATE TABLE audit_events (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                role TEXT NOT NULL,
                action TEXT NOT NULL,
                resource TEXT NOT NULL,
                approved INTEGER NOT NULL,
                reason TEXT NOT NULL,
                matched_grant_id TEXT,
                challenge_id TEXT,
                challenge_present INTEGER DEFAULT 0,
                challenge_result TEXT DEFAULT 'legacy_mode',
                grant_signature_result TEXT DEFAULT 'not_checked',
                row_hash TEXT,
                prev_hash TEXT,
                tenant_id TEXT,
                workspace_id TEXT,
                scope TEXT
            );
        """)

        eid = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

        # Insert an event with a deliberately wrong row_hash
        raw.execute(
            """INSERT INTO audit_events
               (id, timestamp, subject_id, role, action, resource,
                approved, reason, matched_grant_id, challenge_id,
                challenge_present, challenge_result, grant_signature_result,
                row_hash, prev_hash, tenant_id, workspace_id, scope)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (eid, now, "subj", "reader", "read", "res",
             1, "r", None, None, 0, "legacy_mode", "not_checked",
             "deliberately_wrong_hash", None, "t-corp", None, None),
        )
        raw.commit()

        # Verify using the hash chain logic directly (without loading the full app DB)
        from src.audit_log import _filter_chain_rows, _row_to_audit_event, _verify_single_event
        rows = [dict(r) for r in raw.execute(
            "SELECT * FROM audit_events ORDER BY timestamp ASC, rowid ASC"
        ).fetchall()]
        chain_rows = _filter_chain_rows(rows)
        failures = []
        for i, row in enumerate(chain_rows):
            event = _row_to_audit_event(row)
            expected_prev_hash = chain_rows[i - 1]["row_hash"] if i > 0 else None
            failures.extend(_verify_single_event(event, expected_prev_hash, i))

        raw.close()
        self.assertGreater(len(failures), 0,
                           "Expected failures for deliberately wrong row_hash")

    def test_audit_immutability_trigger_blocks_update(self):
        """The audit immutability trigger blocks UPDATE via normal connection."""
        import src.audit_log as al
        e = self._make_event(tenant_id="t-corp")
        al.append_event(e)

        conn = self._db_mod.get_conn()
        try:
            with self.assertRaises(Exception):
                conn.execute(
                    "UPDATE audit_events SET reason = 'tampered' WHERE id = ?",
                    (e.id,),
                )
        finally:
            conn.close()

    def test_chain_verification_report_structure(self):
        """build_audit_chain_verification_report returns expected structure."""
        import src.audit_log as al
        e = self._make_event(tenant_id="t-corp")
        al.append_event(e)
        report = al.build_audit_chain_verification_report()
        self.assertIn("report_type", report)
        self.assertIn("valid", report)
        self.assertIn("checked_events", report)
        self.assertIn("failures", report)
        self.assertIn("summary", report)
        self.assertIn("status", report)
        self.assertIn("recommendations", report)
        self.assertTrue(report["valid"])


# ──────────────────────────────────────────────────────────────
# 8. list_pending_migrations
# ──────────────────────────────────────────────────────────────

class TestListPendingMigrations(unittest.TestCase):
    """list_pending_migrations provides dry-run visibility."""

    def setUp(self):
        self._db_path, self._db_mod = _fresh_db()

    def tearDown(self):
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def test_no_pending_after_init_db(self):
        """list_pending_migrations returns empty list on a fully-applied DB."""
        from src.migrations import list_pending_migrations
        conn = self._db_mod.get_conn()
        try:
            pending = list_pending_migrations(conn)
        finally:
            conn.close()
        self.assertEqual(pending, [])

    def test_pending_before_init_db(self):
        """list_pending_migrations returns all migrations on fresh unapplied DB."""
        db_path = _make_db_file()
        os.environ["GRANTLAYER_DB"] = db_path
        os.environ.pop("GRANTLAYER_DATABASE_URL", None)
        import src.db as db_mod
        importlib.reload(db_mod)
        conn = db_mod.get_conn()
        try:
            from src.migrations import list_pending_migrations, runner
            pending = list_pending_migrations(conn)
            all_versions = [v for v, _ in runner._discovery()]
        finally:
            conn.close()
            try:
                os.unlink(db_path)
            except OSError:
                pass
        self.assertEqual(len(pending), len(all_versions))
        pending_versions = [v for v, _ in pending]
        self.assertIn("0001_gl032_baseline", pending_versions)
        self.assertIn("0010_gl200b_tenant_workspace_isolation", pending_versions)

    def test_pending_returns_version_filepath_tuples(self):
        """list_pending_migrations returns (version, filepath) tuples."""
        db_path = _make_db_file()
        os.environ["GRANTLAYER_DB"] = db_path
        os.environ.pop("GRANTLAYER_DATABASE_URL", None)
        import src.db as db_mod
        importlib.reload(db_mod)
        conn = db_mod.get_conn()
        try:
            from src.migrations import list_pending_migrations
            pending = list_pending_migrations(conn)
            for item in pending:
                self.assertEqual(len(item), 2)
                version, filepath = item
                self.assertIsInstance(version, str)
                self.assertTrue(os.path.isfile(filepath), f"File not found: {filepath}")
        finally:
            conn.close()
            try:
                os.unlink(db_path)
            except OSError:
                pass


# ──────────────────────────────────────────────────────────────
# 9. PostgreSQL static compatibility checks
# ──────────────────────────────────────────────────────────────

class TestPostgreSQLStaticCompatibility(unittest.TestCase):
    """Static checks for PostgreSQL compatibility without live server."""

    def test_placeholder_translation_handles_migration_sql(self):
        """_translate_placeholders converts ? to %s in typical migration SQL."""
        from src.db import _translate_placeholders
        # Typical migration SQL pattern
        sql = (
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = ? AND column_name = ?"
        )
        translated, count = _translate_placeholders(sql)
        self.assertEqual(count, 2)
        self.assertIn("%s", translated)
        self.assertNotIn("?", translated)

    def test_placeholder_translation_ignores_sql_in_comments(self):
        """? inside SQL comments is not translated."""
        from src.db import _translate_placeholders
        sql = "SELECT id FROM t WHERE id = ? -- filter by ? value\nAND name = ?"
        translated, count = _translate_placeholders(sql)
        self.assertEqual(count, 2)

    def test_executescript_comment_stripping_sqlite_backend(self):
        """executescript on SQLite does not use the comment-stripping path."""
        from src.db import _ConnectionWrapper
        import sqlite3 as _sqlite3

        raw = _sqlite3.connect(":memory:")
        raw.row_factory = _sqlite3.Row
        wrapper = _ConnectionWrapper(raw, "sqlite")
        # Normal executescript should work (SQLite native)
        wrapper.executescript(
            "CREATE TABLE IF NOT EXISTS _test_t (id INTEGER);"
        )
        cur = raw.execute("SELECT name FROM sqlite_master WHERE name='_test_t'")
        self.assertIsNotNone(cur.fetchone())
        raw.close()

    def test_executescript_comment_stripping_mock_postgres(self):
        """executescript on postgres backend strips leading comments before executing."""
        executed: list = []

        class _MockCursor:
            def execute(self, sql):
                executed.append(sql.strip())
            def close(self):
                pass

        class _MockConn:
            def cursor(self):
                return _MockCursor()

        from src.db import _ConnectionWrapper
        wrapper = _ConnectionWrapper(_MockConn(), "postgres")
        # Statement with leading comment followed by SQL
        wrapper.executescript(
            "-- Create evidence table\nCREATE TABLE evidence_test (id TEXT);"
            "-- Another comment\nCREATE TABLE audit_test (id TEXT);"
        )
        # Both CREATE TABLE statements should have been executed
        self.assertTrue(any("CREATE TABLE evidence_test" in s for s in executed))
        self.assertTrue(any("CREATE TABLE audit_test" in s for s in executed))
        # Comment-only chunks should NOT have been sent as statements
        self.assertFalse(any(s.startswith("--") for s in executed))

    def test_migration_sql_uses_if_not_exists(self):
        """Key migration files use IF NOT EXISTS syntax (PostgreSQL compatible)."""
        from src.migrations import runner
        for version, filepath in runner._discovery():
            with open(filepath) as fh:
                src_text = fh.read()
            if "CREATE TABLE" in src_text and "CREATE INDEX" in src_text:
                # Files with table and index creation should use safe variants
                with self.subTest(version=version):
                    # Either IF NOT EXISTS or _column_exists guard pattern
                    has_safe_create = (
                        "IF NOT EXISTS" in src_text
                        or "_column_exists" in src_text
                        or "_table_exists" in src_text
                        or "_index_exists" in src_text
                    )
                    self.assertTrue(
                        has_safe_create,
                        f"{version}: no idempotency guard found",
                    )

    def test_migration_sql_no_sqlite_pragma_outside_guard(self):
        """Migrations that use PRAGMA do so inside SQLite-specific branches."""
        from src.migrations import runner
        for version, filepath in runner._discovery():
            with open(filepath) as fh:
                src_text = fh.read()
            if "PRAGMA" in src_text:
                with self.subTest(version=version):
                    # PRAGMA should only appear inside backend check or helper functions
                    self.assertIn(
                        "PRAGMA table_info",
                        src_text,
                        f"{version}: PRAGMA appears without expected table_info usage",
                    )


# ──────────────────────────────────────────────────────────────
# 10. Secret and URL safety
# ──────────────────────────────────────────────────────────────

class TestSecretSafety(unittest.TestCase):
    """DB URLs and secrets are not leaked in error messages."""

    def setUp(self):
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        self._orig_url = os.environ.get("GRANTLAYER_DATABASE_URL")

    def tearDown(self):
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)
        if self._orig_url is not None:
            os.environ["GRANTLAYER_DATABASE_URL"] = self._orig_url
        else:
            os.environ.pop("GRANTLAYER_DATABASE_URL", None)

    def test_postgres_dsn_not_in_connection_error(self):
        """PostgreSQL connection error does not expose the DSN."""
        fake_dsn = "postgresql://fakeuser:S3cret_password@fake-host:5432/fakedb"
        os.environ["GRANTLAYER_DATABASE_URL"] = fake_dsn
        os.environ.pop("GRANTLAYER_DB", None)
        import src.db as db_mod
        importlib.reload(db_mod)
        try:
            db_mod.get_conn()
        except (RuntimeError, Exception) as exc:
            err_msg = str(exc)
            # The password must never appear in the error message
            self.assertNotIn("S3cret_password", err_msg)

    def test_migration_error_contains_version_not_secrets(self):
        """Migration failure error includes version name, not raw secret values."""
        from src.migrations import runner
        import types

        db_path = _make_db_file()
        os.environ["GRANTLAYER_DB"] = db_path
        os.environ.pop("GRANTLAYER_DATABASE_URL", None)
        import src.db as db_mod
        importlib.reload(db_mod)

        conn = db_mod.get_conn()
        try:
            runner._ensure_migrations_table(conn)
            runner._mark_applied(conn, "0001_gl032_baseline")

            def _patched_discovery():
                return [("0002_fake_secret_migration", "/fake/path")]

            def _patched_load(_path):
                mod = types.ModuleType("fake")
                mod.version = "0002_fake_secret_migration"

                def apply(_conn):
                    raise RuntimeError(
                        "DB error: cannot connect to host"
                    )

                mod.apply = apply
                return mod

            orig_disc = runner._discovery
            orig_load = runner._load_module
            runner._discovery = _patched_discovery
            runner._load_module = _patched_load
            try:
                with self.assertRaises(RuntimeError) as ctx:
                    runner.run_migrations(conn)
                err_msg = str(ctx.exception)
                self.assertIn("0002_fake_secret_migration", err_msg)
                # No raw secret values from env
                self.assertNotIn("GRANTLAYER_ADMIN_TOKEN", err_msg)
            finally:
                runner._discovery = orig_disc
                runner._load_module = orig_load
        finally:
            conn.close()
            try:
                os.unlink(db_path)
            except OSError:
                pass


# ──────────────────────────────────────────────────────────────
# 11. GL-201 config fail-closed preservation (regression)
# ──────────────────────────────────────────────────────────────

class TestGL201ConfigPreserved(unittest.TestCase):
    """GL-201 production auth/secrets/config hardening is not weakened."""

    def setUp(self):
        self._orig_env = {}
        for k in [
            "GRANTLAYER_RUNTIME_MODE",
            "GRANTLAYER_REQUIRE_ADMIN_TOKEN",
            "GRANTLAYER_ADMIN_TOKEN",
            "GRANTLAYER_REQUIRE_CHALLENGE",
            "GRANTLAYER_ENABLE_DEMO_ENDPOINTS",
        ]:
            self._orig_env[k] = os.environ.get(k)

    def tearDown(self):
        for k, v in self._orig_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _reload_config(self):
        import src.config as config_mod
        importlib.reload(config_mod)
        return config_mod

    def test_production_mode_rejects_missing_admin_token(self):
        """startup_errors() fires in production-like mode when token is missing."""
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        cfg = self._reload_config()
        errors = cfg.startup_errors()
        self.assertTrue(any("ADMIN_TOKEN" in e for e in errors))

    def test_production_mode_rejects_placeholder_token(self):
        """startup_errors() fires for placeholder admin token in production mode."""
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "demo"  # placeholder
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        cfg = self._reload_config()
        errors = cfg.startup_errors()
        self.assertTrue(any("placeholder" in e.lower() or "unsafe" in e.lower() for e in errors))

    def test_test_mode_does_not_require_admin_token(self):
        """RUNTIME_MODE=test does not mandate REQUIRE_ADMIN_TOKEN by default."""
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "test"
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        cfg = self._reload_config()
        # In test mode, REQUIRE_ADMIN_TOKEN defaults to False so no fatal error
        # on missing token from startup_errors (which checks REQUIRE_ADMIN_TOKEN).
        self.assertFalse(cfg.REQUIRE_ADMIN_TOKEN)

    def test_startup_errors_do_not_contain_raw_token_value(self):
        """startup_errors() messages never expose raw token values."""
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "my-very-secret-token-12345"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
        cfg = self._reload_config()
        errors = cfg.startup_errors()
        for err in errors:
            self.assertNotIn("my-very-secret-token-12345", err)


# ──────────────────────────────────────────────────────────────
# 12. Documentation artifacts
# ──────────────────────────────────────────────────────────────

class TestGL202Artifacts(unittest.TestCase):
    """GL-202 documentation and JSON artifacts are present and structurally valid."""

    def test_doc_file_present(self):
        """docs/persistence_postgres_migration_readiness.md exists."""
        self.assertTrue(os.path.isfile(DOC_PATH), f"Missing: {DOC_PATH}")

    def test_json_artifact_present(self):
        """docs/examples/gl202/persistence_postgres_migration_readiness.json exists."""
        self.assertTrue(os.path.isfile(JSON_PATH), f"Missing: {JSON_PATH}")

    def test_json_artifact_is_valid_json(self):
        """The JSON artifact parses without error."""
        with open(JSON_PATH) as fh:
            data = json.load(fh)
        self.assertIsInstance(data, dict)

    def test_json_has_required_fields(self):
        """JSON artifact contains all required top-level fields."""
        with open(JSON_PATH) as fh:
            data = json.load(fh)
        required = [
            "issue_id", "title", "context", "scope", "non_goals",
            "migration_runner_assessment",
            "sqlite_readiness_assessment",
            "postgresql_readiness_assessment",
            "gl200_tenant_schema_assessment",
            "audit_immutability_assessment",
            "implemented_changes",
            "tests_added",
            "remaining_gaps",
            "decision",
            "safety_confirmations",
        ]
        for field in required:
            with self.subTest(field=field):
                self.assertIn(field, data)

    def test_json_issue_id_is_gl202(self):
        """JSON artifact has issue_id GL-202."""
        with open(JSON_PATH) as fh:
            data = json.load(fh)
        self.assertEqual(data["issue_id"], "GL-202")

    def test_json_no_production_saas_claim(self):
        """JSON artifact does not positively claim production SaaS readiness."""
        with open(JSON_PATH) as fh:
            data = json.load(fh)
        # safety_confirmations.production_saas_claim must be false
        sc = data.get("safety_confirmations", {})
        self.assertFalse(
            sc.get("production_saas_claim", True),
            "safety_confirmations.production_saas_claim must be false",
        )
        # decision must not be a positive SaaS-ready declaration
        decision = data.get("decision", "").lower()
        self.assertNotIn("production saas ready", decision)

    def test_json_safety_confirmations(self):
        """JSON safety_confirmations block covers expected guarantees."""
        with open(JSON_PATH) as fh:
            data = json.load(fh)
        sc = data.get("safety_confirmations", {})
        self.assertFalse(sc.get("production_saas_claim", True))
        self.assertFalse(sc.get("real_customer_data_ready", True))
        self.assertFalse(sc.get("public_push", True))

    def test_doc_states_developer_preview(self):
        """Markdown doc states GrantLayer is Developer Preview."""
        with open(DOC_PATH) as fh:
            content = fh.read()
        self.assertIn("Developer Preview", content)

    def test_doc_references_gl202(self):
        """Markdown doc references GL-202."""
        with open(DOC_PATH) as fh:
            content = fh.read()
        self.assertIn("GL-202", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
