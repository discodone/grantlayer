"""GL-172 Public Snapshot Publish Gate — pre-publish caution resolution and publish verification."""

import json
import os
import re
import subprocess
import unittest

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_ARTIFACT_JSON = os.path.join(
    _REPO_ROOT,
    "docs",
    "examples",
    "gl172",
    "public_snapshot_publish_gate.json",
)
_SNAPSHOT_SCRIPT = os.path.join(_REPO_ROOT, "scripts", "build-clean-public-snapshot.sh")
_GITHUB_REMOTE = "https://github.com/discodone/grantlayer.git"
_PUBLISH_WORKTREE = "/tmp/grantlayer-public-publish"

_REQUIRED_EXCLUSIONS = [
    "docs/demo_script.md",
    "docs/examples/gl163/post_public_agent_intake_triage.json",
    "docs/examples/gl164a/public_repo_discovery_metadata.json",
    "docs/examples/gl165/public_changelog_version_anchors.json",
    "docs/public_release_github_snapshot_readiness_review.md",
    "docs/examples/gl171/public_release_github_snapshot_readiness_review.json",
]

_PRIVATE_PATTERNS = [
    r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----",
    r"ghp_[A-Za-z0-9]{36}",
    r"github_pat_[A-Za-z0-9_]{82}",
    r"AKIA[0-9A-Z]{16}",
    r"tapWjoj",
]

_FORBIDDEN_SCOPE_PATTERNS = [
    r"^backend/src/",
    r"^docs/openapi\.yaml$",
    r"^migrations/",
    r"^requirements(?:-dev)?\.txt$",
    r"^frontend/",
    r"^dashboard/",
]


class TestGL172ArtifactExists(unittest.TestCase):
    def test_artifact_json_exists(self):
        self.assertTrue(os.path.isfile(_ARTIFACT_JSON), f"Artifact not found: {_ARTIFACT_JSON}")

    def test_snapshot_script_exists(self):
        self.assertTrue(os.path.isfile(_SNAPSHOT_SCRIPT), f"Snapshot script not found: {_SNAPSHOT_SCRIPT}")


class TestGL172ArtifactContent(unittest.TestCase):
    def setUp(self):
        with open(_ARTIFACT_JSON) as fh:
            self._a = json.load(fh)

    def test_issue_id(self):
        self.assertEqual(self._a.get("issue_id"), "GL-172")

    def test_github_remote(self):
        self.assertEqual(
            self._a.get("github_remote"),
            _GITHUB_REMOTE,
            f"github_remote must be {_GITHUB_REMOTE}",
        )

    def test_publish_worktree(self):
        self.assertEqual(
            self._a.get("publish_worktree"),
            _PUBLISH_WORKTREE,
            f"publish_worktree must be {_PUBLISH_WORKTREE}",
        )

    def test_no_visibility_change(self):
        self.assertFalse(
            self._a.get("visibility_changed", True),
            "visibility_changed must be false",
        )

    def test_no_force_push(self):
        self.assertFalse(
            self._a.get("force_push_performed", True),
            "force_push_performed must be false",
        )

    def test_internal_repo_not_pushed_to_github(self):
        self.assertFalse(
            self._a.get("internal_repo_pushed_to_github", True),
            "internal_repo_pushed_to_github must be false",
        )

    def test_github_push_from_publish_worktree(self):
        push_source = self._a.get("github_push_source", "")
        self.assertEqual(
            push_source,
            _PUBLISH_WORKTREE,
            f"github_push_source must be {_PUBLISH_WORKTREE}",
        )

    def test_f001_resolved(self):
        findings = self._a.get("resolved_findings", [])
        f001 = next((f for f in findings if f.get("id") == "F-001"), None)
        self.assertIsNotNone(f001, "F-001 must appear in resolved_findings")
        self.assertEqual(f001.get("status"), "resolved", "F-001 must be resolved")

    def test_f002_resolved(self):
        findings = self._a.get("resolved_findings", [])
        f002 = next((f for f in findings if f.get("id") == "F-002"), None)
        self.assertIsNotNone(f002, "F-002 must appear in resolved_findings")
        self.assertEqual(f002.get("status"), "resolved", "F-002 must be resolved")

    def test_excluded_files_listed(self):
        excluded = self._a.get("excluded_files_added", [])
        for req in _REQUIRED_EXCLUSIONS:
            self.assertIn(req, excluded, f"Required exclusion missing from artifact: {req}")

    def test_absence_checks_all_true(self):
        checks = self._a.get("absence_checks", {})
        self.assertTrue(len(checks) > 0, "absence_checks must not be empty")
        for key, val in checks.items():
            self.assertTrue(val, f"absence_checks.{key} must be true")

    def test_first_output_present(self):
        fop = self._a.get("first_output_present", {})
        self.assertTrue(fop.get("examples_first_verifiable_output_py"), "first verifiable output py must be present")
        self.assertTrue(fop.get("examples_first_verifiable_output_json"), "first verifiable output json must be present")
        self.assertTrue(fop.get("docs_first_verifiable_output_md"), "first verifiable output md must be present")

    def test_changed_files_within_scope(self):
        changed = self._a.get("changed_files", [])
        self.assertGreater(len(changed), 0)
        for path in changed:
            for pattern in _FORBIDDEN_SCOPE_PATTERNS:
                self.assertIsNone(
                    re.match(pattern, path),
                    f"Changed file '{path}' violates forbidden scope pattern '{pattern}'",
                )

    def test_no_backend_src_in_changed_files(self):
        for path in self._a.get("changed_files", []):
            self.assertFalse(path.startswith("backend/src/"), f"backend/src/ must not be changed: '{path}'")

    def test_no_production_saas_overclaim(self):
        raw = json.dumps(self._a).lower()
        self.assertNotIn("production saas readiness claimed", raw)
        self.assertIsNone(re.search(r"production[- ]ready\s+saas", raw))

    def test_no_tenant_isolation_claim(self):
        raw = json.dumps(self._a).lower()
        self.assertNotIn("tenant isolation implemented", raw)

    def test_no_paperclip_reference_in_artifact(self):
        raw = json.dumps(self._a)
        lower = raw.lower()
        self.assertNotIn("paperclip api", lower)
        self.assertNotIn("call paperclip", lower)


