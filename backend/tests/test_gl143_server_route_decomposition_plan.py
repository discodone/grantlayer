"""Tests for GL-143: server.py Route Decomposition Plan.

Ensures:
1. Plan document exists and contains all required sections.
2. JSON artifact exists, parses, and contains required boolean flags.
3. Document references required prior issues and security boundary.
4. Document states GL-143 does not implement decomposition.
5. Scope guard: only docs/examples/test files changed; no production src changes.
6. Branch-scope guard: skip diff assertions when not on GL-143 branch.
"""

import json
import os
import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_PLAN_MD = _REPO_ROOT / "docs" / "server_route_decomposition_plan.md"
_PLAN_JSON = _REPO_ROOT / "docs" / "examples" / "gl143" / "server_route_decomposition_plan.json"

_GL143_BRANCH = "gl-143-server-route-decomposition-plan"

_ALLOWED_CHANGED = {
    "docs/server_route_decomposition_plan.md",
    "docs/examples/gl143/server_route_decomposition_plan.json",
    "backend/tests/test_gl143_server_route_decomposition_plan.py",
}

_FORBIDDEN_PATTERNS = [
    ".claude/settings.json",
    "backend/src/server.py",
    "backend/src/config.py",
    "backend/src/audit_log.py",
    "docs/openapi.yaml",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "setup.py",
    "Pipfile",
    "poetry.lock",
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
# 1. Plan document existence
# ---------------------------------------------------------------------------

class TestGl143PlanDocumentExists(unittest.TestCase):

    def test_plan_md_exists(self):
        self.assertTrue(
            _PLAN_MD.is_file(),
            "docs/server_route_decomposition_plan.md must exist"
        )

    def test_plan_json_exists(self):
        self.assertTrue(
            _PLAN_JSON.is_file(),
            "docs/examples/gl143/server_route_decomposition_plan.json must exist"
        )


# ---------------------------------------------------------------------------
# 2. JSON artifact parses and contains required boolean flags
# ---------------------------------------------------------------------------

class TestGl143JsonArtifact(unittest.TestCase):

    def setUp(self):
        with open(_PLAN_JSON, "r", encoding="utf-8") as fh:
            self.data = json.load(fh)

    def test_issue_id_is_gl143(self):
        self.assertEqual(self.data.get("issue_id"), "GL-143")

    def test_plan_only_is_true(self):
        self.assertIs(self.data.get("plan_only"), True)

    def test_production_code_changed_is_false(self):
        self.assertIs(self.data.get("production_code_changed"), False)

    def test_server_py_changed_is_false(self):
        self.assertIs(self.data.get("server_py_changed"), False)

    def test_route_decomposition_implemented_is_false(self):
        self.assertIs(self.data.get("route_decomposition_implemented"), False)

    def test_endpoint_api_behavior_changed_is_false(self):
        self.assertIs(self.data.get("endpoint_api_behavior_changed"), False)

    def test_openapi_changed_is_false(self):
        self.assertIs(self.data.get("openapi_changed"), False)

    def test_db_schema_changed_is_false(self):
        self.assertIs(self.data.get("db_schema_changed"), False)

    def test_dependencies_changed_is_false(self):
        self.assertIs(self.data.get("dependencies_changed"), False)

    def test_auth_semantics_changed_is_false(self):
        self.assertIs(self.data.get("auth_semantics_changed"), False)

    def test_request_parsing_changed_is_false(self):
        self.assertIs(self.data.get("request_parsing_changed"), False)

    def test_threading_http_server_changed_is_false(self):
        self.assertIs(self.data.get("threading_http_server_changed"), False)

    def test_audit_hash_chain_changed_is_false(self):
        self.assertIs(self.data.get("audit_hash_chain_changed"), False)

    def test_validation_gates_present(self):
        gates = self.data.get("validation_gates", [])
        self.assertIsInstance(gates, list)
        self.assertGreater(len(gates), 0)

    def test_risk_register_present(self):
        risks = self.data.get("risk_register", [])
        self.assertIsInstance(risks, list)
        self.assertGreater(len(risks), 0)

    def test_proposed_follow_up_issues_present(self):
        issues = self.data.get("proposed_follow_up_issues", [])
        self.assertIsInstance(issues, list)
        self.assertGreater(len(issues), 0)

    def test_non_goals_present(self):
        non_goals = self.data.get("non_goals", [])
        self.assertIsInstance(non_goals, list)
        self.assertGreater(len(non_goals), 0)

    def test_next_issue_is_gl144(self):
        self.assertEqual(
            self.data.get("next_issue"),
            "GL-144 Tenant / Workspace Data Model Design"
        )


# ---------------------------------------------------------------------------
# 3. Plan document contains required sections
# ---------------------------------------------------------------------------

class TestGl143PlanDocumentSections(unittest.TestCase):

    def setUp(self):
        with open(_PLAN_MD, "r", encoding="utf-8") as fh:
            self.text = fh.read()
        self.lower = self.text.lower()

    def test_current_responsibility_map_section(self):
        self.assertIn("current responsibility map", self.lower)

    def test_proposed_decomposition_boundaries_section(self):
        self.assertIn("proposed decomposition boundaries", self.lower)

    def test_safe_sequencing_section(self):
        self.assertIn("safe sequencing", self.lower)

    def test_risk_register_section(self):
        self.assertIn("risk register", self.lower)

    def test_validation_gates_section(self):
        self.assertIn("validation gates", self.lower)

    def test_non_goals_section(self):
        self.assertIn("non-goals", self.lower)

    def test_proposed_follow_up_issues_section(self):
        self.assertIn("proposed follow-up issues", self.lower)

    def test_go_no_go_criteria_section(self):
        self.assertIn("go/no-go criteria", self.lower)


# ---------------------------------------------------------------------------
# 4. Document references required prior issues and security boundary
# ---------------------------------------------------------------------------

class TestGl143PlanDocumentReferences(unittest.TestCase):

    def setUp(self):
        with open(_PLAN_MD, "r", encoding="utf-8") as fh:
            self.text = fh.read()

    def test_references_gl087(self):
        self.assertIn("GL-087", self.text)

    def test_references_gl090(self):
        self.assertIn("GL-090", self.text)

    def test_references_gl124(self):
        self.assertIn("GL-124", self.text)

    def test_references_gl139(self):
        self.assertIn("GL-139", self.text)

    def test_references_gl140(self):
        self.assertIn("GL-140", self.text)

    def test_references_gl141(self):
        self.assertIn("GL-141", self.text)

    def test_references_gl142(self):
        self.assertIn("GL-142", self.text)

    def test_references_security_boundary(self):
        self.assertIn("security boundary", self.text.lower())


# ---------------------------------------------------------------------------
# 5. Document says GL-143 does not implement decomposition
# ---------------------------------------------------------------------------

class TestGl143PlanDocumentScopeAssertions(unittest.TestCase):

    def setUp(self):
        with open(_PLAN_MD, "r", encoding="utf-8") as fh:
            self.text = fh.read()
        self.lower = self.text.lower()

    def test_doc_says_not_implementation(self):
        self.assertTrue(
            "not implementation" in self.lower or "**not** implementation" in self.text.lower()
        )

    def test_doc_says_not_refactor(self):
        self.assertTrue(
            "not a refactor" in self.lower or "**not** a refactor" in self.text.lower()
        )

    def test_doc_says_not_route_movement(self):
        self.assertTrue(
            "not route movement" in self.lower or "**not** route movement" in self.text.lower()
        )

    def test_doc_says_plan_only(self):
        self.assertIn("plan-only", self.lower)

    def test_doc_says_no_production_code_change(self):
        self.assertIn("no production code change", self.lower)

    def test_doc_says_no_production_code_changed(self):
        self.assertIn("no production code changed", self.lower)


# ---------------------------------------------------------------------------
# 6 & 7. Scope guard + branch-scope guard
# ---------------------------------------------------------------------------

class TestGl143ScopeGuard(unittest.TestCase):

    def test_no_openapi_changes(self):
        branch = _current_branch()
        if branch != _GL143_BRANCH:
            self.skipTest(f"Not on {_GL143_BRANCH} — skipping diff assertions")
        changed = _diff_files()
        openapi_changed = [f for f in changed if "openapi" in f.lower()]
        self.assertEqual(openapi_changed, [], f"OpenAPI files must not change: {openapi_changed}")

    def test_no_migration_or_db_schema_changes(self):
        branch = _current_branch()
        if branch != _GL143_BRANCH:
            self.skipTest(f"Not on {_GL143_BRANCH} — skipping diff assertions")
        changed = _diff_files()
        migration_changed = [f for f in changed if "migration" in f or "schema" in f.lower()]
        self.assertEqual(migration_changed, [], f"Migration/schema files must not change: {migration_changed}")

    def test_no_dependency_files_changed(self):
        branch = _current_branch()
        if branch != _GL143_BRANCH:
            self.skipTest(f"Not on {_GL143_BRANCH} — skipping diff assertions")
        changed = _diff_files()
        dep_changed = [f for f in changed if any(f.endswith(pat.lstrip("*")) or f == pat for pat in [
            "requirements.txt", "requirements-dev.txt", "pyproject.toml",
            "setup.py", "Pipfile", "poetry.lock"
        ])]
        self.assertEqual(dep_changed, [], f"Dependency files must not change: {dep_changed}")

    def test_no_forbidden_files_changed(self):
        branch = _current_branch()
        if branch != _GL143_BRANCH:
            self.skipTest(f"Not on {_GL143_BRANCH} — skipping diff assertions")
        changed = _diff_files()
        forbidden = [f for f in changed if any(pat in f for pat in _FORBIDDEN_PATTERNS)]
        self.assertEqual(forbidden, [], f"Forbidden files changed: {forbidden}")

    def test_no_frontend_website_design_changed(self):
        branch = _current_branch()
        if branch != _GL143_BRANCH:
            self.skipTest(f"Not on {_GL143_BRANCH} — skipping diff assertions")
        changed = _diff_files()
        frontend_changed = [
            f for f in changed
            if f.startswith("frontend/") or f.startswith("website/") or f.startswith("design/")
        ]
        self.assertEqual(frontend_changed, [], f"Frontend/website/design files must not change: {frontend_changed}")

    def test_no_claude_settings_changed(self):
        branch = _current_branch()
        if branch != _GL143_BRANCH:
            self.skipTest(f"Not on {_GL143_BRANCH} — skipping diff assertions")
        changed = _diff_files()
        settings_changed = [f for f in changed if ".claude/settings.json" in f]
        self.assertEqual(settings_changed, [], ".claude/settings.json must not change")

    def test_only_allowed_files_changed(self):
        branch = _current_branch()
        if branch != _GL143_BRANCH:
            self.skipTest(f"Not on {_GL143_BRANCH} — skipping diff assertions")
        changed = set(_diff_files())
        disallowed = changed - _ALLOWED_CHANGED
        self.assertEqual(disallowed, set(), f"Unexpected files changed: {disallowed}")

    def test_no_production_src_files_changed(self):
        branch = _current_branch()
        if branch != _GL143_BRANCH:
            self.skipTest(f"Not on {_GL143_BRANCH} — skipping diff assertions")
        changed = _diff_files()
        src_changed = [f for f in changed if f.startswith("backend/src/")]
        self.assertEqual(src_changed, [], f"No backend/src/ files may change: {src_changed}")


if __name__ == "__main__":
    unittest.main()
