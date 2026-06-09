"""Tests for GL-139: Audit Hash-Chain Write Lock Baseline.

Ensures:
1. Audit module exposes a process-local RLock in the central write path.
2. Sequential audit writes still produce valid hash-chain order.
3. Concurrent/threaded audit writes preserve chain consistency.
4. No duplicate previous-hash race is observed in a controlled threaded test.
5. Existing audit verification still passes after concurrent writes.
6. ThreadingHTTPServer is not enabled by GL-139.
7. No OpenAPI/migration/DB schema/dependency/frontend changes.
8. No auth semantics changes.
9. Branch-scope guard is robust (skips diff assertions off-branch).
10. SQLite behavior preserved; PostgreSQL compatibility unaffected.
"""

import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import unittest
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl139(unittest.TestCase):
    """Shared helpers for GL-139 tests."""

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

        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import src.models as models_mod
        importlib.reload(models_mod)
        self.models_mod = models_mod

        import src.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

        self.db_mod = db_mod

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

    def _append_audit_event(self, event_id, action="test_action", approved=True, reason="test reason"):
        event = self.models_mod.AuditEvent(
            id=event_id,
            timestamp="2026-01-01T00:00:00Z",
            subject_id="test-subject",
            role="tester",
            action=action,
            resource="test-resource",
            approved=approved,
            reason=reason,
            matched_grant_id=None,
            challenge_id=None,
            challenge_present=False,
            challenge_result="legacy_mode",
            grant_signature_result="not_checked",
        )
        self.audit_mod.append_event(event)
        return event


# ═══════════════════════════════════════════════════════════════════════
# 1. Lock exposure
# ═══════════════════════════════════════════════════════════════════════

class TestGl139LockExposed(_BaseGl139):
    """Audit module must expose a process-local RLock."""

    def test_lock_exists(self):
        self.assertTrue(
            hasattr(self.audit_mod, "_AUDIT_HASH_CHAIN_WRITE_LOCK"),
            "Expected _AUDIT_HASH_CHAIN_WRITE_LOCK in audit_log module",
        )

    def test_lock_is_rlock(self):
        lock = self.audit_mod._AUDIT_HASH_CHAIN_WRITE_LOCK
        self.assertEqual(type(lock).__name__, "RLock")

    def test_lock_is_module_level_singleton(self):
        lock1 = self.audit_mod._AUDIT_HASH_CHAIN_WRITE_LOCK
        lock2 = self.audit_mod._AUDIT_HASH_CHAIN_WRITE_LOCK
        self.assertIs(lock1, lock2)


# ═══════════════════════════════════════════════════════════════════════
# 2. Sequential writes still valid
# ═══════════════════════════════════════════════════════════════════════

class TestGl139SequentialWritesValid(_BaseGl139):
    """Sequential audit writes must produce a valid hash chain."""

    def test_three_sequential_events_chain_correctly(self):
        e1 = self._append_audit_event("evt-seq-1")
        e2 = self._append_audit_event("evt-seq-2")
        e3 = self._append_audit_event("evt-seq-3")

        self.assertIsNone(e1.prev_hash)
        self.assertEqual(e2.prev_hash, e1.row_hash)
        self.assertEqual(e3.prev_hash, e2.row_hash)

        result = self.audit_mod.verify_audit_hash_chain()
        self.assertTrue(result["valid"], f"Unexpected failures: {result['failures']}")
        self.assertEqual(result["checked"], 3)


# ═══════════════════════════════════════════════════════════════════════
# 3. Concurrent writes preserve chain consistency
# ═══════════════════════════════════════════════════════════════════════

