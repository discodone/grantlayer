"""Tests for GL-075 Product Foundation Claude Review Gate.

Lightweight validation test proving the Claude review gate is:
- present as a human-readable document
- present as a machine-readable JSON file
- explicitly review-only with no implementation
- not claiming production readiness
- recommending periodic Claude Code review, not mandatory review for every issue
- free of forbidden implementation file changes
"""

import json
import pathlib
import unittest


class TestGL075ProductFoundationClaudeReviewGate(unittest.TestCase):
    """GL-075: Validate Product Foundation Claude Review Gate artifacts."""

    REPO_ROOT = pathlib.Path(__file__).with_suffix("").parent.parent.parent
    DOCS_DIR = REPO_ROOT / "docs"
    EXAMPLE_DIR_GL075 = DOCS_DIR / "examples" / "gl075"
    BACKEND_SRC_DIR = REPO_ROOT / "backend" / "src"
    BACKEND_TESTS_DIR = REPO_ROOT / "backend" / "tests"

    REQUIRED_FINDING_CATEGORIES = [
        "api_contract",
        "architecture_boundaries",
        "runtime_configuration",
        "operator_auth_access",
        "secret_management",
        "persistence_postgresql",
        "observability_logging",
        "backup_restore_lifecycle",
        "operational_runbook_incident_response",
        "implementation_sequence",
    ]

    FORBIDDEN_SRC_PATHS = [
        BACKEND_SRC_DIR / "health.py",
        BACKEND_SRC_DIR / "logging_helper.py",
        BACKEND_SRC_DIR / "secrets.py",
        BACKEND_SRC_DIR / "persistence.py",
        BACKEND_SRC_DIR / "deployment_validation.py",
        BACKEND_SRC_DIR / "auth",
        BACKEND_SRC_DIR / "metrics.py",
        BACKEND_SRC_DIR / "alerting.py",
        BACKEND_SRC_DIR / "backup.py",
        BACKEND_SRC_DIR / "restore.py",
        BACKEND_SRC_DIR / "lifecycle.py",
        BACKEND_SRC_DIR / "incident_response.py",
        BACKEND_SRC_DIR / "runbook.py",
        BACKEND_SRC_DIR / "monitoring.py",
    ]

    FORBIDDEN_TEST_PATTERNS = [
        BACKEND_TESTS_DIR / "test_gl076_health_readiness_baseline.py",
        BACKEND_TESTS_DIR / "test_gl077_structured_logging_baseline.py",
        BACKEND_TESTS_DIR / "test_gl078_secret_source_boundary.py",
        BACKEND_TESTS_DIR / "test_gl079_persistence_backend_abstraction.py",
        BACKEND_TESTS_DIR / "test_gl080_deployment_runtime_mode_validation.py",
        BACKEND_TESTS_DIR / "test_gl081_operator_access_hardening.py",
    ]

    @classmethod
    def setUpClass(cls):
        cls.review_doc_path = cls.DOCS_DIR / "product_foundation_claude_review_gate.md"
        cls.findings_json_path = cls.EXAMPLE_DIR_GL075 / "product_foundation_review_findings.json"

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
            "docs/product_foundation_claude_review_gate.md must exist",
        )

    # ── 2. JSON findings file exists ──────────────────────────────────
    def test_findings_json_exists(self):
        self.assertTrue(
            self.findings_json_path.exists(),
            "docs/examples/gl075/product_foundation_review_findings.json must exist",
        )

    # ── 3. JSON findings file is valid JSON ───────────────────────────
    def test_findings_json_is_valid(self):
        self.assertIsNotNone(self.findings_json, "Findings JSON must parse as valid JSON")
        self.assertIsInstance(self.findings_json, dict)

    # ── 4. Review doc states GL-075 is review-only ───────────────────
    def test_review_doc_states_review_only(self):
        content = self.review_doc_text.lower()
        self.assertIn("gl-075 is review-only", content)

    # ── 5. Review doc states GL-075 adds no implementation ───────────
    def test_review_doc_states_no_implementation(self):
        content = self.review_doc_text.lower()
        self.assertIn("gl-075 adds no implementation", content)

    # ── 6. Review doc states GrantLayer is not production-ready yet ──
    def test_review_doc_states_not_production_ready(self):
        content = self.review_doc_text.lower()
        self.assertIn("grantlayer is not production-ready yet", content)

    # ── 7. Review doc references periodic Claude Code review, not mandatory for every issue
    def test_review_doc_references_periodic_claude_review(self):
        content = self.review_doc_text.lower()
        # Should reference periodic / not mandatory review
        periodic_found = (
            "periodic" in content
            or "not for every issue" in content
            or "not a required step for every issue" in content
        )
        self.assertTrue(
            periodic_found,
            "Review doc must reference periodic Claude Code review, not mandatory review for every issue",
        )

    # ── 8. JSON includes all required finding categories ──────────────
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

    # ── 9. JSON includes at least 5 recommended next issues ───────────
    def test_json_includes_at_least_five_recommended_next_issues(self):
        items = self.findings_json.get("recommended_next_issues", [])
        self.assertGreaterEqual(
            len(items),
            5,
            "Findings JSON must include at least 5 recommended_next_issues",
        )

    # ── 10. JSON includes stop gates ──────────────────────────────────
    def test_json_includes_stop_gates(self):
        stop_gates = self.findings_json.get("stop_gates", [])
        self.assertGreaterEqual(
            len(stop_gates),
            1,
            "Findings JSON must include at least 1 stop gate",
        )

    # ── 11. JSON includes a review disposition ────────────────────────
    def test_json_includes_review_disposition(self):
        disposition = self.findings_json.get("review_disposition", "")
        self.assertIn(
            disposition,
            {"proceed", "proceed_with_cautions", "blocked"},
            "Findings JSON must include a valid review_disposition",
        )

    # ── 12. No forbidden implementation files are changed ─────────────
    def test_no_forbidden_implementation_files_created(self):
        for path in self.FORBIDDEN_SRC_PATHS:
            if path.exists() and path.is_dir():
                continue
            self.assertFalse(
                path.exists(),
                f"Forbidden implementation file must not exist: {path}",
            )

    # ── 13. No future implementation test files exist yet ────────────
    def test_no_future_implementation_test_files_created(self):
        for path in self.FORBIDDEN_TEST_PATTERNS:
            self.assertFalse(
                path.exists(),
                f"Future implementation test file must not exist yet: {path}",
            )

    # ── 14. Review doc includes all 18 required sections ─────────────
    def test_review_doc_includes_required_sections(self):
        content = self.review_doc_text.lower()
        required_sections = [
            "1. purpose and non-goals",
            "2. review scope",
            "3. reviewed documents",
            "4. architecture consistency findings",
            "5. api-first / product-kernel boundary findings",
            "6. runtime configuration readiness findings",
            "7. auth / operator-access readiness findings",
            "8. secret-management readiness findings",
            "9. persistence / postgresql readiness findings",
            "10. observability / logging readiness findings",
            "11. backup / restore / data-lifecycle readiness findings",
            "12. operational runbook / incident-response readiness findings",
            "13. implementation sequencing risks",
            "14. recommended gl-076+ ordering",
            "15. required stop gates before sensitive implementation blocks",
            "16. test strategy recommendations",
            "17. production-readiness disclaimer",
            "18. final review disposition",
        ]
        for section in required_sections:
            with self.subTest(section=section):
                self.assertIn(
                    section,
                    content,
                    f"Review doc must include section '{section}'",
                )

    # ── 15. JSON findings each include status, summary, risk_level, recommendation, related_docs
    def test_json_findings_include_required_fields(self):
        findings = self.findings_json.get("findings", [])
        for finding in findings:
            with self.subTest(category=finding.get("category")):
                self.assertIn("status", finding, "Finding must include 'status'")
                self.assertIn("summary", finding, "Finding must include 'summary'")
                self.assertIn("risk_level", finding, "Finding must include 'risk_level'")
                self.assertIn("recommendation", finding, "Finding must include 'recommendation'")
                self.assertIn("related_docs", finding, "Finding must include 'related_docs'")
                self.assertIsInstance(finding["related_docs"], list)
                self.assertGreaterEqual(len(finding["related_docs"]), 1, "Finding must have at least 1 related_doc")

    # ── 16. Review doc references the specific required next issues ────
    def test_review_doc_references_required_next_issues(self):
        content = self.review_doc_text.lower()
        required_issues = [
            "gl-076",
            "gl-077",
            "gl-078",
            "gl-079",
            "gl-080",
        ]
        for issue in required_issues:
            with self.subTest(issue=issue):
                self.assertIn(
                    issue,
                    content,
                    f"Review doc must reference next issue '{issue}'",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
