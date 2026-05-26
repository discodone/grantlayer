"""Tests for GL-121: Full Backend Suite Timeout Wrapper.

Ensures:
- scripts/run-full-backend-suite.sh exists and is well-formed.
- Script uses safe bash settings and a timeout >= 900 seconds.
- Script preserves exit codes and does not hide failures.
- Script does not contain secrets or reference production hosts.
- docs/full_backend_suite_runner.md exists and documents the workflow.
- No forbidden files are changed.
"""

import os
import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestGl121ScriptContract(unittest.TestCase):
    """Verify the runner script meets its contract."""

    @classmethod
    def setUpClass(cls):
        cls.repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        cls.script_path = cls.repo_root / "scripts" / "run-full-backend-suite.sh"
        cls.docs_path = cls.repo_root / "docs" / "full_backend_suite_runner.md"
        cls.script_text = cls.script_path.read_text()

    def test_script_exists(self):
        self.assertTrue(self.script_path.exists(), "run-full-backend-suite.sh must exist")

    def test_script_has_shebang(self):
        lines = self.script_text.splitlines()
        self.assertTrue(lines, "Script must not be empty")
        self.assertTrue(
            lines[0].startswith("#!/usr/bin/env bash"),
            f"Expected bash shebang, got: {lines[0]}",
        )

    def test_script_uses_strict_mode(self):
        self.assertIn("set -euo pipefail", self.script_text)

    def test_script_references_unittest_discover(self):
        self.assertIn("python3 -m unittest discover backend.tests -v", self.script_text)

    def test_script_default_timeout_at_least_900(self):
        # The default is set via ${FULL_SUITE_TIMEOUT_SECONDS:-900}
        self.assertIn("${FULL_SUITE_TIMEOUT_SECONDS:-900}", self.script_text)

    def test_script_rejects_short_timeout(self):
        self.assertIn("-lt 900", self.script_text)
        self.assertIn("ERROR", self.script_text)

    def test_script_preserves_exit_code(self):
        # Should capture exit code and exit with it
        self.assertIn("EXIT_CODE=", self.script_text)
        self.assertIn("exit \"${EXIT_CODE}\"", self.script_text)

    def test_script_does_not_use_tail_grep_head_as_only_validation(self):
        # The script must not pipe unittest output through tail/grep/head
        # as the *only* validation mechanism.
        for bad in ["| tail", "| grep", "| head"]:
            self.assertNotIn(
                bad,
                self.script_text,
                f"Script must not pipe unittest output through {bad} as sole validation",
            )

    def test_script_no_secrets(self):
        forbidden = ["password", "secret", "api_key", "token"]
        lower = self.script_text.lower()
        for word in forbidden:
            # Allow "timeout" and "unittest" which contain "token" substrings
            if word == "token":
                # Check for actual secret-looking token usage, not just the word token
                lines = self.script_text.splitlines()
                for line in lines:
                    if "token" in line.lower() and any(
                        x in line.lower() for x in ["bearer", "secret", "api_key", "password"]
                    ):
                        self.fail(f"Possible secret in script line: {line}")
                continue
            self.assertNotIn(word, lower, f"Script must not contain secret keyword: {word}")

    def test_script_no_production_hosts(self):
        forbidden_hosts = ["prod.", "production", "grantlayer.io", "api.grantlayer"]
        lower = self.script_text.lower()
        for host in forbidden_hosts:
            self.assertNotIn(host, lower, f"Script must not reference production host: {host}")

    def test_script_is_executable(self):
        self.assertTrue(
            os.access(self.script_path, os.X_OK),
            "run-full-backend-suite.sh must be executable",
        )

    def test_script_uses_timeout_command(self):
        self.assertIn("timeout", self.script_text.lower())

    def test_script_resolves_repo_root(self):
        self.assertIn("REPO_ROOT", self.script_text)


class TestGl121DocumentationContract(unittest.TestCase):
    """Verify the documentation exists and covers required topics."""

    @classmethod
    def setUpClass(cls):
        cls.repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        cls.docs_path = cls.repo_root / "docs" / "full_backend_suite_runner.md"
        cls.docs_text = cls.docs_path.read_text() if cls.docs_path.exists() else ""

    def test_docs_exist(self):
        self.assertTrue(self.docs_path.exists(), "docs/full_backend_suite_runner.md must exist")

    def test_docs_mention_120s_timeout_problem(self):
        lower = self.docs_text.lower()
        self.assertTrue(
            "120000" in lower or "120 s" in lower or "120-second" in lower or "120 seconds" in lower,
            "Docs must mention the 120000ms / 120s agent timeout problem",
        )

    def test_docs_mention_not_run_due_tool_timeout_limit(self):
        self.assertIn(
            "not_run_due_tool_timeout_limit",
            self.docs_text,
            "Docs must mention not_run_due_tool_timeout_limit",
        )

    def test_docs_mention_coding_agent_targeted_rule(self):
        lower = self.docs_text.lower()
        self.assertIn("targeted tests", lower)
        self.assertIn("relevant regressions", lower)

    def test_docs_mention_fast_merge_post_merge_rule(self):
        lower = self.docs_text.lower()
        self.assertIn("fast-merge", lower)
        self.assertIn("post-merge", lower)

    def test_docs_mention_main_zero_failures(self):
        lower = self.docs_text.lower()
        self.assertTrue(
            "0 failures" in lower and "0 errors" in lower,
            "Docs must state main must have 0 failures / 0 errors before push",
        )


class TestGl121NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-121 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-121-full-suite-timeout-wrapper":
            self.skipTest("Branch-wide diff check only valid on GL-121 feature branch")
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "scripts/run-full-backend-suite.sh",
            "backend/tests/test_gl121_full_suite_runner.py",
            "docs/full_backend_suite_runner.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-121 changed a forbidden file: {path}",
            )

    def test_no_production_code_changed(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        for path in changed:
            if path.startswith("backend/src/"):
                self.fail(f"GL-121 must not change production code: {path}")

    def test_no_openapi_changed(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        for path in changed:
            if path == "docs/openapi.yaml":
                self.fail("GL-121 must not change OpenAPI spec")

    def test_no_migration_changed(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        for path in changed:
            if "migration" in path.lower():
                self.fail(f"GL-121 must not change migrations: {path}")

    def test_no_frontend_or_website_changed(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        for path in changed:
            if path.startswith("frontend/") or path.startswith("website/"):
                self.fail(f"GL-121 must not change frontend/website: {path}")

    def test_no_db_schema_changed(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        for path in changed:
            if "schema" in path.lower() and path.endswith(".sql"):
                self.fail(f"GL-121 must not change DB schema: {path}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
