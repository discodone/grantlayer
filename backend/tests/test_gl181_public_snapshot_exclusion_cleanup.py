"""GL-181: Public Snapshot Exclusion Cleanup."""

import json
import os
import re
import subprocess
import tempfile
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GL181_BRANCH = "gl-181-public-snapshot-exclusion-cleanup"
SCRIPT_PATH = os.path.join(REPO_ROOT, "scripts", "build-clean-public-snapshot.sh")
REPORT_PATH = os.path.join(REPO_ROOT, "docs", "public_snapshot_exclusion_cleanup.md")
JSON_PATH = os.path.join(
    REPO_ROOT, "docs", "examples", "gl181", "public_snapshot_exclusion_cleanup.json"
)

ALLOWED_RESULT_VALUES = {
    "public_snapshot_exclusion_cleanup_complete",
    "blocked_missing_snapshot_workflow",
    "blocked_unexpected_snapshot_diff",
    "blocked_private_data_or_secret_safety",
    "blocked_other_with_reason",
}

ALLOWED_CHANGED_FILES = {
    "scripts/build-clean-public-snapshot.sh",
    "docs/public_snapshot_exclusion_cleanup.md",
    "docs/examples/gl181/public_snapshot_exclusion_cleanup.json",
    "backend/tests/test_gl181_public_snapshot_exclusion_cleanup.py",
}

TARGET_EXCLUSIONS = [
    "docs/public_repo_smoke_verification.md",
    "docs/examples/gl177/public_repo_smoke_verification.json",
    "docs/readme_security_post_public_state.md",
    "docs/examples/gl178/readme_security_post_public_state.json",
    "docs/public_snapshot_correction_push_gl179.md",
    "docs/examples/gl179/public_snapshot_correction_push_gl179.json",
    "docs/public_docs_smoke_verification.md",
    "docs/examples/gl180/public_docs_smoke_verification.json",
]

PRESERVED_PUBLIC_FILES = [
    "README.md",
    "SECURITY.md",
    "LICENSE",
    "AGENTS.md",
    "llms.txt",
    "llms-full.txt",
    "docs/first_verifiable_output.md",
    "examples/first_verifiable_output.py",
    "examples/first_verifiable_output.json",
]


def _git_diff_files():
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    if branch.returncode == 0 and branch.stdout.strip() != GL181_BRANCH:
        return list(ALLOWED_CHANGED_FILES)
    result = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        return []
    files = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        # Status lines are of the form "XY path" or "?? path".
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            files.append(parts[1])
    return files


def _run_snapshot_build(output_dir):
    return subprocess.run(
        ["bash", SCRIPT_PATH, "--allow-dirty", "--output", output_dir],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )


class TestGL181FilesExist(unittest.TestCase):
    def test_script_exists(self):
        self.assertTrue(os.path.isfile(SCRIPT_PATH), f"Missing script: {SCRIPT_PATH}")

    def test_report_exists(self):
        self.assertTrue(os.path.isfile(REPORT_PATH), f"Missing report: {REPORT_PATH}")

    def test_json_exists(self):
        self.assertTrue(os.path.isfile(JSON_PATH), f"Missing JSON: {JSON_PATH}")


class TestGL181ScriptExclusions(unittest.TestCase):
    def test_explicit_target_exclusions_present(self):
        with open(SCRIPT_PATH, encoding="utf-8") as fh:
            content = fh.read()
        for path in TARGET_EXCLUSIONS:
            self.assertIn(path, content, f"Expected exclusion missing from script: {path}")

    def test_preserved_public_files_not_excluded(self):
        with open(SCRIPT_PATH, encoding="utf-8") as fh:
            content = fh.read()
        for path in PRESERVED_PUBLIC_FILES:
            if path == "README.md" or path == "SECURITY.md":
                # These are clearly preserved by the inclusion logic, not excluded explicitly.
                self.assertNotIn(f'"{path}"', content.split("PUBLIC_EXPORT_EXCLUDE", 1)[-1])
            else:
                self.assertNotIn(path, TARGET_EXCLUSIONS, f"Public file should not be excluded: {path}")


