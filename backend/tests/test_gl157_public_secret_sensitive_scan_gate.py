"""
GL-157 Validation: Public Secret / Sensitive Data Scan Gate.

Covers:
- File existence checks
- Script content and executable checks
- JSON artifact boolean validation
- Docs content and caveat checks
- Synthetic temp-repo scan tests (no real secrets used)
- Branch scope guard
"""
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

SCAN_SCRIPT = os.path.join(REPO_ROOT, "scripts", "public-secret-sensitive-scan.sh")
SCAN_DOCS = os.path.join(REPO_ROOT, "docs", "public_secret_sensitive_scan_gate.md")
SCAN_JSON = os.path.join(REPO_ROOT, "docs", "examples", "gl157", "public_secret_sensitive_scan_gate.json")
THIS_TEST = os.path.join(REPO_ROOT, "backend", "tests", "test_gl157_public_secret_sensitive_scan_gate.py")


class TestGL157FilesExist(unittest.TestCase):
    def test_scan_script_exists(self):
        self.assertTrue(os.path.isfile(SCAN_SCRIPT), f"Missing: {SCAN_SCRIPT}")

    def test_scan_docs_exist(self):
        self.assertTrue(os.path.isfile(SCAN_DOCS), f"Missing: {SCAN_DOCS}")

    def test_json_artifact_exists(self):
        self.assertTrue(os.path.isfile(SCAN_JSON), f"Missing: {SCAN_JSON}")

    def test_test_file_exists(self):
        self.assertTrue(os.path.isfile(THIS_TEST), f"Missing: {THIS_TEST}")


class TestGL157ScriptContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SCAN_SCRIPT, "r", encoding="utf-8") as f:
            cls.script_text = f.read()

    def test_script_executable(self):
        mode = os.stat(SCAN_SCRIPT).st_mode
        self.assertTrue(mode & stat.S_IXUSR, "Script must be user-executable")

    def test_set_euo_pipefail(self):
        self.assertIn("set -euo pipefail", self.script_text)

    def test_git_ls_files(self):
        self.assertIn("git ls-files", self.script_text)

    def test_excludes_claude_dir(self):
        self.assertIn(".claude", self.script_text)

    def test_has_help_flag(self):
        self.assertIn("--help", self.script_text)

    def test_has_strict_flag(self):
        self.assertIn("--strict", self.script_text)

    def test_checks_private_key(self):
        self.assertIn("private key", self.script_text.lower())

    def test_checks_internal_hostname_forge(self):
        self.assertIn("forge.internal.invalid", self.script_text)

    def test_checks_internal_path_adminuser(self):
        self.assertIn("/home/adminuser", self.script_text)

    def test_checks_production_saas_ready(self):
        self.assertIn("production SaaS ready", self.script_text)

    def test_checks_tenant_isolation_implemented(self):
        self.assertIn("tenant isolation implemented", self.script_text)

    def test_uses_git_rev_parse_toplevel(self):
        self.assertIn("git rev-parse --show-toplevel", self.script_text)

    def test_exits_nonzero_on_blockers(self):
        self.assertIn("exit 1", self.script_text)

    def test_exits_zero_on_clean(self):
        self.assertIn("exit 0", self.script_text)


