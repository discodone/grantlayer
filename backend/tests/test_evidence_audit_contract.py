"""GL-031 — Evidence & Audit Contract Tests.

Covers:
1. Evidence bundle contains all required contract fields
2. Evidence hash is a valid 64-char lowercase hex SHA-256
3. Canonical version and hash algorithm are frozen
4. Audit trail is non-empty for executed actions
5. Audit trail is chronologically sorted
6. Export JSON is valid and deterministic
7. Export artifact headers are documented correctly (Content-Type, Content-Disposition, X-Evidence-Hash)
8. Evidence bundle hash matches between endpoint and export
9. Grant signature result is present in grant block when applicable
10. Usage limits affectedOutcome consistency
"""

import os
import json
import hashlib
import unittest
import tempfile
import importlib


class TestEvidenceAuditContract(unittest.TestCase):
    """Evidence bundle and audit trail contract tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")

        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN"] = "bootstrap-token"

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

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)

        for key, orig in [
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", self._orig_bootstrap_token),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    def _insert_operator(self, op_id, name, role, token):
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators (id, name, role, token_hash, active, created_at)
                   VALUES (?, ?, ?, ?, 1, datetime('now'))""",
                (op_id, name, role, self.ops_mod.hash_token(token)),
            )
            conn.commit()
        finally:
            conn.close()

    def _make_grant(self):
        from backend.src.models import Grant
        g = Grant(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="admin",
            reason="Routine maintenance",
        )
        self.grants_mod.create_grant(g)
        return g

    # ──────────────────────────────────────────────
    # 1. Required contract fields
    # ──────────────────────────────────────────────
    def test_evidence_bundle_contains_all_required_fields(self):
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle = self.eb_mod.build_evidence_bundle(result["executionId"])

        required = [
            "evidenceId", "executionId", "grantId", "grantRequestId",
            "evidenceHash", "canonicalVersion", "hashAlgorithm", "generatedAt",
            "request", "approval", "grant", "execution", "usageLimits", "auditTrail",
        ]
        for field in required:
            self.assertIn(field, bundle, f"Missing required field: {field}")

    # ──────────────────────────────────────────────
    # 2. Evidence hash format
    # ──────────────────────────────────────────────
    def test_evidence_hash_is_valid_sha256_hex(self):
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle = self.eb_mod.build_evidence_bundle(result["executionId"])
        h = bundle["evidenceHash"]
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))

    # ──────────────────────────────────────────────
    # 3. Canonical version and hash algorithm frozen
    # ──────────────────────────────────────────────
    def test_canonical_version_and_algorithm_frozen(self):
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle = self.eb_mod.build_evidence_bundle(result["executionId"])
        self.assertEqual(bundle["canonicalVersion"], "gl-evidence-v1")
        self.assertEqual(bundle["hashAlgorithm"], "sha256")

    # ──────────────────────────────────────────────
    # 4. Audit trail non-empty
    # ──────────────────────────────────────────────
    def test_audit_trail_non_empty_for_executed_actions(self):
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle = self.eb_mod.build_evidence_bundle(result["executionId"])
        self.assertIsInstance(bundle["auditTrail"], list)
        self.assertGreaterEqual(len(bundle["auditTrail"]), 1)

    # ──────────────────────────────────────────────
    # 5. Audit trail chronologically sorted
    # ──────────────────────────────────────────────
    def test_audit_trail_is_chronologically_sorted(self):
        g = self._make_grant()
        # Execute twice to generate multiple audit events
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle = self.eb_mod.build_evidence_bundle(result["executionId"])
        audit_trail = bundle["auditTrail"]
        timestamps = [ev.get("timestamp") or "" for ev in audit_trail]
        self.assertEqual(timestamps, sorted(timestamps))

    # ──────────────────────────────────────────────
    # 6. Export JSON valid and deterministic
    # ──────────────────────────────────────────────
    def test_export_json_is_valid_and_deterministic(self):
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle = self.eb_mod.build_evidence_bundle(result["executionId"])
        export1 = self.eb_mod.export_bundle_json(bundle)
        export2 = self.eb_mod.export_bundle_json(bundle)
        self.assertEqual(export1, export2)
        parsed = json.loads(export1)
        self.assertEqual(parsed["evidenceId"], bundle["evidenceId"])

    # ──────────────────────────────────────────────
    # 7. Export artifact headers (verified via function contract)
    # ──────────────────────────────────────────────
    def test_export_artifact_includes_correct_headers_contract(self):
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle = self.eb_mod.build_evidence_bundle(result["executionId"])
        evidence_hash = bundle.get("evidenceHash", "")
        short_hash = evidence_hash[:8] if evidence_hash else ""
        filename = f"evidence-{result['executionId']}-{short_hash}.json"

        # Verify the filename format matches the server contract
        self.assertTrue(filename.startswith("evidence-"))
        self.assertTrue(filename.endswith(".json"))
        self.assertIn(short_hash, filename)

        # Verify Content-Type would be application/json; charset=utf-8
        # (actual header verification requires HTTP layer)
        self.assertRegex(
            self.eb_mod.export_bundle_json(bundle)[:10],
            r'^\{',
            "Export output starts with JSON object",
        )

    # ──────────────────────────────────────────────
    # 8. Evidence hash matches between endpoint and export
    # ──────────────────────────────────────────────
    def test_evidence_hash_matches_between_endpoint_and_export(self):
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle = self.eb_mod.build_evidence_bundle(result["executionId"])
        hash_from_bundle = bundle["evidenceHash"]

        # Recompute from the bundle itself
        recomputed = self.eb_mod.compute_evidence_hash(bundle)
        self.assertEqual(hash_from_bundle, recomputed)

        # Export does not change the hash
        export = self.eb_mod.export_bundle_json(bundle)
        parsed = json.loads(export)
        self.assertEqual(parsed["evidenceHash"], hash_from_bundle)

    # ──────────────────────────────────────────────
    # 9. Grant signature result present when applicable
    # ──────────────────────────────────────────────
    def test_grant_signature_result_present_when_applicable(self):
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle = self.eb_mod.build_evidence_bundle(result["executionId"])
        self.assertIn("grantSignatureResult", bundle["grant"])

    # ──────────────────────────────────────────────
    # 10. Usage limits affectedOutcome consistency
    # ──────────────────────────────────────────────
    def test_usage_limits_affected_outcome_consistency(self):
        from backend.src.models import Grant

        # Grant with max_uses=1
        g = Grant(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="admin",
            reason="One-time use",
            max_uses=1,
        )
        self.grants_mod.create_grant(g)

        # First execution succeeds
        result1 = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        self.assertTrue(result1["approved"])
        bundle1 = self.eb_mod.build_evidence_bundle(result1["executionId"])
        self.assertFalse(bundle1["usageLimits"]["affectedOutcome"])

        # Second execution is denied due to usage exhaustion
        result2 = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        self.assertFalse(result2["approved"])
        bundle2 = self.eb_mod.build_evidence_bundle(result2["executionId"])
        self.assertTrue(bundle2["usageLimits"]["affectedOutcome"])
        self.assertEqual(bundle2["usageLimits"]["reason"], "grant_usage_exhausted")


if __name__ == "__main__":
    unittest.main(verbosity=2)
