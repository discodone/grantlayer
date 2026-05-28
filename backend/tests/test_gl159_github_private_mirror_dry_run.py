"""
GL-159 Validation: GitHub Private Mirror Dry Run.

Covers:
- File existence checks (doc, JSON artifact, optional script + executable)
- JSON artifact boolean and field validation
- Dry-run document content and caveat checks
- Candidate contents and exclusions checks
- Validation checklist checks
- Optional script safety checks
- Forbidden content guard (no internal hostnames/paths/private key markers)
- Scope guard (no forbidden production files changed)
- Branch scope guard (skipped if not on GL-159 branch)
"""
import json
import os
import subprocess
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

DRY_RUN_DOC = os.path.join(REPO_ROOT, "docs", "github_private_mirror_dry_run.md")
DRY_RUN_JSON = os.path.join(REPO_ROOT, "docs", "examples", "gl159",
                             "github_private_mirror_dry_run.json")
THIS_TEST = os.path.join(REPO_ROOT, "backend", "tests",
                         "test_gl159_github_private_mirror_dry_run.py")
OPTIONAL_SCRIPT = os.path.join(REPO_ROOT, "scripts", "github-private-mirror-dry-run.sh")


def _load_json():
    with open(DRY_RUN_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


class TestGL159FilesExist(unittest.TestCase):
    def test_dry_run_doc_exists(self):
        self.assertTrue(os.path.isfile(DRY_RUN_DOC), f"Missing: {DRY_RUN_DOC}")

    def test_json_artifact_exists(self):
        self.assertTrue(os.path.isfile(DRY_RUN_JSON), f"Missing: {DRY_RUN_JSON}")

    def test_test_file_exists(self):
        self.assertTrue(os.path.isfile(THIS_TEST), f"Missing: {THIS_TEST}")

    def test_optional_script_exists_if_declared(self):
        data = _load_json()
        if data.get("optional_script_added") is True:
            self.assertTrue(os.path.isfile(OPTIONAL_SCRIPT),
                            f"optional_script_added is true but script missing: {OPTIONAL_SCRIPT}")

    def test_optional_script_executable_if_declared(self):
        data = _load_json()
        if data.get("optional_script_added") is True:
            self.assertTrue(os.access(OPTIONAL_SCRIPT, os.X_OK),
                            f"Script exists but is not executable: {OPTIONAL_SCRIPT}")


class TestGL159JsonArtifact(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DRY_RUN_JSON, "r", encoding="utf-8") as f:
            cls.data = json.load(f)

    def _assert_true(self, key):
        self.assertIn(key, self.data, f"Missing key: {key}")
        self.assertIs(self.data[key], True, f"Expected True for: {key}")

    def _assert_false(self, key):
        self.assertIn(key, self.data, f"Missing key: {key}")
        self.assertIs(self.data[key], False, f"Expected False for: {key}")

    def test_issue_id(self):
        self.assertEqual(self.data["issue_id"], "GL-159")

    def test_artifact_type(self):
        self.assertEqual(self.data["artifact_type"], "github_private_mirror_dry_run")

    def test_dry_run_document_added(self):
        self._assert_true("dry_run_document_added")

    def test_validation_test_added(self):
        self._assert_true("validation_test_added")

    def test_clean_public_snapshot_recommended_by_gl158(self):
        self._assert_true("clean_public_snapshot_recommended_by_gl158")

    def test_private_mirror_dry_run_documented(self):
        self._assert_true("private_mirror_dry_run_documented")

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
        self.assertIn("GL-160", next_issue)
        self.assertIn("Public GitHub Go/No-Go + Publish", next_issue)

    def test_dry_run_validation_checklist_present(self):
        checklist = self.data.get("dry_run_validation_checklist", [])
        self.assertIsInstance(checklist, list)
        self.assertGreater(len(checklist), 5)

    def test_clean_snapshot_candidate_contents_present(self):
        contents = self.data.get("clean_snapshot_candidate_contents", [])
        self.assertIsInstance(contents, list)
        self.assertGreater(len(contents), 5)

    def test_excluded_contents_present(self):
        exclusions = self.data.get("excluded_contents", [])
        self.assertIsInstance(exclusions, list)
        self.assertGreater(len(exclusions), 3)

    def test_gl160_go_no_go_inputs_present(self):
        inputs = self.data.get("gl160_go_no_go_inputs", [])
        self.assertIsInstance(inputs, list)
        self.assertGreater(len(inputs), 3)

    def test_validation_gates_present(self):
        gates = self.data.get("validation_gates", {})
        self.assertIsInstance(gates, dict)
        self.assertGreater(len(gates), 5)


class TestGL159DocContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DRY_RUN_DOC, "r", encoding="utf-8") as f:
            cls.doc_text = f.read()
            cls.doc_lower = cls.doc_text.lower()

    def test_developer_preview_caveat(self):
        self.assertIn("Developer Preview", self.doc_text)

    def test_private_dry_run_only_caveat(self):
        self.assertIn("private dry-run only", self.doc_lower)

    def test_not_production_saas_caveat(self):
        self.assertIn("not production saas", self.doc_lower)

    def test_tenant_isolation_not_implemented_caveat(self):
        self.assertIn("tenant isolation is not implemented", self.doc_lower)

    def test_no_real_secrets_caveat(self):
        self.assertIn("no real secrets", self.doc_lower)

    def test_no_real_customer_data_caveat(self):
        self.assertIn("no real customer data", self.doc_lower)

    def test_no_github_publication(self):
        self.assertIn("no github publication", self.doc_lower)

    def test_no_github_api(self):
        self.assertIn("no github api", self.doc_lower)

    def test_no_remote_changes(self):
        self.assertIn("no remote changes", self.doc_lower)

    def test_no_public_repo_created(self):
        self.assertIn("no public repo created", self.doc_lower)

    def test_no_history_rewrite(self):
        self.assertIn("no history rewrite", self.doc_lower)

    def test_clean_public_snapshot_reference(self):
        self.assertIn("clean public snapshot", self.doc_lower)

    def test_gl160_handoff_reference(self):
        self.assertIn("GL-160 Public GitHub Go/No-Go + Publish", self.doc_text)

    def test_non_goals_present(self):
        self.assertIn("non-goals", self.doc_lower)

    def test_risk_register_present(self):
        self.assertIn("risk register", self.doc_lower)

    def test_rollback_abort_procedure_present(self):
        self.assertIn("rollback", self.doc_lower)

    def test_prerequisites_present(self):
        self.assertIn("prerequisites", self.doc_lower)

    def test_dry_run_posture_present(self):
        self.assertIn("dry-run posture", self.doc_lower)