class TestGL172SnapshotExclusionList(unittest.TestCase):
    def setUp(self):
        with open(_SNAPSHOT_SCRIPT) as fh:
            self._script = fh.read()

    def test_demo_script_md_excluded(self):
        self.assertIn(
            '"docs/demo_script.md"',
            self._script,
            "docs/demo_script.md must be in PUBLIC_EXPORT_EXCLUDE",
        )

    def test_gl163_excluded(self):
        self.assertIn(
            '"docs/examples/gl163/post_public_agent_intake_triage.json"',
            self._script,
            "docs/examples/gl163/post_public_agent_intake_triage.json must be in PUBLIC_EXPORT_EXCLUDE",
        )

    def test_gl164a_excluded(self):
        self.assertIn(
            '"docs/examples/gl164a/public_repo_discovery_metadata.json"',
            self._script,
            "docs/examples/gl164a/public_repo_discovery_metadata.json must be in PUBLIC_EXPORT_EXCLUDE",
        )

    def test_gl165_excluded(self):
        self.assertIn(
            '"docs/examples/gl165/public_changelog_version_anchors.json"',
            self._script,
            "docs/examples/gl165/public_changelog_version_anchors.json must be in PUBLIC_EXPORT_EXCLUDE",
        )

    def test_no_private_patterns_in_script(self):
        for pattern in _PRIVATE_PATTERNS:
            self.assertIsNone(
                re.search(pattern, self._script),
                f"Snapshot script must not contain secret pattern '{pattern}'",
            )


class TestGL172READMEWording(unittest.TestCase):
    def setUp(self):
        readme_path = os.path.join(_REPO_ROOT, "README.md")
        with open(readme_path) as fh:
            self._readme = fh.read()

    def test_no_stale_gl169_only_wording(self):
        self.assertNotIn(
            "GL-169 is public-facing polish only",
            self._readme,
            "Stale GL-169-specific wording must be removed from README.md",
        )

    def test_first_verifiable_output_present(self):
        self.assertIn("first_verifiable_output", self._readme)

    def test_no_production_saas_readiness_overclaim(self):
        lower = self._readme.lower()
        self.assertIsNone(re.search(r"production[- ]ready\s+saas", lower))

    def test_no_tenant_isolation_implemented_claim(self):
        self.assertNotIn("tenant isolation implemented", self._readme.lower())


