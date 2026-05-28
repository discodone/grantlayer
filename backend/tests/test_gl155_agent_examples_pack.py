"""GL-155: validation test for Agent Examples Pack.

This test verifies that the GL-155 deliverables exist, are parseable,
execute correctly, and satisfy the acceptance criteria defined in the issue.
"""

import ast
import json
import os
import subprocess
import unittest
import sys
import importlib.util
import importlib.machinery


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Modules that are allowed to be imported by the agent examples.
_ALLOWED_STDLIB_MODULES = frozenset(
    # Core stdlib
    [
        "__future__",
        "abc",
        "argparse",
        "ast",
        "base64",
        "collections",
        "copy",
        "csv",
        "dataclasses",
        "datetime",
        "enum",
        "functools",
        "hashlib",
        "http",
        "importlib",
        "inspect",
        "io",
        "itertools",
        "json",
        "math",
        "numbers",
        "operator",
        "os",
        "pathlib",
        "random",
        "re",
        "shutil",
        "socket",
        "string",
        "sys",
        "tempfile",
        "textwrap",
        "time",
        "traceback",
        "types",
        "typing",
        "unittest",
        "urllib",
        "uuid",
        "warnings",
        "xml",
    ]
)

_DISALLOWED_NETWORK_MODULES = frozenset(
    [
        "requests",
        "httpx",
        "aiohttp",
        "urllib.request",
        "http.client",
    ]
)

_FORBIDDEN_CONTENT_PATTERNS = [
    "sk-",
    "Bearer ",
    "api.openai.com",
    "api.anthropic.com",
    "api.moonshot.cn",
    "api.moonshot",
    "forge.hofercloud.eu",
    "/home/adminuser/projects",
    "production SaaS ready",
    "production-ready SaaS",
    "tenant isolation is implemented",
    "tenant isolation implemented",
]

_AGENT_SCRIPTS = [
    "examples/agents/evidence_review_agent.py",
    "examples/agents/approval_guardrail_agent.py",
    "examples/agents/audit_export_agent.py",
    "examples/agents/policy_check_agent.py",
]


