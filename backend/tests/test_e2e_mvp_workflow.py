"""GL-031 — End-to-End MVP Workflow Tests.

Covers:
1. Full approval workflow: request -> approve -> execute -> evidence
2. Full denial workflow: request -> deny -> no grant created
3. Grant lifecycle: create grant -> execute -> revoke
4. Challenge-restricted execution succeeds with valid challenge
5. Challenge-restricted execution fails without challenge
"""

import os
import json
import unittest
import tempfile
import importlib


class TestE2EMvpWorkflow(unittest.TestCase):
    """End-to-end workflow tests across the full GrantLayer MVP chain."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")
        self._orig_require_challenge = os.environ.get("GRANTLAYER_REQUIRE_CHALLENGE")

        # Enable operator model for full workflow
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN"] = "bootstrap-token"
        os.environ.pop("GRANTLAYER_REQUIRE_CHALLENGE", None)

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

        import backend.src.grants.grant_requests as greps_mod
        importlib.reload(greps_mod)
        self.greps_mod = greps_mod

        import backend.src.grants.grant_executions as execs_mod
        importlib.reload(execs_mod)
        self.execs_mod = execs_mod

        import backend.src.evidence.evidence_bundle as eb_mod
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
            ("GRANTLAYER_REQUIRE_CHALLENGE", self._orig_require_challenge),
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
                   VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)""",
                (op_id, name, role, self.ops_mod.hash_token(token)),
            )
            conn.commit()
        finally:
            conn.close()

    # ──────────────────────────────────────────────
    # 1. Full approval workflow
    # ──────────────────────────────────────────────
    def test_full_approval_workflow(self):
        """request -> approve -> execute -> evidence bundle is complete."""
        from backend.src.core.models import GrantRequest

        # Insert two operators: requester and approver
        self._insert_operator("req-01", "Requester", "grant_admin", "token-req")
        self._insert_operator("app-01", "Approver", "owner", "token-app")

        # Step 1: Create grant request
        request = GrantRequest(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="req-01",
            reason="Routine maintenance",
        )
        created = self.greps_mod.create_grant_request(request, tenant_id="demo")
        self.assertEqual(created.status, "requested")

        # Step 2: Approve request
        updated, grant = self.greps_mod.approve_grant_request(created.id, "app-01", tenant_id="demo")
        self.assertEqual(updated.status, "approved")
        self.assertIsNotNone(updated.grant_id)
        self.assertIsNotNone(grant)

        # Step 3: Execute demo action
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertTrue(result["approved"], f"Demo action denied: {result}")
        self.assertIsNotNone(result["executionId"])

        # Step 4: Evidence bundle exists and is complete
        bundle = self.eb_mod.build_evidence_bundle(result["executionId"])
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle["evidenceId"], result["executionId"])
        self.assertEqual(bundle["grantId"], grant.id)
        self.assertEqual(bundle["grantRequestId"], created.id)
        self.assertIsNotNone(bundle["evidenceHash"])
        self.assertEqual(bundle["canonicalVersion"], "gl-evidence-v1")
        self.assertEqual(bundle["hashAlgorithm"], "sha256")

        # Request and approval sections present
        self.assertIsNotNone(bundle["request"])
        self.assertIsNotNone(bundle["approval"])
        self.assertEqual(bundle["approval"]["approvedBy"], "app-01")

        # Grant section present
        self.assertIsNotNone(bundle["grant"])
        self.assertEqual(bundle["grant"]["id"], grant.id)

        # Execution section present
        self.assertIsNotNone(bundle["execution"])
        self.assertEqual(bundle["execution"]["result"], "succeeded")

        # Audit trail present
        self.assertIsInstance(bundle["auditTrail"], list)
        self.assertGreaterEqual(len(bundle["auditTrail"]), 1)

        # Usage limits present
        self.assertIn("usageLimits", bundle)

    # ──────────────────────────────────────────────
    # 2. Full denial workflow
    # ──────────────────────────────────────────────
    def test_full_denial_workflow(self):
        """request -> deny -> no grant created -> execution denied."""
        from backend.src.core.models import GrantRequest

        self._insert_operator("req-01", "Requester", "grant_admin", "token-req")
        self._insert_operator("den-01", "Denier", "owner", "token-den")

        request = GrantRequest(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="req-01",
            reason="Routine maintenance",
        )
        created = self.greps_mod.create_grant_request(request, tenant_id="demo")

        # Deny the request
        updated = self.greps_mod.deny_grant_request(created.id, "den-01", "Not authorized", tenant_id="demo")
        self.assertEqual(updated.status, "denied")
        self.assertIsNone(updated.grant_id)

        # No grant exists, so execution should be denied
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertFalse(result["approved"])

        # Evidence bundle should NOT have a grant section
        bundle = self.eb_mod.build_evidence_bundle(result["executionId"])
        self.assertIsNotNone(bundle)
        self.assertIsNone(bundle["grant"])
        self.assertIsNone(bundle["grantId"])
        # No grant means no grantRequestId linkage -> request/approval are None
        self.assertIsNone(bundle["request"])
        self.assertIsNone(bundle["approval"])

    # ──────────────────────────────────────────────
    # 3. Grant lifecycle without request
    # ──────────────────────────────────────────────
    def test_grant_lifecycle_create_execute_revoke(self):
        """create grant -> execute -> revoke -> execution denied."""
        from backend.src.core.models import Grant

        self._insert_operator("owner-01", "Owner", "owner", "token-owner")

        grant = Grant(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="owner-01",
            reason="Direct grant",
        )
        self.grants_mod.create_grant(grant, tenant_id="demo")

        # Execute succeeds
        result1 = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertTrue(result1["approved"], f"First execution denied: {result1}")

        # Revoke
        ok = self.grants_mod.revoke_grant(grant.id, "owner-01", "Maintenance complete")
        self.assertTrue(ok)

        # Execute fails after revoke
        result2 = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertFalse(result2["approved"])
        self.assertIn("revoked", result2["reason"].lower())

    # ──────────────────────────────────────────────
    # 4. Challenge-restricted execution succeeds
    # ──────────────────────────────────────────────
    def test_challenge_restricted_execution_succeeds(self):
        """Grant exists, valid challenge, execution succeeds."""
        from backend.src.core.models import Grant

        self._insert_operator("owner-01", "Owner", "owner", "token-owner")

        grant = Grant(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="owner-01",
            reason="Direct grant",
        )
        self.grants_mod.create_grant(grant, tenant_id="demo")

        challenge = self.ch_mod.create_challenge("tech-01", "restart-service", "customer-env-a", tenant_id="demo")
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            challenge_id=challenge.id,
            tenant_id="demo",
        )
        self.assertTrue(result["approved"], f"Execution denied: {result}")
        self.assertEqual(result["challengeId"], challenge.id)

    # ──────────────────────────────────────────────
    # 5. Challenge-restricted execution fails
    # ──────────────────────────────────────────────
    def test_challenge_restricted_execution_fails_without_challenge(self):
        """REQUIRE_CHALLENGE=true without challenge -> denied."""
        from backend.src.core.models import Grant

        self._insert_operator("owner-01", "Owner", "owner", "token-owner")

        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        importlib.reload(self.demo_mod)

        grant = Grant(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="owner-01",
            reason="Direct grant",
        )
        self.grants_mod.create_grant(grant, tenant_id="demo")

        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertFalse(result["approved"])
        self.assertEqual(result["reason"], "challenge_required")
        self.assertEqual(result["challengeResult"], "required_missing")


if __name__ == "__main__":
    unittest.main(verbosity=2)
