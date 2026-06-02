"""
GL-182: External Developer Feedback Intake
Tests for docs, JSON artifact, and scope guards.
"""
import json
import os
import subprocess
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

REPORT_PATH = os.path.join(REPO_ROOT, "docs", "external_developer_feedback_intake.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl182",
    "external_developer_feedback_intake.json",
)

ALLOWED_CHANGED_FILES = {
    "docs/external_developer_feedback_intake.md",
    "docs/examples/gl182/external_developer_feedback_intake.json",
    "backend/tests/test_gl182_external_developer_feedback_intake.py",
}

REQUIRED_REVIEWER_PROFILE_IDS = {
    "external-backend-developer",
    "ai-agent-workflow-developer",
    "grant-compliance-audit-reviewer",
    "security-minded-technical-reviewer",
}

REQUIRED_TRIAGE_CATEGORIES = {
    "blocker",
    "confusing-docs",
    "broken-quickstart",
    "security-concern",
    "production-readiness-concern",
    "feature-request",
}

REQUIRED_SEVERITY_LEVELS = {"critical", "high", "medium", "low", "info"}

REQUIRED_SAFETY_CONFIRMATION_KEYS = {
    "no_github_push_performed",
    "no_visibility_change_performed",
    "internal_repo_not_pushed_directly_to_github",
    "production_saas_not_claimed",
    "tenant_isolation_not_claimed",
    "real_customer_data_not_requested",
    "secrets_not_requested",
    "security_sensitive_reports_directed_to_advisories",
}


def _git_diff_files():
    result = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        return []
    files = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            files.append(parts[1])
    return files


class TestGL182FilesExist(unittest.TestCase):
    def test_report_exists(self):
        self.assertTrue(os.path.isfile(REPORT_PATH), f"Missing report: {REPORT_PATH}")

    def test_json_exists(self):
        self.assertTrue(os.path.isfile(JSON_PATH), f"Missing JSON: {JSON_PATH}")


