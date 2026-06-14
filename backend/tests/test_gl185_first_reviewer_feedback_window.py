"""GL-185: First Reviewer Feedback Window / Feedback Capture."""

import json
import os
import subprocess
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GL185_BRANCH = "gl-185-first-reviewer-feedback-window"
REPORT_PATH = os.path.join(REPO_ROOT, "docs", "first_reviewer_feedback_window.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl185",
    "first_reviewer_feedback_window.json",
)

ALLOWED_CHANGED_FILES = {
    "docs/first_reviewer_feedback_window.md",
    "docs/examples/gl185/first_reviewer_feedback_window.json",
    "backend/tests/test_gl185_first_reviewer_feedback_window.py",
}

PUBLIC_REPO_URL = "https://github.com/Discodone/grantlayer.git"

REQUIRED_TRIAGE_CATEGORIES = {
    "blocker",
    "confusing-docs",
    "broken-quickstart",
    "missing-example",
    "product-question",
    "security-concern",
    "production-readiness-concern",
    "feature-request",
    "non-scope-later",
}

REQUIRED_SEVERITY_LEVELS = {"critical", "high", "medium", "low", "info"}

REQUIRED_FEEDBACK_RECORD_FIELDS = {
    "feedback_id",
    "reviewer_profile",
    "invite_sent_date",
    "response_received_date",
    "public_commit_reviewed",
    "tasks_attempted",
    "first_verifiable_output_result",
    "docs_clarity_score",
    "trust_score",
    "caveat_visibility",
    "quickstart_result",
    "category",
    "severity",
    "blocking",
    "security_sensitive",
    "next_action",
}

REQUIRED_SAFETY_CONFIRMATIONS = {
    "no_outreach_sent",
    "no_github_push_performed",
    "no_visibility_change_performed",
    "internal_repo_not_pushed_directly_to_github",
    "no_github_api_label_changes_performed",
    "no_github_issue_changes_performed",
    "production_saas_not_claimed",
    "tenant_isolation_not_claimed",
    "real_customer_data_not_requested",
    "private_grant_data_not_requested",
    "secrets_not_requested",
    "exploit_details_not_requested_publicly",
    "security_sensitive_reports_directed_to_advisories",
    "automated_reviewer_contact_not_performed",
}


def _git_diff_files():
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    if branch.returncode == 0 and branch.stdout.strip() != GL185_BRANCH:
        return list(ALLOWED_CHANGED_FILES)
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD^1..HEAD"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        return []
    files = []
    for line in result.stdout.splitlines():
        path = line.strip()
        if path:
            files.append(path)
    return files


class TestGL185FilesExist(unittest.TestCase):
    def test_report_exists(self):
        self.assertTrue(os.path.isfile(REPORT_PATH), f"Missing report: {REPORT_PATH}")

    def test_json_exists(self):
        self.assertTrue(os.path.isfile(JSON_PATH), f"Missing JSON: {JSON_PATH}")