class TestGL159CandidateContents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DRY_RUN_DOC, "r", encoding="utf-8") as f:
            cls.doc_lower = f.read().lower()
        with open(DRY_RUN_JSON, "r", encoding="utf-8") as f:
            cls.data = json.load(f)

    def _check_doc_and_json(self, term):
        contents = self.data.get("clean_snapshot_candidate_contents", [])
        combined = " ".join(contents).lower() + "\n" + self.doc_lower
        self.assertIn(term.lower(), combined,
                      f"Expected '{term}' in candidate contents (doc or JSON)")

    def test_license_in_candidate(self):
        self._check_doc_and_json("LICENSE")

    def test_readme_in_candidate(self):
        self._check_doc_and_json("README.md")

    def test_contributing_in_candidate(self):
        self._check_doc_and_json("CONTRIBUTING.md")

    def test_security_in_candidate(self):
        self._check_doc_and_json("SECURITY.md")

    def test_agents_in_candidate(self):
        self._check_doc_and_json("AGENTS.md")

    def test_llms_txt_in_candidate(self):
        self._check_doc_and_json("llms.txt")

    def test_docs_in_candidate(self):
        self._check_doc_and_json("docs")

    def test_examples_in_candidate(self):
        self._check_doc_and_json("examples")

    def test_sdk_python_in_candidate(self):
        self._check_doc_and_json("sdk")

    def test_github_in_candidate(self):
        self._check_doc_and_json(".github")


class TestGL159Exclusions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DRY_RUN_DOC, "r", encoding="utf-8") as f:
            cls.doc_lower = f.read().lower()
        with open(DRY_RUN_JSON, "r", encoding="utf-8") as f:
            cls.data = json.load(f)

    def _check_exclusion(self, term):
        exclusions = self.data.get("excluded_contents", [])
        combined = " ".join(exclusions).lower() + "\n" + self.doc_lower
        self.assertIn(term.lower(), combined,
                      f"Expected '{term}' in exclusions (doc or JSON)")

    def test_git_excluded(self):
        self._check_exclusion(".git")

    def test_claude_excluded(self):
        self._check_exclusion(".claude")

    def test_private_hostnames_excluded(self):
        self._check_exclusion("private hostnames")

    def test_real_secrets_excluded(self):
        self._check_exclusion("real secrets")

    def test_real_customer_data_excluded(self):
        self._check_exclusion("real customer data")

    def test_private_personal_data_excluded(self):
        self._check_exclusion("private personal data")


