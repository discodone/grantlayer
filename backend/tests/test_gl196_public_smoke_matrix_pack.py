"""GL-196 Public Smoke Matrix Pack regression tests."""

import json
import os
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "docs" / "public_smoke_matrix_pack.md"
ARTIFACT_PATH = REPO_ROOT / "docs" / "examples" / "gl196" / "public_smoke_matrix_pack.json"

ALLOWED_RESULTS = {
    "public_smoke_matrix_pack_complete",
    "blocked_unexpected_scope",
    "blocked_public_claim_safety",
    "blocked_other_with_reason",
}

REQUIRED_CHECK_IDS = [
    "public_repo_reachable",
    "readme_present",
    "readme_entry_path_clear",
    "first_output_helper_present",
    "first_output_helper_match",
    "grant_lifecycle_example_present",
    "grant_lifecycle_example_match",
    "public_agent_api_walkthrough_present",
    "public_feedback_infrastructure_present",
    "public_safety_gate_present",
    "security_advisory_route_visible",
    "developer_preview_caveat_visible",
    "not_production_saas_caveat_visible",
    "tenant_isolation_not_implemented_caveat_visible",
    "no_real_customer_data_caveat_visible",
    "no_secrets_caveat_visible",
    "stale_public_state_phrases_absent",
    "private_data_scan_clean",
    "secret_scan_clean",
    "internal_infrastructure_scan_clean",
    "no_force_push_required",
    "internal_repo_not_directly_pushed_to_github",
]

REQUIRED_SAFETY_CONFIRMATIONS = [
    "no_github_push_performed",
    "no_visibility_change_performed",
    "internal_repo_not_pushed_directly_to_github",
    "no_github_api_label_changes_performed",
    "no_github_issue_changes_performed",
    "no_reviewer_outreach_sent",
    "no_backend_src_changes",
    "no_openapi_changes",
    "no_migration_db_dependency_changes",
    "no_dependency_manifest_changes",
    "no_sdk_implementation_changes",
    "no_examples_runtime_changes",
    "no_frontend_website_design_changes",
    "no_github_workflow_changes",
    "no_snapshot_publish_script_behavior_changes",
    "no_production_saas_claim",
    "tenant_isolation_not_claimed",
    "no_real_customer_data_requested",
    "no_private_grant_data_requested",
    "no_secrets_requested",
    "no_exploit_details_included",
    "security_sensitive_reports_routed_to_github_security_advisories",
]

REQUIRED_COMMAND_SNIPPETS = [
    "scripts/verify-first-output.sh",
    "python3 examples/grant_lifecycle_evidence_bundle.py --output /tmp/grantlayer_gl196_grant_lifecycle_check.json",
    "diff -u examples/grant_lifecycle_evidence_bundle.json /tmp/grantlayer_gl196_grant_lifecycle_check.json",
    "rg -n \"publication pending|public GitHub release has not happened|visibility decision pending|formal visibility decision pending|approved internal source|if and when public publication is approved\" README.md CONTRIBUTING.md AGENTS.md llms-full.txt llms.txt docs/ten_minute_quickstart.md docs/agent_quickstart.md || true",
    "rg -n \"GitHub Security Advisories|security/advisories\" SECURITY.md docs/public_feedback_infrastructure_pack.md README.md",
    "rg -n \"Developer Preview|technical preview|not production SaaS|tenant.*not implemented|no real secrets|customer data|private grants\" README.md AGENTS.md llms.txt llms-full.txt docs/public_agent_api_walkthrough_refresh.md docs/public_safety_scanner_claim_consistency_gate.md",
]

REQUIRED_DOC_PHRASES = [
    "gl-196",
    "public smoke matrix",
    "developer preview",
    "not production saas",
    "tenant/workspace isolation not implemented",
    "security-sensitive reports route to GitHub Security Advisories",
    "scripts/verify-first-output.sh",
    "python3 examples/grant_lifecycle_evidence_bundle.py --output /tmp/grantlayer_gl196_grant_lifecycle_check.json",
    "diff -u examples/grant_lifecycle_evidence_bundle.json /tmp/grantlayer_gl196_grant_lifecycle_check.json",
    "publication pending",
    "public gitHub release has not happened",
]

ALLOWED_CHANGED_FILES = {
    "docs/public_smoke_matrix_pack.md",
    "docs/examples/gl196/public_smoke_matrix_pack.json",
    "backend/tests/test_gl196_public_smoke_matrix_pack.py",
}


def _load_doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def _load_artifact():
    return json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))


