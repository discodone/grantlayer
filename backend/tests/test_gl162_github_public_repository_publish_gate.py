"""GL-162 GitHub Public Repository Metadata / Publish Gate — validation tests."""

import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "docs" / "github_public_repository_publish_gate.md"
JSON_PATH = REPO_ROOT / "docs" / "examples" / "gl162" / "github_public_repository_publish_gate.json"
TEST_PATH = REPO_ROOT / "backend" / "tests" / "test_gl162_github_public_repository_publish_gate.py"
GL162_BRANCH = "gl-162-github-public-repository-publish-gate"


def _load_json():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_doc():
    return DOC_PATH.read_text(encoding="utf-8")


def _current_branch():
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    return result.stdout.strip()


def _branch_diff_names():
    result = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    return result.stdout.strip().splitlines()


class TestGL162FilesExist(unittest.TestCase):
    def test_publish_gate_document_exists(self):
        self.assertTrue(DOC_PATH.exists(), f"Missing: {DOC_PATH}")

    def test_json_artifact_exists(self):
        self.assertTrue(JSON_PATH.exists(), f"Missing: {JSON_PATH}")

    def test_validation_test_exists(self):
        self.assertTrue(TEST_PATH.exists(), f"Missing: {TEST_PATH}")


class TestGL162JsonArtifact(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()

    def test_issue_id(self):
        self.assertEqual(self.data["issue_id"], "GL-162")

    def test_artifact_type(self):
        self.assertEqual(self.data["artifact_type"], "github_public_repository_publish_gate")

    def test_publish_gate_document_added(self):
        self.assertTrue(self.data["publish_gate_document_added"])

    def test_validation_test_added(self):
        self.assertTrue(self.data["validation_test_added"])

    def test_repository_metadata_defined(self):
        self.assertTrue(self.data["repository_metadata_defined"])

    def test_recommended_repository_name(self):
        self.assertEqual(self.data["recommended_repository_name"], "grantlayer")

    def test_alternative_repository_name(self):
        self.assertEqual(self.data["alternative_repository_name"], "grantlayer-mvp")

    def test_short_description(self):
        self.assertEqual(
            self.data["recommended_short_description"],
            "Developer-preview verification and audit layer for agentic grant workflows.",
        )

    def test_license_metadata(self):
        self.assertEqual(self.data["license_metadata"], "Apache-2.0")

    def test_visibility_requires_manual_approval(self):
        self.assertTrue(self.data["visibility_requires_manual_approval"])

    def test_manual_approval_phrase_defined(self):
        self.assertTrue(self.data["manual_approval_phrase_defined"])

    def test_manual_approval_phrase_exact(self):
        self.assertEqual(
            self.data["manual_approval_phrase"],
            "I approve publishing the clean GrantLayer developer-preview snapshot to public GitHub.",
        )

    def test_clean_snapshot_required_by_gl160(self):
        self.assertTrue(self.data["clean_public_snapshot_required_by_gl160"])

    def test_clean_snapshot_build_required_by_gl161(self):
        self.assertTrue(self.data["clean_public_snapshot_build_required_by_gl161"])

    def test_pre_publication_security_fixes_required_by_gl162a(self):
        self.assertTrue(self.data["pre_publication_security_fixes_required_by_gl162a"])

    def test_gl162a_security_fixes(self):
        fixes = self.data["gl162a_security_fixes"]
        self.assertIsInstance(fixes, dict)
        self.assertTrue(fixes["scan_gate_self_exclusion_resolved"])
        self.assertTrue(fixes["public_scanner_clean"])
        self.assertTrue(fixes["internal_forge_hostname_removed_from_public_files"])
        self.assertTrue(fixes["claude_directory_ignored"])
        self.assertTrue(fixes["http_security_headers_added"])
        self.assertTrue(fixes["reverse_proxy_rate_limit_resolver_added"])
        self.assertTrue(fixes["grant_role_allowlist_added"])

    def test_full_history_publication_forbidden(self):
        self.assertFalse(self.data["full_history_publication_allowed"])

    def test_suggested_topics_present(self):
        topics = self.data["suggested_topics"]
        self.assertIsInstance(topics, list)
        self.assertGreaterEqual(len(topics), 5)
        for expected in [
            "grant-management", "audit-trail", "compliance",
            "agentic-workflows", "developer-preview",
        ]:
            self.assertIn(expected, topics)

    def test_agent_entrypoints_present(self):
        ep = self.data["agent_entrypoints"]
        self.assertIsInstance(ep, list)
        for expected in [
            "README.md", "AGENTS.md", "llms.txt", "llms-full.txt",
            "docs/agent_quickstart.md", "docs/agent_task_contract.md",
            "docs/agent_integration_manifest.json", "examples/agents/", "sdk/python/",
        ]:
            self.assertIn(expected, ep)

    def test_github_settings_checklist_present(self):
        checklist = self.data["github_settings_checklist"]
        self.assertIsInstance(checklist, list)
        self.assertGreaterEqual(len(checklist), 5)

    def test_publish_gate_checklist_present(self):
        checklist = self.data["publish_gate_checklist"]
        self.assertIsInstance(checklist, list)
        self.assertGreaterEqual(len(checklist), 10)

    def test_gl163_handoff_inputs_present(self):
        handoff = self.data["gl163_handoff_inputs"]
        self.assertIsInstance(handoff, list)
        self.assertGreaterEqual(len(handoff), 3)

    def test_next_issue(self):
        self.assertIn("GL-163", self.data["next_issue"])

    # --- Safety booleans: must be False ---

    def test_github_publication_not_performed(self):
        self.assertFalse(self.data["github_publication_performed"])

    def test_public_repo_not_created(self):
        self.assertFalse(self.data["public_repo_created"])

    def test_mirror_repo_not_created_on_remote(self):
        self.assertFalse(self.data["mirror_repo_created_on_remote"])

    def test_github_api_not_called(self):
        self.assertFalse(self.data["github_api_called"])

    def test_live_github_issues_not_created(self):
        self.assertFalse(self.data["live_github_issues_created"])

    def test_git_remotes_not_changed(self):
        self.assertFalse(self.data["git_remotes_changed"])

    def test_github_remote_not_added(self):
        self.assertFalse(self.data["github_remote_added"])

    def test_not_pushed_to_github(self):
        self.assertFalse(self.data["pushed_to_github"])

    def test_history_rewrite_not_performed(self):
        self.assertFalse(self.data["history_rewrite_performed"])

    def test_git_filter_repo_not_run(self):
        self.assertFalse(self.data["git_filter_repo_run"])

    def test_bfg_not_run(self):
        self.assertFalse(self.data["bfg_run"])

    def test_commits_not_deleted(self):
        self.assertFalse(self.data["commits_deleted"])

    def test_secret_history_cleanup_not_performed(self):
        self.assertFalse(self.data["secret_history_cleanup_performed"])

    def test_secrets_not_rotated(self):
        self.assertFalse(self.data["secrets_rotated"])

    def test_full_history_clean_not_claimed(self):
        self.assertFalse(self.data["full_history_clean_claimed"])

    def test_production_code_not_changed(self):
        self.assertFalse(self.data["production_code_changed"])

    def test_backend_src_not_changed(self):
        self.assertFalse(self.data["backend_src_changed"])

    def test_endpoint_api_behavior_not_changed(self):
        self.assertFalse(self.data["endpoint_api_behavior_changed"])

    def test_openapi_not_changed(self):
        self.assertFalse(self.data["openapi_changed"])

    def test_db_schema_not_changed(self):
        self.assertFalse(self.data["db_schema_changed"])

    def test_dependencies_not_changed(self):
        self.assertFalse(self.data["dependencies_changed"])

    def test_sdk_not_changed(self):
        self.assertFalse(self.data["sdk_changed"])

    def test_langgraph_langchain_not_changed(self):
        self.assertFalse(self.data["langgraph_langchain_code_changed"])

    def test_runtime_agent_examples_not_changed(self):
        self.assertFalse(self.data["runtime_agent_examples_changed"])

    def test_frontend_website_design_not_changed(self):
        self.assertFalse(self.data["frontend_website_design_changed"])

    def test_production_saas_not_claimed(self):
        self.assertFalse(self.data["production_saas_ready_claimed"])

    def test_tenant_isolation_not_claimed(self):
        self.assertFalse(self.data["tenant_isolation_claimed_implemented"])

    def test_public_github_release_not_claimed(self):
        self.assertFalse(self.data["public_github_release_claimed"])

    def test_no_real_secrets(self):
        self.assertFalse(self.data["uses_real_secrets"])

    def test_no_real_customer_data(self):
        self.assertFalse(self.data["uses_real_customer_data"])

    def test_no_private_personal_data(self):
        self.assertFalse(self.data["includes_private_personal_data"])

    # --- Validation gates ---

    def test_validation_gates_present(self):
        gates = self.data["validation_gates"]
        self.assertIsInstance(gates, dict)
        self.assertGreaterEqual(len(gates), 20)

    def test_validation_gates_safety_booleans(self):
        gates = self.data["validation_gates"]
        must_be_false = [
            "github_publication_performed", "public_repo_created",
            "mirror_repo_created_on_remote", "github_api_called",
            "live_github_issues_created", "git_remotes_changed",
            "github_remote_added", "pushed_to_github",
            "history_rewrite_performed", "git_filter_repo_run",
            "bfg_run", "commits_deleted", "secret_history_cleanup_performed",
            "secrets_rotated", "full_history_clean_claimed",
            "production_code_changed", "backend_src_changed",
            "production_saas_ready_claimed", "tenant_isolation_claimed_implemented",
            "public_github_release_claimed", "uses_real_secrets",
            "uses_real_customer_data", "includes_private_personal_data",
        ]
        for key in must_be_false:
            self.assertFalse(gates.get(key), f"validation_gates[{key!r}] must be False")


class TestGL162DocContent(unittest.TestCase):
    def setUp(self):
        self.doc = _load_doc()

    def test_developer_preview_status(self):
        self.assertIn("Developer Preview", self.doc)

    def test_publish_gate_only(self):
        self.assertIn("publish gate only", self.doc)

    def test_not_production_saas(self):
        self.assertIn("not production saas", self.doc.lower())

    def test_tenant_isolation_not_implemented(self):
        self.assertIn("Tenant isolation is not implemented", self.doc)

    def test_no_real_secrets(self):
        self.assertIn("No real secrets", self.doc)

    def test_no_real_customer_data(self):
        self.assertIn("No real customer data", self.doc)

    def test_clean_public_snapshot(self):
        self.assertIn("clean public snapshot", self.doc)

    def test_full_internal_git_history_not_published(self):
        self.assertIn("full internal git history is not published", self.doc.lower())

    def test_manual_approval_required(self):
        self.assertIn("Manual approval required", self.doc)

    def test_exact_approval_phrase(self):
        self.assertIn(
            "I approve publishing the clean GrantLayer developer-preview snapshot to public GitHub.",
            self.doc,
        )

    def test_gl163_handoff(self):
        self.assertIn("GL-163 Post-Public Agent Intake & First Feedback Triage", self.doc)

    def test_no_github_publication(self):
        self.assertIn("no github publication", self.doc.lower())

    def test_no_github_api(self):
        self.assertIn("no github api", self.doc.lower())

    def test_no_repo_creation(self):
        self.assertIn("create a github repository", self.doc.lower())

    def test_no_history_rewrite(self):
        self.assertIn("rewrite git history", self.doc.lower())

    def test_repository_name_grantlayer(self):
        self.assertIn("grantlayer", self.doc)

    def test_repository_name_grantlayer_mvp(self):
        self.assertIn("grantlayer-mvp", self.doc)

    def test_short_description(self):
        self.assertIn(
            "Developer-preview verification and audit layer for agentic grant workflows.",
            self.doc,
        )

    def test_license_apache(self):
        self.assertIn("Apache-2.0", self.doc)

    def test_suggested_topics_present(self):
        for topic in [
            "grant-management", "audit-trail", "compliance",
            "agentic-workflows", "developer-preview",
        ]:
            self.assertIn(topic, self.doc)

    def test_agent_entrypoints_readme(self):
        self.assertIn("README.md", self.doc)

    def test_agent_entrypoints_agents_md(self):
        self.assertIn("AGENTS.md", self.doc)

    def test_agent_entrypoints_llms_txt(self):
        self.assertIn("llms.txt", self.doc)

    def test_agent_entrypoints_llms_full_txt(self):
        self.assertIn("llms-full.txt", self.doc)

    def test_agent_entrypoints_quickstart(self):
        self.assertIn("docs/agent_quickstart.md", self.doc)

    def test_agent_entrypoints_task_contract(self):
        self.assertIn("docs/agent_task_contract.md", self.doc)

    def test_agent_entrypoints_manifest(self):
        self.assertIn("docs/agent_integration_manifest.json", self.doc)

    def test_agent_entrypoints_examples(self):
        self.assertIn("examples/agents/", self.doc)

    def test_agent_entrypoints_sdk(self):
        self.assertIn("sdk/python/", self.doc)

    def test_publish_gate_checklist_present(self):
        self.assertIn("Publish Gate Checklist", self.doc)

    def test_gl162a_security_readiness_scan_gate(self):
        self.assertIn("scan-gate self-exclusion", self.doc.lower())

    def test_gl162a_security_readiness_scanner_clean(self):
        self.assertIn("public scanner clean", self.doc.lower())

    def test_gl162a_security_readiness_forge_hostname(self):
        self.assertIn("internal forgejo hostname removed from public files", self.doc.lower())

    def test_gl162a_security_readiness_claude_ignored(self):
        # Doc uses markdown backtick notation: `.claude/` ignored
        self.assertIn("`.claude/` ignored", self.doc.lower())

    def test_gl162a_security_readiness_http_headers(self):
        self.assertIn("http security headers", self.doc.lower())

    def test_gl162a_security_readiness_reverse_proxy(self):
        self.assertIn("reverse-proxy-aware rate-limit ip resolver", self.doc.lower())

    def test_gl162a_security_readiness_role_allowlist(self):
        self.assertIn("grant role allowlist", self.doc.lower())

    def test_abort_rollback_procedure_present(self):
        self.assertIn("Abort", self.doc)
        self.assertIn("Rollback", self.doc)


class TestGL162NoForbiddenContent(unittest.TestCase):
    def _combined(self):
        content = _load_doc()
        with open(JSON_PATH, encoding="utf-8") as f:
            content += f.read()
        return content

    def test_no_home_adminuser(self):
        self.assertNotIn("/home/adminuser", self._combined())

    def test_no_home_oai(self):
        self.assertNotIn("/home/oai", self._combined())

    def test_no_mnt_data(self):
        self.assertNotIn("/mnt/data", self._combined())

    def test_no_private_key_marker(self):
        # Strings are split to avoid triggering the GL-136 key-hygiene scan
        _rsa = "-----BEGIN RSA PRIVATE" + " KEY-----"
        _openssh = "-----BEGIN OPENSSH PRIVATE" + " KEY-----"
        _ec = "-----BEGIN EC PRIVATE" + " KEY-----"
        combined = self._combined()
        self.assertNotIn(_rsa, combined)
        self.assertNotIn(_openssh, combined)
        self.assertNotIn(_ec, combined)

    def test_no_internal_forge_hostname(self):
        self.assertNotIn("forge.hofercloud.eu", self._combined())

    def test_no_internal_ip_range(self):
        combined = self._combined()
        self.assertNotIn("192.168.2.", combined)
        self.assertNotIn("100.109.", combined)


class TestGL162ScopeGuard(unittest.TestCase):
    def _on_gl162_branch(self):
        return _current_branch() == GL162_BRANCH

    def test_no_backend_src_changes(self):
        if not self._on_gl162_branch():
            self.skipTest("Not on GL-162 branch; skipping diff-based scope guard.")
        changed = _branch_diff_names()
        for path in changed:
            self.assertFalse(
                path.startswith("backend/src/"),
                f"Forbidden: backend/src/ change detected: {path}",
            )

    def test_no_openapi_changes(self):
        if not self._on_gl162_branch():
            self.skipTest("Not on GL-162 branch; skipping diff-based scope guard.")
        changed = _branch_diff_names()
        for path in changed:
            self.assertFalse(
                "openapi" in path.lower(),
                f"Forbidden: OpenAPI change detected: {path}",
            )

    def test_no_migration_changes(self):
        if not self._on_gl162_branch():
            self.skipTest("Not on GL-162 branch; skipping diff-based scope guard.")
        changed = _branch_diff_names()
        for path in changed:
            self.assertFalse(
                "migration" in path.lower() or path.startswith("alembic/"),
                f"Forbidden: migration change detected: {path}",
            )

    def test_no_dependency_file_changes(self):
        if not self._on_gl162_branch():
            self.skipTest("Not on GL-162 branch; skipping diff-based scope guard.")
        forbidden = {
            "requirements.txt", "requirements-dev.txt",
            "pyproject.toml", "setup.py", "Pipfile", "poetry.lock",
        }
        changed = set(_branch_diff_names())
        overlap = forbidden & changed
        self.assertFalse(overlap, f"Forbidden: dependency file(s) changed: {overlap}")

    def test_no_sdk_implementation_changes(self):
        if not self._on_gl162_branch():
            self.skipTest("Not on GL-162 branch; skipping diff-based scope guard.")
        changed = _branch_diff_names()
        for path in changed:
            self.assertFalse(
                path == "sdk/python/grantlayer_client.py",
                f"Forbidden: SDK implementation change detected: {path}",
            )

    def test_no_langgraph_langchain_changes(self):
        if not self._on_gl162_branch():
            self.skipTest("Not on GL-162 branch; skipping diff-based scope guard.")
        changed = _branch_diff_names()
        for path in changed:
            self.assertFalse(
                "langgraph" in path.lower() or "langchain" in path.lower(),
                f"Forbidden: LangGraph/LangChain change detected: {path}",
            )

    def test_no_runtime_agent_example_changes(self):
        if not self._on_gl162_branch():
            self.skipTest("Not on GL-162 branch; skipping diff-based scope guard.")
        changed = _branch_diff_names()
        for path in changed:
            self.assertFalse(
                path.startswith("examples/agents/"),
                f"Forbidden: runtime agent example change detected: {path}",
            )

    def test_no_frontend_website_design_changes(self):
        if not self._on_gl162_branch():
            self.skipTest("Not on GL-162 branch; skipping diff-based scope guard.")
        changed = _branch_diff_names()
        for path in changed:
            self.assertFalse(
                path.startswith("frontend/") or path.startswith("website/") or path.startswith("design/"),
                f"Forbidden: frontend/website/design change detected: {path}",
            )

    def test_no_claude_config_changes(self):
        if not self._on_gl162_branch():
            self.skipTest("Not on GL-162 branch; skipping diff-based scope guard.")
        changed = _branch_diff_names()
        for path in changed:
            self.assertFalse(
                path.startswith(".claude/"),
                f"Forbidden: .claude/ change detected: {path}",
            )

    def test_no_github_action_publishing_changes(self):
        if not self._on_gl162_branch():
            self.skipTest("Not on GL-162 branch; skipping diff-based scope guard.")
        changed = _branch_diff_names()
        for path in changed:
            self.assertFalse(
                path.startswith(".github/workflows/"),
                f"Forbidden: GitHub Actions workflow change detected: {path}",
            )

    def test_expected_files_are_within_scope(self):
        if not self._on_gl162_branch():
            self.skipTest("Not on GL-162 branch; skipping diff-based scope guard.")
        allowed_prefixes = (
            "docs/github_public_repository_publish_gate.md",
            "docs/examples/gl162/",
            "backend/tests/test_gl162_",
            "README.md",
            "SECURITY.md",
            "CONTRIBUTING.md",
            "AGENTS.md",
            "docs/clean_public_snapshot_build.md",
            "docs/public_github_go_no_go_decision.md",
            "docs/github_private_mirror_dry_run.md",
            ".github/pull_request_template.md",
        )
        changed = _branch_diff_names()
        for path in changed:
            allowed = any(path == prefix or path.startswith(prefix) for prefix in allowed_prefixes)
            self.assertTrue(
                allowed,
                f"Unexpected file in GL-162 branch diff: {path}. "
                f"Only expected GL-162 artifacts and allowed docs should be changed.",
            )


if __name__ == "__main__":
    unittest.main()
