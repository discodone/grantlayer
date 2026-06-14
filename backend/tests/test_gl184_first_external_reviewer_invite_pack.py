"""GL-184: First External Reviewer Invite Pack."""

import json
import os
import subprocess
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GL184_BRANCH = "gl-184-first-external-reviewer-invite-pack"
REPORT_PATH = os.path.join(REPO_ROOT, "docs", "first_external_reviewer_invite_pack.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl184",
    "first_external_reviewer_invite_pack.json",
)

ALLOWED_CHANGED_FILES = {
    "docs/first_external_reviewer_invite_pack.md",
    "docs/examples/gl184/first_external_reviewer_invite_pack.json",
    "backend/tests/test_gl184_first_external_reviewer_invite_pack.py",
}

PUBLIC_REPO_URL = "https://github.com/Discodone/grantlayer.git"

REQUIRED_REVIEWER_PROFILE_KEYWORDS = [
    "external backend developer",
    "ai-agent workflow developer",
    "grant",
    "compliance",
    "audit",
    "security-minded technical reviewer",
]

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
}

REQUIRED_FEEDBACK_RECORDING_FIELDS = {
    "reviewer_profile",
    "review_date",
    "public_commit_reviewed",
    "reviewer_tasks_attempted",
    "quickstart_result",
    "first_verifiable_output_result",
    "docs_clarity_score",
    "trust_score",
    "caveat_visibility",
    "severity",
    "category",
    "next_action",
}


def _git_diff_files():
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    if branch.returncode == 0 and branch.stdout.strip() != GL184_BRANCH:
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


class TestGL184FilesExist(unittest.TestCase):
    def test_report_exists(self):
        self.assertTrue(os.path.isfile(REPORT_PATH), f"Missing report: {REPORT_PATH}")

    def test_json_exists(self):
        self.assertTrue(os.path.isfile(JSON_PATH), f"Missing JSON: {JSON_PATH}")


