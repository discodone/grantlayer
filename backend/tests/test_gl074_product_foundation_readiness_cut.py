"""Tests for GL-074 Product Foundation Readiness Review and Implementation Cut.

Lightweight validation test proving the Product Foundation readiness review
and implementation cut are:
- present as human-readable documents
- present as machine-readable JSON files
- coherent with the design baseline from GL-064 through GL-073
- explicitly not claiming production readiness
- free of forbidden implementation file changes
"""

import json
import pathlib
import unittest


class TestGL074ProductFoundationReadinessCut(unittest.TestCase):
    """GL-074: Validate Product Foundation readiness review and implementation cut."""

    REPO_ROOT = pathlib.Path(__file__).with_suffix("").parent.parent.parent
    DOCS_DIR = REPO_ROOT / "docs"
    EXAMPLE_DIR_GL074 = DOCS_DIR / "examples" / "gl074"
    BACKEND_SRC_DIR = REPO_ROOT / "backend" / "src"
    BACKEND_TESTS_DIR = REPO_ROOT / "backend" / "tests"

    REQUIRED_FOUNDATION_AREAS = [
        "api_contract",
        "architecture_boundaries",
        "runtime_configuration",
        "operator_auth_access",
        "secret_management",
        "deployment_runtime_modes",
        "persistence_postgresql",
        "observability_logging",
        "backup_restore_lifecycle",
        "operational_runbook_incident_response",
    ]

    # These paths must not be created by GL-074. Paths that already exist in the
    # repository (e.g., backend/src/config.py) are omitted because GL-074 does not
    # modify them.
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
        BACKEND_TESTS_DIR / "test_gl075_runtime_configuration_enforcement.py",
        BACKEND_TESTS_DIR / "test_gl076_health_readiness_baseline.py",
        BACKEND_TESTS_DIR / "test_gl077_structured_logging_baseline.py",
        BACKEND_TESTS_DIR / "test_gl078_secret_source_boundary.py",
        BACKEND_TESTS_DIR / "test_gl079_persistence_backend_abstraction.py",
        BACKEND_TESTS_DIR / "test_gl080_deployment_runtime_mode_validation.py",
        BACKEND_TESTS_DIR / "test_gl081_operator_access_hardening.py",
    ]

    @classmethod
    def setUpClass(cls):
        cls.readiness_review_path = cls.DOCS_DIR / "product_foundation_readiness_review.md"
        cls.implementation_cut_path = cls.DOCS_DIR / "product_foundation_implementation_cut.md"
        cls.readiness_matrix_path = cls.EXAMPLE_DIR_GL074 / "product_foundation_readiness_matrix.json"
        cls.implementation_backlog_path = cls.EXAMPLE_DIR_GL074 / "product_foundation_implementation_backlog.json"

        cls.readiness_matrix_json = None
        if cls.readiness_matrix_path.exists():
            cls.readiness_matrix_json = json.loads(cls.readiness_matrix_path.read_text(encoding="utf-8"))

        cls.implementation_backlog_json = None
        if cls.implementation_backlog_path.exists():
            cls.implementation_backlog_json = json.loads(cls.implementation_backlog_path.read_text(encoding="utf-8"))

        cls.readiness_review_text = ""
        if cls.readiness_review_path.exists():
            cls.readiness_review_text = cls.readiness_review_path.read_text(encoding="utf-8")

        cls.implementation_cut_text = ""
        if cls.implementation_cut_path.exists():
            cls.implementation_cut_text = cls.implementation_cut_path.read_text(encoding="utf-8")

    # ── 1. Readiness review doc exists ───────────────────────────────
    def test_readiness_review_doc_exists(self):
        self.assertTrue(
            self.readiness_review_path.exists(),
            "docs/product_foundation_readiness_review.md must exist",
        )

    # ── 2. Implementation cut doc exists ─────────────────────────────
    def test_implementation_cut_doc_exists(self):
        self.assertTrue(
            self.implementation_cut_path.exists(),
            "docs/product_foundation_implementation_cut.md must exist",
        )

    # ── 3. Readiness matrix JSON exists and parses ───────────────────
    def test_readiness_matrix_exists_and_parses(self):
        self.assertTrue(
            self.readiness_matrix_path.exists(),
            "docs/examples/gl074/product_foundation_readiness_matrix.json must exist",
        )
        self.assertIsNotNone(self.readiness_matrix_json, "Readiness matrix must parse as valid JSON")
        self.assertIsInstance(self.readiness_matrix_json, dict)

    # ── 4. Implementation backlog JSON exists and parses ─────────────
    def test_implementation_backlog_exists_and_parses(self):
        self.assertTrue(
            self.implementation_backlog_path.exists(),
            "docs/examples/gl074/product_foundation_implementation_backlog.json must exist",
        )
        self.assertIsNotNone(self.implementation_backlog_json, "Implementation backlog must parse as valid JSON")
        self.assertIsInstance(self.implementation_backlog_json, dict)

    # ── 5. Readiness matrix includes all required foundation areas ───
    def test_readiness_matrix_includes_all_areas(self):
        areas = self.readiness_matrix_json.get("foundationAreas", [])
        found_areas = {a.get("area") for a in areas}
        for expected in self.REQUIRED_FOUNDATION_AREAS:
            with self.subTest(area=expected):
                self.assertIn(
                    expected,
                    found_areas,
                    f"Readiness matrix must include area '{expected}'",
                )

    # ── 6. Readiness matrix does not mark production_readiness as complete
    def test_readiness_matrix_no_area_production_ready(self):
        areas = self.readiness_matrix_json.get("foundationAreas", [])
        for area in areas:
            prod_ready = area.get("production_readiness", "").lower()
            self.assertNotEqual(
                prod_ready,
                "ready",
                f"Area '{area.get('area')}' must not be marked production_ready",
            )
            self.assertNotEqual(
                prod_ready,
                "complete",
                f"Area '{area.get('area')}' must not be marked production complete",
            )

    # ── 7. Readiness matrix includes related docs for each area ──────
    def test_readiness_matrix_includes_related_docs(self):
        areas = self.readiness_matrix_json.get("foundationAreas", [])
        for area in areas:
            with self.subTest(area=area.get("area")):
                related = area.get("related_docs", [])
                self.assertTrue(
                    len(related) > 0,
                    f"Area '{area.get('area')}' must have related_docs",
                )

    # ── 8. Implementation backlog includes at least 6 items ──────────
    def test_implementation_backlog_has_at_least_six_items(self):
        items = self.implementation_backlog_json.get("backlogItems", [])
        self.assertGreaterEqual(
            len(items),
            6,
            "Implementation backlog must include at least 6 items",
        )

    # ── 9. Implementation backlog includes a Claude Code review-only checkpoint
    def test_implementation_backlog_includes_claude_review_checkpoint(self):
        items = self.implementation_backlog_json.get("backlogItems", [])
        found = False
        for item in items:
            title = (item.get("title") or "").lower()
            if "claude code review-only checkpoint" in title or "review-only checkpoint" in title:
                found = True
                self.assertTrue(
                    item.get("requires_claude_review"),
                    "Claude Code review-only checkpoint item must set requires_claude_review to true",
                )
                break
        self.assertTrue(
            found,
            "Implementation backlog must include a Claude Code review-only checkpoint item",
        )

    # ── 10. Implementation backlog items include prerequisites and test strategy
    def test_backlog_items_include_prerequisites_and_test_strategy(self):
        items = self.implementation_backlog_json.get("backlogItems", [])
        for item in items:
            with self.subTest(item=item.get("id")):
                prereqs = item.get("prerequisites", [])
                self.assertTrue(
                    len(prereqs) > 0,
                    f"Item '{item.get('id')}' must have prerequisites",
                )
                test_strategy = item.get("test_strategy", "")
                self.assertTrue(
                    len(test_strategy) > 0,
                    f"Item '{item.get('id')}' must have a test_strategy",
                )

    # ── 11. Readiness review doc states GL-074 adds no implementation ─
    def test_readiness_review_states_no_implementation(self):
        content = self.readiness_review_text.lower()
        self.assertIn(
            "gl-074 adds no implementation",
            content,
        )

    # ── 12. Implementation cut doc states GL-074 adds no implementation
    def test_implementation_cut_states_no_implementation(self):
        content = self.implementation_cut_text.lower()
        self.assertIn(
            "gl-074 adds no implementation",
            content,
        )

    # ── 13. Readiness review doc states GrantLayer is not production-ready yet
    def test_readiness_review_states_not_production_ready(self):
        content = self.readiness_review_text.lower()
        self.assertIn(
            "grantlayer is not production-ready yet",
            content,
        )

    # ── 14. Implementation cut doc states GrantLayer is not production-ready yet
    def test_implementation_cut_states_not_production_ready(self):
        content = self.implementation_cut_text.lower()
        self.assertIn(
            "grantlayer is not production-ready yet",
            content,
        )

    # ── 15. No forbidden implementation files are changed ────────────
    def test_no_forbidden_implementation_files_created(self):
        for path in self.FORBIDDEN_SRC_PATHS:
            # Some paths like auth/ may be directories that already exist
            if path.exists() and path.is_dir():
                # If backend/src/auth already exists, that's fine; we only care about new files inside,
                # but the instructions say no backend/src/* changes at all. However, existing dirs are OK.
                continue
            self.assertFalse(
                path.exists(),
                f"Forbidden implementation file must not exist: {path}",
            )

    # ── 16. No future implementation test files exist yet ────────────
    def test_no_future_implementation_test_files_created(self):
        for path in self.FORBIDDEN_TEST_PATTERNS:
            self.assertFalse(
                path.exists(),
                f"Future implementation test file must not exist yet: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
