"""GL-170 status block deduplication validation tests."""

import json
import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
README_PATH = REPO_ROOT / "README.md"
SECURITY_PATH = REPO_ROOT / "SECURITY.md"
ARTIFACT_PATH = (
    REPO_ROOT
    / "docs"
    / "examples"
    / "gl170"
    / "status_block_deduplication.json"
)

DEDUPLICATED_DOCS = [
    REPO_ROOT / "docs" / "developer_adoption_strategy_intake.md",
    REPO_ROOT / "docs" / "public_github_readiness_pack.md",
    REPO_ROOT / "docs" / "ten_minute_quickstart.md",
]

EXPECTED_CHANGED_FILES = {
    "backend/tests/test_gl170_status_block_deduplication.py",
    "docs/developer_adoption_strategy_intake.md",
    "docs/examples/gl170/status_block_deduplication.json",
    "docs/public_github_readiness_pack.md",
    "docs/ten_minute_quickstart.md",
}


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalized(path):
    return " ".join(_read(path).lower().split())


class TestGL170Artifact(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(_read(ARTIFACT_PATH))

    def test_artifact_exists_and_json_parses(self):
        self.assertTrue(ARTIFACT_PATH.is_file())
        self.assertEqual(self.data["issue_id"], "GL-170")
        self.assertEqual(
            self.data["baseline_main"],
            "6165dcd8ea9377674400ba960ae574023a9686a9",
        )

    def test_artifact_contains_required_fields(self):
        required = {
            "issue_id",
            "baseline_main",
            "canonical_status_sources",
            "deduplicated_docs",
            "retained_caveats",
            "removed_or_replaced_repetition_patterns",
            "non_goals",
            "validation_summary",
        }
        self.assertTrue(required.issubset(self.data))

    def test_artifact_records_expected_sources_and_docs(self):
        sources = {entry["path"] for entry in self.data["canonical_status_sources"]}
        self.assertIn("README.md", sources)
        self.assertIn("SECURITY.md", sources)

        docs = {entry["path"] for entry in self.data["deduplicated_docs"]}
        self.assertEqual(
            docs,
            {
                "docs/developer_adoption_strategy_intake.md",
                "docs/public_github_readiness_pack.md",
                "docs/ten_minute_quickstart.md",
            },
        )

    def test_artifact_records_non_goals(self):
        non_goals = set(self.data["non_goals"])
        for item in [
            "change_backend_src",
            "change_openapi",
            "change_migrations",
            "change_dependencies",
            "claim_production_saas_readiness",
            "claim_tenant_isolation_implemented",
            "claim_public_github_release_completed",
            "push_to_github",
            "publish_snapshot",
            "use_external_snapshot_tooling",
        ]:
            self.assertIn(item, non_goals)


class TestGL170CanonicalCaveats(unittest.TestCase):
    def setUp(self):
        self.readme = _normalized(README_PATH)
        self.security = _normalized(SECURITY_PATH)

    def test_readme_remains_canonical_status_source(self):
        for phrase in [
            "## status",
            "production saas readiness",
            "not claimed",
            "tenant/workspace isolation",
            "not implemented",
            "public github release",
            "not performed",
            "real customer data in examples",
            "real secrets in examples",
        ]:
            self.assertIn(phrase, self.readme)

    def test_full_caveats_are_not_removed_entirely(self):
        combined = self.readme + " " + self.security
        for phrase in [
            "production saas readiness is not claimed",
            "tenant isolation is not implemented",
            "public github release has not happened",
            "no real secrets",
            "no real customer data",
        ]:
            self.assertIn(phrase, combined)


class TestGL170DeduplicatedDocs(unittest.TestCase):
    def test_deduplicated_docs_point_to_readme(self):
        for path in DEDUPLICATED_DOCS:
            content = _normalized(path)
            self.assertIn("status and readiness caveats: see `readme.md`", content)

    def test_repeated_long_status_blocks_are_reduced(self):
        for path in DEDUPLICATED_DOCS:
            content = _normalized(path)
            self.assertLessEqual(
                content.count("production saas readiness is not claimed"),
                0,
                path.name,
            )
            self.assertLessEqual(
                content.count(
                    "the backend does not enforce tenant/workspace boundaries at the data, authorization, or audit layers"
                ),
                0,
                path.name,
            )

    def test_context_specific_caveats_remain(self):
        developer_adoption = _normalized(
            REPO_ROOT / "docs" / "developer_adoption_strategy_intake.md"
        )
        public_readiness = _normalized(
            REPO_ROOT / "docs" / "public_github_readiness_pack.md"
        )
        quickstart = _normalized(REPO_ROOT / "docs" / "ten_minute_quickstart.md")

        self.assertIn("gl-144 tenant/workspace design exists", developer_adoption)
        self.assertIn("public push requires explicit later approval", public_readiness)
        self.assertIn("no production deployment", quickstart)
        self.assertIn("no real customer data", quickstart)


class TestGL170SafetyClaims(unittest.TestCase):
    def setUp(self):
        paths = [README_PATH, SECURITY_PATH, ARTIFACT_PATH, *DEDUPLICATED_DOCS]
        self.combined = " ".join(_normalized(path) for path in paths)

    def test_no_production_saas_readiness_overclaiming(self):
        forbidden_patterns = [
            r"\bgrantlayer is production[- ]ready saas\b",
            r"\bgrantlayer is ready for production saas\b",
            r"\bproduction saas readiness is claimed\b",
            r"\bproduction saas readiness: claimed\b",
        ]
        for pattern in forbidden_patterns:
            self.assertIsNone(re.search(pattern, self.combined), pattern)

    def test_no_tenant_isolation_overclaiming(self):
        forbidden_patterns = [
            r"\bgrantlayer tenant isolation is implemented\b",
            r"\bgrantlayer tenant/workspace isolation is implemented\b",
            r"\btenant isolation: implemented\b",
            r"\btenant/workspace isolation: implemented\b",
        ]
        for pattern in forbidden_patterns:
            self.assertIsNone(re.search(pattern, self.combined), pattern)

    def test_no_github_visibility_or_release_completion_overclaiming(self):
        forbidden_patterns = [
            r"\bpublic github release completed\b",
            r"\bpublic github release is complete\b",
            r"\bgithub publication performed: yes\b",
            r"\brepository is public\b",
            r"\bvisibility changed to public\b",
        ]
        for pattern in forbidden_patterns:
            self.assertIsNone(re.search(pattern, self.combined), pattern)

    def test_no_external_snapshot_tool_references_introduced_in_changed_files(self):
        changed_paths = [ARTIFACT_PATH, *DEDUPLICATED_DOCS, Path(__file__)]
        for path in changed_paths:
            lowered = _read(path).lower()
            self.assertNotIn("paper" + "clip", lowered)


class TestGL170FirstOutputAndScope(unittest.TestCase):
    def test_first_output_docs_still_exist(self):
        for rel_path in [
            "examples/first_verifiable_output.py",
            "examples/first_verifiable_output.json",
            "docs/first_verifiable_output.md",
        ]:
            self.assertTrue((REPO_ROOT / rel_path).is_file(), rel_path)

    def test_gl168_first_output_path_is_discoverable_from_readme(self):
        readme = _normalized(README_PATH)
        for phrase in [
            "first verifiable output quickstart",
            "python3 examples/first_verifiable_output.py --output /tmp/grantlayer_first_output.json",
            "examples/first_verifiable_output.json",
            "docs/first_verifiable_output.md",
        ]:
            self.assertIn(phrase, readme)

    def test_changed_files_stay_within_allowed_scope(self):
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
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
            self.assertNotEqual(path, "docs/openapi.yaml")
            self.assertNotIn(path, {"requirements.txt", "requirements-dev.txt"})
            self.assertFalse(path.startswith("frontend/"), path)
            self.assertFalse(path.startswith("website/"), path)
            self.assertFalse(path.startswith("design/"), path)
