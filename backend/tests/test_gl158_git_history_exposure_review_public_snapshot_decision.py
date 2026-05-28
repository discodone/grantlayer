"""
GL-158 Validation: Git History Exposure Review / Public Snapshot Decision.

Covers:
- File existence checks
- JSON artifact boolean and field validation
- Review document content and caveat checks
- Exposure category coverage
- Decision option coverage
- Risk register and go/no-go criteria presence
- Forbidden content guard (no internal hostnames/paths)
- Branch scope guard
"""
import json
import os
import subprocess
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

REVIEW_DOC = os.path.join(REPO_ROOT, "docs", "git_history_exposure_review_public_snapshot_decision.md")
REVIEW_JSON = os.path.join(REPO_ROOT, "docs", "examples", "gl158",
                           "git_history_exposure_review_public_snapshot_decision.json")
THIS_TEST = os.path.join(REPO_ROOT, "backend", "tests",
                         "test_gl158_git_history_exposure_review_public_snapshot_decision.py")


class TestGL158FilesExist(unittest.TestCase):
    def test_review_doc_exists(self):
        self.assertTrue(os.path.isfile(REVIEW_DOC), f"Missing: {REVIEW_DOC}")

    def test_json_artifact_exists(self):
        self.assertTrue(os.path.isfile(REVIEW_JSON), f"Missing: {REVIEW_JSON}")

    def test_test_file_exists(self):
        self.assertTrue(os.path.isfile(THIS_TEST), f"Missing: {THIS_TEST}")