class GL155AgentExamplesPackTest(unittest.TestCase):

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _path(self, rel):
        return os.path.join(REPO_ROOT, rel)

    def _read_text(self, rel):
        with open(self._path(rel), encoding="utf-8") as f:
            return f.read()

    def _read_json(self, rel):
        with open(self._path(rel), encoding="utf-8") as f:
            return json.load(f)

    def _run_script(self, rel):
        result = subprocess.run(
            [sys.executable, self._path(rel)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        return result

    def _parse_ast(self, rel):
        source = self._read_text(rel)
        return ast.parse(source)

    # ------------------------------------------------------------------
    # 1. Assert README exists
    # ------------------------------------------------------------------
    def test_readme_exists(self):
        self.assertTrue(os.path.isfile(self._path("examples/agents/README.md")))

    # ------------------------------------------------------------------
    # 2. Assert four scripts exist
    # ------------------------------------------------------------------
    def test_evidence_review_agent_exists(self):
        self.assertTrue(os.path.isfile(self._path("examples/agents/evidence_review_agent.py")))

    def test_approval_guardrail_agent_exists(self):
        self.assertTrue(os.path.isfile(self._path("examples/agents/approval_guardrail_agent.py")))

    def test_audit_export_agent_exists(self):
        self.assertTrue(os.path.isfile(self._path("examples/agents/audit_export_agent.py")))

    def test_policy_check_agent_exists(self):
        self.assertTrue(os.path.isfile(self._path("examples/agents/policy_check_agent.py")))

    # ------------------------------------------------------------------
    # 3. Assert JSON artifact exists and parses
    # ------------------------------------------------------------------
    def test_json_artifact_exists(self):
        self.assertTrue(os.path.isfile(self._path("docs/examples/gl155/agent_examples_pack.json")))

    def test_json_artifact_is_valid_json(self):
        data = self._read_json("docs/examples/gl155/agent_examples_pack.json")
        self.assertIsInstance(data, dict)

    # ------------------------------------------------------------------
    # 4. Assert JSON artifact booleans
    # ------------------------------------------------------------------
    def _artifact(self):
        return self._read_json("docs/examples/gl155/agent_examples_pack.json")

    def test_artifact_issue_id(self):
        self.assertEqual(self._artifact().get("issue_id"), "GL-155")

    def test_artifact_type(self):
        self.assertEqual(self._artifact().get("artifact_type"), "agent_examples_pack")

    def test_artifact_agent_examples_pack_added(self):
        self.assertIs(self._artifact().get("agent_examples_pack_added"), True)

    def test_artifact_examples_agents_readme_added(self):
        self.assertIs(self._artifact().get("examples_agents_readme_added"), True)

    def test_artifact_evidence_review_agent_added(self):
        self.assertIs(self._artifact().get("evidence_review_agent_added"), True)

    def test_artifact_approval_guardrail_agent_added(self):
        self.assertIs(self._artifact().get("approval_guardrail_agent_added"), True)

    def test_artifact_audit_export_agent_added(self):
        self.assertIs(self._artifact().get("audit_export_agent_added"), True)

    def test_artifact_policy_check_agent_added(self):
        self.assertIs(self._artifact().get("policy_check_agent_added"), True)

    def test_artifact_standard_library_only(self):
        self.assertIs(self._artifact().get("standard_library_only"), True)

    def test_artifact_dry_run_default(self):
        self.assertIs(self._artifact().get("dry_run_default"), True)

    def test_artifact_no_external_api_key_required(self):
        self.assertIs(self._artifact().get("no_external_api_key_required"), True)

    def test_artifact_no_network_call_on_import(self):
        self.assertIs(self._artifact().get("no_network_call_on_import"), True)

    def test_artifact_fake_demo_data_only(self):
        self.assertIs(self._artifact().get("fake_demo_data_only"), True)

    def test_artifact_production_code_changed_false(self):
        self.assertIs(self._artifact().get("production_code_changed"), False)

    def test_artifact_backend_src_changed_false(self):
        self.assertIs(self._artifact().get("backend_src_changed"), False)

    def test_artifact_endpoint_api_behavior_changed_false(self):
        self.assertIs(self._artifact().get("endpoint_api_behavior_changed"), False)

    def test_artifact_openapi_changed_false(self):
        self.assertIs(self._artifact().get("openapi_changed"), False)

    def test_artifact_db_schema_changed_false(self):
        self.assertIs(self._artifact().get("db_schema_changed"), False)

    def test_artifact_dependencies_changed_false(self):
        self.assertIs(self._artifact().get("dependencies_changed"), False)

    def test_artifact_sdk_changed_false(self):
        self.assertIs(self._artifact().get("sdk_changed"), False)

    def test_artifact_langgraph_langchain_code_changed_false(self):
        self.assertIs(self._artifact().get("langgraph_langchain_code_changed"), False)

    def test_artifact_github_issue_templates_added_false(self):
        self.assertIs(self._artifact().get("github_issue_templates_added"), False)

    def test_artifact_github_publication_performed_false(self):
        self.assertIs(self._artifact().get("github_publication_performed"), False)

    def test_artifact_git_remotes_changed_false(self):
        self.assertIs(self._artifact().get("git_remotes_changed"), False)

    def test_artifact_git_history_rewritten_false(self):
        self.assertIs(self._artifact().get("git_history_rewritten"), False)

    def test_artifact_secret_history_cleanup_performed_false(self):
        self.assertIs(self._artifact().get("secret_history_cleanup_performed"), False)

    def test_artifact_production_saas_ready_claimed_false(self):
        self.assertIs(self._artifact().get("production_saas_ready_claimed"), False)

    def test_artifact_tenant_isolation_claimed_implemented_false(self):
        self.assertIs(self._artifact().get("tenant_isolation_claimed_implemented"), False)

    def test_artifact_public_github_release_claimed_false(self):
        self.assertIs(self._artifact().get("public_github_release_claimed"), False)

    def test_artifact_uses_real_secrets_false(self):
        self.assertIs(self._artifact().get("uses_real_secrets"), False)

    def test_artifact_uses_real_customer_data_false(self):
        self.assertIs(self._artifact().get("uses_real_customer_data"), False)

    def test_artifact_includes_private_personal_data_false(self):
        self.assertIs(self._artifact().get("includes_private_personal_data"), False)

    def test_artifact_next_issue(self):
        self.assertEqual(
            self._artifact().get("next_issue"),
            "GL-156 GitHub Issue Templates / Feedback Templates",
        )

    # ------------------------------------------------------------------
    # 5. Assert README includes required content
    # ------------------------------------------------------------------
    def test_readme_contains_developer_preview(self):
        text = self._read_text("examples/agents/README.md")
        # README uses table with exact phrase
        self.assertRegex(text, r"Developer Preview")

    def test_readme_contains_not_production_saas(self):
        text = self._read_text("examples/agents/README.md")
        self.assertIn("not a production SaaS", text)

    def test_readme_contains_tenant_isolation_not_implemented(self):
        text = self._read_text("examples/agents/README.md")
        self.assertIn("tenant isolation is not implemented", text)

    def test_readme_contains_no_real_secrets(self):
        text = self._read_text("examples/agents/README.md")
        self.assertIn("No real secrets", text)

    def test_readme_contains_no_real_customer_data(self):
        text = self._read_text("examples/agents/README.md")
        self.assertIn("No real customer data", text)

    def test_readme_contains_no_external_api_key(self):
        text = self._read_text("examples/agents/README.md")
        self.assertIn("no external API key", text)

    def test_readme_contains_evidence_review_command(self):
        text = self._read_text("examples/agents/README.md")
        self.assertIn("python3 examples/agents/evidence_review_agent.py", text)

    def test_readme_contains_approval_guardrail_command(self):
        text = self._read_text("examples/agents/README.md")
        self.assertIn("python3 examples/agents/approval_guardrail_agent.py", text)

    def test_readme_contains_audit_export_command(self):
        text = self._read_text("examples/agents/README.md")
        self.assertIn("python3 examples/agents/audit_export_agent.py", text)

    def test_readme_contains_policy_check_command(self):
        text = self._read_text("examples/agents/README.md")
        self.assertIn("python3 examples/agents/policy_check_agent.py", text)

    # ------------------------------------------------------------------
    # 6. For each script: AST, import safety, main(), run and parse JSON
    # ------------------------------------------------------------------
    def _assert_script_ast_imports_safe(self, rel):
        tree = self._parse_ast(rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    self.assertIn(
                        top,
                        _ALLOWED_STDLIB_MODULES,
                        f"{rel}: import '{alias.name}' is not in allowed stdlib set",
                    )
            elif isinstance(node, ast.ImportFrom):
                top = (node.module or "").split(".")[0]
                if top:
                    self.assertIn(
                        top,
                        _ALLOWED_STDLIB_MODULES,
                        f"{rel}: from-import '{node.module}' is not in allowed stdlib set",
                    )

    def _assert_script_no_network_usage(self, rel):
        source = self._read_text(rel)
        for disallowed in _DISALLOWED_NETWORK_MODULES:
            self.assertNotIn(
                disallowed,
                source,
                f"{rel}: contains disallowed network module '{disallowed}'",
            )

    def _assert_script_no_os_environ_secrets(self, rel):
        source = self._read_text(rel)
        # Disallow os.environ lookups that look like secret retrieval
        if "os.environ.get" in source or "os.environ[" in source:
            self.fail(
                f"{rel}: uses os.environ for secret/key retrieval — not allowed in dry-run examples."
            )

    def _assert_script_has_main(self, rel):
        tree = self._parse_ast(rel)
        has_main = any(
            isinstance(node, ast.FunctionDef) and node.name == "main"
            for node in ast.walk(tree)
        )
        self.assertTrue(has_main, f"{rel}: missing 'main' function")

    def _assert_script_has_name_equals_main(self, rel):
        source = self._read_text(rel)
        self.assertIn('if __name__ == "__main__":', source, f"{rel}: missing __main__ guard")

    def _assert_script_import_safe(self, rel):
        """Import the module without executing main()."""
        spec = importlib.util.spec_from_file_location(
            os.path.basename(rel).replace(".py", ""),
            self._path(rel),
        )
        module = importlib.util.module_from_spec(spec)
        # We exercise the import but do not call module.main()
        loader = importlib.machinery.SourceFileLoader(
            module.__name__, self._path(rel)
        )
        loader.exec_module(module)
        self.assertTrue(module)

    def _assert_script_runnable_json(self, rel):
        result = self._run_script(rel)
        self.assertEqual(
            result.returncode, 0,
            f"{rel}: exited non-zero. stderr: {result.stderr}",
        )
        data = json.loads(result.stdout)
        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("mode"), "dry_run")
        self.assertIs(data.get("developer_preview"), True)
        self.assertIs(data.get("production_saas_ready"), False)
        self.assertIs(data.get("tenant_isolation_implemented"), False)
        self.assertIs(data.get("uses_real_customer_data"), False)
        self.assertIs(data.get("uses_real_secrets"), False)
        self.assertIn("grantlayer_concept", data)

    def _assert_script_no_forbidden_content(self, rel):
        source = self._read_text(rel)
        for pattern in _FORBIDDEN_CONTENT_PATTERNS:
            self.assertNotIn(
                pattern.lower(),
                source.lower(),
                f"{rel}: contains forbidden pattern '{pattern}'",
            )

    def test_evidence_review_agent_compliance(self):
        rel = "examples/agents/evidence_review_agent.py"
        self._assert_script_ast_imports_safe(rel)
        self._assert_script_no_network_usage(rel)
        self._assert_script_no_os_environ_secrets(rel)
        self._assert_script_has_main(rel)
        self._assert_script_has_name_equals_main(rel)
        self._assert_script_import_safe(rel)
        self._assert_script_runnable_json(rel)
        self._assert_script_no_forbidden_content(rel)

    def test_approval_guardrail_agent_compliance(self):
        rel = "examples/agents/approval_guardrail_agent.py"
        self._assert_script_ast_imports_safe(rel)
        self._assert_script_no_network_usage(rel)
        self._assert_script_no_os_environ_secrets(rel)
        self._assert_script_has_main(rel)
        self._assert_script_has_name_equals_main(rel)
        self._assert_script_import_safe(rel)
        self._assert_script_runnable_json(rel)
        self._assert_script_no_forbidden_content(rel)

    def test_audit_export_agent_compliance(self):
        rel = "examples/agents/audit_export_agent.py"
        self._assert_script_ast_imports_safe(rel)
        self._assert_script_no_network_usage(rel)
        self._assert_script_no_os_environ_secrets(rel)
        self._assert_script_has_main(rel)
        self._assert_script_has_name_equals_main(rel)
        self._assert_script_import_safe(rel)
        self._assert_script_runnable_json(rel)
        self._assert_script_no_forbidden_content(rel)

    def test_policy_check_agent_compliance(self):
        rel = "examples/agents/policy_check_agent.py"
        self._assert_script_ast_imports_safe(rel)
        self._assert_script_no_network_usage(rel)
        self._assert_script_no_os_environ_secrets(rel)
        self._assert_script_has_main(rel)
        self._assert_script_has_name_equals_main(rel)
        self._assert_script_import_safe(rel)
        self._assert_script_runnable_json(rel)
        self._assert_script_no_forbidden_content(rel)

    # ------------------------------------------------------------------
    # 8. Scope guard — branch-specific diff
    # ------------------------------------------------------------------
    def test_branch_scope_guard(self):
        """If on gl-155-agent-examples-pack, assert only expected files
        (plus allowed docs) changed. Skip on other branches (e.g. main after merge)."""
        try:
            branch = subprocess.check_output(
                ["git", "branch", "--show-current"],
                cwd=REPO_ROOT, text=True
            ).strip()
        except Exception:
            self.skipTest("Cannot determine current branch; skipping scope guard.")
            return

        if branch != "gl-155-agent-examples-pack":
            self.skipTest(
                f"Not on gl-155-agent-examples-pack (on '{branch}'); "
                "skipping branch-specific diff assertions."
            )
            return

        try:
            diff = subprocess.check_output(
                ["git", "diff", "--name-only", "main"],
                cwd=REPO_ROOT, text=True
            ).strip()
        except Exception as exc:
            self.skipTest(f"Could not compute diff against main: {exc}")
            return

        changed = set(diff.splitlines()) if diff else set()

        expected = {
            "examples/agents/README.md",
            "examples/agents/evidence_review_agent.py",
            "examples/agents/approval_guardrail_agent.py",
            "examples/agents/audit_export_agent.py",
            "examples/agents/policy_check_agent.py",
            "docs/examples/gl155/agent_examples_pack.json",
            "backend/tests/test_gl155_agent_examples_pack.py",
        }

        allowed = {
            "README.md",
            "AGENTS.md",
            "llms.txt",
            "llms-full.txt",
            "docs/agent_quickstart.md",
            "docs/agent_integration_manifest.json",
            "docs/agent_task_contract.md",
            "backend/tests/test_gl154_agent_entry_points_manifest.py",
        }

        forbidden = changed - expected - allowed

        if forbidden:
            self.fail(
                "Forbidden files changed in GL-155 branch scope: "
                + ", ".join(sorted(forbidden))
            )

        prod_changes = [p for p in changed if p.startswith("backend/src/")]
        if prod_changes:
            self.fail(
                "Production backend code must not change in GL-155: "
                + ", ".join(sorted(prod_changes))
            )

        for pattern in (
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
            ".claude/",
            ".github/ISSUE_TEMPLATE/",
            ".github/pull_request_template.md",
            "sdk/python/grantlayer_client.py",
            "examples/langgraph_langchain/grantlayer_agent_example.py",
        ):
            hits = [p for p in changed if p.startswith(pattern) or p == pattern]
            if hits:
                self.fail(
                    f"Scope violation: '{pattern}' files changed: "
                    + ", ".join(sorted(hits))
                )


if __name__ == "__main__":
    unittest.main()