class TestGL196FilesExist(unittest.TestCase):
    def test_doc_exists(self):
        self.assertTrue(DOC_PATH.is_file(), f"Missing doc: {DOC_PATH}")

    def test_artifact_exists(self):
        self.assertTrue(ARTIFACT_PATH.is_file(), f"Missing artifact: {ARTIFACT_PATH}")


class TestGL196ArtifactStructure(unittest.TestCase):
    def setUp(self):
        self.data = _load_artifact()

    def test_valid_json(self):
        self.assertIsInstance(self.data, dict)

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-196")

    def test_result_allowed(self):
        self.assertIn(self.data.get("result"), ALLOWED_RESULTS)

    def test_smoke_matrix_exists(self):
        matrix = self.data.get("smoke_matrix", [])
        self.assertIsInstance(matrix, list)
        self.assertGreater(len(matrix), 0)

    def test_required_check_ids_present(self):
        check_ids = {row.get("check_id") for row in self.data.get("smoke_matrix", [])}
        for check_id in REQUIRED_CHECK_IDS:
            self.assertIn(check_id, check_ids, f"Missing smoke matrix check: {check_id}")

    def test_each_smoke_matrix_row_has_required_fields(self):
        for row in self.data.get("smoke_matrix", []):
            self.assertIn("check_id", row)
            self.assertIn("purpose", row)
            self.assertIn("command_or_method", row)
            self.assertIn("expected_result", row)
            self.assertIn("blocking", row)
            self.assertIn("related_docs", row)
            self.assertIsInstance(row["related_docs"], list)

    def test_commands_documented(self):
        commands = " ".join(entry.get("command", "") for entry in self.data.get("commands", []))
        for snippet in REQUIRED_COMMAND_SNIPPETS:
            self.assertIn(snippet, commands)

    def test_expected_results_and_blocking_criteria_exist(self):
        self.assertIsInstance(self.data.get("expected_results", []), list)
        self.assertIsInstance(self.data.get("blocking_criteria", []), list)
        self.assertGreater(len(self.data["expected_results"]), 0)
        self.assertGreater(len(self.data["blocking_criteria"]), 0)

    def test_safety_confirmations(self):
        confirmations = self.data.get("safety_confirmations", {})
        for key in REQUIRED_SAFETY_CONFIRMATIONS:
            self.assertIn(key, confirmations, f"Missing safety confirmation: {key}")
            self.assertTrue(confirmations[key], f"False safety confirmation: {key}")

    def test_changed_files_within_scope(self):
        changed = set(self.data.get("changed_files", []))
        self.assertEqual(changed, ALLOWED_CHANGED_FILES)

    def test_no_forbidden_changes_in_changed_files(self):
        for changed_file in self.data.get("changed_files", []):
            lowered = changed_file.lower()
            self.assertFalse(changed_file.startswith("backend/src/"), changed_file)
            self.assertNotIn("openapi", lowered, changed_file)
            self.assertNotIn("migration", lowered, changed_file)
            self.assertNotIn("requirements", lowered, changed_file)
            self.assertNotIn("sdk/", lowered, changed_file)
            self.assertNotIn("examples/", lowered.replace("docs/examples/gl196/public_smoke_matrix_pack.json", ""), changed_file)
            self.assertNotIn("frontend/", lowered, changed_file)
            self.assertNotIn("website/", lowered, changed_file)
            self.assertNotIn("design/", lowered, changed_file)
            self.assertNotIn(".github/workflows/", lowered, changed_file)


class TestGL196DocContent(unittest.TestCase):
    def setUp(self):
        self.doc = _load_doc().lower()

    def test_doc_mentions_required_topics(self):
        for phrase in REQUIRED_DOC_PHRASES:
            self.assertIn(phrase.lower(), self.doc)

    def test_doc_mentions_safety_routing(self):
        self.assertIn("github security advisories", self.doc)
        self.assertIn("security-sensitive reports", self.doc)

    def test_doc_mentions_public_caveats(self):
        for phrase in [
            "developer preview",
            "not production saas",
            "tenant/workspace isolation not implemented",
            "no real customer data",
            "no real secrets",
            "no private grants",
        ]:
            self.assertIn(phrase, self.doc)

    def test_doc_does_not_include_exploit_details(self):
        for phrase in [
            "proof-of-concept",
            "payload",
            "exploit reproduction",
            "attack steps",
        ]:
            self.assertNotIn(phrase, self.doc)

    def test_doc_mentions_next_recommended_issue(self):
        self.assertIn(
            "gl-196 combined merge-and-publish for public smoke matrix pack",
            self.doc,
        )


if __name__ == "__main__":
    unittest.main()
