"""
GL-160 Validation: Public GitHub Go/No-Go Decision Pack.

Covers:
- File existence checks (decision doc, JSON artifact, this test file)
- JSON artifact boolean and field validation
- Decision document content and caveat checks
- Decision document section checks (go criteria, no-go blockers, etc.)
- Forbidden content guard (no internal hostnames/paths/private key markers)
- Scope guard (no forbidden production files changed)
- Branch scope guard (skipped if not on GL-160 branch)
"""
import json
import os
import subprocess
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

DECISION_DOC = os.path.join(REPO_ROOT, "docs", "public_github_go_no_go_decision.md")
DECISION_JSON = os.path.join(REPO_ROOT, "docs", "examples", "gl160",
                             "public_github_go_no_go_decision.json")
THIS_TEST = os.path.join(REPO_ROOT, "backend", "tests",
                         "test_gl160_public_github_go_no_go_decision.py")


def _load_json():
    with open(DECISION_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


class TestGL160FilesExist(unittest.TestCase):
    def test_decision_doc_exists(self):
        self.assertTrue(os.path.isfile(DECISION_DOC), f"Missing: {DECISION_DOC}")

    def test_json_artifact_exists(self):
        self.assertTrue(os.path.isfile(DECISION_JSON), f"Missing: {DECISION_JSON}")

    def test_test_file_exists(self):
        self.assertTrue(os.path.isfile(THIS_TEST), f"Missing: {THIS_TEST}")


class TestGL160JsonArtifact(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DECISION_JSON, "r", encoding="utf-8") as f:
            cls.data = json.load(f)

    def _assert_true(self, key):
        self.assertIn(key, self.data, f"Missing key: {key}")
        self.assertIs(self.data[key], True, f"Expected True for: {key}")

    def _assert_false(self, key):
        self.assertIn(key, self.data, f"Missing key: {key}")
        self.assertIs(self.data[key], False, f"Expected False for: {key}")

    def test_issue_id(self):
        self.assertEqual(self.data["issue_id"], "GL-160")

    def test_artifact_type(self):
        self.assertEqual(self.data["artifact_type"], "public_github_go_no_go_decision")

    def test_decision_document_added(self):
        self._assert_true("decision_document_added")

    def test_validation_test_added(self):
        self._assert_true("validation_test_added")

    def test_go_decision_allows_next_step(self):
        self._assert_true("go_decision_allows_next_step")

    def test_clean_public_snapshot_required(self):
        self._assert_true("clean_public_snapshot_required")

    def test_manual_approval_required_before_publication(self):
        self._assert_true("manual_approval_required_before_publication")

    def test_full_history_publication_allowed_false(self):
        self._assert_false("full_history_publication_allowed")

    def test_github_publication_performed_false(self):
        self._assert_false("github_publication_performed")

    def test_public_repo_created_false(self):
        self._assert_false("public_repo_created")

    def test_mirror_repo_created_on_remote_false(self):
        self._assert_false("mirror_repo_created_on_remote")

    def test_github_api_called_false(self):
        self._assert_false("github_api_called")

    def test_live_github_issues_created_false(self):
        self._assert_false("live_github_issues_created")

    def test_git_remotes_changed_false(self):
        self._assert_false("git_remotes_changed")

    def test_github_remote_added_false(self):
        self._assert_false("github_remote_added")

    def test_pushed_to_github_false(self):
        self._assert_false("pushed_to_github")

    def test_history_rewrite_performed_false(self):
        self._assert_false("history_rewrite_performed")

    def test_git_filter_repo_run_false(self):
        self._assert_false("git_filter_repo_run")

    def test_bfg_run_false(self):
        self._assert_false("bfg_run")

    def test_commits_deleted_false(self):
        self._assert_false("commits_deleted")

    def test_secret_history_cleanup_performed_false(self):
        self._assert_false("secret_history_cleanup_performed")

    def test_secrets_rotated_false(self):
        self._assert_false("secrets_rotated")

    def test_full_history_clean_claimed_false(self):
        self._assert_false("full_history_clean_claimed")

    def test_production_code_changed_false(self):
        self._assert_false("production_code_changed")

    def test_backend_src_changed_false(self):
        self._assert_false("backend_src_changed")

    def test_endpoint_api_behavior_changed_false(self):
        self._assert_false("endpoint_api_behavior_changed")

    def test_openapi_changed_false(self):
        self._assert_false("openapi_changed")

    def test_db_schema_changed_false(self):
        self._assert_false("db_schema_changed")

    def test_dependencies_changed_false(self):
        self._assert_false("dependencies_changed")

    def test_sdk_changed_false(self):
        self._assert_false("sdk_changed")

    def test_langgraph_langchain_code_changed_false(self):
        self._assert_false("langgraph_langchain_code_changed")

    def test_runtime_agent_examples_changed_false(self):
        self._assert_false("runtime_agent_examples_changed")

    def test_frontend_website_design_changed_false(self):
        self._assert_false("frontend_website_design_changed")

    def test_production_saas_ready_claimed_false(self):
        self._assert_false("production_saas_ready_claimed")

    def test_tenant_isolation_claimed_implemented_false(self):
        self._assert_false("tenant_isolation_claimed_implemented")

    def test_public_github_release_claimed_false(self):
        self._assert_false("public_github_release_claimed")

    def test_uses_real_secrets_false(self):
        self._assert_false("uses_real_secrets")

    def test_uses_real_customer_data_false(self):
        self._assert_false("uses_real_customer_data")

    def test_includes_private_personal_data_false(self):
        self._assert_false("includes_private_personal_data")

    def test_next_issue(self):
        next_issue = self.data.get("next_issue", "")
        self.assertIn("GL-161", next_issue)
        self.assertIn("Clean Public Snapshot Build", next_issue)

    def test_prerequisites_reviewed_present(self):
        prereqs = self.data.get("prerequisites_reviewed", [])
        self.assertIsInstance(prereqs, list)
        self.assertGreater(len(prereqs), 5)

    def test_go_criteria_present(self):
        criteria = self.data.get("go_criteria", [])
        self.assertIsInstance(criteria, list)
        self.assertGreater(len(criteria), 5)

    def test_no_go_blockers_present(self):
        blockers = self.data.get("no_go_blockers", [])
        self.assertIsInstance(blockers, list)
        self.assertGreater(len(blockers), 3)

    def test_manual_approval_inputs_present(self):
        inputs = self.data.get("manual_approval_inputs", [])
        self.assertIsInstance(inputs, list)
        self.assertGreater(len(inputs), 3)

    def test_gl161_requirements_present(self):
        reqs = self.data.get("gl161_requirements", [])
        self.assertIsInstance(reqs, list)
        self.assertGreater(len(reqs), 3)

    def test_gl162_requirements_present(self):
        reqs = self.data.get("gl162_requirements", [])
        self.assertIsInstance(reqs, list)
        self.assertGreater(len(reqs), 3)

    def test_validation_gates_present(self):
        gates = self.data.get("validation_gates", {})
        self.assertIsInstance(gates, dict)
        self.assertGreater(len(gates), 5)


class TestGL160DocContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DECISION_DOC, "r", encoding="utf-8") as f:
            cls.doc_text = f.read()
            cls.doc_lower = cls.doc_text.lower()

    def test_developer_preview_caveat(self):
        self.assertIn("Developer Preview", self.doc_text)

    def test_not_production_saas_caveat(self):
        self.assertIn("not production saas", self.doc_lower)

    def test_tenant_isolation_not_implemented_caveat(self):
        self.assertIn("tenant isolation is not implemented", self.doc_lower)

    def test_no_real_secrets_caveat(self):
        self.assertIn("no real secrets", self.doc_lower)

    def test_no_real_customer_data_caveat(self):
        self.assertIn("no real customer data", self.doc_lower)

    def test_clean_public_snapshot_reference(self):
        self.assertIn("clean public snapshot", self.doc_lower)

    def test_full_internal_git_history_must_not_be_published(self):
        self.assertIn("full internal git history must not be published", self.doc_lower)

    def test_manual_approval_required_reference(self):
        self.assertIn("manual approval required", self.doc_lower)

    def test_gl161_clean_public_snapshot_build_reference(self):
        self.assertIn("GL-161 Clean Public Snapshot Build", self.doc_text)

    def test_gl162_github_public_repository_metadata_reference(self):
        self.assertIn("GL-162 GitHub Public Repository Metadata / Publish Gate", self.doc_text)

    def test_no_github_publication(self):
        self.assertIn("no github publication", self.doc_lower)

    def test_no_history_rewrite(self):
        self.assertIn("no history rewrite", self.doc_lower)

    def test_approval_phrase_present(self):
        self.assertIn(
            "I approve preparing the clean GrantLayer developer-preview snapshot for public GitHub publication.",
            self.doc_text
        )


