import json
import os
import unittest

REPORT_MD = "docs/public_snapshot_correction_push_gl187.md"
ARTIFACT_JSON = "docs/examples/gl187p/public_snapshot_correction_push_gl187.json"

_ARTIFACT = None


def _load_artifact():
    global _ARTIFACT
    if _ARTIFACT is None:
        with open(ARTIFACT_JSON, encoding="utf-8") as f:
            _ARTIFACT = json.load(f)
    return _ARTIFACT


class TestGL187PReportExists(unittest.TestCase):
    def test_report_markdown_exists(self):
        self.assertTrue(os.path.isfile(REPORT_MD), f"Missing: {REPORT_MD}")

    def test_json_artifact_exists(self):
        self.assertTrue(os.path.isfile(ARTIFACT_JSON), f"Missing: {ARTIFACT_JSON}")

    def test_json_artifact_is_valid_json(self):
        a = _load_artifact()
        self.assertIsInstance(a, dict)


class TestGL187PArtifactFields(unittest.TestCase):
    def test_issue_id(self):
        a = _load_artifact()
        self.assertEqual(a["issue_id"], "GL-187P")

    def test_public_publish_worktree(self):
        a = _load_artifact()
        self.assertEqual(a["public_publish_worktree"], "/tmp/grantlayer-public-publish")

    def test_github_remote(self):
        a = _load_artifact()
        self.assertEqual(a["github_remote"], "https://github.com/discodone/grantlayer.git")

    def test_previous_public_commit_present(self):
        a = _load_artifact()
        self.assertIn("previous_public_commit", a)
        self.assertTrue(len(a["previous_public_commit"]) >= 7)

    def test_new_public_commit_present_when_correction_pushed(self):
        a = _load_artifact()
        if a["final_disposition"] == "correction_pushed":
            self.assertIn("new_public_commit", a)
            self.assertTrue(len(a["new_public_commit"]) >= 7)

    def test_gl187_fixes_published_keys(self):
        a = _load_artifact()
        fixes = a["gl187_fixes_published"]
        self.assertIn("readme_stale_test_count_removed", fixes)
        self.assertIn("contributing_public_release_stale_claim_removed", fixes)
        self.assertIn("agents_llms_full_stale_public_state_removed", fixes)
        self.assertIn("ten_minute_quickstart_public_clone_corrected", fixes)
        self.assertIn("agent_quickstart_public_clone_internal_source_corrected", fixes)
        self.assertTrue(fixes["readme_stale_test_count_removed"])
        self.assertTrue(fixes["contributing_public_release_stale_claim_removed"])

    def test_stale_phrase_verification_exists(self):
        a = _load_artifact()
        self.assertIn("stale_phrase_verification", a)
        spv = a["stale_phrase_verification"]
        self.assertIn("result", spv)
        self.assertEqual(spv["result"], "CLEAN")
        self.assertEqual(spv["occurrences_found"], 0)

    def test_caveats_preserved_exists(self):
        a = _load_artifact()
        self.assertIn("caveats_preserved", a)
        cp = a["caveats_preserved"]
        self.assertTrue(cp.get("developer_preview"))
        self.assertTrue(cp.get("not_production_saas"))
        self.assertTrue(cp.get("tenant_isolation_not_implemented"))
        self.assertTrue(cp.get("no_real_secrets_or_customer_data"))

    def test_private_data_secret_safety_object_exists(self):
        a = _load_artifact()
        self.assertIn("private_data_secret_safety", a)

    def test_private_data_secret_safety_private_data_field(self):
        a = _load_artifact()
        safety = a["private_data_secret_safety"]
        self.assertIn("private_data_found", safety)
        self.assertIsInstance(safety["private_data_found"], bool)

    def test_private_data_secret_safety_secret_material_field(self):
        a = _load_artifact()
        safety = a["private_data_secret_safety"]
        self.assertIn("secret_material_found", safety)
        self.assertIsInstance(safety["secret_material_found"], bool)

    def test_blocked_when_blockers_found(self):
        a = _load_artifact()
        safety = a["private_data_secret_safety"]
        if safety.get("blockers_found"):
            self.assertEqual(
                a["final_disposition"],
                "blocked_private_data_or_secret_safety",
            )

    def test_no_private_data_found(self):
        a = _load_artifact()
        safety = a["private_data_secret_safety"]
        self.assertFalse(safety["private_data_found"])

    def test_no_secret_material_found(self):
        a = _load_artifact()
        safety = a["private_data_secret_safety"]
        self.assertFalse(safety["secret_material_found"])


