"""GL-094B: Audit Log Immutability Review — artifact validation tests.

Validates that the review artifacts exist, are structurally correct,
and that no production code files were changed on this branch.
"""

import json
import os
import subprocess
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MD_PATH = os.path.join(REPO_ROOT, "docs", "audit_log_immutability_review.md")
JSON_PATH = os.path.join(
    REPO_ROOT, "docs", "examples", "gl094b", "audit_log_immutability_findings.json"
)

VALID_CONCLUSIONS = {"proceed", "proceed_with_cautions", "do_not_proceed"}

REQUIRED_FINDING_FIELDS = {
    "id",
    "severity",
    "status",
    "title",
    "description",
    "affectedFiles",
    "recommendedIssue",
}

VALID_SEVERITIES = {"critical", "high", "medium", "low", "informational"}
VALID_STATUSES = {"confirmed", "suspected", "test_gap", "resolved_by_existing_work"}

FORBIDDEN_PRODUCTION_PATHS = [
    "backend/src/",
    "frontend/",
    "migrations/",
    "openapi",
    "docs/openapi",
]


class TestGl094bMarkdownArtifact(unittest.TestCase):
    def _content(self):
        with open(MD_PATH, encoding="utf-8") as f:
            return f.read()

    def test_markdown_exists(self):
        self.assertTrue(os.path.isfile(MD_PATH), f"Missing: {MD_PATH}")

    def test_markdown_contains_review_only(self):
        self.assertIn("review-only", self._content().lower())

    def test_markdown_contains_immutability_risks(self):
        self.assertIn("Immutability risks", self._content())

    def test_markdown_contains_tamper_evidence_gaps(self):
        self.assertIn("Tamper-evidence gaps", self._content())

    def test_markdown_contains_recommended_implementation_issues(self):
        self.assertIn("Recommended implementation issues", self._content())

    def test_markdown_contains_conclusion(self):
        content = self._content()
        found = any(c in content for c in VALID_CONCLUSIONS)
        self.assertTrue(found, "Markdown must contain a valid conclusion keyword")


class TestGl094bJsonArtifact(unittest.TestCase):
    def _data(self):
        with open(JSON_PATH, encoding="utf-8") as f:
            return json.load(f)

    def test_json_exists(self):
        self.assertTrue(os.path.isfile(JSON_PATH), f"Missing: {JSON_PATH}")

    def test_json_is_valid(self):
        with open(JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)

    def test_review_id(self):
        self.assertEqual(self._data()["reviewId"], "GL-094B")

    def test_review_type(self):
        self.assertEqual(
            self._data()["reviewType"], "audit_log_immutability_review"
        )

    def test_findings_list_exists(self):
        data = self._data()
        self.assertIn("findings", data)
        self.assertIsInstance(data["findings"], list)
        self.assertGreater(len(data["findings"]), 0, "findings list must not be empty")

    def test_every_finding_has_required_fields(self):
        for finding in self._data()["findings"]:
            missing = REQUIRED_FINDING_FIELDS - finding.keys()
            self.assertFalse(
                missing,
                f"Finding {finding.get('id', '?')} is missing fields: {missing}",
            )

    def test_every_finding_has_valid_severity(self):
        for finding in self._data()["findings"]:
            self.assertIn(
                finding["severity"],
                VALID_SEVERITIES,
                f"Finding {finding.get('id', '?')} has invalid severity: {finding['severity']}",
            )

    def test_every_finding_has_valid_status(self):
        for finding in self._data()["findings"]:
            self.assertIn(
                finding["status"],
                VALID_STATUSES,
                f"Finding {finding.get('id', '?')} has invalid status: {finding['status']}",
            )

    def test_every_finding_has_affected_files_list(self):
        for finding in self._data()["findings"]:
            self.assertIsInstance(
                finding["affectedFiles"],
                list,
                f"Finding {finding.get('id', '?')}: affectedFiles must be a list",
            )

    def test_recommended_next_issues_exists(self):
        data = self._data()
        self.assertIn("recommendedNextIssues", data)
        self.assertIsInstance(data["recommendedNextIssues"], list)
        self.assertGreater(
            len(data["recommendedNextIssues"]),
            0,
            "recommendedNextIssues must not be empty",
        )

    def test_conclusion_is_valid(self):
        conclusion = self._data()["conclusion"]
        self.assertIn(
            conclusion,
            VALID_CONCLUSIONS,
            f"conclusion '{conclusion}' is not one of {VALID_CONCLUSIONS}",
        )

    def test_base_main_present(self):
        self.assertIn("baseMain", self._data())
        self.assertTrue(len(self._data()["baseMain"]) > 0)

    def test_finding_ids_are_unique(self):
        ids = [f["id"] for f in self._data()["findings"]]
        self.assertEqual(len(ids), len(set(ids)), "Finding IDs must be unique")


class TestGl094bNoBranchProductionChanges(unittest.TestCase):
    """Verify that no production code files were modified on this branch."""

    def _current_branch(self):
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        return result.stdout.strip()

    def _changed_files(self):
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        if result.returncode != 0:
            self.skipTest(f"git diff failed: {result.stderr}")
        return result.stdout.strip().splitlines()

    def test_no_production_source_changes(self):
        if self._current_branch() != "gl-094b-audit-log-immutability-review":
            self.skipTest("Production-source diff check only valid on original GL-094B feature branch")
        changed = self._changed_files()
        violations = [
            f
            for f in changed
            if any(f.startswith(p) for p in FORBIDDEN_PRODUCTION_PATHS)
        ]
        self.assertFalse(
            violations,
            f"Production files must not be changed on this branch: {violations}",
        )

    def test_expected_artifact_files_changed(self):
        expected = {
            "docs/audit_log_immutability_review.md",
            "docs/examples/gl094b/audit_log_immutability_findings.json",
            "backend/tests/test_gl094b_audit_log_immutability_review_artifact.py",
        }
        # Always: assert artifact files exist on disk
        for path in expected:
            self.assertTrue(
                os.path.isfile(os.path.join(REPO_ROOT, path)),
                f"Expected artifact file missing from disk: {path}",
            )
        # On the original GL-094B feature branch: also verify files appear in git diff
        if self._current_branch() != "gl-094b-audit-log-immutability-review":
            return
        changed = self._changed_files()
        for path in expected:
            self.assertIn(
                path, changed, f"Expected artifact file not found in branch diff: {path}"
            )

    def test_only_allowed_files_changed(self):
        if self._current_branch() != "gl-094b-audit-log-immutability-review":
            self.skipTest("Allowed-files diff check only valid on original GL-094B feature branch")
        changed = self._changed_files()
        allowed = {
            "docs/audit_log_immutability_review.md",
            "docs/examples/gl094b/audit_log_immutability_findings.json",
            "backend/tests/test_gl094b_audit_log_immutability_review_artifact.py",
        }
        unexpected = set(changed) - allowed
        self.assertFalse(
            unexpected,
            f"Unexpected files changed on branch (only review artifacts allowed): {unexpected}",
        )


if __name__ == "__main__":
    unittest.main()
