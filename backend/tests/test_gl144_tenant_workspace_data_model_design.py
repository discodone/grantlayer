"""Tests for GL-144: Tenant / Workspace Data Model Design.

Ensures:
1. Design document exists and contains all required sections.
2. JSON artifact exists, parses, and contains required boolean flags.
3. Document references required prior issues and security boundary.
4. Document states no production SaaS readiness claim and tenant isolation
   not implemented.
5. Scope guard: only docs/examples/test files changed; no production src changes.
6. Branch-scope guard: skip diff assertions when not on GL-144 branch.
"""

import json
import os
import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_DESIGN_MD = _REPO_ROOT / "docs" / "tenant_workspace_data_model_design.md"
_DESIGN_JSON = _REPO_ROOT / "docs" / "examples" / "gl144" / "tenant_workspace_data_model_design.json"

_GL144_BRANCH = "gl-144-tenant-workspace-data-model-design"

_ALLOWED_CHANGED = {
    "docs/tenant_workspace_data_model_design.md",
    "docs/examples/gl144/tenant_workspace_data_model_design.json",
    "backend/tests/test_gl144_tenant_workspace_data_model_design.py",
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
# 1. Design document existence
# ---------------------------------------------------------------------------

class TestGl144DesignDocumentExists(unittest.TestCase):

    def test_design_md_exists(self):
        self.assertTrue(
            _DESIGN_MD.is_file(),
            "docs/tenant_workspace_data_model_design.md must exist"
        )

    def test_design_json_exists(self):
        self.assertTrue(
            _DESIGN_JSON.is_file(),
            "docs/examples/gl144/tenant_workspace_data_model_design.json must exist"
        )


# ---------------------------------------------------------------------------
# 2. JSON artifact parses and contains required boolean flags
# ---------------------------------------------------------------------------

class TestGl144JsonArtifact(unittest.TestCase):

    def setUp(self):
        with open(_DESIGN_JSON, "r", encoding="utf-8") as fh:
            self.data = json.load(fh)

    def test_issue_id_is_gl144(self):
        self.assertEqual(self.data.get("issue_id"), "GL-144")

    def test_design_only_is_true(self):
        self.assertIs(self.data.get("design_only"), True)

    def test_production_code_changed_is_false(self):
        self.assertIs(self.data.get("production_code_changed"), False)

    def test_tenant_implementation_added_is_false(self):
        self.assertIs(self.data.get("tenant_implementation_added"), False)

    def test_workspace_implementation_added_is_false(self):
        self.assertIs(self.data.get("workspace_implementation_added"), False)

    def test_db_schema_changed_is_false(self):
        self.assertIs(self.data.get("db_schema_changed"), False)

    def test_migration_changed_is_false(self):
        self.assertIs(self.data.get("migration_changed"), False)

    def test_endpoint_api_behavior_changed_is_false(self):
        self.assertIs(self.data.get("endpoint_api_behavior_changed"), False)

    def test_openapi_changed_is_false(self):
        self.assertIs(self.data.get("openapi_changed"), False)

    def test_auth_semantics_changed_is_false(self):
        self.assertIs(self.data.get("auth_semantics_changed"), False)

    def test_operator_model_default_changed_is_false(self):
        self.assertIs(self.data.get("operator_model_default_changed"), False)

    def test_audit_hash_chain_changed_is_false(self):
        self.assertIs(self.data.get("audit_hash_chain_changed"), False)

    def test_request_parsing_changed_is_false(self):
        self.assertIs(self.data.get("request_parsing_changed"), False)

    def test_threading_http_server_changed_is_false(self):
        self.assertIs(self.data.get("threading_http_server_changed"), False)

    def test_production_saas_ready_claimed_is_false(self):
        self.assertIs(self.data.get("production_saas_ready_claimed"), False)

    def test_tenant_isolation_claimed_implemented_is_false(self):
        self.assertIs(self.data.get("tenant_isolation_claimed_implemented"), False)

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

    def test_next_issue_is_gl145(self):
        self.assertEqual(
            self.data.get("next_issue"),
            "GL-145 Developer Adoption Strategy Intake"
        )


# ---------------------------------------------------------------------------
# 3. Design document contains required sections
# ---------------------------------------------------------------------------

class TestGl144DesignDocumentSections(unittest.TestCase):

    def setUp(self):
        with open(_DESIGN_MD, "r", encoding="utf-8") as fh:
            self.text = fh.read()
        self.lower = self.text.lower()

    def test_current_posture_section(self):
        self.assertIn("current posture", self.lower)

    def test_definitions_section(self):
        self.assertIn("definitions", self.lower)

    def test_proposed_data_model_section(self):
        self.assertIn("proposed data model", self.lower)

    def test_proposed_fields_section(self):
        self.assertIn("proposed fields", self.lower)

    def test_relationship_model_section(self):
        self.assertIn("relationship model", self.lower)

    def test_isolation_rules_section(self):
        self.assertIn("isolation rules", self.lower)

    def test_auth_permission_implications_section(self):
        self.assertIn("auth/permission implications", self.lower)

    def test_audit_provenance_logging_implications_section(self):
        self.assertIn("audit/provenance/logging implications", self.lower)

    def test_migration_sequencing_section(self):
        self.assertIn("migration sequencing", self.lower)

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

class TestGl144DocumentReferences(unittest.TestCase):

    def setUp(self):
        with open(_DESIGN_MD, "r", encoding="utf-8") as fh:
            self.text = fh.read()
        self.lower = self.text.lower()

    def test_references_gl132(self):
        self.assertIn("gl-132", self.lower)

    def test_references_gl139(self):
        self.assertIn("gl-139", self.lower)

    def test_references_gl140(self):
        self.assertIn("gl-140", self.lower)

    def test_references_gl141(self):
        self.assertIn("gl-141", self.lower)

    def test_references_gl142(self):
        self.assertIn("gl-142", self.lower)

    def test_references_gl143(self):
        self.assertIn("gl-143", self.lower)

    def test_references_security_boundary(self):
        self.assertIn("security boundary", self.lower)

    def test_no_production_saas_readiness_claim(self):
        self.assertIn("no production saas readiness claim", self.lower)

    def test_tenant_isolation_not_implemented(self):
        self.assertIn("tenant isolation", self.lower)
        self.assertIn("not implemented", self.lower)

    def test_no_schema_migration_change(self):
        self.assertIn("no schema/migration", self.lower)


# ---------------------------------------------------------------------------
# 5. Scope guard — only allowed files changed; no production src changes
# ---------------------------------------------------------------------------

class TestGl144ScopeGuard(unittest.TestCase):

    def test_branch_scope_guard(self):
        branch = _current_branch()
        if branch != _GL144_BRANCH:
            self.skipTest(
                f"Not on {_GL144_BRANCH} (current: {branch!r}); "
                "skipping branch-specific diff assertions."
            )

    def test_diff_only_allowed_files(self):
        branch = _current_branch()
        if branch != _GL144_BRANCH:
            self.skipTest("Branch-scope guard: skip diff assertions on main.")
        diff_files = _diff_files()
        for f in diff_files:
            self.assertIn(
                f, _ALLOWED_CHANGED,
                f"Unexpected changed file: {f}"
            )

    def test_no_forbidden_patterns_in_diff(self):
        branch = _current_branch()
        if branch != _GL144_BRANCH:
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
        if branch != _GL144_BRANCH:
            self.skipTest("Branch-scope guard: skip diff assertions on main.")
        diff_files = _diff_files()
        src_changes = [f for f in diff_files if f.startswith("backend/src/")]
        self.assertEqual(
            src_changes, [],
            f"backend/src/ must not be changed: {src_changes}"
        )

    def test_no_openapi_changes(self):
        branch = _current_branch()
        if branch != _GL144_BRANCH:
            self.skipTest("Branch-scope guard: skip diff assertions on main.")
        diff_files = _diff_files()
        self.assertNotIn(
            "docs/openapi.yaml", diff_files,
            "OpenAPI must not be changed"
        )

    def test_no_migration_changes(self):
        branch = _current_branch()
        if branch != _GL144_BRANCH:
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
        if branch != _GL144_BRANCH:
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
        if branch != _GL144_BRANCH:
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
        if branch != _GL144_BRANCH:
            self.skipTest("Branch-scope guard: skip diff assertions on main.")
        diff_files = _diff_files()
        for f in diff_files:
            self.assertFalse(
                f.startswith(".claude/"),
                f".claude/ must not be changed: {f}"
            )


if __name__ == "__main__":
    unittest.main()
