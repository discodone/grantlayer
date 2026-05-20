"""GL-085: Validation tests for the security and data integrity follow-up review gate.

These tests verify that the GL-085 review artifacts exist, are structurally valid,
and contain all required content. They do not test implementation behavior.
"""

import json
import os
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

REVIEW_DOC = os.path.join(REPO_ROOT, "docs", "security_data_integrity_followup_claude_review.md")
FINDINGS_JSON = os.path.join(
    REPO_ROOT, "docs", "examples", "gl085", "security_data_integrity_review_findings.json"
)

REQUIRED_FINDING_CATEGORIES = [
    "revoke_grant_request_atomicity",
    "migration_runner_dict_rows",
    "query_parameter_parsing",
    "read_endpoint_auth_enforcement",
    "demo_action_auth_hardening",
    "openapi_consistency",
    "error_response_safety",
    "test_quality",
    "remaining_security_risks",
    "production_readiness_gap",
]

FORBIDDEN_IMPLEMENTATION_FILES = [
    os.path.join(REPO_ROOT, "backend", "src", "server.py"),
    os.path.join(REPO_ROOT, "backend", "src", "grant_requests.py"),
    os.path.join(REPO_ROOT, "backend", "src", "grants.py"),
    os.path.join(REPO_ROOT, "backend", "src", "migrations", "runner.py"),
    os.path.join(REPO_ROOT, "docs", "openapi.yaml"),
]

REQUIRED_NEXT_ISSUE_IDS = {"GL-086", "GL-087", "GL-088", "GL-089", "GL-090", "GL-091"}


class TestReviewDocExists(unittest.TestCase):
    def test_review_doc_exists(self):
        self.assertTrue(
            os.path.isfile(REVIEW_DOC),
            f"Review document not found: {REVIEW_DOC}",
        )

    def test_findings_json_exists(self):
        self.assertTrue(
            os.path.isfile(FINDINGS_JSON),
            f"Findings JSON not found: {FINDINGS_JSON}",
        )


class TestReviewDocContent(unittest.TestCase):
    def setUp(self):
        with open(REVIEW_DOC, "r", encoding="utf-8") as f:
            self.content = f.read()

    def test_states_review_only(self):
        self.assertIn(
            "review-only",
            self.content.lower(),
            "Review doc must state that GL-085 is review-only",
        )

    def test_states_no_implementation(self):
        self.assertTrue(
            "adds no implementation" in self.content.lower()
            or "no implementation" in self.content.lower(),
            "Review doc must state that GL-085 adds no implementation",
        )

    def test_states_not_production_ready(self):
        self.assertTrue(
            "not production-ready" in self.content.lower()
            or "not production ready" in self.content.lower(),
            "Review doc must state that GrantLayer is not production-ready",
        )

    def test_references_periodic_claude_review(self):
        self.assertTrue(
            "periodically" in self.content.lower()
            or "periodic" in self.content.lower(),
            "Review doc must reference periodic (not mandatory per-issue) Claude Code use",
        )

    def test_has_review_disposition(self):
        self.assertIn(
            "disposition",
            self.content.lower(),
            "Review doc must include a review disposition section",
        )

    def test_has_stop_gates_section(self):
        self.assertIn(
            "stop gate",
            self.content.lower(),
            "Review doc must include a stop gates section",
        )

    def test_has_recommended_next_issues(self):
        self.assertIn(
            "recommended next",
            self.content.lower(),
            "Review doc must include recommended next issues",
        )

    def test_covers_all_five_issues(self):
        for issue in ("GL-080", "GL-081", "GL-082", "GL-083", "GL-084"):
            self.assertIn(issue, self.content, f"Review doc must reference {issue}")


class TestFindingsJsonStructure(unittest.TestCase):
    def setUp(self):
        with open(FINDINGS_JSON, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def test_json_is_valid(self):
        self.assertIsInstance(self.data, dict)

    def test_has_findings_list(self):
        self.assertIn("findings", self.data)
        self.assertIsInstance(self.data["findings"], list)

    def test_all_required_finding_categories_present(self):
        categories = {f["category"] for f in self.data["findings"]}
        for required in REQUIRED_FINDING_CATEGORIES:
            self.assertIn(
                required,
                categories,
                f"Findings JSON must include category: {required}",
            )

    def test_each_finding_has_required_fields(self):
        required_fields = {"status", "summary", "risk_level", "recommendation", "related_files", "related_issue"}
        for finding in self.data["findings"]:
            missing = required_fields - set(finding.keys())
            self.assertEqual(
                missing,
                set(),
                f"Finding '{finding.get('category', '?')}' is missing fields: {missing}",
            )

    def test_has_at_least_six_recommended_next_issues(self):
        issues = self.data.get("recommended_next_issues", [])
        self.assertGreaterEqual(
            len(issues),
            6,
            "Findings JSON must include at least 6 recommended next issues",
        )

    def test_recommended_next_issues_include_required_ids(self):
        issue_ids = {i["id"] for i in self.data.get("recommended_next_issues", [])}
        for required_id in REQUIRED_NEXT_ISSUE_IDS:
            self.assertIn(
                required_id,
                issue_ids,
                f"Findings JSON must include recommended issue: {required_id}",
            )

    def test_has_stop_gates(self):
        self.assertIn("stop_gates", self.data)
        self.assertIsInstance(self.data["stop_gates"], list)
        self.assertGreater(len(self.data["stop_gates"]), 0, "stop_gates must not be empty")

    def test_has_review_disposition(self):
        self.assertIn("review_disposition", self.data)
        disposition = self.data["review_disposition"]
        self.assertIn(
            disposition,
            ("proceed", "proceed_with_cautions", "blocked"),
            f"review_disposition must be one of proceed/proceed_with_cautions/blocked, got: {disposition}",
        )

    def test_has_review_scope(self):
        self.assertIn("review_scope", self.data)
        self.assertIsInstance(self.data["review_scope"], list)
        self.assertGreater(len(self.data["review_scope"]), 0)

    def test_has_reviewed_issues(self):
        self.assertIn("reviewed_issues", self.data)
        self.assertEqual(len(self.data["reviewed_issues"]), 5)

    def test_has_reviewed_files(self):
        self.assertIn("reviewed_files", self.data)
        self.assertGreater(len(self.data["reviewed_files"]), 0)


class TestNoForbiddenFilesChanged(unittest.TestCase):
    def _get_branch_changed_files(self):
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        return set(result.stdout.strip().splitlines())

    def test_no_production_code_changed(self):
        changed = self._get_branch_changed_files()
        forbidden_relative = {
            "backend/src/server.py",
            "backend/src/grant_requests.py",
            "backend/src/grants.py",
            "backend/src/migrations/runner.py",
            "docs/openapi.yaml",
        }
        violations = changed & forbidden_relative
        self.assertEqual(
            violations,
            set(),
            f"GL-085 must not change production files: {violations}",
        )

    def test_only_review_artifacts_changed(self):
        changed = self._get_branch_changed_files()
        allowed_prefixes = (
            "docs/security_data_integrity_followup_claude_review.md",
            "docs/examples/gl085/",
            "backend/tests/test_gl085_",
            "docs/product_foundation_implementation_cut.md",
        )
        for path in changed:
            is_allowed = any(path.startswith(prefix) or path == prefix for prefix in allowed_prefixes)
            self.assertTrue(
                is_allowed,
                f"GL-085 branch contains unexpected changed file: {path}",
            )


if __name__ == "__main__":
    unittest.main()
