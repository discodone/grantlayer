"""Tests for GL-036-A Evidence Bundle Persistence Foundation (GRA-52).

Covers:
 1. Migration creates evidence_archives and evidence_hashes tables and indexes
 2. Migration is idempotent (rerunning does not fail)
 3. store_bundle persists a valid evidence bundle
 4. store_bundle rejects already-stored execution (duplicate handling)
 5. store_bundle rejects missing/invalid evidenceHash
 6. get_stored_bundle returns EvidenceBundle by archive ID
 7. get_stored_bundle returns None for missing archive
 8. get_bundle_by_execution returns EvidenceBundle by execution_id
 9. get_bundle_by_execution returns None for missing execution
10. get_bundle_by_hash returns EvidenceBundle by SHA-256
11. list_stored_bundles returns paginated archive summaries
12. list_stored_bundles filters by grant_id
13. stored bundle_json contains no secrets
14. db backend agnostic (SQLite verified inline, PostgreSQL via acceptance_postgres.sh)
"""

import os
import sys
import json
import unittest
import tempfile
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestEvidencePersistenceFoundation(unittest.TestCase):
    """GRA-52 — Evidence Persistence Foundation tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")

        import backend.src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

        import backend.src.challenges as ch_mod
        importlib.reload(ch_mod)
        self.ch_mod = ch_mod

        import backend.src.demo_action as demo_mod
        importlib.reload(demo_mod)
        self.demo_mod = demo_mod

        import backend.src.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        crypto_mod.ensure_demo_keypair()

        import backend.src.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import backend.src.grant_executions as execs_mod
        importlib.reload(execs_mod)
        self.execs_mod = execs_mod

        import backend.src.evidence_bundle as eb_mod
        importlib.reload(eb_mod)
        self.eb_mod = eb_mod

        import backend.src.evidence_persistence as ep_mod
        importlib.reload(ep_mod)
        self.ep_mod = ep_mod

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if "GRANTLAYER_DB" in os.environ:
            del os.environ["GRANTLAYER_DB"]

        for key, orig in [
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", self._orig_bootstrap_token),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    # ── Helpers ──────────────────────────────────────────────

    def _make_grant(self, **kwargs):
        from backend.src.models import Grant
        defaults = dict(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="admin",
            reason="Routine",
        )
        defaults.update(kwargs)
        g = Grant(**defaults)
        self.grants_mod.create_grant(g)
        return g

    def _build_test_bundle(self, execution_id="ex-1", grant_id=None, grant_request_id=None):
        """Build a minimal valid evidence bundle for persistence tests."""
        bundle = {
            "evidenceId": execution_id,
            "executionId": execution_id,
            "grantId": grant_id,
            "grantRequestId": grant_request_id,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": None,
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-01-01T00:00:00Z",
                "auditEventId": None,
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "generatedAt": "2026-01-01T00:00:00Z",
        }
        # Manually set hash metadata to match the expected format
        from backend.src.evidence_bundle import compute_evidence_hash
        bundle["evidenceHash"] = compute_evidence_hash(bundle)
        bundle["canonicalVersion"] = "gl-evidence-v1"
        bundle["hashAlgorithm"] = "sha256"
        return bundle

    # ── GRA-52 Tests ─────────────────────────────────────────

    def test_01_migration_creates_tables_and_indexes(self):
        """Migration 0002 creates evidence_archives and evidence_hashes with indexes."""
        conn = self.db_mod.get_conn()
        try:
            # evidence_archives exists
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='evidence_archives'"
            ).fetchone()
            self.assertIsNotNone(row)

            # evidence_hashes exists
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='evidence_hashes'"
            ).fetchone()
            self.assertIsNotNone(row)

            # check columns in evidence_archives
            cols = conn.execute("PRAGMA table_info(evidence_archives)").fetchall()
            col_names = {c[1] for c in cols}
            expected = {
                "id", "evidence_hash", "canonical_version", "hash_algorithm",
                "bundle_json", "execution_id", "grant_id", "grant_request_id",
                "created_at", "stored_by",
            }
            self.assertTrue(expected.issubset(col_names), f"Missing columns: {expected - col_names}")

            # indexes exist
            indexes = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='evidence_archives'"
            ).fetchall()
            idx_names = {r[0] for r in indexes}
            self.assertIn("idx_evidence_archives_grant_id", idx_names)
            self.assertIn("idx_evidence_archives_execution_id", idx_names)
            self.assertIn("idx_evidence_archives_created_at", idx_names)

            idx_names_hashes = {
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='evidence_hashes'"
                ).fetchall()
            }
            self.assertIn("idx_evidence_hashes_archive_id", idx_names_hashes)
        finally:
            conn.close()

    def test_02_migration_is_idempotent(self):
        """Rerunning init_db (and thus migration) does not fail or duplicate."""
        # init_db was already called in setUp. Call again.
        self.db_mod.init_db()
        # Verify only one record per evidence archive still possible
        conn = self.db_mod.get_conn()
        try:
            rows = conn.execute("SELECT COUNT(*) FROM evidence_archives").fetchone()
            self.assertEqual(rows[0], 0)
        finally:
            conn.close()

    def test_03_store_bundle_persists_valid_bundle(self):
        """store_bundle saves a valid evidence bundle and returns ok metadata."""
        bundle = self._build_test_bundle(execution_id="ex-valid")
        result = self.ep_mod.store_bundle("ex-valid", bundle)
        self.assertTrue(result["ok"])
        self.assertEqual(result["archiveId"], "ex-valid")
        self.assertEqual(result["executionId"], "ex-valid")
        self.assertEqual(result["evidenceHash"], bundle["evidenceHash"])
        self.assertIn("storedAt", result)

    def test_04_store_bundle_rejects_duplicate(self):
        """store_bundle rejects already-stored execution with already_stored error."""
        bundle = self._build_test_bundle(execution_id="ex-dup")
        r1 = self.ep_mod.store_bundle("ex-dup", bundle)
        self.assertTrue(r1["ok"])

        r2 = self.ep_mod.store_bundle("ex-dup", bundle)
        self.assertFalse(r2["ok"])
        self.assertEqual(r2["error"], "already_stored")
        self.assertEqual(r2["archiveId"], "ex-dup")

    def test_05_store_bundle_rejects_invalid_hash(self):
        """store_bundle rejects bundle missing or with invalid evidenceHash."""
        bundle = self._build_test_bundle(execution_id="ex-bad")
        del bundle["evidenceHash"]
        result = self.ep_mod.store_bundle("ex-bad", bundle)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "invalid_bundle")

    def test_06_get_stored_bundle_returns_bundle(self):
        """get_stored_bundle loads EvidenceBundle by archive ID."""
        bundle = self._build_test_bundle(execution_id="ex-get")
        self.ep_mod.store_bundle("ex-get", bundle)

        record = self.ep_mod.get_stored_bundle("ex-get")
        self.assertIsNotNone(record)
        self.assertEqual(record.id, "ex-get")
        self.assertEqual(record.execution_id, "ex-get")
        self.assertEqual(record.evidence_hash, bundle["evidenceHash"])
        self.assertEqual(record.canonical_version, "gl-evidence-v1")
        self.assertEqual(record.hash_algorithm, "sha256")

    def test_07_get_stored_bundle_returns_none_for_missing(self):
        """get_stored_bundle returns None for nonexistent archive ID."""
        record = self.ep_mod.get_stored_bundle("nonexistent-id")
        self.assertIsNone(record)

    def test_08_get_bundle_by_execution(self):
        """get_bundle_by_execution returns EvidenceBundle by execution_id."""
        bundle = self._build_test_bundle(execution_id="ex-exec")
        self.ep_mod.store_bundle("ex-exec", bundle)

        record = self.ep_mod.get_bundle_by_execution("ex-exec")
        self.assertIsNotNone(record)
        self.assertEqual(record.execution_id, "ex-exec")

    def test_09_get_bundle_by_execution_none_for_missing(self):
        """get_bundle_by_execution returns None for missing execution."""
        record = self.ep_mod.get_bundle_by_execution("no-such-exec")
        self.assertIsNone(record)

    def test_10_get_bundle_by_hash(self):
        """get_bundle_by_hash returns EvidenceBundle by SHA-256 evidence hash."""
        bundle = self._build_test_bundle(execution_id="ex-hash")
        self.ep_mod.store_bundle("ex-hash", bundle)
        expected_hash = bundle["evidenceHash"]

        record = self.ep_mod.get_bundle_by_hash(expected_hash)
        self.assertIsNotNone(record)
        self.assertEqual(record.evidence_hash, expected_hash)
        self.assertEqual(record.execution_id, "ex-hash")

    def test_11_list_stored_bundles_paginated(self):
        """list_stored_bundles returns paginated summaries."""
        for i in range(5):
            bundle = self._build_test_bundle(execution_id=f"ex-list-{i}")
            self.ep_mod.store_bundle(f"ex-list-{i}", bundle)

        result = self.ep_mod.list_stored_bundles(limit=3, offset=0)
        self.assertEqual(len(result["items"]), 3)
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["limit"], 3)
        self.assertEqual(result["offset"], 0)

        # Page 2
        result2 = self.ep_mod.list_stored_bundles(limit=3, offset=3)
        self.assertEqual(len(result2["items"]), 2)
        self.assertEqual(result2["offset"], 3)

    def test_12_list_stored_bundles_filter_by_grant_id(self):
        """list_stored_bundles filters by grant_id."""
        bundle_a = self._build_test_bundle(execution_id="ex-grant-a", grant_id="grant-a")
        bundle_b = self._build_test_bundle(execution_id="ex-grant-b", grant_id="grant-b")
        self.ep_mod.store_bundle("ex-grant-a", bundle_a)
        self.ep_mod.store_bundle("ex-grant-b", bundle_b)

        result = self.ep_mod.list_stored_bundles(grant_id="grant-a")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["grantId"], "grant-a")

    def test_13_stored_bundle_secret_free(self):
        """Stored bundle_json contains no secrets (Bearer, token_hash, salt, GRANTLAYER_)."""
        bundle = self._build_test_bundle(execution_id="ex-secret")
        self.ep_mod.store_bundle("ex-secret", bundle)

        record = self.ep_mod.get_stored_bundle("ex-secret")
        self.assertIsNotNone(record)
        raw = record.bundle_json
        self.assertNotIn("Bearer", raw)
        self.assertNotIn("token_hash", raw)
        self.assertNotIn("salt", raw)
        self.assertNotIn("GRANTLAYER_", raw)

    def test_14_db_backend_agnostic_sqlite(self):
        """All operations succeed on SQLite backend (default)."""
        bundle = self._build_test_bundle(execution_id="ex-sqlite")
        result = self.ep_mod.store_bundle("ex-sqlite", bundle)
        self.assertTrue(result["ok"])
        self.assertIsNotNone(self.ep_mod.get_stored_bundle("ex-sqlite"))
        self.assertIsNotNone(self.ep_mod.get_bundle_by_execution("ex-sqlite"))
        self.assertIsNotNone(self.ep_mod.get_bundle_by_hash(bundle["evidenceHash"]))
        self.assertEqual(self.ep_mod.list_stored_bundles()["total"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
