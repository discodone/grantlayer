"""Tests for GL-145: Developer Adoption Strategy Intake.

Ensures:
1. Strategy document exists and contains all required sections.
2. JSON artifact exists, parses, and contains required boolean flags.
3. Document references required prior and follow-up issues.
4. Document states no production SaaS readiness claim and tenant isolation
   not implemented.
5. Scope guard: only docs/examples/test files changed; no production src changes.
6. Branch-scope guard: skip diff assertions when not on GL-145 branch.
"""

import json
import os
import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_STRATEGY_MD = _REPO_ROOT / "docs" / "developer_adoption_strategy_intake.md"
_STRATEGY_JSON = _REPO_ROOT / "docs" / "examples" / "gl145" / "developer_adoption_strategy_intake.json"

_GL145_BRANCH = "gl-145-developer-adoption-strategy-intake"

_ALLOWED_CHANGED = {
    "docs/developer_adoption_strategy_intake.md",
    "docs/examples/gl145/developer_adoption_strategy_intake.json",
    "backend/tests/test_gl145_developer_adoption_strategy_intake.py",
}

_FORBIDDEN_PATTERNS = [
    ".claude/settings.json",
    "backend/src/server.py",
    "backend/src/config.py",
    "backend/src/models.py",
    "backend/src/audit_log.py",
    "docs/openapi.yaml",
    "backend/src/migrations/",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "setup.py",
    "Pipfile",
    "poetry.lock",
    "scripts/",
    "frontend/",
    "website/",
    "design/",
]


def _current_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=_REPO_ROOT
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _diff_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        capture_output=True, text=True, cwd=_REPO_ROOT
    )
    lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    return lines


# ---------------------------------------------------------------------------
# 1. Strategy document existence
# ---------------------------------------------------------------------------

class TestGl145StrategyDocumentExists(unittest.TestCase):

    def test_strategy_md_exists(self):
        self.assertTrue(
            _STRATEGY_MD.is_file(),
            "docs/developer_adoption_strategy_intake.md must exist"
        )

    def test_strategy_json_exists(self):
        self.assertTrue(
            _STRATEGY_JSON.is_file(),
            "docs/examples/gl145/developer_adoption_strategy_intake.json must exist"
        )


# ---------------------------------------------------------------------------
# 2. JSON artifact parses and contains required boolean flags
# ---------------------------------------------------------------------------

class TestGl145JsonArtifact(unittest.TestCase):

    def setUp(self):
        with open(_STRATEGY_JSON, "r", encoding="utf-8") as fh:
            self.data = json.load(fh)

    def test_issue_id_is_gl145(self):
        self.assertEqual(self.data.get("issue_id"), "GL-145")

    def test_strategy_intake_only_is_true(self):
        self.assertIs(self.data.get("strategy_intake_only"), True)

    def test_production_code_changed_is_false(self):
        self.assertIs(self.data.get("production_code_changed"), False)

    def test_sdk_implemented_is_false(self):
        self.assertIs(self.data.get("sdk_implemented"), False)

    def test_quickstart_implemented_is_false(self):
        self.assertIs(self.data.get("quickstart_implemented"), False)

    def test_langgraph_langchain_example_implemented_is_false(self):
        self.assertIs(self.data.get("langgraph_langchain_example_implemented"), False)

    def test_public_github_ready_claimed_is_false(self):
        self.assertIs(self.data.get("public_github_ready_claimed"), False)

    def test_production_saas_ready_claimed_is_false(self):
        self.assertIs(self.data.get("production_saas_ready_claimed"), False)

    def test_tenant_isolation_claimed_implemented_is_false(self):
        self.assertIs(self.data.get("tenant_isolation_claimed_implemented"), False)

    def test_endpoint_api_behavior_changed_is_false(self):
        self.assertIs(self.data.get("endpoint_api_behavior_changed"), False)

    def test_openapi_changed_is_false(self):
        self.assertIs(self.data.get("openapi_changed"), False)

    def test_db_schema_changed_is_false(self):
        self.assertIs(self.data.get("db_schema_changed"), False)

    def test_dependencies_changed_is_false(self):
        self.assertIs(self.data.get("dependencies_changed"), False)

    def test_target_developer_audiences_present(self):
        audiences = self.data.get("target_developer_audiences", [])
        self.assertIsInstance(audiences, list)
        self.assertGreater(len(audiences), 0)

    def test_adoption_track_present(self):
        track = self.data.get("adoption_track", [])
        self.assertIsInstance(track, list)
        self.assertGreater(len(track), 0)

    def test_artifact_map_present(self):
        artifact_map = self.data.get("artifact_map", [])
        self.assertIsInstance(artifact_map, list)
        self.assertGreater(len(artifact_map), 0)

    def test_messaging_rules_present(self):
        rules = self.data.get("messaging_rules", [])
        self.assertIsInstance(rules, list)
        self.assertGreater(len(rules), 0)

    def test_risks_present(self):
        risks = self.data.get("risks", [])
        self.assertIsInstance(risks, list)
        self.assertGreater(len(risks), 0)

    def test_validation_gates_present(self):
        gates = self.data.get("validation_gates", [])
        self.assertIsInstance(gates, list)
        self.assertGreater(len(gates), 0)

    def test_non_goals_present(self):
        non_goals = self.data.get("non_goals", [])
        self.assertIsInstance(non_goals, list)
        self.assertGreater(len(non_goals), 0)

    def test_proposed_follow_up_issues_present(self):
        issues = self.data.get("proposed_follow_up_issues", [])
        self.assertIsInstance(issues, list)
        self.assertGreater(len(issues), 0)

    def test_next_issue_is_gl146(self):
        self.assertEqual(
            self.data.get("next_issue"),
            "GL-146 10-Minute Quickstart"
        )


