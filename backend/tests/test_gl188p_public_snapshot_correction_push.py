"""GL-188P public snapshot correction push regression tests."""

import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

REPORT_PATH = REPO_ROOT / "docs" / "public_snapshot_correction_push_gl188.md"
ARTIFACT_PATH = REPO_ROOT / "docs" / "examples" / "gl188p" / "public_snapshot_correction_push_gl188.json"

ALLOWED_CHANGED_FILES = {
    "docs/public_snapshot_correction_push_gl188.md",
    "docs/examples/gl188p/public_snapshot_correction_push_gl188.json",
    "backend/tests/test_gl188p_public_snapshot_correction_push.py",
    "scripts/build-clean-public-snapshot.sh",
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_artifact() -> dict:
    return json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))


def _changed_files() -> list[str]:
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout
    if status.strip():
        changed = []
        for entry in status.split("\0"):
            if not entry.strip():
                continue
            changed.append(entry[3:].strip() if len(entry) > 3 else entry.strip())
        return changed

    diff = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout
    return [line.strip() for line in diff.splitlines() if line.strip()]


class TestGL188PDocsAndArtifact(unittest.TestCase):
    def test_report_markdown_exists(self):
        self.assertTrue(REPORT_PATH.exists(), f"Report not found: {REPORT_PATH}")

    def test_json_artifact_exists(self):
        self.assertTrue(ARTIFACT_PATH.exists(), f"Artifact not found: {ARTIFACT_PATH}")

    def test_json_artifact_is_valid_json(self):
        data = _load_artifact()
        self.assertIsInstance(data, dict)

    def test_issue_id_is_gl188p(self):
        data = _load_artifact()
        self.assertEqual(data["issue_id"], "GL-188P")

    def test_public_publish_worktree(self):
        data = _load_artifact()
        self.assertEqual(data["public_publish_worktree"], "/tmp/grantlayer-public-publish")

    def test_github_remote(self):
        data = _load_artifact()
        self.assertEqual(
            data["github_remote"],
            "https://github.com/discodone/grantlayer.git",
        )

    def test_previous_public_commit_present(self):
        data = _load_artifact()
        self.assertIn("previous_public_commit", data)
        self.assertTrue(data["previous_public_commit"])

    def test_new_public_commit_present_when_correction_pushed(self):
        data = _load_artifact()
        if data["final_disposition"] == "correction_pushed":
            self.assertIn("new_public_commit", data)
            self.assertTrue(data["new_public_commit"])


class TestGL188PHelperVerification(unittest.TestCase):
    def setUp(self):
        self.data = _load_artifact()

    def test_gl188_helper_published_exists(self):
        self.assertIn("gl188_helper_published", self.data)
        self.assertIsInstance(self.data["gl188_helper_published"], dict)

    def test_helper_behavior_verification_exists(self):
        self.assertIn("helper_behavior_verification", self.data)
        self.assertIsInstance(self.data["helper_behavior_verification"], dict)

    def test_helper_script_present(self):
        hbv = self.data["helper_behavior_verification"]
        self.assertTrue(hbv["script_present"])

    def test_helper_bash_syntax_ok(self):
        hbv = self.data["helper_behavior_verification"]
        self.assertTrue(hbv["bash_syntax_ok"])

    def test_helper_default_output_match(self):
        hbv = self.data["helper_behavior_verification"]
        self.assertTrue(hbv["default_output_match"])

    def test_helper_custom_output_match(self):
        hbv = self.data["helper_behavior_verification"]
        self.assertTrue(hbv["custom_output_match"])

    def test_helper_reference_artifact_unchanged(self):
        hbv = self.data["helper_behavior_verification"]
        self.assertTrue(hbv["reference_artifact_unchanged"])

    def test_helper_no_network_required(self):
        hbv = self.data["helper_behavior_verification"]
        self.assertTrue(hbv["no_network_required"])

    def test_helper_no_backend_required(self):
        hbv = self.data["helper_behavior_verification"]
        self.assertTrue(hbv["no_backend_required"])

    def test_helper_no_secrets_required(self):
        hbv = self.data["helper_behavior_verification"]
        self.assertTrue(hbv["no_secrets_required"])

    def test_helper_no_customer_data_required(self):
        hbv = self.data["helper_behavior_verification"]
        self.assertTrue(hbv["no_customer_data_required"])


