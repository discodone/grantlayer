"""
GL-161 Validation: Clean Public Snapshot Build.

Covers:
- File existence checks (script, doc, JSON artifact, this test file)
- Script content checks (required flags, git ls-files, exclusions, dirty-tree refusal)
- Script safety checks (no forbidden commands)
- JSON artifact boolean and field validation
- Documentation content and caveat checks
- Synthetic snapshot tests (temp git repo — include/exclude, dirty tree, allow-dirty)
- Forbidden content guard (no internal hostnames/paths/private key markers)
- Scope guard (no forbidden production files changed; skipped if not on GL-161 branch)
"""
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

SNAPSHOT_SCRIPT = os.path.join(REPO_ROOT, "scripts", "build-clean-public-snapshot.sh")
SNAPSHOT_DOC = os.path.join(REPO_ROOT, "docs", "clean_public_snapshot_build.md")
SNAPSHOT_JSON = os.path.join(REPO_ROOT, "docs", "examples", "gl161",
                              "clean_public_snapshot_build.json")
THIS_TEST = os.path.join(REPO_ROOT, "backend", "tests",
                         "test_gl161_clean_public_snapshot_build.py")


def _load_json():
    with open(SNAPSHOT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def _create_base_repo(tmp_dir):
    """Create a minimal clean git repo with tracked files for synthetic tests."""
    subprocess.run(["git", "init", tmp_dir], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"],
                   cwd=tmp_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"],
                   cwd=tmp_dir, check=True, capture_output=True)
    # Script lives in scripts/ subdir; REPO_ROOT resolves to tmp_dir
    scripts_dir = os.path.join(tmp_dir, "scripts")
    os.makedirs(scripts_dir)
    script_dest = os.path.join(scripts_dir, "build-clean-public-snapshot.sh")
    shutil.copy2(SNAPSHOT_SCRIPT, script_dest)
    os.chmod(script_dest, 0o755)
    # LICENSE is required by the script
    with open(os.path.join(tmp_dir, "LICENSE"), "w") as f:
        f.write("Apache-2.0\n")
    # Normal tracked public file
    with open(os.path.join(tmp_dir, "public_file.txt"), "w") as f:
        f.write("This is a public file.\n")
    # Tracked .claude file — must be excluded by script exclusion filter
    os.makedirs(os.path.join(tmp_dir, ".claude"), exist_ok=True)
    with open(os.path.join(tmp_dir, ".claude", "ignored.txt"), "w") as f:
        f.write("should be excluded\n")
    # Commit all of the above
    subprocess.run(["git", "add", "."], cwd=tmp_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"],
                   cwd=tmp_dir, check=True, capture_output=True)
    # Untracked .claude/secret.txt (not committed — won't appear in git ls-files at all)
    with open(os.path.join(tmp_dir, ".claude", "secret.txt"), "w") as f:
        f.write("untracked secret\n")


# ---------------------------------------------------------------------------
# File existence
# ---------------------------------------------------------------------------

class TestGL161FilesExist(unittest.TestCase):
    def test_snapshot_build_script_exists(self):
        self.assertTrue(os.path.isfile(SNAPSHOT_SCRIPT), f"Missing: {SNAPSHOT_SCRIPT}")

    def test_snapshot_build_docs_exists(self):
        self.assertTrue(os.path.isfile(SNAPSHOT_DOC), f"Missing: {SNAPSHOT_DOC}")

    def test_json_artifact_exists(self):
        self.assertTrue(os.path.isfile(SNAPSHOT_JSON), f"Missing: {SNAPSHOT_JSON}")

    def test_validation_test_exists(self):
        self.assertTrue(os.path.isfile(THIS_TEST), f"Missing: {THIS_TEST}")

    def test_script_is_executable(self):
        self.assertTrue(os.path.isfile(SNAPSHOT_SCRIPT), f"Missing: {SNAPSHOT_SCRIPT}")
        self.assertTrue(os.access(SNAPSHOT_SCRIPT, os.X_OK),
                        f"Script exists but is not executable: {SNAPSHOT_SCRIPT}")


# ---------------------------------------------------------------------------
# Script content
# ---------------------------------------------------------------------------

class TestGL161ScriptContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SNAPSHOT_SCRIPT, "r", encoding="utf-8") as f:
            cls.script_text = f.read()

    def test_script_has_set_euo_pipefail(self):
        self.assertIn("set -euo pipefail", self.script_text)

    def test_script_has_help_flag(self):
        self.assertIn("--help", self.script_text)

    def test_script_has_output_flag(self):
        self.assertIn("--output", self.script_text)

    def test_script_has_allow_dirty_flag(self):
        self.assertIn("--allow-dirty", self.script_text)

    def test_script_uses_git_ls_files_or_git_archive(self):
        self.assertTrue(
            "git ls-files" in self.script_text or "git archive" in self.script_text,
            "Script must use 'git ls-files' or 'git archive'"
        )

    def test_script_excludes_claude(self):
        self.assertIn(".claude", self.script_text,
                      "Script must reference .claude for exclusion")

    def test_script_excludes_git(self):
        self.assertIn(".git", self.script_text,
                      "Script must reference .git for exclusion verification")

    def test_script_checks_dirty_tree(self):
        self.assertIn("diff --quiet", self.script_text,
                      "Script must use 'diff --quiet' for dirty-tree detection")