class TestGL187PPublicationActions(unittest.TestCase):
    def test_snapshot_pushed_when_correction_pushed(self):
        a = _load_artifact()
        if a["final_disposition"] == "correction_pushed":
            self.assertTrue(a["publication_actions"]["public_snapshot_pushed"])

    def test_force_push_not_used(self):
        a = _load_artifact()
        self.assertFalse(a["publication_actions"]["force_push_used"])

    def test_visibility_not_changed(self):
        a = _load_artifact()
        self.assertFalse(a["publication_actions"]["visibility_changed"])

    def test_internal_repo_not_pushed_directly_to_github(self):
        a = _load_artifact()
        self.assertFalse(a["publication_actions"]["internal_repo_pushed_directly_to_github"])


class TestGL187PReportContent(unittest.TestCase):
    def _read_report(self):
        with open(REPORT_MD, encoding="utf-8") as f:
            return f.read()

    def test_report_says_no_force_push(self):
        content = self._read_report()
        self.assertIn("No force push", content)

    def test_report_says_visibility_unchanged(self):
        content = self._read_report()
        self.assertIn("Visibility unchanged", content.replace("visibility unchanged", "Visibility unchanged"))
        # Accept either capitalisation
        self.assertTrue(
            "isibility unchanged" in content or "isibility change" in content.lower(),
            "Report must state visibility unchanged",
        )

    def test_report_says_internal_repo_not_pushed(self):
        content = self._read_report()
        self.assertIn("NOT pushed directly to GitHub", content)

    def test_report_correction_pushed_disposition(self):
        content = self._read_report()
        self.assertIn("correction_pushed", content)


class TestGL187PChangedFilesScope(unittest.TestCase):
    def test_no_backend_src_changes(self):
        a = _load_artifact()
        self.assertTrue(a["changed_files"]["no_backend_src_changes"])

    def test_no_openapi_changes(self):
        a = _load_artifact()
        self.assertTrue(a["changed_files"]["no_openapi_changes"])

    def test_no_migration_changes(self):
        a = _load_artifact()
        self.assertTrue(a["changed_files"]["no_migration_changes"])

    def test_no_db_schema_changes(self):
        a = _load_artifact()
        self.assertTrue(a["changed_files"]["no_db_schema_changes"])

    def test_no_dependency_changes(self):
        a = _load_artifact()
        self.assertTrue(a["changed_files"]["no_dependency_changes"])

    def test_no_frontend_website_design_changes(self):
        a = _load_artifact()
        self.assertTrue(a["changed_files"]["no_frontend_website_design_changes"])

    def test_no_github_workflow_changes(self):
        a = _load_artifact()
        self.assertTrue(a["changed_files"]["no_github_workflow_changes"])

    def test_no_snapshot_publish_script_behavior_changes(self):
        a = _load_artifact()
        self.assertTrue(a["changed_files"]["no_snapshot_publish_script_behavior_changes"])

    def test_no_git_remote_changes(self):
        a = _load_artifact()
        self.assertTrue(a["changed_files"]["no_git_remote_changes"])

    def test_no_paperclip_status_updates(self):
        a = _load_artifact()
        self.assertTrue(a["changed_files"]["no_paperclip_status_updates"])

    def test_internal_report_files_only(self):
        a = _load_artifact()
        for f in a["changed_files"]["internal_report_files"]:
            self.assertFalse(
                f.startswith("backend/src/"),
                f"Report file in backend/src/: {f}",
            )
