"""GL-154: validation test for agent-native entry points and manifest.

This test verifies that the GL-154 deliverables exist, are parseable,
and satisfy the acceptance criteria defined in the issue.
"""

import json
import os
import subprocess
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class GL154AgentEntryPointsManifestTest(unittest.TestCase):

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

    # ------------------------------------------------------------------
    # 1. Assert files exist
    # ------------------------------------------------------------------
    def test_agents_md_exists(self):
        self.assertTrue(os.path.isfile(self._path("AGENTS.md")))

    def test_llms_txt_exists(self):
        self.assertTrue(os.path.isfile(self._path("llms.txt")))

    def test_llms_full_txt_exists(self):
        self.assertTrue(os.path.isfile(self._path("llms-full.txt")))

    def test_agent_task_contract_exists(self):
        self.assertTrue(os.path.isfile(self._path("docs/agent_task_contract.md")))

    def test_agent_integration_manifest_exists(self):
        self.assertTrue(os.path.isfile(self._path("docs/agent_integration_manifest.json")))

    def test_agent_quickstart_exists(self):
        self.assertTrue(os.path.isfile(self._path("docs/agent_quickstart.md")))

    def test_gl154_artifact_exists(self):
        self.assertTrue(os.path.isfile(self._path("docs/examples/gl154/agent_entry_points_manifest.json")))

    # ------------------------------------------------------------------
    # 2. Assert both JSON files parse
    # ------------------------------------------------------------------
    def test_agent_integration_manifest_is_valid_json(self):
        data = self._read_json("docs/agent_integration_manifest.json")
        self.assertIsInstance(data, dict)

    def test_gl154_artifact_is_valid_json(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIsInstance(data, dict)

    # ------------------------------------------------------------------
    # 3. Assert docs/agent_integration_manifest.json keys
    # ------------------------------------------------------------------
    def test_manifest_project(self):
        data = self._read_json("docs/agent_integration_manifest.json")
        self.assertEqual(data.get("project"), "GrantLayer")

    def test_manifest_status(self):
        data = self._read_json("docs/agent_integration_manifest.json")
        self.assertEqual(data.get("status"), "developer_preview")

    def test_manifest_production_saas_ready_false(self):
        data = self._read_json("docs/agent_integration_manifest.json")
        self.assertIs(data.get("production_saas_ready"), False)

    def test_manifest_tenant_isolation_false(self):
        data = self._read_json("docs/agent_integration_manifest.json")
        self.assertIs(data.get("tenant_isolation_implemented"), False)

    def test_manifest_public_github_release_false(self):
        data = self._read_json("docs/agent_integration_manifest.json")
        self.assertIs(data.get("public_github_release_completed"), False)

    def test_manifest_license(self):
        data = self._read_json("docs/agent_integration_manifest.json")
        self.assertEqual(data.get("license"), "Apache-2.0")

    def test_manifest_local_first_true(self):
        data = self._read_json("docs/agent_integration_manifest.json")
        self.assertIs(data.get("local_first"), True)

    def test_manifest_external_api_key_false(self):
        data = self._read_json("docs/agent_integration_manifest.json")
        self.assertIs(data.get("external_api_key_required_for_quickstart"), False)

    def test_manifest_real_customer_data_false(self):
        data = self._read_json("docs/agent_integration_manifest.json")
        self.assertIs(data.get("real_customer_data_required"), False)

    def test_manifest_next_issue(self):
        data = self._read_json("docs/agent_integration_manifest.json")
        self.assertEqual(data.get("next_issue"), "GL-155 Agent Examples Pack")

    # ------------------------------------------------------------------
    # 4. Assert GL-154 artifact booleans
    # ------------------------------------------------------------------
    def test_gl154_agents_md_added(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("agents_md_added"), True)

    def test_gl154_llms_txt_added(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("llms_txt_added"), True)

    def test_gl154_llms_full_txt_added(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("llms_full_txt_added"), True)

    def test_gl154_agent_task_contract_added(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("agent_task_contract_added"), True)

    def test_gl154_agent_integration_manifest_added(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("agent_integration_manifest_added"), True)

    def test_gl154_agent_quickstart_added(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("agent_quickstart_added"), True)

    def test_gl154_readme_section_added(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("readme_ai_coding_agents_section_added"), True)

    def test_gl154_runtime_examples_not_added(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("runtime_agent_examples_added"), False)

    def test_gl154_github_issue_templates_not_added(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("github_issue_templates_added"), False)

    def test_gl154_production_code_not_changed(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("production_code_changed"), False)

    def test_gl154_backend_src_not_changed(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("backend_src_changed"), False)

    def test_gl154_endpoint_api_not_changed(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("endpoint_api_behavior_changed"), False)

    def test_gl154_openapi_not_changed(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("openapi_changed"), False)

    def test_gl154_db_schema_not_changed(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("db_schema_changed"), False)

    def test_gl154_dependencies_not_changed(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("dependencies_changed"), False)

    def test_gl154_sdk_not_changed(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("sdk_changed"), False)

    def test_gl154_langgraph_langchain_not_changed(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("langgraph_langchain_example_changed"), False)

    def test_gl154_production_saas_not_claimed(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("production_saas_ready_claimed"), False)

    def test_gl154_tenant_isolation_not_claimed(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("tenant_isolation_claimed_implemented"), False)

    def test_gl154_public_release_not_claimed(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("public_github_release_claimed"), False)

    def test_gl154_uses_real_secrets_false(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("uses_real_secrets"), False)

    def test_gl154_uses_real_customer_data_false(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("uses_real_customer_data"), False)

    def test_gl154_includes_private_personal_data_false(self):
        data = self._read_json("docs/examples/gl154/agent_entry_points_manifest.json")
        self.assertIs(data.get("includes_private_personal_data"), False)

    # ------------------------------------------------------------------
    # 5. Assert AGENTS.md content
    # ------------------------------------------------------------------
    def test_agents_md_contains_developer_preview(self):
        text = self._read_text("AGENTS.md")
        self.assertIn("Developer Preview", text)

    def test_agents_md_contains_not_production_saas(self):
        text = self._read_text("AGENTS.md")
        self.assertIn("not a production SaaS", text)

    def test_agents_md_contains_tenant_isolation_not_implemented(self):
        text = self._read_text("AGENTS.md")
        self.assertIn("tenant isolation is not implemented", text)

    def test_agents_md_contains_no_real_secrets(self):
        text = self._read_text("AGENTS.md")
        self.assertIn("no real secrets", text)

    def test_agents_md_contains_no_real_customer_data(self):
        text = self._read_text("AGENTS.md")
        self.assertIn("no real customer data", text)

    def test_agents_md_contains_claude_dir(self):
        text = self._read_text("AGENTS.md")
        self.assertIn(".claude/", text)

    def test_agents_md_contains_full_suite_script(self):
        text = self._read_text("AGENTS.md")
        self.assertIn("scripts/run-full-backend-suite.sh", text)

    def test_agents_md_contains_security_boundary_command(self):
        text = self._read_text("AGENTS.md")
        self.assertIn("python3 -m unittest backend.tests.test_security_boundary_regression -v", text)

    def test_agents_md_contains_gl155(self):
        text = self._read_text("AGENTS.md")
        self.assertIn("GL-155", text)

    # ------------------------------------------------------------------
    # 6. Assert llms.txt and llms-full.txt content
    # ------------------------------------------------------------------
    def test_llms_txt_contains_agents_md(self):
        text = self._read_text("llms.txt")
        self.assertIn("AGENTS.md", text)

    def test_llms_txt_contains_agent_quickstart(self):
        text = self._read_text("llms.txt")
        self.assertIn("docs/agent_quickstart.md", text)

    def test_llms_txt_contains_agent_task_contract(self):
        text = self._read_text("llms.txt")
        self.assertIn("docs/agent_task_contract.md", text)

    def test_llms_txt_contains_sdk_readme(self):
        text = self._read_text("llms.txt")
        self.assertIn("sdk/python/README.md", text)

    def test_llms_txt_contains_langgraph_docs(self):
        text = self._read_text("llms.txt")
        self.assertIn("docs/langgraph_langchain_integration_example.md", text)

    def test_llms_txt_contains_not_production_saas(self):
        text = self._read_text("llms.txt")
        self.assertIn("not a production SaaS", text)

    def test_llms_txt_contains_tenant_isolation_not_implemented(self):
        text = self._read_text("llms.txt")
        self.assertIn("tenant isolation is not implemented", text)

    def test_llms_full_txt_contains_agents_md(self):
        text = self._read_text("llms-full.txt")
        self.assertIn("AGENTS.md", text)

    def test_llms_full_txt_contains_agent_quickstart(self):
        text = self._read_text("llms-full.txt")
        self.assertIn("docs/agent_quickstart.md", text)

    def test_llms_full_txt_contains_agent_task_contract(self):
        text = self._read_text("llms-full.txt")
        self.assertIn("docs/agent_task_contract.md", text)

    def test_llms_full_txt_contains_sdk_readme(self):
        text = self._read_text("llms-full.txt")
        self.assertIn("sdk/python/README.md", text)

    def test_llms_full_txt_contains_langgraph_docs(self):
        text = self._read_text("llms-full.txt")
        self.assertIn("docs/langgraph_langchain_integration_example.md", text)

    def test_llms_full_txt_contains_not_production_saas(self):
        text = self._read_text("llms-full.txt")
        self.assertIn("not a production SaaS", text)

    def test_llms_full_txt_contains_tenant_isolation_not_implemented(self):
        text = self._read_text("llms-full.txt")
        self.assertIn("tenant isolation is not implemented", text)

    # ------------------------------------------------------------------
    # 7. Assert README contains For AI Coding Agents section
    # ------------------------------------------------------------------
    def test_readme_contains_for_ai_coding_agents(self):
        text = self._read_text("README.md")
        self.assertIn("For AI Coding Agents", text)

    def test_readme_contains_agents_md(self):
        text = self._read_text("README.md")
        self.assertIn("AGENTS.md", text)

    def test_readme_contains_llms_txt(self):
        text = self._read_text("README.md")
        self.assertIn("llms.txt", text)

    def test_readme_contains_llms_full_txt(self):
        text = self._read_text("README.md")
        self.assertIn("llms-full.txt", text)

    def test_readme_contains_agent_quickstart(self):
        text = self._read_text("README.md")
        self.assertIn("docs/agent_quickstart.md", text)

    def test_readme_contains_agent_integration_manifest(self):
        text = self._read_text("README.md")
        self.assertIn("docs/agent_integration_manifest.json", text)

    def test_readme_contains_gl155(self):
        text = self._read_text("README.md")
        self.assertIn("GL-155", text)

    # ------------------------------------------------------------------
    # 8. Assert docs/agent_task_contract.md disposition values
    # ------------------------------------------------------------------
    def test_task_contract_contains_ready_for_merge(self):
        text = self._read_text("docs/agent_task_contract.md")
        self.assertIn("ready_for_merge", text)

    def test_task_contract_contains_merged_done(self):
        text = self._read_text("docs/agent_task_contract.md")
        self.assertIn("merged_done", text)

    def test_task_contract_contains_blocked(self):
        text = self._read_text("docs/agent_task_contract.md")
        self.assertIn("blocked", text)

    def test_task_contract_contains_needs_manual_review(self):
        text = self._read_text("docs/agent_task_contract.md")
        self.assertIn("needs_manual_review", text)

    def test_task_contract_contains_provider_timeout(self):
        text = self._read_text("docs/agent_task_contract.md")
        self.assertIn("provider_timeout_recovery_needed", text)

    # ------------------------------------------------------------------
    # 9. Assert no runtime agent examples were added
    # ------------------------------------------------------------------
    def test_no_examples_agents_directory(self):
        examples_agents = self._path("examples/agents")
        self.assertFalse(os.path.exists(examples_agents),
                         "examples/agents directory must not exist in GL-154")

    # ------------------------------------------------------------------
    # 10 & 11. Scope guard — branch-specific diff
    # ------------------------------------------------------------------
    def test_branch_scope_guard(self):
        """If on gl-154-agents-llms-agent-manifest, assert only expected files
        (plus allowed docs) changed. Skip on other branches (e.g. main after merge)."""
        try:
            branch = subprocess.check_output(
                ["git", "branch", "--show-current"],
                cwd=REPO_ROOT, text=True
            ).strip()
        except Exception:
            self.skipTest("Cannot determine current branch; skipping scope guard.")
            return

        if branch != "gl-154-agents-llms-agent-manifest":
            self.skipTest(
                f"Not on gl-154-agents-llms-agent-manifest (on '{branch}'); "
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
            "AGENTS.md",
            "llms.txt",
            "llms-full.txt",
            "docs/agent_task_contract.md",
            "docs/agent_integration_manifest.json",
            "docs/agent_quickstart.md",
            "README.md",
            "docs/examples/gl154/agent_entry_points_manifest.json",
            "backend/tests/test_gl154_agent_entry_points_manifest.py",
        }

        allowed = {
            "CONTRIBUTING.md",
            "SECURITY.md",
            "docs/public_github_readiness_pack.md",
            "docs/first_developer_feedback_log.md",
            "docs/ten_minute_quickstart.md",
            "sdk/python/README.md",
            "docs/langgraph_langchain_integration_example.md",
            "backend/tests/test_gl153_license_contributing_security_decision.py",
        }

        forbidden = (
            changed - expected - allowed
        )

        if forbidden:
            self.fail(
                "Forbidden files changed in GL-154 branch scope: "
                + ", ".join(sorted(forbidden))
            )

        # Assert no production backend src files changed
        prod_changes = [p for p in changed if p.startswith("backend/src/")]
        if prod_changes:
            self.fail(
                "Production backend code must not change in GL-154: "
                + ", ".join(sorted(prod_changes))
            )

        # Assert no openapi, migrations, dependency files, SDK code, LangGraph code
        for pattern in (
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
