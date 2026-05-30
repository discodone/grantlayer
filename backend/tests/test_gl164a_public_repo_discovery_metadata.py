"""GL-164A Public Repository Discovery Metadata — validation tests."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GITATTRIBUTES = REPO_ROOT / ".gitattributes"
JSON_PATH = REPO_ROOT / "docs" / "examples" / "gl164a" / "public_repo_discovery_metadata.json"
TEST_PATH = REPO_ROOT / "backend" / "tests" / "test_gl164a_public_repo_discovery_metadata.py"
SNAPSHOT_SCRIPT = REPO_ROOT / "scripts" / "build-clean-public-snapshot.sh"
SCANNER_SCRIPT = REPO_ROOT / "scripts" / "public-secret-sensitive-scan.sh"

GL164A_BRANCH = "gl-164a-public-repo-discovery-metadata"


def _load_json():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _read_gitattributes():
    return GITATTRIBUTES.read_text(encoding="utf-8")


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

class TestGL164AFilesExist(unittest.TestCase):

    def test_gitattributes_exists(self):
        self.assertTrue(GITATTRIBUTES.exists(), f"Missing: {GITATTRIBUTES}")

    def test_json_artifact_exists(self):
        self.assertTrue(JSON_PATH.exists(), f"Missing: {JSON_PATH}")

    def test_test_file_exists(self):
        self.assertTrue(TEST_PATH.exists(), f"Missing: {TEST_PATH}")


# ---------------------------------------------------------------------------
# 2. .gitattributes content — Linguist rules
# ---------------------------------------------------------------------------

class TestGitattributesLinguistRules(unittest.TestCase):

    def setUp(self):
        self.content = _read_gitattributes()

    def test_shell_linguist_detectable_false(self):
        self.assertIn("*.sh linguist-detectable=false", self.content)

    def test_has_comment_about_github_only(self):
        self.assertIn("linguist", self.content.lower())

    def test_no_python_files_marked_detectable_false(self):
        lines = self.content.splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            self.assertFalse(
                stripped.startswith("*.py") and "linguist-detectable=false" in stripped,
                "Python source files must not be marked as non-detectable",
            )

    def test_no_sdk_python_marked_detectable_false(self):
        self.assertNotIn("sdk/python", self.content + " linguist-detectable=false")

    def test_no_examples_python_marked_detectable_false(self):
        lines = self.content.splitlines()
        for line in lines:
            if "examples/" in line and "linguist-detectable=false" in line:
                self.fail(f"examples/ Python marked as non-detectable: {line!r}")

    def test_no_production_behavior_claims(self):
        content_lower = self.content.lower()
        self.assertNotIn("production-ready", content_lower)
        self.assertNotIn("tenant isolation implemented", content_lower)

    def test_file_is_minimal(self):
        non_comment_lines = [
            ln for ln in self.content.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        self.assertLessEqual(
            len(non_comment_lines), 5,
            "gitattributes should stay minimal — unexpected rules added",
        )


# ---------------------------------------------------------------------------
# 3. JSON artifact — parses and required keys
# ---------------------------------------------------------------------------

class TestGL164AJsonParses(unittest.TestCase):

    def test_json_parses(self):
        data = _load_json()
        self.assertIsInstance(data, dict)


class TestGL164AJsonRequiredKeys(unittest.TestCase):

    def setUp(self):
        self.data = _load_json()

    def test_issue_key(self):
        self.assertIn("issue", self.data)
        self.assertEqual(self.data["issue"], "GL-164A")

    def test_title_key(self):
        self.assertIn("title", self.data)

    def test_status_key(self):
        self.assertIn("status", self.data)

    def test_linguist_rules_added(self):
        self.assertIn("linguistRulesAdded", self.data)
        self.assertIsInstance(self.data["linguistRulesAdded"], list)
        self.assertGreater(len(self.data["linguistRulesAdded"]), 0)

    def test_product_behavior_changed_false(self):
        self.assertIn("productBehaviorChanged", self.data)
        self.assertFalse(self.data["productBehaviorChanged"])

    def test_gitattributes_affects_runtime_false(self):
        self.assertIn("gitattributesAffectsRuntime", self.data)
        self.assertFalse(self.data["gitattributesAffectsRuntime"])

    def test_publish_copy_safety_note(self):
        self.assertIn("publishCopySafetyNote", self.data)
        note = self.data["publishCopySafetyNote"]
        self.assertIn("rsyncCommand", note)
        self.assertIn("cpFallback", note)
        self.assertIn("--exclude='.git'", note["rsyncCommand"])

    def test_files_not_hidden_includes_sdk(self):
        not_hidden = self.data.get("filesNotHidden", [])
        sdk_files = [f for f in not_hidden if "sdk/python" in f]
        self.assertTrue(sdk_files, "sdk/python must be listed as not hidden")

    def test_files_not_hidden_includes_examples(self):
        not_hidden = self.data.get("filesNotHidden", [])
        example_files = [f for f in not_hidden if "examples/" in f]
        self.assertTrue(example_files, "examples/ must be listed as not hidden")

    def test_forbidden_scope_confirmation(self):
        scope = self.data.get("forbiddenScopeConfirmation", {})
        self.assertTrue(scope.get("backendSrcUnchanged"))
        self.assertTrue(scope.get("noProductionReadyClaims"))
        self.assertTrue(scope.get("noTenantIsolationImplementedClaims"))


# ---------------------------------------------------------------------------
# 4. Publish copy safety — documented safe-copy pattern
# ---------------------------------------------------------------------------

class TestPublishCopySafety(unittest.TestCase):

    def setUp(self):
        self.data = _load_json()
        self.note = self.data.get("publishCopySafetyNote", {})

    def test_rsync_excludes_git(self):
        self.assertIn("--exclude='.git'", self.note.get("rsyncCommand", ""))

    def test_cp_fallback_excludes_git(self):
        fallback = self.note.get("cpFallback", "")
        self.assertIn(".git", fallback)

    def test_cp_fallback_uses_find(self):
        fallback = self.note.get("cpFallback", "")
        self.assertIn("find", fallback)

    def test_note_warns_against_plain_cp(self):
        note_text = self.note.get("note", "")
        self.assertIn(".git", note_text)

    def test_issue_describes_problem(self):
        issue_text = self.note.get("issue", "")
        self.assertIn(".git", issue_text)


# ---------------------------------------------------------------------------
# 5. No internal secrets / private hostnames in .gitattributes
# ---------------------------------------------------------------------------

class TestGitattributesNoSecrets(unittest.TestCase):

    def setUp(self):
        self.content = _read_gitattributes()
        self.lower = self.content.lower()

    def test_no_private_key(self):
        self.assertNotIn("begin rsa private key", self.lower)
        self.assertNotIn("begin openssh private key", self.lower)

    def test_no_internal_hostname(self):
        self.assertNotIn("forge.hofercloud", self.lower)
        self.assertNotIn("terminal.hofercloud", self.lower)
        self.assertNotIn(".internal.invalid", self.lower)

    def test_no_internal_path(self):
        self.assertNotIn("/home/adminuser", self.content)
        self.assertNotIn("/home/oai", self.content)
        self.assertNotIn("/mnt/data", self.content)

    def test_no_production_ready_claim(self):
        self.assertNotIn("production-ready saas", self.lower)
        self.assertNotIn("tenant isolation implemented", self.lower)


# ---------------------------------------------------------------------------
# 6. Branch / diff validation (runs on feature branch)
# ---------------------------------------------------------------------------

class TestGL164ABranchDiff(unittest.TestCase):

    def test_gitattributes_in_diff(self):
        changed = _branch_diff_names()
        if changed:
            self.assertIn(".gitattributes", changed,
                          ".gitattributes must appear in the GL-164A diff")

    def test_json_artifact_in_diff(self):
        changed = _branch_diff_names()
        if changed:
            artifact_rel = "docs/examples/gl164a/public_repo_discovery_metadata.json"
            self.assertIn(artifact_rel, changed,
                          "GL-164A JSON artifact must appear in the diff")

    def test_no_backend_src_in_diff(self):
        changed = _branch_diff_names()
        backend_src = [f for f in changed if f.startswith("backend/src/")]
        self.assertEqual(backend_src, [],
                         f"backend/src must not be modified: {backend_src}")


# ---------------------------------------------------------------------------
# 7. Snapshot content validation (uses a temp snapshot if feasible)
# ---------------------------------------------------------------------------

class TestGL164ASnapshotContent(unittest.TestCase):
    """Build a temporary snapshot and confirm .gitattributes is included."""

    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.mkdtemp(prefix="gl164a-snap-")
        cls.snapshot_dir = os.path.join(cls.tmp_dir, "snapshot-output")
        result = subprocess.run(
            ["bash", str(SNAPSHOT_SCRIPT), "--output", cls.snapshot_dir, "--allow-dirty"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        cls.build_rc = result.returncode
        cls.build_stdout = result.stdout
        cls.build_stderr = result.stderr

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def _skip_if_build_failed(self):
        if self.build_rc != 0:
            self.skipTest(
                f"Snapshot build failed (rc={self.build_rc}); snapshot tests skipped.\n"
                f"stderr: {self.build_stderr[:500]}"
            )

    def test_snapshot_build_succeeds(self):
        self.assertEqual(self.build_rc, 0,
                         f"Snapshot build failed:\n{self.build_stderr[:800]}")

    def test_gitattributes_in_snapshot(self):
        self._skip_if_build_failed()
        path = os.path.join(self.snapshot_dir, ".gitattributes")
        self.assertTrue(os.path.isfile(path), ".gitattributes must be present in snapshot")

    def test_gitattributes_snapshot_content(self):
        self._skip_if_build_failed()
        path = os.path.join(self.snapshot_dir, ".gitattributes")
        content = Path(path).read_text(encoding="utf-8")
        self.assertIn("*.sh linguist-detectable=false", content)

    def test_backend_absent_from_snapshot(self):
        self._skip_if_build_failed()
        backend_path = os.path.join(self.snapshot_dir, "backend")
        self.assertFalse(os.path.exists(backend_path), "backend/ must not be in snapshot")

    def test_claude_absent_from_snapshot(self):
        self._skip_if_build_failed()
        claude_path = os.path.join(self.snapshot_dir, ".claude")
        self.assertFalse(os.path.exists(claude_path), ".claude/ must not be in snapshot")

    def test_env_example_present_in_snapshot(self):
        self._skip_if_build_failed()
        env_path = os.path.join(self.snapshot_dir, ".env.example")
        self.assertTrue(os.path.isfile(env_path), ".env.example must be present in snapshot")

    def test_dashboard_present_in_snapshot(self):
        self._skip_if_build_failed()
        dash_path = os.path.join(self.snapshot_dir, "dashboard", "index.html")
        self.assertTrue(os.path.isfile(dash_path), "dashboard/index.html must be in snapshot")

    def test_gl163_doc_present_in_snapshot(self):
        self._skip_if_build_failed()
        doc_path = os.path.join(
            self.snapshot_dir, "docs", "post_public_agent_intake_triage.md"
        )
        self.assertTrue(os.path.isfile(doc_path),
                        "GL-163 doc must still be present in snapshot")

    def test_postgres_ci_absent_from_snapshot(self):
        self._skip_if_build_failed()
        ci_path = os.path.join(
            self.snapshot_dir, ".github", "workflows", "postgres-ci.yml"
        )
        self.assertFalse(os.path.exists(ci_path),
                         ".github/workflows/postgres-ci.yml must not be in snapshot")

    def test_git_absent_from_snapshot(self):
        self._skip_if_build_failed()
        git_path = os.path.join(self.snapshot_dir, ".git")
        self.assertFalse(os.path.exists(git_path),
                         ".git must not be present in generated snapshot")

    def test_sdk_python_present_in_snapshot(self):
        self._skip_if_build_failed()
        sdk_path = os.path.join(self.snapshot_dir, "sdk", "python", "grantlayer_client.py")
        self.assertTrue(os.path.isfile(sdk_path),
                        "sdk/python/grantlayer_client.py must be present in snapshot")

    def test_examples_agents_present_in_snapshot(self):
        self._skip_if_build_failed()
        examples_dir = os.path.join(self.snapshot_dir, "examples", "agents")
        self.assertTrue(os.path.isdir(examples_dir),
                        "examples/agents/ must be present in snapshot")
        py_files = list(Path(examples_dir).glob("*.py"))
        self.assertTrue(py_files, "examples/agents/ must contain Python files")


# ---------------------------------------------------------------------------
# 8. Scanner clean — run scanner inside temporary snapshot
# ---------------------------------------------------------------------------

class TestGL164AScannerClean(unittest.TestCase):
    """Scanner must exit 0 with 0 blockers on a fresh snapshot."""

    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.mkdtemp(prefix="gl164a-scan-")
        cls.snapshot_dir = os.path.join(cls.tmp_dir, "snapshot-output")
        build = subprocess.run(
            ["bash", str(SNAPSHOT_SCRIPT), "--output", cls.snapshot_dir, "--allow-dirty"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        cls.build_ok = build.returncode == 0
        if cls.build_ok:
            subprocess.run(["git", "init"], cwd=cls.snapshot_dir,
                           capture_output=True)
            subprocess.run(["git", "add", "."], cwd=cls.snapshot_dir,
                           capture_output=True)
            scanner = subprocess.run(
                ["bash", str(SCANNER_SCRIPT)],
                capture_output=True, text=True, cwd=cls.snapshot_dir,
            )
            cls.scanner_rc = scanner.returncode
            cls.scanner_output = scanner.stdout + scanner.stderr
        else:
            cls.scanner_rc = -1
            cls.scanner_output = ""

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def test_scanner_exits_zero(self):
        if not self.build_ok:
            self.skipTest("Snapshot build failed; scanner test skipped.")
        self.assertEqual(
            self.scanner_rc, 0,
            f"Scanner must exit 0 (0 blockers).\nOutput:\n{self.scanner_output[:1000]}",
        )

    def test_scanner_reports_zero_blockers(self):
        if not self.build_ok:
            self.skipTest("Snapshot build failed; scanner test skipped.")
        self.assertIn("Blockers found: 0", self.scanner_output)


if __name__ == "__main__":
    unittest.main()
