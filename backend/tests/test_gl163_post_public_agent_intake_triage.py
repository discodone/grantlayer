"""GL-163 Post-Public Agent Intake & First Feedback Triage — validation tests."""

import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "docs" / "post_public_agent_intake_triage.md"
JSON_PATH = REPO_ROOT / "docs" / "examples" / "gl163" / "post_public_agent_intake_triage.json"
TEST_PATH = REPO_ROOT / "backend" / "tests" / "test_gl163_post_public_agent_intake_triage.py"
GL163_BRANCH = "gl-163-post-public-agent-intake-triage"


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


# ---------------------------------------------------------------------------
# 1. Files exist
# ---------------------------------------------------------------------------

class TestGL163FilesExist(unittest.TestCase):

    def test_markdown_document_exists(self):
        self.assertTrue(DOC_PATH.exists(), f"Missing: {DOC_PATH}")

    def test_json_artifact_exists(self):
        self.assertTrue(JSON_PATH.exists(), f"Missing: {JSON_PATH}")

    def test_test_file_exists(self):
        self.assertTrue(TEST_PATH.exists(), f"Missing: {TEST_PATH}")


# ---------------------------------------------------------------------------
# 2. JSON artifact — parses and required keys
# ---------------------------------------------------------------------------

class TestGL163JsonParses(unittest.TestCase):

    def test_json_parses(self):
        data = _load_json()
        self.assertIsInstance(data, dict)


class TestGL163JsonRequiredKeys(unittest.TestCase):

    def setUp(self):
        self.data = _load_json()

    def test_issue_key(self):
        self.assertIn("issue", self.data)

    def test_title_key(self):
        self.assertIn("title", self.data)

    def test_status_key(self):
        self.assertIn("status", self.data)

    def test_public_repository_key(self):
        self.assertIn("publicRepository", self.data)

    def test_public_head_at_planning_key(self):
        self.assertIn("publicHeadAtPlanning", self.data)

    def test_source_of_truth_key(self):
        self.assertIn("sourceOfTruth", self.data)

    def test_public_snapshot_model_key(self):
        self.assertIn("publicSnapshotModel", self.data)

    def test_direct_public_edits_allowed_key(self):
        self.assertIn("directPublicEditsAllowed", self.data)

    def test_triage_categories_key(self):
        self.assertIn("triageCategories", self.data)

    def test_severity_model_key(self):
        self.assertIn("severityModel", self.data)

    def test_first_week_checklist_key(self):
        self.assertIn("firstWeekChecklist", self.data)

    def test_public_update_workflow_key(self):
        self.assertIn("publicUpdateWorkflow", self.data)

    def test_no_go_criteria_key(self):
        self.assertIn("noGoCriteria", self.data)

    def test_caveats_key(self):
        self.assertIn("caveats", self.data)


# ---------------------------------------------------------------------------
# 3. JSON artifact — value assertions
# ---------------------------------------------------------------------------

