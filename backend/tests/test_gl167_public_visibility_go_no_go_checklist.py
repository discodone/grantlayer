"""GL-167 public visibility go/no-go checklist validation tests."""

import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "docs" / "public_visibility_go_no_go_checklist.md"
JSON_PATH = (
    REPO_ROOT
    / "docs"
    / "examples"
    / "gl167"
    / "public_visibility_go_no_go_checklist.json"
)

BASELINE_INTERNAL_MAIN = "08460fddeb9f841776b13f973bac6d5acdaf1584"
DEFERRED_PUBLISH_COMMIT = "4e4d7fc1733323148cfeb0306deb455aa1ebd63b"
GL167_BRANCH = "gl-167-public-visibility-go-no-go-checklist"


def _read(path):
    return path.read_text(encoding="utf-8")


def _load_json():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestGL167FilesExist(unittest.TestCase):
    def test_markdown_exists(self):
        self.assertTrue(DOC_PATH.is_file(), f"Missing: {DOC_PATH}")

    def test_json_exists(self):
        self.assertTrue(JSON_PATH.is_file(), f"Missing: {JSON_PATH}")


class TestGL167MarkdownContent(unittest.TestCase):
    def setUp(self):
        self.content = _read(DOC_PATH)
        self.lower = self.content.lower()

    def test_required_sections_present(self):
        sections = [
            "## Purpose",
            "## Decision States",
            "## Current Recommendation",
            "## Snapshot Scanner Status",
            "## Absence Checks",
            "## Deferred GitHub Push Status",
            "## Repository Visibility",
            "## Publication Boundaries",
            "## Branch And History Safety",
            "## Secrets, Keys, And Token Checks",
            "## Internal Hostname And Path Checks",
            "## Backend/Internal Fixture Absence",
            "## Production Readiness Claim Checks",
            "## License, README, CHANGELOG, And Version Anchor Checks",
            "## Open Blockers Before Public Visibility",
            "## Required Final Verification Before Visibility Change",
            "## Explicit Non-Goals",
        ]
        for section in sections:
            self.assertIn(section, self.content)

    def test_public_visibility_not_public_launch(self):
        self.assertIn("public visibility readiness checklist", self.lower)
        self.assertIn("not a public launch", self.lower)

    def test_current_recommendation_no_go(self):
        self.assertIn("**current recommendation**: `no_go`", self.lower)
        self.assertIn("**recommendation**: `no_go`", self.lower)
        self.assertIn("github push is deferred", self.lower)
        self.assertIn("final remote verification has not occurred", self.lower)

    def test_decision_states(self):
        for state in ["`no_go`", "`go_after_deferred_push_verified`", "`go`"]:
            self.assertIn(state, self.content)

    def test_required_checklist_topics(self):
        phrases = [
            "snapshot scanner",
            "absence checks",
            "deferred github push",
            "repository visibility is unchanged",
            "full internal git history publication",
            "internal repository pushed to github",
            "branch and history safety",
            "secret scanner",
            "private key markers",
            "bearer tokens",
            "internal hostnames",
            "internal absolute paths",
            "backend/internal fixtures",
            "license",
            "readme",
            "changelog",
            "version anchor",
            "open blockers",
            "required final verification",
        ]
        for phrase in phrases:
            self.assertIn(phrase, self.lower)

    def test_required_blockers(self):
        for blocker in [
            "`github_push_deferred`",
            "`remote_verification_missing`",
            "`visibility_change_not_authorized`",
        ]:
            self.assertIn(blocker, self.content)

    def test_no_production_ready_overclaiming(self):
        forbidden = [
            "production saas " + "ready",
            "production-ready " + "saas",
            "grantlayer is production " + "ready",
            "grantlayer is production-" + "ready",
            "enterprise complete",
            "tenant isolation is fully " + "implemented",
            "tenant isolation has been " + "implemented",
            "full tenant isolation",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, self.lower)

    def test_no_disallowed_tool_reference(self):
        forbidden = "Paper" + "clip"
        self.assertNotIn(forbidden.lower(), self.lower)

    def test_no_github_visibility_change_instruction(self):
        forbidden = [
            "make the repository public",
            "change github visibility to public",
            "set github visibility to public",
            "publish the internal repository",
            "run git push",
            "git push github",
            "push to github now",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, self.lower)