class TestGL188PSafetyAndCaveats(unittest.TestCase):
    def setUp(self):
        self.data = _load_artifact()

    def test_stale_phrase_verification_exists(self):
        self.assertIn("stale_phrase_verification", self.data)
        spv = self.data["stale_phrase_verification"]
        self.assertIn("result", spv)

    def test_caveats_preserved_exists(self):
        self.assertIn("caveats_preserved", self.data)
        self.assertIsInstance(self.data["caveats_preserved"], dict)

    def test_private_data_secret_safety_exists(self):
        self.assertIn("private_data_secret_safety", self.data)
        pdss = self.data["private_data_secret_safety"]
        self.assertIn("private_data_found", pdss)
        self.assertIn("secret_material_found", pdss)

    def test_private_data_not_found(self):
        pdss = self.data["private_data_secret_safety"]
        self.assertFalse(pdss["private_data_found"])

    def test_secret_material_not_found(self):
        pdss = self.data["private_data_secret_safety"]
        self.assertFalse(pdss["secret_material_found"])

    def test_blockers_found_implies_blocked_disposition(self):
        pdss = self.data["private_data_secret_safety"]
        if pdss.get("blockers_found"):
            self.assertEqual(
                self.data["final_disposition"],
                "blocked_private_data_or_secret_safety",
            )


class TestGL188PPublicationActions(unittest.TestCase):
    def setUp(self):
        self.data = _load_artifact()

    def test_publication_actions_exist(self):
        self.assertIn("publication_actions", self.data)
        pa = self.data["publication_actions"]
        self.assertIn("public_snapshot_pushed", pa)
        self.assertIn("force_push_used", pa)
        self.assertIn("visibility_changed", pa)
        self.assertIn("internal_repo_pushed_directly_to_github", pa)

    def test_snapshot_pushed_when_correction_pushed(self):
        if self.data["final_disposition"] == "correction_pushed":
            self.assertTrue(self.data["publication_actions"]["public_snapshot_pushed"])

    def test_no_force_push(self):
        self.assertFalse(self.data["publication_actions"]["force_push_used"])

    def test_no_visibility_change(self):
        self.assertFalse(self.data["publication_actions"]["visibility_changed"])

    def test_no_direct_github_push(self):
        self.assertFalse(
            self.data["publication_actions"]["internal_repo_pushed_directly_to_github"]
        )

    def test_report_says_no_force_push(self):
        report = _read_text(REPORT_PATH)
        self.assertIn("Force push used", report)
        self.assertIn("NO", report)

    def test_report_says_visibility_unchanged(self):
        report = _read_text(REPORT_PATH)
        self.assertIn("Visibility changed", report)
        self.assertIn("NO", report)

    def test_report_says_internal_repo_not_pushed_to_github(self):
        report = _read_text(REPORT_PATH)
        self.assertIn("Internal repo was NOT pushed directly to GitHub", report)


class TestGL188PScopeGuard(unittest.TestCase):
    def test_changed_files_stay_within_allowed_scope(self):
        changed_files = _changed_files()
        self.assertEqual(set(changed_files), ALLOWED_CHANGED_FILES)
        for path in changed_files:
            self.assertFalse(path.startswith("backend/src/"), path)
            self.assertNotEqual(path, "docs/openapi.yaml", path)
            self.assertFalse(path.startswith("backend/src/migrations/"), path)
            self.assertFalse(path.startswith("frontend/"), path)
            self.assertFalse(path.startswith("website/"), path)
            self.assertFalse(path.startswith("design/"), path)
            self.assertFalse(path.startswith(".github/workflows/"), path)

    def test_no_forbidden_terms_in_changed_files(self):
        content = "\n".join([
            _read_text(REPORT_PATH),
            _read_text(ARTIFACT_PATH),
        ]).lower()
        for phrase in [
            "github push",
            "force push",
            "backend/src/",
        ]:
            if phrase == "force push":
                self.assertIn("force push used", content, "no_force_push_confirmation missing")
                self.assertNotIn("force push used | **yes**", content, "force_push_used must be NO")
            else:
                self.assertNotIn(phrase, content, f"Forbidden phrase found: {phrase!r}")

    def test_result_is_complete(self):
        data = _load_artifact()
        self.assertIn(
            data["final_disposition"],
            {
                "correction_pushed",
                "blocked_missing_publish_workflow",
                "blocked_unexpected_public_worktree_diff",
                "blocked_private_data_or_secret_safety",
                "blocked_force_push_required",
                "blocked_other_with_reason",
            },
        )
        self.assertIn("next_recommended_step", data)
        self.assertIn("changed_files", data)
        self.assertTrue(data["changed_files"]["no_backend_src_changes"])
        self.assertTrue(data["changed_files"]["no_openapi_changes"])
        self.assertTrue(data["changed_files"]["no_migration_changes"])
        self.assertTrue(data["changed_files"]["no_db_schema_changes"])
        self.assertTrue(data["changed_files"]["no_dependency_changes"])
        self.assertTrue(data["changed_files"]["no_frontend_website_design_changes"])
        self.assertTrue(data["changed_files"]["no_github_workflow_changes"])
        self.assertTrue(data["changed_files"]["no_snapshot_publish_script_behavior_changes"])
        self.assertTrue(data["changed_files"]["no_git_remote_changes"])
        self.assertTrue(data["changed_files"]["no_paperclip_status_updates"])


if __name__ == "__main__":
    unittest.main()