class TestGL163JsonValues(unittest.TestCase):

    def setUp(self):
        self.data = _load_json()

    def test_issue_is_gl163(self):
        self.assertEqual(self.data["issue"], "GL-163")

    def test_status_is_developer_preview_post_public_triage(self):
        self.assertEqual(self.data["status"], "developer-preview-post-public-triage")

    def test_public_repository_url(self):
        self.assertEqual(
            self.data["publicRepository"],
            "https://github.com/discodone/grantlayer",
        )

    def test_source_of_truth_is_internal_forgejo(self):
        self.assertEqual(self.data["sourceOfTruth"], "internal-forgejo")

    def test_direct_public_edits_emergency_only(self):
        self.assertEqual(self.data["directPublicEditsAllowed"], "emergency-only")

    def test_public_snapshot_model_true(self):
        self.assertTrue(self.data["publicSnapshotModel"])

    def test_triage_categories_is_list(self):
        self.assertIsInstance(self.data["triageCategories"], list)

    def test_severity_model_has_p0(self):
        self.assertIn("P0", self.data["severityModel"])

    def test_severity_model_has_p1(self):
        self.assertIn("P1", self.data["severityModel"])

    def test_severity_model_has_p2(self):
        self.assertIn("P2", self.data["severityModel"])

    def test_severity_model_has_p3(self):
        self.assertIn("P3", self.data["severityModel"])

    def test_first_week_checklist_is_list(self):
        self.assertIsInstance(self.data["firstWeekChecklist"], list)
        self.assertGreaterEqual(len(self.data["firstWeekChecklist"]), 5)

    def test_public_update_workflow_includes_internal_issue(self):
        workflow = self.data["publicUpdateWorkflow"]
        self.assertTrue(
            any("internal-issue" in step or "internal_issue" in step for step in workflow),
            "publicUpdateWorkflow must include internal-issue step",
        )

    def test_public_update_workflow_includes_internal_branch(self):
        workflow = self.data["publicUpdateWorkflow"]
        self.assertTrue(
            any("internal-branch" in step or "internal_branch" in step for step in workflow),
            "publicUpdateWorkflow must include internal-branch step",
        )

    def test_public_update_workflow_includes_validation(self):
        workflow = self.data["publicUpdateWorkflow"]
        self.assertTrue(
            any("validation" in step for step in workflow),
            "publicUpdateWorkflow must include validation step",
        )

    def test_public_update_workflow_includes_merge_to_main(self):
        workflow = self.data["publicUpdateWorkflow"]
        self.assertTrue(
            any("main" in step for step in workflow),
            "publicUpdateWorkflow must include merge-to-internal-main step",
        )

    def test_public_update_workflow_includes_clean_snapshot(self):
        workflow = self.data["publicUpdateWorkflow"]
        self.assertTrue(
            any("snapshot" in step for step in workflow),
            "publicUpdateWorkflow must include clean snapshot step",
        )

    def test_public_update_workflow_includes_scanner(self):
        workflow = self.data["publicUpdateWorkflow"]
        self.assertTrue(
            any("scanner" in step for step in workflow),
            "publicUpdateWorkflow must include scanner step",
        )

    def test_public_update_workflow_includes_public_push(self):
        workflow = self.data["publicUpdateWorkflow"]
        self.assertTrue(
            any("push" in step for step in workflow),
            "publicUpdateWorkflow must include public push step",
        )

    def test_public_update_workflow_includes_token_revoke(self):
        workflow = self.data["publicUpdateWorkflow"]
        self.assertTrue(
            any("token" in step or "revoke" in step for step in workflow),
            "publicUpdateWorkflow must include token revoke step",
        )

    def test_public_update_workflow_includes_post_push_verification(self):
        workflow = self.data["publicUpdateWorkflow"]
        self.assertTrue(
            any("verification" in step or "post-push" in step for step in workflow),
            "publicUpdateWorkflow must include post-push verification step",
        )

    def test_no_go_criteria_is_list(self):
        self.assertIsInstance(self.data["noGoCriteria"], list)
        self.assertGreaterEqual(len(self.data["noGoCriteria"]), 3)

    def test_caveats_is_list(self):
        self.assertIsInstance(self.data["caveats"], list)

    def test_caveats_includes_developer_preview(self):
        caveats = self.data["caveats"]
        self.assertTrue(
            any("Developer Preview" in c for c in caveats),
            "caveats must include 'Developer Preview'",
        )

    def test_caveats_includes_not_production_saas(self):
        caveats = self.data["caveats"]
        self.assertTrue(
            any("production SaaS" in c or "not production" in c for c in caveats),
            "caveats must include not-production-SaaS statement",
        )

    def test_caveats_includes_tenant_isolation_not_implemented(self):
        caveats = self.data["caveats"]
        self.assertTrue(
            any("tenant isolation" in c.lower() for c in caveats),
            "caveats must include tenant isolation not implemented",
        )

    def test_caveats_includes_no_real_secrets(self):
        caveats = self.data["caveats"]
        self.assertTrue(
            any("secret" in c.lower() for c in caveats),
            "caveats must include no real secrets",
        )

    def test_caveats_includes_no_real_customer_data(self):
        caveats = self.data["caveats"]
        self.assertTrue(
            any("customer data" in c.lower() for c in caveats),
            "caveats must include no real customer data",
        )

    def test_triage_categories_includes_security(self):
        self.assertIn("security", self.data["triageCategories"])

    def test_triage_categories_includes_sensitive_data(self):
        self.assertIn("sensitive-data", self.data["triageCategories"])

    def test_triage_categories_includes_docs(self):
        self.assertIn("docs", self.data["triageCategories"])

    def test_triage_categories_includes_public_snapshot(self):
        self.assertIn("public-snapshot", self.data["triageCategories"])

    def test_triage_categories_includes_agent_feedback(self):
        self.assertIn("agent-feedback", self.data["triageCategories"])

    def test_triage_categories_includes_sdk(self):
        self.assertIn("sdk", self.data["triageCategories"])

    def test_triage_categories_includes_dashboard(self):
        self.assertIn("dashboard", self.data["triageCategories"])

    def test_triage_categories_includes_compliance_language(self):
        self.assertIn("compliance-language", self.data["triageCategories"])


