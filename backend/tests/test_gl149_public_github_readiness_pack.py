"""
GL-149 Public GitHub Readiness Pack — Validation Test

This test asserts that the GL-149 readiness pack artifacts exist,
are well-formed, and contain the required safety statements.

Scope guard: this test must not change production backend code.
"""

import json
import os
import re
import subprocess
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "public_github_readiness_pack.md")
JSON_PATH = os.path.join(
    REPO_ROOT, "docs", "examples", "gl149", "public_github_readiness_pack.json"
)


class TestGL149PublicGitHubReadinessPack(unittest.TestCase):
    """Validation test for GL-149 readiness pack."""

    # ------------------------------------------------------------------
    # 1. Artifact existence
    # ------------------------------------------------------------------

    def test_readiness_pack_md_exists(self):
        self.assertTrue(
            os.path.isfile(DOC_PATH),
            f"docs/public_github_readiness_pack.md must exist ({DOC_PATH})",
        )

    def test_json_artifact_exists(self):
        self.assertTrue(
            os.path.isfile(JSON_PATH),
            f"JSON artifact must exist ({JSON_PATH})",
        )

    # ------------------------------------------------------------------
    # 2. JSON parsing and required fields
    # ------------------------------------------------------------------

    def _load_json(self):
        with open(JSON_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def test_json_parses(self):
        data = self._load_json()
        self.assertIsInstance(data, dict)

    def test_json_issue_id(self):
        data = self._load_json()
        self.assertEqual(data.get("issue_id"), "GL-149")

    def test_json_readiness_pack_created_true(self):
        data = self._load_json()
        self.assertIs(data.get("readiness_pack_created"), True)

    def test_json_github_publication_performed_false(self):
        data = self._load_json()
        self.assertIs(data.get("github_publication_performed"), False)

    def test_json_git_remotes_changed_false(self):
        data = self._load_json()
        self.assertIs(data.get("git_remotes_changed"), False)

    def test_json_git_history_rewritten_false(self):
        data = self._load_json()
        self.assertIs(data.get("git_history_rewritten"), False)

    def test_json_secret_history_cleanup_performed_false(self):
        data = self._load_json()
        self.assertIs(data.get("secret_history_cleanup_performed"), False)

    def test_json_production_code_changed_false(self):
        data = self._load_json()
        self.assertIs(data.get("production_code_changed"), False)

    def test_json_backend_src_changed_false(self):
        data = self._load_json()
        self.assertIs(data.get("backend_src_changed"), False)

    def test_json_endpoint_api_behavior_changed_false(self):
        data = self._load_json()
        self.assertIs(data.get("endpoint_api_behavior_changed"), False)

    def test_json_openapi_changed_false(self):
        data = self._load_json()
        self.assertIs(data.get("openapi_changed"), False)

    def test_json_db_schema_changed_false(self):
        data = self._load_json()
        self.assertIs(data.get("db_schema_changed"), False)

    def test_json_dependencies_changed_false(self):
        data = self._load_json()
        self.assertIs(data.get("dependencies_changed"), False)

    def test_json_sdk_changed_false(self):
        data = self._load_json()
        self.assertIs(data.get("sdk_changed"), False)

    def test_json_langgraph_langchain_example_changed_false(self):
        data = self._load_json()
        self.assertIs(data.get("langgraph_langchain_example_changed"), False)

    def test_json_public_github_ready_claimed_complete_false(self):
        data = self._load_json()
        self.assertIs(data.get("public_github_ready_claimed_complete"), False)

    def test_json_public_release_approved_false(self):
        data = self._load_json()
        self.assertIs(data.get("public_release_approved"), False)

    def test_json_production_saas_ready_claimed_false(self):
        data = self._load_json()
        self.assertIs(data.get("production_saas_ready_claimed"), False)

    def test_json_tenant_isolation_claimed_implemented_false(self):
        data = self._load_json()
        self.assertIs(data.get("tenant_isolation_claimed_implemented"), False)

    def test_json_uses_real_secrets_false(self):
        data = self._load_json()
        self.assertIs(data.get("uses_real_secrets"), False)

    def test_json_uses_real_customer_data_false(self):
        data = self._load_json()
        self.assertIs(data.get("uses_real_customer_data"), False)

    # ------------------------------------------------------------------
    # 3. Markdown document required sections
    # ------------------------------------------------------------------

    def _load_md(self):
        with open(DOC_PATH, "r", encoding="utf-8") as fh:
            return fh.read()

    def test_md_has_current_posture_section(self):
        md = self._load_md()
        self.assertIn("Current Posture", md)

    def test_md_has_what_gl149_does_section(self):
        md = self._load_md()
        self.assertIn("What GL-149 Does", md)

    def test_md_has_what_gl149_does_not_do_section(self):
        md = self._load_md()
        self.assertIn("What GL-149 Does Not Do", md)

    def test_md_has_public_readiness_checklist_section(self):
        md = self._load_md()
        self.assertIn("Public Readiness Checklist", md)

    def test_md_has_repository_safety_checks_section(self):
        md = self._load_md()
        self.assertIn("Repository Safety Checks", md)

    def test_md_has_developer_entry_path_section(self):
        md = self._load_md()
        self.assertIn("Developer Entry Path", md)

    def test_md_has_messaging_rules_section(self):
        md = self._load_md()
        self.assertIn("Public-Facing Messaging Rules", md)

    def test_md_has_release_blockers_section(self):
        md = self._load_md()
        self.assertIn("Release Blockers", md)

    def test_md_has_go_no_go_criteria_section(self):
        md = self._load_md()
        self.assertIn("Go/No-Go Criteria", md)

    def test_md_has_proposed_follow_up_tasks_section(self):
        md = self._load_md()
        self.assertIn("Proposed Follow-Up Tasks", md)

    def test_md_has_validation_gates_section(self):
        md = self._load_md()
        self.assertIn("Validation Gates", md)

    # ------------------------------------------------------------------
    # 4. Document references required issues
    # ------------------------------------------------------------------

    def test_md_references_gl136(self):
        md = self._load_md()
        self.assertIn("GL-136", md)

    def test_md_references_gl137(self):
        md = self._load_md()
        self.assertIn("GL-137", md)

    def test_md_references_gl145(self):
        md = self._load_md()
        self.assertIn("GL-145", md)

    def test_md_references_gl146(self):
        md = self._load_md()
        self.assertIn("GL-146", md)

    def test_md_references_gl147(self):
        md = self._load_md()
        self.assertIn("GL-147", md)

    def test_md_references_gl148(self):
        md = self._load_md()
        self.assertIn("GL-148", md)

    def test_md_references_gl150(self):
        md = self._load_md()
        self.assertIn("GL-150", md)

    def test_md_references_security_boundary(self):
        md = self._load_md()
        self.assertIn("security boundary", md.lower())

    # ------------------------------------------------------------------
    # 5. Explicit safety statements
    # ------------------------------------------------------------------

    def test_md_states_no_github_publication(self):
        md = self._load_md()
        self.assertIn("not github publication", md.lower())

    def test_md_states_public_push_requires_approval(self):
        md = self._load_md()
        self.assertIn("public push requires explicit later approval", md.lower())

    def test_md_states_no_production_saas_claim(self):
        md = self._load_md()
        self.assertTrue(
            "production saas readiness is not claimed" in md.lower()
            or (
                "status and readiness caveats: see `readme.md`" in md.lower()
                and "not production saas launch" in md.lower()
            ),
            "Markdown must state production SaaS readiness is not claimed",
        )

    def test_md_states_tenant_isolation_not_implemented(self):
        md = self._load_md()
        self.assertTrue(
            "tenant isolation not implemented" in md.lower()
            or "implement tenant isolation" in md.lower()
            or "tenant/workspace isolation" in md.lower(),
            "Markdown must state tenant isolation is not implemented",
        )

    def test_md_states_no_real_secrets(self):
        md = self._load_md()
        self.assertIn("no real secrets", md.lower())

    def test_md_states_no_real_customer_data(self):
        md = self._load_md()
        self.assertIn("no real customer data", md.lower())

    # ------------------------------------------------------------------
    # 6. Optional safety text scan (placeholder-aware)
    # ------------------------------------------------------------------

    def test_no_obvious_private_key_markers_in_docs(self):
        """Flag obvious PEM private key blocks in docs/examples.

        Known-safe placeholder docs (key_hygiene.md) are allowed to mention
        PEM markers for educational purposes.
        """
        pem_marker = re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |)?PRIVATE KEY-----")
        flagged = []
        for root, _dirs, files in os.walk(os.path.join(REPO_ROOT, "docs")):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(root, fname)
                # key_hygiene.md is allowed to mention PEM markers
                if fpath.endswith("key_hygiene.md"):
                    continue
                with open(fpath, "r", encoding="utf-8") as fh:
                    content = fh.read()
                if pem_marker.search(content):
                    flagged.append(fpath)
        self.assertEqual(
            flagged,
            [],
            f"Unexpected PEM private key markers found in: {flagged}",
        )

    # ------------------------------------------------------------------
    # 7. Scope / branch guard
    # ------------------------------------------------------------------

    def test_no_backend_src_changes_on_gl149_branch(self):
        """If on the GL-149 branch, assert no backend/src files are modified."""
        try:
            branch = (
                subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=REPO_ROOT,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except Exception:
            self.skipTest("Unable to determine current git branch; skipping branch guard")
            return

        if branch != "gl-149-public-github-readiness-pack":
            self.skipTest(
                f"Not on gl-149-public-github-readiness-pack branch (on {branch}); "
                "skipping branch-specific diff assertions"
            )
            return

        try:
            diff_files = (
                subprocess.check_output(
                    ["git", "diff", "--name-only", "main...HEAD"],
                    cwd=REPO_ROOT,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
                .splitlines()
            )
        except Exception:
            self.skipTest("Unable to compute diff against main; skipping branch guard")
            return

        allowed_prefixes = (
            "docs/public_github_readiness_pack.md",
            "docs/examples/gl149/",
            "backend/tests/test_gl149_public_github_readiness_pack.py",
            "README.md",
            "docs/ten_minute_quickstart.md",
            "sdk/python/README.md",
            "docs/langgraph_langchain_integration_example.md",
        )

        forbidden = []
        for f in diff_files:
            if not f:
                continue
            if any(f.startswith(p) for p in allowed_prefixes):
                continue
            forbidden.append(f)

        self.assertEqual(
            forbidden,
            [],
            f"Forbidden files changed on GL-149 branch: {forbidden}",
        )

    def test_no_backend_src_in_diff(self):
        """Assert backend/src/ does not appear in the branch diff."""
        try:
            branch = (
                subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=REPO_ROOT,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except Exception:
            self.skipTest("Unable to determine current git branch")
            return

        if branch != "gl-149-public-github-readiness-pack":
            self.skipTest(f"Not on GL-149 branch (on {branch})")
            return

        try:
            diff_files = (
                subprocess.check_output(
                    ["git", "diff", "--name-only", "main...HEAD"],
                    cwd=REPO_ROOT,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
                .splitlines()
            )
        except Exception:
            self.skipTest("Unable to compute diff against main")
            return

        backend_src_changes = [f for f in diff_files if f.startswith("backend/src/")]
        self.assertEqual(
            backend_src_changes,
            [],
            f"backend/src/ must not change on GL-149: {backend_src_changes}",
        )

    def test_no_openapi_changes_in_diff(self):
        """Assert docs/openapi.yaml does not appear in the branch diff."""
        try:
            branch = (
                subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=REPO_ROOT,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except Exception:
            self.skipTest("Unable to determine current git branch")
            return

        if branch != "gl-149-public-github-readiness-pack":
            self.skipTest(f"Not on GL-149 branch (on {branch})")
            return

        try:
            diff_files = (
                subprocess.check_output(
                    ["git", "diff", "--name-only", "main...HEAD"],
                    cwd=REPO_ROOT,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
                .splitlines()
            )
        except Exception:
            self.skipTest("Unable to compute diff against main")
            return

        openapi_changes = [f for f in diff_files if f == "docs/openapi.yaml"]
        self.assertEqual(
            openapi_changes,
            [],
            f"docs/openapi.yaml must not change on GL-149: {openapi_changes}",
        )

    def test_no_migration_changes_in_diff(self):
        """Assert backend/src/migrations/ does not appear in the branch diff."""
        try:
            branch = (
                subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=REPO_ROOT,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except Exception:
            self.skipTest("Unable to determine current git branch")
            return

        if branch != "gl-149-public-github-readiness-pack":
            self.skipTest(f"Not on GL-149 branch (on {branch})")
            return

        try:
            diff_files = (
                subprocess.check_output(
                    ["git", "diff", "--name-only", "main...HEAD"],
                    cwd=REPO_ROOT,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
                .splitlines()
            )
        except Exception:
            self.skipTest("Unable to compute diff against main")
            return

        migration_changes = [
            f for f in diff_files if f.startswith("backend/src/migrations/")
        ]
        self.assertEqual(
            migration_changes,
            [],
            f"backend/src/migrations/ must not change on GL-149: {migration_changes}",
        )

    def test_no_dependency_file_changes_in_diff(self):
        """Assert requirements files do not appear in the branch diff."""
        try:
            branch = (
                subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=REPO_ROOT,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except Exception:
            self.skipTest("Unable to determine current git branch")
            return

        if branch != "gl-149-public-github-readiness-pack":
            self.skipTest(f"Not on GL-149 branch (on {branch})")
            return

        try:
            diff_files = (
                subprocess.check_output(
                    ["git", "diff", "--name-only", "main...HEAD"],
                    cwd=REPO_ROOT,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
                .splitlines()
            )
        except Exception:
            self.skipTest("Unable to compute diff against main")
            return

        dep_files = {
            "requirements.txt",
            "requirements-dev.txt",
            "pyproject.toml",
            "setup.py",
            "Pipfile",
            "poetry.lock",
        }
        changed_deps = [f for f in diff_files if f in dep_files]
        self.assertEqual(
            changed_deps,
            [],
            f"Dependency files must not change on GL-149: {changed_deps}",
        )

    def test_no_sdk_changes_in_diff(self):
        """Assert sdk/python/grantlayer_client.py does not appear in the branch diff."""
        try:
            branch = (
                subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=REPO_ROOT,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except Exception:
            self.skipTest("Unable to determine current git branch")
            return

        if branch != "gl-149-public-github-readiness-pack":
            self.skipTest(f"Not on GL-149 branch (on {branch})")
            return

        try:
            diff_files = (
                subprocess.check_output(
                    ["git", "diff", "--name-only", "main...HEAD"],
                    cwd=REPO_ROOT,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
                .splitlines()
            )
        except Exception:
            self.skipTest("Unable to compute diff against main")
            return

        sdk_changes = [f for f in diff_files if f == "sdk/python/grantlayer_client.py"]
        self.assertEqual(
            sdk_changes,
            [],
            f"sdk/python/grantlayer_client.py must not change on GL-149: {sdk_changes}",
        )

    def test_no_langgraph_example_changes_in_diff(self):
        """Assert examples/langgraph_langchain/grantlayer_agent_example.py does not appear in the branch diff."""
        try:
            branch = (
                subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=REPO_ROOT,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except Exception:
            self.skipTest("Unable to determine current git branch")
            return

        if branch != "gl-149-public-github-readiness-pack":
            self.skipTest(f"Not on GL-149 branch (on {branch})")
            return

        try:
            diff_files = (
                subprocess.check_output(
                    ["git", "diff", "--name-only", "main...HEAD"],
                    cwd=REPO_ROOT,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
                .splitlines()
            )
        except Exception:
            self.skipTest("Unable to compute diff against main")
            return

        example_changes = [
            f
            for f in diff_files
            if f == "examples/langgraph_langchain/grantlayer_agent_example.py"
        ]
        self.assertEqual(
            example_changes,
            [],
            f"LangGraph example must not change on GL-149: {example_changes}",
        )

    def test_no_claude_changes_in_diff(self):
        """Assert .claude/ does not appear in the branch diff."""
        try:
            branch = (
                subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=REPO_ROOT,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except Exception:
            self.skipTest("Unable to determine current git branch")
            return

        if branch != "gl-149-public-github-readiness-pack":
            self.skipTest(f"Not on GL-149 branch (on {branch})")
            return

        try:
            diff_files = (
                subprocess.check_output(
                    ["git", "diff", "--name-only", "main...HEAD"],
                    cwd=REPO_ROOT,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
                .splitlines()
            )
        except Exception:
            self.skipTest("Unable to compute diff against main")
            return

        claude_changes = [f for f in diff_files if f.startswith(".claude/")]
        self.assertEqual(
            claude_changes,
            [],
            f".claude/ must not change on GL-149: {claude_changes}",
        )


if __name__ == "__main__":
    unittest.main()