class TestGL160DocSections(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DECISION_DOC, "r", encoding="utf-8") as f:
            cls.doc_lower = f.read().lower()

    def test_go_criteria_section_present(self):
        self.assertIn("go criteria", self.doc_lower)

    def test_no_go_blockers_section_present(self):
        self.assertIn("no-go blockers", self.doc_lower)

    def test_publication_constraints_section_present(self):
        self.assertIn("publication constraints", self.doc_lower)

    def test_rollback_abort_procedure_present(self):
        self.assertIn("rollback", self.doc_lower)

    def test_risk_register_present(self):
        self.assertIn("risk register", self.doc_lower)

    def test_non_goals_present(self):
        self.assertIn("non-goals", self.doc_lower)

    def test_prerequisites_section_present(self):
        self.assertIn("prerequisites", self.doc_lower)

    def test_manual_approval_section_present(self):
        self.assertIn("manual approval", self.doc_lower)

    def test_gl161_handoff_section_present(self):
        self.assertIn("gl-161 handoff", self.doc_lower)

    def test_gl162_handoff_section_present(self):
        self.assertIn("gl-162 handoff", self.doc_lower)


class TestGL160NoForbiddenContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DECISION_DOC, "r", encoding="utf-8") as f:
            cls.doc_text = f.read()
        with open(DECISION_JSON, "r", encoding="utf-8") as f:
            cls.json_text = f.read()

    def test_no_internal_forge_hostname_in_doc(self):
        self.assertNotIn("forge.hofercloud.eu", self.doc_text)

    def test_no_internal_forge_hostname_in_json(self):
        self.assertNotIn("forge.hofercloud.eu", self.json_text)

    def test_no_internal_terminal_hostname_in_doc(self):
        self.assertNotIn("terminal.hofercloud.eu", self.doc_text)

    def test_no_internal_terminal_hostname_in_json(self):
        self.assertNotIn("terminal.hofercloud.eu", self.json_text)

    def test_no_home_adminuser_in_doc(self):
        self.assertNotIn("/home/adminuser", self.doc_text)

    def test_no_home_adminuser_in_json(self):
        self.assertNotIn("/home/adminuser", self.json_text)

    def test_no_home_oai_in_doc(self):
        self.assertNotIn("/home/oai", self.doc_text)

    def test_no_home_oai_in_json(self):
        self.assertNotIn("/home/oai", self.json_text)

    def test_no_mnt_data_in_doc(self):
        self.assertNotIn("/mnt/data", self.doc_text)

    def test_no_mnt_data_in_json(self):
        self.assertNotIn("/mnt/data", self.json_text)

    def test_no_private_key_marker_in_doc(self):
        self.assertNotIn("BEGIN RSA PRIVATE KEY", self.doc_text)
        self.assertNotIn("BEGIN OPENSSH PRIVATE KEY", self.doc_text)
        self.assertNotIn("BEGIN PRIVATE KEY", self.doc_text)

    def test_no_private_key_marker_in_json(self):
        self.assertNotIn("BEGIN RSA PRIVATE KEY", self.json_text)
        self.assertNotIn("BEGIN OPENSSH PRIVATE KEY", self.json_text)
        self.assertNotIn("BEGIN PRIVATE KEY", self.json_text)