class TestGL158JsonArtifact(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(REVIEW_JSON, "r", encoding="utf-8") as f:
            cls.data = json.load(f)

    def _assert_true(self, key):
        self.assertIn(key, self.data, f"Missing key: {key}")
        self.assertIs(self.data[key], True, f"Expected True for: {key}")

    def _assert_false(self, key):
        self.assertIn(key, self.data, f"Missing key: {key}")
        self.assertIs(self.data[key], False, f"Expected False for: {key}")

    def test_issue_id(self):
        self.assertEqual(self.data["issue_id"], "GL-158")

    def test_artifact_type(self):
        self.assertEqual(self.data["artifact_type"], "git_history_exposure_review_public_snapshot_decision")

    def test_review_document_added(self):
        self._assert_true("review_document_added")

    def test_validation_test_added(self):
        self._assert_true("validation_test_added")

    def test_clean_public_snapshot_recommended(self):
        self._assert_true("clean_public_snapshot_recommended")

    def test_full_history_publication_recommended_false(self):
        self._assert_false("full_history_publication_recommended")

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

    def test_github_publication_performed_false(self):
        self._assert_false("github_publication_performed")

    def test_live_github_issues_created_false(self):
        self._assert_false("live_github_issues_created")

    def test_github_api_called_false(self):
        self._assert_false("github_api_called")

    def test_git_remotes_changed_false(self):
        self._assert_false("git_remotes_changed")

    def test_public_repo_created_false(self):
        self._assert_false("public_repo_created")

    def test_mirror_repo_created_false(self):
        self._assert_false("mirror_repo_created")

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

    def test_full_history_clean_claimed_false(self):
        self._assert_false("full_history_clean_claimed")

    def test_uses_real_secrets_false(self):
        self._assert_false("uses_real_secrets")

    def test_uses_real_customer_data_false(self):
        self._assert_false("uses_real_customer_data")

    def test_includes_private_personal_data_false(self):
        self._assert_false("includes_private_personal_data")

    def test_exposure_categories_reviewed_present(self):
        cats = self.data.get("exposure_categories_reviewed", [])
        self.assertIsInstance(cats, list)
        self.assertGreater(len(cats), 5)

    def test_decision_options_considered_present(self):
        opts = self.data.get("decision_options_considered", [])
        self.assertIsInstance(opts, list)
        self.assertGreater(len(opts), 2)

    def test_gl159_requirements_present(self):
        reqs = self.data.get("gl159_requirements", [])
        self.assertIsInstance(reqs, list)
        self.assertGreater(len(reqs), 3)

    def test_gl160_go_no_go_inputs_present(self):
        inputs = self.data.get("gl160_go_no_go_inputs", [])
        self.assertIsInstance(inputs, list)
        self.assertGreater(len(inputs), 3)

    def test_validation_gates_present(self):
        gates = self.data.get("validation_gates", {})
        self.assertIsInstance(gates, dict)
        self.assertGreater(len(gates), 5)

    def test_recommendation_present(self):
        rec = self.data.get("recommendation", "")
        self.assertIsInstance(rec, str)
        self.assertGreater(len(rec), 10)

    def test_next_issue(self):
        self.assertIn("GL-159", self.data.get("next_issue", ""))
        self.assertIn("GitHub Private Mirror Dry Run", self.data.get("next_issue", ""))


class TestGL158DocContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(REVIEW_DOC, "r", encoding="utf-8") as f:
            cls.doc_lower = f.read().lower()
            f.seek(0)
            cls.doc_text = f.read()

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

    def test_clean_public_snapshot_present(self):
        self.assertIn("clean public snapshot", self.doc_lower)

    def test_do_not_publish_full_history(self):
        self.assertIn("do not publish full internal git history", self.doc_lower)

    def test_gl159_reference(self):
        self.assertIn("GL-159 GitHub Private Mirror Dry Run", self.doc_text)

    def test_gl160_reference(self):
        self.assertIn("GL-160", self.doc_text)
        self.assertIn("Go/No-Go", self.doc_text)

    def test_no_history_rewrite(self):
        self.assertIn("no history rewrite", self.doc_lower)

    def test_no_github_publication(self):
        self.assertIn("no github publication", self.doc_lower)


class TestGL158ExposureCategories(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(REVIEW_DOC, "r", encoding="utf-8") as f:
            cls.doc_lower = f.read().lower()

    def test_internal_hostnames_category(self):
        self.assertIn("internal hostnames", self.doc_lower)

    def test_internal_absolute_paths_category(self):
        self.assertIn("internal absolute paths", self.doc_lower)

    def test_provider_traces_category(self):
        self.assertIn("provider traces", self.doc_lower)

    def test_prompt_artifacts_category(self):
        self.assertIn("prompt", self.doc_lower)
        self.assertIn("artifacts", self.doc_lower)

    def test_sensitive_data_category(self):
        self.assertIn("sensitive", self.doc_lower)

    def test_customer_data_category(self):
        self.assertIn("customer data", self.doc_lower)

    def test_private_personal_data_category(self):
        self.assertIn("private personal data", self.doc_lower)


class TestGL158DecisionOptions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(REVIEW_DOC, "r", encoding="utf-8") as f:
            cls.doc_lower = f.read().lower()

    def test_full_history_option(self):
        self.assertIn("full history", self.doc_lower)

    def test_filtered_history_option(self):
        self.assertIn("filter", self.doc_lower)

    def test_clean_public_snapshot_option(self):
        self.assertIn("clean public snapshot", self.doc_lower)

    def test_keep_private_option(self):
        self.assertIn("keep private", self.doc_lower)


class TestGL158RiskAndCriteria(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(REVIEW_DOC, "r", encoding="utf-8") as f:
            cls.doc_lower = f.read().lower()

    def test_risk_register_present(self):
        self.assertIn("risk register", self.doc_lower)

    def test_go_no_go_criteria_present(self):
        self.assertIn("go/no-go", self.doc_lower)

    def test_non_goals_present(self):
        self.assertIn("non-goals", self.doc_lower)


class TestGL158NoForbiddenContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(REVIEW_DOC, "r", encoding="utf-8") as f:
            cls.doc_text = f.read()
        with open(REVIEW_JSON, "r", encoding="utf-8") as f:
            cls.json_text = f.read()

    def _combined(self):
        return self.doc_text + "\n" + self.json_text

    def test_no_home_adminuser_in_doc(self):
        self.assertNotIn("/home/adminuser", self.doc_text,
                         "Review doc must not contain internal path /home/adminuser")

    def test_no_home_adminuser_in_json(self):
        self.assertNotIn("/home/adminuser", self.json_text,
                         "JSON artifact must not contain internal path /home/adminuser")

    def test_no_home_oai_in_doc(self):
        self.assertNotIn("/home/oai", self.doc_text,
                         "Review doc must not contain internal path /home/oai")

    def test_no_home_oai_in_json(self):
        self.assertNotIn("/home/oai", self.json_text,
                         "JSON artifact must not contain internal path /home/oai")

    def test_no_mnt_data_in_doc(self):
        self.assertNotIn("/mnt/data", self.doc_text,
                         "Review doc must not contain internal path /mnt/data")

    def test_no_mnt_data_in_json(self):
        self.assertNotIn("/mnt/data", self.json_text,
                         "JSON artifact must not contain internal path /mnt/data")

    def test_no_internal_forge_hostname_in_doc(self):
        self.assertNotIn("forge.hofercloud.eu", self.doc_text,
                         "Review doc must not contain internal hostname forge.hofercloud.eu")

    def test_no_internal_forge_hostname_in_json(self):
        self.assertNotIn("forge.hofercloud.eu", self.json_text,
                         "JSON artifact must not contain internal hostname forge.hofercloud.eu")

    def test_no_internal_terminal_hostname_in_doc(self):
        self.assertNotIn("terminal.hofercloud.eu", self.doc_text,
                         "Review doc must not contain internal hostname terminal.hofercloud.eu")

    def test_no_internal_terminal_hostname_in_json(self):
        self.assertNotIn("terminal.hofercloud.eu", self.json_text,
                         "JSON artifact must not contain internal hostname terminal.hofercloud.eu")


class TestGL158BranchScopeGuard(unittest.TestCase):
    _BRANCH = "gl-158-git-history-exposure-review-public-snapshot-decision"

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
                f"Not on GL-158 branch (current: {branch}); skipping diff assertions"
            )

        changed = self._get_changed_files()

        allowed = {
            "docs/git_history_exposure_review_public_snapshot_decision.md",
            "docs/examples/gl158/git_history_exposure_review_public_snapshot_decision.json",
            "backend/tests/test_gl158_git_history_exposure_review_public_snapshot_decision.py",
            "README.md",
            "SECURITY.md",
            "CONTRIBUTING.md",
            "AGENTS.md",
            "docs/public_secret_sensitive_scan_gate.md",
            ".github/pull_request_template.md",
        }

        forbidden_prefixes = [
            "backend/src/",
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
            "sdk/python/grantlayer_client.py",
            "examples/langgraph_langchain/grantlayer_agent_example.py",
            "examples/agents/",
            ".github/ISSUE_TEMPLATE/",
            "scripts/",
        ]

        for f in changed:
            for prefix in forbidden_prefixes:
                self.assertFalse(
                    f == prefix or f.startswith(prefix),
                    f"Forbidden file changed: {f} (matches forbidden prefix: {prefix})"
                )

        unexpected = [f for f in changed if f not in allowed]
        self.assertEqual(
            unexpected, [],
            f"Unexpected files changed outside allowed set: {unexpected}"
        )


if __name__ == "__main__":
    unittest.main()
