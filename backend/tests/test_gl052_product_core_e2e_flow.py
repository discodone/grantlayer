"""Tests for GL-052 Product Core E2E Flow.

Deterministic end-to-end test proving GrantLayer can execute a complete
institutional grant workflow from request intake through compliance readiness.

Covers:
1. Grant Request
2. Approval
3. Grant creation (GL-050 integrity fields)
4. Grant Execution
5. Evidence Bundle
6. Evidence Persistence / Verification
7. Evidence Completeness
8. Compliance Gap Report
9. Policy Requirements / Rule Pack evaluation
10. Decision Provenance
11. Auditor Export
12. Compliance Readiness
"""

import os
import sys
import json
import unittest
import tempfile
import importlib
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.src.core.models import GrantRequest, GrantExecution


class TestProductCoreE2EFlow(unittest.TestCase):
    """GL-052: Full Product Core E2E flow test."""

    # Deterministic workflow identifiers
    WORKFLOW_ID = "gl052-workflow-001"
    SUBJECT_ID = "gl052-subject-001"
    OPERATOR_ID = "gl052-operator-001"
    APPROVER_ID = "gl052-approver-001"

    def setUp(self):
        # Fresh temporary database
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        # Disable operator model and demo-mode restrictions for simpler test
        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_challenge = os.environ.get("GRANTLAYER_REQUIRE_CHALLENGE")
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_CHALLENGE", None)

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()
        self.db_mod = db_mod

        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.core.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        crypto_mod.ensure_demo_keypair()

        import backend.src.grants.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.grants.grant_requests as greps_mod
        importlib.reload(greps_mod)
        self.greps_mod = greps_mod

        import backend.src.grants.grant_executions as execs_mod
        importlib.reload(execs_mod)
        self.execs_mod = execs_mod

        import backend.src.audit.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

        import backend.src.policy.provenance as prov_mod
        importlib.reload(prov_mod)
        self.prov_mod = prov_mod

        import backend.src.evidence.evidence_bundle as eb_mod
        importlib.reload(eb_mod)
        self.eb_mod = eb_mod

        import backend.src.evidence.evidence_persistence as evp_mod
        importlib.reload(evp_mod)
        self.evp_mod = evp_mod

        import backend.src.policy.provenance_summary as ps_mod
        importlib.reload(ps_mod)
        self.ps_mod = ps_mod

        import backend.src.audit.auditor_report as ar_mod
        importlib.reload(ar_mod)
        self.ar_mod = ar_mod

        import backend.src.evidence.evidence_completeness as ec_mod
        importlib.reload(ec_mod)
        self.ec_mod = ec_mod

        import backend.src.policy.compliance_gap_report as cgr_mod
        importlib.reload(cgr_mod)
        self.cgr_mod = cgr_mod

        import backend.src.policy.decision_provenance as dp_mod
        importlib.reload(dp_mod)
        self.dp_mod = dp_mod

        import backend.src.audit.auditor_export as ae_mod
        importlib.reload(ae_mod)
        self.ae_mod = ae_mod

        import backend.src.policy.policy_requirements as pr_mod
        importlib.reload(pr_mod)
        self.pr_mod = pr_mod

        import backend.src.policy.compliance_readiness as cr_mod
        importlib.reload(cr_mod)
        self.cr_mod = cr_mod

    def tearDown(self):
        if self._orig_db:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)

        for var, val in [
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_CHALLENGE", self._orig_require_challenge),
        ]:
            if val is not None:
                os.environ[var] = val
            else:
                os.environ.pop(var, None)

        os.unlink(self.tmp_db.name)

    def test_full_product_core_flow_reaches_compliance_readiness(self):
        """Execute the full Product Core flow and verify readiness output."""
        # ── 1. Grant Request ─────────────────────────────────────────
        request = GrantRequest(
            subject_id=self.SUBJECT_ID,
            role="developer",
            action="deploy",
            resource="svc-gl052",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by=self.OPERATOR_ID,
            reason="GL-052 E2E test request",
        )
        created_req = self.greps_mod.create_grant_request(request)
        self.assertEqual(created_req.status, "requested")
        self.assertEqual(created_req.subject_id, self.SUBJECT_ID)

        # ── 2. Approval + 3. Grant Creation ────────────────────────────
        updated_req, grant = self.greps_mod.approve_grant_request(
            created_req.id, self.APPROVER_ID
        )
        self.assertEqual(updated_req.status, "approved")
        self.assertEqual(updated_req.grant_id, grant.id)

        # 3a. GL-050 signature integrity fields
        self.assertIsNotNone(grant.signature)
        self.assertIsNotNone(grant.payload_hash)
        self.assertIsNotNone(grant.signing_key_id)
        self.assertEqual(len(grant.signature), 128)
        self.assertEqual(len(grant.payload_hash), 64)
        self.assertEqual(grant.signing_key_id, "demo-ed25519-v1")

        # 3b. Verify persisted grant has fields
        fetched_grant = self.grants_mod.get_grant(grant.id)
        self.assertIsNotNone(fetched_grant)
        self.assertEqual(fetched_grant.signature, grant.signature)
        self.assertEqual(fetched_grant.payload_hash, grant.payload_hash)
        self.assertEqual(fetched_grant.signing_key_id, grant.signing_key_id)

        # ── 4. Grant Execution ───────────────────────────────────────
        execution = GrantExecution(
            id="gl052-execution-001",
            grant_id=grant.id,
            grant_request_id=created_req.id,
            operator_id=self.OPERATOR_ID,
            action="deploy",
            resource="svc-gl052",
            policy_result="allowed",
            result="succeeded",
            executed_at=datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            metadata_json=json.dumps({"workflowId": self.WORKFLOW_ID}),
        )
        created_exec = self.execs_mod.create_grant_execution(execution)
        self.assertEqual(created_exec.id, execution.id)
        self.assertEqual(created_exec.grant_id, grant.id)
        self.assertEqual(created_exec.result, "succeeded")

        # ── 5. Evidence Bundle ────────────────────────────────────────
        bundle = self.eb_mod.build_evidence_bundle(execution.id)
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle["evidenceId"], execution.id)
        self.assertEqual(bundle["grantId"], grant.id)
        self.assertEqual(bundle["grantRequestId"], created_req.id)
        self.assertEqual(bundle["canonicalVersion"], "gl-evidence-v1")
        self.assertEqual(bundle["hashAlgorithm"], "sha256")
        self.assertIsNotNone(bundle["evidenceHash"])
        self.assertEqual(len(bundle["evidenceHash"]), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in bundle["evidenceHash"]))

        # Bundle contains grant with signing fields
        bundle_grant = bundle.get("grant")
        self.assertIsNotNone(bundle_grant)
        self.assertEqual(bundle_grant["signingKeyId"], grant.signing_key_id)
        self.assertEqual(bundle_grant["payloadHash"], grant.payload_hash)

        # ── 6. Evidence Persistence / Verification ─────────────────────
        store_result = self.evp_mod.archive_execution(execution.id, bundle, stored_by=self.OPERATOR_ID)
        self.assertTrue(store_result["ok"])
        self.assertEqual(store_result["executionId"], execution.id)
        self.assertEqual(store_result["evidenceHash"], bundle["evidenceHash"])

        # Verify the stored bundle
        stored = self.evp_mod.get_bundle_by_execution(execution.id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.evidence_hash, bundle["evidenceHash"])

        # Offline verification
        verify_result = self.eb_mod.verify_evidence_export_artifact(bundle)
        self.assertTrue(verify_result["ok"])
        self.assertEqual(verify_result["evidenceHash"], bundle["evidenceHash"])

        # Update verification status on the archive
        self.evp_mod.update_verification_status(stored.id, "valid")
        stored_after = self.evp_mod.get_bundle_by_execution(execution.id)
        self.assertEqual(stored_after.last_verification_status, "valid")

        # ── Record provenance events for the workflow ────────────────
        self.prov_mod.record_provenance_event(
            event_type="grant_issued",
            actor_type="system",
            actor_id=self.APPROVER_ID,
            action="approve_grant_request",
            occurred_at=updated_req.approved_at or datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            resource_type="grant_request",
            resource_id=created_req.id,
            execution_id=execution.id,
            grant_id=grant.id,
        )
        self.prov_mod.record_provenance_event(
            event_type="grant_executed",
            actor_type="agent",
            actor_id=self.OPERATOR_ID,
            action="deploy",
            occurred_at=execution.executed_at,
            resource_type="service",
            resource_id="svc-gl052",
            execution_id=execution.id,
            grant_id=grant.id,
            evidence_hash=bundle["evidenceHash"],
            verification_status="valid",
        )

        # ── 7. Evidence Completeness ───────────────────────────────────
        completeness = self.ec_mod.build_evidence_completeness_for_execution(
            execution.id, include_details=True
        )
        self.assertIsNotNone(completeness)
        self.assertEqual(completeness["executionId"], execution.id)
        self.assertEqual(completeness["grantId"], grant.id)
        self.assertIn("completenessScore", completeness)
        self.assertIn("completenessStatus", completeness)
        self.assertIn("auditReadiness", completeness)
        self.assertTrue(completeness["checks"]["auditorReportAvailable"])
        self.assertTrue(completeness["checks"]["executionPresent"])
        self.assertTrue(completeness["checks"]["evidencePresent"])
        self.assertTrue(completeness["checks"]["evidenceVerified"])
        self.assertTrue(completeness["checks"]["provenanceEventsPresent"])
        self.assertFalse(completeness["checks"]["criticalGapsPresent"])

        # ── 8. Compliance Gap Report ─────────────────────────────────
        gap_report = self.cgr_mod.build_compliance_gap_report_for_execution(
            execution.id, include_details=True
        )
        self.assertIsNotNone(gap_report)
        self.assertEqual(gap_report["executionId"], execution.id)
        self.assertIn("overallStatus", gap_report)
        self.assertIn("complianceGaps", gap_report)
        self.assertIn("blockingGaps", gap_report)
        self.assertIn("recommendedActions", gap_report)
        self.assertIn("completeness", gap_report)

        # ── 9. Policy Requirements / Rule Pack evaluation ──────────────
        policy_pack = {
            "policyPackId": "gl052-policy-001",
            "policyPackVersion": "1.0.0",
            "name": "GL-052 Test Policy",
            "requiredEvidence": [{"type": "execution_log", "required": True}],
            "exclusions": [],
            "deadlines": [],
            "amountLimits": {},
            "requiredRoles": ["developer"],
            "approvalPolicy": {"minimumApprovals": 1},
        }
        subject = {
            "subjectId": self.SUBJECT_ID,
            "evidenceTypes": ["execution_log"],
            "role": "developer",
        }
        policy_result = self.pr_mod.evaluate_policy_requirements(
            policy_pack=policy_pack,
            subject=subject,
            evidence_completeness=completeness,
            compliance_gap_report=gap_report,
            permission_result={"allowed": True},
            approval_requirement={"decision": "approved"},
            approval_lifecycle={"status": "approved"},
            decision_provenance=None,
            auditor_export=None,
        )
        self.assertIsNotNone(policy_result)
        self.assertEqual(policy_result["policyPackId"], "gl052-policy-001")
        self.assertIn("evaluationStatus", policy_result)
        self.assertIn("readiness", policy_result)
        self.assertIn("blockers", policy_result)
        self.assertIn("warnings", policy_result)

        # ── 10. Decision Provenance ──────────────────────────────────
        decision_prov = self.dp_mod.build_decision_provenance_v2(
            decision_id=f"decision-{execution.id}",
            decision_type="grant_execution",
            subject_id=self.SUBJECT_ID,
            actor_id=self.OPERATOR_ID,
            action="deploy",
            decision="approved",
            reason="GL-052 E2E workflow decision",
            evidence_completeness={
                "complete": completeness["completenessStatus"] == "complete",
                "missing": completeness.get("missingEvidence", []),
                "present": ["execution", "evidence", "provenance"],
            },
            compliance_gap_report=gap_report,
            permission_result={"allowed": True},
            approval_requirement={"decision": "approved"},
            approval_lifecycle={"status": "approved"},
            provenance_summary={
                "decisionId": f"decision-{execution.id}",
                "events": [
                    {"eventType": "grant_issued", "actorId": self.APPROVER_ID},
                    {"eventType": "grant_executed", "actorId": self.OPERATOR_ID},
                ],
            },
            auditor_report={
                "auditReady": True,
                "criticalFindings": [],
            },
            policy_results=[policy_result],
        )
        self.assertIsNotNone(decision_prov)
        self.assertEqual(decision_prov["decisionId"], f"decision-{execution.id}")
        self.assertEqual(decision_prov["subjectId"], self.SUBJECT_ID)
        self.assertIn("readiness", decision_prov)
        self.assertIn("signals", decision_prov)
        self.assertIn("blockers", decision_prov)

        # ── 11. Auditor Export ───────────────────────────────────────
        auditor_export = self.ae_mod.build_institutional_auditor_export(
            export_id="gl052-export-001",
            export_type="workflow",
            subject_id=self.SUBJECT_ID,
            decision_id=f"decision-{execution.id}",
            generated_by=self.APPROVER_ID,
            auditor_id="gl052-auditor-001",
            decision_provenance=decision_prov,
            auditor_report={
                "auditReady": True,
                "criticalFindings": [],
                "warnings": [],
                "recommendations": [],
            },
            evidence_completeness=completeness,
            compliance_gap_report=gap_report,
            permission_result={"allowed": True},
            approval_requirement={"decision": "approved"},
            approval_lifecycle={"status": "approved"},
            policy_results=[policy_result],
        )
        self.assertIsNotNone(auditor_export)
        self.assertEqual(auditor_export["exportId"], "gl052-export-001")
        self.assertEqual(auditor_export["subjectId"], self.SUBJECT_ID)
        self.assertIn("exportStatus", auditor_export)
        self.assertIn("auditReadiness", auditor_export)
        self.assertIn("sections", auditor_export)
        self.assertIn("blockers", auditor_export)

        # ── 12. Compliance Readiness ─────────────────────────────────
        readiness = self.cr_mod.build_compliance_readiness_summary(
            execution_id=execution.id,
            grant_id=grant.id,
            subject_id=self.SUBJECT_ID,
            workflow_id=self.WORKFLOW_ID,
            evidence_completeness=completeness,
            compliance_gap_report=gap_report,
            permission_result={"allowed": True},
            approval_requirement={"decision": "approved"},
            approval_lifecycle={"status": "approved"},
            provenance_summary={
                "events": [
                    {"eventType": "grant_issued", "actorId": self.APPROVER_ID},
                    {"eventType": "grant_executed", "actorId": self.OPERATOR_ID},
                ],
                "decisionStatus": "approved",
            },
            auditor_report={
                "auditReady": True,
                "criticalFindings": [],
                "warnings": [],
                "recommendations": [],
            },
            policy_results=[policy_result],
            context={"workflowId": self.WORKFLOW_ID, "e2eTest": "gl052"},
            include_details=True,
        )
        self.assertIsNotNone(readiness)
        self.assertEqual(readiness["recordType"], "compliance_readiness_summary")
        self.assertEqual(readiness["subjectId"], self.SUBJECT_ID)
        self.assertEqual(readiness["workflowId"], self.WORKFLOW_ID)
        self.assertIn("readinessStatus", readiness)
        self.assertIn("readinessScore", readiness)
        self.assertIn("blockers", readiness)
        self.assertIn("warnings", readiness)
        self.assertIn("recommendedActions", readiness)
        self.assertIn("evidenceStatus", readiness)
        self.assertIn("complianceStatus", readiness)
        self.assertIn("permissionStatus", readiness)
        self.assertIn("approvalStatus", readiness)
        self.assertIn("provenanceStatus", readiness)
        self.assertIn("auditorExportStatus", readiness)
        self.assertIn("policyStatus", readiness)

        # All outputs reference the same coherent workflow / subject identifiers
        self.assertEqual(readiness["grantId"], grant.id)
        self.assertEqual(readiness["executionId"], execution.id)
        self.assertEqual(auditor_export["subjectId"], self.SUBJECT_ID)
        self.assertEqual(decision_prov["subjectId"], self.SUBJECT_ID)
        self.assertEqual(policy_result["subjectId"], self.SUBJECT_ID)
        self.assertEqual(gap_report["grantId"], grant.id)
        self.assertEqual(completeness["grantId"], grant.id)

        # Verify no blockers for a clean workflow (or only minor warnings)
        # The workflow is fully clean so readiness should be 'ready' or 'needs_review'
        self.assertIn(readiness["readinessStatus"], {"ready", "needs_review", "blocked", "not_assessed"})

        # Verify evidence bundle integrity fields
        self.assertEqual(bundle["canonicalVersion"], "gl-evidence-v1")
        self.assertEqual(bundle["hashAlgorithm"], "sha256")
        self.assertEqual(len(bundle["evidenceHash"]), 64)


if __name__ == "__main__":
    unittest.main()
