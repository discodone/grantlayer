"""
GL-156: GitHub Issue Templates / Feedback Templates — validation test.

Validates that all issue templates, PR template, config, JSON artifact, and
safety constraints are in place. Does NOT call GitHub API or create live issues.
"""
import json
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

GL156_BRANCH = "gl-156-github-issue-feedback-templates"

EXPECTED_FILES = [
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/agent_task_request.yml",
    ".github/ISSUE_TEMPLATE/developer_feedback.yml",
    ".github/ISSUE_TEMPLATE/documentation_feedback.yml",
    ".github/ISSUE_TEMPLATE/security_report.md",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/pull_request_template.md",
    "docs/examples/gl156/github_issue_feedback_templates.json",
]

JSON_ARTIFACT = "docs/examples/gl156/github_issue_feedback_templates.json"

YAML_FORM_FILES = [
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/agent_task_request.yml",
    ".github/ISSUE_TEMPLATE/developer_feedback.yml",
    ".github/ISSUE_TEMPLATE/documentation_feedback.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
]

FORBIDDEN_PRODUCTION_FILES = [
    "backend/src/",
    "docs/openapi.yaml",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "setup.py",
    "Pipfile",
    "poetry.lock",
    "sdk/python/grantlayer_client.py",
    "examples/langgraph_langchain/grantlayer_agent_example.py",
    "examples/agents/evidence_review_agent.py",
    "examples/agents/approval_guardrail_agent.py",
    "examples/agents/audit_export_agent.py",
    "examples/agents/policy_check_agent.py",
    ".claude/",
]

INTERNAL_PATHS = [
    "forge.hofercloud.eu",
    "/home/adminuser",
    "terminal.hofercloud.eu",
    "192.168.2.",
    "100.109.111.",
]


def _repo_path(*parts):
    return os.path.join(REPO_ROOT, *parts)


def _read(rel_path):
    with open(_repo_path(rel_path), "r", encoding="utf-8") as f:
        return f.read()


def _current_branch():
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _branch_diff_files():
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return None
        return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except Exception:
        return None


try:
    import yaml as _yaml

    def _load_yaml(text):
        return _yaml.safe_load(text)

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

    def _load_yaml(text):
        return None


class TestGL156FilesExist(unittest.TestCase):
    def test_all_expected_files_exist(self):
        for rel in EXPECTED_FILES:
            with self.subTest(file=rel):
                self.assertTrue(
                    os.path.isfile(_repo_path(rel)),
                    f"Expected file missing: {rel}",
                )

    def test_test_file_itself_exists(self):
        self.assertTrue(
            os.path.isfile(
                _repo_path("backend/tests/test_gl156_github_issue_feedback_templates.py")
            )
        )


class TestGL156JsonArtifact(unittest.TestCase):
    def setUp(self):
        with open(_repo_path(JSON_ARTIFACT), "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def test_issue_id(self):
        self.assertEqual(self.data["issue_id"], "GL-156")

    def test_template_booleans_true(self):
        true_keys = [
            "github_issue_templates_added",
            "bug_report_template_added",
            "feature_request_template_added",
            "agent_task_request_template_added",
            "developer_feedback_template_added",
            "documentation_feedback_template_added",
            "security_report_template_added",
            "issue_template_config_added",
            "pull_request_template_added",
        ]
        for key in true_keys:
            with self.subTest(key=key):
                self.assertIs(self.data[key], True, f"{key} must be true")

    def test_forbidden_action_booleans_false(self):
        false_keys = [
            "github_publication_performed",
            "live_github_issues_created",
            "github_api_called",
            "git_remotes_changed",
            "git_history_rewritten",
            "secret_history_cleanup_performed",
            "production_code_changed",
            "backend_src_changed",
            "endpoint_api_behavior_changed",
            "openapi_changed",
            "db_schema_changed",
            "dependencies_changed",
            "sdk_changed",
            "langgraph_langchain_code_changed",
            "runtime_agent_examples_changed",
            "production_saas_ready_claimed",
            "tenant_isolation_claimed_implemented",
            "public_github_release_claimed",
            "uses_real_secrets",
            "uses_real_customer_data",
            "includes_private_personal_data",
        ]
        for key in false_keys:
            with self.subTest(key=key):
                self.assertIs(self.data[key], False, f"{key} must be false")

    def test_next_issue(self):
        self.assertEqual(
            self.data["next_issue"],
            "GL-157 Public Secret / Sensitive Data Scan Gate",
        )

    def test_templates_map_present(self):
        self.assertIn("templates", self.data)
        self.assertIsInstance(self.data["templates"], dict)

    def test_validation_gates_present(self):
        self.assertIn("validation_gates", self.data)
        self.assertIsInstance(self.data["validation_gates"], dict)


class TestGL156YamlForms(unittest.TestCase):
    def _content(self, rel):
        return _read(rel)

    def test_yaml_forms_parse(self):
        for rel in YAML_FORM_FILES:
            with self.subTest(file=rel):
                content = self._content(rel)
                if YAML_AVAILABLE:
                    parsed = _load_yaml(content)
                    self.assertIsNotNone(parsed, f"YAML parse returned None for {rel}")
                else:
                    # Basic structural check without PyYAML
                    self.assertGreater(len(content.strip()), 0, f"{rel} is empty")

    def test_yaml_forms_have_name_field(self):
        for rel in YAML_FORM_FILES:
            if rel.endswith("config.yml"):
                continue
            with self.subTest(file=rel):
                content = self._content(rel)
                self.assertIn("name:", content, f"{rel} missing 'name:' field")

    def test_yaml_forms_have_labels(self):
        labeled_forms = [
            ".github/ISSUE_TEMPLATE/bug_report.yml",
            ".github/ISSUE_TEMPLATE/feature_request.yml",
            ".github/ISSUE_TEMPLATE/agent_task_request.yml",
            ".github/ISSUE_TEMPLATE/developer_feedback.yml",
            ".github/ISSUE_TEMPLATE/documentation_feedback.yml",
        ]
        for rel in labeled_forms:
            with self.subTest(file=rel):
                content = self._content(rel)
                self.assertIn("labels:", content, f"{rel} missing 'labels:' field")


class TestGL156SafetyPhrases(unittest.TestCase):
    """All templates must contain required safety phrases."""

    SAFETY_PHRASES = [
        "no real secrets",
        "no real customer data",
        "no private personal data",
        "not production SaaS",
        "tenant isolation is not implemented",
    ]

    def _all_template_content(self):
        parts = []
        for rel in EXPECTED_FILES:
            if os.path.isfile(_repo_path(rel)):
                parts.append(_read(rel).lower())
        return "\n".join(parts)

    def test_safety_phrases_present_across_templates(self):
        combined = self._all_template_content()
        for phrase in self.SAFETY_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(
                    phrase.lower(),
                    combined,
                    f"Safety phrase not found in any template: '{phrase}'",
                )

    def test_bug_report_has_checklist(self):
        # Bug report uses "I did not include X" form per task spec;
        # check for the substantive data-safety phrases present in the file.
        content = _read(".github/ISSUE_TEMPLATE/bug_report.yml").lower()
        for phrase in ["real secrets", "real customer data", "private personal data"]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, content)

    def test_pull_request_template_safety(self):
        content = _read(".github/pull_request_template.md").lower()
        for phrase in ["no real secrets", "no real customer data", "no private personal data"]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, content)


