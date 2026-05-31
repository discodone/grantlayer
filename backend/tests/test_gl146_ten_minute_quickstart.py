"""Tests for GL-146: 10-Minute Quickstart.

Ensures:
1. Quickstart document exists and contains all required sections.
2. JSON artifact exists, parses, and contains required boolean flags.
3. Document references required follow-up issues (GL-147 through GL-150).
4. Document states no production SaaS readiness claim and tenant isolation
   not implemented.
5. Document includes copy-paste friendly command indicators.
6. Scope guard: only docs/examples/test files changed; no production src changes.
7. Branch-scope guard: skip diff assertions when not on GL-146 branch.
"""

import json
import os
import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_QUICK_MD = _REPO_ROOT / "docs" / "ten_minute_quickstart.md"
_QUICK_JSON = _REPO_ROOT / "docs" / "examples" / "gl146" / "ten_minute_quickstart.json"

_GL146_BRANCH = "gl-146-ten-minute-quickstart"

_ALLOWED_CHANGED = {
    "docs/ten_minute_quickstart.md",
    "docs/examples/gl146/ten_minute_quickstart.json",
    "backend/tests/test_gl146_ten_minute_quickstart.py",
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
# 1. Quickstart document existence
# ---------------------------------------------------------------------------

class TestGl146QuickstartDocumentExists(unittest.TestCase):

    def test_quickstart_md_exists(self):
        self.assertTrue(
            _QUICK_MD.is_file(),
            "docs/ten_minute_quickstart.md must exist"
        )

    def test_quickstart_json_exists(self):
        self.assertTrue(
            _QUICK_JSON.is_file(),
            "docs/examples/gl146/ten_minute_quickstart.json must exist"
        )


# ---------------------------------------------------------------------------
# 2. JSON artifact parses and contains required boolean flags
# ---------------------------------------------------------------------------

class TestGl146JsonArtifact(unittest.TestCase):

    def setUp(self):
        with open(_QUICK_JSON, "r", encoding="utf-8") as fh:
            self.data = json.load(fh)

    def test_issue_id_is_gl146(self):
        self.assertEqual(self.data.get("issue_id"), "GL-146")

    def test_quickstart_created_is_true(self):
        self.assertIs(self.data.get("quickstart_created"), True)

    def test_production_code_changed_is_false(self):
        self.assertIs(self.data.get("production_code_changed"), False)

    def test_backend_src_changed_is_false(self):
        self.assertIs(self.data.get("backend_src_changed"), False)

    def test_endpoint_api_behavior_changed_is_false(self):
        self.assertIs(self.data.get("endpoint_api_behavior_changed"), False)

    def test_openapi_changed_is_false(self):
        self.assertIs(self.data.get("openapi_changed"), False)

    def test_db_schema_changed_is_false(self):
        self.assertIs(self.data.get("db_schema_changed"), False)

    def test_dependencies_changed_is_false(self):
        self.assertIs(self.data.get("dependencies_changed"), False)

    def test_sdk_implemented_is_false(self):
        self.assertIs(self.data.get("sdk_implemented"), False)

    def test_langgraph_langchain_example_implemented_is_false(self):
        self.assertIs(self.data.get("langgraph_langchain_example_implemented"), False)

    def test_public_github_ready_claimed_is_false(self):
        self.assertIs(self.data.get("public_github_ready_claimed"), False)

    def test_production_saas_ready_claimed_is_false(self):
        self.assertIs(self.data.get("production_saas_ready_claimed"), False)

    def test_tenant_isolation_claimed_implemented_is_false(self):
        self.assertIs(self.data.get("tenant_isolation_claimed_implemented"), False)

    def test_uses_real_secrets_is_false(self):
        self.assertIs(self.data.get("uses_real_secrets"), False)

    def test_uses_real_customer_data_is_false(self):
        self.assertIs(self.data.get("uses_real_customer_data"), False)

    def test_sections_present(self):
        sections = self.data.get("sections", [])
        self.assertIsInstance(sections, list)
        self.assertGreater(len(sections), 0)

    def test_commands_documented_present(self):
        commands = self.data.get("commands_documented", [])
        self.assertIsInstance(commands, list)
        self.assertGreater(len(commands), 0)

    def test_safety_caveats_present(self):
        caveats = self.data.get("safety_caveats", [])
        self.assertIsInstance(caveats, list)
        self.assertGreater(len(caveats), 0)

    def test_troubleshooting_topics_present(self):
        topics = self.data.get("troubleshooting_topics", [])
        self.assertIsInstance(topics, list)
        self.assertGreater(len(topics), 0)

    def test_validation_gates_present(self):
        gates = self.data.get("validation_gates", [])
        self.assertIsInstance(gates, list)
        self.assertGreater(len(gates), 0)

    def test_next_issue_is_gl147(self):
        self.assertEqual(
            self.data.get("next_issue"),
            "GL-147 Minimal Python SDK"
        )


# ---------------------------------------------------------------------------
# 3. Quickstart document contains required sections
# ---------------------------------------------------------------------------

class TestGl146QuickstartDocumentSections(unittest.TestCase):

    def setUp(self):
        with open(_QUICK_MD, "r", encoding="utf-8") as fh:
            self.text = fh.read()
        self.lower = self.text.lower()

    def test_what_this_quickstart_does_section(self):
        self.assertIn("what this quickstart does", self.lower)

    def test_what_this_quickstart_does_not_do_section(self):
        self.assertIn("what this quickstart does not do", self.lower)

    def test_prerequisites_section(self):
        self.assertIn("prerequisites", self.lower)

    def test_setup_section(self):
        self.assertIn("setup", self.lower)

    def test_configuration_section(self):
        self.assertIn("configuration", self.lower)

    def test_run_backend_section(self):
        self.assertIn("run backend", self.lower)

    def test_verify_health_readiness_section(self):
        self.assertIn("verify health", self.lower)
        self.assertIn("readiness", self.lower)

    def test_minimal_smoke_path_section(self):
        self.assertIn("minimal smoke path", self.lower)

    def test_troubleshooting_section(self):
        self.assertIn("troubleshooting", self.lower)

    def test_safety_checklist_section(self):
        self.assertIn("safety checklist", self.lower)

    def test_next_steps_section(self):
        self.assertIn("next steps", self.lower)


# ---------------------------------------------------------------------------
# 4. Document references required issues and non-claims
# ---------------------------------------------------------------------------

class TestGl146DocumentReferences(unittest.TestCase):

    def setUp(self):
        with open(_QUICK_MD, "r", encoding="utf-8") as fh:
            self.text = fh.read()
        self.lower = self.text.lower()

    def test_references_gl147(self):
        self.assertIn("gl-147", self.lower)

    def test_references_gl148(self):
        self.assertIn("gl-148", self.lower)

    def test_references_gl149(self):
        self.assertIn("gl-149", self.lower)

    def test_references_gl150(self):
        self.assertIn("gl-150", self.lower)

    def test_no_production_saas_readiness_claim(self):
        self.assertTrue(
            "production saas readiness is not claimed" in self.lower
            or (
                "status and readiness caveats: see `readme.md`" in self.lower
                and "not production deployment guidance" in self.lower
            ),
            "Document must include a clear statement that production SaaS readiness is not claimed",
        )

    def test_tenant_isolation_not_implemented(self):
        self.assertTrue(
            "tenant isolation is not implemented" in self.lower
            or "no tenant isolation" in self.lower
            or "not tenant/workspace implementation" in self.lower,
            "Document must state tenant isolation is not implemented"
        )

    def test_no_real_secrets(self):
        self.assertTrue(
            "no real secrets" in self.lower
            or "no secrets" in self.lower
            or "placeholder" in self.lower,
            "Document must state no real secrets are used"
        )

    def test_no_real_customer_data(self):
        self.assertTrue(
            "no real customer data" in self.lower
            or "synthetic" in self.lower
            or "demo" in self.lower,
            "Document must state no real customer data is used"
        )


# ---------------------------------------------------------------------------
# 5. Document includes copy-paste command indicators
# ---------------------------------------------------------------------------

class TestGl146CopyPasteCommands(unittest.TestCase):

    def setUp(self):
        with open(_QUICK_MD, "r", encoding="utf-8") as fh:
            self.text = fh.read()
        self.lower = self.text.lower()

    def test_git_clone_or_local_checkout(self):
        self.assertTrue(
            "git clone" in self.lower or "local checkout" in self.lower
            or "local repo checkout" in self.lower
            or "copy the directory" in self.lower,
            "Document must reference git clone or local checkout"
        )

    def test_python3_m_venv_or_equivalent(self):
        self.assertTrue(
            "python3 -m venv" in self.lower
            or "virtualenv" in self.lower
            or "python -m venv" in self.lower,
            "Document must reference python3 -m venv or equivalent"
        )

    def test_pip_install(self):
        self.assertIn("pip install", self.lower)

    def test_curl_health_examples(self):
        self.assertIn("curl", self.lower)
        self.assertIn("/health", self.lower)

    def test_curl_readiness_examples(self):
        self.assertIn("/readiness", self.lower)


# ---------------------------------------------------------------------------
# 6. Scope guard — only allowed files changed; no production src changes
# ---------------------------------------------------------------------------

class TestGl146ScopeGuard(unittest.TestCase):

    def test_branch_scope_guard(self):
        branch = _current_branch()
        if branch != _GL146_BRANCH:
            self.skipTest(
                f"Not on {_GL146_BRANCH} (current: {branch!r}); "
                "skipping branch-specific diff assertions."
            )

    def test_diff_only_allowed_files(self):
        branch = _current_branch()
        if branch != _GL146_BRANCH:
            self.skipTest("Branch-scope guard: skip diff assertions on main.")
        diff_files = _diff_files()
        for f in diff_files:
            self.assertIn(
                f, _ALLOWED_CHANGED,
                f"Unexpected changed file: {f}"
            )

    def test_no_forbidden_patterns_in_diff(self):
        branch = _current_branch()
        if branch != _GL146_BRANCH:
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
        if branch != _GL146_BRANCH:
            self.skipTest("Branch-scope guard: skip diff assertions on main.")
        diff_files = _diff_files()
        src_changes = [f for f in diff_files if f.startswith("backend/src/")]
        self.assertEqual(
            src_changes, [],
            f"backend/src/ must not be changed: {src_changes}"
        )

    def test_no_openapi_changes(self):
        branch = _current_branch()
        if branch != _GL146_BRANCH:
            self.skipTest("Branch-scope guard: skip diff assertions on main.")
        diff_files = _diff_files()
        self.assertNotIn(
            "docs/openapi.yaml", diff_files,
            "OpenAPI must not be changed"
        )

    def test_no_migration_changes(self):
        branch = _current_branch()
        if branch != _GL146_BRANCH:
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
        if branch != _GL146_BRANCH:
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
        if branch != _GL146_BRANCH:
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
        if branch != _GL146_BRANCH:
            self.skipTest("Branch-scope guard: skip diff assertions on main.")
        diff_files = _diff_files()
        for f in diff_files:
            self.assertFalse(
                f.startswith(".claude/"),
                f".claude/ must not be changed: {f}"
            )


if __name__ == "__main__":
    unittest.main()
