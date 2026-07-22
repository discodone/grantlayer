"""GL-165 Public CHANGELOG / Version Anchors validation tests."""

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"
README_PATH = REPO_ROOT / "README.md"
JSON_PATH = (
    REPO_ROOT
    / "docs"
    / "examples"
    / "gl165"
    / "public_changelog_version_anchors.json"
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _load_json():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestGL165ChangelogExists(unittest.TestCase):
    def test_changelog_exists(self):
        self.assertTrue(CHANGELOG_PATH.is_file(), f"Missing: {CHANGELOG_PATH}")

    def test_changelog_title(self):
        self.assertTrue(_read(CHANGELOG_PATH).startswith("# Changelog"))


class TestGL165CaveatsAndSafety(unittest.TestCase):
    def setUp(self):
        self.content = _read(CHANGELOG_PATH)
        self.lower = self.content.lower()

    def test_no_production_readiness_claim(self):
        forbidden = [
            "production saas " + "ready",
            "production-ready " + "saas",
            "grantlayer is production " + "ready",
            "grantlayer is production-" + "ready",
            "enterprise complete",
            "full compliance",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, self.lower)

    def test_no_tenant_isolation_implemented_claim(self):
        forbidden = [
            "tenant isolation " + "implemented",
            "tenant isolation is " + "implemented",
            "tenant isolation has been " + "implemented",
            "full tenant isolation",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, self.lower)

    def test_no_private_hostnames_or_paths(self):
        forbidden = [
            "forge." + "hofercloud.eu",
            "terminal." + "hofercloud.eu",
            "forge." + "internal.invalid",
            "terminal." + "internal.invalid",
            "/home/" + "adminuser",
            "/home/" + "oai",
            "/mnt/" + "data",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, self.content)


class TestGL165JsonArtifact(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()

    def test_json_parses(self):
        self.assertIsInstance(self.data, dict)

    def test_required_values(self):
        self.assertEqual(self.data["issue"], "GL-165")
        self.assertEqual(self.data["status"], "developer-preview-version-anchors")
        self.assertEqual(self.data["changelogPath"], "CHANGELOG.md")
        self.assertTrue(self.data["publicSnapshotModel"])
        self.assertEqual(self.data["sourceOfTruth"], "internal-forgejo")

    def test_required_arrays(self):
        for key in [
            "caveats",
            "publicUpdateWorkflow",
            "publicHardeningNotes",
            "forbiddenClaims",
        ]:
            self.assertIn(key, self.data)
            self.assertIsInstance(self.data[key], list)
            self.assertGreater(len(self.data[key]), 0)

    def test_caveats_include_required_safety_phrases(self):
        caveats = " ".join(self.data["caveats"]).lower()
        self.assertIn("developer preview", caveats)
        self.assertIn("not production saas", caveats)
        self.assertIn("tenant isolation is not implemented", caveats)
        self.assertIn("real secrets", caveats)
        self.assertIn("real customer data", caveats)
        self.assertIn("clean snapshot", caveats)

    def test_public_update_workflow_includes_required_steps(self):
        workflow = self.data["publicUpdateWorkflow"]
        for step in [
            "internal-issue",
            "internal-branch",
            "validation",
            "merge-to-internal-main",
            "build-clean-snapshot",
            "scanner-clean",
            "publish-public-snapshot",
        ]:
            self.assertIn(step, workflow)


class TestGL165ReadmeLink(unittest.TestCase):
    def test_readme_links_to_changelog(self):
        readme = _read(README_PATH)
        self.assertIn("[CHANGELOG.md](CHANGELOG.md)", readme)