class TestGL182ArtifactJSON(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(JSON_PATH, encoding="utf-8") as fh:
            cls.data = json.load(fh)

    def test_valid_json(self):
        self.assertIsInstance(self.data, dict)

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-182")

    def test_target_reviewer_profiles_present(self):
        profiles = self.data.get("target_reviewer_profiles", [])
        self.assertTrue(len(profiles) >= 4, "Expected at least 4 reviewer profiles")

    def test_required_reviewer_profile_ids(self):
        profiles = self.data.get("target_reviewer_profiles", [])
        found_ids = {p.get("id") for p in profiles}
        for required_id in REQUIRED_REVIEWER_PROFILE_IDS:
            self.assertIn(
                required_id,
                found_ids,
                f"Required reviewer profile ID missing: {required_id}",
            )

    def test_reviewer_tasks_include_first_verifiable_output(self):
        tasks = self.data.get("reviewer_tasks", [])
        combined = " ".join(
            t.get("task", "") + " " + t.get("goal", "") + " " + t.get("command", "")
            for t in tasks
        ).lower()
        self.assertIn(
            "first verifiable output",
            combined,
            "reviewer_tasks must include the first verifiable output task",
        )

    def test_feedback_questions_include_quickstart(self):
        questions = self.data.get("feedback_questions", [])
        combined = " ".join(q.get("question", "") for q in questions).lower()
        self.assertIn(
            "10 minutes",
            combined,
            "feedback_questions must ask about quickstart / 10-minute path",
        )

    def test_feedback_questions_include_caveat_visibility(self):
        questions = self.data.get("feedback_questions", [])
        combined = " ".join(q.get("question", "") for q in questions).lower()
        self.assertTrue(
            "caveat" in combined or "safety" in combined or "not production" in combined,
            "feedback_questions must ask about caveat visibility",
        )

    def test_triage_categories_present(self):
        categories = self.data.get("triage_categories", [])
        found_ids = {c.get("id") for c in categories}
        for required in REQUIRED_TRIAGE_CATEGORIES:
            self.assertIn(
                required,
                found_ids,
                f"Required triage category missing: {required}",
            )

    def test_severity_model_present(self):
        severity = self.data.get("severity_model", [])
        found_levels = {s.get("level") for s in severity}
        for level in REQUIRED_SEVERITY_LEVELS:
            self.assertIn(
                level,
                found_levels,
                f"Required severity level missing: {level}",
            )

    def test_reviewer_safety_instructions_no_secrets(self):
        instructions = self.data.get("reviewer_safety_instructions", [])
        combined = " ".join(instructions).lower()
        self.assertTrue(
            "secret" in combined or "credential" in combined,
            "reviewer_safety_instructions must say not to include secrets",
        )

    def test_reviewer_safety_instructions_no_customer_data(self):
        instructions = self.data.get("reviewer_safety_instructions", [])
        combined = " ".join(instructions).lower()
        self.assertIn(
            "customer data",
            combined,
            "reviewer_safety_instructions must say not to include customer data",
        )

    def test_reviewer_safety_instructions_direct_to_advisories(self):
        instructions = self.data.get("reviewer_safety_instructions", [])
        combined = " ".join(instructions).lower()
        self.assertTrue(
            "security advisor" in combined or "advisories" in combined,
            "reviewer_safety_instructions must direct security-sensitive reports to GitHub Security Advisories",
        )

    def test_non_goals_no_production_saas(self):
        non_goals = self.data.get("non_goals", [])
        ids = {ng.get("item", "") for ng in non_goals}
        descriptions = " ".join(ng.get("description", "") for ng in non_goals).lower()
        self.assertTrue(
            "no-production-saas-promise" in ids or "production saas" in descriptions,
            "non_goals must include no production SaaS promise",
        )

    def test_non_goals_no_tenant_isolation(self):
        non_goals = self.data.get("non_goals", [])
        ids = {ng.get("item", "") for ng in non_goals}
        descriptions = " ".join(ng.get("description", "") for ng in non_goals).lower()
        self.assertTrue(
            "no-tenant-isolation-claim" in ids or "tenant" in descriptions,
            "non_goals must include no tenant/workspace isolation claim",
        )

    def test_non_goals_no_payment_treasury(self):
        non_goals = self.data.get("non_goals", [])
        descriptions = " ".join(ng.get("description", "") for ng in non_goals).lower()
        self.assertTrue(
            "payment" in descriptions or "treasury" in descriptions,
            "non_goals must include no payment/treasury flow",
        )

    def test_non_goals_no_real_customer_data(self):
        non_goals = self.data.get("non_goals", [])
        descriptions = " ".join(ng.get("description", "") for ng in non_goals).lower()
        self.assertTrue(
            "real" in descriptions and "customer data" in descriptions,
            "non_goals must include no real grant/customer data collection",
        )

    def test_safety_confirmations_present(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertIsInstance(confirmations, dict)
        for key in REQUIRED_SAFETY_CONFIRMATION_KEYS:
            self.assertIn(key, confirmations, f"Missing safety confirmation: {key}")

    def test_safety_confirmations_all_true(self):
        confirmations = self.data.get("safety_confirmations", {})
        for key in REQUIRED_SAFETY_CONFIRMATION_KEYS:
            if key in confirmations:
                self.assertTrue(
                    confirmations[key],
                    f"Safety confirmation must be true: {key}",
                )

    def test_non_goals_confirm_no_push_or_visibility_change(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertTrue(
            confirmations.get("no_github_push_performed", False),
            "safety_confirmations.no_github_push_performed must be true",
        )
        self.assertTrue(
            confirmations.get("no_visibility_change_performed", False),
            "safety_confirmations.no_visibility_change_performed must be true",
        )
        self.assertTrue(
            confirmations.get("internal_repo_not_pushed_directly_to_github", False),
            "safety_confirmations.internal_repo_not_pushed_directly_to_github must be true",
        )

    def test_finding_counts_present(self):
        counts = self.data.get("finding_counts_by_severity", {})
        self.assertIsInstance(counts, dict)
        for level in REQUIRED_SEVERITY_LEVELS:
            self.assertIn(level, counts, f"finding_counts_by_severity missing level: {level}")

    def test_changed_files_present(self):
        changed = self.data.get("changed_files", [])
        self.assertTrue(len(changed) > 0, "changed_files must not be empty")


class TestGL182ReportContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(REPORT_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()

    def test_mentions_issue_id(self):
        self.assertIn("GL-182", self.text)

    def test_states_no_github_push(self):
        lower = self.text.lower()
        self.assertIn("no github push", lower)

    def test_states_no_visibility_change(self):
        lower = self.text.lower()
        self.assertIn("no visibility change", lower)

    def test_states_internal_repo_not_pushed_directly(self):
        lower = self.text.lower()
        self.assertTrue(
            "internal repo was not pushed directly" in lower
            or "not pushed directly to github" in lower,
            "Report must state internal repo was not pushed directly to GitHub",
        )

    def test_mentions_target_reviewer_profiles(self):
        self.assertIn("Target Reviewer Profile", self.text)

    def test_mentions_feedback_questions(self):
        self.assertIn("Feedback Question", self.text)

    def test_mentions_triage_categories(self):
        self.assertIn("Triage", self.text)

    def test_mentions_severity_model(self):
        self.assertIn("Severity", self.text)

    def test_mentions_safety_instructions(self):
        lower = self.text.lower()
        self.assertIn("safety", lower)

    def test_mentions_non_goals(self):
        self.assertIn("Non-Goal", self.text)

    def test_no_production_saas_claim(self):
        lower = self.text.lower()
        self.assertNotIn(
            "production saas ready",
            lower,
            "Report must not claim production SaaS readiness",
        )

    def test_no_tenant_isolation_claim(self):
        lower = self.text.lower()
        self.assertNotIn(
            "tenant isolation is implemented",
            lower,
            "Report must not claim tenant isolation is implemented",
        )

    def test_mentions_next_recommended_issue(self):
        self.assertIn("GL-183", self.text)

    def test_mentions_security_advisories(self):
        lower = self.text.lower()
        self.assertTrue(
            "security advisor" in lower or "advisories" in lower,
            "Report must mention GitHub Security Advisories for security-sensitive reports",
        )


class TestGL182ScopeGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.diff_files = _git_diff_files()

    def test_changed_files_within_allowed_scope(self):
        for path in self.diff_files:
            self.assertIn(
                path,
                ALLOWED_CHANGED_FILES,
                f"changed file '{path}' is outside allowed GL-182 scope",
            )

    def test_no_backend_src_changes(self):
        for path in self.diff_files:
            self.assertFalse(
                path.startswith("backend/src/"),
                f"backend/src change is forbidden: {path}",
            )

    def test_no_openapi_changes(self):
        for path in self.diff_files:
            self.assertFalse(
                "openapi" in path.lower(),
                f"OpenAPI change is forbidden: {path}",
            )

    def test_no_migration_changes(self):
        for path in self.diff_files:
            self.assertFalse(
                "migration" in path.lower(),
                f"Migration change is forbidden: {path}",
            )

    def test_no_dependency_manifest_changes(self):
        for path in self.diff_files:
            self.assertFalse(
                path in {"requirements.txt", "pyproject.toml", "setup.py", "Pipfile"},
                f"Dependency manifest change is forbidden: {path}",
            )

    def test_no_frontend_or_website_changes(self):
        for path in self.diff_files:
            self.assertFalse(
                path.startswith("frontend/") or path.startswith("website/"),
                f"Frontend/website change is forbidden: {path}",
            )

    def test_no_github_workflow_changes(self):
        for path in self.diff_files:
            self.assertFalse(
                path.startswith(".github/workflows/"),
                f"GitHub workflow change is forbidden: {path}",
            )

    def test_no_snapshot_publish_script_changes(self):
        for path in self.diff_files:
            self.assertFalse(
                "build-clean-public-snapshot" in path or "build_clean_public_snapshot" in path,
                f"Snapshot publish script change is forbidden: {path}",
            )


if __name__ == "__main__":
    unittest.main()
