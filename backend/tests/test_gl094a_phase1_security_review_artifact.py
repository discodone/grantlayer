"""
GL-094A: Phase 1 Security Remediation Review — Artifact Validation Tests

Validates that the review markdown, JSON findings, and this test file itself
are present and structurally correct. Does not modify any production code.
"""
import json
import os
import subprocess
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MARKDOWN_PATH = os.path.join(REPO_ROOT, "docs", "phase1_security_remediation_review.md")
JSON_PATH = os.path.join(REPO_ROOT, "docs", "examples", "gl094a", "phase1_security_review_findings.json")

VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}
VALID_STATUSES = {"implemented", "gap", "regression", "inconsistency", "note"}
VALID_CONCLUSIONS = {"proceed", "proceed_with_cautions", "do_not_proceed"}
EXPECTED_ISSUES = {"GL-088", "GL-089", "GL-090", "GL-091", "GL-092", "GL-093"}
EXPECTED_REVIEW_ID = "GL-094A"
EXPECTED_BASE_MAIN = "5b63026fdc333f36e4b0a3f6713cf4436ff76a63"


def _load_json():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestMarkdownArtifact(unittest.TestCase):

    def test_markdown_exists(self):
        self.assertTrue(os.path.isfile(MARKDOWN_PATH), f"Missing: {MARKDOWN_PATH}")

    def test_markdown_non_empty(self):
        self.assertGreater(os.path.getsize(MARKDOWN_PATH), 0, "Markdown file is empty")

    def test_review_only_statement_in_markdown(self):
        with open(MARKDOWN_PATH, encoding="utf-8") as f:
            content = f.read()
        has_statement = (
            "review-only" in content.lower()
            or "no production" in content.lower()
            or "Review-only" in content
        )
        self.assertTrue(
            has_statement,
            "Markdown must contain a review-only statement (no production code changes)",
        )

    def test_markdown_contains_all_reviewed_issues(self):
        with open(MARKDOWN_PATH, encoding="utf-8") as f:
            content = f.read()
        for issue in EXPECTED_ISSUES:
            self.assertIn(issue, content, f"Markdown does not mention {issue}")

    def test_markdown_contains_conclusion(self):
        with open(MARKDOWN_PATH, encoding="utf-8") as f:
            content = f.read()
        has_conclusion = any(c in content for c in VALID_CONCLUSIONS)
        self.assertTrue(has_conclusion, "Markdown does not contain a valid conclusion keyword")


