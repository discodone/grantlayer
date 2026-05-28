"""
GL-153: LICENSE / CONTRIBUTING / SECURITY Decision Pack — Validation Test

Validates:
- LICENSE exists and contains Apache License 2.0 text and GrantLayer contributors
- CONTRIBUTING.md exists and contains required sections
- SECURITY.md exists and contains required sections
- JSON artifact exists, parses, and contains required boolean flags
- No AGENTS.md / llms.txt / agent manifest was added in GL-153
- Branch-scope guard (conditional on gl-153-license-contributing-security-decision branch)

Scope guard: this test must not change production backend code.
"""

import json
import os
import re
import subprocess
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LICENSE_PATH = os.path.join(REPO_ROOT, "LICENSE")
CONTRIBUTING_PATH = os.path.join(REPO_ROOT, "CONTRIBUTING.md")
SECURITY_PATH = os.path.join(REPO_ROOT, "SECURITY.md")
JSON_PATH = os.path.join(
    REPO_ROOT, "docs", "examples", "gl153", "license_contributing_security_decision.json"
)

EXPECTED_BRANCH = "gl-153-license-contributing-security-decision"

ALLOWED_FILES = {
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "docs/examples/gl153/license_contributing_security_decision.json",
    "backend/tests/test_gl153_license_contributing_security_decision.py",
    # Allowed only if intentionally touched
    "README.md",
    "docs/public_github_readiness_pack.md",
    "docs/first_developer_feedback_log.md",
}

