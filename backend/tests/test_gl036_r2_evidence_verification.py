"""Tests for GL-036-R2 Evidence Verification Core (GRA-71).

Covers:
 1. verify_execution returns missing_data when no bundle is persisted
 2. verify_execution returns valid for a correct, persisted bundle
 3. verify_execution returns invalid for a hash mismatch
 4. verify_execution returns unsupported_version for wrong canonicalVersion
 5. verify_execution returns invalid for structural incompleteness
 6. verify_execution updates last_verified_at and last_verification_status
 7. list_stored_bundles exposes lastVerifiedAt and lastVerificationStatus
 8. Stored verification status survives reload
"""

import os
import sys
import json
import unittest
import tempfile
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestEvidenceVerificationCore(unittest.TestCase):
    """GRA-71 — Evidence Verification Core tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.grants.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.audit.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

        import backend.src.auth.challenges as ch_mod
        importlib.reload(ch_mod)
        self.ch_mod = ch_mod

        import backend.src.demo.demo_action as demo_mod
        importlib.reload(demo_mod)
        self.demo_mod = demo_mod

        import backend.src.core.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        crypto_mod.ensure_demo_keypair()

        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import backend.src.grants.grant_executions as execs_mod
        importlib.reload(execs_mod)
        self.execs_mod = execs_mod

        import backend.src.evidence.evidence_bundle as eb_mod
        importlib.reload(eb_mod)
        self.eb_mod = eb_mod

        import backend.src.evidence.evidence_persistence as ep_mod
        importlib.reload(ep_mod)
        self.ep_mod = ep_mod

        import backend.src.evidence.evidence_verification as ev_mod
        importlib.reload(ev_mod)
        self.ev_mod = ev_mod

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
        from backend.src.core.models import Grant
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
        from backend.src.evidence.evidence_bundle import compute_evidence_hash
        bundle["evidenceHash"] = compute_evidence_hash(bundle)
        bundle["canonicalVersion"] = "gl-evidence-v1"
        bundle["hashAlgorithm"] = "sha256"
        return bundle

    def _store_bundle(self, execution_id="ex-1", **kwargs):
        bundle = self._build_test_bundle(execution_id=execution_id, **kwargs)
        self.ep_mod.store_bundle(execution_id, bundle)
        return bundle

    # ── GRA-71 Tests ─────────────────────────────────────────

    def test_01_verify_execution_missing_data(self):
        """verify_execution returns missing_data when no bundle exists."""
        result = self.ev_mod.verify_execution("nonexistent-exec")
        self.assertEqual(result["status"], "missing_data")
        self.assertEqual(result["executionId"], "nonexistent-exec")
        self.assertIn("verifiedAt", result)
        self.assertIn("reason", result)

    def test_02_verify_execution_valid(self):
        """verify_execution returns valid for a correct persisted bundle."""
        self._store_bundle("ex-valid")
        result = self.ev_mod.verify_execution("ex-valid")
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["executionId"], "ex-valid")
        self.assertIn("verifiedAt", result)
        self.assertIn("reason", result)

    def test_03_verify_execution_invalid_hash_mismatch(self):
        """verify_execution returns invalid when stored hash does not match."""
        bundle = self._build_test_bundle("ex-bad-hash")
        bundle["evidenceHash"] = "0" * 64
        self.ep_mod.store_bundle("ex-bad-hash", bundle)
        result = self.ev_mod.verify_execution("ex-bad-hash")
        self.assertEqual(result["status"], "invalid")
        self.assertIn("hash", result["reason"].lower())

    def test_04_verify_execution_unsupported_version(self):
        """verify_execution returns unsupported_version for wrong canonicalVersion."""
        bundle = self._build_test_bundle("ex-version")
        bundle["canonicalVersion"] = "gl-evidence-v999"
        bundle["evidenceHash"] = self.eb_mod.compute_evidence_hash(bundle)
        self.ep_mod.store_bundle("ex-version", bundle)
        result = self.ev_mod.verify_execution("ex-version")
        self.assertEqual(result["status"], "unsupported_version")
        self.assertIn("unsupported", result["reason"].lower())

    def test_05_verify_execution_invalid_incomplete(self):
        """verify_execution returns invalid when bundle is structurally incomplete."""
        bundle = self._build_test_bundle("ex-incomplete")
        # Remove execution section to break completeness
        del bundle["execution"]
        bundle["evidenceHash"] = self.eb_mod.compute_evidence_hash(bundle)
        self.ep_mod.store_bundle("ex-incomplete", bundle)
        result = self.ev_mod.verify_execution("ex-incomplete")
        self.assertEqual(result["status"], "invalid")
        self.assertIn("completeness", result["reason"].lower())

    def test_06_verify_updates_persistence(self):
        """verify_execution writes last_verified_at and last_verification_status."""
        self._store_bundle("ex-track")
        result = self.ev_mod.verify_execution("ex-track")
        self.assertEqual(result["status"], "valid")

        record = self.ep_mod.get_bundle_by_execution("ex-track")
        self.assertIsNotNone(record)
        self.assertIsNotNone(record.last_verified_at)
        self.assertEqual(record.last_verification_status, "valid")

    def test_07_list_stored_bundles_shows_verification(self):
        """list_stored_bundles exposes lastVerifiedAt and lastVerificationStatus."""
        self._store_bundle("ex-list")
        self.ev_mod.verify_execution("ex-list")

        result = self.ep_mod.list_stored_bundles()
        self.assertEqual(result["total"], 1)
        item = result["items"][0]
        self.assertIn("lastVerifiedAt", item)
        self.assertIn("lastVerificationStatus", item)
        self.assertEqual(item["lastVerificationStatus"], "valid")
        self.assertIsNotNone(item["lastVerifiedAt"])

    def test_08_status_survives_reload(self):
        """Verification status is persisted and survives a fresh read."""
        self._store_bundle("ex-survive")
        self.ev_mod.verify_execution("ex-survive")

        # Reload module (and thus DB connection) to ensure data is on disk
        importlib.reload(self.ep_mod)
        record = self.ep_mod.get_bundle_by_execution("ex-survive")
        self.assertIsNotNone(record)
        self.assertEqual(record.last_verification_status, "valid")
        self.assertIsNotNone(record.last_verified_at)


if __name__ == "__main__":
    unittest.main(verbosity=2)
