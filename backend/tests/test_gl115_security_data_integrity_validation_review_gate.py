"""GL-115: Security / Data Integrity / Validation Review Gate — artifact integrity tests."""

import json
import os
import subprocess
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

REVIEW_MD = os.path.join(REPO_ROOT, "docs", "security_data_integrity_validation_review_gate.md")
FINDINGS_JSON = os.path.join(
    REPO_ROOT, "docs", "examples", "gl115", "security_data_integrity_validation_findings.json"
)

EXPECTED_COMMIT = "179d7d8bc6ea8203ee86c8047e3ef63aa2707c27"
VALID_DISPOSITIONS = {"proceed", "proceed_with_cautions", "blocked"}
VALID_SEVERITIES = {"critical", "high", "medium", "low"}

ALLOWED_CHANGED_FILES = {
    "docs/security_data_integrity_validation_review_gate.md",
    "docs/examples/gl115/security_data_integrity_validation_findings.json",
    "backend/tests/test_gl115_security_data_integrity_validation_review_gate.py",
}

REQUIRED_FINDING_FIELDS = {
    "id",
    "severity",
    "category",
    "title",
    "evidence",
    "risk",
    "recommendation",
    "suggested_issue_title",
    "implementation_scope",
    "blocks_production",
}

REQUIRED_NEXT_ISSUE_FIELDS = {
    "title",
    "rationale",
    "expected_changed_files",
    "forbidden_changes",
    "acceptance_summary",
}


def _load_findings():
    with open(FINDINGS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def _git_diff_files():
    result = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


class TestGL115ReviewArtifactExists(unittest.TestCase):

    def test_review_markdown_exists(self):
        self.assertTrue(
            os.path.isfile(REVIEW_MD),
            f"Review markdown not found: {REVIEW_MD}",
        )

    def test_findings_json_exists(self):
        self.assertTrue(
            os.path.isfile(FINDINGS_JSON),
            f"Findings JSON not found: {FINDINGS_JSON}",
        )


class TestGL115FindingsJSON(unittest.TestCase):

    def setUp(self):
        self.data = _load_findings()

    def test_findings_json_parses(self):
        self.assertIsInstance(self.data, dict)

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-115")

    def test_review_type(self):
        self.assertEqual(
            self.data.get("review_type"),
            "security_data_integrity_validation_review_gate",
        )

    def test_disposition_valid(self):
        disposition = self.data.get("disposition")
        self.assertIn(
            disposition,
            VALID_DISPOSITIONS,
            f"disposition '{disposition}' is not one of {VALID_DISPOSITIONS}",
        )

    def test_reviewed_after_main_commit(self):
        self.assertEqual(
            self.data.get("reviewed_after_main_commit"),
            EXPECTED_COMMIT,
        )

    def test_findings_non_empty(self):
        findings = self.data.get("findings", [])
        self.assertIsInstance(findings, list)
        self.assertGreater(len(findings), 0, "findings array must not be empty")

    def test_recommended_next_issues_non_empty(self):
        issues = self.data.get("recommended_next_issues", [])
        self.assertIsInstance(issues, list)
        self.assertGreater(len(issues), 0, "recommended_next_issues array must not be empty")

    def test_reviewed_areas_non_empty(self):
        areas = self.data.get("reviewed_areas", [])
        self.assertIsInstance(areas, list)
        self.assertGreater(len(areas), 0, "reviewed_areas must not be empty")

    def test_resolved_risks_non_empty(self):
        risks = self.data.get("resolved_or_improved_risks", [])
        self.assertIsInstance(risks, list)
        self.assertGreater(len(risks), 0, "resolved_or_improved_risks must not be empty")

    def test_production_readiness_summary_exists(self):
        summary = self.data.get("production_readiness_summary")
        self.assertIsNotNone(summary, "production_readiness_summary key must be present")
        self.assertIsInstance(summary, dict)

    def test_finding_fields(self):
        findings = self.data.get("findings", [])
        for finding in findings:
            for field in REQUIRED_FINDING_FIELDS:
                self.assertIn(
                    field,
                    finding,
                    f"Finding '{finding.get('id', '?')}' is missing required field '{field}'",
                )

    def test_finding_severities_valid(self):
        findings = self.data.get("findings", [])
        for finding in findings:
            severity = finding.get("severity")
            self.assertIn(
                severity,
                VALID_SEVERITIES,
                f"Finding '{finding.get('id', '?')}' has invalid severity '{severity}'",
            )

    def test_finding_blocks_production_bool(self):
        findings = self.data.get("findings", [])
        for finding in findings:
            bp = finding.get("blocks_production")
            self.assertIsInstance(
                bp,
                bool,
                f"Finding '{finding.get('id', '?')}' blocks_production must be bool, got {type(bp).__name__}",
            )

    def test_high_or_medium_if_not_proceed(self):
        disposition = self.data.get("disposition")
        if disposition == "proceed":
            return
        findings = self.data.get("findings", [])
        high_or_medium = [f for f in findings if f.get("severity") in {"high", "medium"}]
        self.assertGreater(
            len(high_or_medium),
            0,
            f"disposition is '{disposition}' but no high or medium findings found",
        )

    def test_recommended_next_issue_fields(self):
        issues = self.data.get("recommended_next_issues", [])
        for issue in issues:
            for field in REQUIRED_NEXT_ISSUE_FIELDS:
                self.assertIn(
                    field,
                    issue,
                    f"Recommended issue '{issue.get('title', '?')}' is missing required field '{field}'",
                )


class TestGL115ScopeClean(unittest.TestCase):

    def _get_diff_files(self):
        files = _git_diff_files()
        if files is None:
            self.skipTest("git diff main...HEAD failed — likely not on feature branch")
        return files

    def test_scope_only_allowed_files(self):
        diff_files = self._get_diff_files()
        unexpected = set(diff_files) - ALLOWED_CHANGED_FILES
        self.assertEqual(
            unexpected,
            set(),
            f"Unexpected files in diff: {sorted(unexpected)}",
        )

    def test_no_production_code_changed(self):
        diff_files = self._get_diff_files()
        prod_changes = [f for f in diff_files if f.startswith("backend/src/")]
        self.assertEqual(
            prod_changes,
            [],
            f"Production code files changed: {prod_changes}",
        )

    def test_no_openapi_changed(self):
        diff_files = self._get_diff_files()
        openapi_changes = [f for f in diff_files if "openapi" in f]
        self.assertEqual(
            openapi_changes,
            [],
            f"OpenAPI files changed: {openapi_changes}",
        )

    def test_no_migration_files_changed(self):
        diff_files = self._get_diff_files()
        migration_changes = [
            f for f in diff_files if "migrations" in f or "alembic" in f
        ]
        self.assertEqual(
            migration_changes,
            [],
            f"Migration files changed: {migration_changes}",
        )

    def test_no_frontend_files_changed(self):
        diff_files = self._get_diff_files()
        frontend_changes = [
            f for f in diff_files
            if f.startswith("frontend/") or f.startswith("website/")
        ]
        self.assertEqual(
            frontend_changes,
            [],
            f"Frontend/website files changed: {frontend_changes}",
        )


if __name__ == "__main__":
    unittest.main()