FORBIDDEN_PATTERNS = [
    "backend/src/",
    "docs/openapi.yaml",
    "backend/src/migrations/",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "setup.py",
    "Pipfile",
    "poetry.lock",
    "frontend/",
    "website/",
    "design/",
    ".claude/",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_branch() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return result.stdout.strip()


def _changed_files() -> list:
    result = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# 1. File existence
# ---------------------------------------------------------------------------

class TestGl153FilesExist(unittest.TestCase):
    def test_license_exists(self):
        self.assertTrue(
            os.path.isfile(LICENSE_PATH),
            f"LICENSE must exist ({LICENSE_PATH})",
        )

    def test_contributing_exists(self):
        self.assertTrue(
            os.path.isfile(CONTRIBUTING_PATH),
            f"CONTRIBUTING.md must exist ({CONTRIBUTING_PATH})",
        )

    def test_security_exists(self):
        self.assertTrue(
            os.path.isfile(SECURITY_PATH),
            f"SECURITY.md must exist ({SECURITY_PATH})",
        )

    def test_json_artifact_exists(self):
        self.assertTrue(
            os.path.isfile(JSON_PATH),
            f"JSON artifact must exist ({JSON_PATH})",
        )


# ---------------------------------------------------------------------------
# 2. JSON parsing and required fields
# ---------------------------------------------------------------------------

class TestGl153JsonArtifact(unittest.TestCase):
    def setUp(self):
        with open(JSON_PATH, "r", encoding="utf-8") as fh:
            self.data = json.load(fh)

    def test_json_parses(self):
        self.assertIsInstance(self.data, dict)

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-153")

    def test_license_file_added_true(self):
        self.assertIs(self.data.get("license_file_added"), True)

    def test_license_is_apache_2_0(self):
        self.assertEqual(self.data.get("license"), "Apache-2.0")

    def test_contributing_file_added_true(self):
        self.assertIs(self.data.get("contributing_file_added"), True)

    def test_security_file_added_true(self):
        self.assertIs(self.data.get("security_file_added"), True)

    def test_notice_file_added_false(self):
        self.assertIs(self.data.get("notice_file_added"), False)

    def test_dco_recommended_true(self):
        self.assertIs(self.data.get("dco_recommended"), True)

    def test_cla_required_now_false(self):
        self.assertIs(self.data.get("cla_required_now"), False)

    def test_github_publication_performed_false(self):
        self.assertIs(self.data.get("github_publication_performed"), False)

    def test_git_remotes_changed_false(self):
        self.assertIs(self.data.get("git_remotes_changed"), False)

    def test_git_history_rewritten_false(self):
        self.assertIs(self.data.get("git_history_rewritten"), False)

    def test_secret_history_cleanup_performed_false(self):
        self.assertIs(self.data.get("secret_history_cleanup_performed"), False)

    def test_production_code_changed_false(self):
        self.assertIs(self.data.get("production_code_changed"), False)

    def test_backend_src_changed_false(self):
        self.assertIs(self.data.get("backend_src_changed"), False)

    def test_endpoint_api_behavior_changed_false(self):
        self.assertIs(self.data.get("endpoint_api_behavior_changed"), False)

    def test_openapi_changed_false(self):
        self.assertIs(self.data.get("openapi_changed"), False)

    def test_db_schema_changed_false(self):
        self.assertIs(self.data.get("db_schema_changed"), False)

    def test_dependencies_changed_false(self):
        self.assertIs(self.data.get("dependencies_changed"), False)

    def test_sdk_changed_false(self):
        self.assertIs(self.data.get("sdk_changed"), False)

    def test_langgraph_langchain_example_changed_false(self):
        self.assertIs(self.data.get("langgraph_langchain_example_changed"), False)

    def test_agent_entry_points_added_false(self):
        self.assertIs(self.data.get("agent_entry_points_added"), False)

    def test_github_issue_templates_added_false(self):
        self.assertIs(self.data.get("github_issue_templates_added"), False)

    def test_production_saas_ready_claimed_false(self):
        self.assertIs(self.data.get("production_saas_ready_claimed"), False)

    def test_tenant_isolation_claimed_implemented_false(self):
        self.assertIs(self.data.get("tenant_isolation_claimed_implemented"), False)

    def test_public_github_release_claimed_false(self):
        self.assertIs(self.data.get("public_github_release_claimed"), False)

    def test_uses_real_secrets_false(self):
        self.assertIs(self.data.get("uses_real_secrets"), False)

    def test_uses_real_customer_data_false(self):
        self.assertIs(self.data.get("uses_real_customer_data"), False)

    def test_includes_private_personal_data_false(self):
        self.assertIs(self.data.get("includes_private_personal_data"), False)


# ---------------------------------------------------------------------------
# 3. LICENSE content assertions
# ---------------------------------------------------------------------------

class TestGl153LicenseContent(unittest.TestCase):
    def setUp(self):
        with open(LICENSE_PATH, "r", encoding="utf-8") as fh:
            self.text = fh.read()
        self.lower = self.text.lower()

    def test_contains_apache_license(self):
        self.assertIn("apache license", self.lower)

    def test_contains_version_2_0(self):
        self.assertIn("version 2.0", self.lower)

    def test_contains_grantlayer_contributors(self):
        self.assertIn("grantlayer contributors", self.lower)

    def test_not_mit(self):
        # MIT license has a very specific short form; ensure it's not the active license
        self.assertNotIn("permission is hereby granted, free of charge", self.lower)

    def test_not_agpl(self):
        self.assertNotIn("gnu affero general public license", self.lower)

    def test_not_gpl(self):
        # Check for explicit GPL license text, not just the word "general"
        self.assertNotIn("gnu general public license", self.lower)


# ---------------------------------------------------------------------------
# 4. CONTRIBUTING.md content assertions
# ---------------------------------------------------------------------------

class TestGl153ContributingContent(unittest.TestCase):
    def setUp(self):
        with open(CONTRIBUTING_PATH, "r", encoding="utf-8") as fh:
            self.text = fh.read()
        self.lower = self.text.lower()

    def test_developer_preview_present(self):
        self.assertIn("developer preview", self.lower)

    def test_not_production_saas_present(self):
        self.assertTrue(
            "not production saas" in self.lower or "not a production saas" in self.lower,
            "CONTRIBUTING.md must state that this is not production SaaS",
        )

    def test_tenant_isolation_not_implemented(self):
        self.assertIn("tenant isolation", self.lower)
        self.assertIn("not implemented", self.lower)

    def test_no_real_secrets(self):
        self.assertTrue(
            "no real secrets" in self.lower or "do not use real secrets" in self.lower,
            "CONTRIBUTING.md must state no real secrets",
        )

    def test_no_real_customer_data(self):
        self.assertTrue(
            "no real customer data" in self.lower or "do not use real customer data" in self.lower,
            "CONTRIBUTING.md must state no real customer data",
        )

    def test_claude_directory_mentioned(self):
        self.assertIn(".claude/", self.text)

    def test_dco_mentioned(self):
        self.assertIn("dco", self.lower)

    def test_cla_not_required_now(self):
        self.assertTrue(
            "cla is not required now" in self.lower or "not required now" in self.lower,
            "CONTRIBUTING.md must state CLA is not required now",
        )

    def test_full_backend_suite_script(self):
        self.assertIn("scripts/run-full-backend-suite.sh", self.text)

    def test_gl154_referenced(self):
        self.assertIn("gl-154", self.lower)


# ---------------------------------------------------------------------------
# 5. SECURITY.md content assertions
# ---------------------------------------------------------------------------

class TestGl153SecurityContent(unittest.TestCase):
    def setUp(self):
        with open(SECURITY_PATH, "r", encoding="utf-8") as fh:
            self.text = fh.read()
        self.lower = self.text.lower()

    def test_developer_preview_present(self):
        self.assertIn("developer preview", self.lower)

    def test_github_security_advisories(self):
        self.assertIn("github security advisories", self.lower)

    def test_no_real_secrets(self):
        self.assertTrue(
            "no real secrets" in self.lower or "do not include real secrets" in self.lower,
            "SECURITY.md must state no real secrets",
        )

    def test_no_real_customer_data(self):
        self.assertTrue(
            "no real customer data" in self.lower or "do not include real customer data" in self.lower,
            "SECURITY.md must state no real customer data",
        )

    def test_tenant_isolation_not_implemented(self):
        self.assertIn("tenant isolation", self.lower)
        self.assertIn("not implemented", self.lower)

    def test_production_saas_not_claimed(self):
        self.assertTrue(
            "production saas readiness not claimed" in self.lower
            or "no production saas support guarantee" in self.lower
            or "production saas readiness not claimed" in self.lower,
            "SECURITY.md must include production SaaS caveat",
        )

    def test_public_release_not_approved(self):
        self.assertTrue(
            "public release not approved" in self.lower
            or "public github publication has not happened" in self.lower,
            "SECURITY.md must state public release not approved by GL-153",
        )


# ---------------------------------------------------------------------------
# 6. No agent entry points added in GL-153
# ---------------------------------------------------------------------------

class TestGl153NoAgentEntryPoints(unittest.TestCase):
    def test_no_agents_md(self):
        path = os.path.join(REPO_ROOT, "AGENTS.md")
        self.assertFalse(
            os.path.isfile(path),
            "AGENTS.md must not exist in GL-153 (deferred to GL-154)",
        )

    def test_no_llms_txt(self):
        path = os.path.join(REPO_ROOT, "llms.txt")
        self.assertFalse(
            os.path.isfile(path),
            "llms.txt must not exist in GL-153 (deferred to GL-154)",
        )

    def test_no_llms_full_txt(self):
        path = os.path.join(REPO_ROOT, "llms-full.txt")
        self.assertFalse(
            os.path.isfile(path),
            "llms-full.txt must not exist in GL-153 (deferred to GL-154)",
        )

    def test_no_agent_task_contract(self):
        path = os.path.join(REPO_ROOT, "docs", "agent_task_contract.md")
        self.assertFalse(
            os.path.isfile(path),
            "docs/agent_task_contract.md must not exist in GL-153 (deferred to GL-154)",
        )

    def test_no_agent_integration_manifest(self):
        path = os.path.join(REPO_ROOT, "docs", "agent_integration_manifest.json")
        self.assertFalse(
            os.path.isfile(path),
            "docs/agent_integration_manifest.json must not exist in GL-153 (deferred to GL-154)",
        )

    def test_no_agent_quickstart(self):
        path = os.path.join(REPO_ROOT, "docs", "agent_quickstart.md")
        self.assertFalse(
            os.path.isfile(path),
            "docs/agent_quickstart.md must not exist in GL-153 (deferred to GL-154)",
        )


# ---------------------------------------------------------------------------
# 7. Scope guard (branch-specific)
# ---------------------------------------------------------------------------

class TestGl153ScopeGuard(unittest.TestCase):
    """Branch-specific diff assertions. Skipped when not on the GL-153 branch."""

    def _current_branch(self) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        return result.stdout.strip()

    def _changed_files(self) -> list:
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def setUp(self):
        self.branch = self._current_branch()
        if self.branch != EXPECTED_BRANCH:
            self.skipTest(
                f"Scope guard skipped: not on {EXPECTED_BRANCH} (current: {self.branch})"
            )
        self.changed = self._changed_files()

    def test_no_backend_src_changes(self):
        violations = [f for f in self.changed if f.startswith("backend/src/")]
        self.assertEqual(violations, [], f"backend/src/ must not be modified: {violations}")

    def test_no_openapi_changes(self):
        violations = [f for f in self.changed if f == "docs/openapi.yaml"]
        self.assertEqual(violations, [], "docs/openapi.yaml must not be modified")

    def test_no_migration_changes(self):
        violations = [f for f in self.changed if f.startswith("backend/src/migrations/")]
        self.assertEqual(violations, [], f"Migrations must not be modified: {violations}")

    def test_no_dependency_file_changes(self):
        dep_files = {
            "requirements.txt",
            "requirements-dev.txt",
            "pyproject.toml",
            "setup.py",
            "Pipfile",
            "poetry.lock",
        }
        violations = [f for f in self.changed if f in dep_files]
        self.assertEqual(violations, [], f"Dependency files must not be modified: {violations}")

    def test_no_frontend_website_design_changes(self):
        violations = [
            f for f in self.changed
            if any(f.startswith(prefix) for prefix in ("frontend/", "website/", "design/"))
        ]
        self.assertEqual(
            violations, [], f"Frontend/website/design files must not be modified: {violations}"
        )

    def test_no_claude_config_changes(self):
        violations = [f for f in self.changed if f.startswith(".claude/")]
        self.assertEqual(violations, [], f".claude/ files must not be modified: {violations}")

    def test_only_expected_files_changed(self):
        unexpected = [f for f in self.changed if f not in ALLOWED_FILES]
        self.assertEqual(
            unexpected,
            [],
            f"Unexpected files changed: {unexpected}. Allowed: {sorted(ALLOWED_FILES)}",
        )

    def test_no_forbidden_pattern_in_diff(self):
        for pattern in FORBIDDEN_PATTERNS:
            violations = [f for f in self.changed if pattern in f]
            self.assertEqual(
                violations,
                [],
                f"Forbidden pattern '{pattern}' found in changed files: {violations}",
            )

    def test_no_sdk_changes_unless_allowed(self):
        sdk_changes = [f for f in self.changed if f == "sdk/python/grantlayer_client.py"]
        self.assertEqual(
            sdk_changes,
            [],
            f"sdk/python/grantlayer_client.py must not change on GL-153: {sdk_changes}",
        )

    def test_no_langgraph_example_changes_unless_allowed(self):
        example_changes = [
            f
            for f in self.changed
            if f == "examples/langgraph_langchain/grantlayer_agent_example.py"
        ]
        self.assertEqual(
            example_changes,
            [],
            f"LangGraph example must not change on GL-153: {example_changes}",
        )

    def test_no_github_issue_templates(self):
        violations = [f for f in self.changed if f.startswith(".github/ISSUE_TEMPLATE/")]
        self.assertEqual(
            violations, [], f"GitHub issue templates must not be added on GL-153: {violations}"
        )

    def test_no_github_pr_template(self):
        violations = [f for f in self.changed if f == ".github/pull_request_template.md"]
        self.assertEqual(
            violations, [], f"GitHub PR template must not be added on GL-153: {violations}"
        )


if __name__ == "__main__":
    unittest.main()