# ---------------------------------------------------------------------------
# Script safety — forbidden commands must be absent
# ---------------------------------------------------------------------------

class TestGL161ScriptSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SNAPSHOT_SCRIPT, "r", encoding="utf-8") as f:
            cls.script_text = f.read()
            cls.script_lower = cls.script_text.lower()

    def test_no_git_push(self):
        self.assertNotIn("git push", self.script_text,
                         "Script must not contain 'git push'")

    def test_no_gh_api(self):
        self.assertNotIn("gh api", self.script_text,
                         "Script must not contain 'gh api'")

    def test_no_git_remote_add(self):
        self.assertNotIn("git remote add", self.script_text,
                         "Script must not contain 'git remote add'")

    def test_no_git_filter_repo(self):
        self.assertNotIn("git filter-repo", self.script_text,
                         "Script must not contain 'git filter-repo'")

    def test_no_bfg(self):
        self.assertNotIn("bfg", self.script_lower,
                         "Script must not reference BFG (case-insensitive)")


# ---------------------------------------------------------------------------
# JSON artifact
# ---------------------------------------------------------------------------

class TestGL161JsonArtifact(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SNAPSHOT_JSON, "r", encoding="utf-8") as f:
            cls.data = json.load(f)

    def _assert_true(self, key):
        self.assertIn(key, self.data, f"Missing key: {key}")
        self.assertIs(self.data[key], True, f"Expected True for: {key}")

    def _assert_false(self, key):
        self.assertIn(key, self.data, f"Missing key: {key}")
        self.assertIs(self.data[key], False, f"Expected False for: {key}")

    def test_issue_id(self):
        self.assertEqual(self.data["issue_id"], "GL-161")

    def test_artifact_type(self):
        self.assertEqual(self.data["artifact_type"], "clean_public_snapshot_build")

    def test_snapshot_build_script_added(self):
        self._assert_true("snapshot_build_script_added")

    def test_snapshot_build_docs_added(self):
        self._assert_true("snapshot_build_docs_added")

    def test_validation_test_added(self):
        self._assert_true("validation_test_added")

    def test_local_only_snapshot_build(self):
        self._assert_true("local_only_snapshot_build")

    def test_clean_public_snapshot_required_by_gl160(self):
        self._assert_true("clean_public_snapshot_required_by_gl160")

    def test_full_history_publication_allowed_false(self):
        self._assert_false("full_history_publication_allowed")

    def test_manual_approval_required_before_publication(self):
        self._assert_true("manual_approval_required_before_publication")

    def test_copies_tracked_files_only(self):
        self._assert_true("copies_tracked_files_only")

    def test_excludes_git_directory(self):
        self._assert_true("excludes_git_directory")

    def test_excludes_claude_directory(self):
        self._assert_true("excludes_claude_directory")

    def test_refuses_dirty_tracked_tree_by_default(self):
        self._assert_true("refuses_dirty_tracked_tree_by_default")

    def test_allow_dirty_requires_explicit_flag(self):
        self._assert_true("allow_dirty_requires_explicit_flag")

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

    def test_included_content_categories_present(self):
        cats = self.data.get("included_content_categories", [])
        self.assertIsInstance(cats, list)
        self.assertGreater(len(cats), 5)

    def test_excluded_content_categories_present(self):
        cats = self.data.get("excluded_content_categories", [])
        self.assertIsInstance(cats, list)
        self.assertGreater(len(cats), 5)

    def test_validation_checklist_present(self):
        checklist = self.data.get("validation_checklist", [])
        self.assertIsInstance(checklist, list)
        self.assertGreater(len(checklist), 5)

    def test_gl162_handoff_inputs_present(self):
        inputs = self.data.get("gl162_handoff_inputs", [])
        self.assertIsInstance(inputs, list)
        self.assertGreater(len(inputs), 3)

    def test_validation_gates_present(self):
        gates = self.data.get("validation_gates", {})
        self.assertIsInstance(gates, dict)
        self.assertGreater(len(gates), 5)

    def test_next_issue(self):
        next_issue = self.data.get("next_issue", "")
        self.assertIn("GL-162", next_issue)
        self.assertIn("GitHub Public Repository Metadata", next_issue)