class TestGL157JsonArtifact(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SCAN_JSON, "r", encoding="utf-8") as f:
            cls.data = json.load(f)

    def test_issue_id(self):
        self.assertEqual(self.data["issue_id"], "GL-157")

    def test_artifact_type(self):
        self.assertEqual(self.data["artifact_type"], "public_secret_sensitive_scan_gate")

    def _assert_true(self, key):
        self.assertIn(key, self.data, f"Missing key: {key}")
        self.assertIs(self.data[key], True, f"Expected True for: {key}")

    def _assert_false(self, key):
        self.assertIn(key, self.data, f"Missing key: {key}")
        self.assertIs(self.data[key], False, f"Expected False for: {key}")

    def test_scan_gate_script_added(self):
        self._assert_true("scan_gate_script_added")

    def test_scan_gate_docs_added(self):
        self._assert_true("scan_gate_docs_added")

    def test_validation_test_added(self):
        self._assert_true("validation_test_added")

    def test_scans_tracked_files_by_default(self):
        self._assert_true("scans_tracked_files_by_default")

    def test_avoids_git_directory(self):
        self._assert_true("avoids_git_directory")

    def test_avoids_claude_directory(self):
        self._assert_true("avoids_claude_directory")

    def test_secret_like_patterns_checked(self):
        self._assert_true("secret_like_patterns_checked")

    def test_internal_hostname_patterns_checked(self):
        self._assert_true("internal_hostname_patterns_checked")

    def test_internal_path_patterns_checked(self):
        self._assert_true("internal_path_patterns_checked")

    def test_customer_data_patterns_checked(self):
        self._assert_true("customer_data_patterns_checked")

    def test_private_personal_data_patterns_checked(self):
        self._assert_true("private_personal_data_patterns_checked")

    def test_public_readiness_overclaim_patterns_checked(self):
        self._assert_true("public_readiness_overclaim_patterns_checked")

    def test_safe_placeholder_allowlist_documented(self):
        self._assert_true("safe_placeholder_allowlist_documented")

    def test_redaction_guidance_included(self):
        self._assert_true("redaction_guidance_included")

    def test_non_zero_on_blockers(self):
        self._assert_true("non_zero_on_blockers")

    def test_github_publication_performed_false(self):
        self._assert_false("github_publication_performed")

    def test_live_github_issues_created_false(self):
        self._assert_false("live_github_issues_created")

    def test_github_api_called_false(self):
        self._assert_false("github_api_called")

    def test_git_remotes_changed_false(self):
        self._assert_false("git_remotes_changed")

    def test_git_history_rewritten_false(self):
        self._assert_false("git_history_rewritten")

    def test_secret_history_cleanup_performed_false(self):
        self._assert_false("secret_history_cleanup_performed")

    def test_secrets_rotated_false(self):
        self._assert_false("secrets_rotated")

    def test_external_secret_scanner_added_false(self):
        self._assert_false("external_secret_scanner_added")

    def test_dependencies_changed_false(self):
        self._assert_false("dependencies_changed")

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

    def test_sdk_changed_false(self):
        self._assert_false("sdk_changed")

    def test_langgraph_langchain_code_changed_false(self):
        self._assert_false("langgraph_langchain_code_changed")

    def test_runtime_agent_examples_changed_false(self):
        self._assert_false("runtime_agent_examples_changed")

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

    def test_scan_categories_present(self):
        cats = self.data.get("scan_categories", [])
        self.assertIsInstance(cats, list)
        for expected in ["private_key", "aws_access_key", "github_token", "internal_hostname",
                         "internal_path", "customer_data", "private_personal_data", "overclaim"]:
            self.assertIn(expected, cats, f"Missing scan category: {expected}")

    def test_allowed_placeholders_present(self):
        placeholders = self.data.get("allowed_placeholders", [])
        self.assertIsInstance(placeholders, list)
        self.assertGreater(len(placeholders), 5)

    def test_validation_gates_present(self):
        gates = self.data.get("validation_gates", {})
        self.assertIsInstance(gates, dict)
        self.assertGreater(len(gates), 5)

    def test_next_issue(self):
        self.assertIn("GL-158", self.data.get("next_issue", ""))


class TestGL157DocContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SCAN_DOCS, "r", encoding="utf-8") as f:
            cls.doc_text = f.read()

    def test_developer_preview_caveat(self):
        self.assertIn("Developer Preview", self.doc_text)

    def test_not_production_saas_caveat(self):
        self.assertIn("not production SaaS", self.doc_text.lower().replace("not production saas", "not production SaaS"))
        # case-insensitive check
        self.assertIn("not production saas", self.doc_text.lower())

    def test_tenant_isolation_not_implemented_caveat(self):
        self.assertIn("tenant isolation is not implemented", self.doc_text.lower())

    def test_no_real_secrets_caveat(self):
        self.assertIn("no real secrets", self.doc_text.lower())

    def test_no_real_customer_data_caveat(self):
        self.assertIn("no real customer data", self.doc_text.lower())

    def test_heuristic_scan_only_limitation(self):
        self.assertIn("heuristic scan only", self.doc_text.lower())

    def test_does_not_rewrite_history_limitation(self):
        self.assertIn("does not rewrite history", self.doc_text.lower())

    def test_does_not_publish_to_github_limitation(self):
        self.assertIn("does not publish to github", self.doc_text.lower())

    def test_gl158_reference(self):
        self.assertIn("GL-158", self.doc_text)

    def test_redaction_guidance(self):
        self.assertIn("placeholder", self.doc_text.lower())
        self.assertIn("rotate", self.doc_text.lower())


