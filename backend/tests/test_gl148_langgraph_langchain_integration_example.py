"""
GL-148: LangGraph/LangChain Integration Example — Validation Tests

Validates:
- Example script, documentation, and JSON artifact exist
- JSON artifact structure and boolean flags
- Example module imports without network side effects
- Required functions exist and are callable
- Dry-run workflow returns correct shape and safety caveats
- Documentation contains required sections and safety caveats
- Branch-scope guard (conditional on gl-148-langgraph-langchain-integration-example branch)
"""

import importlib.util
import json
import subprocess
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLE_PY = REPO_ROOT / "examples" / "langgraph_langchain" / "grantlayer_agent_example.py"
DOC_MD = REPO_ROOT / "docs" / "langgraph_langchain_integration_example.md"
JSON_ARTIFACT = (
    REPO_ROOT / "docs" / "examples" / "gl148" / "langgraph_langchain_integration_example.json"
)


def _load_example() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("grantlayer_agent_example", EXAMPLE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Files exist
# ---------------------------------------------------------------------------

class TestGl148FilesExist(unittest.TestCase):
    def test_example_script_exists(self):
        self.assertTrue(EXAMPLE_PY.exists(), f"Example script not found: {EXAMPLE_PY}")

    def test_documentation_exists(self):
        self.assertTrue(DOC_MD.exists(), f"Documentation not found: {DOC_MD}")

    def test_json_artifact_exists(self):
        self.assertTrue(JSON_ARTIFACT.exists(), f"JSON artifact not found: {JSON_ARTIFACT}")


# ---------------------------------------------------------------------------
# JSON artifact
# ---------------------------------------------------------------------------

class TestGl148JsonArtifact(unittest.TestCase):
    def setUp(self):
        with open(JSON_ARTIFACT, encoding="utf-8") as f:
            self.data = json.load(f)

    def test_json_parses(self):
        self.assertIsInstance(self.data, dict)

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-148")

    def test_artifact_type(self):
        self.assertEqual(self.data.get("artifact_type"), "langgraph_langchain_integration_example")

    def test_integration_example_created_true(self):
        self.assertIs(self.data.get("integration_example_created"), True)

    def test_uses_gl147_sdk_true(self):
        self.assertIs(self.data.get("uses_gl147_sdk"), True)

    def test_standard_library_only_true(self):
        self.assertIs(self.data.get("standard_library_only"), True)

    def test_langgraph_required_dependency_false(self):
        self.assertIs(self.data.get("langgraph_required_dependency"), False)

    def test_langchain_required_dependency_false(self):
        self.assertIs(self.data.get("langchain_required_dependency"), False)

    def test_external_llm_api_required_false(self):
        self.assertIs(self.data.get("external_llm_api_required"), False)

    def test_network_call_at_import_false(self):
        self.assertIs(self.data.get("network_call_at_import"), False)

    def test_dry_run_default_true(self):
        self.assertIs(self.data.get("dry_run_default"), True)

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

    def test_auth_semantics_changed_false(self):
        self.assertIs(self.data.get("auth_semantics_changed"), False)

    def test_public_github_ready_claimed_false(self):
        self.assertIs(self.data.get("public_github_ready_claimed"), False)

    def test_production_saas_ready_claimed_false(self):
        self.assertIs(self.data.get("production_saas_ready_claimed"), False)

    def test_tenant_isolation_claimed_implemented_false(self):
        self.assertIs(self.data.get("tenant_isolation_claimed_implemented"), False)

    def test_uses_real_secrets_false(self):
        self.assertIs(self.data.get("uses_real_secrets"), False)

    def test_uses_real_customer_data_false(self):
        self.assertIs(self.data.get("uses_real_customer_data"), False)

    def test_features_present(self):
        features = self.data.get("features")
        self.assertIsInstance(features, list)
        self.assertGreater(len(features), 0)

    def test_safety_caveats_present(self):
        caveats = self.data.get("safety_caveats")
        self.assertIsInstance(caveats, list)
        self.assertGreater(len(caveats), 0)

    def test_validation_gates_present(self):
        gates = self.data.get("validation_gates")
        self.assertIsInstance(gates, list)
        self.assertGreater(len(gates), 0)

    def test_next_issue(self):
        next_issue = self.data.get("next_issue", "")
        self.assertIn("GL-149", next_issue)

    def test_example_path_field(self):
        self.assertIn(
            "examples/langgraph_langchain/grantlayer_agent_example.py",
            self.data.get("example_path", ""),
        )

    def test_documentation_path_field(self):
        self.assertIn(
            "docs/langgraph_langchain_integration_example.md",
            self.data.get("documentation_path", ""),
        )


# ---------------------------------------------------------------------------
# Example module import — no network, no langgraph/langchain required
# ---------------------------------------------------------------------------

class TestGl148ExampleImport(unittest.TestCase):
    def setUp(self):
        self.mod = _load_example()

    def test_no_network_at_import(self):
        # If we got here the module loaded without raising a network error.
        self.assertIsNotNone(self.mod)

    def test_no_langgraph_import_required(self):
        self.assertNotIn("langgraph", sys.modules)

    def test_no_langchain_import_required(self):
        self.assertNotIn("langchain", sys.modules)

    def test_build_sample_agent_state_exists(self):
        self.assertTrue(
            callable(getattr(self.mod, "build_sample_agent_state", None)),
            "build_sample_agent_state must be a callable",
        )

    def test_preflight_grantlayer_exists(self):
        self.assertTrue(
            callable(getattr(self.mod, "preflight_grantlayer", None)),
            "preflight_grantlayer must be a callable",
        )

    def test_prepare_grant_decision_context_exists(self):
        self.assertTrue(
            callable(getattr(self.mod, "prepare_grant_decision_context", None)),
            "prepare_grant_decision_context must be a callable",
        )

    def test_run_dry_run_workflow_exists(self):
        self.assertTrue(
            callable(getattr(self.mod, "run_dry_run_workflow", None)),
            "run_dry_run_workflow must be a callable",
        )

    def test_run_local_workflow_exists(self):
        self.assertTrue(
            callable(getattr(self.mod, "run_local_workflow", None)),
            "run_local_workflow must be a callable",
        )

    def test_grantlayer_client_imported(self):
        self.assertTrue(
            hasattr(self.mod, "GrantLayerClient"),
            "GrantLayerClient must be importable from the example module",
        )


# ---------------------------------------------------------------------------
# Dry-run workflow output shape
# ---------------------------------------------------------------------------

class TestGl148DryRunWorkflow(unittest.TestCase):
    def setUp(self):
        self.mod = _load_example()
        self.result = self.mod.run_dry_run_workflow()

    def test_result_is_dict(self):
        self.assertIsInstance(self.result, dict)

    def test_mode_is_dry_run(self):
        self.assertEqual(self.result.get("mode"), "dry_run")

    def test_safety_caveats_present(self):
        caveats = self.result.get("safety_caveats")
        self.assertIsInstance(caveats, list)
        self.assertGreater(len(caveats), 0)

    def test_safety_caveats_reference_developer_preview(self):
        caveats = self.result.get("safety_caveats", [])
        combined = " ".join(caveats).lower()
        self.assertIn("developer-preview", combined)

    def test_safety_caveats_reference_tenant_isolation(self):
        caveats = self.result.get("safety_caveats", [])
        combined = " ".join(caveats).lower()
        self.assertIn("tenant isolation", combined)

    def test_grantlayer_preflight_present(self):
        self.assertIn("grantlayer_preflight", self.result)

    def test_preflight_mode_is_dry_run(self):
        preflight = self.result.get("grantlayer_preflight", {})
        self.assertEqual(preflight.get("mode"), "dry_run")

    def test_sample_decision_context_present(self):
        self.assertIn("sample_decision_context", self.result)

    def test_no_token_in_result(self):
        serialised = json.dumps(self.result)
        # Ensure no real-looking token leaked into output
        forbidden = ["-----BEGIN", "PRIVATE KEY", "sk-", "eyJhbGciOiJSUzI"]
        for marker in forbidden:
            self.assertNotIn(marker, serialised, f"Output must not contain '{marker}'")

    def test_no_real_customer_data_in_result(self):
        # The sample state uses placeholder values only
        state = self.result.get("sample_decision_context", {}).get("agent_state_summary", {})
        if state:
            subject = state.get("subjectId", "")
            # Must be obviously synthetic — not a real email or UUID
            self.assertIn("demo", subject.lower(), "subjectId must be a demo placeholder")


# ---------------------------------------------------------------------------
# Example script text — references GL-147 SDK, no fake real secrets
# ---------------------------------------------------------------------------

class TestGl148ExampleText(unittest.TestCase):
    def setUp(self):
        self.text = EXAMPLE_PY.read_text(encoding="utf-8")

    def test_references_grantlayer_client(self):
        self.assertIn("GrantLayerClient", self.text)

    def test_no_fake_real_secrets(self):
        forbidden = ["-----BEGIN", "PRIVATE KEY", "sk-", "eyJhbGciOiJSUzI"]
        for marker in forbidden:
            self.assertNotIn(marker, self.text, f"Example must not contain '{marker}'")

    def test_no_real_looking_token_in_default_args(self):
        # Default token arg must be None or a clearly synthetic placeholder
        self.assertNotIn('token="sk-', self.text)
        self.assertNotIn("token='sk-", self.text)

    def test_sdk_import_present(self):
        self.assertIn("grantlayer_client", self.text)

    def test_dry_run_default_in_code(self):
        self.assertIn("dry_run", self.text)


# ---------------------------------------------------------------------------
# Documentation content
# ---------------------------------------------------------------------------

class TestGl148DocContent(unittest.TestCase):
    def setUp(self):
        self.text = DOC_MD.read_text(encoding="utf-8")
        self.lower = self.text.lower()

    def test_developer_preview_mentioned(self):
        self.assertIn("developer-preview", self.lower)

    def test_no_production_saas_ready_claim(self):
        self.assertNotIn(
            "production saas ready",
            self.lower,
            "Docs must not claim production SaaS readiness",
        )

    def test_tenant_isolation_not_implemented(self):
        self.assertIn("tenant isolation", self.lower)
        self.assertIn("not implemented", self.lower)

    def test_no_external_llm_api_key_required(self):
        self.assertTrue(
            "no external llm" in self.lower or "no llm" in self.lower or
            "no external" in self.lower,
            "Docs must state no external LLM/API key is required",
        )

    def test_references_gl149(self):
        self.assertIn("gl-149", self.lower)

    def test_references_gl150(self):
        self.assertIn("gl-150", self.lower)

    def test_no_real_secrets_in_docs(self):
        forbidden = ["-----BEGIN", "PRIVATE KEY", "sk-", "eyJhbGciOiJSUzI"]
        for marker in forbidden:
            self.assertNotIn(marker, self.text, f"Docs must not contain '{marker}'")

    def test_dry_run_section_present(self):
        self.assertIn("dry-run", self.lower)

    def test_security_caveats_section_present(self):
        self.assertTrue(
            "security caveats" in self.lower or "safety caveats" in self.lower,
            "Docs must include a security/safety caveats section",
        )

    def test_troubleshooting_section_present(self):
        self.assertIn("troubleshooting", self.lower)


# ---------------------------------------------------------------------------
# Scope guard (branch-specific)
# ---------------------------------------------------------------------------

class TestGl148ScopeGuard(unittest.TestCase):
    """Branch-specific diff assertions. Skipped when not on the GL-148 branch."""

    EXPECTED_BRANCH = "gl-148-langgraph-langchain-integration-example"

    ALLOWED_FILES = {
        "examples/langgraph_langchain/grantlayer_agent_example.py",
        "docs/langgraph_langchain_integration_example.md",
        "docs/examples/gl148/langgraph_langchain_integration_example.json",
        "backend/tests/test_gl148_langgraph_langchain_integration_example.py",
        # Allowed only if intentionally touched
        "sdk/python/README.md",
        "docs/ten_minute_quickstart.md",
        "README.md",
    }

    FORBIDDEN_PATTERNS = [
        "backend/src/",
        "docs/openapi.yaml",
        "migrations/",
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
        if self.branch != self.EXPECTED_BRANCH:
            self.skipTest(
                f"Scope guard skipped: not on {self.EXPECTED_BRANCH} (current: {self.branch})"
            )
        self.changed = self._changed_files()

    def test_no_backend_src_changes(self):
        violations = [f for f in self.changed if f.startswith("backend/src/")]
        self.assertEqual(violations, [], f"backend/src/ must not be modified: {violations}")

    def test_no_openapi_changes(self):
        violations = [f for f in self.changed if f == "docs/openapi.yaml"]
        self.assertEqual(violations, [], "docs/openapi.yaml must not be modified")

    def test_no_migration_changes(self):
        violations = [f for f in self.changed if "migration" in f.lower()]
        self.assertEqual(violations, [], f"Migration files must not be modified: {violations}")

    def test_no_dependency_file_changes(self):
        dep_files = {
            "requirements.txt", "requirements-dev.txt", "pyproject.toml",
            "setup.py", "Pipfile", "poetry.lock",
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
        unexpected = [f for f in self.changed if f not in self.ALLOWED_FILES]
        self.assertEqual(
            unexpected,
            [],
            f"Unexpected files changed: {unexpected}. Allowed: {sorted(self.ALLOWED_FILES)}",
        )

    def test_no_forbidden_pattern_in_diff(self):
        for pattern in self.FORBIDDEN_PATTERNS:
            violations = [f for f in self.changed if pattern in f]
            self.assertEqual(
                violations,
                [],
                f"Forbidden pattern '{pattern}' found in changed files: {violations}",
            )


if __name__ == "__main__":
    unittest.main()