# ---------------------------------------------------------------------------
# Documentation content
# ---------------------------------------------------------------------------

class TestGL161DocContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SNAPSHOT_DOC, "r", encoding="utf-8") as f:
            cls.doc_text = f.read()
            cls.doc_lower = cls.doc_text.lower()

    def test_developer_preview_caveat(self):
        self.assertIn("Developer Preview", self.doc_text)

    def test_local_snapshot_only_status(self):
        self.assertIn("local snapshot only", self.doc_lower)

    def test_not_production_saas_caveat(self):
        self.assertIn("not production saas", self.doc_lower)

    def test_tenant_isolation_not_implemented(self):
        self.assertIn("tenant isolation is not implemented", self.doc_lower)

    def test_no_real_secrets(self):
        self.assertIn("no real secrets", self.doc_lower)

    def test_no_real_customer_data(self):
        self.assertIn("no real customer data", self.doc_lower)

    def test_clean_public_snapshot_reference(self):
        self.assertIn("clean public snapshot", self.doc_lower)

    def test_full_history_publication_disallowed(self):
        self.assertIn("full history publication disallowed", self.doc_lower)

    def test_manual_approval_required(self):
        self.assertIn("manual approval required", self.doc_lower)

    def test_gl162_reference(self):
        self.assertIn("GL-162 GitHub Public Repository Metadata / Publish Gate", self.doc_text)

    def test_no_github_publication(self):
        self.assertIn("no github publication", self.doc_lower)

    def test_no_history_rewrite(self):
        self.assertIn("no history rewrite", self.doc_lower)

    def test_prerequisites_section_present(self):
        self.assertIn("prerequisites", self.doc_lower)

    def test_how_to_run_section_present(self):
        self.assertIn("how to run", self.doc_lower)

    def test_what_is_included_section_present(self):
        self.assertIn("what is included", self.doc_lower)

    def test_what_is_excluded_section_present(self):
        self.assertIn("what is excluded", self.doc_lower)

    def test_validation_checklist_section_present(self):
        self.assertIn("validation checklist", self.doc_lower)

    def test_gl162_handoff_section_present(self):
        self.assertIn("gl-162", self.doc_lower)

    def test_risk_register_section_present(self):
        self.assertIn("risk register", self.doc_lower)

    def test_rollback_abort_section_present(self):
        self.assertIn("rollback", self.doc_lower)

    def test_non_goals_section_present(self):
        self.assertIn("non-goals", self.doc_lower)