class TestGL159ValidationChecklist(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DRY_RUN_JSON, "r", encoding="utf-8") as f:
            cls.data = json.load(f)
        with open(DRY_RUN_DOC, "r", encoding="utf-8") as f:
            cls.doc_lower = f.read().lower()

    def _checklist_combined(self):
        items = self.data.get("dry_run_validation_checklist", [])
        return " ".join(items).lower() + "\n" + self.doc_lower

    def test_checklist_includes_scan_gate(self):
        self.assertIn("public-secret-sensitive-scan.sh", self._checklist_combined())

    def test_checklist_includes_gl157(self):
        self.assertIn("gl-157", self._checklist_combined())

    def test_checklist_includes_gl158(self):
        self.assertIn("gl-158", self._checklist_combined())

    def test_checklist_includes_gl156(self):
        self.assertIn("gl-156", self._checklist_combined())

    def test_checklist_includes_gl155(self):
        self.assertIn("gl-155", self._checklist_combined())

    def test_checklist_includes_full_backend_suite(self):
        combined = self._checklist_combined()
        self.assertTrue(
            "full backend suite" in combined or "run-full-backend-suite" in combined,
            "Expected 'full backend suite' or 'run-full-backend-suite' in checklist"
        )


class TestGL159OptionalScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = _load_json()
        cls.script_declared = data.get("optional_script_added") is True
        if cls.script_declared and os.path.isfile(OPTIONAL_SCRIPT):
            with open(OPTIONAL_SCRIPT, "r", encoding="utf-8") as f:
                cls.script_text = f.read()
        else:
            cls.script_text = ""

    def _skip_if_no_script(self):
        if not self.script_declared or not self.script_text:
            self.skipTest("optional_script_added is false or script not present; skipping script checks")

    def test_script_has_set_euo_pipefail(self):
        self._skip_if_no_script()
        self.assertIn("set -euo pipefail", self.script_text)

    def test_script_has_dry_run_wording(self):
        self._skip_if_no_script()
        lower = self.script_text.lower()
        self.assertTrue(
            "dry run" in lower or "dry-run" in lower,
            "Script must contain 'dry run' or 'dry-run' wording"
        )

    def test_script_uses_git_ls_files_or_git_archive(self):
        self._skip_if_no_script()
        self.assertTrue(
            "git ls-files" in self.script_text or "git archive" in self.script_text,
            "Script must use 'git ls-files' or 'git archive' for copying tracked files"
        )

    def test_script_excludes_claude(self):
        self._skip_if_no_script()
        self.assertIn(".claude", self.script_text,
                      "Script must reference .claude exclusion")

    def test_script_supports_help(self):
        self._skip_if_no_script()
        self.assertIn("--help", self.script_text)

    def test_script_does_not_contain_git_push(self):
        self._skip_if_no_script()
        self.assertNotIn("git push", self.script_text,
                         "Script must not contain 'git push'")

    def test_script_does_not_contain_gh_api(self):
        self._skip_if_no_script()
        self.assertNotIn("gh api", self.script_text,
                         "Script must not contain 'gh api'")

    def test_script_does_not_contain_git_remote_add(self):
        self._skip_if_no_script()
        self.assertNotIn("git remote add", self.script_text,
                         "Script must not contain 'git remote add'")

    def test_script_does_not_contain_git_filter_repo(self):
        self._skip_if_no_script()
        self.assertNotIn("git filter-repo", self.script_text,
                         "Script must not contain 'git filter-repo'")

    def test_script_does_not_contain_bfg(self):
        self._skip_if_no_script()
        lower = self.script_text.lower()
        self.assertNotIn("bfg", lower,
                         "Script must not reference BFG")


