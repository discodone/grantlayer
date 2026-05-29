"""
GL-162B Validation: Public Snapshot Scanner-Clean Export.

Covers:
- File existence checks (script, JSON artifact, scan script, this test file)
- JSON artifact validation (parses, required boolean fields)
- Build script content check (public export exclusion logic present)
- Snapshot content tests: excluded internal gate fixtures absent, public files present
- Scanner pass test: git init + git add + run public-secret-sensitive-scan.sh in snapshot
- Forbidden content grep in snapshot (no internal hostnames, paths, private key markers)
- Internal validation not weakened: scanner script and GL-157 test still in source repo
- Branch scope guard
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

SNAPSHOT_SCRIPT = os.path.join(REPO_ROOT, "scripts", "build-clean-public-snapshot.sh")
SCAN_SCRIPT = os.path.join(REPO_ROOT, "scripts", "public-secret-sensitive-scan.sh")
SNAPSHOT_JSON = os.path.join(REPO_ROOT, "docs", "examples", "gl162b",
                              "public_snapshot_scanner_clean_export.json")
THIS_TEST = os.path.join(REPO_ROOT, "backend", "tests",
                         "test_gl162b_public_snapshot_scanner_clean_export.py")

# Files that must be absent from the public snapshot (internal gate/scanner/meta fixtures).
INTERNAL_GATE_FIXTURES_EXCLUDED = [
    "backend/tests/test_gl157_public_secret_sensitive_scan_gate.py",
    "backend/tests/test_gl158_git_history_exposure_review_public_snapshot_decision.py",
    "backend/tests/test_gl159_github_private_mirror_dry_run.py",
    "backend/tests/test_gl160_public_github_go_no_go_decision.py",
    "backend/tests/test_gl161_clean_public_snapshot_build.py",
    "backend/tests/test_gl162_github_public_repository_publish_gate.py",
    "backend/tests/test_gl162a_pre_publication_security_review_fixes.py",
    "backend/tests/test_gl162b_public_snapshot_scanner_clean_export.py",
    "docs/public_secret_sensitive_scan_gate.md",
    "docs/git_history_exposure_review_public_snapshot_decision.md",
    "docs/github_private_mirror_dry_run.md",
    "docs/public_github_go_no_go_decision.md",
    "docs/clean_public_snapshot_build.md",
    "docs/github_public_repository_publish_gate.md",
    "docs/examples/gl136/key_hygiene.json",
    "docs/examples/gl157/public_secret_sensitive_scan_gate.json",
    "docs/examples/gl158/git_history_exposure_review_public_snapshot_decision.json",
    "docs/examples/gl159/github_private_mirror_dry_run.json",
    "docs/examples/gl160/public_github_go_no_go_decision.json",
    "docs/examples/gl161/clean_public_snapshot_build.json",
    "docs/examples/gl162/github_public_repository_publish_gate.json",
    "docs/examples/gl162b/public_snapshot_scanner_clean_export.json",
]

# Files that must be present in the public snapshot.
PUBLIC_FILES_REQUIRED = [
    "README.md",
    "LICENSE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "AGENTS.md",
]

# Forbidden content strings that must not appear anywhere in the snapshot.
FORBIDDEN_STRINGS = [
    "forge.hofercloud.eu",
    "/home/adminuser",
    "/home/oai",
    "/mnt/data",
    "BEGIN RSA PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
]


def _build_snapshot(output_dir):
    """Run the build script with --allow-dirty against the real repo."""
    return subprocess.run(
        ["bash", SNAPSHOT_SCRIPT, "--allow-dirty", "--output", output_dir],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def _init_snapshot_git(snapshot_dir):
    """Run git init and git add . inside the snapshot directory."""
    subprocess.run(["git", "init", snapshot_dir], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=snapshot_dir, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=snapshot_dir, check=True, capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=snapshot_dir, check=True, capture_output=True)


# ---------------------------------------------------------------------------
# File existence
# ---------------------------------------------------------------------------

class TestGL162BFilesExist(unittest.TestCase):
    def test_snapshot_script_exists(self):
        self.assertTrue(os.path.isfile(SNAPSHOT_SCRIPT), f"Missing: {SNAPSHOT_SCRIPT}")

    def test_scan_script_exists(self):
        self.assertTrue(os.path.isfile(SCAN_SCRIPT), f"Missing: {SCAN_SCRIPT}")

    def test_json_artifact_exists(self):
        self.assertTrue(os.path.isfile(SNAPSHOT_JSON), f"Missing: {SNAPSHOT_JSON}")

    def test_validation_test_exists(self):
        self.assertTrue(os.path.isfile(THIS_TEST), f"Missing: {THIS_TEST}")

    def test_script_is_executable(self):
        self.assertTrue(os.access(SNAPSHOT_SCRIPT, os.X_OK),
                        f"Script not executable: {SNAPSHOT_SCRIPT}")


# ---------------------------------------------------------------------------
# JSON artifact
# ---------------------------------------------------------------------------

class TestGL162BJsonArtifact(unittest.TestCase):
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
        self.assertEqual(self.data["issue_id"], "GL-162B")

    def test_artifact_type(self):
        self.assertEqual(self.data["artifact_type"], "public_snapshot_scanner_clean_export")

    def test_public_snapshot_export_exclusions_added(self):
        self._assert_true("public_snapshot_export_exclusions_added")

    def test_scanner_clean_snapshot_required(self):
        self._assert_true("scanner_clean_snapshot_required")

    def test_internal_gate_fixtures_excluded(self):
        self._assert_true("internal_gate_fixtures_excluded")

    def test_scanner_meta_files_excluded(self):
        self._assert_true("scanner_meta_files_excluded")

    def test_synthetic_private_key_marker_fixtures_excluded(self):
        self._assert_true("synthetic_private_key_marker_fixtures_excluded")

    def test_internal_path_marker_fixtures_excluded(self):
        self._assert_true("internal_path_marker_fixtures_excluded")

    def test_internal_hostname_marker_fixtures_excluded(self):
        self._assert_true("internal_hostname_marker_fixtures_excluded")

    def test_product_public_docs_preserved(self):
        self._assert_true("product_public_docs_preserved")

    def test_agent_entrypoints_preserved(self):
        self._assert_true("agent_entrypoints_preserved")

    def test_sdk_preserved(self):
        self._assert_true("sdk_preserved")

    def test_examples_agents_preserved(self):
        self._assert_true("examples_agents_preserved")

    def test_github_templates_preserved(self):
        self._assert_true("github_templates_preserved")

    def test_internal_validation_not_weakened(self):
        self._assert_true("internal_validation_not_weakened")

    def test_github_publication_performed_false(self):
        self._assert_false("github_publication_performed")

    def test_github_api_called_false(self):
        self._assert_false("github_api_called")

    def test_public_repo_created_false(self):
        self._assert_false("public_repo_created")

    def test_git_remotes_changed_false(self):
        self._assert_false("git_remotes_changed")

    def test_history_rewrite_performed_false(self):
        self._assert_false("history_rewrite_performed")

    def test_secret_history_cleanup_performed_false(self):
        self._assert_false("secret_history_cleanup_performed")

    def test_production_code_changed_false(self):
        self._assert_false("production_code_changed")

    def test_backend_src_changed_false(self):
        self._assert_false("backend_src_changed")

    def test_openapi_changed_false(self):
        self._assert_false("openapi_changed")

    def test_db_schema_changed_false(self):
        self._assert_false("db_schema_changed")

    def test_dependencies_changed_false(self):
        self._assert_false("dependencies_changed")

    def test_sdk_changed_false(self):
        self._assert_false("sdk_changed")

    def test_frontend_website_design_changed_false(self):
        self._assert_false("frontend_website_design_changed")

    def test_uses_real_secrets_false(self):
        self._assert_false("uses_real_secrets")

    def test_uses_real_customer_data_false(self):
        self._assert_false("uses_real_customer_data")

    def test_includes_private_personal_data_false(self):
        self._assert_false("includes_private_personal_data")

    def test_next_step_present(self):
        self.assertIn("next_step", self.data)
        self.assertIsInstance(self.data["next_step"], str)
        self.assertGreater(len(self.data["next_step"]), 10)


# ---------------------------------------------------------------------------
# Build script content check
# ---------------------------------------------------------------------------

class TestGL162BBuildScriptContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SNAPSHOT_SCRIPT, "r", encoding="utf-8") as f:
            cls.script_text = f.read()

    def test_script_has_public_export_exclude_array(self):
        self.assertIn("PUBLIC_EXPORT_EXCLUDE", self.script_text,
                      "Script must define PUBLIC_EXPORT_EXCLUDE array")

    def test_script_has_grep_vfxf_exclusion(self):
        self.assertIn("grep -vFxf", self.script_text,
                      "Script must apply exclusion list with grep -vFxf")

    def test_script_excludes_test_gl157(self):
        self.assertIn("test_gl157_public_secret_sensitive_scan_gate.py", self.script_text)

    def test_script_excludes_test_gl161(self):
        self.assertIn("test_gl161_clean_public_snapshot_build.py", self.script_text)

    def test_script_excludes_key_hygiene_json(self):
        self.assertIn("docs/examples/gl136/key_hygiene.json", self.script_text)

    def test_script_excludes_scanner_meta_doc(self):
        self.assertIn("docs/public_secret_sensitive_scan_gate.md", self.script_text)

    def test_script_no_git_push(self):
        self.assertNotIn("git push", self.script_text)

    def test_script_no_gh_api(self):
        self.assertNotIn("gh api", self.script_text)


# ---------------------------------------------------------------------------
# Snapshot build and content tests
# ---------------------------------------------------------------------------

class TestGL162BSnapshotContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.mkdtemp(prefix="gl162b-snap-")
        cls.snapshot_dir = os.path.join(cls.tmp_dir, "snapshot")
        try:
            result = _build_snapshot(cls.snapshot_dir)
            cls.build_result = result
            cls.build_ok = (result.returncode == 0)
        except Exception as exc:
            cls.build_result = None
            cls.build_ok = False
            cls.setup_error = str(exc)
        else:
            cls.setup_error = None

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def _require_build(self):
        if not self.build_ok:
            stdout = getattr(self.build_result, "stdout", "")
            stderr = getattr(self.build_result, "stderr", "")
            self.fail(
                f"Snapshot build failed (rc={getattr(self.build_result, 'returncode', '?')}).\n"
                f"stdout: {stdout}\nstderr: {stderr}\nsetup_error: {self.setup_error}"
            )

    def test_build_exits_zero(self):
        self._require_build()

    def test_no_git_in_snapshot(self):
        self._require_build()
        self.assertFalse(
            os.path.exists(os.path.join(self.snapshot_dir, ".git")),
            ".git must not be present in snapshot"
        )

    def test_no_claude_in_snapshot(self):
        self._require_build()
        self.assertFalse(
            os.path.exists(os.path.join(self.snapshot_dir, ".claude")),
            ".claude must not be present in snapshot"
        )

    def test_required_public_files_present(self):
        self._require_build()
        for rel in PUBLIC_FILES_REQUIRED:
            path = os.path.join(self.snapshot_dir, rel)
            self.assertTrue(
                os.path.isfile(path),
                f"Required public file missing from snapshot: {rel}"
            )

    def test_llms_txt_present(self):
        self._require_build()
        self.assertTrue(
            os.path.isfile(os.path.join(self.snapshot_dir, "llms.txt")),
            "llms.txt should be in snapshot"
        )

    def test_llms_full_txt_present(self):
        self._require_build()
        self.assertTrue(
            os.path.isfile(os.path.join(self.snapshot_dir, "llms-full.txt")),
            "llms-full.txt should be in snapshot"
        )

    def test_sdk_python_present(self):
        self._require_build()
        sdk_dir = os.path.join(self.snapshot_dir, "sdk", "python")
        self.assertTrue(
            os.path.isdir(sdk_dir),
            f"sdk/python should be in snapshot: {sdk_dir}"
        )

    def test_github_templates_present(self):
        self._require_build()
        github_dir = os.path.join(self.snapshot_dir, ".github")
        self.assertTrue(
            os.path.isdir(github_dir),
            ".github templates should be in snapshot"
        )

    def test_backend_directory_excluded(self):
        self._require_build()
        backend_dir = os.path.join(self.snapshot_dir, "backend")
        self.assertFalse(
            os.path.isdir(backend_dir),
            "backend/ directory must NOT be present in public snapshot "
            "(contains legitimate code patterns that trigger the scanner heuristic)"
        )

    def test_internal_gate_fixtures_excluded(self):
        self._require_build()
        for rel in INTERNAL_GATE_FIXTURES_EXCLUDED:
            path = os.path.join(self.snapshot_dir, rel)
            self.assertFalse(
                os.path.exists(path),
                f"Internal gate fixture must NOT be in snapshot: {rel}"
            )


# ---------------------------------------------------------------------------
# Scanner pass test
# ---------------------------------------------------------------------------

class TestGL162BScannerPass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.mkdtemp(prefix="gl162b-scan-")
        cls.snapshot_dir = os.path.join(cls.tmp_dir, "snapshot")
        cls.scan_result = None
        cls.build_ok = False
        cls.init_ok = False

        try:
            build = _build_snapshot(cls.snapshot_dir)
            if build.returncode != 0:
                cls.build_stdout = build.stdout
                cls.build_stderr = build.stderr
                return
            cls.build_ok = True

            _init_snapshot_git(cls.snapshot_dir)
            cls.init_ok = True

            cls.scan_result = subprocess.run(
                ["bash", "scripts/public-secret-sensitive-scan.sh"],
                cwd=cls.snapshot_dir,
                capture_output=True,
                text=True,
            )
        except Exception as exc:
            cls.setup_exc = str(exc)
        else:
            cls.setup_exc = None

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def test_scanner_exits_clean(self):
        if not self.build_ok:
            self.skipTest("Snapshot build failed — skipping scanner test")
        if not self.init_ok:
            self.skipTest("git init/add failed — skipping scanner test")
        self.assertIsNotNone(self.scan_result, "Scanner did not run")
        self.assertEqual(
            self.scan_result.returncode, 0,
            f"Scanner found blockers in snapshot.\n"
            f"stdout:\n{self.scan_result.stdout}\n"
            f"stderr:\n{self.scan_result.stderr}"
        )


# ---------------------------------------------------------------------------
# Forbidden content in snapshot
# ---------------------------------------------------------------------------

class TestGL162BForbiddenContentInSnapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.mkdtemp(prefix="gl162b-grep-")
        cls.snapshot_dir = os.path.join(cls.tmp_dir, "snapshot")
        cls.build_ok = False
        try:
            build = _build_snapshot(cls.snapshot_dir)
            cls.build_ok = (build.returncode == 0)
        except Exception:
            cls.build_ok = False

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def _grep_snapshot(self, pattern):
        result = subprocess.run(
            ["grep", "-rF",
             # The scanner script itself mentions internal hostnames/paths as regex patterns
             # in its help text — exclude it from forbidden-content grep.
             "--exclude=public-secret-sensitive-scan.sh",
             pattern, "."],
            cwd=self.snapshot_dir,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def _check_absent(self, pattern):
        if not self.build_ok:
            self.skipTest("Snapshot build failed")
        found = self._grep_snapshot(pattern)
        self.assertEqual(
            found, "",
            f"Forbidden pattern found in snapshot: {pattern!r}\n{found}"
        )

    def test_no_forge_hostname(self):
        self._check_absent("forge.hofercloud.eu")

    def test_no_home_adminuser(self):
        self._check_absent("/home/adminuser")

    def test_no_home_oai(self):
        self._check_absent("/home/oai")

    def test_no_mnt_data(self):
        self._check_absent("/mnt/data")

    def test_no_begin_rsa_private_key(self):
        self._check_absent("BEGIN RSA PRIVATE KEY")

    def test_no_begin_openssh_private_key(self):
        self._check_absent("BEGIN OPENSSH PRIVATE KEY")


# ---------------------------------------------------------------------------
# Internal validation not weakened
# ---------------------------------------------------------------------------

class TestGL162BInternalValidationNotWeakened(unittest.TestCase):
    def test_scanner_script_still_in_source_repo(self):
        self.assertTrue(os.path.isfile(SCAN_SCRIPT),
                        f"Scanner script missing from source repo: {SCAN_SCRIPT}")

    def test_gl157_test_still_in_source_repo(self):
        gl157_test = os.path.join(REPO_ROOT, "backend", "tests",
                                  "test_gl157_public_secret_sensitive_scan_gate.py")
        self.assertTrue(os.path.isfile(gl157_test),
                        f"GL-157 scanner test missing from source repo: {gl157_test}")

    def test_scanner_script_executable(self):
        self.assertTrue(os.access(SCAN_SCRIPT, os.X_OK),
                        f"Scanner script not executable: {SCAN_SCRIPT}")


# ---------------------------------------------------------------------------
# Branch scope guard
# ---------------------------------------------------------------------------

class TestGL162BScopeGuard(unittest.TestCase):
    _BRANCH = "gl-162b-public-snapshot-scanner-clean-export"

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
                f"Not on GL-162B branch (current: {branch}); skipping diff assertions"
            )

        changed = self._get_changed_files()

        allowed = {
            "scripts/build-clean-public-snapshot.sh",
            "scripts/public-secret-sensitive-scan.sh",
            "docs/clean_public_snapshot_build.md",
            "docs/examples/gl161/clean_public_snapshot_build.json",
            "docs/examples/gl162b/public_snapshot_scanner_clean_export.json",
            "backend/tests/test_gl162b_public_snapshot_scanner_clean_export.py",
            "backend/tests/test_gl161_clean_public_snapshot_build.py",
            ".github/pull_request_template.md",
            # allowed only if necessary
            "docs/github_public_repository_publish_gate.md",
            "docs/examples/gl162/github_public_repository_publish_gate.json",
            "backend/tests/test_gl162_github_public_repository_publish_gate.py",
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
            ".github/workflows/",
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
