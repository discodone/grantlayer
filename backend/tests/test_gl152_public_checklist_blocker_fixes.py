"""
GL-152: Public Checklist Blocker Fixes — Validation Test

Validates:
- docs/ten_minute_quickstart.md exists and does not contain internal Forgejo clone URL
- docs/integration_guide.md exists and does not contain absolute home-server path
- .gitignore exists and contains .claude/
- .github/workflows/postgres-ci.yml contains ephemeral CI-only comment near test DB password
- JSON artifact exists, parses, and contains required boolean flags
- Branch-scope guard (conditional on gl-152-public-checklist-blocker-fixes branch)

Scope guard: this test must not change production backend code.
"""

import json
import os
import re
import subprocess
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QUICKSTART_PATH = os.path.join(REPO_ROOT, "docs", "ten_minute_quickstart.md")
INTEGRATION_PATH = os.path.join(REPO_ROOT, "docs", "integration_guide.md")
GITIGNORE_PATH = os.path.join(REPO_ROOT, ".gitignore")
POSTGRES_CI_PATH = os.path.join(REPO_ROOT, ".github", "workflows", "postgres-ci.yml")
JSON_PATH = os.path.join(
    REPO_ROOT, "docs", "examples", "gl152", "public_checklist_blocker_fixes.json"
)

EXPECTED_BRANCH = "gl-152-public-checklist-blocker-fixes"