class TestGL181ArtifactJSON(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(JSON_PATH, encoding="utf-8") as fh:
            cls.data = json.load(fh)

    def test_valid_json(self):
        self.assertIsInstance(self.data, dict)

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-181")

    def test_result_valid(self):
        self.assertIn(self.data.get("result"), ALLOWED_RESULT_VALUES)

    def test_exclusions_added_present(self):
        exclusions = self.data.get("exclusions_added")
        self.assertIsInstance(exclusions, list)
        self.assertGreater(len(exclusions), 0)
        for path in TARGET_EXCLUSIONS:
            self.assertIn(path, exclusions)

    def test_public_files_preserved_present(self):
        preserved = self.data.get("public_files_preserved")
        self.assertIsInstance(preserved, list)
        for path in PRESERVED_PUBLIC_FILES:
            self.assertIn(path, preserved)

    def test_private_data_secret_safety_exists(self):
        safety = self.data.get("private_data_secret_safety")
        self.assertIsInstance(safety, dict)

    def test_private_data_secret_safety_flags(self):
        safety = self.data.get("private_data_secret_safety", {})
        self.assertFalse(safety.get("private_data_found"))
        self.assertFalse(safety.get("secret_material_found"))
        self.assertFalse(safety.get("internal_infrastructure_found"))
        self.assertFalse(safety.get("blockers_found"))
        if safety.get("blockers_found"):
            self.assertEqual(
                self.data.get("result"),
                "blocked_private_data_or_secret_safety",
            )

    def test_findings_structure(self):
        findings = self.data.get("findings", [])
        self.assertIsInstance(findings, list)
        for finding in findings:
            for field in ("id", "severity", "status", "recommendation", "blocking"):
                self.assertIn(field, finding)

    def test_finding_counts_match(self):
        findings = self.data.get("findings", [])
        counts = self.data.get("finding_counts_by_severity", {})
        actual_counts = {}
        for finding in findings:
            sev = finding.get("severity", "unknown")
            actual_counts[sev] = actual_counts.get(sev, 0) + 1
        for sev, count in actual_counts.items():
            self.assertEqual(counts.get(sev), count)
        self.assertEqual(counts.get("total"), len(findings))

    def test_non_goals_confirm_no_push_or_visibility_change(self):
        non_goals = " ".join(self.data.get("non_goals", [])).lower()
        self.assertIn("no github push", non_goals)
        self.assertIn("no visibility change", non_goals)
        self.assertIn("internal repo was not pushed directly to github", non_goals)

    def test_snapshot_build_verification_block_exists(self):
        verification = self.data.get("verification")
        self.assertIsInstance(verification, dict)
        self.assertIn("snapshot_build_run", verification)
        self.assertIn("snapshot_output_path", verification)
        self.assertIn("excluded_files_absent", verification)
        self.assertIn("required_public_files_present", verification)
        self.assertIn("readme_security_state_preserved", verification)

    def test_result_blocked_only_on_safety_blockers(self):
        safety = self.data.get("private_data_secret_safety", {})
        if safety.get("blockers_found"):
            self.assertEqual(
                self.data.get("result"),
                "blocked_private_data_or_secret_safety",
            )


class TestGL181SnapshotBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output_dir = tempfile.mkdtemp(prefix="gl181-public-snapshot-")
        cls.result = _run_snapshot_build(cls.output_dir)

    def test_snapshot_script_executable(self):
        self.assertEqual(self.result.returncode, 0, self.result.stdout + self.result.stderr)

    def test_excluded_files_absent(self):
        for path in TARGET_EXCLUSIONS:
            self.assertFalse(
                os.path.exists(os.path.join(self.output_dir, path)),
                f"Excluded file should be absent from snapshot: {path}",
            )

    def test_required_public_files_present(self):
        for path in PRESERVED_PUBLIC_FILES:
            self.assertTrue(
                os.path.exists(os.path.join(self.output_dir, path)),
                f"Required public file missing from snapshot: {path}",
            )

    def test_readme_security_state_preserved(self):
        readme_path = os.path.join(self.output_dir, "README.md")
        security_path = os.path.join(self.output_dir, "SECURITY.md")
        with open(readme_path, encoding="utf-8") as fh:
            readme = fh.read()
        with open(security_path, encoding="utf-8") as fh:
            security = fh.read()

        self.assertIn("Developer Preview", readme)
        self.assertIn("GitHub Security Advisories", security)
        self.assertNotIn("visibility pending GL-175", readme.lower())
        self.assertNotIn("visibility pending GL-175", security.lower())
        self.assertNotIn("public_github_readiness_pack.md", readme)

    def test_no_private_data_or_secret_blocker_introduced(self):
        combined = self.result.stdout + self.result.stderr
        self.assertNotIn("Traceback", combined)
        self.assertNotIn("TypeError", combined)
        self.assertNotIn("AssertionError", combined)


class TestGL181ScopeGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.diff_files = _git_diff_files()

    def test_changed_files_within_allowed_scope(self):
        self.assertEqual(set(self.diff_files), ALLOWED_CHANGED_FILES)

    def test_no_backend_src_changes(self):
        for path in self.diff_files:
            self.assertFalse(path.startswith("backend/src/"))

    def test_no_openapi_changes(self):
        for path in self.diff_files:
            self.assertNotEqual(path, "docs/openapi.yaml")

    def test_no_migration_changes(self):
        for path in self.diff_files:
            self.assertFalse(path.startswith("backend/src/migrations/"))

    def test_no_dependency_manifest_changes(self):
        for path in self.diff_files:
            self.assertNotIn(path, {"requirements.txt", "requirements-dev.txt"})

    def test_no_frontend_or_website_changes(self):
        for path in self.diff_files:
            self.assertFalse(path.startswith("frontend/"))
            self.assertFalse(path.startswith("website/"))
            self.assertFalse(path.startswith("design/"))

    def test_no_github_workflow_changes(self):
        for path in self.diff_files:
            self.assertFalse(path.startswith(".github/workflows/"))