class TestGL160ScopeGuard(unittest.TestCase):
    _BRANCH = "gl-160-public-github-go-no-go-decision"

    def _get_current_branch(self):
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=REPO_ROOT, capture_output=True, text=True
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def _get_changed_files(self):
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "main...HEAD"],
                cwd=REPO_ROOT, capture_output=True, text=True
            )
            return [f.strip() for f in result.stdout.strip().splitlines() if f.strip()]
        except Exception:
            return []

    def test_scope_guard(self):
        branch = self._get_current_branch()
        if branch != self._BRANCH:
            self.skipTest(
                f"Not on GL-160 branch (current: {branch}); skipping diff assertions"
            )

        changed = self._get_changed_files()

        allowed = {
            "docs/public_github_go_no_go_decision.md",
            "docs/examples/gl160/public_github_go_no_go_decision.json",
            "backend/tests/test_gl160_public_github_go_no_go_decision.py",
            # allowed only if necessary
            "README.md",
            "SECURITY.md",
            "CONTRIBUTING.md",
            "AGENTS.md",
            "docs/github_private_mirror_dry_run.md",
            "docs/git_history_exposure_review_public_snapshot_decision.md",
            "docs/public_secret_sensitive_scan_gate.md",
            ".github/pull_request_template.md",
        }

        forbidden_prefixes = [
            "backend/src/",
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
            "sdk/python/grantlayer_client.py",
            "examples/langgraph_langchain/grantlayer_agent_example.py",
            "examples/agents/",
            ".github/ISSUE_TEMPLATE/",
        ]

        forbidden_exact = [
            "docs/openapi.yaml",
        ]

        for f in changed:
            for prefix in forbidden_prefixes:
                self.assertFalse(
                    f == prefix or f.startswith(prefix),
                    f"Forbidden file changed: {f} (matches forbidden prefix: {prefix})"
                )
            for exact in forbidden_exact:
                self.assertNotEqual(f, exact,
                                    f"Forbidden file changed: {f}")

        unexpected = [f for f in changed if f not in allowed]
        self.assertEqual(
            unexpected, [],
            f"Unexpected files changed outside allowed set: {unexpected}"
        )


if __name__ == "__main__":
    unittest.main()