class TestGL185ArtifactJSON(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(JSON_PATH, encoding="utf-8") as fh:
            cls.data = json.load(fh)

    def test_valid_json(self):
        self.assertIsInstance(self.data, dict)

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-185")

    def test_public_repository_url(self):
        self.assertEqual(self.data.get("public_repository_url"), PUBLIC_REPO_URL)

    # --- feedback_window ---

    def test_feedback_window_exists(self):
        window = self.data.get("feedback_window", {})
        self.assertIsInstance(window, dict)
        self.assertGreater(len(window), 0, "feedback_window must be non-empty")

    def test_feedback_window_target_reviewer_count(self):
        window = self.data.get("feedback_window", {})
        combined = " ".join(str(v) for v in window.values()).lower()
        self.assertTrue(
            "2" in combined and "5" in combined,
            "feedback_window must include target reviewer count of 2-5",
        )

    def test_feedback_window_manual_capture_only(self):
        window = self.data.get("feedback_window", {})
        combined = " ".join(str(v) for v in window.values()).lower()
        self.assertIn(
            "manual",
            combined,
            "feedback_window must state manual/internal feedback capture only",
        )

    def test_feedback_window_no_automated_outreach(self):
        window = self.data.get("feedback_window", {})
        self.assertFalse(
            window.get("automated_outreach_performed", True),
            "feedback_window must confirm no automated outreach was performed",
        )

    # --- reviewer_invitation_procedure ---

    def test_reviewer_invitation_procedure_exists(self):
        proc = self.data.get("reviewer_invitation_procedure", {})
        self.assertIsInstance(proc, dict)
        self.assertGreater(len(proc), 0, "reviewer_invitation_procedure must be non-empty")

    def test_reviewer_invitation_procedure_is_manual(self):
        proc = self.data.get("reviewer_invitation_procedure", {})
        method = proc.get("method", "").lower()
        self.assertIn(
            "manual",
            method,
            "reviewer_invitation_procedure must say invites are manual",
        )

    def test_reviewer_invitation_procedure_references_gl184(self):
        proc = self.data.get("reviewer_invitation_procedure", {})
        combined = json.dumps(proc).lower()
        self.assertTrue(
            "gl-184" in combined or "invite pack" in combined,
            "reviewer_invitation_procedure must reference GL-184 invite pack or invite message",
        )

    def test_reviewer_invitation_procedure_no_secrets(self):
        proc = self.data.get("reviewer_invitation_procedure", {})
        combined = json.dumps(proc).lower()
        self.assertTrue(
            "no secrets" in combined or "secrets" in combined,
            "reviewer_invitation_procedure must say no secrets/customer data/exploit details",
        )

    # --- feedback_capture_record_model ---

    def test_feedback_capture_record_model_exists(self):
        model = self.data.get("feedback_capture_record_model", {})
        self.assertIsInstance(model, dict)
        self.assertGreater(len(model), 0, "feedback_capture_record_model must be non-empty")

    def test_feedback_capture_record_model_required_fields(self):
        model = self.data.get("feedback_capture_record_model", {})
        for field in REQUIRED_FEEDBACK_RECORD_FIELDS:
            self.assertIn(
                field,
                model,
                f"feedback_capture_record_model must include field: {field}",
            )

    # --- feedback_triage_flow ---

    def test_feedback_triage_flow_exists(self):
        flow = self.data.get("feedback_triage_flow", {})
        self.assertIsInstance(flow, dict)
        self.assertGreater(len(flow), 0, "feedback_triage_flow must be non-empty")

    def test_feedback_triage_flow_references_gl183(self):
        flow = self.data.get("feedback_triage_flow", {})
        ref = flow.get("reference", "").lower()
        self.assertIn("gl-183", ref, "feedback_triage_flow must reference GL-183")

    def test_feedback_triage_flow_includes_gl183_categories(self):
        flow = self.data.get("feedback_triage_flow", {})
        categories = flow.get("categories", [])
        self.assertIsInstance(categories, list)
        found = {item.get("id") for item in categories}
        for category in REQUIRED_TRIAGE_CATEGORIES:
            self.assertIn(
                category,
                found,
                f"feedback_triage_flow must include GL-183 category: {category}",
            )

    def test_feedback_triage_flow_includes_severity_levels(self):
        flow = self.data.get("feedback_triage_flow", {})
        levels = flow.get("severity_levels", [])
        self.assertIsInstance(levels, list)
        found = {item.get("severity") for item in levels}
        for severity in REQUIRED_SEVERITY_LEVELS:
            self.assertIn(
                severity,
                found,
                f"feedback_triage_flow must include severity level: {severity}",
            )

    # --- safety_checklist ---

    def test_safety_checklist_exists(self):
        checklist = self.data.get("safety_checklist", {})
        self.assertIsInstance(checklist, dict)
        self.assertGreater(len(checklist), 0, "safety_checklist must be non-empty")

    def test_safety_checklist_no_secrets(self):
        checklist = self.data.get("safety_checklist", {})
        combined = json.dumps(checklist).lower()
        self.assertIn("secrets", combined, "safety_checklist must address secrets")

    def test_safety_checklist_no_customer_data(self):
        checklist = self.data.get("safety_checklist", {})
        combined = json.dumps(checklist).lower()
        self.assertIn("customer data", combined, "safety_checklist must address customer data")

    def test_safety_checklist_no_private_grants(self):
        checklist = self.data.get("safety_checklist", {})
        combined = json.dumps(checklist).lower()
        self.assertTrue(
            "private grant" in combined or "institutional data" in combined,
            "safety_checklist must address private grants or institutional data",
        )

    def test_safety_checklist_no_exploit_details_publicly(self):
        checklist = self.data.get("safety_checklist", {})
        combined = json.dumps(checklist).lower()
        self.assertIn(
            "exploit details",
            combined,
            "safety_checklist must address exploit details publicly",
        )

    def test_safety_checklist_synthetic_data_only(self):
        checklist = self.data.get("safety_checklist", {})
        combined = json.dumps(checklist).lower()
        self.assertTrue(
            "synthetic" in combined or "demo data" in combined,
            "safety_checklist must say use synthetic/demo data only",
        )

    def test_safety_checklist_directs_to_advisories(self):
        checklist = self.data.get("safety_checklist", {})
        combined = json.dumps(checklist).lower()
        self.assertIn(
            "github security advisories",
            combined,
            "safety_checklist must direct security-sensitive reports to GitHub Security Advisories",
        )

    # --- initial_reviewer_packet ---

    def test_initial_reviewer_packet_exists(self):
        packet = self.data.get("initial_reviewer_packet", {})
        self.assertIsInstance(packet, dict)
        self.assertGreater(len(packet), 0, "initial_reviewer_packet must be non-empty")

    def test_initial_reviewer_packet_public_github_url(self):
        packet = self.data.get("initial_reviewer_packet", {})
        combined = json.dumps(packet).lower()
        self.assertIn(
            "github.com/discodone/grantlayer",
            combined,
            "initial_reviewer_packet must include public GitHub URL",
        )

    def test_initial_reviewer_packet_technical_preview_caveat(self):
        packet = self.data.get("initial_reviewer_packet", {})
        combined = json.dumps(packet).lower()
        self.assertTrue(
            "technical preview" in combined or "developer preview" in combined,
            "initial_reviewer_packet must include technical preview caveat",
        )

    def test_initial_reviewer_packet_first_verifiable_output_task(self):
        packet = self.data.get("initial_reviewer_packet", {})
        combined = json.dumps(packet).lower()
        self.assertTrue(
            "first verifiable output" in combined or "first_verifiable_output" in combined,
            "initial_reviewer_packet must include first verifiable output task",
        )

    def test_initial_reviewer_packet_feedback_questions(self):
        packet = self.data.get("initial_reviewer_packet", {})
        self.assertIn(
            "feedback_questions",
            packet,
            "initial_reviewer_packet must include feedback_questions field",
        )
        self.assertIsInstance(packet["feedback_questions"], list)
        self.assertGreater(len(packet["feedback_questions"]), 0)

    def test_initial_reviewer_packet_safety_instructions(self):
        packet = self.data.get("initial_reviewer_packet", {})
        combined = json.dumps(packet).lower()
        self.assertIn(
            "safety",
            combined,
            "initial_reviewer_packet must include safety instructions",
        )

    # --- success_criteria ---

    def test_success_criteria_exists(self):
        criteria = self.data.get("success_criteria", [])
        self.assertIsInstance(criteria, list)
        self.assertGreater(len(criteria), 0, "success_criteria must be non-empty")

    def test_success_criteria_2_to_5_reviewers_invited(self):
        criteria = self.data.get("success_criteria", [])
        combined = " ".join(criteria).lower()
        self.assertTrue(
            "2" in combined and "5" in combined and "invited" in combined,
            "success_criteria must include 2-5 reviewers invited manually",
        )

    def test_success_criteria_responses_captured(self):
        criteria = self.data.get("success_criteria", [])
        combined = " ".join(criteria).lower()
        self.assertTrue(
            "response" in combined or "captured" in combined,
            "success_criteria must include responses captured",
        )

    def test_success_criteria_no_secrets_customer_data(self):
        criteria = self.data.get("success_criteria", [])
        combined = " ".join(criteria).lower()
        self.assertTrue(
            "secrets" in combined or "customer data" in combined,
            "success_criteria must include no secrets/customer data collected",
        )

    def test_success_criteria_feedback_categorized(self):
        criteria = self.data.get("success_criteria", [])
        combined = " ".join(criteria).lower()
        self.assertTrue(
            "categorized" in combined or "triage" in combined,
            "success_criteria must include feedback categorized",
        )

    def test_success_criteria_severity_ranked(self):
        criteria = self.data.get("success_criteria", [])
        combined = " ".join(criteria).lower()
        self.assertIn(
            "severity",
            combined,
            "success_criteria must include severity-ranked",
        )

    # --- non_goals ---

    def test_non_goals_exists(self):
        non_goals = self.data.get("non_goals", [])
        self.assertIsInstance(non_goals, list)
        self.assertGreater(len(non_goals), 0, "non_goals must be non-empty")

    def test_non_goals_no_outreach_sent(self):
        non_goals = self.data.get("non_goals", [])
        combined = " ".join(non_goals).lower()
        self.assertIn(
            "outreach",
            combined,
            "non_goals must include no outreach sent by this issue",
        )

    def test_non_goals_no_production_saas(self):
        non_goals = self.data.get("non_goals", [])
        combined = " ".join(non_goals).lower()
        self.assertIn(
            "production saas",
            combined,
            "non_goals must include no production SaaS promise",
        )

    def test_non_goals_no_tenant_isolation(self):
        non_goals = self.data.get("non_goals", [])
        combined = " ".join(non_goals).lower()
        self.assertTrue(
            "tenant/workspace isolation" in combined or "tenant isolation" in combined,
            "non_goals must include no tenant/workspace isolation claim",
        )

    def test_non_goals_no_real_customer_data(self):
        non_goals = self.data.get("non_goals", [])
        combined = " ".join(non_goals).lower()
        self.assertIn(
            "customer data",
            combined,
            "non_goals must include no real customer data collection",
        )

    def test_non_goals_no_github_label_creation(self):
        non_goals = self.data.get("non_goals", [])
        combined = " ".join(non_goals).lower()
        self.assertTrue(
            "github label" in combined or "label creation" in combined,
            "non_goals must include no GitHub label creation",
        )

    def test_non_goals_no_github_issue_creation(self):
        non_goals = self.data.get("non_goals", [])
        combined = " ".join(non_goals).lower()
        self.assertTrue(
            "github issue creation" in combined or "no github issue" in combined,
            "non_goals must include no GitHub issue creation",
        )

    def test_non_goals_no_automated_personal_data_collection(self):
        non_goals = self.data.get("non_goals", [])
        combined = " ".join(non_goals).lower()
        self.assertTrue(
            "automated collection" in combined or "personal reviewer data" in combined,
            "non_goals must include no automated collection of personal reviewer data",
        )

    # --- safety_confirmations ---

    def test_safety_confirmations_exists(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertIsInstance(confirmations, dict)

    def test_safety_confirmations_all_keys_present(self):
        confirmations = self.data.get("safety_confirmations", {})
        for key in REQUIRED_SAFETY_CONFIRMATIONS:
            self.assertIn(
                key,
                confirmations,
                f"safety_confirmations must include key: {key}",
            )

    def test_safety_confirmations_all_true(self):
        confirmations = self.data.get("safety_confirmations", {})
        for key in REQUIRED_SAFETY_CONFIRMATIONS:
            self.assertTrue(
                confirmations.get(key),
                f"safety_confirmations[{key!r}] must be true",
            )

    def test_changed_files_present(self):
        changed = self.data.get("changed_files", [])
        self.assertIsInstance(changed, list)
        self.assertEqual(set(changed), ALLOWED_CHANGED_FILES)


class TestGL185ReportExplicitStatements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(REPORT_PATH, encoding="utf-8") as fh:
            cls.content = fh.read().lower()

    def test_report_says_no_outreach_sent(self):
        self.assertTrue(
            "no outreach was sent" in self.content,
            "report must explicitly say no outreach was sent",
        )

    def test_report_says_no_github_push(self):
        self.assertIn(
            "no github push was performed",
            self.content,
            "report must explicitly say no GitHub push was performed",
        )

    def test_report_says_no_visibility_change(self):
        self.assertIn(
            "no visibility change was performed",
            self.content,
            "report must explicitly say no visibility change was performed",
        )

    def test_report_says_internal_repo_not_pushed_to_github(self):
        self.assertIn(
            "internal repo was not pushed directly to github",
            self.content,
            "report must explicitly say internal repo was not pushed directly to GitHub",
        )

    def test_report_says_no_github_api_label_or_issue_changes(self):
        self.assertTrue(
            "no github api label" in self.content
            or "no github api label or issue changes" in self.content,
            "report must explicitly say no GitHub API label or issue changes were performed",
        )


class TestGL185ScopeGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.diff_files = _git_diff_files()

    def test_changed_files_within_allowed_scope(self):
        self.assertEqual(set(self.diff_files), ALLOWED_CHANGED_FILES)

    def test_no_backend_src_changes(self):
        for path in self.diff_files:
            self.assertFalse(path.startswith("backend/src/"), f"Forbidden backend/src change: {path}")

    def test_no_openapi_changes(self):
        for path in self.diff_files:
            self.assertNotIn("openapi", path.lower(), f"Forbidden OpenAPI change: {path}")

    def test_no_migration_changes(self):
        for path in self.diff_files:
            self.assertFalse("migrations" in path, f"Forbidden migration change: {path}")

    def test_no_db_schema_changes(self):
        for path in self.diff_files:
            self.assertFalse("/db/" in path.lower(), f"Forbidden db/schema change: {path}")

    def test_no_dependency_manifest_changes(self):
        for path in self.diff_files:
            self.assertNotIn("requirements", path, f"Forbidden dependency manifest change: {path}")

    def test_no_sdk_implementation_changes(self):
        for path in self.diff_files:
            self.assertFalse(path.startswith("sdk/"), f"Forbidden SDK change: {path}")

    def test_no_frontend_website_design_changes(self):
        for path in self.diff_files:
            self.assertFalse(path.startswith("frontend/"), f"Forbidden frontend change: {path}")
            self.assertFalse(path.startswith("website/"), f"Forbidden website change: {path}")
            self.assertFalse(path.startswith("design/"), f"Forbidden design change: {path}")

    def test_no_github_workflow_changes(self):
        for path in self.diff_files:
            self.assertFalse(
                path.startswith(".github/workflows/"), f"Forbidden GitHub workflow change: {path}"
            )

    def test_no_snapshot_publish_script_behavior_changes(self):
        for path in self.diff_files:
            self.assertNotIn(
                "build-clean-public-snapshot", path,
                f"Forbidden snapshot publish script change: {path}",
            )

    def test_no_git_remote_changes(self):
        for path in self.diff_files:
            self.assertNotIn(".git/config", path, f"Forbidden git config change: {path}")

    def test_no_public_github_push(self):
        for path in self.diff_files:
            self.assertFalse(path == "public-github-push", f"Forbidden public GitHub push: {path}")

    def test_no_visibility_change(self):
        for path in self.diff_files:
            self.assertFalse(path == "visibility-change", f"Forbidden visibility change: {path}")

    def test_no_paperclip_status_updates(self):
        for path in self.diff_files:
            self.assertNotIn("paperclip", path.lower(), f"Forbidden Paperclip reference: {path}")


if __name__ == "__main__":
    unittest.main()
