"""Tests for GL-054 Integration Demo Pack.

Lightweight validation test proving the demo fixture is:
- loadable
- coherent
- aligned with Product Core concepts
- free of obvious secrets
"""

import json
import pathlib
import unittest


class TestGL054DemoScenarioFixture(unittest.TestCase):
    """GL-054: Validate the integration demo fixture."""

    FIXTURE_PATH = pathlib.Path(__file__).with_suffix("").parent / "fixtures" / "gl054_demo_scenario.json"

    REQUIRED_TOP_LEVEL_SECTIONS = {
        "scenarioId",
        "scenarioVersion",
        "title",
        "description",
        "workflowId",
        "subjectId",
        "actors",
        "grantRequest",
        "approval",
        "grant",
        "execution",
        "evidence",
        "evidenceVerification",
        "evidenceCompleteness",
        "complianceGapReport",
        "policyRequirements",
        "decisionProvenance",
        "auditorExport",
        "complianceReadiness",
        "notes",
    }

    STABLE_IDS = {
        "scenarioId": "gl054-demo-scenario",
        "workflowId": "gl054-workflow-001",
        "subjectId": "gl054-subject-001",
        "grantRequestId": "gl054-request-001",
        "grantId": "gl054-grant-001",
        "executionId": "gl054-execution-001",
        "evidenceId": "gl054-evidence-001",
        "policyPackId": "gl054-policy-001",
        "auditorExportId": "gl054-auditor-export-001",
    }

    SECRET_PATTERNS = [
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "private_key",
        "privatekey",
        "bearer",
        "authorization",
    ]

    @classmethod
    def setUpClass(cls):
        cls.fixture_text = cls.FIXTURE_PATH.read_text(encoding="utf-8")
        cls.fixture = json.loads(cls.fixture_text)

    # ── 1. Fixture file exists ─────────────────────────────────────────
    def test_fixture_file_exists(self):
        self.assertTrue(self.FIXTURE_PATH.exists(), f"Fixture not found: {self.FIXTURE_PATH}")

    # ── 2. Valid JSON ──────────────────────────────────────────────────
    def test_fixture_is_valid_json(self):
        # If setUpClass succeeded, this is already proven; assert explicitly.
        self.assertIsInstance(self.fixture, dict)

    # ── 3. scenarioId and scenarioVersion present ──────────────────────
    def test_scenario_id_present(self):
        self.assertEqual(self.fixture.get("scenarioId"), self.STABLE_IDS["scenarioId"])

    def test_scenario_version_present(self):
        self.assertEqual(self.fixture.get("scenarioVersion"), "1.0")

    # ── 4. Required top-level sections present ─────────────────────────
    def test_required_top_level_sections_present(self):
        missing = self.REQUIRED_TOP_LEVEL_SECTIONS - set(self.fixture.keys())
        self.assertEqual(missing, set(), f"Missing top-level sections: {missing}")

    # ── 5. Stable IDs reused consistently ──────────────────────────────
    def test_stable_ids_reused_consistently(self):
        f = self.fixture
        self.assertEqual(f["workflowId"], self.STABLE_IDS["workflowId"])
        self.assertEqual(f["subjectId"], self.STABLE_IDS["subjectId"])
        self.assertEqual(f["grantRequest"]["grantRequestId"], self.STABLE_IDS["grantRequestId"])
        self.assertEqual(f["grant"]["grantId"], self.STABLE_IDS["grantId"])
        self.assertEqual(f["execution"]["executionId"], self.STABLE_IDS["executionId"])
        self.assertEqual(f["evidence"][0]["evidenceId"], self.STABLE_IDS["evidenceId"])
        self.assertEqual(f["policyRequirements"]["policyPackId"], self.STABLE_IDS["policyPackId"])
        self.assertEqual(f["auditorExport"]["exportId"], self.STABLE_IDS["auditorExportId"])

    # ── 6. grantRequest links to workflowId and subjectId ──────────────
    def test_grant_request_links_workflow_and_subject(self):
        req = self.fixture["grantRequest"]
        self.assertEqual(req["workflowId"], self.fixture["workflowId"])
        self.assertEqual(req["subjectId"], self.fixture["subjectId"])

    # ── 7. approval links to grantRequestId ────────────────────────────
    def test_approval_links_grant_request(self):
        approval = self.fixture["approval"]
        self.assertEqual(approval["grantRequestId"], self.fixture["grantRequest"]["grantRequestId"])

    # ── 8. grant links to grantRequestId and grantId ───────────────────
    def test_grant_links_request_and_grant_id(self):
        grant = self.fixture["grant"]
        self.assertEqual(grant["grantRequestId"], self.fixture["grantRequest"]["grantRequestId"])
        self.assertEqual(grant["grantId"], self.STABLE_IDS["grantId"])

    # ── 9. execution links to grantId and executionId ──────────────────
    def test_execution_links_grant_and_execution_id(self):
        execution = self.fixture["execution"]
        self.assertEqual(execution["grantId"], self.fixture["grant"]["grantId"])
        self.assertEqual(execution["executionId"], self.STABLE_IDS["executionId"])

    # ── 10. evidence links to executionId and evidenceId ─────────────────
    def test_evidence_links_execution_and_evidence_id(self):
        ev = self.fixture["evidence"][0]
        self.assertEqual(ev["executionId"], self.fixture["execution"]["executionId"])
        self.assertEqual(ev["evidenceId"], self.STABLE_IDS["evidenceId"])

    # ── 11. evidence verification links to evidenceId ────────────────────
    def test_evidence_verification_links_evidence(self):
        ver = self.fixture["evidenceVerification"]
        self.assertEqual(ver["evidenceId"], self.fixture["evidence"][0]["evidenceId"])

    # ── 12. evidence completeness references evidence set or execution ───
    def test_evidence_completeness_references_execution(self):
        ec = self.fixture["evidenceCompleteness"]
        self.assertEqual(ec["executionId"], self.fixture["execution"]["executionId"])
        self.assertEqual(ec["grantId"], self.fixture["grant"]["grantId"])

    # ── 13. compliance gap report references workflowId or subjectId ───
    def test_compliance_gap_report_references_workflow_or_subject(self):
        cgr = self.fixture["complianceGapReport"]
        self.assertIn(cgr.get("workflowId"), {self.fixture["workflowId"], None})
        self.assertIn(cgr.get("subjectId"), {self.fixture["subjectId"], None})
        self.assertTrue(
            cgr.get("workflowId") == self.fixture["workflowId"]
            or cgr.get("subjectId") == self.fixture["subjectId"],
            "complianceGapReport must reference workflowId or subjectId",
        )

    # ── 14. policy requirements reference policyId or rulePackId ───────
    def test_policy_requirements_reference_policy_id(self):
        pr = self.fixture["policyRequirements"]
        self.assertTrue(
            "policyPackId" in pr or "policyId" in pr or "rulePackId" in pr,
            "policyRequirements must reference a policy identifier",
        )

    # ── 15. decision provenance references workflowId or executionId ─────
    def test_decision_provenance_references_workflow_or_execution(self):
        dp = self.fixture["decisionProvenance"]
        self.assertTrue(
            dp.get("workflowId") == self.fixture["workflowId"]
            or dp.get("executionId") == self.fixture["execution"]["executionId"],
            "decisionProvenance must reference workflowId or executionId",
        )

    # ── 16. auditor export references workflowId, grantId, or executionId
    def test_auditor_export_references_workflow_grant_or_execution(self):
        ae = self.fixture["auditorExport"]
        refs = {
            ae.get("workflowId"),
            ae.get("grantId"),
            ae.get("executionId"),
        }
        self.assertTrue(
            self.fixture["workflowId"] in refs
            or self.fixture["grant"]["grantId"] in refs
            or self.fixture["execution"]["executionId"] in refs,
            "auditorExport must reference workflowId, grantId, or executionId",
        )

    # ── 17. compliance readiness references workflowId and subjectId ─────
    def test_compliance_readiness_references_workflow_and_subject(self):
        cr = self.fixture["complianceReadiness"]
        self.assertEqual(cr["workflowId"], self.fixture["workflowId"])
        self.assertEqual(cr["subjectId"], self.fixture["subjectId"])

    # ── 18. No obvious secrets ─────────────────────────────────────────
    def test_fixture_contains_no_obvious_secrets(self):
        text_lower = self.fixture_text.lower()
        for pattern in self.SECRET_PATTERNS:
            self.assertNotIn(
                pattern,
                text_lower,
                f"Fixture may contain secret-like pattern: {pattern}",
            )

    # ── Extra coherence checks ─────────────────────────────────────────
    def test_grant_signature_fields_present(self):
        grant = self.fixture["grant"]
        self.assertIsNotNone(grant.get("signature"))
        self.assertIsNotNone(grant.get("payloadHash"))
        self.assertIsNotNone(grant.get("signingKeyId"))
        self.assertEqual(len(grant["signature"]), 128)
        self.assertEqual(len(grant["payloadHash"]), 64)

    def test_evidence_hash_length_and_charset(self):
        ev = self.fixture["evidence"][0]
        h = ev["evidenceHash"]
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))

    def test_evidence_verification_hashes_match(self):
        ver = self.fixture["evidenceVerification"]
        self.assertEqual(ver["recomputedHash"], ver["storedHash"])
        self.assertTrue(ver["match"])

    def test_all_evidence_items_reference_same_grant_and_execution(self):
        for ev in self.fixture["evidence"]:
            self.assertEqual(ev["grantId"], self.fixture["grant"]["grantId"])
            self.assertEqual(ev["executionId"], self.fixture["execution"]["executionId"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