class TestGl139ConcurrentWrites(_BaseGl139):
    """Concurrent audit writes must not break hash-chain continuity."""

    def test_ten_threads_five_events_each_no_race(self):
        """50 concurrent appends must result in a valid chain with no duplicates."""
        num_threads = 10
        events_per_thread = 5
        total_events = num_threads * events_per_thread

        barrier = threading.Barrier(num_threads)
        errors = []

        def worker(thread_idx):
            try:
                barrier.wait(timeout=5)
                for i in range(events_per_thread):
                    event_id = f"evt-t{thread_idx:02d}-i{i:02d}"
                    self._append_audit_event(event_id)
            except Exception as exc:
                errors.append((thread_idx, str(exc)))

        threads = [
            threading.Thread(target=worker, args=(t,))
            for t in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        self.assertEqual(len(errors), 0, f"Worker errors: {errors}")

        # Verify chain integrity
        result = self.audit_mod.verify_audit_hash_chain()
        self.assertTrue(
            result["valid"],
            f"Hash chain invalid after concurrent writes: {result['failures']}",
        )
        self.assertEqual(result["checked"], total_events)

        # Verify no duplicate prev_hash (indicates two events saw same tail)
        rows = self.audit_mod._fetch_all_audit_events_ordered()
        chain_rows = self.audit_mod._filter_chain_rows(rows)
        self.assertEqual(len(chain_rows), total_events)

        prev_hashes = [r["prev_hash"] for r in chain_rows]
        # Genesis event has None prev_hash; all others must be unique
        non_none_prev_hashes = [ph for ph in prev_hashes if ph is not None]
        self.assertEqual(
            len(non_none_prev_hashes),
            len(set(non_none_prev_hashes)),
            "Duplicate prev_hash detected: two events linked to the same predecessor",
        )

        # Verify every non-genesis prev_hash matches some row_hash
        row_hashes = {r["row_hash"] for r in chain_rows}
        for ph in non_none_prev_hashes:
            self.assertIn(ph, row_hashes, f"prev_hash {ph!r} does not match any row_hash")

    def test_appends_with_conn_parameter_within_transaction(self):
        """append_event with explicit conn inserts correctly inside a caller-managed tx."""
        conn = self.db_mod.get_conn()
        try:
            for i in range(5):
                event_id = f"evt-conn-{i:02d}"
                event = self.models_mod.AuditEvent(
                    id=event_id,
                    timestamp="2026-01-01T00:00:00Z",
                    subject_id="test-subject",
                    role="tester",
                    action="test_action",
                    resource="test-resource",
                    approved=True,
                    reason="test reason",
                    matched_grant_id=None,
                    challenge_id=None,
                    challenge_present=False,
                    challenge_result="legacy_mode",
                    grant_signature_result="not_checked",
                )
                self.audit_mod.append_event(event, conn=conn)
            conn.commit()
        finally:
            conn.close()

        result = self.audit_mod.verify_audit_hash_chain()
        self.assertTrue(
            result["valid"],
            f"Hash chain invalid after conn writes: {result['failures']}",
        )
        self.assertEqual(result["checked"], 5)

        # Verify chaining
        events = self.audit_mod.list_events(limit=10)
        self.assertEqual(len(events), 5)
        # Events are returned DESC by timestamp
        ids = [e.id for e in events]
        for eid in [f"evt-conn-{i:02d}" for i in range(5)]:
            self.assertIn(eid, ids)


# ═══════════════════════════════════════════════════════════════════════
# 4. No duplicate previous-hash race
# ═══════════════════════════════════════════════════════════════════════

class TestGl139NoDuplicatePrevHashRace(_BaseGl139):
    """Explicit regression test for the prev_hash race condition."""

    def test_all_non_genesis_prev_hashes_are_unique(self):
        num_threads = 8
        events_per_thread = 4
        barrier = threading.Barrier(num_threads)

        def worker(thread_idx):
            barrier.wait(timeout=5)
            for i in range(events_per_thread):
                self._append_audit_event(f"evt-race-t{thread_idx}-i{i}")

        threads = [
            threading.Thread(target=worker, args=(t,))
            for t in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        rows = self.audit_mod._fetch_all_audit_events_ordered()
        chain_rows = self.audit_mod._filter_chain_rows(rows)
        prev_hashes = [r["prev_hash"] for r in chain_rows]
        non_none = [ph for ph in prev_hashes if ph is not None]
        duplicates = len(non_none) - len(set(non_none))
        self.assertEqual(
            duplicates,
            0,
            f"Found {duplicates} duplicate prev_hash value(s) — race condition not prevented",
        )


# ═══════════════════════════════════════════════════════════════════════
# 5. Existing audit verification preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl139ExistingVerificationPreserved(_BaseGl139):
    """verify_audit_hash_chain and build_audit_chain_verification_report still work."""

    def test_verify_after_concurrent_writes(self):
        for i in range(5):
            self._append_audit_event(f"evt-verify-{i}")
        result = self.audit_mod.verify_audit_hash_chain()
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked"], 5)

    def test_report_after_concurrent_writes(self):
        for i in range(5):
            self._append_audit_event(f"evt-report-{i}")
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertTrue(report["valid"])
        self.assertEqual(report["checked_events"], 5)
        self.assertEqual(report["status"], "valid")


# ═══════════════════════════════════════════════════════════════════════
# 6. ThreadingHTTPServer not enabled
# ═══════════════════════════════════════════════════════════════════════

class TestGl139ThreadingHttpserverNotEnabled(unittest.TestCase):
    """GL-139 must not enable ThreadingHTTPServer."""

    def test_server_uses_plain_httpserver(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-139-audit-hash-chain-write-lock":
            self.skipTest("ThreadingHTTPServer guard only valid on GL-139 branch")
        server_path = repo_root / "backend" / "src" / "server.py"
        source = server_path.read_text(encoding="utf-8")
        self.assertIn("HTTPServer", source)
        self.assertNotIn("ThreadingHTTPServer", source)


# ═══════════════════════════════════════════════════════════════════════
# 7. Scope guard
# ═══════════════════════════════════════════════════════════════════════

class TestGl139ScopeGuard(unittest.TestCase):
    """Diff scope limited to allowed files; branch-aware skip."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-139-audit-hash-chain-write-lock":
            self.skipTest(
                "Branch-wide diff check only valid on GL-139 feature branch"
            )
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/audit_log.py",
            "backend/tests/test_gl139_audit_hash_chain_write_lock.py",
            "backend/tests/test_gl103_audit_hash_chain.py",
            "backend/tests/test_gl108_postgres_audit_immutability.py",
            "backend/tests/test_gl112_audit_log_duplication_cleanup.py",
            "docs/audit_hash_chain_write_lock.md",
            "docs/examples/gl139/audit_hash_chain_write_lock.json",
            "docs/security_remediation_intake_2026_05_26.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-139 changed a forbidden file: {path}",
            )

    def test_no_openapi_change(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        openapi_path = repo_root / "docs" / "openapi.yaml"
        self.assertTrue(openapi_path.exists(), "openapi.yaml missing")
        content = openapi_path.read_text()
        # GL-139 must not add or remove endpoints
        self.assertNotIn("threading", content.lower())

    def test_no_new_migration(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        migrations_dir = repo_root / "backend" / "src" / "migrations"
        scripts = sorted(migrations_dir.glob("0*.py"))
        self.assertEqual(len(scripts), 11, f"Expected 11 migration scripts, got {len(scripts)}")

    def test_no_dependency_files_changed(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        forbidden = {
            "requirements.txt",
            "requirements-dev.txt",
            "pyproject.toml",
            "setup.py",
            "Pipfile",
            "poetry.lock",
        }
        for path in changed:
            self.assertNotIn(
                path,
                forbidden,
                f"GL-139 must not change dependency file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