ALLOWED_FILES = {
    "docs/ten_minute_quickstart.md",
    "docs/integration_guide.md",
    ".gitignore",
    ".github/workflows/postgres-ci.yml",
    "docs/examples/gl152/public_checklist_blocker_fixes.json",
    "backend/tests/test_gl152_public_checklist_blocker_fixes.py",
    # Allowed only if intentionally touched
    "README.md",
    "docs/public_github_readiness_pack.md",
    "docs/examples/gl151/public_readme_repo_metadata_polish.json",
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

class TestGl152FilesExist(unittest.TestCase):
    def test_quickstart_md_exists(self):
        self.assertTrue(
            os.path.isfile(QUICKSTART_PATH),
            f"docs/ten_minute_quickstart.md must exist ({QUICKSTART_PATH})",
        )

    def test_integration_guide_md_exists(self):
        self.assertTrue(
            os.path.isfile(INTEGRATION_PATH),
            f"docs/integration_guide.md must exist ({INTEGRATION_PATH})",
        )

    def test_gitignore_exists(self):
        self.assertTrue(
            os.path.isfile(GITIGNORE_PATH),
            f".gitignore must exist ({GITIGNORE_PATH})",
        )

    def test_postgres_ci_yml_exists_if_repo_has_workflows(self):
        # If the repo has .github/workflows, the file should exist
        workflows_dir = os.path.join(REPO_ROOT, ".github", "workflows")
        if os.path.isdir(workflows_dir):
            self.assertTrue(
                os.path.isfile(POSTGRES_CI_PATH),
                f".github/workflows/postgres-ci.yml must exist when .github/workflows dir is present",
            )

    def test_json_artifact_exists(self):
        self.assertTrue(
            os.path.isfile(JSON_PATH),
            f"JSON artifact must exist ({JSON_PATH})",
        )


# ---------------------------------------------------------------------------
# 2. JSON parsing and required fields
# ---------------------------------------------------------------------------

class TestGl152JsonArtifact(unittest.TestCase):
    def setUp(self):
        with open(JSON_PATH, "r", encoding="utf-8") as fh:
            self.data = json.load(fh)

    def test_json_parses(self):
        self.assertIsInstance(self.data, dict)

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-152")

    def test_checklist_blocker_fixes_created_true(self):
        self.assertIs(self.data.get("checklist_blocker_fixes_created"), True)

    def test_internal_forgejo_clone_url_removed_or_replaced_true(self):
        self.assertIs(self.data.get("internal_forgejo_clone_url_removed_or_replaced"), True)

    def test_absolute_home_server_path_removed_or_replaced_true(self):
        self.assertIs(self.data.get("absolute_home_server_path_removed_or_replaced"), True)

    def test_claude_directory_ignored_true(self):
        self.assertIs(self.data.get("claude_directory_ignored"), True)

    def test_ci_test_password_marked_ephemeral_true(self):
        self.assertIs(self.data.get("ci_test_password_marked_ephemeral"), True)

    def test_github_publication_performed_false(self):
        self.assertIs(self.data.get("github_publication_performed"), False)

    def test_git_remotes_changed_false(self):
        self.assertIs(self.data.get("git_remotes_changed"), False)

    def test_git_history_rewritten_false(self):
        self.assertIs(self.data.get("git_history_rewritten"), False)

    def test_secret_history_cleanup_performed_false(self):
        self.assertIs(self.data.get("secret_history_cleanup_performed"), False)

    def test_license_file_added_false(self):
        self.assertIs(self.data.get("license_file_added"), False)

    def test_contributing_file_added_false(self):
        self.assertIs(self.data.get("contributing_file_added"), False)

    def test_security_file_added_false(self):
        self.assertIs(self.data.get("security_file_added"), False)

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


# ---------------------------------------------------------------------------
# 3. Content assertions
# ---------------------------------------------------------------------------

class TestGl152QuickstartContent(unittest.TestCase):
    def setUp(self):
        with open(QUICKSTART_PATH, "r", encoding="utf-8") as fh:
            self.text = fh.read()

    def test_no_internal_forgejo_url(self):
        self.assertNotIn(
            "forge.hofercloud.eu/toni/grantlayer-mvp.git",
            self.text,
            "Quickstart must not contain internal Forgejo clone URL",
        )

    def test_contains_public_safe_placeholder(self):
        self.assertIn(
            "github.com/<ORG_OR_USER>/grantlayer-mvp.git",
            self.text,
            "Quickstart must contain public-safe GitHub placeholder",
        )


class TestGl152IntegrationGuideContent(unittest.TestCase):
    def setUp(self):
        with open(INTEGRATION_PATH, "r", encoding="utf-8") as fh:
            self.text = fh.read()

    def test_no_absolute_home_server_path(self):
        self.assertNotIn(
            "/home/adminuser/projects/grantlayer-mvp",
            self.text,
            "Integration guide must not contain absolute home-server path",
        )


class TestGl152GitignoreContent(unittest.TestCase):
    def setUp(self):
        with open(GITIGNORE_PATH, "r", encoding="utf-8") as fh:
            self.text = fh.read()

    def test_contains_claude_directory(self):
        self.assertIn(
            ".claude/",
            self.text,
            ".gitignore must contain .claude/",
        )


class TestGl152PostgresCiContent(unittest.TestCase):
    def setUp(self):
        if os.path.isfile(POSTGRES_CI_PATH):
            with open(POSTGRES_CI_PATH, "r", encoding="utf-8") as fh:
                self.text = fh.read()
        else:
            self.text = ""

    def test_ephemeral_comment_near_password(self):
        if not self.text:
            self.skipTest("postgres-ci.yml not present")
        # The workflow contains a literal password; verify comment exists
        if "grantlayer_test_password" not in self.text:
            self.skipTest("No literal test password in workflow")
        self.assertTrue(
            "ephemeral" in self.text.lower()
            and "ci-only" in self.text.lower()
            and "not a production secret" in self.text.lower(),
            "Workflow must contain explicit ephemeral CI-only comment near test DB password",
        )


# ---------------------------------------------------------------------------
# 4. No public overclaims introduced
# ---------------------------------------------------------------------------

class TestGl152NoOverclaims(unittest.TestCase):
    def setUp(self):
        paths = [QUICKSTART_PATH, INTEGRATION_PATH]
        self.combined = ""
        for p in paths:
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as fh:
                    self.combined += fh.read() + "\n"
        self.lower = self.combined.lower()

    def test_no_production_saas_readiness_claim(self):
        # Allow negated forms; block standalone overclaims
        for m in re.finditer(r"production saas ready", self.lower):
            start = max(0, m.start() - 80)
            end = min(len(self.lower), m.end() + 80)
            context = self.lower[start:end]
            if any(word in context for word in ["not", "no ", "never"]):
                continue
            self.fail(
                f"Un-negated 'production SaaS ready' overclaim in context: ...{context}..."
            )

    def test_no_tenant_isolation_implemented_claim(self):
        for m in re.finditer(r"tenant isolation implemented", self.lower):
            start = max(0, m.start() - 80)
            end = min(len(self.lower), m.end() + 80)
            context = self.lower[start:end]
            if any(word in context for word in ["not", "no ", "never"]):
                continue
            self.fail(
                f"Un-negated 'tenant isolation implemented' overclaim in context: ...{context}..."
            )

    def test_no_public_github_release_completed_claim(self):
        for m in re.finditer(r"public github release completed", self.lower):
            start = max(0, m.start() - 80)
            end = min(len(self.lower), m.end() + 80)
            context = self.lower[start:end]
            if any(word in context for word in ["not", "no ", "never"]):
                continue
            self.fail(
                f"Un-negated 'public GitHub release completed' overclaim in context: ...{context}..."
            )


# ---------------------------------------------------------------------------
# 5. Scope guard (branch-specific)
# ---------------------------------------------------------------------------

class TestGl152ScopeGuard(unittest.TestCase):
    """Branch-specific diff assertions. Skipped when not on the GL-152 branch."""

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
            f"sdk/python/grantlayer_client.py must not change on GL-152: {sdk_changes}",
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
            f"LangGraph example must not change on GL-152: {example_changes}",
        )


if __name__ == "__main__":
    unittest.main()
