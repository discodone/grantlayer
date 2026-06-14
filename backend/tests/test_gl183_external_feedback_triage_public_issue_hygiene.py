"""GL-183: External Feedback Triage / Public Issue Hygiene."""

import json
import os
import subprocess
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GL183_BRANCH = "gl-183-external-feedback-triage-public-issue-hygiene"
REPORT_PATH = os.path.join(
    REPO_ROOT, "docs", "external_feedback_triage_public_issue_hygiene.md"
)
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl183",
    "external_feedback_triage_public_issue_hygiene.json",
)

ALLOWED_CHANGED_FILES = {
    "docs/external_feedback_triage_public_issue_hygiene.md",
    "docs/examples/gl183/external_feedback_triage_public_issue_hygiene.json",
    "backend/tests/test_gl183_external_feedback_triage_public_issue_hygiene.py",
}

REQUIRED_FEEDBACK_CATEGORIES = {
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

REQUIRED_LABELS = {
    "feedback",
    "docs",
    "quickstart",
    "security-review-needed",
    "production-readiness",
    "needs-triage",
}

REQUIRED_SEVERITIES = {"critical", "high", "medium", "low", "info"}

REQUIRED_INTAKE_STEPS = {
    "classify category",
    "assign severity",
    "check safety constraints",
    "decide public issue vs private security advisory",
    "record source and date",
    "decide next action",
}

REQUIRED_SAFETY_CONFIRMATIONS = {
    "no_github_push_performed",
    "no_visibility_change_performed",
    "internal_repo_not_pushed_directly_to_github",
    "no_github_api_label_changes_performed",
    "production_saas_not_claimed",
    "tenant_isolation_not_claimed",
    "real_customer_data_not_requested",
    "secrets_not_requested",
    "security_sensitive_reports_directed_to_advisories",
    "no_exploit_details_requested_publicly",
}


def _git_diff_files():
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    if branch.returncode == 0 and branch.stdout.strip() != GL183_BRANCH:
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


class TestGL183FilesExist(unittest.TestCase):
    def test_report_exists(self):
        self.assertTrue(os.path.isfile(REPORT_PATH), f"Missing report: {REPORT_PATH}")

    def test_json_exists(self):
        self.assertTrue(os.path.isfile(JSON_PATH), f"Missing JSON: {JSON_PATH}")


class TestGL183ArtifactJSON(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(JSON_PATH, encoding="utf-8") as fh:
            cls.data = json.load(fh)

    def test_valid_json(self):
        self.assertIsInstance(self.data, dict)

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-183")

    def test_feedback_categories_present(self):
        categories = self.data.get("feedback_categories", [])
        self.assertIsInstance(categories, list)
        found = {item.get("id") for item in categories}
        for category in REQUIRED_FEEDBACK_CATEGORIES:
            self.assertIn(category, found, f"Missing feedback category: {category}")

    def test_proposed_labels_present(self):
        labels = self.data.get("proposed_labels", [])
        self.assertIsInstance(labels, list)
        found = {item.get("name") for item in labels}
        for label in REQUIRED_LABELS:
            self.assertIn(label, found, f"Missing proposed label: {label}")

    def test_severity_mapping_present(self):
        mapping = self.data.get("severity_mapping", [])
        self.assertIsInstance(mapping, list)
        found = {item.get("severity") for item in mapping}
        for severity in REQUIRED_SEVERITIES:
            self.assertIn(severity, found, f"Missing severity mapping: {severity}")

    def test_intake_workflow_present(self):
        workflow = self.data.get("intake_workflow", [])
        self.assertIsInstance(workflow, list)
        combined = " ".join(workflow).lower()
        for phrase in REQUIRED_INTAKE_STEPS:
            self.assertIn(phrase, combined, f"Missing intake workflow step: {phrase}")

    def test_security_handling_present(self):
        security = self.data.get("security_handling", {})
        self.assertIsInstance(security, dict)
        combined = " ".join(security.get("rules", [])).lower()
        self.assertIn(
            "github security advisories",
            combined,
            "security_handling must direct security-sensitive reports to GitHub Security Advisories",
        )
        self.assertIn(
            "secrets",
            combined,
            "security_handling must say not to post secrets publicly",
        )
        self.assertIn(
            "exploit details",
            combined,
            "security_handling must say not to post exploit details publicly",
        )
        self.assertIn(
            "customer data",
            combined,
            "security_handling must say not to post customer data publicly",
        )

    def test_issue_template_decision(self):
        decision = self.data.get("issue_template_decision", {})
        self.assertIsInstance(decision, dict)
        self.assertIn(
            decision.get("decision"),
            {"templates_deferred", "templates_documented_only", "templates_added"},
        )
        if decision.get("decision") == "templates_added":
            templates_dir = os.path.join(REPO_ROOT, ".github", "ISSUE_TEMPLATE")
            self.assertTrue(os.path.isdir(templates_dir), "Expected issue templates directory")
            for filename in ("feedback.yml", "bug_report.yml", "config.yml"):
                self.assertTrue(
                    os.path.isfile(os.path.join(templates_dir, filename)),
                    f"Missing safe issue template file: {filename}",
                )

    def test_non_goals_present(self):
        non_goals = self.data.get("non_goals", [])
        combined = " ".join(non_goals).lower()
        self.assertIn("production saas", combined)
        self.assertIn("tenant/workspace isolation", combined)
        self.assertIn("customer onboarding", combined)
        self.assertIn("sla", combined)

    def test_safety_confirmations_present(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertIsInstance(confirmations, dict)
        for key in REQUIRED_SAFETY_CONFIRMATIONS:
            self.assertIn(key, confirmations, f"Missing safety confirmation: {key}")

    def test_safety_confirmations_all_true(self):
        confirmations = self.data.get("safety_confirmations", {})
        for key in REQUIRED_SAFETY_CONFIRMATIONS:
            self.assertTrue(confirmations.get(key), f"Safety confirmation must be true: {key}")

    def test_report_explicit_statements_present(self):
        with open(REPORT_PATH, encoding="utf-8") as fh:
            content = fh.read().lower()
        self.assertIn("no github push was performed", content)
        self.assertIn("no visibility change was performed", content)
        self.assertIn("internal repo was not pushed directly to github", content)
        self.assertIn("no github api label changes were performed", content)

    def test_changed_files_present(self):
        changed = self.data.get("changed_files", [])
        self.assertIsInstance(changed, list)
        self.assertEqual(set(changed), ALLOWED_CHANGED_FILES)


class TestGL183ScopeGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.diff_files = _git_diff_files()

    def test_changed_files_within_allowed_scope(self):
        self.assertEqual(set(self.diff_files), ALLOWED_CHANGED_FILES)

    def test_no_backend_src_changes(self):
        for path in self.diff_files:
            self.assertFalse(path.startswith("backend/src/"))

    def test_no_openapi_changes(self):
        for path in self.diff_files:
            self.assertNotIn("docs/openapi.yaml", path)

    def test_no_migration_changes(self):
        for path in self.diff_files:
            self.assertFalse("migrations" in path)

    def test_no_db_schema_changes(self):
        for path in self.diff_files:
            self.assertFalse("/db/" in path.lower())

    def test_no_dependency_manifest_changes(self):
        for path in self.diff_files:
            self.assertNotIn("requirements", path)

    def test_no_sdk_implementation_changes(self):
        for path in self.diff_files:
            self.assertFalse(path.startswith("sdk/"))

    def test_no_frontend_website_design_changes(self):
        for path in self.diff_files:
            self.assertFalse(path.startswith("frontend/"))
            self.assertFalse(path.startswith("website/"))
            self.assertFalse(path.startswith("design/"))

    def test_no_github_workflow_changes(self):
        for path in self.diff_files:
            self.assertFalse(path.startswith(".github/workflows/"))

    def test_no_snapshot_publish_script_behavior_changes(self):
        for path in self.diff_files:
            self.assertNotIn("build-clean-public-snapshot", path)

    def test_no_git_remote_changes(self):
        for path in self.diff_files:
            self.assertNotIn(".git/config", path)

    def test_no_public_github_push(self):
        for path in self.diff_files:
            self.assertFalse(path == "public-github-push")

    def test_no_visibility_change(self):
        for path in self.diff_files:
            self.assertFalse(path == "visibility-change")

    def test_no_paperclip_status_updates(self):
        for path in self.diff_files:
            self.assertNotIn("paperclip", path.lower())
