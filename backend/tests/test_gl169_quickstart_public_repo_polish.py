"""GL-169 quickstart URL and public repository polish validation tests."""

import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
README_PATH = REPO_ROOT / "README.md"
FIRST_OUTPUT_DOC_PATH = REPO_ROOT / "docs" / "first_verifiable_output.md"
ARTIFACT_PATH = (
    REPO_ROOT
    / "docs"
    / "examples"
    / "gl169"
    / "quickstart_public_repo_polish.json"
)

EXPECTED_CHANGED_FILES = {
    "README.md",
    "backend/tests/test_gl168_first_verifiable_output.py",
    "backend/tests/test_gl169_quickstart_public_repo_polish.py",
    "docs/examples/gl169/quickstart_public_repo_polish.json",
}

GL169_BRANCH = "gl-169-quickstart-public-repo-polish"

REQUIRED_ARTIFACT_FIELDS = {
    "issue_id",
    "title",
    "base_commit",
    "changed_files",
    "public_facing_summary",
    "quickstart_command",
    "expected_output",
    "safety_caveats",
    "non_goals",
    "validation_checklist",
    "next_recommended_step",
}


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalized(*paths):
    content = "\n".join(_read(path) for path in paths)
    return " ".join(content.lower().split())


class TestGL169ReadmePublicPolish(unittest.TestCase):
    def setUp(self):
        self.readme = _normalized(README_PATH)
        self.readme_and_doc = _normalized(README_PATH, FIRST_OUTPUT_DOC_PATH)

    def test_readme_has_public_facing_description_and_status(self):
        for phrase in [
            "grantlayer is a verification, audit, and compliance layer",
            "developer preview",
            "local evaluation and controlled pilot only",
            "not production saas",
            "tenant/workspace isolation",
            "not implemented",
        ]:
            self.assertIn(phrase, self.readme)

    def test_readme_references_first_verifiable_output(self):
        for phrase in [
            "first verifiable output quickstart",
            "docs/first_verifiable_output.md",
            "examples/first_verifiable_output.json",
            "/tmp/grantlayer_first_output.json",
            "committed deterministic reference output",
            "git clone https://github.com/discodone/grantlayer.git",
        ]:
            self.assertIn(phrase, self.readme)
        self.assertNotIn("git clone <repo>", self.readme)
        self.assertNotIn(
            "https://github.com/<org_or_user>/grantlayer-mvp.git",
            self.readme,
        )

    def test_readme_includes_exact_first_output_command(self):
        self.assertIn(
            "python3 examples/first_verifiable_output.py --output /tmp/grantlayer_first_output.json",
            self.readme,
        )

    def test_docs_state_local_safety_boundaries(self):
        for phrase in [
            "requires no real secrets",
            "requires no customer data",
            "local/demo only",
            "no real secrets",
            "no real customer data",
        ]:
            self.assertIn(phrase, self.readme_and_doc)

    def test_docs_do_not_overclaim_production_or_tenant_isolation(self):
        forbidden_claims = [
            "production saas ready",
            "production-ready saas",
            "ready for production saas",
            "tenant isolation is implemented",
            "tenant isolation implemented",
            "tenant/workspace isolation is implemented",
            "tenant/workspace isolation implemented",
        ]
        for phrase in forbidden_claims:
            self.assertNotIn(phrase, self.readme_and_doc)
        self.assertIn("tenant isolation is not implemented", self.readme_and_doc)
        self.assertIn("production saas readiness is not claimed", self.readme_and_doc)

    def test_docs_do_not_instruct_github_push_or_visibility_change(self):
        forbidden_instructions = [
            "git push",
            "gh repo edit",
            "change repository visibility to public",
            "make the repository public",
            "publish to github now",
            "push to github now",
        ]
        for phrase in forbidden_instructions:
            self.assertNotIn(phrase, self.readme_and_doc)
        self.assertIn("no github push", self.readme)
        self.assertIn("no repository visibility change", self.readme)


class TestGL169Artifact(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(_read(ARTIFACT_PATH))

    def test_artifact_exists_and_is_valid_json(self):
        self.assertTrue(ARTIFACT_PATH.is_file())
        self.assertEqual(self.data["issue_id"], "GL-169")

    def test_artifact_contains_required_fields(self):
        self.assertTrue(REQUIRED_ARTIFACT_FIELDS.issubset(self.data))
        self.assertEqual(
            self.data["quickstart_command"],
            "python3 examples/first_verifiable_output.py --output /tmp/grantlayer_first_output.json",
        )
        self.assertEqual(
            self.data["expected_output"]["generated_path"],
            "/tmp/grantlayer_first_output.json",
        )
        self.assertEqual(
            self.data["expected_output"]["committed_reference_path"],
            "examples/first_verifiable_output.json",
        )
        self.assertEqual(
            self.data["expected_output"]["documentation_path"],
            "docs/first_verifiable_output.md",
        )

    def test_artifact_records_safety_caveats_and_non_goals(self):
        caveats = " ".join(self.data["safety_caveats"]).lower()
        non_goals = set(self.data["non_goals"])
        for phrase in [
            "no real secrets required",
            "no customer data required",
            "local/demo only",
            "not production saas",
            "tenant isolation is not implemented yet",
            "no github push is performed",
            "no repository visibility change is performed",
        ]:
            self.assertIn(phrase, caveats)
        for non_goal in [
            "push_to_github",
            "change_repository_visibility",
            "publish_public_snapshot",
            "claim_production_saas_readiness",
            "claim_tenant_isolation_implemented",
            "change_backend_src",
            "change_openapi",
            "change_migrations",
            "change_database_schema",
            "change_dependencies",
        ]:
            self.assertIn(non_goal, non_goals)


class TestGL169ScopeGuard(unittest.TestCase):
    def test_changed_files_stay_within_allowed_scope(self):
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        if branch != GL169_BRANCH:
            self.skipTest(f"Not on {GL169_BRANCH} branch; skipping diff-based scope guard.")

        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        changed = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        self.assertEqual(changed, EXPECTED_CHANGED_FILES)
        for path in changed:
            self.assertFalse(path.startswith("backend/src/"), path)
            self.assertFalse(path.startswith("backend/src/migrations/"), path)
            self.assertFalse(path.startswith("frontend/"), path)
            self.assertFalse(path.startswith("website/"), path)
            self.assertFalse(path.startswith("design/"), path)
            self.assertFalse(path.startswith(".claude/"), path)
            self.assertNotEqual(path, "docs/openapi.yaml")
            self.assertNotIn(path, {"requirements.txt", "requirements-dev.txt"})
