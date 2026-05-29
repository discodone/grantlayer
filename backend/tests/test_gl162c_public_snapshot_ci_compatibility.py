"""
GL-162C Validation: Public GitHub CI Snapshot Compatibility.

Covers:
- File existence checks (build script, JSON artifact, this test file)
- JSON artifact validation (parses, required boolean fields)
- Build script content check (.github/workflows/postgres-ci.yml in exclusion list,
  backend-dependent workflow runtime check present)
- Snapshot content tests: postgres-ci.yml absent, no workflow references backend.tests,
  backend/ and .claude/ excluded, required public files present
- Scanner pass: git init + git add + run public-secret-sensitive-scan.sh in snapshot
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
SNAPSHOT_JSON = os.path.join(REPO_ROOT, "docs", "examples", "gl162c",
                              "public_github_ci_snapshot_compatibility.json")
THIS_TEST = os.path.join(REPO_ROOT, "backend", "tests",
                         "test_gl162c_public_snapshot_ci_compatibility.py")

POSTGRES_CI_WORKFLOW = ".github/workflows/postgres-ci.yml"

# Files that must be absent from the public snapshot.
EXCLUDED_FROM_SNAPSHOT = [
    POSTGRES_CI_WORKFLOW,
    "backend/tests/test_gl162c_public_snapshot_ci_compatibility.py",
    "docs/examples/gl162c/public_github_ci_snapshot_compatibility.json",
    # GL-162B exclusions must remain intact
    "backend/tests/test_gl157_public_secret_sensitive_scan_gate.py",
    "backend/tests/test_gl161_clean_public_snapshot_build.py",
    "backend/tests/test_gl162b_public_snapshot_scanner_clean_export.py",
    "docs/public_secret_sensitive_scan_gate.md",
    "docs/examples/gl136/key_hygiene.json",
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

FORBIDDEN_STRINGS = [
    "forge.hofercloud.eu",
    "/home/adminuser",
    "/home/oai",
    "/mnt/data",
    "BEGIN RSA PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
]


def _build_snapshot(output_dir):
    return subprocess.run(
        ["bash", SNAPSHOT_SCRIPT, "--allow-dirty", "--output", output_dir],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def _init_snapshot_git(snapshot_dir):
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

class TestGL162CFilesExist(unittest.TestCase):
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

class TestGL162CJsonArtifact(unittest.TestCase):
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
        self.assertEqual(self.data["issue_id"], "GL-162C")

    def test_artifact_type(self):
        self.assertEqual(self.data["artifact_type"], "public_github_ci_snapshot_compatibility")

    def test_postgres_ci_workflow_excluded(self):
        self._assert_true("postgres_ci_workflow_excluded_from_snapshot")

    def test_backend_dependent_workflows_blocked(self):
        self._assert_true("backend_dependent_workflows_blocked_at_build_time")

    def test_public_export_exclusion_list_updated(self):
        self._assert_true("public_export_exclusion_list_updated")

    def test_backend_directory_absent(self):
        self._assert_true("backend_directory_absent_from_snapshot")

    def test_claude_directory_absent(self):
        self._assert_true("claude_directory_absent_from_snapshot")

    def test_no_public_workflow_references_backend_tests(self):
        self._assert_true("no_public_workflow_references_backend_tests")

    def test_scanner_clean_guarantee_preserved(self):
        self._assert_true("scanner_clean_guarantee_preserved")

    def test_gl162b_exclusions_intact(self):
        self._assert_true("gl162b_exclusions_intact")

    def test_internal_validation_not_weakened(self):
        self._assert_true("internal_validation_not_weakened")

    def test_github_publication_performed_false(self):
        self._assert_false("github_publication_performed")

    def test_github_api_called_false(self):
        self._assert_false("github_api_called")

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

    def test_uses_real_secrets_false(self):
        self._assert_false("uses_real_secrets")

    def test_uses_real_customer_data_false(self):
        self._assert_false("uses_real_customer_data")

    def test_next_step_present(self):
        self.assertIn("next_step", self.data)
        self.assertIsInstance(self.data["next_step"], str)
        self.assertGreater(len(self.data["next_step"]), 10)


# ---------------------------------------------------------------------------
# Build script content
# ---------------------------------------------------------------------------

class TestGL162CBuildScriptContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SNAPSHOT_SCRIPT, "r", encoding="utf-8") as f:
            cls.script_text = f.read()

    def test_script_has_public_export_exclude_array(self):
        self.assertIn("PUBLIC_EXPORT_EXCLUDE", self.script_text)

    def test_script_excludes_postgres_ci_workflow(self):
        self.assertIn(".github/workflows/postgres-ci.yml", self.script_text,
                      "Build script must exclude .github/workflows/postgres-ci.yml")

    def test_script_has_backend_workflow_check(self):
        self.assertIn("backend[./]tests", self.script_text,
                      "Build script must grep for backend-dependent workflows in Step 5")

    def test_script_excludes_gl162c_test(self):
        self.assertIn("test_gl162c_public_snapshot_ci_compatibility.py", self.script_text)

    def test_script_excludes_gl162c_json(self):
        self.assertIn("docs/examples/gl162c/public_github_ci_snapshot_compatibility.json",
                      self.script_text)

    def test_script_no_git_push(self):
        self.assertNotIn("git push", self.script_text)

    def test_script_no_gh_api(self):
        self.assertNotIn("gh api", self.script_text)

    def test_script_gl162b_exclusions_still_present(self):
        self.assertIn("test_gl162b_public_snapshot_scanner_clean_export.py", self.script_text,
                      "GL-162B exclusions must still be present")


# ---------------------------------------------------------------------------
# Snapshot content
# ---------------------------------------------------------------------------

class TestGL162CSnapshotContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.mkdtemp(prefix="gl162c-snap-")
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

    def test_postgres_ci_workflow_absent(self):
        self._require_build()
        path = os.path.join(self.snapshot_dir, POSTGRES_CI_WORKFLOW)
        self.assertFalse(
            os.path.exists(path),
            f"{POSTGRES_CI_WORKFLOW} must NOT be present in public snapshot "
            "(requires backend/ which is intentionally excluded)"
        )

    def test_no_backend_dependent_workflows(self):
        self._require_build()
        workflows_dir = os.path.join(self.snapshot_dir, ".github", "workflows")
        if not os.path.isdir(workflows_dir):
            return
        for fname in os.listdir(workflows_dir):
            if not (fname.endswith(".yml") or fname.endswith(".yaml")):
                continue
            fpath = os.path.join(workflows_dir, fname)
            with open(fpath, encoding="utf-8", errors="replace") as f:
                content = f.read()
            self.assertNotIn(
                "backend.tests", content,
                f"{fname} references backend.tests — backend/ is absent from the snapshot"
            )
            self.assertNotIn(
                "backend/tests", content,
                f"{fname} references backend/tests — backend/ is absent from the snapshot"
            )

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

    def test_backend_directory_excluded(self):
        self._require_build()
        self.assertFalse(
            os.path.isdir(os.path.join(self.snapshot_dir, "backend")),
            "backend/ must NOT be present in public snapshot"
        )

    def test_required_public_files_present(self):
        self._require_build()
        for rel in PUBLIC_FILES_REQUIRED:
            self.assertTrue(
                os.path.isfile(os.path.join(self.snapshot_dir, rel)),
                f"Required public file missing from snapshot: {rel}"
            )

    def test_excluded_files_absent(self):
        self._require_build()
        for rel in EXCLUDED_FROM_SNAPSHOT:
            self.assertFalse(
                os.path.exists(os.path.join(self.snapshot_dir, rel)),
                f"Must NOT be in snapshot: {rel}"
            )


# ---------------------------------------------------------------------------
# Scanner pass
# ---------------------------------------------------------------------------

class TestGL162CScannerPass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.mkdtemp(prefix="gl162c-scan-")
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

class TestGL162CForbiddenContentInSnapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.mkdtemp(prefix="gl162c-grep-")
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
        self.assertEqual(found, "",
                         f"Forbidden pattern found in snapshot: {pattern!r}\n{found}")

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

class TestGL162CInternalValidationNotWeakened(unittest.TestCase):
    def test_scanner_script_still_in_source_repo(self):
        self.assertTrue(os.path.isfile(SCAN_SCRIPT),
                        f"Scanner script missing from source repo: {SCAN_SCRIPT}")

    def test_gl157_test_still_in_source_repo(self):
        gl157 = os.path.join(REPO_ROOT, "backend", "tests",
                              "test_gl157_public_secret_sensitive_scan_gate.py")
        self.assertTrue(os.path.isfile(gl157),
                        f"GL-157 scanner test missing from source repo: {gl157}")

    def test_gl162b_test_still_in_source_repo(self):
        gl162b = os.path.join(REPO_ROOT, "backend", "tests",
                               "test_gl162b_public_snapshot_scanner_clean_export.py")
        self.assertTrue(os.path.isfile(gl162b),
                        f"GL-162B test missing from source repo: {gl162b}")

    def test_postgres_ci_workflow_still_in_source_repo(self):
        wf = os.path.join(REPO_ROOT, ".github", "workflows", "postgres-ci.yml")
        self.assertTrue(os.path.isfile(wf),
                        f"postgres-ci.yml missing from internal source repo: {wf} "
                        "(must remain internal — only excluded from public snapshot export)")

    def test_scanner_script_executable(self):
        self.assertTrue(os.access(SCAN_SCRIPT, os.X_OK),
                        f"Scanner script not executable: {SCAN_SCRIPT}")


# ---------------------------------------------------------------------------
# Branch scope guard
# ---------------------------------------------------------------------------

class TestGL162CScopeGuard(unittest.TestCase):
    _BRANCH = "gl-162c-public-snapshot-ci-compatibility"

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
                f"Not on GL-162C branch (current: {branch}); skipping diff assertions"
            )

        changed = self._get_changed_files()

        allowed = {
            "scripts/build-clean-public-snapshot.sh",
            "backend/tests/test_gl162c_public_snapshot_ci_compatibility.py",
            "docs/examples/gl162c/public_github_ci_snapshot_compatibility.json",
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
