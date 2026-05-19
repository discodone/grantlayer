"""Tests for GL-059 Pilot-Ready Handoff Plan.

Lightweight validation test proving the pilot handoff package is:
- present as documents and a machine-readable JSON file
- coherent and aligned with Integration-Ready artifacts
- explicitly not claiming production readiness
- free of obvious secrets
"""

import json
import pathlib
import unittest


class TestGL059PilotReadyHandoff(unittest.TestCase):
    """GL-059: Validate the pilot-ready handoff plan."""

    REPO_ROOT = pathlib.Path(__file__).with_suffix("").parent.parent.parent
    DOCS_DIR = REPO_ROOT / "docs"
    EXAMPLE_DIR_GL058 = DOCS_DIR / "examples" / "gl058"
    EXAMPLE_DIR_GL059 = DOCS_DIR / "examples" / "gl059"
    BACKEND_TESTS_DIR = REPO_ROOT / "backend" / "tests"

    REQUIRED_INTEGRATION_DOCS = [
        "integration_guide.md",
        "demo_scenario.md",
        "integration_ready_checklist.md",
        "integration_ready_release_candidate.md",
        "integrator_quickstart.md",
        "minimal_api_usage_walkthrough.md",
    ]

    REQUIRED_TESTS = [
        "test_gl052_product_core_e2e_flow.py",
        "test_gl054_demo_scenario_fixture.py",
        "test_gl055_integration_contract_readiness.py",
        "test_gl057_integrator_quickstart_examples.py",
        "test_gl058_minimal_api_usage_walkthrough.py",
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
        cls.handoff_plan_path = cls.DOCS_DIR / "pilot_ready_handoff_plan.md"
        cls.handoff_checklist_path = cls.DOCS_DIR / "pilot_ready_checklist.md"
        cls.handoff_json_path = cls.EXAMPLE_DIR_GL059 / "pilot_handoff_package.json"
        cls.handoff_json = None
        cls.handoff_json_text = None
        if cls.handoff_json_path.exists():
            cls.handoff_json_text = cls.handoff_json_path.read_text(encoding="utf-8")
            cls.handoff_json = json.loads(cls.handoff_json_text)

    # ── 1. Pilot handoff plan doc exists ─────────────────────────────
    def test_handoff_plan_doc_exists(self):
        self.assertTrue(
            self.handoff_plan_path.exists(),
            "docs/pilot_ready_handoff_plan.md must exist",
        )

    # ── 2. Pilot-ready checklist doc exists ──────────────────────────
    def test_handoff_checklist_doc_exists(self):
        self.assertTrue(
            self.handoff_checklist_path.exists(),
            "docs/pilot_ready_checklist.md must exist",
        )

    # ── 3. Pilot handoff JSON exists and parses ──────────────────────
    def test_handoff_json_exists_and_parses(self):
        self.assertTrue(
            self.handoff_json_path.exists(),
            "docs/examples/gl059/pilot_handoff_package.json must exist",
        )
        self.assertIsNotNone(self.handoff_json, "Handoff JSON must parse as valid JSON")
        self.assertIsInstance(self.handoff_json, dict)

    # ── 4. Required Integration-Ready docs exist ───────────────────────
    def test_required_integration_docs_exist(self):
        missing = []
        for name in self.REQUIRED_INTEGRATION_DOCS:
            path = self.DOCS_DIR / name
            if not path.exists():
                missing.append(name)
        self.assertEqual(missing, [], f"Missing required integration docs: {missing}")

    # ── 5. GL-057 example directory exists ───────────────────────────
    def test_gl057_example_directory_exists(self):
        gl057_dir = self.DOCS_DIR / "examples" / "gl057"
        self.assertTrue(
            gl057_dir.exists(),
            "docs/examples/gl057/ must exist",
        )

    # ── 6. GL-058 walkthrough JSON exists ────────────────────────────
    def test_gl058_walkthrough_json_exists(self):
        walkthrough_json = self.EXAMPLE_DIR_GL058 / "minimal_api_usage_walkthrough.json"
        self.assertTrue(
            walkthrough_json.exists(),
            "docs/examples/gl058/minimal_api_usage_walkthrough.json must exist",
        )

    # ── 7. Required validation tests exist ─────────────────────────────
    def test_required_validation_tests_exist(self):
        missing = []
        for name in self.REQUIRED_TESTS:
            path = self.BACKEND_TESTS_DIR / name
            if not path.exists():
                missing.append(name)
        self.assertEqual(missing, [], f"Missing required validation tests: {missing}")

    # ── 8. Pilot JSON references required docs and tests ─────────────
    def test_handoff_json_references_required_docs(self):
        required_docs = self.handoff_json.get("requiredDocs", [])
        doc_paths = {d.get("path") for d in required_docs}
        for expected in self.REQUIRED_INTEGRATION_DOCS:
            with self.subTest(doc=expected):
                self.assertIn(
                    f"docs/{expected}",
                    doc_paths,
                    f"Pilot JSON must reference docs/{expected}",
                )

    def test_handoff_json_references_required_tests(self):
        required_tests = self.handoff_json.get("requiredTests", [])
        test_paths = {t.get("path") for t in required_tests}
        for expected in self.REQUIRED_TESTS:
            with self.subTest(test=expected):
                self.assertIn(
                    f"backend/tests/{expected}",
                    test_paths,
                    f"Pilot JSON must reference backend/tests/{expected}",
                )

    # ── 9. Pilot JSON includes non-goals ─────────────────────────────
    def test_handoff_json_includes_non_goals(self):
        non_goals = self.handoff_json.get("nonGoals", [])
        self.assertTrue(len(non_goals) > 0, "nonGoals must not be empty")
        non_goals_lower = " ".join(non_goals).lower()
        self.assertIn("oauth", non_goals_lower, "nonGoals must mention OAuth")
        self.assertIn("jwt", non_goals_lower, "nonGoals must mention JWT")
        self.assertIn("blockchain", non_goals_lower, "nonGoals must mention blockchain")
        self.assertIn("sdk", non_goals_lower, "nonGoals must mention SDK")

    # ── 10. Handoff plan explicitly says production-ready is no ────────
    def test_handoff_plan_says_not_production_ready(self):
        content = self.handoff_plan_path.read_text(encoding="utf-8").lower()
        # The markdown table contains | Production-ready | **No** |
        # After stripping spaces, pipes, and asterisks we should find production-readyno
        stripped = content.replace(" ", "").replace("|", "").replace("*", "")
        self.assertIn("production-readyno", stripped)
        # Also verify the phrase appears in the document
        self.assertIn("production-ready", content)

    # ── 11. Checklist explicitly says ready for production deployment is no ─
    def test_checklist_says_not_ready_for_production_deployment(self):
        content = self.handoff_checklist_path.read_text(encoding="utf-8").lower()
        self.assertIn("ready for production deployment", content)
        # The checklist table should contain "No" in the production deployment row
        lines = content.splitlines()
        found_production_line = False
        for line in lines:
            if "ready for production deployment" in line.lower():
                found_production_line = True
                self.assertIn("no", line.lower(), "Checklist must state production deployment is no")
        self.assertTrue(found_production_line, "Checklist must contain a production deployment decision row")

    # ── 12. No obvious secrets appear in the pilot JSON ──────────────
    def test_no_obvious_secrets_in_pilot_json(self):
        text_lower = self.handoff_json_text.lower()
        for pattern in self.SECRET_PATTERNS:
            self.assertNotIn(
                pattern,
                text_lower,
                f"Pilot JSON may contain secret-like pattern: {pattern}",
            )

    # ── Extra coherence checks ───────────────────────────────────────
    def test_handoff_json_has_package_id_and_version(self):
        self.assertEqual(self.handoff_json.get("packageId"), "gl059-pilot-handoff")
        self.assertEqual(self.handoff_json.get("packageVersion"), "1.0")

    def test_handoff_json_has_status(self):
        self.assertEqual(self.handoff_json.get("status"), "pilot-ready-planning")

    def test_handoff_json_has_integration_ready_base(self):
        self.assertEqual(
            self.handoff_json.get("integrationReadyBase"),
            "GL-052 through GL-058",
        )

    def test_handoff_json_has_verification_commands(self):
        commands = self.handoff_json.get("verificationCommands", [])
        self.assertTrue(len(commands) > 0, "verificationCommands must not be empty")
        self.assertIn(
            "python3 -m unittest backend.tests.test_gl059_pilot_ready_handoff -v",
            commands,
        )

    def test_handoff_json_has_pilot_success_criteria(self):
        criteria = self.handoff_json.get("pilotSuccessCriteria", [])
        self.assertTrue(len(criteria) > 0, "pilotSuccessCriteria must not be empty")
        criteria_text = " ".join(criteria).lower()
        self.assertIn("core flow", criteria_text, "success criteria must mention core flow")
        self.assertIn("blockers", criteria_text, "success criteria must mention blockers")

    def test_handoff_json_has_recommended_next_decisions(self):
        decisions = self.handoff_json.get("recommendedNextDecisions", [])
        self.assertTrue(len(decisions) > 0, "recommendedNextDecisions must not be empty")

    def test_handoff_json_has_boolean_flags(self):
        self.assertFalse(self.handoff_json.get("productionReady"), "productionReady must be false")
        self.assertTrue(self.handoff_json.get("pilotDiscussionReady"), "pilotDiscussionReady must be true")

    def test_handoff_plan_references_gl058_walkthrough(self):
        content = self.handoff_plan_path.read_text(encoding="utf-8")
        self.assertIn("minimal_api_usage_walkthrough.md", content)
        self.assertIn("gl058", content.lower())

    def test_handoff_plan_references_gl057_examples(self):
        content = self.handoff_plan_path.read_text(encoding="utf-8")
        self.assertIn("docs/examples/gl057/", content)

    def test_handoff_plan_references_integration_artifacts(self):
        content = self.handoff_plan_path.read_text(encoding="utf-8")
        self.assertIn("integration_guide.md", content)
        self.assertIn("demo_scenario.md", content)
        self.assertIn("integration_ready_checklist.md", content)
        self.assertIn("integration_ready_release_candidate.md", content)
        self.assertIn("integrator_quickstart.md", content)
        self.assertIn("openapi.yaml", content)

    def test_handoff_plan_references_validation_tests(self):
        content = self.handoff_plan_path.read_text(encoding="utf-8")
        self.assertIn("test_gl052_product_core_e2e_flow.py", content)
        self.assertIn("test_gl055_integration_contract_readiness.py", content)
        self.assertIn("test_gl058_minimal_api_usage_walkthrough.py", content)
        self.assertIn("test_gl059_pilot_ready_handoff.py", content)

    def test_handoff_plan_references_pilot_handoff_json(self):
        content = self.handoff_plan_path.read_text(encoding="utf-8")
        self.assertIn("docs/examples/gl059/pilot_handoff_package.json", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
