"""GL-188 first output verify helper regression tests."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify-first-output.sh"
REFERENCE_PATH = REPO_ROOT / "examples" / "first_verifiable_output.json"
DOC_PATH = REPO_ROOT / "docs" / "first_output_verify_helper.md"
ARTIFACT_PATH = REPO_ROOT / "docs" / "examples" / "gl188" / "first_output_verify_helper.json"
EXAMPLE_SCRIPT_PATH = REPO_ROOT / "examples" / "first_verifiable_output.py"
DEFAULT_OUTPUT_PATH = Path("/tmp/grantlayer_first_output_verify.json")
CUSTOM_OUTPUT_PATH = Path("/tmp/grantlayer_first_output_verify_custom.json")

ALLOWED_CHANGED_FILES = {
    "backend/tests/test_gl188_first_output_verify_helper.py",
    "docs/examples/gl188/first_output_verify_helper.json",
    "docs/first_output_verify_helper.md",
    "scripts/verify-first-output.sh",
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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


def _run_script(output_path: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [str(SCRIPT_PATH)]
    if output_path is not None:
        command.append(str(output_path))
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class TestGL188ScriptAndOutputs(unittest.TestCase):
    def setUp(self):
        self.reference_before = _read_text(REFERENCE_PATH)
        for path in [DEFAULT_OUTPUT_PATH, CUSTOM_OUTPUT_PATH]:
            if path.exists():
                path.unlink()

    def tearDown(self):
        for path in [DEFAULT_OUTPUT_PATH, CUSTOM_OUTPUT_PATH]:
            if path.exists():
                path.unlink()

    def test_script_exists_and_is_executable(self):
        self.assertTrue(SCRIPT_PATH.is_file(), "helper script is missing")
        self.assertTrue(os.access(SCRIPT_PATH, os.X_OK), "helper script is not executable")

    def test_script_uses_safe_bash_settings_and_expected_paths(self):
        content = _read_text(SCRIPT_PATH)
        self.assertIn("set -euo pipefail", content)
        self.assertIn("examples/first_verifiable_output.py", content)
        self.assertIn("examples/first_verifiable_output.json", content)
        self.assertIn("/tmp/grantlayer_first_output_verify.json", content)

    def test_default_output_path_verifies_exact_match(self):
        result = _run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(DEFAULT_OUTPUT_PATH.is_file(), "default output file was not created")
        self.assertEqual(_read_text(DEFAULT_OUTPUT_PATH), self.reference_before)
        self.assertEqual(_read_text(REFERENCE_PATH), self.reference_before)
        self.assertIn("MATCH", result.stdout)
        self.assertIn("Running first verifiable output generator", result.stdout)
        self.assertIn("Comparing generated output with committed reference", result.stdout)

    def test_custom_output_path_verifies_exact_match(self):
        result = _run_script(CUSTOM_OUTPUT_PATH)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(CUSTOM_OUTPUT_PATH.is_file(), "custom output file was not created")
        self.assertEqual(_read_text(CUSTOM_OUTPUT_PATH), self.reference_before)
        self.assertEqual(_read_text(REFERENCE_PATH), self.reference_before)
        self.assertIn("MATCH", result.stdout)
        self.assertIn(str(CUSTOM_OUTPUT_PATH), result.stdout)

    def test_generator_script_reference_is_unmodified(self):
        _ = _run_script()
        self.assertEqual(_read_text(REFERENCE_PATH), self.reference_before)


class TestGL188DocsAndArtifact(unittest.TestCase):
    def test_docs_and_artifact_exist(self):
        self.assertTrue(DOC_PATH.is_file(), "documentation file is missing")
        self.assertTrue(ARTIFACT_PATH.is_file(), "JSON artifact is missing")

    def test_docs_include_required_topics(self):
        content = _read_text(DOC_PATH).lower()
        for phrase in [
            "gl-188",
            "scripts/verify-first-output.sh",
            "examples/first_verifiable_output.json",
            "no network",
            "no backend",
            "no secrets",
            "no real customer data",
            "what it verifies",
            "what it does not verify",
            "troubleshooting",
            "next recommended issue",
        ]:
            self.assertIn(phrase, content)

    def test_json_artifact_is_valid_and_allowed(self):
        data = json.loads(_read_text(ARTIFACT_PATH))
        self.assertEqual(data["issue_id"], "GL-188")
        self.assertEqual(data["result"], "first_output_verify_helper_complete")
        self.assertEqual(data["script_path"], "scripts/verify-first-output.sh")
        self.assertEqual(data["reference_artifact"], "examples/first_verifiable_output.json")
        self.assertEqual(data["default_output_path"], "/tmp/grantlayer_first_output_verify.json")
        self.assertEqual(
            data["next_recommended_step"],
            "GL-189 Second Runnable Example / Grant Lifecycle Evidence Bundle",
        )
        self.assertTrue(data["safety_properties"]["no_network_required"])
        self.assertTrue(data["safety_properties"]["no_backend_required"])
        self.assertTrue(data["safety_properties"]["no_secrets_required"])
        self.assertTrue(data["safety_properties"]["no_customer_data_required"])
        self.assertTrue(data["safety_properties"]["writes_only_to_requested_or_temp_output"])
        self.assertTrue(data["safety_properties"]["does_not_modify_reference_artifact"])
        self.assertEqual(
            set(data["changed_files"]),
            ALLOWED_CHANGED_FILES,
        )
        self.assertEqual(data["findings"], [])
        self.assertEqual(
            data["finding_counts_by_severity"],
            {"critical": 0, "high": 0, "medium": 0, "low": 0},
        )
        self.assertIn(data["result"], {
            "first_output_verify_helper_complete",
            "blocked_unexpected_scope",
            "blocked_determinism_failure",
            "blocked_other_with_reason",
        })


class TestGL188ScopeAndSafety(unittest.TestCase):
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
        content = "\n".join(
            _read_text(path)
            for path in [SCRIPT_PATH, DOC_PATH, ARTIFACT_PATH]
        ).lower()
        for phrase in [
            "paperclip",
            "github push",
            "force push",
            "backend/src/",
            "openapi",
            "migration",
            "production saas readiness",
        ]:
            self.assertNotIn(phrase, content)


if __name__ == "__main__":
    unittest.main()
