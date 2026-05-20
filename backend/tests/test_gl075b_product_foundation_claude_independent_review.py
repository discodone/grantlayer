"""Tests for GL-075B Product Foundation Independent Claude Code Review.

Lightweight validation proving the independent Claude Code review is:
- present as a human-readable document
- present as a machine-readable JSON file
- explicitly review-only with no implementation
- not replacing or reverting GL-075
- not claiming production readiness
- free of forbidden implementation file changes
- recommending GL-077 as next issue (already completed)
- including all required finding categories
- including stop gates
- including a valid review disposition
"""

import json
import pathlib
import unittest


class TestGL075BProductFoundationClaudeIndependentReview(unittest.TestCase):
    """GL-075B: Validate Product Foundation Independent Claude Code Review artifacts."""

    REPO_ROOT = pathlib.Path(__file__).with_suffix("").parent.parent.parent
    DOCS_DIR = REPO_ROOT / "docs"
    EXAMPLE_DIR_GL075B = DOCS_DIR / "examples" / "gl075b"
    BACKEND_SRC_DIR = REPO_ROOT / "backend" / "src"

    REQUIRED_FINDING_CATEGORIES = [
        "gl075_review_validity",
        "gl076_runtime_config_implementation",
        "security_secret_exposure",
        "api_first_boundary",
        "implementation_sequence",
        "test_strategy",
        "next_issue_gl077_readiness",
    ]

    FORBIDDEN_IMPL_PATHS = [
        BACKEND_SRC_DIR / "health.py",
        BACKEND_SRC_DIR / "logging_helper.py",
        BACKEND_SRC_DIR / "secrets.py",
        BACKEND_SRC_DIR / "persistence.py",
        BACKEND_SRC_DIR / "deployment_validation.py",
        BACKEND_SRC_DIR / "metrics.py",
        BACKEND_SRC_DIR / "alerting.py",
        BACKEND_SRC_DIR / "backup.py",
        BACKEND_SRC_DIR / "restore.py",
        BACKEND_SRC_DIR / "lifecycle.py",
        BACKEND_SRC_DIR / "incident_response.py",
        BACKEND_SRC_DIR / "runbook.py",
    ]

    @classmethod
    def setUpClass(cls):
        cls.review_doc_path = cls.DOCS_DIR / "product_foundation_claude_independent_review.md"
        cls.findings_json_path = cls.EXAMPLE_DIR_GL075B / "product_foundation_independent_review_findings.json"

        cls.findings_json = None
        if cls.findings_json_path.exists():
            cls.findings_json = json.loads(cls.findings_json_path.read_text(encoding="utf-8"))

        cls.review_doc_text = ""
        if cls.review_doc_path.exists():
            cls.review_doc_text = cls.review_doc_path.read_text(encoding="utf-8")

    # ── 1. Review document exists ──────────────────────────────────────
    def test_review_doc_exists(self):
        self.assertTrue(
            self.review_doc_path.exists(),
            "docs/product_foundation_claude_independent_review.md must exist",
        )

    # ── 2. JSON findings file exists ──────────────────────────────────
    def test_findings_json_exists(self):
        self.assertTrue(
            self.findings_json_path.exists(),
            "docs/examples/gl075b/product_foundation_independent_review_findings.json must exist",
        )

    # ── 3. JSON findings file is valid JSON ───────────────────────────
    def test_findings_json_is_valid(self):
        self.assertIsNotNone(self.findings_json, "Findings JSON must parse as valid JSON")
        self.assertIsInstance(self.findings_json, dict)

    # ── 4. Review doc states GL-075B is review-only ──────────────────
    def test_review_doc_states_review_only(self):
        content = self.review_doc_text.lower()
        self.assertIn(
            "gl-075b is review-only",
            content,
            "Review doc must explicitly state 'GL-075B is review-only'",
        )

    # ── 5. Review doc states GL-075B adds no implementation ──────────
    def test_review_doc_states_no_implementation(self):
        content = self.review_doc_text.lower()
        self.assertIn(
            "gl-075b adds no implementation",
            content,
            "Review doc must explicitly state 'GL-075B adds no implementation'",
        )

    # ── 6. Review doc states GL-075B does not replace or revert GL-075
    def test_review_doc_states_does_not_replace_or_revert_gl075(self):
        content = self.review_doc_text.lower()
        self.assertIn(
            "gl-075b does not replace or revert gl-075",
            content,
            "Review doc must explicitly state 'GL-075B does not replace or revert GL-075'",
        )

    # ── 7. Review doc states GrantLayer is not production-ready yet ──
    def test_review_doc_states_not_production_ready(self):
        content = self.review_doc_text.lower()
        self.assertIn(
            "grantlayer is not production-ready yet",
            content,
            "Review doc must explicitly state 'GrantLayer is not production-ready yet'",
        )

    # ── 8. Review doc references periodic Claude Code review ─────────
    def test_review_doc_references_periodic_claude_review(self):
        content = self.review_doc_text.lower()
        periodic_found = (
            "periodic" in content
            or "not a required step for every issue" in content
            or "not for every issue" in content
        )
        self.assertTrue(
            periodic_found,
            "Review doc must reference periodic Claude Code review, not mandatory for every issue",
        )

    # ── 9. JSON includes all required finding categories ──────────────
    def test_json_includes_all_required_finding_categories(self):
        findings = self.findings_json.get("findings", [])
        found_categories = {f.get("category") for f in findings}
        for expected in self.REQUIRED_FINDING_CATEGORIES:
            with self.subTest(category=expected):
                self.assertIn(
                    expected,
                    found_categories,
                    f"Findings JSON must include category '{expected}'",
                )

    # ── 10. JSON includes GL-077 in recommended next issues ───────────
    def test_json_includes_gl077_as_recommended_next_issue(self):
        items = self.findings_json.get("recommended_next_issues", [])
        issue_ids = {item.get("issue") for item in items}
        self.assertIn(
            "GL-077",
            issue_ids,
            "Findings JSON must include GL-077 in recommended_next_issues",
        )

    # ── 11. JSON includes stop gates ──────────────────────────────────
    def test_json_includes_stop_gates(self):
        stop_gates = self.findings_json.get("stop_gates", [])
        self.assertGreaterEqual(
            len(stop_gates),
            1,
            "Findings JSON must include at least 1 stop gate",
        )

    # ── 12. JSON includes a valid review disposition ──────────────────
    def test_json_includes_valid_review_disposition(self):
        disposition = self.findings_json.get("review_disposition", "")
        self.assertIn(
            disposition,
            {"proceed", "proceed_with_cautions", "blocked"},
            "Findings JSON must include a valid review_disposition",
        )

    # ── 13. No forbidden implementation files are changed ────────────
    def test_no_forbidden_implementation_files_created(self):
        for path in self.FORBIDDEN_IMPL_PATHS:
            self.assertFalse(
                path.exists(),
                f"Forbidden implementation file must not exist: {path}",
            )

    # ── 14. JSON findings each include required fields ────────────────
    def test_json_findings_include_required_fields(self):
        findings = self.findings_json.get("findings", [])
        self.assertGreater(len(findings), 0, "Findings JSON must have at least one finding")
        for finding in findings:
            with self.subTest(category=finding.get("category")):
                self.assertIn("status", finding, "Finding must include 'status'")
                self.assertIn("summary", finding, "Finding must include 'summary'")
                self.assertIn("risk_level", finding, "Finding must include 'risk_level'")
                self.assertIn("recommendation", finding, "Finding must include 'recommendation'")
                self.assertIn("related_files", finding, "Finding must include 'related_files'")
                self.assertIsInstance(finding["related_files"], list)
                self.assertGreaterEqual(
                    len(finding["related_files"]),
                    1,
                    f"Finding '{finding.get('category')}' must have at least 1 related_file",
                )

    # ── 15. JSON includes GL-078 and GL-079 as recommended next issues
    def test_json_includes_gl078_and_gl079_as_recommended_next_issues(self):
        items = self.findings_json.get("recommended_next_issues", [])
        issue_ids = {item.get("issue") for item in items}
        for required in ("GL-078", "GL-079"):
            with self.subTest(issue=required):
                self.assertIn(
                    required,
                    issue_ids,
                    f"Findings JSON must include {required} in recommended_next_issues",
                )

    # ── 16. JSON findings field is a list ─────────────────────────────
    def test_json_findings_is_list(self):
        findings = self.findings_json.get("findings", None)
        self.assertIsInstance(findings, list, "findings must be a list")

    # ── 17. JSON includes review_scope ────────────────────────────────
    def test_json_includes_review_scope(self):
        scope = self.findings_json.get("review_scope", "")
        self.assertIsInstance(scope, str)
        self.assertGreater(len(scope), 0, "review_scope must be non-empty")

    # ── 18. JSON includes reviewed_documents list ─────────────────────
    def test_json_includes_reviewed_documents(self):
        docs = self.findings_json.get("reviewed_documents", [])
        self.assertIsInstance(docs, list)
        self.assertGreaterEqual(len(docs), 5, "reviewed_documents must list at least 5 documents")

    # ── 19. JSON includes reviewed_code_files list ────────────────────
    def test_json_includes_reviewed_code_files(self):
        files = self.findings_json.get("reviewed_code_files", [])
        self.assertIsInstance(files, list)
        self.assertGreaterEqual(len(files), 1, "reviewed_code_files must list at least 1 file")


if __name__ == "__main__":
    unittest.main(verbosity=2)