class TestGL167JsonArtifact(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()

    def test_json_parses(self):
        self.assertIsInstance(self.data, dict)

    def test_required_identity_fields(self):
        self.assertEqual(self.data["issue_id"], "GL-167")
        self.assertEqual(
            self.data["artifact_type"],
            "public_visibility_go_no_go_checklist",
        )
        self.assertEqual(self.data["baseline_internal_main"], BASELINE_INTERNAL_MAIN)
        self.assertEqual(self.data["deferred_publish_commit"], DEFERRED_PUBLISH_COMMIT)

    def test_recommendation_is_no_go(self):
        self.assertEqual(self.data["current_recommendation"], "no_go")
        self.assertIn("GitHub push is deferred", self.data["recommendation_reason"])
        self.assertIn("final remote verification has not occurred", self.data["recommendation_reason"])

    def test_decision_states(self):
        self.assertEqual(
            self.data["decision_states"],
            ["no_go", "go_after_deferred_push_verified", "go"],
        )

    def test_blockers_include_required_values(self):
        blockers = set(self.data["blockers"])
        self.assertIn("github_push_deferred", blockers)
        self.assertIn("remote_verification_missing", blockers)
        self.assertIn("visibility_change_not_authorized", blockers)

    def test_non_goals_are_explicit(self):
        non_goals = set(self.data["explicit_non_goals"])
        for value in [
            "push_to_github",
            "change_github_visibility",
            "force_push",
            "push_internal_repo_to_github",
            "publish_full_internal_git_history",
            "change_production_code",
            "change_backend_src",
            "change_openapi",
            "change_migrations",
        ]:
            self.assertIn(value, non_goals)

    def test_status_flags_preserve_scope(self):
        status = self.data["status"]
        self.assertTrue(status["public_visibility_readiness_checklist"])
        for key in [
            "public_launch",
            "github_push_performed",
            "remote_verification_completed",
            "visibility_change_authorized",
            "repository_visibility_changed",
            "force_push_performed",
            "internal_repo_pushed_to_github",
            "full_internal_history_published",
            "production_code_changed",
            "backend_src_changed",
            "openapi_changed",
            "migrations_changed",
            "dependencies_changed",
            "production_saas_ready_claimed",
            "tenant_isolation_claimed_implemented",
            "public_launch_claimed",
        ]:
            self.assertIs(status[key], False, f"Expected false for {key}")

    def test_no_disallowed_tool_reference(self):
        forbidden = ("Paper" + "clip").lower()
        serialized = json.dumps(self.data, sort_keys=True).lower()
        self.assertNotIn(forbidden, serialized)


class TestGL167ScopeGuard(unittest.TestCase):
    def test_changed_files_stay_in_issue_scope(self):
        current_branch = (
            subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.strip()
        )
        if current_branch != GL167_BRANCH:
            self.skipTest(f"Not on {GL167_BRANCH} branch; skipping diff-based scope guard.")
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        changed = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        allowed = {
            "docs/public_visibility_go_no_go_checklist.md",
            "docs/examples/gl167/public_visibility_go_no_go_checklist.json",
            "backend/tests/test_gl167_public_visibility_go_no_go_checklist.py",
        }
        self.assertTrue(changed.issubset(allowed), f"Unexpected changed files: {changed - allowed}")

    def test_forbidden_paths_not_changed(self):
        current_branch = (
            subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.strip()
        )
        if current_branch != GL167_BRANCH:
            self.skipTest(f"Not on {GL167_BRANCH} branch; skipping diff-based scope guard.")
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        changed = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        forbidden_prefixes = (
            "backend/src/",
            "backend/src/migrations/",
            "frontend/",
            "website/",
            "design/",
        )
        forbidden_files = {
            "docs/openapi.yaml",
            "requirements.txt",
            "requirements-dev.txt",
        }
        for path in changed:
            self.assertFalse(path.startswith(forbidden_prefixes), path)
            self.assertNotIn(path, forbidden_files)