# ---------------------------------------------------------------------------
# Synthetic snapshot tests — creates a temp git repo and runs the script
# ---------------------------------------------------------------------------

class TestGL161SyntheticSnapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.mkdtemp(prefix="gl161-snap-")
        cls.snapshot_dir = os.path.join(cls.tmp_dir, "snapshot-output")
        try:
            _create_base_repo(cls.tmp_dir)
            script_path = os.path.join(cls.tmp_dir, "scripts", "build-clean-public-snapshot.sh")
            result = subprocess.run(
                ["bash", script_path, "--output", cls.snapshot_dir],
                cwd=cls.tmp_dir, capture_output=True, text=True
            )
            cls.result = result
        except Exception as exc:
            cls.result = None
            cls.setup_error = str(exc)
        else:
            cls.setup_error = None

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def _require_setup(self):
        if self.setup_error:
            self.fail(f"setUpClass failed: {self.setup_error}")

    def test_script_exits_zero(self):
        self._require_setup()
        self.assertEqual(
            self.result.returncode, 0,
            f"Script should exit 0 on clean repo.\nstdout: {self.result.stdout}\nstderr: {self.result.stderr}"
        )

    def test_public_file_included(self):
        self._require_setup()
        self.assertTrue(
            os.path.isfile(os.path.join(self.snapshot_dir, "public_file.txt")),
            "public_file.txt should be present in snapshot"
        )

    def test_git_excluded(self):
        self._require_setup()
        self.assertFalse(
            os.path.exists(os.path.join(self.snapshot_dir, ".git")),
            ".git should not be present in snapshot"
        )

    def test_claude_directory_excluded(self):
        self._require_setup()
        self.assertFalse(
            os.path.exists(os.path.join(self.snapshot_dir, ".claude")),
            ".claude should not be present in snapshot (tracked .claude/ignored.txt must be excluded)"
        )

    def test_tracked_claude_file_excluded(self):
        self._require_setup()
        self.assertFalse(
            os.path.isfile(os.path.join(self.snapshot_dir, ".claude", "ignored.txt")),
            "tracked .claude/ignored.txt must be excluded from snapshot by grep filter"
        )

    def test_untracked_claude_secret_excluded(self):
        self._require_setup()
        self.assertFalse(
            os.path.isfile(os.path.join(self.snapshot_dir, ".claude", "secret.txt")),
            "untracked .claude/secret.txt must not be present in snapshot"
        )

    def test_license_included(self):
        self._require_setup()
        self.assertTrue(
            os.path.isfile(os.path.join(self.snapshot_dir, "LICENSE")),
            "LICENSE should be present in snapshot"
        )


# ---------------------------------------------------------------------------
# Dirty tree refusal
# ---------------------------------------------------------------------------

class TestGL161DirtyTreeRefusal(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="gl161-dirty-")
        self.snapshot_dir = os.path.join(self.tmp_dir, "snapshot-output")
        _create_base_repo(self.tmp_dir)
        # Modify a tracked file to make the tree dirty
        with open(os.path.join(self.tmp_dir, "public_file.txt"), "a") as f:
            f.write("dirty uncommitted change\n")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_refuses_dirty_tree(self):
        script_path = os.path.join(self.tmp_dir, "scripts", "build-clean-public-snapshot.sh")
        result = subprocess.run(
            ["bash", script_path, "--output", self.snapshot_dir],
            cwd=self.tmp_dir, capture_output=True, text=True
        )
        self.assertNotEqual(
            result.returncode, 0,
            "Script must refuse a dirty tracked tree without --allow-dirty"
        )


# ---------------------------------------------------------------------------
# Allow-dirty flag
# ---------------------------------------------------------------------------

