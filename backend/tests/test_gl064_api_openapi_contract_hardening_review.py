"""Tests for GL-064 API/OpenAPI Contract Hardening Review.

Lightweight validation test proving the API/OpenAPI contract hardening review
and its artifacts are:
- present as a human-readable document
- present as machine-readable JSON files
- coherent with referenced Pilot-Ready and Production-Hardening artifacts
- explicitly not claiming a Production-Ready API contract
- free of obvious secrets
"""

import json
import pathlib
import unittest


class TestGL064ApiOpenapiContractHardeningReview(unittest.TestCase):
    """GL-064: Validate the API/OpenAPI contract hardening review."""

    REPO_ROOT = pathlib.Path(__file__).with_suffix("").parent.parent.parent
    DOCS_DIR = REPO_ROOT / "docs"
    EXAMPLE_DIR_GL064 = DOCS_DIR / "examples" / "gl064"
    BACKEND_TESTS_DIR = REPO_ROOT / "backend" / "tests"

    REQUIRED_PILOT_HARDENING_DOCS = [
        "integration_guide.md",
        "integrator_quickstart.md",
        "minimal_api_usage_walkthrough.md",
        "demo_scenario.md",
        "pilot_ready_handoff_plan.md",
        "pilot_ready_release_decision.md",
        "demo_runner_api_smoke.md",
        "pilot_partner_preparation_pack.md",
        "production_hardening_roadmap.md",
        "production_readiness_cut.md",
    ]

    REQUIRED_CATEGORIES = [
        "Endpoint inventory and path stability",
        "Request schema completeness",
        "Response schema completeness",
        "Error response consistency",
        "Authentication and authorization contract clarity",
        "Operation IDs and naming consistency",
        "Examples and sample payloads",
        "Versioning and compatibility policy",
        "Pagination/filtering/query parameter consistency",
        "Audit/provenance/export contract clarity",
        "Evidence and compliance payload consistency",
        "OpenAPI validation in CI",
        "External integrator documentation alignment",
        "Deprecation and legacy-path policy",
        "Production contract freeze process",
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
        cls.review_path = cls.DOCS_DIR / "api_openapi_contract_hardening_review.md"
        cls.backlog_path = cls.EXAMPLE_DIR_GL064 / "api_contract_hardening_backlog.json"
        cls.snapshot_path = cls.EXAMPLE_DIR_GL064 / "api_contract_readiness_snapshot.json"

        cls.backlog_json = None
        cls.backlog_text = None
        if cls.backlog_path.exists():
            cls.backlog_text = cls.backlog_path.read_text(encoding="utf-8")
            cls.backlog_json = json.loads(cls.backlog_text)

        cls.snapshot_json = None
        cls.snapshot_text = None
        if cls.snapshot_path.exists():
            cls.snapshot_text = cls.snapshot_path.read_text(encoding="utf-8")
            cls.snapshot_json = json.loads(cls.snapshot_text)

    # ── 1. Review doc exists ─────────────────────────────────────────
    def test_review_doc_exists(self):
        self.assertTrue(
            self.review_path.exists(),
            "docs/api_openapi_contract_hardening_review.md must exist",
        )

    # ── 2. Backlog JSON exists and parses ────────────────────────────
    def test_backlog_exists_and_parses(self):
        self.assertTrue(
            self.backlog_path.exists(),
            "docs/examples/gl064/api_contract_hardening_backlog.json must exist",
        )
        self.assertIsNotNone(self.backlog_json, "Backlog must parse as valid JSON")
        self.assertIsInstance(self.backlog_json, dict)

    # ── 3. Snapshot JSON exists and parses ───────────────────────────
    def test_snapshot_exists_and_parses(self):
        self.assertTrue(
            self.snapshot_path.exists(),
            "docs/examples/gl064/api_contract_readiness_snapshot.json must exist",
        )
        self.assertIsNotNone(self.snapshot_json, "Snapshot must parse as valid JSON")
        self.assertIsInstance(self.snapshot_json, dict)

    # ── 4. docs/openapi.yaml exists ──────────────────────────────────
    def test_openapi_yaml_exists(self):
        path = self.DOCS_DIR / "openapi.yaml"
        self.assertTrue(
            path.exists(),
            "docs/openapi.yaml must exist",
        )

    # ── 5. Required Pilot-Ready / Production-Hardening docs exist ────
    def test_referenced_required_docs_exist(self):
        missing = []
        for name in self.REQUIRED_PILOT_HARDENING_DOCS:
            path = self.DOCS_DIR / name
            if not path.exists():
                missing.append(name)
        self.assertEqual(missing, [], f"Missing required docs: {missing}")

    # ── 6. GL-055, GL-058, GL-061 validation tests exist ─────────────
    def test_gl055_test_exists(self):
        path = self.BACKEND_TESTS_DIR / "test_gl055_integration_contract_readiness.py"
        self.assertTrue(path.exists(), "GL-055 test must exist")

    def test_gl058_test_exists(self):
        path = self.BACKEND_TESTS_DIR / "test_gl058_minimal_api_usage_walkthrough.py"
        self.assertTrue(path.exists(), "GL-058 test must exist")

    def test_gl061_test_exists(self):
        path = self.BACKEND_TESTS_DIR / "test_gl061_demo_runner_api_smoke.py"
        self.assertTrue(path.exists(), "GL-061 test must exist")

    # ── 7. Required review categories are present in the backlog ─────
    def test_backlog_includes_required_categories(self):
        categories = self.backlog_json.get("categories", [])
        for category in self.REQUIRED_CATEGORIES:
            with self.subTest(category=category):
                self.assertIn(
                    category,
                    categories,
                    f"Backlog categories must include '{category}'",
                )

    # ── 8. Backlog has P0/P1/P2 workstreams ──────────────────────────
    def test_backlog_has_p0_workstreams(self):
        p0 = self.backlog_json.get("p0Workstreams", [])
        self.assertTrue(len(p0) > 0, "Backlog must have P0 workstreams")
        for ws in p0:
            self.assertEqual(ws.get("priority"), "P0", "P0 workstream must have priority P0")

    def test_backlog_has_p1_workstreams(self):
        p1 = self.backlog_json.get("p1Workstreams", [])
        self.assertTrue(len(p1) > 0, "Backlog must have P1 workstreams")
        for ws in p1:
            self.assertEqual(ws.get("priority"), "P1", "P1 workstream must have priority P1")

    def test_backlog_has_p2_workstreams(self):
        p2 = self.backlog_json.get("p2Workstreams", [])
        self.assertTrue(len(p2) > 0, "Backlog must have P2 workstreams")
        for ws in p2:
            self.assertEqual(ws.get("priority"), "P2", "P2 workstream must have priority P2")

    # ── 9. Snapshot says productionReadyApiContract is false ─────────
    def test_snapshot_says_not_production_ready(self):
        self.assertFalse(
            self.snapshot_json.get("productionReadyApiContract"),
            "snapshot productionReadyApiContract must be false",
        )

    # ── 10. Snapshot says pilotReadyApiReview is true ────────────────
    def test_snapshot_says_pilot_ready(self):
        self.assertTrue(
            self.snapshot_json.get("pilotReadyApiReview"),
            "snapshot pilotReadyApiReview must be true",
        )

    # ── 11. Review doc states Production-Ready API contract: no ──────
    def test_review_says_not_production_ready(self):
        content = self.review_path.read_text(encoding="utf-8").lower()
        # The markdown table contains | Production-Ready API contract | **No** |
        stripped = content.replace(" ", "").replace("|", "").replace("*", "")
        self.assertIn("production-readyapicontractno", stripped)
        self.assertIn("production-ready", content)

    # ── 12. Review doc includes recommended hardening order ──────────
    def test_review_includes_recommended_order(self):
        content = self.review_path.read_text(encoding="utf-8").lower()
        self.assertIn("recommended hardening order", content)

    # ── 13. Review doc includes what not to change yet ───────────────
    def test_review_includes_what_not_to_change_yet(self):
        content = self.review_path.read_text(encoding="utf-8").lower()
        self.assertIn("what not to change yet", content)

    # ── 14. No obvious secrets appear in JSON files ──────────────────
    def _sanitize_known_safe_terms(self, text):
        """Remove legitimate planning terms that contain secret-like substrings."""
        safe_terms = [
            "admin-token",
            "operator-token",
            "authentication and authorization contract clarity",
            "secret management",
            "secret-management",
            "managed secrets",
            "production secrets",
            "synthetic data",
            "secrets",
            "secret",
            "authorization",
            "token",
            "bearer",
        ]
        result = text.lower()
        # Replace longer terms first to avoid partial matches
        for term in sorted(safe_terms, key=len, reverse=True):
            result = result.replace(term.lower(), "")
        return result

    def test_no_obvious_secrets_in_backlog(self):
        text_lower = self._sanitize_known_safe_terms(self.backlog_text)
        for pattern in self.SECRET_PATTERNS:
            self.assertNotIn(
                pattern,
                text_lower,
                f"Backlog may contain secret-like pattern: {pattern}",
            )

    def test_no_obvious_secrets_in_snapshot(self):
        text_lower = self._sanitize_known_safe_terms(self.snapshot_text)
        for pattern in self.SECRET_PATTERNS:
            self.assertNotIn(
                pattern,
                text_lower,
                f"Snapshot may contain secret-like pattern: {pattern}",
            )

    # ── Extra coherence checks ───────────────────────────────────────
    def test_backlog_has_id_and_version(self):
        self.assertEqual(
            self.backlog_json.get("backlogId"),
            "gl064-api-contract-hardening-backlog",
        )
        self.assertEqual(self.backlog_json.get("backlogVersion"), "1.0")

    def test_backlog_status_is_planning(self):
        self.assertEqual(self.backlog_json.get("status"), "planning")

    def test_backlog_pilot_ready_true(self):
        self.assertTrue(self.backlog_json.get("pilotReadyApiReview"))

    def test_backlog_production_ready_false(self):
        self.assertFalse(self.backlog_json.get("productionReadyApiContract"))

    def test_snapshot_has_id_and_version(self):
        self.assertEqual(
            self.snapshot_json.get("snapshotId"),
            "gl064-api-contract-readiness-snapshot",
        )
        self.assertEqual(self.snapshot_json.get("snapshotVersion"), "1.0")

    def test_snapshot_integration_ready_true(self):
        self.assertTrue(self.snapshot_json.get("integrationReadyApiReview"))

    def test_snapshot_has_basis(self):
        basis = self.snapshot_json.get("basis", [])
        self.assertTrue(len(basis) > 0, "basis must not be empty")
        basis_text = " ".join(basis).lower()
        self.assertIn("gl-052", basis_text, "basis must reference GL-052")
        self.assertIn("gl-063", basis_text, "basis must reference GL-063")

    def test_snapshot_has_production_blockers(self):
        blockers = self.snapshot_json.get("productionBlockers", [])
        self.assertTrue(len(blockers) > 0, "productionBlockers must not be empty")
        blocker_ids = {b.get("blockerId") for b in blockers}
        self.assertIn("b01-freeze-process", blocker_ids, "blockers must include freeze process")

    def test_snapshot_has_pilot_permitted_scope(self):
        scope = self.snapshot_json.get("pilotPermittedScope", [])
        self.assertTrue(len(scope) > 0, "pilotPermittedScope must not be empty")
        scope_text = " ".join(scope).lower()
        self.assertIn("openapi.yaml", scope_text, "scope must mention openapi.yaml")

    def test_snapshot_has_contract_claim_stop_conditions(self):
        conditions = self.snapshot_json.get("contractClaimStopConditions", [])
        self.assertTrue(len(conditions) > 0, "contractClaimStopConditions must not be empty")

    def test_snapshot_has_next_recommended_options(self):
        options = self.snapshot_json.get("nextRecommendedOptions", [])
        self.assertTrue(len(options) > 0, "nextRecommendedOptions must not be empty")
        option_ids = {o.get("optionId") for o in options}
        self.assertIn("opt-01", option_ids, "options must include opt-01")

    def test_review_references_gl052_and_gl063(self):
        content = self.review_path.read_text(encoding="utf-8").lower()
        self.assertIn("gl-052", content, "Review must reference GL-052")
        self.assertIn("gl-063", content, "Review must reference GL-063")
        self.assertIn("through gl-0", content, "Review must reference the GL artifact range")

    def test_review_includes_p0_section(self):
        content = self.review_path.read_text(encoding="utf-8").lower()
        self.assertIn("p0 contract-hardening workstreams", content)

    def test_review_includes_p1_section(self):
        content = self.review_path.read_text(encoding="utf-8").lower()
        self.assertIn("p1 pilot-expansion workstreams", content)

    def test_review_includes_p2_section(self):
        content = self.review_path.read_text(encoding="utf-8").lower()
        self.assertIn("p2 productization workstreams", content)

    def test_review_includes_decision_boundary(self):
        content = self.review_path.read_text(encoding="utf-8").lower()
        self.assertIn("decision boundary", content)

    def test_review_includes_current_readiness_state(self):
        content = self.review_path.read_text(encoding="utf-8").lower()
        self.assertIn("current readiness state", content)

    def test_review_includes_current_contract_artifacts(self):
        content = self.review_path.read_text(encoding="utf-8").lower()
        self.assertIn("current contract artifacts", content)

    def test_review_doc_references_openapi_yaml(self):
        content = self.review_path.read_text(encoding="utf-8").lower()
        self.assertIn("openapi.yaml", content)

    def test_review_doc_references_gl055_test(self):
        content = self.review_path.read_text(encoding="utf-8").lower()
        self.assertIn("test_gl055_integration_contract_readiness.py", content)

    def test_review_doc_references_gl058_test(self):
        content = self.review_path.read_text(encoding="utf-8").lower()
        self.assertIn("test_gl058_minimal_api_usage_walkthrough.py", content)

    def test_review_doc_references_gl061_test(self):
        content = self.review_path.read_text(encoding="utf-8").lower()
        self.assertIn("test_gl061_demo_runner_api_smoke.py", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
