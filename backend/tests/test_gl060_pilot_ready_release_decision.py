"""Tests for GL-060 Pilot-Ready Release Decision Check.

Lightweight validation test proving the pilot-ready release decision is:
- present as a human-readable document and a machine-readable JSON file
- coherent with all referenced Pilot-Ready artifacts
- explicitly not claiming production readiness
- free of obvious secrets
"""

import json
import pathlib
import unittest


class TestGL060PilotReadyReleaseDecision(unittest.TestCase):
    """GL-060: Validate the pilot-ready release decision."""

    REPO_ROOT = pathlib.Path(__file__).with_suffix("").parent.parent.parent
    DOCS_DIR = REPO_ROOT / "docs"
    EXAMPLE_DIR_GL060 = DOCS_DIR / "examples" / "gl060"
    BACKEND_TESTS_DIR = REPO_ROOT / "backend" / "tests"

    REQUIRED_DOCS = [
        "integration_guide.md",
        "demo_scenario.md",
        "integration_ready_checklist.md",
        "integration_ready_release_candidate.md",
        "integrator_quickstart.md",
        "minimal_api_usage_walkthrough.md",
        "pilot_ready_handoff_plan.md",
        "pilot_ready_checklist.md",
    ]

    REQUIRED_TESTS = [
        "test_gl052_product_core_e2e_flow.py",
        "test_gl054_demo_scenario_fixture.py",
        "test_gl055_integration_contract_readiness.py",
        "test_gl057_integrator_quickstart_examples.py",
        "test_gl058_minimal_api_usage_walkthrough.py",
        "test_gl059_pilot_ready_handoff.py",
    ]

    REQUIRED_EXAMPLE_DIRS = [
        ("gl057", True),
        ("gl058", False),
        ("gl059", False),
    ]

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
        cls.decision_doc_path = cls.DOCS_DIR / "pilot_ready_release_decision.md"
        cls.decision_json_path = cls.EXAMPLE_DIR_GL060 / "pilot_ready_decision_record.json"
        cls.decision_json = None
        cls.decision_json_text = None
        if cls.decision_json_path.exists():
            cls.decision_json_text = cls.decision_json_path.read_text(encoding="utf-8")
            cls.decision_json = json.loads(cls.decision_json_text)

    # ── 1. Decision doc exists ───────────────────────────────────────
    def test_decision_doc_exists(self):
        self.assertTrue(
            self.decision_doc_path.exists(),
            "docs/pilot_ready_release_decision.md must exist",
        )

    # ── 2. Decision JSON exists and parses ───────────────────────────
    def test_decision_json_exists_and_parses(self):
        self.assertTrue(
            self.decision_json_path.exists(),
            "docs/examples/gl060/pilot_ready_decision_record.json must exist",
        )
        self.assertIsNotNone(self.decision_json, "Decision JSON must parse as valid JSON")
        self.assertIsInstance(self.decision_json, dict)

    # ── 3. Referenced required docs exist ────────────────────────────
    def test_referenced_required_docs_exist(self):
        missing = []
        for name in self.REQUIRED_DOCS:
            path = self.DOCS_DIR / name
            if not path.exists():
                missing.append(name)
        self.assertEqual(missing, [], f"Missing required docs: {missing}")

    # ── 4. Referenced required example directories/files exist ────────
    def test_referenced_required_examples_exist(self):
        missing = []
        for subdir, is_dir in self.REQUIRED_EXAMPLE_DIRS:
            path = self.DOCS_DIR / "examples" / subdir
            if not path.exists():
                missing.append(f"docs/examples/{subdir}/")
                continue
            if is_dir and not path.is_dir():
                missing.append(f"docs/examples/{subdir}/ must be a directory")
        self.assertEqual(missing, [], f"Missing required examples: {missing}")

    # ── 5. Referenced GL-058 JSON exists ─────────────────────────────
    def test_gl058_walkthrough_json_exists(self):
        gl058_json = self.DOCS_DIR / "examples" / "gl058" / "minimal_api_usage_walkthrough.json"
        self.assertTrue(
            gl058_json.exists(),
            "docs/examples/gl058/minimal_api_usage_walkthrough.json must exist",
        )

    # ── 6. Referenced GL-059 JSON exists ─────────────────────────────
    def test_gl059_handoff_package_exists(self):
        gl059_json = self.DOCS_DIR / "examples" / "gl059" / "pilot_handoff_package.json"
        self.assertTrue(
            gl059_json.exists(),
            "docs/examples/gl059/pilot_handoff_package.json must exist",
        )

    # ── 7. Referenced required tests exist ───────────────────────────
    def test_referenced_required_tests_exist(self):
        missing = []
        for name in self.REQUIRED_TESTS:
            path = self.BACKEND_TESTS_DIR / name
            if not path.exists():
                missing.append(name)
        self.assertEqual(missing, [], f"Missing required tests: {missing}")

    # ── 8. Decision JSON says pilotPlanningReady is true ─────────────
    def test_decision_json_says_pilot_planning_ready(self):
        self.assertTrue(
            self.decision_json.get("pilotPlanningReady"),
            "pilotPlanningReady must be true",
        )

    # ── 9. Decision JSON says productionReady is false ───────────────
    def test_decision_json_says_not_production_ready(self):
        self.assertFalse(
            self.decision_json.get("productionReady"),
            "productionReady must be false",
        )

    # ── 10. Decision JSON includes GL-052 through GL-059 in integrationReadyBase ──
    def test_decision_json_includes_gl052_through_gl059(self):
        base = self.decision_json.get("integrationReadyBase", "")
        self.assertIn("GL-052", base, "integrationReadyBase must include GL-052")
        self.assertIn("GL-059", base, "integrationReadyBase must include GL-059")

    # ── 11. Decision JSON includes non-goals ─────────────────────────
    def test_decision_json_includes_non_goals(self):
        non_goals = self.decision_json.get("nonGoals", [])
        self.assertTrue(len(non_goals) > 0, "nonGoals must not be empty")
        non_goals_lower = " ".join(non_goals).lower()
        self.assertIn("oauth", non_goals_lower, "nonGoals must mention OAuth")
        self.assertIn("jwt", non_goals_lower, "nonGoals must mention JWT")
        self.assertIn("blockchain", non_goals_lower, "nonGoals must mention blockchain")
        self.assertIn("sdk", non_goals_lower, "nonGoals must mention SDK")

    # ── 12. Decision JSON includes recommended next options ──────────
    def test_decision_json_includes_recommended_next_options(self):
        options = self.decision_json.get("recommendedNextOptions", [])
        self.assertTrue(len(options) > 0, "recommendedNextOptions must not be empty")

    # ── 13. Decision JSON includes default next block ────────────────
    def test_decision_json_includes_default_next_block(self):
        default = self.decision_json.get("defaultNextBlock", "")
        self.assertTrue(len(default) > 0, "defaultNextBlock must not be empty")

    # ── 14. Decision document states ready for production deployment is no ──
    def test_decision_doc_says_not_ready_for_production_deployment(self):
        content = self.decision_doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("ready for production deployment", content)
        lines = content.splitlines()
        found_production_line = False
        for line in lines:
            if "ready for production deployment" in line:
                found_production_line = True
                self.assertIn("no", line, "Doc must state production deployment is no")
        self.assertTrue(
            found_production_line,
            "Doc must contain a production deployment decision row",
        )

    # ── 15. Decision document recommends a next default workstream ───
    def test_decision_doc_recommends_next_default_workstream(self):
        content = self.decision_doc_path.read_text(encoding="utf-8")
        self.assertIn("default recommended next block", content.lower())

    # ── 16. No obvious secrets appear in the decision JSON ───────────
    def test_no_obvious_secrets_in_decision_json(self):
        text_lower = self.decision_json_text.lower()
        for pattern in self.SECRET_PATTERNS:
            self.assertNotIn(
                pattern,
                text_lower,
                f"Decision JSON may contain secret-like pattern: {pattern}",
            )

    # ── Extra coherence checks ───────────────────────────────────────
    def test_decision_json_has_id_and_version(self):
        self.assertEqual(self.decision_json.get("decisionId"), "gl060-pilot-ready-release-decision")
        self.assertEqual(self.decision_json.get("decisionVersion"), "1.0")

    def test_decision_json_has_status(self):
        self.assertEqual(
            self.decision_json.get("status"),
            "pilot-ready-for-technical-review",
        )

    def test_decision_json_supporting_docs_match_required_docs(self):
        """All required docs must be listed in supportingDocs."""
        docs = self.decision_json.get("supportingDocs", [])
        doc_paths = {d.get("path") for d in docs}
        for expected in self.REQUIRED_DOCS:
            with self.subTest(doc=expected):
                self.assertIn(
                    f"docs/{expected}",
                    doc_paths,
                    f"Decision JSON must reference docs/{expected}",
                )

    def test_decision_json_supporting_tests_match_required_tests(self):
        """All required tests except GL-060 must be listed in supportingTests."""
        tests = self.decision_json.get("supportingTests", [])
        test_paths = {t.get("path") for t in tests}
        for expected in self.REQUIRED_TESTS:
            with self.subTest(test=expected):
                self.assertIn(
                    f"backend/tests/{expected}",
                    test_paths,
                    f"Decision JSON must reference backend/tests/{expected}",
                )
        # GL-060 must also be present
        self.assertIn(
            "backend/tests/test_gl060_pilot_ready_release_decision.py",
            test_paths,
        )

    def test_decision_json_has_stop_conditions(self):
        conditions = self.decision_json.get("stopConditions", [])
        self.assertTrue(len(conditions) > 0, "stopConditions must not be empty")
        conditions_text = " ".join(conditions).lower()
        self.assertIn("backend", conditions_text, "stopConditions must mention backend")
        self.assertIn("openapi", conditions_text, "stopConditions must mention OpenAPI")

    def test_decision_doc_references_all_required_docs(self):
        content = self.decision_doc_path.read_text(encoding="utf-8")
        for expected in self.REQUIRED_DOCS:
            with self.subTest(doc=expected):
                self.assertIn(expected, content, f"Decision doc must reference {expected}")

    def test_decision_doc_references_all_required_tests(self):
        content = self.decision_doc_path.read_text(encoding="utf-8")
        for expected in self.REQUIRED_TESTS:
            with self.subTest(test=expected):
                self.assertIn(expected, content, f"Decision doc must reference {expected}")
        self.assertIn("test_gl060_pilot_ready_release_decision.py", content)

    def test_decision_doc_references_gl060_json(self):
        content = self.decision_doc_path.read_text(encoding="utf-8")
        self.assertIn("docs/examples/gl060/pilot_ready_decision_record.json", content)

    def test_decision_doc_references_pilot_handoff_plan(self):
        content = self.decision_doc_path.read_text(encoding="utf-8")
        self.assertIn("pilot_ready_handoff_plan.md", content)

    def test_decision_doc_references_pilot_ready_checklist(self):
        content = self.decision_doc_path.read_text(encoding="utf-8")
        self.assertIn("pilot_ready_checklist.md", content)

    def test_decision_doc_references_integration_ready_rc(self):
        content = self.decision_doc_path.read_text(encoding="utf-8")
        self.assertIn("integration_ready_release_candidate.md", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
