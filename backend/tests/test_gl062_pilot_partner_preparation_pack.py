"""Tests for GL-062 Pilot Partner Preparation Pack.

Lightweight validation test proving the pilot partner preparation pack is:
- present as a human-readable document and two machine-readable JSON files
- coherent with all referenced Pilot-Ready artifacts
- explicitly not claiming production readiness
- referencing the GL-061 demo runner dry-run
- free of obvious secrets
"""

import json
import pathlib
import unittest


class TestGL062PilotPartnerPreparationPack(unittest.TestCase):
    """GL-062: Validate the pilot partner preparation pack."""

    REPO_ROOT = pathlib.Path(__file__).with_suffix("").parent.parent.parent
    DOCS_DIR = REPO_ROOT / "docs"
    EXAMPLE_DIR_GL062 = DOCS_DIR / "examples" / "gl062"
    BACKEND_TESTS_DIR = REPO_ROOT / "backend" / "tests"

    REQUIRED_DOCS = [
        "integration_guide.md",
        "integrator_quickstart.md",
        "minimal_api_usage_walkthrough.md",
        "demo_scenario.md",
        "pilot_ready_handoff_plan.md",
        "pilot_ready_release_decision.md",
        "demo_runner_api_smoke.md",
        "pilot_partner_preparation_pack.md",
    ]

    REQUIRED_TESTS = [
        "test_gl052_product_core_e2e_flow.py",
        "test_gl054_demo_scenario_fixture.py",
        "test_gl055_integration_contract_readiness.py",
        "test_gl057_integrator_quickstart_examples.py",
        "test_gl058_minimal_api_usage_walkthrough.py",
        "test_gl059_pilot_ready_handoff.py",
        "test_gl060_pilot_ready_release_decision.py",
        "test_gl061_demo_runner_api_smoke.py",
        "test_gl062_pilot_partner_preparation_pack.py",
    ]

    REQUIRED_QUESTION_GROUPS = [
        "partnerProfileQuestions",
        "workflowFitQuestions",
        "evidenceQuestions",
        "auditComplianceQuestions",
        "integrationQuestions",
        "dataPrivacyQuestions",
        "authSecurityQuestions",
        "productionHardeningQuestions",
        "pilotSuccessCriteriaQuestions",
        "blockerQuestions",
        "nonGoals",
    ]

    REQUIRED_AGENDA_ITEMS = [
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
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
        cls.pack_doc_path = cls.DOCS_DIR / "pilot_partner_preparation_pack.md"
        cls.questionnaire_path = cls.EXAMPLE_DIR_GL062 / "pilot_partner_questionnaire.json"
        cls.agenda_path = cls.EXAMPLE_DIR_GL062 / "pilot_review_agenda.json"

        cls.questionnaire_json = None
        cls.questionnaire_text = None
        if cls.questionnaire_path.exists():
            cls.questionnaire_text = cls.questionnaire_path.read_text(encoding="utf-8")
            cls.questionnaire_json = json.loads(cls.questionnaire_text)

        cls.agenda_json = None
        cls.agenda_text = None
        if cls.agenda_path.exists():
            cls.agenda_text = cls.agenda_path.read_text(encoding="utf-8")
            cls.agenda_json = json.loads(cls.agenda_text)

    # ── 1. Preparation pack doc exists ───────────────────────────────
    def test_preparation_pack_doc_exists(self):
        self.assertTrue(
            self.pack_doc_path.exists(),
            "docs/pilot_partner_preparation_pack.md must exist",
        )

    # ── 2. Questionnaire JSON exists and parses ──────────────────────
    def test_questionnaire_exists_and_parses(self):
        self.assertTrue(
            self.questionnaire_path.exists(),
            "docs/examples/gl062/pilot_partner_questionnaire.json must exist",
        )
        self.assertIsNotNone(self.questionnaire_json, "Questionnaire must parse as valid JSON")
        self.assertIsInstance(self.questionnaire_json, dict)

    # ── 3. Agenda JSON exists and parses ─────────────────────────────
    def test_agenda_exists_and_parses(self):
        self.assertTrue(
            self.agenda_path.exists(),
            "docs/examples/gl062/pilot_review_agenda.json must exist",
        )
        self.assertIsNotNone(self.agenda_json, "Agenda must parse as valid JSON")
        self.assertIsInstance(self.agenda_json, dict)

    # ── 4. Referenced required Pilot-Ready docs exist ────────────────
    def test_referenced_required_docs_exist(self):
        missing = []
        for name in self.REQUIRED_DOCS:
            path = self.DOCS_DIR / name
            if not path.exists():
                missing.append(name)
        self.assertEqual(missing, [], f"Missing required docs: {missing}")

    # ── 5. GL-057 examples directory exists ──────────────────────────
    def test_gl057_example_directory_exists(self):
        gl057_dir = self.DOCS_DIR / "examples" / "gl057"
        self.assertTrue(
            gl057_dir.exists(),
            "docs/examples/gl057/ must exist",
        )
        self.assertTrue(
            gl057_dir.is_dir(),
            "docs/examples/gl057/ must be a directory",
        )

    # ── 6. GL-058 walkthrough JSON exists ────────────────────────────
    def test_gl058_walkthrough_json_exists(self):
        gl058_json = self.DOCS_DIR / "examples" / "gl058" / "minimal_api_usage_walkthrough.json"
        self.assertTrue(
            gl058_json.exists(),
            "docs/examples/gl058/minimal_api_usage_walkthrough.json must exist",
        )

    # ── 7. GL-061 demo runner script exists ──────────────────────────
    def test_gl061_demo_runner_script_exists(self):
        script_path = self.REPO_ROOT / "scripts" / "demo" / "gl061_api_smoke.py"
        self.assertTrue(
            script_path.exists(),
            "scripts/demo/gl061_api_smoke.py must exist",
        )

    # ── 8. Required validation tests exist ───────────────────────────
    def test_required_validation_tests_exist(self):
        missing = []
        for name in self.REQUIRED_TESTS:
            path = self.BACKEND_TESTS_DIR / name
            if not path.exists():
                missing.append(name)
        self.assertEqual(missing, [], f"Missing required tests: {missing}")

    # ── 9. Questionnaire includes required question groups ───────────
    def test_questionnaire_includes_required_question_groups(self):
        for group in self.REQUIRED_QUESTION_GROUPS:
            with self.subTest(group=group):
                self.assertIn(
                    group,
                    self.questionnaire_json,
                    f"Questionnaire must include '{group}'",
                )
                value = self.questionnaire_json[group]
                self.assertTrue(
                    len(value) > 0 if hasattr(value, "__len__") else value is not None,
                    f"Questionnaire group '{group}' must not be empty",
                )

    # ── 10. Agenda includes required agenda items ────────────────────
    def test_agenda_includes_required_agenda_items(self):
        agenda_items = self.agenda_json.get("agendaItems", [])
        item_numbers = {item.get("itemNumber") for item in agenda_items}
        for num in self.REQUIRED_AGENDA_ITEMS:
            with self.subTest(itemNumber=num):
                self.assertIn(
                    num,
                    item_numbers,
                    f"Agenda must include agenda item {num}",
                )

    # ── 11. Preparation pack states Production-Ready: no ─────────────
    def test_preparation_pack_says_not_production_ready(self):
        content = self.pack_doc_path.read_text(encoding="utf-8").lower()
        # The markdown table contains | Production-Ready | **No** |
        stripped = content.replace(" ", "").replace("|", "").replace("*", "")
        self.assertIn("production-readyno", stripped)
        # Also verify the phrase appears
        self.assertIn("production-ready", content)

    # ── 12. Preparation pack references demo runner dry-run ──────────
    def test_preparation_pack_references_demo_runner_dry_run(self):
        content = self.pack_doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("dry-run", content, "Pack must mention dry-run")
        self.assertIn("gl061_api_smoke.py", content, "Pack must reference gl061_api_smoke.py")

    # ── 13. JSON files include non-goals ─────────────────────────────
    def test_questionnaire_includes_non_goals(self):
        non_goals = self.questionnaire_json.get("nonGoals", [])
        self.assertTrue(len(non_goals) > 0, "Questionnaire nonGoals must not be empty")
        non_goals_lower = " ".join(non_goals).lower()
        self.assertIn("oauth", non_goals_lower, "nonGoals must mention OAuth")
        self.assertIn("jwt", non_goals_lower, "nonGoals must mention JWT")
        self.assertIn("blockchain", non_goals_lower, "nonGoals must mention blockchain")
        self.assertIn("sdk", non_goals_lower, "nonGoals must mention SDK")

    def test_agenda_includes_non_goals(self):
        non_goals = self.agenda_json.get("nonGoals", [])
        self.assertTrue(len(non_goals) > 0, "Agenda nonGoals must not be empty")
        non_goals_lower = " ".join(non_goals).lower()
        self.assertIn("oauth", non_goals_lower, "nonGoals must mention OAuth")
        self.assertIn("jwt", non_goals_lower, "nonGoals must mention JWT")
        self.assertIn("blockchain", non_goals_lower, "nonGoals must mention blockchain")
        self.assertIn("sdk", non_goals_lower, "nonGoals must mention SDK")

    # ── 14. No obvious secrets appear in the JSON files ──────────────
    def test_no_obvious_secrets_in_questionnaire(self):
        text_lower = self.questionnaire_text.lower()
        for pattern in self.SECRET_PATTERNS:
            self.assertNotIn(
                pattern,
                text_lower,
                f"Questionnaire may contain secret-like pattern: {pattern}",
            )

    def test_no_obvious_secrets_in_agenda(self):
        text_lower = self.agenda_text.lower()
        for pattern in self.SECRET_PATTERNS:
            self.assertNotIn(
                pattern,
                text_lower,
                f"Agenda may contain secret-like pattern: {pattern}",
            )

    # ── Extra coherence checks ───────────────────────────────────────
    def test_questionnaire_has_id_and_version(self):
        self.assertEqual(
            self.questionnaire_json.get("questionnaireId"),
            "gl062-pilot-partner-questionnaire",
        )
        self.assertEqual(self.questionnaire_json.get("questionnaireVersion"), "1.0")

    def test_questionnaire_has_status(self):
        self.assertEqual(
            self.questionnaire_json.get("status"),
            "pilot-partner-preparation",
        )

    def test_agenda_has_id_and_version(self):
        self.assertEqual(
            self.agenda_json.get("agendaId"),
            "gl062-pilot-review-agenda",
        )
        self.assertEqual(self.agenda_json.get("agendaVersion"), "1.0")

    def test_agenda_has_status(self):
        self.assertEqual(
            self.agenda_json.get("status"),
            "pilot-review-preparation",
        )

    def test_agenda_has_meeting_goal(self):
        meeting_goal = self.agenda_json.get("meetingGoal", "")
        self.assertTrue(len(meeting_goal) > 0, "Agenda must have a meetingGoal")
        self.assertIn("Product Core", meeting_goal, "meetingGoal must mention Product Core")

    def test_agenda_has_prerequisites(self):
        prerequisites = self.agenda_json.get("prerequisites", [])
        self.assertTrue(len(prerequisites) > 0, "Agenda prerequisites must not be empty")
        prereq_text = " ".join(prerequisites).lower()
        self.assertIn("integration_guide.md", prereq_text, "Prerequisites must mention integration_guide.md")

    def test_agenda_has_demo_commands(self):
        demo_commands = self.agenda_json.get("demoCommands", [])
        self.assertTrue(len(demo_commands) > 0, "Agenda demoCommands must not be empty")
        commands_text = " ".join([d.get("command", "") for d in demo_commands]).lower()
        self.assertIn("gl061_api_smoke.py", commands_text, "demoCommands must reference gl061_api_smoke.py")

    def test_agenda_has_required_artifacts(self):
        artifacts = self.agenda_json.get("requiredArtifacts", [])
        self.assertTrue(len(artifacts) > 0, "Agenda requiredArtifacts must not be empty")
        artifact_paths = {a.get("path") for a in artifacts}
        self.assertIn(
            "docs/pilot_partner_preparation_pack.md",
            artifact_paths,
            "requiredArtifacts must reference the preparation pack",
        )
        self.assertIn(
            "docs/examples/gl062/pilot_partner_questionnaire.json",
            artifact_paths,
            "requiredArtifacts must reference the questionnaire",
        )
        self.assertIn(
            "docs/examples/gl062/pilot_review_agenda.json",
            artifact_paths,
            "requiredArtifacts must reference the agenda",
        )

    def test_agenda_has_decision_options(self):
        options = self.agenda_json.get("decisionOptions", [])
        self.assertTrue(len(options) > 0, "Agenda decisionOptions must not be empty")
        option_ids = {o.get("optionId") for o in options}
        self.assertIn("opt-01", option_ids, "decisionOptions must include opt-01")

    def test_agenda_has_default_decision_option(self):
        default = self.agenda_json.get("defaultDecisionOptionId", "")
        self.assertEqual(default, "opt-01", "defaultDecisionOptionId must be opt-01")

    def test_agenda_has_stop_conditions(self):
        conditions = self.agenda_json.get("stopConditions", [])
        self.assertTrue(len(conditions) > 0, "Agenda stopConditions must not be empty")
        conditions_text = " ".join(conditions).lower()
        self.assertIn("backend", conditions_text, "stopConditions must mention backend")
        self.assertIn("openapi", conditions_text, "stopConditions must mention OpenAPI")

    def test_questionnaire_partner_profile_not_empty(self):
        questions = self.questionnaire_json.get("partnerProfileQuestions", [])
        self.assertTrue(len(questions) > 0, "partnerProfileQuestions must not be empty")

    def test_questionnaire_workflow_fit_not_empty(self):
        questions = self.questionnaire_json.get("workflowFitQuestions", [])
        self.assertTrue(len(questions) > 0, "workflowFitQuestions must not be empty")

    def test_questionnaire_evidence_not_empty(self):
        questions = self.questionnaire_json.get("evidenceQuestions", [])
        self.assertTrue(len(questions) > 0, "evidenceQuestions must not be empty")

    def test_questionnaire_audit_compliance_not_empty(self):
        questions = self.questionnaire_json.get("auditComplianceQuestions", [])
        self.assertTrue(len(questions) > 0, "auditComplianceQuestions must not be empty")

    def test_questionnaire_integration_not_empty(self):
        questions = self.questionnaire_json.get("integrationQuestions", [])
        self.assertTrue(len(questions) > 0, "integrationQuestions must not be empty")

    def test_questionnaire_data_privacy_not_empty(self):
        questions = self.questionnaire_json.get("dataPrivacyQuestions", [])
        self.assertTrue(len(questions) > 0, "dataPrivacyQuestions must not be empty")

    def test_questionnaire_auth_security_not_empty(self):
        questions = self.questionnaire_json.get("authSecurityQuestions", [])
        self.assertTrue(len(questions) > 0, "authSecurityQuestions must not be empty")

    def test_questionnaire_production_hardening_not_empty(self):
        questions = self.questionnaire_json.get("productionHardeningQuestions", [])
        self.assertTrue(len(questions) > 0, "productionHardeningQuestions must not be empty")

    def test_questionnaire_success_criteria_not_empty(self):
        questions = self.questionnaire_json.get("pilotSuccessCriteriaQuestions", [])
        self.assertTrue(len(questions) > 0, "pilotSuccessCriteriaQuestions must not be empty")

    def test_questionnaire_blockers_not_empty(self):
        questions = self.questionnaire_json.get("blockerQuestions", [])
        self.assertTrue(len(questions) > 0, "blockerQuestions must not be empty")

    def test_preparation_pack_references_gl057(self):
        content = self.pack_doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("gl-057", content, "Pack must reference GL-057")

    def test_preparation_pack_references_gl058(self):
        content = self.pack_doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("gl-058", content, "Pack must reference GL-058")

    def test_preparation_pack_references_gl061(self):
        content = self.pack_doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("gl-061", content, "Pack must reference GL-061")

    def test_preparation_pack_references_questionnaire_json(self):
        content = self.pack_doc_path.read_text(encoding="utf-8")
        self.assertIn(
            "docs/examples/gl062/pilot_partner_questionnaire.json",
            content,
            "Pack must reference the questionnaire JSON",
        )

    def test_preparation_pack_references_agenda_json(self):
        content = self.pack_doc_path.read_text(encoding="utf-8")
        self.assertIn(
            "docs/examples/gl062/pilot_review_agenda.json",
            content,
            "Pack must reference the agenda JSON",
        )

    def test_preparation_pack_has_explicit_non_goals_section(self):
        content = self.pack_doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("explicit non-goals", content, "Pack must have an explicit non-goals section")
        self.assertIn("production deployment", content, "Non-goals must mention production deployment")
        self.assertIn("production auth", content, "Non-goals must mention production auth")

    def test_preparation_pack_has_pilot_success_criteria_section(self):
        content = self.pack_doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("pilot success criteria", content, "Pack must have a pilot success criteria section")
        self.assertIn("product core", content, "Success criteria must mention Product Core")

    def test_preparation_pack_has_recommended_next_decision_section(self):
        content = self.pack_doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("recommended next decision", content, "Pack must have a recommended next decision section")

    def test_preparation_pack_has_purpose_section(self):
        content = self.pack_doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("purpose", content, "Pack must have a purpose section")

    def test_preparation_pack_has_partner_profile_section(self):
        content = self.pack_doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("ideal first pilot partner profile", content, "Pack must document the ideal partner profile")


if __name__ == "__main__":
    unittest.main(verbosity=2)
