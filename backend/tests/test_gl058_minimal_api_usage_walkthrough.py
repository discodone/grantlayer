"""Tests for GL-058 Minimal API Usage Walkthrough.

Lightweight validation test proving the walkthrough is:
- present as a document and a machine-readable JSON file
- coherent and aligned with GL-057 quickstart examples
- aligned with the OpenAPI contract where paths are declared
- free of obvious secrets
"""

import json
import pathlib
import unittest


try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


class TestGL058MinimalAPIUsageWalkthrough(unittest.TestCase):
    """GL-058: Validate the minimal API usage walkthrough."""

    REPO_ROOT = pathlib.Path(__file__).with_suffix("").parent.parent.parent
    DOCS_DIR = REPO_ROOT / "docs"
    EXAMPLE_DIR_GL057 = DOCS_DIR / "examples" / "gl057"
    EXAMPLE_DIR_GL058 = DOCS_DIR / "examples" / "gl058"

    STABLE_IDS = {
        "workflowId": "gl057-workflow-001",
        "subjectId": "gl057-subject-001",
        "grantRequestId": "gl057-request-001",
        "grantId": "gl057-grant-001",
        "executionId": "gl057-execution-001",
        "evidenceId": "gl057-evidence-001",
        "policyId": "gl057-policy-001",
        "auditorExportId": "gl057-auditor-export-001",
    }

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
        cls.walkthrough_json_path = cls.EXAMPLE_DIR_GL058 / "minimal_api_usage_walkthrough.json"
        cls.walkthrough_doc_path = cls.DOCS_DIR / "minimal_api_usage_walkthrough.md"
        cls.openapi_path = cls.DOCS_DIR / "openapi.yaml"
        cls.walkthrough = None
        cls.walkthrough_text = None
        if cls.walkthrough_json_path.exists():
            cls.walkthrough_text = cls.walkthrough_json_path.read_text(encoding="utf-8")
            cls.walkthrough = json.loads(cls.walkthrough_json_path.read_text(encoding="utf-8"))

    # ── 1. Walkthrough doc exists ────────────────────────────────────
    def test_walkthrough_doc_exists(self):
        self.assertTrue(
            self.walkthrough_doc_path.exists(),
            "docs/minimal_api_usage_walkthrough.md must exist",
        )

    # ── 2. Walkthrough JSON exists and parses ────────────────────────
    def test_walkthrough_json_exists_and_parses(self):
        self.assertTrue(
            self.walkthrough_json_path.exists(),
            "docs/examples/gl058/minimal_api_usage_walkthrough.json must exist",
        )
        self.assertIsNotNone(self.walkthrough, "Walkthrough JSON must parse as valid JSON")
        self.assertIsInstance(self.walkthrough, dict)

    # ── 3. GL-057 example directory exists ───────────────────────────
    def test_gl057_example_directory_exists(self):
        self.assertTrue(
            self.EXAMPLE_DIR_GL057.exists(),
            "docs/examples/gl057/ must exist",
        )

    # ── 4. All GL-057 files referenced by the walkthrough JSON exist ─
    def test_all_referenced_gl057_files_exist(self):
        steps = self.walkthrough.get("steps", [])
        missing = []
        for step in steps:
            example_file = step.get("exampleFile", "")
            if example_file.startswith("docs/examples/gl057/"):
                path = self.REPO_ROOT / example_file
                if not path.exists():
                    missing.append(example_file)
        self.assertEqual(missing, [], f"Missing referenced GL-057 example files: {missing}")

    # ── 5. Stable IDs match GL-057 conventions ───────────────────────
    def test_stable_ids_match_gl057_conventions(self):
        stable = self.walkthrough.get("stableIds", {})
        for key, expected in self.STABLE_IDS.items():
            with self.subTest(id=key):
                self.assertEqual(
                    stable.get(key),
                    expected,
                    f"stableIds.{key} must match GL-057 convention",
                )

    # ── 6. Walkthrough steps are ordered and non-empty ───────────────
    def test_steps_are_ordered_and_non_empty(self):
        steps = self.walkthrough.get("steps", [])
        self.assertTrue(len(steps) > 0, "steps array must not be empty")
        for i, step in enumerate(steps, start=1):
            with self.subTest(step=i):
                self.assertEqual(
                    step.get("stepNumber"),
                    i,
                    "stepNumber must be sequential starting at 1",
                )

    # ── 7. Each step has productCoreArea and exampleFile ─────────────
    def test_each_step_has_required_fields(self):
        steps = self.walkthrough.get("steps", [])
        for step in steps:
            step_num = step.get("stepNumber", "?")
            with self.subTest(step=step_num):
                self.assertTrue(
                    step.get("productCoreArea"),
                    f"Step {step_num} must have productCoreArea",
                )
                self.assertTrue(
                    step.get("exampleFile"),
                    f"Step {step_num} must have exampleFile",
                )

    # ── 8. Declared OpenAPI paths exist in docs/openapi.yaml ─────────
    def test_declared_openapi_paths_exist(self):
        self.assertTrue(
            self.openapi_path.exists(),
            "docs/openapi.yaml must exist to validate declared paths",
        )
        text = self.openapi_path.read_text(encoding="utf-8")
        steps = self.walkthrough.get("steps", [])
        for step in steps:
            path = step.get("openapiPath")
            if path:
                step_num = step.get("stepNumber", "?")
                with self.subTest(step=step_num, path=path):
                    needle = f"{path}:"
                    self.assertIn(
                        needle,
                        text,
                        f"Declared OpenAPI path {path} not found in openapi.yaml",
                    )

    # ── 9. No obvious secrets appear in walkthrough JSON or referenced examples ──
    def test_no_obvious_secrets_in_walkthrough_json(self):
        text_lower = self.walkthrough_json_path.read_text(encoding="utf-8").lower()
        for pattern in self.SECRET_PATTERNS:
            self.assertNotIn(
                pattern,
                text_lower,
                f"Walkthrough JSON may contain secret-like pattern: {pattern}",
            )

    def test_no_obvious_secrets_in_referenced_examples(self):
        steps = self.walkthrough.get("steps", [])
        for step in steps:
            example_file = step.get("exampleFile", "")
            if example_file.startswith("docs/examples/gl057/"):
                path = self.REPO_ROOT / example_file
                if path.exists():
                    text_lower = path.read_text(encoding="utf-8").lower()
                    for pattern in self.SECRET_PATTERNS:
                        with self.subTest(file=example_file, pattern=pattern):
                            self.assertNotIn(
                                pattern,
                                text_lower,
                                f"Example {example_file} may contain secret-like pattern: {pattern}",
                            )

    # ── 10. Walkthrough doc references GL-057 quickstart and Integration-Ready artifacts ─
    def test_walkthrough_doc_references_gl057_quickstart(self):
        content = self.walkthrough_doc_path.read_text(encoding="utf-8")
        self.assertIn("integrator_quickstart.md", content)
        self.assertIn("gl057", content.lower())

    def test_walkthrough_doc_references_integration_artifacts(self):
        content = self.walkthrough_doc_path.read_text(encoding="utf-8")
        self.assertIn("integration_guide.md", content)
        self.assertIn("demo_scenario.md", content)
        self.assertIn("integration_ready_release_candidate.md", content)
        self.assertIn("openapi.yaml", content)
        self.assertIn("test_gl052_product_core_e2e_flow.py", content)
        self.assertIn("test_gl055_integration_contract_readiness.py", content)

    # ── 11. Walkthrough doc documents non-goals ──────────────────────
    def test_walkthrough_doc_documents_non_goals(self):
        content = self.walkthrough_doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("non-goals", content, "Walkthrough doc must document non-goals")
        # Representative items from the non-goals list
        self.assertIn("oauth", content, "Walkthrough doc must mention OAuth as a non-goal")
        self.assertIn("jwt", content, "Walkthrough doc must mention JWT as a non-goal")
        self.assertIn("sso", content, "Walkthrough doc must mention SSO as a non-goal")
        self.assertIn("blockchain", content, "Walkthrough doc must mention blockchain as a non-goal")
        self.assertIn("sdk", content, "Walkthrough doc must mention SDKs as a non-goal")

    # ── Extra coherence checks ───────────────────────────────────────
    def test_walkthrough_json_has_walkthrough_id_and_version(self):
        self.assertIsNotNone(self.walkthrough.get("walkthroughId"))
        self.assertIsNotNone(self.walkthrough.get("walkthroughVersion"))

    def test_walkthrough_json_has_related_artifacts(self):
        artifacts = self.walkthrough.get("relatedArtifacts", [])
        self.assertTrue(len(artifacts) > 0, "relatedArtifacts must not be empty")
        artifact_ids = {a.get("artifactId") for a in artifacts}
        self.assertIn("gl057-quickstart-examples", artifact_ids)

    def test_walkthrough_json_has_non_goals(self):
        non_goals = self.walkthrough.get("nonGoals", [])
        self.assertTrue(len(non_goals) > 0, "nonGoals must not be empty")


if __name__ == "__main__":
    unittest.main(verbosity=2)
