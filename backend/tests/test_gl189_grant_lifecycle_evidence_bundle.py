"""GL-189 grant lifecycle evidence bundle regression tests."""

import json
import subprocess
import sys
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_SCRIPT_PATH = REPO_ROOT / "examples" / "grant_lifecycle_evidence_bundle.py"
REFERENCE_PATH = REPO_ROOT / "examples" / "grant_lifecycle_evidence_bundle.json"
DOC_PATH = REPO_ROOT / "docs" / "grant_lifecycle_evidence_bundle.md"
REPORT_PATH = (
    REPO_ROOT / "docs" / "examples" / "gl189" / "grant_lifecycle_evidence_bundle_report.json"
)
DEFAULT_OUTPUT_PATH = Path("/tmp/grantlayer_grant_lifecycle_evidence_bundle.json")
CUSTOM_OUTPUT_PATH = Path("/tmp/grantlayer_grant_lifecycle_evidence_bundle_custom.json")

ALLOWED_CHANGED_FILES = {
    "backend/tests/test_gl189_grant_lifecycle_evidence_bundle.py",
    "docs/examples/gl189/grant_lifecycle_evidence_bundle_report.json",
    "docs/grant_lifecycle_evidence_bundle.md",
    "examples/grant_lifecycle_evidence_bundle.json",
    "examples/grant_lifecycle_evidence_bundle.py",
}
GL189_BRANCH = "gl-189-grant-lifecycle-evidence-bundle"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path):
    return json.loads(_read_text(path))


def _run_script(output_path: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(EXAMPLE_SCRIPT_PATH)]
    if output_path is not None:
        command.extend(["--output", str(output_path)])
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _canonical_json(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_json(data):
    import hashlib

    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


def _changed_files():
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.strip()
    if branch != GL189_BRANCH:
        return list(ALLOWED_CHANGED_FILES)
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout
    changed = []
    for entry in status.split("\0"):
        if entry.strip():
            changed.append(entry[3:].strip() if len(entry) > 3 else entry.strip())
    if changed:
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


class TestGL189FilesAndArtifacts(unittest.TestCase):
    def test_required_files_exist(self):
        for path in [EXAMPLE_SCRIPT_PATH, REFERENCE_PATH, DOC_PATH, REPORT_PATH]:
            self.assertTrue(path.is_file(), f"Expected file to exist: {path}")

    def test_report_is_valid_json_and_allowed(self):
        report = _read_json(REPORT_PATH)
        self.assertEqual(report["issue_id"], "GL-189")
        self.assertEqual(report["result"], "second_runnable_example_complete")
        self.assertEqual(report["reference_artifact"], "examples/grant_lifecycle_evidence_bundle.json")
        self.assertEqual(report["docs_path"], "docs/grant_lifecycle_evidence_bundle.md")
        self.assertEqual(report["default_output_path"], "/tmp/grantlayer_grant_lifecycle_evidence_bundle.json")
        self.assertEqual(set(report["changed_files"]), ALLOWED_CHANGED_FILES)
        self.assertEqual(report["findings"], [])
        self.assertEqual(
            report["finding_counts_by_severity"],
            {"critical": 0, "high": 0, "medium": 0, "low": 0},
        )
        self.assertTrue(report["safety_properties"]["no_network_required"])
        self.assertTrue(report["safety_properties"]["no_backend_required"])
        self.assertTrue(report["safety_properties"]["no_secrets_required"])
        self.assertTrue(report["safety_properties"]["no_customer_data_required"])
        self.assertTrue(report["safety_properties"]["synthetic_demo_data_only"])
        self.assertTrue(report["safety_properties"]["no_production_saas_claim"])
        self.assertTrue(report["safety_properties"]["tenant_isolation_not_claimed"])
        self.assertTrue(report["safety_properties"]["writes_only_to_requested_or_temp_output"])
        self.assertTrue(report["safety_properties"]["does_not_modify_reference_artifact"])
        self.assertIn(
            report["result"],
            {
                "second_runnable_example_complete",
                "blocked_determinism_failure",
                "blocked_unexpected_scope",
                "blocked_private_data_or_secret_safety",
                "blocked_other_with_reason",
            },
        )


class TestGL189ScriptBehavior(unittest.TestCase):
    def setUp(self):
        self.reference_before = _read_text(REFERENCE_PATH)
        for path in [DEFAULT_OUTPUT_PATH, CUSTOM_OUTPUT_PATH]:
            if path.exists():
                path.unlink()

    def tearDown(self):
        for path in [DEFAULT_OUTPUT_PATH, CUSTOM_OUTPUT_PATH]:
            if path.exists():
                path.unlink()

    def test_script_uses_only_standard_library_and_deterministic_inputs(self):
        content = _read_text(EXAMPLE_SCRIPT_PATH).lower()
        for phrase in [
            "import requests",
            "urllib3",
            "random.",
            "secrets.",
            "uuid4",
            "time.time",
            "datetime.now",
            "datetime.utcnow",
            "os.environ",
        ]:
            self.assertNotIn(phrase, content)
        for phrase in [
            "argparse",
            "hashlib",
            "json",
            "pathlib",
        ]:
            self.assertIn(phrase, content)

    def test_default_output_path_matches_reference(self):
        result = _run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(DEFAULT_OUTPUT_PATH.is_file(), "default output file was not created")
        self.assertEqual(_read_text(DEFAULT_OUTPUT_PATH), self.reference_before)
        self.assertEqual(_read_text(REFERENCE_PATH), self.reference_before)

    def test_custom_output_path_matches_reference(self):
        result = _run_script(CUSTOM_OUTPUT_PATH)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(CUSTOM_OUTPUT_PATH.is_file(), "custom output file was not created")
        self.assertEqual(_read_text(CUSTOM_OUTPUT_PATH), self.reference_before)
        self.assertEqual(_read_text(REFERENCE_PATH), self.reference_before)

    def test_repeat_runs_are_identical(self):
        first = _run_script(DEFAULT_OUTPUT_PATH)
        first_output = _read_text(DEFAULT_OUTPUT_PATH)
        second = _run_script(DEFAULT_OUTPUT_PATH)
        second_output = _read_text(DEFAULT_OUTPUT_PATH)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first_output, self.reference_before)
        self.assertEqual(second_output, self.reference_before)
        self.assertEqual(first_output, second_output)


