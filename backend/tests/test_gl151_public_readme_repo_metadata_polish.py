"""
GL-151: Public README / Repo Metadata Polish — Validation Test

Validates:
- README.md exists and contains required public-facing sections
- JSON artifact exists, parses, and contains required boolean flags
- README links to developer entry path docs
- README includes explicit safety caveats
- README does not overclaim production readiness, tenant isolation, or public release
- Branch-scope guard (conditional on gl-151-public-readme-repo-metadata-polish branch)

Scope guard: this test must not change production backend code.
"""

import json
import os
import re
import subprocess
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
README_PATH = os.path.join(REPO_ROOT, "README.md")
JSON_PATH = os.path.join(
    REPO_ROOT, "docs", "examples", "gl151", "public_readme_repo_metadata_polish.json"
)

EXPECTED_BRANCH = "gl-151-public-readme-repo-metadata-polish"

ALLOWED_FILES = {
    "README.md",
    "docs/examples/gl151/public_readme_repo_metadata_polish.json",
    "backend/tests/test_gl151_public_readme_repo_metadata_polish.py",
    # Allowed only if intentionally touched
    "docs/public_github_readiness_pack.md",
    "docs/first_developer_feedback_log.md",
    "docs/ten_minute_quickstart.md",
    "sdk/python/README.md",
    "docs/langgraph_langchain_integration_example.md",
    "docs/key_hygiene.md",
    "docs/dependency_manifest.md",
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
# 1. Artifact existence
# ---------------------------------------------------------------------------

class TestGl151FilesExist(unittest.TestCase):
    def test_readme_md_exists(self):
        self.assertTrue(
            os.path.isfile(README_PATH),
            f"README.md must exist ({README_PATH})",
        )

    def test_json_artifact_exists(self):
        self.assertTrue(
            os.path.isfile(JSON_PATH),
            f"JSON artifact must exist ({JSON_PATH})",
        )


# ---------------------------------------------------------------------------
# 2. JSON parsing and required fields
# ---------------------------------------------------------------------------

class TestGl151JsonArtifact(unittest.TestCase):
    def setUp(self):
        with open(JSON_PATH, "r", encoding="utf-8") as fh:
            self.data = json.load(fh)

    def test_json_parses(self):
        self.assertIsInstance(self.data, dict)

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-151")

    def test_readme_polished_true(self):
        self.assertIs(self.data.get("readme_polished"), True)

    def test_repo_metadata_guidance_added_true(self):
        self.assertIs(self.data.get("repo_metadata_guidance_added"), True)

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

    def test_license_file_added_false(self):
        self.assertIs(self.data.get("license_file_added"), False)

    def test_contributing_file_added_false(self):
        self.assertIs(self.data.get("contributing_file_added"), False)

    def test_security_file_added_false(self):
        self.assertIs(self.data.get("security_file_added"), False)

    def test_apache_2_0_recommended_true(self):
        self.assertIs(self.data.get("apache_2_0_recommended"), True)

    def test_production_saas_ready_claimed_false(self):
        self.assertIs(self.data.get("production_saas_ready_claimed"), False)

    def test_tenant_isolation_claimed_implemented_false(self):
        self.assertIs(self.data.get("tenant_isolation_claimed_implemented"), False)

    def test_public_github_release_claimed_false(self):
        self.assertIs(self.data.get("public_github_release_claimed"), False)

    def test_real_external_feedback_claimed_false(self):
        self.assertIs(self.data.get("real_external_feedback_claimed"), False)

    def test_uses_real_secrets_false(self):
        self.assertIs(self.data.get("uses_real_secrets"), False)

    def test_uses_real_customer_data_false(self):
        self.assertIs(self.data.get("uses_real_customer_data"), False)


# ---------------------------------------------------------------------------
# 3. README required sections and links
# ---------------------------------------------------------------------------

class TestGl151ReadmeSections(unittest.TestCase):
    def setUp(self):
        with open(README_PATH, "r", encoding="utf-8") as fh:
            self.text = fh.read()
        self.lower = self.text.lower()

    def test_readme_has_status_section(self):
        self.assertIn("status", self.lower)

    def test_readme_has_developer_entry_path_section(self):
        self.assertIn("developer entry path", self.lower)

    def test_readme_has_safety_and_limitations_section(self):
        self.assertIn("safety and limitations", self.lower)

    def test_readme_has_license_posture_section(self):
        self.assertIn("license posture", self.lower)

    def test_readme_has_contribution_security_posture_section(self):
        self.assertIn("contribution and security posture", self.lower)

    def test_readme_has_suggested_repo_metadata_section(self):
        self.assertIn("suggested repository metadata", self.lower)

    def test_readme_has_next_steps_section(self):
        self.assertIn("next steps", self.lower)


class TestGl151ReadmeLinks(unittest.TestCase):
    def setUp(self):
        with open(README_PATH, "r", encoding="utf-8") as fh:
            self.text = fh.read()
        self.lower = self.text.lower()

    def test_links_to_quickstart(self):
        self.assertIn("docs/ten_minute_quickstart.md", self.text)

    def test_links_to_sdk_readme(self):
        self.assertIn("sdk/python/README.md", self.text)

    def test_links_to_langgraph_example(self):
        self.assertIn("docs/langgraph_langchain_integration_example.md", self.text)

    def test_links_to_public_github_readiness_pack(self):
        self.assertIn("docs/public_github_readiness_pack.md", self.text)

    def test_links_to_first_developer_feedback_log(self):
        self.assertIn("docs/first_developer_feedback_log.md", self.text)


class TestGl151ReadmeSafetyStatements(unittest.TestCase):
    def setUp(self):
        with open(README_PATH, "r", encoding="utf-8") as fh:
            self.text = fh.read()
        self.lower = self.text.lower()

    def test_developer_preview_posture(self):
        self.assertIn("developer preview", self.lower)

    def test_local_first_or_local_evaluation(self):
        self.assertTrue(
            "local evaluation" in self.lower or "local-first" in self.lower,
            "README must mention local evaluation or local-first",
        )

    def test_apache_license_2_0_direction(self):
        self.assertTrue(
            "apache license 2.0" in self.lower or "apache-2.0" in self.lower,
            "README must include Apache License 2.0 direction",
        )

    def test_gl152_referenced(self):
        self.assertIn("gl-152", self.lower)

    def test_gl153_referenced(self):
        self.assertIn("gl-153", self.lower)

    def test_gl154_referenced(self):
        self.assertIn("gl-154", self.lower)

    def test_production_saas_not_claimed(self):
        self.assertTrue(
            "production saas readiness is not claimed" in self.lower,
            "README must explicitly state production SaaS readiness is not claimed",
        )

    def test_tenant_isolation_not_implemented(self):
        self.assertTrue(
            "tenant isolation is not implemented" in self.lower,
            "README must explicitly state tenant isolation is not implemented",
        )

    def test_public_github_release_not_happened(self):
        self.assertTrue(
            "public github release/publication has not happened" in self.lower
            or "public github release" in self.lower and "not performed" in self.lower,
            "README must explicitly state public GitHub release has not happened",
        )

    def test_no_real_secrets(self):
        self.assertTrue(
            "do not use real secrets" in self.lower
            or "no real secrets" in self.lower,
            "README must state no real secrets",
        )

    def test_no_real_customer_data(self):
        self.assertTrue(
            "do not use real customer data" in self.lower
            or "no real customer data" in self.lower,
            "README must state no real customer data",
        )


class TestGl151ReadmeNoOverclaims(unittest.TestCase):
    def setUp(self):
        with open(README_PATH, "r", encoding="utf-8") as fh:
            self.text = fh.read()
        self.lower = self.text.lower()

    def test_no_production_ready_saas_phrase(self):
        # Allow negated forms; block standalone overclaims
        standalone = re.compile(r"production-ready saas")
        matches = standalone.findall(self.lower)
        # If found, verify it is within a clear caveat/negation
        for m in re.finditer(r"production-ready saas", self.lower):
            start = max(0, m.start() - 80)
            end = min(len(self.lower), m.end() + 80)
            context = self.lower[start:end]
            # Accept if context contains clear negation words
            if any(word in context for word in ["not", "no ", "never"]):
                continue
            self.fail(
                f"README contains un-negated 'production-ready SaaS' overclaim in context: ...{context}..."
            )

    def test_no_tenant_isolation_implemented_phrase(self):
        standalone = re.compile(r"tenant isolation implemented")
        for m in re.finditer(r"tenant isolation implemented", self.lower):
            start = max(0, m.start() - 80)
            end = min(len(self.lower), m.end() + 80)
            context = self.lower[start:end]
            if any(word in context for word in ["not", "no ", "never"]):
                continue
            self.fail(
                f"README contains un-negated 'tenant isolation implemented' overclaim in context: ...{context}..."
            )

    def test_no_public_github_release_completed_phrase(self):
        standalone = re.compile(r"public github release completed")
        for m in re.finditer(r"public github release completed", self.lower):
            start = max(0, m.start() - 80)
            end = min(len(self.lower), m.end() + 80)
            context = self.lower[start:end]
            if any(word in context for word in ["not", "no ", "never"]):
                continue
            self.fail(
                f"README contains un-negated 'public GitHub release completed' overclaim in context: ...{context}..."
            )


# ---------------------------------------------------------------------------
# 4. Scope guard (branch-specific)
# ---------------------------------------------------------------------------

class TestGl151ScopeGuard(unittest.TestCase):
    """Branch-specific diff assertions. Skipped when not on the GL-151 branch."""

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
            f"sdk/python/grantlayer_client.py must not change on GL-151: {sdk_changes}",
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
            f"LangGraph example must not change on GL-151: {example_changes}",
        )


if __name__ == "__main__":
    unittest.main()