class TestGL161AllowDirty(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="gl161-allowdirty-")
        self.snapshot_dir = os.path.join(self.tmp_dir, "snapshot-output")
        _create_base_repo(self.tmp_dir)
        # Modify a tracked file to make the tree dirty
        with open(os.path.join(self.tmp_dir, "public_file.txt"), "a") as f:
            f.write("dirty uncommitted change\n")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_allow_dirty_succeeds(self):
        script_path = os.path.join(self.tmp_dir, "scripts", "build-clean-public-snapshot.sh")
        result = subprocess.run(
            ["bash", script_path, "--output", self.snapshot_dir, "--allow-dirty"],
            cwd=self.tmp_dir, capture_output=True, text=True
        )
        self.assertEqual(
            result.returncode, 0,
            f"Script must succeed with --allow-dirty on dirty tree.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# Forbidden content
# ---------------------------------------------------------------------------

class TestGL161NoForbiddenContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SNAPSHOT_DOC, "r", encoding="utf-8") as f:
            cls.doc_text = f.read()
        with open(SNAPSHOT_JSON, "r", encoding="utf-8") as f:
            cls.json_text = f.read()
        with open(SNAPSHOT_SCRIPT, "r", encoding="utf-8") as f:
            cls.script_text = f.read()

    def test_no_forge_hostname_in_doc(self):
        self.assertNotIn("forge.hofercloud.eu", self.doc_text)

    def test_no_forge_hostname_in_json(self):
        self.assertNotIn("forge.hofercloud.eu", self.json_text)

    def test_no_forge_hostname_in_script(self):
        self.assertNotIn("forge.hofercloud.eu", self.script_text)

    def test_no_terminal_hostname_in_doc(self):
        self.assertNotIn("terminal.hofercloud.eu", self.doc_text)

    def test_no_terminal_hostname_in_json(self):
        self.assertNotIn("terminal.hofercloud.eu", self.json_text)

    def test_no_terminal_hostname_in_script(self):
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

    def test_no_private_key_in_doc(self):
        self.assertNotIn("BEGIN RSA PRIVATE KEY", self.doc_text)
        self.assertNotIn("BEGIN OPENSSH PRIVATE KEY", self.doc_text)
        self.assertNotIn("BEGIN PRIVATE KEY", self.doc_text)

    def test_no_private_key_in_json(self):
        self.assertNotIn("BEGIN RSA PRIVATE KEY", self.json_text)
        self.assertNotIn("BEGIN OPENSSH PRIVATE KEY", self.json_text)
        self.assertNotIn("BEGIN PRIVATE KEY", self.json_text)

    def test_no_private_key_in_script(self):
        self.assertNotIn("BEGIN RSA PRIVATE KEY", self.script_text)
        self.assertNotIn("BEGIN OPENSSH PRIVATE KEY", self.script_text)
        self.assertNotIn("BEGIN PRIVATE KEY", self.script_text)


# ---------------------------------------------------------------------------
# Scope guard (skipped if not on GL-161 branch)
# ---------------------------------------------------------------------------

class TestGL161ScopeGuard(unittest.TestCase):
    _BRANCH = "gl-161-clean-public-snapshot-build"

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
                f"Not on GL-161 branch (current: {branch}); skipping diff assertions"
            )

        changed = self._get_changed_files()

        allowed = {
            "scripts/build-clean-public-snapshot.sh",
            "docs/clean_public_snapshot_build.md",
            "docs/examples/gl161/clean_public_snapshot_build.json",
            "backend/tests/test_gl161_clean_public_snapshot_build.py",
            # allowed only if necessary
            "README.md",
            "SECURITY.md",
            "CONTRIBUTING.md",
            "AGENTS.md",
            "docs/public_github_go_no_go_decision.md",
            "docs/github_private_mirror_dry_run.md",
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
                self.assertNotEqual(f, exact, f"Forbidden file changed: {f}")

        unexpected = [f for f in changed if f not in allowed]
        self.assertEqual(
            unexpected, [],
            f"Unexpected files changed outside allowed set: {unexpected}"
        )


if __name__ == "__main__":
    unittest.main()