# ---------------------------------------------------------------------------
# 3. Strategy document contains required sections
# ---------------------------------------------------------------------------

class TestGl145StrategyDocumentSections(unittest.TestCase):

    def setUp(self):
        with open(_STRATEGY_MD, "r", encoding="utf-8") as fh:
            self.text = fh.read()
        self.lower = self.text.lower()

    def test_current_posture_section(self):
        self.assertIn("current posture", self.lower)

    def test_target_developer_audiences_section(self):
        self.assertIn("target developer audiences", self.lower)

    def test_developer_value_proposition_section(self):
        self.assertIn("developer value proposition", self.lower)

    def test_adoption_track_section(self):
        self.assertIn("adoption track", self.lower)

    def test_artifact_map_section(self):
        self.assertIn("artifact map", self.lower)

    def test_messaging_rules_section(self):
        self.assertIn("messaging rules", self.lower)

    def test_risks_section(self):
        self.assertIn("risks", self.lower)

    def test_validation_gates_section(self):
        self.assertIn("validation gates", self.lower)

    def test_non_goals_section(self):
        self.assertIn("non-goals", self.lower)

    def test_proposed_issue_definitions_section(self):
        self.assertIn("proposed issue definitions", self.lower)

    def test_go_no_go_criteria_section(self):
        self.assertIn("go/no-go criteria", self.lower)


# ---------------------------------------------------------------------------
# 4. Document references required issues and non-claims
# ---------------------------------------------------------------------------

class TestGl145DocumentReferences(unittest.TestCase):

    def setUp(self):
        with open(_STRATEGY_MD, "r", encoding="utf-8") as fh:
            self.text = fh.read()
        self.lower = self.text.lower()

    def test_references_gl146(self):
        self.assertIn("gl-146", self.lower)

    def test_references_gl147(self):
        self.assertIn("gl-147", self.lower)

    def test_references_gl148(self):
        self.assertIn("gl-148", self.lower)

    def test_references_gl149(self):
        self.assertIn("gl-149", self.lower)

    def test_references_gl150(self):
        self.assertIn("gl-150", self.lower)

    def test_references_gl144(self):
        self.assertIn("gl-144", self.lower)

    def test_no_production_saas_readiness_claim(self):
        self.assertTrue(
            "production saas readiness is not claimed" in self.lower
            or (
                "status and readiness caveats: see `readme.md`" in self.lower
                and "not production saas enablement" in self.lower
            ),
            "Document must clearly state that production SaaS readiness is not claimed",
        )

    def test_tenant_isolation_not_implemented(self):
        self.assertTrue(
            "tenant isolation is not implemented" in self.lower
            or (
                "status and readiness caveats: see `readme.md`" in self.lower
                and "not tenant/workspace implementation" in self.lower
            ),
            "Document must state tenant isolation is not implemented",
        )