class TestGL159NoForbiddenContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DRY_RUN_DOC, "r", encoding="utf-8") as f:
            cls.doc_text = f.read()
        with open(DRY_RUN_JSON, "r", encoding="utf-8") as f:
            cls.json_text = f.read()
        data = _load_json()
        cls.script_text = ""
        if data.get("optional_script_added") is True and os.path.isfile(OPTIONAL_SCRIPT):
            with open(OPTIONAL_SCRIPT, "r", encoding="utf-8") as f:
                cls.script_text = f.read()

    def _all_artifacts(self):
        return self.doc_text + "\n" + self.json_text + "\n" + self.script_text

    def test_no_internal_forge_hostname_in_doc(self):
        self.assertNotIn("forge.hofercloud.eu", self.doc_text)

    def test_no_internal_forge_hostname_in_json(self):
        self.assertNotIn("forge.hofercloud.eu", self.json_text)

    def test_no_internal_forge_hostname_in_script(self):
        self.assertNotIn("forge.hofercloud.eu", self.script_text)

    def test_no_internal_terminal_hostname_in_doc(self):
        self.assertNotIn("terminal.hofercloud.eu", self.doc_text)

    def test_no_internal_terminal_hostname_in_json(self):
        self.assertNotIn("terminal.hofercloud.eu", self.json_text)

    def test_no_internal_terminal_hostname_in_script(self):
        self.assertNotIn("terminal.hofercloud.eu", self.script_text)

    def test_no_home_adminuser_in_doc(self):
        self.assertNotIn("/home/adminuser", self.doc_text)

    def test_no_home_adminuser_in_json(self):
        self.assertNotIn("/home/adminuser", self.json_text)

    def test_no_home_adminuser_in_script(self):
        self.assertNotIn("/home/adminuser", self.script_text)

    def test_no_home_oai_in_doc(self):
        self.assertNotIn("/home/oai", self.doc_text)

    def test_no_home_oai_in_json(self):
        self.assertNotIn("/home/oai", self.json_text)

    def test_no_home_oai_in_script(self):
        self.assertNotIn("/home/oai", self.script_text)

    def test_no_mnt_data_in_doc(self):
        self.assertNotIn("/mnt/data", self.doc_text)

    def test_no_mnt_data_in_json(self):
        self.assertNotIn("/mnt/data", self.json_text)

    def test_no_mnt_data_in_script(self):
        self.assertNotIn("/mnt/data", self.script_text)

    def test_no_private_key_marker_in_doc(self):
        self.assertNotIn("BEGIN RSA PRIVATE KEY", self.doc_text)
        self.assertNotIn("BEGIN OPENSSH PRIVATE KEY", self.doc_text)
        self.assertNotIn("BEGIN PRIVATE KEY", self.doc_text)

    def test_no_private_key_marker_in_json(self):
        self.assertNotIn("BEGIN RSA PRIVATE KEY", self.json_text)
        self.assertNotIn("BEGIN OPENSSH PRIVATE KEY", self.json_text)
        self.assertNotIn("BEGIN PRIVATE KEY", self.json_text)

    def test_no_private_key_marker_in_script(self):
        self.assertNotIn("BEGIN RSA PRIVATE KEY", self.script_text)
        self.assertNotIn("BEGIN OPENSSH PRIVATE KEY", self.script_text)
        self.assertNotIn("BEGIN PRIVATE KEY", self.script_text)


class TestGL159ScopeGuard(unittest.TestCase):
    _BRANCH = "gl-159-github-private-mirror-dry-run"

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
                f"Not on GL-159 branch (current: {branch}); skipping diff assertions"
            )

        changed = self._get_changed_files()
        data = _load_json()
        optional_script = data.get("optional_script_added") is True

        allowed = {
            "docs/github_private_mirror_dry_run.md",
            "docs/examples/gl159/github_private_mirror_dry_run.json",
            "backend/tests/test_gl159_github_private_mirror_dry_run.py",
            # allowed only if necessary
            "README.md",
            "SECURITY.md",
            "CONTRIBUTING.md",
            "AGENTS.md",
            "docs/git_history_exposure_review_public_snapshot_decision.md",
            "docs/public_secret_sensitive_scan_gate.md",
            ".github/pull_request_template.md",
        }

        if optional_script:
            allowed.add("scripts/github-private-mirror-dry-run.sh")

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

        # Any script file other than the declared optional script is forbidden
        for f in changed:
            if f.startswith("scripts/") and f != "scripts/github-private-mirror-dry-run.sh":
                self.fail(f"Unexpected script file changed: {f}")

        unexpected = [f for f in changed if f not in allowed]
        self.assertEqual(
            unexpected, [],
            f"Unexpected files changed outside allowed set: {unexpected}"
        )


if __name__ == "__main__":
    unittest.main()