# ---------------------------------------------------------------------------
# 4. JSON safety booleans
# ---------------------------------------------------------------------------

class TestGL163JsonSafetyBooleans(unittest.TestCase):

    def setUp(self):
        self.data = _load_json()

    def test_backend_src_not_changed(self):
        self.assertFalse(self.data["backend_src_changed"])

    def test_openapi_not_changed(self):
        self.assertFalse(self.data["openapi_changed"])

    def test_db_schema_not_changed(self):
        self.assertFalse(self.data["db_schema_changed"])

    def test_dependencies_not_changed(self):
        self.assertFalse(self.data["dependencies_changed"])

    def test_sdk_not_changed(self):
        self.assertFalse(self.data["sdk_changed"])

    def test_not_pushed_to_github(self):
        self.assertFalse(self.data["pushed_to_github"])

    def test_github_api_not_called(self):
        self.assertFalse(self.data["github_api_called"])

    def test_live_github_issues_not_created(self):
        self.assertFalse(self.data["live_github_issues_created"])

    def test_git_remotes_not_changed(self):
        self.assertFalse(self.data["git_remotes_changed"])

    def test_history_rewrite_not_performed(self):
        self.assertFalse(self.data["history_rewrite_performed"])

    def test_production_code_not_changed(self):
        self.assertFalse(self.data["production_code_changed"])

    def test_production_saas_not_claimed(self):
        self.assertFalse(self.data["production_saas_ready_claimed"])

    def test_tenant_isolation_not_claimed(self):
        self.assertFalse(self.data["tenant_isolation_claimed_implemented"])

    def test_no_real_secrets(self):
        self.assertFalse(self.data["uses_real_secrets"])

    def test_no_real_customer_data(self):
        self.assertFalse(self.data["uses_real_customer_data"])

    def test_no_private_personal_data(self):
        self.assertFalse(self.data["includes_private_personal_data"])

    def test_public_github_not_modified(self):
        self.assertFalse(self.data["public_github_modified"])


# ---------------------------------------------------------------------------
# 5. Document content assertions
# ---------------------------------------------------------------------------

