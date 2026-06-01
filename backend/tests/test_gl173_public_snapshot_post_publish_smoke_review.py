"""GL-173 public snapshot post-publish smoke review artifact validation."""

import json
import os
import re
import unittest

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_ARTIFACT_MD = os.path.join(
    _REPO_ROOT,
    "docs",
    "public_snapshot_post_publish_smoke_review.md",
)
_ARTIFACT_JSON = os.path.join(
    _REPO_ROOT,
    "docs",
    "examples",
    "gl173",
    "public_snapshot_post_publish_smoke_review.json",
)

_EXPECTED_GITHUB_REPO = "https://github.com/discodone/grantlayer.git"
_ALLOWED_CHANGED_FILES = {
    "docs/public_snapshot_post_publish_smoke_review.md",
    "docs/examples/gl173/public_snapshot_post_publish_smoke_review.json",
    "backend/tests/test_gl173_public_snapshot_post_publish_smoke_review.py",
}
_REQUIRED_ABSENCE_KEYS = {
    "docs_demo_script_md_absent",
    "docs_examples_gl163_audit_snapshot_asset_json_absent",
    "excluded_gl164_gl165_internal_label_artifacts_absent",
    "dot_claude_absent",
    "backend_internal_fixtures_absent",
    "internal_forgejo_hostnames_or_remotes_absent",
    "paperclip_path_absent",
    "paperclip_references_absent",
    "private_key_markers_absent",
    "raw_tokens_api_keys_passwords_session_cookies_jwts_absent",
    "private_absolute_paths_absent",
    "customer_data_absent",
    "private_emails_or_phone_numbers_absent",
    "internal_repo_push_instructions_absent",
    "github_visibility_change_instructions_absent",
}


class TestGL173ArtifactFilesExist(unittest.TestCase):
    def test_markdown_exists(self):
        self.assertTrue(os.path.isfile(_ARTIFACT_MD), f"Markdown not found: {_ARTIFACT_MD}")

    def test_json_exists(self):
        self.assertTrue(os.path.isfile(_ARTIFACT_JSON), f"Artifact JSON not found: {_ARTIFACT_JSON}")


class TestGL173ArtifactJSON(unittest.TestCase):
    def setUp(self):
        with open(_ARTIFACT_JSON, encoding="utf-8") as fh:
            self._artifact = json.load(fh)

    def test_valid_json(self):
        self.assertIsInstance(self._artifact, dict)

    def test_issue_id(self):
        self.assertEqual(self._artifact.get("issue_id"), "GL-173")

    def test_github_repo(self):
        self.assertEqual(self._artifact.get("github_repo"), _EXPECTED_GITHUB_REPO)

    def test_first_output_smoke_present(self):
        smoke = self._artifact.get("first_output_smoke")
        self.assertIsInstance(smoke, dict)
        self.assertIn("result", smoke)
        self.assertIn("diff_result", smoke)
        self.assertEqual(smoke.get("result"), "pass")
        self.assertEqual(smoke.get("diff_result"), "exact_match")

    def test_absence_checks_include_required_keys(self):
        absence = self._artifact.get("absence_checks")
        self.assertIsInstance(absence, dict)
        self.assertTrue(_REQUIRED_ABSENCE_KEYS.issubset(absence.keys()))
        for key in _REQUIRED_ABSENCE_KEYS:
            self.assertTrue(absence.get(key), f"absence_checks.{key} must be true")

    def test_findings_have_required_shape_if_any_exist(self):
        findings = self._artifact.get("findings")
        self.assertIsInstance(findings, list)
        for finding in findings:
            self.assertIn("severity", finding)
            self.assertIn("status", finding)
            self.assertIn("recommendation", finding)

    def test_finding_counts_match_findings(self):
        counts = self._artifact.get("finding_counts_by_severity", {})
        findings = self._artifact.get("findings", [])
        self.assertEqual(counts.get("total"), len(findings))
        for severity in ("critical", "high", "medium", "low"):
            expected = counts.get(severity, 0)
            actual = sum(1 for finding in findings if finding.get("severity") == severity)
            self.assertEqual(expected, actual, f"Count mismatch for severity '{severity}'")

    def test_no_github_push_performed(self):
        self.assertFalse(self._artifact.get("github_push_performed", True))

    def test_no_visibility_change(self):
        self.assertFalse(self._artifact.get("visibility_changed", True))

    def test_no_production_saas_claim(self):
        raw = json.dumps(self._artifact).lower()
        self.assertNotIn("production saas readiness claimed", raw)
        self.assertIsNone(re.search(r"production[- ]ready\s+saas", raw))

    def test_no_tenant_isolation_claim(self):
        raw = json.dumps(self._artifact).lower()
        self.assertNotIn("tenant isolation implemented", raw)

    def test_no_positive_paperclip_usage_claim(self):
        raw = json.dumps(self._artifact).lower()
        for phrase in (
            "paperclip is used",
            "use paperclip",
            "paperclip api calls are required",
            "call paperclip apis",
        ):
            self.assertNotIn(phrase, raw)

    def test_changed_files_within_scope(self):
        changed_files = self._artifact.get("changed_files", [])
        self.assertTrue(changed_files, "changed_files must not be empty")
        for path in changed_files:
            self.assertIn(path, _ALLOWED_CHANGED_FILES, f"Unexpected changed file: {path}")

    def test_next_recommended_step_present(self):
        self.assertTrue(self._artifact.get("next_recommended_step"))


class TestGL173MarkdownContent(unittest.TestCase):
    def setUp(self):
        with open(_ARTIFACT_MD, encoding="utf-8") as fh:
            self._content = fh.read()
        self._lower = self._content.lower()

    def test_must_reference_repo_and_commit(self):
        self.assertIn("GL-173", self._content)
        self.assertIn(_EXPECTED_GITHUB_REPO, self._content)
        self.assertIn("4b42f7f00b11a12413d4e4bdce99c4ea921dfa0d", self._content)

    def test_must_state_no_github_push_and_visibility_change(self):
        self.assertIn("No GitHub push performed", self._content)
        self.assertIn("No visibility change performed", self._content)

    def test_must_reference_first_output_and_canonical_sources(self):
        self.assertIn("first verifiable output", self._lower)
        self.assertIn("README.md", self._content)
        self.assertIn("SECURITY.md", self._content)

    def test_must_not_claim_production_saas_readiness(self):
        self.assertNotIn("production saas readiness claimed", self._lower)
        self.assertIsNone(re.search(r"production[- ]ready\s+saas", self._lower))

    def test_must_not_claim_tenant_isolation_implemented(self):
        self.assertNotIn("tenant isolation implemented", self._lower)

    def test_no_positive_paperclip_usage_claim(self):
        for phrase in (
            "paperclip is used",
            "use paperclip",
            "paperclip api calls are required",
            "call paperclip apis",
        ):
            self.assertNotIn(phrase, self._lower)