class TestGL172PublishWorktree(unittest.TestCase):
    def test_publish_worktree_exists(self):
        self.assertTrue(
            os.path.isdir(_PUBLISH_WORKTREE),
            f"Publish worktree must exist: {_PUBLISH_WORKTREE}",
        )

    def test_publish_worktree_not_internal_repo(self):
        publish_real = os.path.realpath(_PUBLISH_WORKTREE)
        internal_real = os.path.realpath(_REPO_ROOT)
        self.assertNotEqual(
            publish_real,
            internal_real,
            "Publish worktree must not be the same directory as the internal repo",
        )

    def test_publish_worktree_remote_is_github(self):
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=_PUBLISH_WORKTREE,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            self.skipTest("Publish worktree git remote not accessible")
        remote = result.stdout.strip()
        self.assertEqual(
            remote,
            _GITHUB_REMOTE,
            f"Publish worktree origin must be {_GITHUB_REMOTE}, got '{remote}'",
        )

    def test_demo_script_absent_from_publish_worktree(self):
        path = os.path.join(_PUBLISH_WORKTREE, "docs", "demo_script.md")
        self.assertFalse(
            os.path.exists(path),
            f"docs/demo_script.md must be absent from publish worktree after snapshot refresh",
        )

    def test_gl163_absent_from_publish_worktree(self):
        path = os.path.join(_PUBLISH_WORKTREE, "docs", "examples", "gl163", "post_public_agent_intake_triage.json")
        self.assertFalse(
            os.path.exists(path),
            "gl163/post_public_agent_intake_triage.json must be absent from publish worktree",
        )

    def test_gl171_review_doc_absent_from_publish_worktree(self):
        path = os.path.join(_PUBLISH_WORKTREE, "docs", "public_release_github_snapshot_readiness_review.md")
        self.assertFalse(
            os.path.exists(path),
            "docs/public_release_github_snapshot_readiness_review.md must be absent (internal gate doc)",
        )

    def test_gl171_review_artifact_absent_from_publish_worktree(self):
        path = os.path.join(_PUBLISH_WORKTREE, "docs", "examples", "gl171", "public_release_github_snapshot_readiness_review.json")
        self.assertFalse(
            os.path.exists(path),
            "docs/examples/gl171/public_release_github_snapshot_readiness_review.json must be absent (internal gate artifact)",
        )

    def test_scanner_script_present_in_publish_worktree(self):
        path = os.path.join(_PUBLISH_WORKTREE, "scripts", "public-secret-sensitive-scan.sh")
        self.assertTrue(
            os.path.exists(path),
            "scripts/public-secret-sensitive-scan.sh must be present in publish worktree (self-excluding scanner)",
        )

    def test_first_verifiable_output_in_publish_worktree(self):
        for rel in [
            "examples/first_verifiable_output.py",
            "examples/first_verifiable_output.json",
            "docs/first_verifiable_output.md",
        ]:
            self.assertTrue(
                os.path.exists(os.path.join(_PUBLISH_WORKTREE, rel)),
                f"{rel} must be present in publish worktree",
            )

    def test_no_paperclip_path_in_publish_worktree(self):
        result = subprocess.run(
            ["grep", "-r", "/paperclip/", "."],
            cwd=_PUBLISH_WORKTREE,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        matches = result.stdout.strip()
        self.assertEqual(
            matches,
            "",
            f"No /paperclip/ path must appear in publish worktree, found:\n{matches}",
        )

    def test_no_internal_forgejo_in_publish_worktree(self):
        result = subprocess.run(
            ["grep", "-r", "internal-forgejo", "."],
            cwd=_PUBLISH_WORKTREE,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        matches = result.stdout.strip()
        self.assertEqual(
            matches,
            "",
            f"No internal-forgejo label must appear in publish worktree, found:\n{matches}",
        )

    def test_no_dot_claude_in_publish_worktree(self):
        self.assertFalse(
            os.path.exists(os.path.join(_PUBLISH_WORKTREE, ".claude")),
            ".claude must not exist in publish worktree",
        )

    def test_no_backend_in_publish_worktree(self):
        self.assertFalse(
            os.path.exists(os.path.join(_PUBLISH_WORKTREE, "backend")),
            "backend/ must not exist in publish worktree",
        )


if __name__ == "__main__":
    unittest.main()