class TestJsonArtifact(unittest.TestCase):

    def test_json_exists(self):
        self.assertTrue(os.path.isfile(JSON_PATH), f"Missing: {JSON_PATH}")

    def test_json_valid(self):
        data = _load_json()
        self.assertIsInstance(data, dict)

    def test_review_id(self):
        data = _load_json()
        self.assertEqual(data.get("reviewId"), EXPECTED_REVIEW_ID)

    def test_base_main(self):
        data = _load_json()
        self.assertEqual(data.get("baseMain"), EXPECTED_BASE_MAIN)

    def test_reviewed_issues_contains_all(self):
        data = _load_json()
        reviewed = set(data.get("reviewedIssues", []))
        missing = EXPECTED_ISSUES - reviewed
        self.assertFalse(missing, f"Missing from reviewedIssues: {missing}")

    def test_findings_exist(self):
        data = _load_json()
        findings = data.get("findings", [])
        self.assertIsInstance(findings, list)
        self.assertGreater(len(findings), 0, "findings must be non-empty")

    def test_findings_schema(self):
        data = _load_json()
        required_keys = {"id", "severity", "status", "title", "description", "affectedFiles", "recommendedIssue"}
        for i, finding in enumerate(data.get("findings", [])):
            missing = required_keys - set(finding.keys())
            self.assertFalse(missing, f"findings[{i}] missing keys: {missing}")

    def test_findings_severity_values(self):
        data = _load_json()
        for i, finding in enumerate(data.get("findings", [])):
            severity = finding.get("severity", "")
            self.assertIn(
                severity,
                VALID_SEVERITIES,
                f"findings[{i}].severity '{severity}' not in {VALID_SEVERITIES}",
            )

    def test_findings_status_values(self):
        data = _load_json()
        for i, finding in enumerate(data.get("findings", [])):
            status = finding.get("status", "")
            self.assertIn(
                status,
                VALID_STATUSES,
                f"findings[{i}].status '{status}' not in {VALID_STATUSES}",
            )

    def test_findings_affected_files_is_list(self):
        data = _load_json()
        for i, finding in enumerate(data.get("findings", [])):
            self.assertIsInstance(
                finding.get("affectedFiles"),
                list,
                f"findings[{i}].affectedFiles must be a list",
            )

    def test_recommended_next_issues_exists(self):
        data = _load_json()
        next_issues = data.get("recommendedNextIssues", [])
        self.assertIsInstance(next_issues, list)
        self.assertGreater(len(next_issues), 0, "recommendedNextIssues must be non-empty")

    def test_recommended_next_issues_count(self):
        data = _load_json()
        next_issues = data.get("recommendedNextIssues", [])
        self.assertGreaterEqual(len(next_issues), 5, "At least 5 recommendedNextIssues required")

    def test_recommended_next_issues_have_issue_id(self):
        data = _load_json()
        for i, issue in enumerate(data.get("recommendedNextIssues", [])):
            self.assertIn(
                "issueId",
                issue,
                f"recommendedNextIssues[{i}] missing issueId",
            )

    def test_conclusion_valid(self):
        data = _load_json()
        conclusion = data.get("conclusion", "")
        self.assertIn(
            conclusion,
            VALID_CONCLUSIONS,
            f"conclusion '{conclusion}' not in {VALID_CONCLUSIONS}",
        )


class TestNoProductionFilesChanged(unittest.TestCase):
    def setUp(self):
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if result.stdout.strip() != "gl-094a-phase1-security-review":
            self.skipTest("Branch-wide diff check only valid on original GL-094A review branch")

    def test_no_production_files_changed(self):
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        changed = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        production_src = [
            f for f in changed
            if f.startswith("backend/src/")
        ]
        self.assertFalse(
            production_src,
            f"Production source files must not be changed in a review-only branch: {production_src}",
        )

    def test_artifact_files_present_in_diff(self):
        expected_artifacts = {
            "docs/phase1_security_remediation_review.md",
            "docs/examples/gl094a/phase1_security_review_findings.json",
            "backend/tests/test_gl094a_phase1_security_review_artifact.py",
        }

        # Primary assertion: artifact files must exist on disk regardless of branch.
        missing_on_disk = {
            a for a in expected_artifacts
            if not os.path.isfile(os.path.join(REPO_ROOT, a))
        }
        self.assertFalse(
            missing_on_disk,
            f"Expected GL-094A artifact files not found on disk: {missing_on_disk}",
        )

        # Secondary assertion: on the GL-094A introducing branch the three
        # artifacts must appear in the branch diff or working-tree status.
        # The review markdown is the sentinel: if it is absent from the diff,
        # the GL-094A artifacts were already merged to main and the disk-
        # existence check above is the meaningful assertion.
        diff_result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        committed = set(diff_result.stdout.splitlines())
        if "docs/phase1_security_remediation_review.md" not in committed:
            return

        # Review markdown is new in this branch — all three artifacts must appear.
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        # porcelain lines: "?? path" or " M path" — extract the path (last token).
        # New directories appear as "?? dir/" so we match prefix as well.
        status_tokens = {
            line.strip().split()[-1]
            for line in status_result.stdout.splitlines()
            if line.strip()
        }
        missing = set()
        for artifact in expected_artifacts:
            in_committed = artifact in committed
            in_status = any(
                artifact == token or artifact.startswith(token.rstrip("/"))
                for token in status_tokens
            )
            if not (in_committed or in_status):
                missing.add(artifact)
        self.assertFalse(
            missing,
            f"Expected artifact files not found in git diff/status: {missing}",
        )


if __name__ == "__main__":
    unittest.main()
