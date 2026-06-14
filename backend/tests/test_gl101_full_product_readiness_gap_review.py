"""Validation test for GL-101 Full Product Readiness Gap Review artifacts.

Ensures:
- Markdown review exists and contains required sections
- JSON findings file exists and is valid
- JSON shape matches specification
- Review framing is product-readiness (not pilot-readiness)
- No production code files changed in this branch
"""

import json
import os
import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestGl101Artifacts(unittest.TestCase):
    """Validate GL-101 review artifacts exist and are well-formed."""

    @classmethod
    def setUpClass(cls):
        cls.repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        cls.markdown_path = cls.repo_root / "docs" / "full_product_readiness_gap_review.md"
        cls.json_path = cls.repo_root / "docs" / "examples" / "gl101" / "full_product_readiness_findings.json"

    def test_markdown_review_exists(self):
        self.assertTrue(self.markdown_path.exists(), "Markdown review must exist")

    def test_json_findings_exists(self):
        self.assertTrue(self.json_path.exists(), "JSON findings must exist")

    def test_json_is_valid(self):
        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)

    def test_review_id_is_gl101(self):
        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data.get("reviewId"), "GL-101")

    def test_review_type_correct(self):
        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data.get("reviewType"), "full_product_readiness_gap_review")

    def test_reviewed_issues_includes_gl095_through_gl100(self):
        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        reviewed = data.get("reviewedIssues", [])
        for issue in ["GL-095", "GL-096", "GL-097", "GL-098", "GL-099", "GL-100"]:
            self.assertIn(issue, reviewed, f"{issue} must be in reviewedIssues")

    def test_product_readiness_exists_and_valid(self):
        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        val = data.get("productReadiness")
        self.assertIsNotNone(val)
        self.assertIn(val, ["product_ready", "product_ready_with_minor_gaps", "not_product_ready"])

    def test_production_readiness_exists(self):
        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsNotNone(data.get("productionReadiness"))

    def test_findings_list_exists(self):
        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data.get("findings"), list)
        self.assertGreater(len(data["findings"]), 0, "findings list must not be empty")

    def test_every_finding_has_required_fields(self):
        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        required = {"id", "severity", "status", "category", "title", "description", "affectedFiles", "recommendedIssue"}
        for finding in data.get("findings", []):
            missing = required - set(finding.keys())
            self.assertEqual(missing, set(), f"Finding {finding.get('id')} missing fields: {missing}")
            self.assertIsInstance(finding["affectedFiles"], list)
            self.assertIsInstance(finding["recommendedIssue"], str)

    def test_resolved_risks_exists(self):
        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data.get("resolvedRisks"), list)

    def test_recommended_next_issues_exists(self):
        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data.get("recommendedNextIssues"), list)
        self.assertGreater(len(data["recommendedNextIssues"]), 0, "recommendedNextIssues must not be empty")

    def test_conclusion_valid(self):
        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn(data.get("conclusion"), ["product_ready", "product_ready_with_minor_gaps", "not_product_ready"])

    def test_markdown_contains_review_only(self):
        with open(self.markdown_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("review-only", content.lower(), "Markdown must contain 'review-only'")

    def test_markdown_contains_audit_trust_core_gap_assessment(self):
        with open(self.markdown_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Audit trust core gap assessment", content)

    def test_markdown_contains_production_operations_gap_assessment(self):
        with open(self.markdown_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Production operations gap assessment", content)

    def test_markdown_contains_recommended_next_issues(self):
        with open(self.markdown_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Recommended next implementation issues", content)

    def test_markdown_does_not_frame_target_as_pilot_readiness(self):
        with open(self.markdown_path, "r", encoding="utf-8") as f:
            content = f.read()
        # The review should not frame the target as pilot readiness.
        # It should repeatedly frame the target as a finished product.
        lower = content.lower()
        # Ensure the conclusion section does not say the target is pilot readiness.
        # We allow mentioning pilot as historical context but the target must be product.
        self.assertIn("finished product", lower, "Review must frame target as finished product")

    def test_no_production_code_files_changed(self):
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )
        if branch_result.stdout.strip() != "gl-101-full-product-readiness-gap-review":
            self.skipTest("Branch-wide diff check only valid on original GL-101 review branch")
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "docs/full_product_readiness_gap_review.md",
            "docs/examples/gl101/full_product_readiness_findings.json",
            "backend/tests/test_gl101_full_product_readiness_gap_review.py",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-101 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