class TestGL163DocContent(unittest.TestCase):

    def setUp(self):
        self.doc = _load_doc()

    def test_developer_preview_stated(self):
        self.assertIn("Developer Preview", self.doc)

    def test_internal_forgejo_source_of_truth(self):
        self.assertIn("Internal Forgejo remains the source of truth", self.doc)

    def test_public_snapshot_stated(self):
        self.assertIn("clean developer-facing snapshot", self.doc)

    def test_not_production_saas(self):
        self.assertIn("not production SaaS", self.doc)

    def test_tenant_isolation_not_implemented(self):
        lower = self.doc.lower()
        self.assertTrue(
            "tenant isolation is not implemented" in lower or
            "tenant isolation not implemented" in lower,
            "doc must state tenant isolation is not implemented",
        )

    def test_no_real_secrets_stated(self):
        self.assertIn("No real secrets", self.doc)

    def test_no_real_customer_data_stated(self):
        self.assertIn("No real customer data", self.doc)

    def test_emergency_only_direct_edits(self):
        lower = self.doc.lower()
        self.assertIn("emergency", lower)
        self.assertTrue(
            "direct public" in lower or "direct public hotfix" in lower or
            "direct public github" in lower,
            "doc must mention direct public edits are emergency-only",
        )

    def test_no_live_github_api_instruction(self):
        # The doc must not instruct the reader to call the GitHub API programmatically.
        # The doc may reference the GitHub API in prohibition context ("do not call the GitHub API").
        lower = self.doc.lower()
        self.assertNotIn("requests.get(\"https://api.github", lower)
        self.assertNotIn("requests.post(\"https://api.github", lower)
        self.assertNotIn("curl https://api.github.com", lower)
        # No positive instruction to use the API (prohibitions are acceptable)
        self.assertNotIn("use the github api to create", lower)
        self.assertNotIn("use the github api to assign", lower)

    def test_no_production_ready_claim(self):
        # The doc must not assert that GrantLayer is production-ready SaaS.
        # References in non-goals or prohibitions are acceptable.
        lower = self.doc.lower()
        self.assertNotIn("grantlayer is now production-ready", lower)
        self.assertNotIn("grantlayer is production ready saas", lower)
        self.assertNotIn("fully production ready and available", lower)
        # Positive "it is production-ready saas" without a preceding "not" or prohibition context
        self.assertNotIn("is production-ready saas and", lower)

    def test_no_tenant_isolation_implemented_claim(self):
        # The doc must not assert that tenant isolation has been implemented.
        # References in non-goals or exclusions are acceptable.
        lower = self.doc.lower()
        self.assertNotIn("tenant isolation is now implemented", lower)
        self.assertNotIn("tenant isolation has been implemented", lower)
        self.assertNotIn("full tenant isolation implemented", lower)

    def test_severity_p0_present(self):
        self.assertIn("P0", self.doc)

    def test_severity_p1_present(self):
        self.assertIn("P1", self.doc)

    def test_severity_p2_present(self):
        self.assertIn("P2", self.doc)

    def test_severity_p3_present(self):
        self.assertIn("P3", self.doc)

    def test_triage_category_security(self):
        self.assertIn("`security`", self.doc)

    def test_triage_category_sensitive_data(self):
        self.assertIn("`sensitive-data`", self.doc)

    def test_triage_category_docs(self):
        self.assertIn("`docs`", self.doc)

    def test_triage_category_public_snapshot(self):
        self.assertIn("`public-snapshot`", self.doc)

    def test_triage_category_agent_feedback(self):
        self.assertIn("`agent-feedback`", self.doc)

    def test_triage_category_sdk(self):
        self.assertIn("`sdk`", self.doc)

    def test_triage_category_dashboard(self):
        self.assertIn("`dashboard`", self.doc)

    def test_triage_category_compliance_language(self):
        self.assertIn("`compliance-language`", self.doc)

    def test_public_update_workflow_internal_issue(self):
        self.assertIn("Internal issue", self.doc)

    def test_public_update_workflow_internal_branch(self):
        self.assertIn("Internal branch", self.doc)

    def test_public_update_workflow_scanner(self):
        lower = self.doc.lower()
        self.assertIn("scanner clean", lower)

    def test_public_update_workflow_push(self):
        self.assertIn("Push public snapshot", self.doc)

    def test_public_update_workflow_token_revoke(self):
        lower = self.doc.lower()
        self.assertIn("revoke", lower)

    def test_public_update_workflow_post_push_verification(self):
        lower = self.doc.lower()
        self.assertIn("post-push verification", lower)

    def test_doc_does_not_instruct_direct_public_edits_except_emergency(self):
        # The doc must not instruct direct public edits as a normal workflow step.
        lower = self.doc.lower()
        self.assertNotIn("push directly to the public repository as a normal workflow", lower)
        self.assertNotIn("always push directly to public github", lower)

    def test_first_week_checklist_present(self):
        self.assertIn("First-Week Monitoring Checklist", self.doc)

    def test_agent_feedback_intake_policy_present(self):
        self.assertIn("Agent Feedback Intake Policy", self.doc)

    def test_security_report_handling_present(self):
        self.assertIn("Security Report Handling", self.doc)

    def test_emergency_exception_present(self):
        self.assertIn("Emergency Exception", self.doc)

    def test_go_no_go_criteria_present(self):
        lower = self.doc.lower()
        self.assertIn("go / no-go", lower)

    def test_handoff_present(self):
        self.assertIn("Handoff", self.doc)


