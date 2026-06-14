"""
GL-176: Public GitHub Visibility Change Report — validation tests.
"""
import json
import os
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GL176_BRANCH = "gl-176-public-github-visibility-change-report"
MARKDOWN_PATH = os.path.join(REPO_ROOT, "docs", "public_github_visibility_change_report.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl176",
    "public_github_visibility_change_report.json",
)


class TestGL176ArtifactFilesExist(unittest.TestCase):
    def test_markdown_exists(self):
        self.assertTrue(
            os.path.isfile(MARKDOWN_PATH),
            f"GL-176 report markdown not found: {MARKDOWN_PATH}",
        )

    def test_json_exists(self):
        self.assertTrue(
            os.path.isfile(JSON_PATH),
            f"GL-176 report JSON not found: {JSON_PATH}",
        )


class TestGL176ArtifactJSON(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(JSON_PATH, encoding="utf-8") as f:
            cls.data = json.load(f)

    def test_valid_json(self):
        self.assertIsInstance(self.data, dict)

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-176")

    def test_public_publish_worktree(self):
        self.assertEqual(
            self.data.get("public_publish_worktree"),
            "/tmp/grantlayer-public-publish",
            "report must record public publish worktree as /tmp/grantlayer-public-publish",
        )

    def test_github_remote(self):
        self.assertEqual(
            self.data.get("github_remote"),
            "https://github.com/discodone/grantlayer.git",
            "report must record GitHub remote as https://github.com/discodone/grantlayer.git",
        )

    def test_no_force_push(self):
        actions = self.data.get("publication_actions", {})
        self.assertFalse(
            actions.get("force_push", True),
            "report must confirm no force push was performed",
        )

    def test_internal_repo_not_pushed_directly_to_github(self):
        actions = self.data.get("publication_actions", {})
        self.assertFalse(
            actions.get("internal_repo_pushed_directly_to_github", True),
            "report must confirm internal repo was not pushed directly to GitHub",
        )

    def test_private_data_secret_safety_result(self):
        safety = self.data.get("private_data_public_snapshot_safety", {})
        self.assertIn(
            "result", safety,
            "private_data_public_snapshot_safety must include result field",
        )
        self.assertIn(
            "blockers_found", safety,
            "private_data_public_snapshot_safety must include blockers_found field",
        )

    def test_if_blocked_then_snapshot_not_pushed_and_visibility_not_changed(self):
        safety = self.data.get("private_data_public_snapshot_safety", {})
        result = safety.get("result", "")
        actions = self.data.get("publication_actions", {})
        visibility = self.data.get("visibility_change", {})
        if result in ("blocked", "blocked_private_data_or_secret_safety"):
            self.assertFalse(
                actions.get("public_snapshot_pushed", True),
                "if private data blocked, public_snapshot_pushed must be false",
            )
            self.assertFalse(
                visibility.get("changed", True),
                "if private data blocked, visibility_change.changed must be false",
            )

    def test_source_internal_main_commit_present(self):
        self.assertIn("source_internal_main_commit", self.data)
        commit = self.data["source_internal_main_commit"]
        self.assertIsInstance(commit, str)
        self.assertGreater(len(commit), 0)

    def test_preflight_checks_present(self):
        self.assertIn("preflight_checks", self.data)
        preflight = self.data["preflight_checks"]
        self.assertIsInstance(preflight, dict)
        self.assertGreater(len(preflight), 0)

    def test_github_remote_verified_field(self):
        preflight = self.data.get("preflight_checks", {})
        self.assertIn(
            "github_remote_verified",
            preflight,
            "preflight_checks must include github_remote_verified",
        )

    def test_no_internal_forgejo_as_github_target(self):
        preflight = self.data.get("preflight_checks", {})
        self.assertFalse(
            preflight.get("no_internal_forgejo_remote_as_github_push_target") is False,
        )

    def test_publication_actions_present(self):
        self.assertIn("publication_actions", self.data)

    def test_visibility_change_present(self):
        self.assertIn("visibility_change", self.data)

    def test_post_publication_checks_present(self):
        self.assertIn("post_publication_checks", self.data)

    def test_remaining_cautions_present(self):
        self.assertIn("remaining_cautions", self.data)
        self.assertIsInstance(self.data["remaining_cautions"], list)

    def test_next_recommended_step_present(self):
        self.assertIn("next_recommended_step", self.data)

    def test_final_disposition_valid(self):
        valid = {
            "published_and_public",
            "published_but_visibility_not_changed",
            "blocked_before_gl176",
            "blocked_private_data_or_secret_safety",
            "blocked_github_auth",
            "blocked_missing_publish_workflow",
            "blocked_other_with_reason",
        }
        self.assertIn(self.data.get("final_disposition"), valid)

    def test_no_backend_src_or_api_changes(self):
        internal_files = self.data.get("internal_report_files", [])
        for f in internal_files:
            self.assertFalse(
                f.startswith("backend/src/"),
                f"internal report must not include backend/src changes: {f}",
            )
            self.assertFalse(
                "openapi" in f.lower(),
                f"internal report must not include OpenAPI changes: {f}",
            )

    def test_no_forbidden_patterns_in_artifact(self):
        text = json.dumps(self.data)
        forbidden = [
            "forge.hofercloud.eu",
            "terminal.hofercloud.eu",
            "192.168.2.",
            "100.109.111.",
            "tapWjoj8",
        ]
        for pattern in forbidden:
            self.assertNotIn(
                pattern, text,
                f"forbidden pattern '{pattern}' found in GL-176 JSON artifact",
            )


class TestGL176MarkdownContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(MARKDOWN_PATH, encoding="utf-8") as f:
            cls.content = f.read()

    def test_must_reference_issue_id(self):
        self.assertIn("GL-176", self.content)

    def test_must_include_public_publish_worktree(self):
        self.assertIn("/tmp/grantlayer-public-publish", self.content)

    def test_must_include_github_remote(self):
        self.assertIn("https://github.com/discodone/grantlayer.git", self.content)

    def test_must_state_no_force_push(self):
        self.assertIn("force", self.content.lower())

    def test_must_state_internal_repo_not_pushed_directly(self):
        self.assertIn("NOT pushed directly to GitHub", self.content)

    def test_must_include_private_data_safety_result(self):
        self.assertIn("scanner", self.content.lower())
        self.assertIn("blockers", self.content.lower())

    def test_must_include_final_disposition(self):
        valid_dispositions = [
            "published_and_public",
            "published_but_visibility_not_changed",
            "blocked_before_gl176",
            "blocked_private_data_or_secret_safety",
            "blocked_github_auth",
            "blocked_missing_publish_workflow",
        ]
        self.assertTrue(
            any(d in self.content for d in valid_dispositions),
            "markdown must reference a valid final_disposition",
        )

    def test_must_state_no_backend_src_changes(self):
        self.assertIn("backend/src", self.content)

    def test_must_include_post_publication_checks(self):
        self.assertIn("smoke", self.content.lower())

    def test_must_reference_f003(self):
        self.assertIn("F-003", self.content)

    def test_must_not_claim_tenant_isolation_implemented(self):
        self.assertNotIn("tenant isolation implemented", self.content.lower())
        self.assertNotIn("tenant isolation is implemented", self.content.lower())

    def test_must_not_claim_production_saas(self):
        self.assertNotIn("production saas ready", self.content.lower())
        self.assertNotIn("production-ready saas", self.content.lower())

    def test_no_forbidden_patterns_in_markdown(self):
        forbidden = [
            "forge.hofercloud.eu",
            "terminal.hofercloud.eu",
            "192.168.2.",
            "100.109.111.",
            "tapWjoj8",
        ]
        for pattern in forbidden:
            self.assertNotIn(
                pattern, self.content,
                f"forbidden pattern '{pattern}' found in GL-176 markdown",
            )

    def test_must_confirm_no_history_rewrite(self):
        self.assertIn("history rewrite", self.content.lower())

    def test_must_include_remaining_cautions(self):
        self.assertIn("caution", self.content.lower())


class TestGL176ChangedFilesScope(unittest.TestCase):
    ALLOWED_FILES = {
        "docs/public_github_visibility_change_report.md",
        "docs/examples/gl176/public_github_visibility_change_report.json",
        "backend/tests/test_gl176_public_github_visibility_change_report.py",
    }

    FORBIDDEN_PREFIXES = [
        "backend/src/",
        "openapi",
        "migrations/",
        "requirements",
        "package.json",
        "package-lock.json",
        "frontend/",
        "website/",
        ".github/workflows/",
    ]

    def _get_changed_files(self):
        import subprocess
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        if branch.returncode == 0 and branch.stdout.strip() != GL176_BRANCH:
            return []
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        if result.returncode != 0:
            return []
        return [f.strip() for f in result.stdout.splitlines() if f.strip()]

    def test_changed_files_within_allowed_scope(self):
        changed = self._get_changed_files()
        if not changed:
            self.skipTest("No branch diff (likely on main or single-commit branch)")
        for path in changed:
            for prefix in self.FORBIDDEN_PREFIXES:
                self.assertFalse(
                    path.lower().startswith(prefix),
                    f"Changed file '{path}' starts with forbidden prefix '{prefix}' for GL-176",
                )


if __name__ == "__main__":
    unittest.main()