class TestGL189OutputStructure(unittest.TestCase):
    def setUp(self):
        self.reference_before = _read_text(REFERENCE_PATH)
        self.output_path = DEFAULT_OUTPUT_PATH
        if self.output_path.exists():
            self.output_path.unlink()
        result = _run_script(self.output_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.data = _read_json(self.output_path)

    def tearDown(self):
        if self.output_path.exists():
            self.output_path.unlink()
        if CUSTOM_OUTPUT_PATH.exists():
            CUSTOM_OUTPUT_PATH.unlink()

    def test_top_level_fields_exist(self):
        for key in [
            "record_type",
            "record_version",
            "generated_at",
            "example_id",
            "grant_request",
            "lifecycle_events",
            "evidence_items",
            "audit_chain",
            "evidence_bundle",
            "bundle_sha256",
            "verification_summary",
            "non_goals",
        ]:
            self.assertIn(key, self.data)

    def test_lifecycle_evidence_and_audit_counts(self):
        self.assertGreaterEqual(len(self.data["lifecycle_events"]), 5)
        self.assertGreaterEqual(len(self.data["evidence_items"]), 3)
        self.assertEqual(len(self.data["audit_chain"]), len(self.data["lifecycle_events"]))

    def test_audit_chain_links_and_final_hash(self):
        audit_chain = self.data["audit_chain"]
        self.assertIsNone(audit_chain[0]["previous_event_hash"])
        for previous, current in zip(audit_chain, audit_chain[1:]):
            self.assertEqual(current["previous_event_hash"], previous["event_hash"])
        self.assertEqual(self.data["evidence_bundle"]["final_event_hash"], audit_chain[-1]["event_hash"])

    def test_bundle_hash_matches_canonical_summary(self):
        self.assertEqual(self.data["bundle_sha256"], _sha256_json(self.data["evidence_bundle"]))
        self.assertEqual(self.data["evidence_bundle"]["bundle_hash_algorithm"], "sha256")

    def test_verification_summary_is_positive(self):
        summary = self.data["verification_summary"]
        self.assertTrue(summary["deterministic_output"])
        self.assertTrue(summary["no_network_required"])
        self.assertTrue(summary["no_backend_required"])
        self.assertTrue(summary["no_secrets_required"])
        self.assertTrue(summary["no_customer_data_required"])
        self.assertEqual(summary["reference_artifact"], "examples/grant_lifecycle_evidence_bundle.json")

    def test_no_private_data_or_forbidden_paths(self):
        forbidden_substrings = [
            "bearer ",
            "token ",
            "password ",
            "private url",
            "internal hostname",
            "/home/",
            "localhost",
            "127.0.0.1",
            "customer_name",
            "https://",
            "http://",
        ]

        def walk(value):
            if isinstance(value, str):
                yield value.lower()
            elif isinstance(value, list):
                for item in value:
                    yield from walk(item)
            elif isinstance(value, dict):
                for item in value.values():
                    yield from walk(item)

        all_values = list(walk(self.data))
        for phrase in forbidden_substrings:
            self.assertFalse(any(phrase in value for value in all_values), phrase)

    def test_reference_artifact_is_unchanged_by_generation(self):
        self.assertEqual(_read_text(REFERENCE_PATH), self.reference_before)

    def test_no_forbidden_repo_scope_changes(self):
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


if __name__ == "__main__":
    unittest.main()