class TestGL156AgentTaskRequestTemplate(unittest.TestCase):
    """agent_task_request.yml must reference required docs and include safety constraints."""

    def setUp(self):
        self.content = _read(".github/ISSUE_TEMPLATE/agent_task_request.yml")

    def test_references_agents_md(self):
        self.assertIn("AGENTS.md", self.content)

    def test_references_agent_task_contract(self):
        self.assertIn("docs/agent_task_contract.md", self.content)

    def test_references_agent_integration_manifest(self):
        self.assertIn("docs/agent_integration_manifest.json", self.content)

    def test_references_agent_quickstart(self):
        self.assertIn("docs/agent_quickstart.md", self.content)

    def test_references_claude_dir(self):
        self.assertIn(".claude/", self.content)

    def test_references_final_report(self):
        self.assertIn("final report", self.content.lower())

    def test_references_allowed_files(self):
        self.assertIn("allowed files", self.content.lower())

    def test_references_forbidden_files(self):
        self.assertIn("forbidden files", self.content.lower())

    def test_includes_agent_task_label(self):
        self.assertIn("agent-task", self.content)

    def test_branch_merge_separation(self):
        content_lower = self.content.lower()
        self.assertIn("branch", content_lower)
        self.assertIn("merge", content_lower)


class TestGL156SecurityReportTemplate(unittest.TestCase):
    def setUp(self):
        self.content = _read(".github/ISSUE_TEMPLATE/security_report.md")
        self.content_lower = self.content.lower()

    def test_do_not_open_public_issue(self):
        self.assertIn("do not open a public issue", self.content_lower)

    def test_references_security_md(self):
        self.assertIn("SECURITY.md", self.content)

    def test_references_github_security_advisories(self):
        self.assertIn("GitHub Security Advisories", self.content)

    def test_developer_preview_caveat(self):
        self.assertIn("developer preview", self.content_lower)

    def test_not_production_saas(self):
        self.assertIn("not production saas", self.content_lower)

    def test_tenant_isolation_caveat(self):
        self.assertIn("tenant isolation is not implemented", self.content_lower)


class TestGL156PullRequestTemplate(unittest.TestCase):
    def setUp(self):
        self.content = _read(".github/pull_request_template.md")
        self.content_lower = self.content.lower()

    def test_no_real_secrets(self):
        self.assertIn("no real secrets", self.content_lower)

    def test_no_real_customer_data(self):
        self.assertIn("no real customer data", self.content_lower)

    def test_no_internal_infrastructure_paths(self):
        self.assertIn("internal infrastructure paths", self.content_lower)

    def test_no_production_saas_claim(self):
        self.assertIn("production saas", self.content_lower)

    def test_no_tenant_isolation_claim(self):
        self.assertIn("tenant isolation", self.content_lower)

    def test_did_not_stage_claude_dir(self):
        self.assertIn(".claude/", self.content)

    def test_has_summary_section(self):
        self.assertIn("## Summary", self.content)

    def test_has_validation_section(self):
        self.assertIn("## Validation", self.content)

    def test_has_changed_files_section(self):
        self.assertIn("Changed files", self.content)

    def test_has_tests_run_section(self):
        self.assertIn("Tests run", self.content)

    def test_has_follow_up_issues(self):
        self.assertIn("Follow-up", self.content)


