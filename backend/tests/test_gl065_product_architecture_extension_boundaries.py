"""Tests for GL-065 Product Architecture and Extension Boundaries.

Lightweight validation test proving the product architecture and extension
boundaries are:
- present as a human-readable document
- present as machine-readable JSON files
- coherent with referenced Pilot-Ready and Production-Hardening artifacts
- explicitly defining Product Core, extension surfaces, and non-core areas
- free of obvious secrets
"""

import json
import pathlib
import unittest


class TestGL065ProductArchitectureExtensionBoundaries(unittest.TestCase):
    """GL-065: Validate product architecture and extension boundaries."""

    REPO_ROOT = pathlib.Path(__file__).with_suffix("").parent.parent.parent
    DOCS_DIR = REPO_ROOT / "docs"
    EXAMPLE_DIR_GL065 = DOCS_DIR / "examples" / "gl065"

    REQUIRED_PRODUCT_FOUNDATION_DOCS = [
        "integration_guide.md",
        "integrator_quickstart.md",
        "minimal_api_usage_walkthrough.md",
        "demo_scenario.md",
        "pilot_ready_handoff_plan.md",
        "pilot_ready_release_decision.md",
        "demo_runner_api_smoke.md",
        "pilot_partner_preparation_pack.md",
    ]

    REQUIRED_ARCHITECTURE_LAYERS = [
        "API / Contract Layer",
        "Product Core Domain Layer",
        "Evidence and Verification Layer",
        "Policy and Permission Layer",
        "Provenance, Audit, and Export Layer",
        "Persistence Layer",
        "Runtime Configuration Layer",
        "Extension / Adapter Layer",
        "Optional Integration Layer",
    ]

    REQUIRED_CORE_MODULES = [
        "Grant Requests",
        "Approvals",
        "Grants",
        "Grant Executions",
        "Evidence Bundles",
        "Evidence Persistence",
        "Evidence Verification",
        "Evidence Completeness",
        "Compliance Gap Reports",
        "Policy Requirements / Rule Packs",
        "Agent Permissions",
        "Approval Lifecycle",
        "Decision Provenance",
        "Auditor Exports",
        "Compliance Readiness",
        "API / OpenAPI Contract",
        "Audit / Event Records",
        "Persistence Layer",
        "Operator / Admin Access Boundary",
    ]

    REQUIRED_STABLE_PUBLIC_CONTRACTS = [
        "API paths",
        "evidence bundle records",
        "verification result records",
        "provenance summaries",
        "auditor export records",
        "compliance readiness summaries",
        "policy requirement results",
        "permission evaluation results",
        "approval lifecycle records",
        "persistent IDs",
    ]

    REQUIRED_EXTENSION_SURFACES = [
        "Policy rule packs",
        "Evidence source adapters",
        "Evidence verification strategies",
        "Auditor export formats",
        "Compliance readiness dimensions",
        "Permission profiles",
        "Approval workflow profiles",
        "Storage / persistence backends",
        "Auth / identity providers",
        "SDK / API clients",
        "Workflow orchestrator integrations",
        "Observability sinks",
        "Optional blockchain anchoring",
        "Optional wallet / payment integration",
        "Dashboard / UI layer",
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
        cls.architecture_doc_path = cls.DOCS_DIR / "product_architecture_extension_boundaries.md"
        cls.map_path = cls.EXAMPLE_DIR_GL065 / "product_architecture_map.json"
        cls.catalog_path = cls.EXAMPLE_DIR_GL065 / "extension_boundary_catalog.json"

        cls.map_json = None
        cls.map_text = None
        if cls.map_path.exists():
            cls.map_text = cls.map_path.read_text(encoding="utf-8")
            cls.map_json = json.loads(cls.map_text)

        cls.catalog_json = None
        cls.catalog_text = None
        if cls.catalog_path.exists():
            cls.catalog_text = cls.catalog_path.read_text(encoding="utf-8")
            cls.catalog_json = json.loads(cls.catalog_text)

    # ── 1. Architecture doc exists ────────────────────────────────────
    def test_architecture_doc_exists(self):
        self.assertTrue(
            self.architecture_doc_path.exists(),
            "docs/product_architecture_extension_boundaries.md must exist",
        )

    # ── 2. Product architecture map JSON exists and parses ────────────
    def test_architecture_map_exists_and_parses(self):
        self.assertTrue(
            self.map_path.exists(),
            "docs/examples/gl065/product_architecture_map.json must exist",
        )
        self.assertIsNotNone(self.map_json, "Architecture map must parse as valid JSON")
        self.assertIsInstance(self.map_json, dict)

    # ── 3. Extension boundary catalog JSON exists and parses ──────────
    def test_extension_catalog_exists_and_parses(self):
        self.assertTrue(
            self.catalog_path.exists(),
            "docs/examples/gl065/extension_boundary_catalog.json must exist",
        )
        self.assertIsNotNone(self.catalog_json, "Catalog must parse as valid JSON")
        self.assertIsInstance(self.catalog_json, dict)

    # ── 4. Required product-foundation docs exist ──────────────────────
    def test_required_product_foundation_docs_exist(self):
        missing = []
        for name in self.REQUIRED_PRODUCT_FOUNDATION_DOCS:
            path = self.DOCS_DIR / name
            if not path.exists():
                missing.append(name)
        self.assertEqual(missing, [], f"Missing required docs: {missing}")

    # ── 5. GL-064 contract review doc exists ─────────────────────────
    def test_gl064_contract_review_doc_exists(self):
        path = self.DOCS_DIR / "api_openapi_contract_hardening_review.md"
        self.assertTrue(path.exists(), "GL-064 contract review doc must exist")

    # ── 6. GL-063 production hardening roadmap exists ─────────────────
    def test_gl063_production_hardening_roadmap_exists(self):
        path = self.DOCS_DIR / "production_hardening_roadmap.md"
        self.assertTrue(path.exists(), "GL-063 production hardening roadmap must exist")

    # ── 7. Product architecture map includes required architecture layers ─
    def test_map_includes_required_architecture_layers(self):
        layers = self.map_json.get("architectureLayers", [])
        layer_names = {layer.get("name") for layer in layers}
        for expected in self.REQUIRED_ARCHITECTURE_LAYERS:
            with self.subTest(layer=expected):
                self.assertIn(
                    expected,
                    layer_names,
                    f"Architecture map must include layer '{expected}'",
                )

    # ── 8. Product architecture map includes required core modules ────
    def test_map_includes_required_core_modules(self):
        modules = self.map_json.get("coreModules", [])
        module_names = {m.get("name") for m in modules}
        for expected in self.REQUIRED_CORE_MODULES:
            with self.subTest(module=expected):
                self.assertIn(
                    expected,
                    module_names,
                    f"Architecture map must include core module '{expected}'",
                )

    # ── 9. Product architecture map includes stable public contracts ──
    def test_map_includes_stable_public_contracts(self):
        contracts = self.map_json.get("stablePublicContracts", [])
        contract_text = " ".join(contracts).lower()
        for expected in self.REQUIRED_STABLE_PUBLIC_CONTRACTS:
            with self.subTest(contract=expected):
                self.assertIn(
                    expected.lower(),
                    contract_text,
                    f"Stable public contracts must include '{expected}'",
                )

    # ── 10. Extension boundary catalog includes required extension surfaces ─
    def test_catalog_includes_required_extension_surfaces(self):
        surfaces = self.catalog_json.get("extensionBoundaries", [])
        surface_names = {s.get("name") for s in surfaces}
        for expected in self.REQUIRED_EXTENSION_SURFACES:
            with self.subTest(surface=expected):
                self.assertIn(
                    expected,
                    surface_names,
                    f"Extension catalog must include surface '{expected}'",
                )

    # ── 11. Extension boundaries mark adapters as replaceable where appropriate ─
    def test_extension_boundaries_mark_replaceable(self):
        surfaces = self.catalog_json.get("extensionBoundaries", [])
        replaceable_count = 0
        total_count = len(surfaces)
        for surface in surfaces:
            if surface.get("replaceable") is True:
                replaceable_count += 1
        self.assertGreater(
            replaceable_count,
            0,
            "At least one extension boundary must be marked replaceable",
        )
        self.assertEqual(
            replaceable_count,
            total_count,
            "All extension boundaries should be marked replaceable",
        )

    # ── 12. Explicit non-core areas include blockchain/payment/dashboard/SaaS/legal certification ─
    def test_non_core_areas_include_expected_items(self):
        non_core = self.map_json.get("explicitNonCoreAreas", [])
        non_core_text = " ".join(non_core).lower()
        expected_items = [
            "blockchain",
            "payment",
            "dashboard",
            "saas",
            "legal",
            "certification",
        ]
        for item in expected_items:
            with self.subTest(item=item):
                self.assertIn(
                    item,
                    non_core_text,
                    f"Non-core areas must mention '{item}'",
                )

    # ── 13. Document states GrantLayer is a modular product foundation ─
    def test_doc_states_modular_product_foundation(self):
        content = self.architecture_doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("modular product foundation", content)

    # ── 14. Document states adapters must not redefine Product Core records ─
    def test_doc_states_adapters_must_not_redefine(self):
        content = self.architecture_doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("adapters must not redefine product core records", content)

    # ── 15. No obvious secrets appear in JSON files ───────────────────
    def _sanitize_known_safe_terms(self, text):
        """Remove legitimate planning terms that contain secret-like substrings."""
        safe_terms = [
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
        for term in sorted(safe_terms, key=len, reverse=True):
            result = result.replace(term.lower(), "")
        return result

    def test_no_obvious_secrets_in_map(self):
        text_lower = self._sanitize_known_safe_terms(self.map_text)
        for pattern in self.SECRET_PATTERNS:
            self.assertNotIn(
                pattern,
                text_lower,
                f"Architecture map may contain secret-like pattern: {pattern}",
            )

    def test_no_obvious_secrets_in_catalog(self):
        text_lower = self._sanitize_known_safe_terms(self.catalog_text)
        for pattern in self.SECRET_PATTERNS:
            self.assertNotIn(
                pattern,
                text_lower,
                f"Extension catalog may contain secret-like pattern: {pattern}",
            )

    # ── Extra coherence checks ────────────────────────────────────────
    def test_map_has_id_and_version(self):
        self.assertEqual(
            self.map_json.get("architectureId"),
            "gl065-product-architecture-map",
        )
        self.assertEqual(self.map_json.get("architectureVersion"), "1.0")

    def test_map_status_is_product_foundation_planning(self):
        self.assertEqual(self.map_json.get("status"), "product-foundation-planning")

    def test_catalog_has_id_and_version(self):
        self.assertEqual(
            self.catalog_json.get("catalogId"),
            "gl065-extension-boundary-catalog",
        )
        self.assertEqual(self.catalog_json.get("catalogVersion"), "1.0")

    def test_catalog_status_is_product_foundation_planning(self):
        self.assertEqual(self.catalog_json.get("status"), "product-foundation-planning")

    def test_doc_includes_adapter_rules(self):
        content = self.architecture_doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("adapter rules", content)
        self.assertIn("adapters must not redefine product core records", content)
        self.assertIn("adapters should be replaceable", content)
        self.assertIn("adapters should not leak secrets", content)

    def test_doc_includes_customization_model(self):
        content = self.architecture_doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("customization model", content)

    def test_doc_includes_recommended_evolution_order(self):
        content = self.architecture_doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("recommended architecture evolution order", content)

    def test_doc_includes_explicit_non_core_areas(self):
        content = self.architecture_doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("explicit non-core areas", content)

    def test_doc_includes_decision_boundary(self):
        content = self.architecture_doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("decision boundary", content)

    def test_catalog_includes_adapter_rules(self):
        rules = self.catalog_json.get("adapterRules", [])
        self.assertTrue(len(rules) > 0, "Catalog must include adapter rules")
        rules_text = " ".join(rules).lower()
        self.assertIn("adapters must not redefine product core records", rules_text)

    def test_catalog_includes_non_core_boundaries(self):
        non_core = self.catalog_json.get("nonCoreBoundaries", [])
        self.assertTrue(len(non_core) > 0, "Catalog must include nonCoreBoundaries")

    def test_catalog_includes_testing_expectations(self):
        expectations = self.catalog_json.get("testingExpectations", [])
        self.assertTrue(len(expectations) > 0, "Catalog must include testingExpectations")

    def test_catalog_includes_security_expectations(self):
        expectations = self.catalog_json.get("securityExpectations", [])
        self.assertTrue(len(expectations) > 0, "Catalog must include securityExpectations")


if __name__ == "__main__":
    unittest.main(verbosity=2)