# ---------------------------------------------------------------------------
# 5. Scope guard — only allowed files changed; no production src changes
# ---------------------------------------------------------------------------

class TestGl145ScopeGuard(unittest.TestCase):

    def test_branch_scope_guard(self):
        branch = _current_branch()
        if branch != _GL145_BRANCH:
            self.skipTest(
                f"Not on {_GL145_BRANCH} (current: {branch!r}); "
                "skipping branch-specific diff assertions."
            )

    def test_diff_only_allowed_files(self):
        branch = _current_branch()
        if branch != _GL145_BRANCH:
            self.skipTest("Branch-scope guard: skip diff assertions on main.")
        diff_files = _diff_files()
        for f in diff_files:
            self.assertIn(
                f, _ALLOWED_CHANGED,
                f"Unexpected changed file: {f}"
            )

    def test_no_forbidden_patterns_in_diff(self):
        branch = _current_branch()
        if branch != _GL145_BRANCH:
            self.skipTest("Branch-scope guard: skip diff assertions on main.")
        diff_files = _diff_files()
        for f in diff_files:
            for pat in _FORBIDDEN_PATTERNS:
                self.assertFalse(
                    f.startswith(pat) or f == pat,
                    f"Forbidden pattern {pat!r} found in diff: {f}"
                )

    def test_no_backend_src_changes(self):
        branch = _current_branch()
        if branch != _GL145_BRANCH:
            self.skipTest("Branch-scope guard: skip diff assertions on main.")
        diff_files = _diff_files()
        src_changes = [f for f in diff_files if f.startswith("backend/src/")]
        self.assertEqual(
            src_changes, [],
            f"backend/src/ must not be changed: {src_changes}"
        )

    def test_no_openapi_changes(self):
        branch = _current_branch()
        if branch != _GL145_BRANCH:
            self.skipTest("Branch-scope guard: skip diff assertions on main.")
        diff_files = _diff_files()
        self.assertNotIn(
            "docs/openapi.yaml", diff_files,
            "OpenAPI must not be changed"
        )

    def test_no_migration_changes(self):
        branch = _current_branch()
        if branch != _GL145_BRANCH:
            self.skipTest("Branch-scope guard: skip diff assertions on main.")
        diff_files = _diff_files()
        migration_changes = [
            f for f in diff_files
            if f.startswith("backend/src/migrations/")
        ]
        self.assertEqual(
            migration_changes, [],
            f"Migrations must not be changed: {migration_changes}"
        )

    def test_no_dependency_changes(self):
        branch = _current_branch()
        if branch != _GL145_BRANCH:
            self.skipTest("Branch-scope guard: skip diff assertions on main.")
        diff_files = _diff_files()
        dep_files = {
            "requirements.txt",
            "requirements-dev.txt",
            "pyproject.toml",
            "setup.py",
            "Pipfile",
            "poetry.lock",
        }
        for f in diff_files:
            self.assertNotIn(
                f, dep_files,
                f"Dependency file must not be changed: {f}"
            )

    def test_no_frontend_website_design_changes(self):
        branch = _current_branch()
        if branch != _GL145_BRANCH:
            self.skipTest("Branch-scope guard: skip diff assertions on main.")
        diff_files = _diff_files()
        for f in diff_files:
            self.assertFalse(
                f.startswith("frontend/") or
                f.startswith("website/") or
                f.startswith("design/"),
                f"Frontend/website/design must not be changed: {f}"
            )

    def test_no_claude_changes(self):
        branch = _current_branch()
        if branch != _GL145_BRANCH:
            self.skipTest("Branch-scope guard: skip diff assertions on main.")
        diff_files = _diff_files()
        for f in diff_files:
            self.assertFalse(
                f.startswith(".claude/"),
                f".claude/ must not be changed: {f}"
            )


if __name__ == "__main__":
    unittest.main()
