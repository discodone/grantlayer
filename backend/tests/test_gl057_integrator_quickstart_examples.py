"""Tests for GL-057 Integrator Quickstart Examples.

Lightweight validation test proving the quickstart examples are:
- loadable
- valid JSON
- coherent and consistent
- aligned with Product Core concepts
- free of obvious secrets
"""

import json
import pathlib
import unittest


class TestGL057IntegratorQuickstartExamples(unittest.TestCase):
    """GL-057: Validate the integrator quickstart examples."""

    REPO_ROOT = pathlib.Path(__file__).with_suffix("").parent.parent.parent
    DOCS_DIR = REPO_ROOT / "docs"
    EXAMPLE_DIR = DOCS_DIR / "examples" / "gl057"

    EXPECTED_FILES = [
        "grant_request.json",
        "approval_result.json",
        "grant.json",
        "grant_execution.json",
        "evidence_item.json",
        "evidence_completeness.json",
        "compliance_gap_report.json",
        "policy_requirements_result.json",
        "decision_provenance_summary.json",
        "auditor_export.json",
        "compliance_readiness_summary.json",
        "minimal_flow_bundle.json",
    ]

    STABLE_IDS = {
        "workflowId": "gl057-workflow-001",
        "subjectId": "gl057-subject-001",
        "grantRequestId": "gl057-request-001",
        "grantId": "gl057-grant-001",
        "executionId": "gl057-execution-001",
        "evidenceId": "gl057-evidence-001",
        "policyId": "gl057-policy-001",
        "auditorExportId": "gl057-auditor-export-001",
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
        cls.examples = {}
        cls.example_texts = {}
        for name in cls.EXPECTED_FILES:
            path = cls.EXAMPLE_DIR / name
            if path.exists():
                text = path.read_text(encoding="utf-8")
                cls.example_texts[name] = text
                cls.examples[name] = json.loads(text)

    # ── 1. Quickstart doc exists ───────────────────────────────────────
    def test_quickstart_doc_exists(self):
        path = self.DOCS_DIR / "integrator_quickstart.md"
        self.assertTrue(path.exists(), "docs/integrator_quickstart.md must exist")

    # ── 2. Example directory exists ────────────────────────────────────
    def test_example_directory_exists(self):
        self.assertTrue(
            self.EXAMPLE_DIR.exists(),
            f"Example directory must exist: {self.EXAMPLE_DIR}",
        )

    # ── 3. All expected JSON files exist ───────────────────────────────
    def test_all_expected_json_files_exist(self):
        missing = []
        for name in self.EXPECTED_FILES:
            path = self.EXAMPLE_DIR / name
            if not path.exists():
                missing.append(name)
        self.assertEqual(missing, [], f"Missing example JSON files: {missing}")

    # ── 4. Every JSON file parses ──────────────────────────────────────
    def test_every_json_file_parses(self):
        for name in self.EXPECTED_FILES:
            with self.subTest(file=name):
                self.assertIn(name, self.examples, f"{name} must parse as valid JSON")
                self.assertIsInstance(self.examples[name], dict)

    # ── 5. Stable IDs are present where expected ───────────────────────
    def test_stable_ids_present_where_expected(self):
        # workflowId should appear in most files
        for name in [
            "grant_request.json",
            "compliance_gap_report.json",
            "decision_provenance_summary.json",
            "auditor_export.json",
            "compliance_readiness_summary.json",
            "minimal_flow_bundle.json",
        ]:
            with self.subTest(file=name, id="workflowId"):
                self.assertEqual(
                    self.examples[name].get("workflowId"),
                    self.STABLE_IDS["workflowId"],
                )

        for name in [
            "grant_request.json",
            "grant.json",
            "compliance_gap_report.json",
            "decision_provenance_summary.json",
            "compliance_readiness_summary.json",
            "minimal_flow_bundle.json",
        ]:
            with self.subTest(file=name, id="subjectId"):
                self.assertEqual(
                    self.examples[name].get("subjectId"),
                    self.STABLE_IDS["subjectId"],
                )

        self.assertEqual(
            self.examples["grant_request.json"].get("grantRequestId"),
            self.STABLE_IDS["grantRequestId"],
        )
        self.assertEqual(
            self.examples["grant.json"].get("grantId"),
            self.STABLE_IDS["grantId"],
        )
        self.assertEqual(
            self.examples["grant_execution.json"].get("executionId"),
            self.STABLE_IDS["executionId"],
        )
        self.assertEqual(
            self.examples["evidence_item.json"].get("evidenceId"),
            self.STABLE_IDS["evidenceId"],
        )
        self.assertEqual(
            self.examples["policy_requirements_result.json"].get("policyPackId"),
            self.STABLE_IDS["policyId"],
        )
        self.assertEqual(
            self.examples["auditor_export.json"].get("exportId"),
            self.STABLE_IDS["auditorExportId"],
        )

    # ── 6. minimal_flow_bundle.json links all main IDs ─────────────────
    def test_minimal_flow_bundle_links_all_main_ids(self):
        bundle = self.examples["minimal_flow_bundle.json"]
        self.assertEqual(bundle.get("workflowId"), self.STABLE_IDS["workflowId"])
        self.assertEqual(bundle.get("subjectId"), self.STABLE_IDS["subjectId"])
        self.assertEqual(bundle.get("grantRequestId"), self.STABLE_IDS["grantRequestId"])
        self.assertEqual(bundle.get("grantId"), self.STABLE_IDS["grantId"])
        self.assertEqual(bundle.get("executionId"), self.STABLE_IDS["executionId"])
        self.assertEqual(bundle.get("evidenceId"), self.STABLE_IDS["evidenceId"])
        self.assertEqual(bundle.get("policyId"), self.STABLE_IDS["policyId"])
        self.assertEqual(bundle.get("auditorExportId"), self.STABLE_IDS["auditorExportId"])

    # ── 7. Examples reuse IDs consistently ─────────────────────────────
    def test_grant_request_links_workflow_and_subject(self):
        req = self.examples["grant_request.json"]
        self.assertEqual(req["workflowId"], self.STABLE_IDS["workflowId"])
        self.assertEqual(req["subjectId"], self.STABLE_IDS["subjectId"])

    def test_approval_links_grant_request(self):
        approval = self.examples["approval_result.json"]
        self.assertEqual(approval["grantRequestId"], self.STABLE_IDS["grantRequestId"])
        self.assertEqual(approval["grantId"], self.STABLE_IDS["grantId"])

    def test_grant_links_request_and_grant_id(self):
        grant = self.examples["grant.json"]
        self.assertEqual(grant["grantRequestId"], self.STABLE_IDS["grantRequestId"])
        self.assertEqual(grant["grantId"], self.STABLE_IDS["grantId"])
        self.assertEqual(grant["subjectId"], self.STABLE_IDS["subjectId"])

    def test_execution_links_grant_and_execution_id(self):
        execution = self.examples["grant_execution.json"]
        self.assertEqual(execution["grantId"], self.STABLE_IDS["grantId"])
        self.assertEqual(execution["grantRequestId"], self.STABLE_IDS["grantRequestId"])
        self.assertEqual(execution["executionId"], self.STABLE_IDS["executionId"])

    def test_evidence_links_execution_and_evidence_id(self):
        ev = self.examples["evidence_item.json"]
        self.assertEqual(ev["executionId"], self.STABLE_IDS["executionId"])
        self.assertEqual(ev["evidenceId"], self.STABLE_IDS["evidenceId"])
        self.assertEqual(ev["grantId"], self.STABLE_IDS["grantId"])
        self.assertEqual(ev["grantRequestId"], self.STABLE_IDS["grantRequestId"])

    def test_evidence_completeness_references_execution(self):
        ec = self.examples["evidence_completeness.json"]
        self.assertEqual(ec["executionId"], self.STABLE_IDS["executionId"])
        self.assertEqual(ec["grantId"], self.STABLE_IDS["grantId"])

    def test_compliance_gap_report_references_workflow_or_subject(self):
        cgr = self.examples["compliance_gap_report.json"]
        self.assertTrue(
            cgr.get("workflowId") == self.STABLE_IDS["workflowId"]
            or cgr.get("subjectId") == self.STABLE_IDS["subjectId"],
            "complianceGapReport must reference workflowId or subjectId",
        )

    def test_decision_provenance_references_workflow_or_execution(self):
        dp = self.examples["decision_provenance_summary.json"]
        self.assertTrue(
            dp.get("workflowId") == self.STABLE_IDS["workflowId"]
            or dp.get("executionId") == self.STABLE_IDS["executionId"],
            "decisionProvenance must reference workflowId or executionId",
        )

    def test_auditor_export_references_workflow_grant_or_execution(self):
        ae = self.examples["auditor_export.json"]
        refs = {
            ae.get("workflowId"),
            ae.get("grantId"),
            ae.get("executionId"),
        }
        self.assertTrue(
            self.STABLE_IDS["workflowId"] in refs
            or self.STABLE_IDS["grantId"] in refs
            or self.STABLE_IDS["executionId"] in refs,
            "auditorExport must reference workflowId, grantId, or executionId",
        )

    def test_compliance_readiness_references_workflow_and_subject(self):
        cr = self.examples["compliance_readiness_summary.json"]
        self.assertEqual(cr["workflowId"], self.STABLE_IDS["workflowId"])
        self.assertEqual(cr["subjectId"], self.STABLE_IDS["subjectId"])

    # ── 8. No obvious secrets exist in examples ────────────────────────
    def test_examples_contain_no_obvious_secrets(self):
        for name, text in self.example_texts.items():
            text_lower = text.lower()
            for pattern in self.SECRET_PATTERNS:
                with self.subTest(file=name, pattern=pattern):
                    self.assertNotIn(
                        pattern,
                        text_lower,
                        f"Example {name} may contain secret-like pattern: {pattern}",
                    )

    # ── 9. Quickstart doc references the example files ─────────────────
    def test_quickstart_doc_references_example_files(self):
        path = self.DOCS_DIR / "integrator_quickstart.md"
        content = path.read_text(encoding="utf-8")
        for name in self.EXPECTED_FILES:
            self.assertIn(
                name,
                content,
                f"Quickstart doc should reference example file {name}",
            )
        self.assertIn(
            "docs/examples/gl057/",
            content,
            "Quickstart doc should reference the example directory",
        )

    # ── 10. Quickstart doc references integration guide and other docs ─
    def test_quickstart_doc_references_integration_artifacts(self):
        path = self.DOCS_DIR / "integrator_quickstart.md"
        content = path.read_text(encoding="utf-8")
        self.assertIn("integration_guide.md", content)
        self.assertIn("demo_scenario.md", content)
        self.assertIn("integration_ready_checklist.md", content)
        self.assertIn("integration_ready_release_candidate.md", content)
        self.assertIn("openapi.yaml", content)

    # ── Extra coherence checks ─────────────────────────────────────────
    def test_grant_signature_fields_present(self):
        grant = self.examples["grant.json"]
        self.assertIsNotNone(grant.get("signature"))
        self.assertIsNotNone(grant.get("payloadHash"))
        self.assertIsNotNone(grant.get("signingKeyId"))
        self.assertEqual(len(grant["signature"]), 128)
        self.assertEqual(len(grant["payloadHash"]), 64)

    def test_evidence_hash_length_and_charset(self):
        ev = self.examples["evidence_item.json"]
        h = ev["evidenceHash"]
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))

    def test_all_examples_are_deterministic_objects(self):
        for name, obj in self.examples.items():
            with self.subTest(file=name):
                self.assertIsInstance(obj, dict)
                self.assertTrue(len(obj) > 0, f"{name} must not be empty")


if __name__ == "__main__":
    unittest.main(verbosity=2)