class TestGL156IssueTemplateConfig(unittest.TestCase):
    def setUp(self):
        self.content = _read(".github/ISSUE_TEMPLATE/config.yml")

    def test_blank_issues_disabled(self):
        self.assertIn("blank_issues_enabled: false", self.content)

    def test_has_security_contact_link(self):
        self.assertIn("SECURITY.md", self.content)

    def test_has_agent_task_contract_link(self):
        self.assertIn("agent_task_contract.md", self.content)

    def test_has_agent_quickstart_link(self):
        self.assertIn("agent_quickstart.md", self.content)


class TestGL156NoInternalPaths(unittest.TestCase):
    """No template file may contain internal infrastructure paths or real secrets."""

    def _all_content(self):
        parts = []
        for rel in EXPECTED_FILES:
            if os.path.isfile(_repo_path(rel)):
                parts.append(_read(rel))
        return "\n".join(parts)

    def test_no_internal_paths(self):
        combined = self._all_content()
        for path in INTERNAL_PATHS:
            with self.subTest(path=path):
                self.assertNotIn(
                    path,
                    combined,
                    f"Internal infrastructure path found in templates: '{path}'",
                )

    def test_no_token_like_secrets(self):
        combined = self._all_content()
        import re
        # Allow safe placeholder patterns like <token>, <api_key>, example, sk-xxx
        # Flag only realistic-looking secrets: long alphanumeric strings that look like real tokens
        # but not placeholder patterns
        suspicious = re.findall(
            r"\b(?:sk-[A-Za-z0-9]{20,}|xoxb-[A-Za-z0-9\-]{20,}|ghp_[A-Za-z0-9]{20,})\b",
            combined,
        )
        self.assertEqual(
            suspicious,
            [],
            f"Suspicious token-like values found in templates: {suspicious}",
        )


class TestGL156BranchScopeGuard(unittest.TestCase):
    """
    Branch-specific scope assertions.
    Skipped when not on the GL-156 branch (e.g. after merge to main).
    """

    def setUp(self):
        self.on_gl156_branch = _current_branch() == GL156_BRANCH
        if not self.on_gl156_branch:
            self.skipTest(
                f"Not on {GL156_BRANCH} — skipping branch-scope diff assertions."
            )

    def test_no_forbidden_files_in_diff(self):
        diff_files = _branch_diff_files()
        if diff_files is None:
            self.skipTest("Could not retrieve branch diff — skipping scope guard.")
        for changed in diff_files:
            for forbidden in FORBIDDEN_PRODUCTION_FILES:
                with self.subTest(changed=changed, forbidden=forbidden):
                    self.assertFalse(
                        changed.startswith(forbidden) or changed == forbidden.rstrip("/"),
                        f"Forbidden file changed: {changed} (matches pattern: {forbidden})",
                    )

    def test_no_openapi_in_diff(self):
        diff_files = _branch_diff_files()
        if diff_files is None:
            self.skipTest("Could not retrieve branch diff.")
        for f in diff_files:
            with self.subTest(file=f):
                self.assertNotIn("openapi", f.lower(), f"OpenAPI file changed: {f}")

    def test_no_migration_files_in_diff(self):
        diff_files = _branch_diff_files()
        if diff_files is None:
            self.skipTest("Could not retrieve branch diff.")
        for f in diff_files:
            with self.subTest(file=f):
                self.assertNotIn(
                    "migration", f.lower(), f"Migration file changed: {f}"
                )

    def test_no_frontend_or_website_in_diff(self):
        diff_files = _branch_diff_files()
        if diff_files is None:
            self.skipTest("Could not retrieve branch diff.")
        for f in diff_files:
            with self.subTest(file=f):
                self.assertFalse(
                    f.startswith("frontend/") or f.startswith("website/"),
                    f"Frontend/website file changed: {f}",
                )

    def test_no_claude_dir_in_diff(self):
        diff_files = _branch_diff_files()
        if diff_files is None:
            self.skipTest("Could not retrieve branch diff.")
        for f in diff_files:
            with self.subTest(file=f):
                self.assertFalse(
                    f.startswith(".claude/"),
                    f".claude/ file staged: {f} — must not be committed",
                )

    def test_expected_files_all_in_diff(self):
        diff_files = _branch_diff_files()
        if diff_files is None:
            self.skipTest("Could not retrieve branch diff.")
        if not diff_files:
            self.skipTest("Branch diff is empty (files not yet committed) — skipping.")
        for rel in EXPECTED_FILES:
            with self.subTest(file=rel):
                self.assertIn(
                    rel,
                    diff_files,
                    f"Expected file not in branch diff: {rel}",
                )


if __name__ == "__main__":
    unittest.main()
