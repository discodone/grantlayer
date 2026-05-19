"""Tests for GL-061 Demo Runner / API Smoke Script.

Lightweight validation test proving the demo runner is:
- present as an executable script
- able to perform a successful dry-run
- coherent with the smoke manifest, GL-057 examples, and GL-058 walkthrough
- explicitly not claiming production readiness
- free of obvious secrets
"""

import json
import pathlib
import subprocess
import sys
import unittest


class TestGL061DemoRunnerApiSmoke(unittest.TestCase):
    """GL-061: Validate the demo runner / API smoke script."""

    REPO_ROOT = pathlib.Path(__file__).with_suffix("").parent.parent.parent
    SCRIPT_PATH = REPO_ROOT / "scripts" / "demo" / "gl061_api_smoke.py"
    MANIFEST_PATH = REPO_ROOT / "docs" / "examples" / "gl061" / "api_smoke_manifest.json"
    USAGE_DOC_PATH = REPO_ROOT / "docs" / "demo_runner_api_smoke.md"
    DOCS_DIR = REPO_ROOT / "docs"
    EXAMPLES_GL057 = DOCS_DIR / "examples" / "gl057"
    EXAMPLES_GL058 = DOCS_DIR / "examples" / "gl058"

    GL057_EXAMPLE_FILES = [
        "grant_request.json",
        "approval_result.json",
        "grant.json",
        "grant_execution.json",
        "evidence_item.json",
        "evidence_completeness.json",
        "compliance_gap_report.json",
        "policy_requirements_result.json",
        "decision_provenance_summary.json",
        "auditor_export.json",
        "compliance_readiness_summary.json",
        "minimal_flow_bundle.json",
    ]

    SECRET_PATTERNS = [
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "private_key",
        "privatekey",
        "bearer",
        "authorization",
    ]

    @classmethod
    def setUpClass(cls):
        cls.manifest_json = None
        cls.manifest_text = None
        if cls.MANIFEST_PATH.exists():
            cls.manifest_text = cls.MANIFEST_PATH.read_text(encoding="utf-8")
            cls.manifest_json = json.loads(cls.manifest_text)

    # ── 1. Script exists ───────────────────────────────────────────────
    def test_script_exists(self):
        self.assertTrue(
            self.SCRIPT_PATH.exists(),
            "scripts/demo/gl061_api_smoke.py must exist",
        )

    # ── 2. Manifest exists and parses ────────────────────────────────
    def test_manifest_exists_and_parses(self):
        self.assertTrue(
            self.MANIFEST_PATH.exists(),
            "docs/examples/gl061/api_smoke_manifest.json must exist",
        )
        self.assertIsNotNone(self.manifest_json, "Manifest must parse as valid JSON")
        self.assertIsInstance(self.manifest_json, dict)

    # ── 3. Usage doc exists ────────────────────────────────────────────
    def test_usage_doc_exists(self):
        self.assertTrue(
            self.USAGE_DOC_PATH.exists(),
            "docs/demo_runner_api_smoke.md must exist",
        )

    # ── 4. Script dry-run exits 0 ─────────────────────────────────────
    def test_script_dry_run_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(self.SCRIPT_PATH), "--dry-run"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Dry-run exited non-zero. stderr: {result.stderr}",
        )

    # ── 5. Script dry-run output mentions smoke ID and ordered steps ─
    def test_script_dry_run_mentions_smoke_id_and_steps(self):
        result = subprocess.run(
            [sys.executable, str(self.SCRIPT_PATH), "--dry-run"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        output = result.stdout
        self.assertIn("gl061-api-smoke", output, "Output must mention smokeId")
        self.assertIn("Ordered Smoke Plan", output, "Output must mention ordered smoke plan")
        for i in range(1, 12):
            self.assertIn(
                f"{i}.",
                output,
                f"Output must mention step {i}",
            )
        self.assertIn("dry-run validation passed", output, "Output must confirm dry-run passed")

    # ── 6. Manifest says networkRequiredByDefault is false ───────────
    def test_manifest_network_not_required_by_default(self):
        self.assertFalse(
            self.manifest_json.get("networkRequiredByDefault"),
            "networkRequiredByDefault must be false",
        )

    # ── 7. Manifest says productionReady is false ────────────────────
    def test_manifest_not_production_ready(self):
        self.assertFalse(
            self.manifest_json.get("productionReady"),
            "productionReady must be false",
        )

    # ── 8. Referenced GL-057 example files exist and parse ─────────────
    def test_gl057_example_files_exist_and_parse(self):
        missing = []
        for name in self.GL057_EXAMPLE_FILES:
            path = self.EXAMPLES_GL057 / name
            if not path.exists():
                missing.append(name)
                continue
            try:
                with path.open("r", encoding="utf-8") as f:
                    json.load(f)
            except json.JSONDecodeError as exc:
                missing.append(f"{name} (invalid JSON: {exc})")
        self.assertEqual(missing, [], f"Missing or invalid GL-057 examples: {missing}")

    # ── 9. GL-058 walkthrough JSON exists ────────────────────────────
    def test_gl058_walkthrough_json_exists(self):
        walkthrough_json = self.EXAMPLES_GL058 / "minimal_api_usage_walkthrough.json"
        self.assertTrue(
            walkthrough_json.exists(),
            "docs/examples/gl058/minimal_api_usage_walkthrough.json must exist",
        )

    # ── 10. Stable IDs match GL-057 conventions ────────────────────────
    def test_stable_ids_match_gl057_conventions(self):
        stable_ids = self.manifest_json.get("stableIds", {})
        expected = {
            "workflowId": "gl057-workflow-001",
            "subjectId": "gl057-subject-001",
            "grantRequestId": "gl057-request-001",
            "grantId": "gl057-grant-001",
            "executionId": "gl057-execution-001",
            "evidenceId": "gl057-evidence-001",
            "policyId": "gl057-policy-001",
            "auditorExportId": "gl057-auditor-export-001",
        }
        for key, value in expected.items():
            with self.subTest(id=key):
                self.assertEqual(
                    stable_ids.get(key),
                    value,
                    f"stableIds.{key} must be '{value}'",
                )

    # ── 11. No obvious secrets appear in manifest or referenced examples ─
    def test_no_obvious_secrets_in_manifest(self):
        text_lower = self.manifest_text.lower()
        for pattern in self.SECRET_PATTERNS:
            self.assertNotIn(
                pattern,
                text_lower,
                f"Manifest may contain secret-like pattern: {pattern}",
            )

    def test_no_obvious_secrets_in_gl057_examples(self):
        for name in self.GL057_EXAMPLE_FILES:
            path = self.EXAMPLES_GL057 / name
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8").lower()
            for pattern in self.SECRET_PATTERNS:
                self.assertNotIn(
                    pattern,
                    text,
                    f"GL-057 example {name} may contain secret-like pattern: {pattern}",
                )

    # ── 12. Usage doc mentions dry-run ───────────────────────────────
    def test_usage_doc_mentions_dry_run(self):
        content = self.USAGE_DOC_PATH.read_text(encoding="utf-8").lower()
        self.assertIn("dry-run", content, "Usage doc must mention dry-run")
        self.assertIn("--dry-run", content, "Usage doc must mention --dry-run flag")

    # ── 13. Usage doc documents non-goals ──────────────────────────────
    def test_usage_doc_documents_non_goals(self):
        content = self.USAGE_DOC_PATH.read_text(encoding="utf-8").lower()
        self.assertIn("non-goals", content, "Usage doc must contain a non-goals section")
        self.assertIn("production deployment", content, "Non-goals must mention production deployment")
        self.assertIn("production monitoring", content, "Non-goals must mention production monitoring")

    # ── Extra coherence checks ─────────────────────────────────────────
    def test_manifest_has_id_and_version(self):
        self.assertEqual(self.manifest_json.get("smokeId"), "gl061-api-smoke")
        self.assertEqual(self.manifest_json.get("smokeVersion"), "1.0")

    def test_manifest_has_steps(self):
        steps = self.manifest_json.get("steps", [])
        self.assertEqual(len(steps), 11, "Manifest must have exactly 11 steps")
        for i, step in enumerate(steps, start=1):
            with self.subTest(step=i):
                self.assertEqual(step.get("stepNumber"), i)
                self.assertTrue(step.get("name"), f"Step {i} must have a name")
                self.assertTrue(step.get("exampleFile"), f"Step {i} must have an exampleFile")

    def test_manifest_referenced_examples_match_steps(self):
        steps = self.manifest_json.get("steps", [])
        referenced = self.manifest_json.get("referencedExamples", [])
        ref_paths = {r.get("path") for r in referenced}
        for step in steps:
            example = step.get("exampleFile")
            if example:
                self.assertIn(
                    example,
                    ref_paths,
                    f"Step example {example} must be listed in referencedExamples",
                )

    def test_manifest_default_mode_is_dry_run(self):
        self.assertEqual(self.manifest_json.get("defaultMode"), "dry-run")

    def test_script_is_executable(self):
        self.assertTrue(
            self.SCRIPT_PATH.stat().st_mode & 0o111,
            "scripts/demo/gl061_api_smoke.py should be executable",
        )

    def test_script_dry_run_without_args(self):
        result = subprocess.run(
            [sys.executable, str(self.SCRIPT_PATH)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            "Script should exit 0 even without explicit --dry-run (default is dry-run)",
        )

    def test_script_dry_run_with_base_url(self):
        result = subprocess.run(
            [sys.executable, str(self.SCRIPT_PATH), "--dry-run", "--base-url", "http://localhost:8000"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("baseUrl", result.stdout, "Output must mention baseUrl when provided")

    def test_manifest_has_verification_commands(self):
        commands = self.manifest_json.get("verificationCommands", [])
        self.assertTrue(len(commands) > 0, "verificationCommands must not be empty")
        self.assertIn(
            "python3 scripts/demo/gl061_api_smoke.py --dry-run",
            commands,
        )

    def test_manifest_has_non_goals(self):
        non_goals = self.manifest_json.get("nonGoals", [])
        self.assertTrue(len(non_goals) > 0, "nonGoals must not be empty")
        text = " ".join(non_goals).lower()
        self.assertIn("oauth", text, "nonGoals must mention OAuth")
        self.assertIn("jwt", text, "nonGoals must mention JWT")
        self.assertIn("blockchain", text, "nonGoals must mention blockchain")
        self.assertIn("sdk", text, "nonGoals must mention SDK")

    def test_manifest_has_related_artifacts(self):
        artifacts = self.manifest_json.get("relatedArtifacts", [])
        self.assertTrue(len(artifacts) > 0, "relatedArtifacts must not be empty")
        artifact_ids = {a.get("artifactId") for a in artifacts}
        self.assertIn("gl057-quickstart-examples", artifact_ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)