class TestGL184ArtifactJSON(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(JSON_PATH, encoding="utf-8") as fh:
            cls.data = json.load(fh)

    def test_valid_json(self):
        self.assertIsInstance(self.data, dict)

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-184")

    def test_public_repository_url(self):
        self.assertEqual(self.data.get("public_repository_url"), PUBLIC_REPO_URL)

    def test_reviewer_profiles_present(self):
        profiles = self.data.get("reviewer_profiles", [])
        self.assertIsInstance(profiles, list)
        self.assertGreaterEqual(len(profiles), 4, "Expected at least 4 reviewer profiles")

    def test_reviewer_profiles_include_required_archetypes(self):
        profiles = self.data.get("reviewer_profiles", [])
        combined = " ".join(
            (p.get("id", "") + " " + p.get("name", "") + " " + p.get("description", "")).lower()
            for p in profiles
        )
        self.assertIn("external backend developer", combined)
        self.assertIn("ai-agent workflow developer", combined)
        self.assertIn("grant", combined)
        self.assertIn("compliance", combined)
        self.assertIn("audit", combined)
        self.assertIn("security-minded technical reviewer", combined)

    def test_invite_message_draft_exists(self):
        draft = self.data.get("invite_message_draft", "")
        self.assertIsInstance(draft, str)
        self.assertGreater(len(draft.strip()), 100, "invite_message_draft must be non-trivial")

    def test_invite_message_mentions_preview(self):
        draft = self.data.get("invite_message_draft", "").lower()
        self.assertTrue(
            "technical preview" in draft or "developer preview" in draft,
            "invite_message_draft must mention 'technical preview' or 'developer preview'",
        )

    def test_invite_message_no_production_saas_claim(self):
        draft = self.data.get("invite_message_draft", "").lower()
        self.assertIn(
            "not a production",
            draft,
            "invite_message_draft must explicitly disclaim production SaaS readiness",
        )

    def test_invite_message_no_tenant_isolation_claim(self):
        draft = self.data.get("invite_message_draft", "").lower()
        self.assertIn(
            "tenant",
            draft,
            "invite_message_draft must address tenant isolation",
        )
        self.assertNotIn(
            "tenant isolation is implemented",
            draft,
            "invite_message_draft must not claim tenant isolation is implemented",
        )

    def test_invite_message_no_secrets_from_reviewers(self):
        draft = self.data.get("invite_message_draft", "").lower()
        self.assertTrue(
            "do not share secrets" in draft or "not share secrets" in draft or "no secrets" in draft,
            "invite_message_draft must instruct reviewers not to use/share secrets",
        )

    def test_invite_message_no_real_customer_data(self):
        draft = self.data.get("invite_message_draft", "").lower()
        self.assertIn(
            "customer data",
            draft,
            "invite_message_draft must address real customer data",
        )
        self.assertTrue(
            "do not share real customer data" in draft
            or "not share customer data" in draft
            or "do not share customer data" in draft
            or "real customer data" in draft,
            "invite_message_draft must instruct reviewers not to share real customer data",
        )

    def test_invite_message_directs_security_to_advisories(self):
        draft = self.data.get("invite_message_draft", "").lower()
        self.assertIn(
            "github security advisories",
            draft,
            "invite_message_draft must direct security-sensitive feedback to GitHub Security Advisories",
        )

    def test_invite_message_links_to_public_repo(self):
        draft = self.data.get("invite_message_draft", "")
        self.assertIn(
            "https://github.com/Discodone/grantlayer.git",
            draft,
            "invite_message_draft must link to the public GitHub repository",
        )

    def test_reviewer_task_list_present(self):
        tasks = self.data.get("reviewer_task_list", [])
        self.assertIsInstance(tasks, list)
        self.assertGreater(len(tasks), 0, "reviewer_task_list must be non-empty")

    def test_reviewer_task_list_includes_readme(self):
        tasks = self.data.get("reviewer_task_list", [])
        combined = " ".join(tasks).lower()
        self.assertIn("readme", combined, "reviewer_task_list must include README task")

    def test_reviewer_task_list_includes_security(self):
        tasks = self.data.get("reviewer_task_list", [])
        combined = " ".join(tasks).lower()
        self.assertIn("security", combined, "reviewer_task_list must include SECURITY task")

    def test_reviewer_task_list_includes_first_verifiable_output(self):
        tasks = self.data.get("reviewer_task_list", [])
        combined = " ".join(tasks).lower()
        self.assertTrue(
            "first verifiable output" in combined or "first_verifiable_output" in combined,
            "reviewer_task_list must include first verifiable output task",
        )

    def test_feedback_questions_present(self):
        questions = self.data.get("feedback_questions", [])
        self.assertIsInstance(questions, list)
        self.assertGreater(len(questions), 0, "feedback_questions must be non-empty")

    def test_feedback_questions_include_clarity(self):
        questions = self.data.get("feedback_questions", [])
        combined = " ".join(questions).lower()
        self.assertTrue(
            "confus" in combined or "clarity" in combined or "clear" in combined,
            "feedback_questions must include clarity-related question",
        )

    def test_feedback_questions_include_quickstart(self):
        questions = self.data.get("feedback_questions", [])
        combined = " ".join(questions).lower()
        self.assertTrue(
            "quickstart" in combined
            or "first verifiable output" in combined
            or "first_verifiable_output" in combined
            or "run" in combined,
            "feedback_questions must include quickstart-related question",
        )

    def test_feedback_questions_include_trust(self):
        questions = self.data.get("feedback_questions", [])
        combined = " ".join(questions).lower()
        self.assertTrue(
            "trust" in combined or "credib" in combined,
            "feedback_questions must include trust-related question",
        )

    def test_feedback_questions_include_caveats(self):
        questions = self.data.get("feedback_questions", [])
        combined = " ".join(questions).lower()
        self.assertTrue(
            "caveat" in combined or "non-production" in combined or "not production" in combined,
            "feedback_questions must include caveat-visibility question",
        )

    def test_feedback_questions_include_next_example(self):
        questions = self.data.get("feedback_questions", [])
        combined = " ".join(questions).lower()
        self.assertTrue(
            "next example" in combined or "smallest" in combined or "usefulness" in combined
            or "try" in combined or "sdk" in combined or "api" in combined,
            "feedback_questions must include next-example or usefulness question",
        )

    def test_reviewer_safety_instructions_present(self):
        instructions = self.data.get("reviewer_safety_instructions", [])
        self.assertIsInstance(instructions, list)
        self.assertGreater(len(instructions), 0, "reviewer_safety_instructions must be non-empty")

    def test_reviewer_safety_no_secrets(self):
        instructions = self.data.get("reviewer_safety_instructions", [])
        combined = " ".join(instructions).lower()
        self.assertIn("secrets", combined, "reviewer_safety_instructions must address secrets")

    def test_reviewer_safety_no_customer_data(self):
        instructions = self.data.get("reviewer_safety_instructions", [])
        combined = " ".join(instructions).lower()
        self.assertIn(
            "customer data",
            combined,
            "reviewer_safety_instructions must address customer data",
        )

    def test_reviewer_safety_no_private_grants(self):
        instructions = self.data.get("reviewer_safety_instructions", [])
        combined = " ".join(instructions).lower()
        self.assertTrue(
            "private grant" in combined or "institutional data" in combined or "private grants" in combined,
            "reviewer_safety_instructions must address private grants or institutional data",
        )

    def test_reviewer_safety_no_exploit_details_publicly(self):
        instructions = self.data.get("reviewer_safety_instructions", [])
        combined = " ".join(instructions).lower()
        self.assertIn(
            "exploit details",
            combined,
            "reviewer_safety_instructions must say not to post exploit details publicly",
        )

    def test_reviewer_safety_directs_to_advisories(self):
        instructions = self.data.get("reviewer_safety_instructions", [])
        combined = " ".join(instructions).lower()
        self.assertIn(
            "github security advisories",
            combined,
            "reviewer_safety_instructions must direct security-sensitive reports to GitHub Security Advisories",
        )

    def test_feedback_recording_model_present(self):
        model = self.data.get("feedback_recording_model", {})
        self.assertIsInstance(model, dict)
        self.assertGreater(len(model), 0, "feedback_recording_model must be non-empty")

    def test_feedback_recording_model_required_fields(self):
        model = self.data.get("feedback_recording_model", {})
        for field in REQUIRED_FEEDBACK_RECORDING_FIELDS:
            self.assertIn(
                field,
                model,
                f"feedback_recording_model must include field: {field}",
            )

    def test_triage_alignment_present(self):
        alignment = self.data.get("triage_alignment", {})
        self.assertIsInstance(alignment, dict)

    def test_triage_alignment_references_gl183(self):
        alignment = self.data.get("triage_alignment", {})
        ref = alignment.get("reference", "").lower()
        self.assertIn("gl-183", ref, "triage_alignment must reference GL-183")

    def test_triage_alignment_includes_gl183_categories(self):
        alignment = self.data.get("triage_alignment", {})
        categories = alignment.get("categories", [])
        self.assertIsInstance(categories, list)
        found = set(categories)
        for category in REQUIRED_TRIAGE_CATEGORIES:
            self.assertIn(
                category,
                found,
                f"triage_alignment must include GL-183 category: {category}",
            )

    def test_non_goals_present(self):
        non_goals = self.data.get("non_goals", [])
        self.assertIsInstance(non_goals, list)
        self.assertGreater(len(non_goals), 0, "non_goals must be non-empty")

    def test_non_goals_no_production_saas(self):
        non_goals = self.data.get("non_goals", [])
        combined = " ".join(non_goals).lower()
        self.assertIn("production saas", combined, "non_goals must include no production SaaS promise")

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

    def test_non_goals_no_payment_treasury(self):
        non_goals = self.data.get("non_goals", [])
        combined = " ".join(non_goals).lower()
        self.assertTrue(
            "payment" in combined or "treasury" in combined,
            "non_goals must include no payment/treasury flow",
        )

    def test_non_goals_no_sla(self):
        non_goals = self.data.get("non_goals", [])
        combined = " ".join(non_goals).lower()
        self.assertIn("sla", combined, "non_goals must include no SLA/support promise")

    def test_non_goals_no_github_label_creation(self):
        non_goals = self.data.get("non_goals", [])
        combined = " ".join(non_goals).lower()
        self.assertTrue(
            "github label" in combined or "label creation" in combined,
            "non_goals must include no GitHub label creation in this issue",
        )

    def test_non_goals_no_reviewer_outreach_sent(self):
        non_goals = self.data.get("non_goals", [])
        combined = " ".join(non_goals).lower()
        self.assertTrue(
            "outreach" in combined or "invite" in combined,
            "non_goals must include no reviewer outreach sent in this issue",
        )

    def test_safety_confirmations_present(self):
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


class TestGL184ReportExplicitStatements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(REPORT_PATH, encoding="utf-8") as fh:
            cls.content = fh.read().lower()

    def test_report_says_no_outreach_sent(self):
        self.assertTrue(
            "no outreach was sent" in self.content or "outreach was sent" in self.content,
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
            "no github api label" in self.content or "no github api label or issue changes" in self.content,
            "report must explicitly say no GitHub API label or issue changes were performed",
        )


class TestGL184ScopeGuards(unittest.TestCase):
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
                "build-clean-public-snapshot", path, f"Forbidden snapshot publish script change: {path}"
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
