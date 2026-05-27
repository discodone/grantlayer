"""
GL-150: First Developer Feedback Log — Validation Tests

Validates:
- Feedback log markdown and JSON artifact exist and are well-formed
- JSON contains required boolean flags and consistency checks
- Markdown contains required sections, references, and safety statements
- Branch-scope guard (conditional on gl-150-first-developer-feedback-log branch)

Scope guard: this test must not change production backend code.
"""

import json
import os
import subprocess
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "first_developer_feedback_log.md")
JSON_PATH = os.path.join(
    REPO_ROOT, "docs", "examples", "gl150", "first_developer_feedback_log.json"
)

EXPECTED_BRANCH = "gl-150-first-developer-feedback-log"

ALLOWED_FILES = {
    "docs/first_developer_feedback_log.md",
    "docs/examples/gl150/first_developer_feedback_log.json",
    "backend/tests/test_gl150_first_developer_feedback_log.py",
    # Allowed only if intentionally touched
    "docs/public_github_readiness_pack.md",
    "docs/ten_minute_quickstart.md",
    "sdk/python/README.md",
    "docs/langgraph_langchain_integration_example.md",
    "README.md",
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

class TestGl150FilesExist(unittest.TestCase):
    def test_feedback_log_md_exists(self):
        self.assertTrue(
            os.path.isfile(DOC_PATH),
            f"docs/first_developer_feedback_log.md must exist ({DOC_PATH})",
        )

    def test_json_artifact_exists(self):
        self.assertTrue(
            os.path.isfile(JSON_PATH),
            f"JSON artifact must exist ({JSON_PATH})",
        )


# ---------------------------------------------------------------------------
# 2. JSON parsing and required fields
# ---------------------------------------------------------------------------

class TestGl150JsonArtifact(unittest.TestCase):
    def setUp(self):
        with open(JSON_PATH, "r", encoding="utf-8") as fh:
            self.data = json.load(fh)

    def test_json_parses(self):
        self.assertIsInstance(self.data, dict)

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-150")

    def test_feedback_log_created_true(self):
        self.assertIs(self.data.get("feedback_log_created"), True)

    def test_feedback_intake_template_created_true(self):
        self.assertIs(self.data.get("feedback_intake_template_created"), True)

    def test_public_github_release_claimed_false(self):
        self.assertIs(self.data.get("public_github_release_claimed"), False)

    def test_production_saas_ready_claimed_false(self):
        self.assertIs(self.data.get("production_saas_ready_claimed"), False)

    def test_tenant_isolation_claimed_implemented_false(self):
        self.assertIs(self.data.get("tenant_isolation_claimed_implemented"), False)

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

    def test_uses_real_secrets_false(self):
        self.assertIs(self.data.get("uses_real_secrets"), False)

    def test_uses_real_customer_data_false(self):
        self.assertIs(self.data.get("uses_real_customer_data"), False)

    def test_includes_private_personal_data_false(self):
        self.assertIs(self.data.get("includes_private_personal_data"), False)

    def test_feedback_consistency(self):
        """
        Assert that real_external_feedback_claimed and simulated_or_internal_dry_run_used
        are not both true (inconsistent), and that if simulated is true, real is false.
        """
        real = self.data.get("real_external_feedback_claimed", False)
        simulated = self.data.get("simulated_or_internal_dry_run_used", False)
        if simulated:
            self.assertFalse(
                real,
                "If simulated_or_internal_dry_run_used is true, "
                "real_external_feedback_claimed must be false",
            )

    def test_at_least_one_feedback_entry(self):
        entries = self.data.get("first_feedback_entries", [])
        self.assertIsInstance(entries, list)
        self.assertGreater(len(entries), 0, "At least one feedback entry must exist")

    def test_next_recommended_issue(self):
        next_issue = self.data.get("next_recommended_issue", "")
        self.assertIn("GL-151", next_issue)


# ---------------------------------------------------------------------------
# 3. Markdown document required sections
# ---------------------------------------------------------------------------

class TestGl150DocSections(unittest.TestCase):
    def setUp(self):
        with open(DOC_PATH, "r", encoding="utf-8") as fh:
            self.text = fh.read()
        self.lower = self.text.lower()

    def test_feedback_authenticity_statement_section(self):
        self.assertIn("feedback authenticity statement", self.lower)

    def test_current_developer_entry_path_section(self):
        self.assertIn("current developer entry path", self.lower)

    def test_feedback_intake_template_section(self):
        self.assertIn("feedback intake template", self.lower)

    def test_first_feedback_entry_section(self):
        self.assertIn("first feedback entry", self.lower)

    def test_findings_summary_section(self):
        self.assertIn("findings summary", self.lower)

    def test_follow_up_actions_section(self):
        self.assertIn("follow-up actions", self.lower)

    def test_go_no_go_criteria_section(self):
        self.assertIn("go/no-go criteria", self.lower)

    def test_validation_gates_section(self):
        self.assertIn("validation gates", self.lower)

    def test_next_recommended_issue_section(self):
        self.assertIn("next recommended issue", self.lower)


# ---------------------------------------------------------------------------
# 4. Document references required issues
# ---------------------------------------------------------------------------

class TestGl150DocReferences(unittest.TestCase):
    def setUp(self):
        with open(DOC_PATH, "r", encoding="utf-8") as fh:
            self.text = fh.read()
        self.lower = self.text.lower()

    def test_references_gl145(self):
        self.assertIn("gl-145", self.lower)

    def test_references_gl146(self):
        self.assertIn("gl-146", self.lower)

    def test_references_gl147(self):
        self.assertIn("gl-147", self.lower)

    def test_references_gl148(self):
        self.assertIn("gl-148", self.lower)

    def test_references_gl149(self):
        self.assertIn("gl-149", self.lower)

    def test_references_gl151(self):
        self.assertIn("gl-151", self.lower)

    def test_references_security_boundary(self):
        self.assertIn("security boundary", self.lower)


# ---------------------------------------------------------------------------
# 5. Explicit safety statements
# ---------------------------------------------------------------------------

class TestGl150DocSafetyStatements(unittest.TestCase):
    def setUp(self):
        with open(DOC_PATH, "r", encoding="utf-8") as fh:
            self.text = fh.read()
        self.lower = self.text.lower()

    def test_no_public_github_release_claim(self):
        self.assertTrue(
            "public github release claimed" in self.lower
            or "not public github publication" in self.lower
            or "no public github release" in self.lower,
            "Document must explicitly state no public GitHub release claim",
        )

    def test_no_production_saas_readiness_claim(self):
        self.assertTrue(
            "production saas readiness claimed" in self.lower
            or "no production saas" in self.lower
            or "not production saas" in self.lower,
            "Document must explicitly state no production SaaS readiness claim",
        )

    def test_tenant_isolation_not_implemented(self):
        self.assertTrue(
            "tenant isolation" in self.lower and "not implemented" in self.lower,
            "Document must state tenant isolation is not implemented",
        )

    def test_simulated_feedback_not_evidence_of_adoption(self):
        self.assertTrue(
            "simulated" in self.lower
            and "not evidence" in self.lower
            or "not evidence of external adoption" in self.lower
            or "simulated feedback is explicitly not evidence" in self.lower,
            "Document must state that simulated/internal feedback is not evidence of external adoption",
        )

    def test_no_real_secrets(self):
        self.assertTrue(
            "no real secrets" in self.lower
            or "uses real secrets" in self.lower,
            "Document must state no real secrets are used",
        )

    def test_no_real_customer_data(self):
        self.assertTrue(
            "no real customer data" in self.lower
            or "uses real customer data" in self.lower,
            "Document must state no real customer data is used",
        )


# ---------------------------------------------------------------------------
# 6. Scope guard (branch-specific)
# ---------------------------------------------------------------------------

class TestGl150ScopeGuard(unittest.TestCase):
    """Branch-specific diff assertions. Skipped when not on the GL-150 branch."""

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
            f"sdk/python/grantlayer_client.py must not change on GL-150: {sdk_changes}",
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
            f"LangGraph example must not change on GL-150: {example_changes}",
        )


if __name__ == "__main__":
    unittest.main()