class TestGL157SyntheticScan(unittest.TestCase):
    """
    Synthetic temp-repo tests. Creates isolated git repos so the scan
    exercises the script logic without touching the real GrantLayer repo.
    Each test gets its own fresh temp repo to prevent blocker accumulation.
    No real secrets are used in any fixture content.
    """

    def _make_repo(self):
        tmp = tempfile.mkdtemp(prefix="gl157_test_")
        subprocess.run(["git", "init", tmp], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.email", "test@example.com"],
                       cwd=tmp, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"],
                       cwd=tmp, check=True, capture_output=True)
        scripts_dir = os.path.join(tmp, "scripts")
        os.makedirs(scripts_dir, exist_ok=True)
        dest = os.path.join(scripts_dir, "public-secret-sensitive-scan.sh")
        shutil.copy2(SCAN_SCRIPT, dest)
        os.chmod(dest, os.stat(dest).st_mode | stat.S_IXUSR | stat.S_IXGRP)
        return tmp

    def setUp(self):
        self.tmp = self._make_repo()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_and_track(self, filename, content):
        filepath = os.path.join(self.tmp, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        subprocess.run(["git", "add", filename], cwd=self.tmp, check=True, capture_output=True)
        return filepath

    def _write_untracked(self, filename, content):
        filepath = os.path.join(self.tmp, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def _run_scan(self):
        result = subprocess.run(
            ["bash", os.path.join(self.tmp, "scripts", "public-secret-sensitive-scan.sh")],
            cwd=self.tmp,
            capture_output=True,
            text=True,
        )
        return result

    def test_safe_placeholder_exits_0(self):
        self._write_and_track("safe_config.txt",
            "api_key = placeholder\n"
            "token = test-token\n"
            "password = example\n"
            "apiKey: <api-key>\n"
        )
        result = self._run_scan()
        self.assertEqual(result.returncode, 0,
                         f"Expected exit 0 for safe placeholders.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

    def test_private_key_marker_exits_nonzero(self):
        # Construct the PEM header by concatenation so this source file does not
        # contain the literal contiguous marker (which GL-136/GL-149 guards forbid).
        pem_header = "-----BEGIN " + "RSA PRIVATE KEY-----"
        pem_footer = "-----END " + "RSA PRIVATE KEY-----"
        self._write_and_track("bad_key.txt",
            pem_header + "\n"
            "SYNTHETICFAKECONTENTNOTAREALKEY\n"
            + pem_footer + "\n"
        )
        result = self._run_scan()
        self.assertNotEqual(result.returncode, 0,
                            f"Expected non-zero for private key marker.\nSTDOUT:\n{result.stdout}")

    def test_internal_hostname_exits_nonzero(self):
        self._write_and_track("hostname_ref.txt",
            "Remote: forge.internal.invalid/toni/repo.git\n"
        )
        result = self._run_scan()
        self.assertNotEqual(result.returncode, 0,
                            f"Expected non-zero for internal hostname.\nSTDOUT:\n{result.stdout}")

    def test_internal_path_exits_nonzero(self):
        self._write_and_track("path_ref.txt",
            "config_dir: /home/adminuser/projects/config\n"
        )
        result = self._run_scan()
        self.assertNotEqual(result.returncode, 0,
                            f"Expected non-zero for internal path.\nSTDOUT:\n{result.stdout}")

    def test_public_overclaim_exits_nonzero(self):
        self._write_and_track("overclaim.txt",
            "GrantLayer is production SaaS ready for enterprise customers.\n"
        )
        result = self._run_scan()
        self.assertNotEqual(result.returncode, 0,
                            f"Expected non-zero for overclaim phrase.\nSTDOUT:\n{result.stdout}")

    def test_untracked_blocker_file_ignored(self):
        # Write a file with a blocker but do NOT git add it
        self._write_untracked("untracked_blocker.txt",
            "forge.internal.invalid\n"
        )
        result = self._run_scan()
        # The scan only checks tracked files; untracked file must not appear in output
        self.assertNotIn("untracked_blocker.txt", result.stdout,
                         "Untracked file must not appear in scan output")

    def test_claude_dir_blocker_excluded(self):
        # Track a file inside .claude/ that contains a blocker pattern
        self._write_and_track(".claude/settings.txt",
            "forge.internal.invalid\n"
            "token = real-secret-value-here\n"
        )
        result = self._run_scan()
        # .claude/ exclusion means .claude/settings.txt must not appear in BLOCKER lines.
        # The banner says "excluding .git/ .claude/" so we check for the specific file path.
        blocker_lines = [ln for ln in result.stdout.splitlines() if "BLOCKER" in ln]
        for line in blocker_lines:
            self.assertNotIn(".claude/settings.txt", line,
                             f".claude/ file must not appear in BLOCKER output; got: {line}")


class TestGL157BranchScopeGuard(unittest.TestCase):
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
        if branch != "gl-157-public-secret-sensitive-scan-gate":
            self.skipTest(f"Not on GL-157 branch (current: {branch}); skipping diff assertions")

        changed = self._get_changed_files()

        allowed = {
            "scripts/public-secret-sensitive-scan.sh",
            "docs/public_secret_sensitive_scan_gate.md",
            "docs/examples/gl157/public_secret_sensitive_scan_gate.json",
            "backend/tests/test_gl157_public_secret_sensitive_scan_gate.py",
            "README.md",
            "SECURITY.md",
            "CONTRIBUTING.md",
            "AGENTS.md",
            ".github/pull_request_template.md",
            ".github/ISSUE_TEMPLATE/security_report.md",
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
            "examples/agents/evidence_review_agent.py",
            "examples/agents/approval_guardrail_agent.py",
            "examples/agents/audit_export_agent.py",
            "examples/agents/policy_check_agent.py",
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