# ---------------------------------------------------------------------------
# 6. No forbidden content in doc or JSON
# ---------------------------------------------------------------------------

class TestGL163NoForbiddenContent(unittest.TestCase):

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


# ---------------------------------------------------------------------------
# 7. Scope guard (branch-specific)
# ---------------------------------------------------------------------------

class TestGL163ScopeGuard(unittest.TestCase):

    def _on_gl163_branch(self):
        return _current_branch() == GL163_BRANCH

    def test_no_backend_src_changes(self):
        if not self._on_gl163_branch():
            self.skipTest("Not on GL-163 branch; skipping diff-based scope guard.")
        changed = _branch_diff_names()
        for path in changed:
            self.assertFalse(
                path.startswith("backend/src/"),
                f"Forbidden: backend/src/ change detected: {path}",
            )

    def test_no_openapi_changes(self):
        if not self._on_gl163_branch():
            self.skipTest("Not on GL-163 branch; skipping diff-based scope guard.")
        changed = _branch_diff_names()
        for path in changed:
            self.assertFalse(
                "openapi" in path.lower(),
                f"Forbidden: OpenAPI change detected: {path}",
            )

    def test_no_migration_changes(self):
        if not self._on_gl163_branch():
            self.skipTest("Not on GL-163 branch; skipping diff-based scope guard.")
        changed = _branch_diff_names()
        for path in changed:
            self.assertFalse(
                "migration" in path.lower() or path.startswith("alembic/"),
                f"Forbidden: migration change detected: {path}",
            )

    def test_no_dependency_file_changes(self):
        if not self._on_gl163_branch():
            self.skipTest("Not on GL-163 branch; skipping diff-based scope guard.")
        forbidden = {
            "requirements.txt", "requirements-dev.txt",
            "pyproject.toml", "setup.py", "Pipfile", "poetry.lock",
        }
        changed = set(_branch_diff_names())
        overlap = forbidden & changed
        self.assertFalse(overlap, f"Forbidden: dependency file(s) changed: {overlap}")

    def test_no_sdk_implementation_changes(self):
        if not self._on_gl163_branch():
            self.skipTest("Not on GL-163 branch; skipping diff-based scope guard.")
        changed = _branch_diff_names()
        for path in changed:
            self.assertFalse(
                path == "sdk/python/grantlayer_client.py",
                f"Forbidden: SDK implementation change detected: {path}",
            )

    def test_no_frontend_dashboard_design_changes(self):
        if not self._on_gl163_branch():
            self.skipTest("Not on GL-163 branch; skipping diff-based scope guard.")
        changed = _branch_diff_names()
        for path in changed:
            self.assertFalse(
                path.startswith("frontend/") or path.startswith("website/")
                or path.startswith("design/") or path.startswith("dashboard/"),
                f"Forbidden: frontend/dashboard/design change detected: {path}",
            )

    def test_no_claude_config_changes(self):
        if not self._on_gl163_branch():
            self.skipTest("Not on GL-163 branch; skipping diff-based scope guard.")
        changed = _branch_diff_names()
        for path in changed:
            self.assertFalse(
                path.startswith(".claude/"),
                f"Forbidden: .claude/ change detected: {path}",
            )

    def test_expected_files_within_scope(self):
        if not self._on_gl163_branch():
            self.skipTest("Not on GL-163 branch; skipping diff-based scope guard.")
        allowed_prefixes = (
            "docs/post_public_agent_intake_triage.md",
            "docs/examples/gl163/",
            "backend/tests/test_gl163_",
        )
        changed = _branch_diff_names()
        for path in changed:
            allowed = any(path == prefix or path.startswith(prefix) for prefix in allowed_prefixes)
            self.assertTrue(
                allowed,
                f"Unexpected file in GL-163 branch diff: {path}. "
                f"Only expected GL-163 artifacts should be changed.",
            )


if __name__ == "__main__":
    unittest.main()
