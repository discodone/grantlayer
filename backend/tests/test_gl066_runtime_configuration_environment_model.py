"""Tests for GL-066 Runtime Configuration and Environment Model.

Lightweight validation test proving the runtime configuration and environment
model are:
- present as a human-readable document
- present as machine-readable JSON files
- coherent with referenced Pilot-Ready and Production-Hardening artifacts
- explicitly defining runtime modes, configuration categories, safe defaults,
  and production fail-closed boundaries
- free of obvious secrets
- not introducing forbidden implementation files
"""

import json
import pathlib
import unittest


class TestGL066RuntimeConfigurationEnvironmentModel(unittest.TestCase):
    """GL-066: Validate runtime configuration and environment model."""

    REPO_ROOT = pathlib.Path(__file__).with_suffix("").parent.parent.parent
    DOCS_DIR = REPO_ROOT / "docs"
    EXAMPLE_DIR_GL066 = DOCS_DIR / "examples" / "gl066"
    BACKEND_TESTS_DIR = REPO_ROOT / "backend" / "tests"
    BACKEND_SRC_DIR = REPO_ROOT / "backend" / "src"

    REQUIRED_RUNTIME_MODES = [
        "local-dev",
        "test",
        "demo",
        "integration",
        "staging",
        "production",
    ]

    REQUIRED_CONFIGURATION_CATEGORIES = [
        "Runtime mode",
        "Database backend",
        "Persistence path / connection",
        "Admin/operator access",
        "Authentication provider",
        "Secret management",
        "Signing/key management",
        "Evidence storage",
        "Evidence verification strategy",
        "Audit/provenance retention",
        "Compliance/readiness profile",
        "Policy/rule pack profile",
        "API server binding / network exposure",
        "CORS / external access",
        "Logging / observability",
        "Backup / restore",
        "Feature flags / extension toggles",
        "External integrations",
        "Demo/test fixture mode",
        "Safe failure behavior",
    ]

    REQUIRED_PRODUCTION_CONFIGURATION = [
        "Runtime mode",
        "Database backend and connection",
        "Auth provider",
        "Operator/admin access model",
        "Secret management",
        "Signing/key management",
        "Evidence storage",
        "Retention policy",
        "Observability/logging",
        "Backup/restore",
        "Network binding",
        "CORS/external access",
        "Deployment environment",
        "Compliance/legal boundary",
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

    FORBIDDEN_PATH_PATTERNS = [
        BACKEND_SRC_DIR / "config_loader.py",
        BACKEND_SRC_DIR / "environment.py",
        BACKEND_SRC_DIR / "settings.py",
        BACKEND_SRC_DIR / "secrets.py",
        BACKEND_SRC_DIR / "vault.py",
        BACKEND_SRC_DIR / "auth_provider.py",
        BACKEND_SRC_DIR / "oauth.py",
        BACKEND_SRC_DIR / "jwt.py",
        BACKEND_SRC_DIR / "sso.py",
        BACKEND_SRC_DIR / "mtls.py",
        BACKEND_SRC_DIR / "observability.py",
        BACKEND_SRC_DIR / "metrics.py",
        BACKEND_SRC_DIR / "prometheus.py",
        BACKEND_SRC_DIR / "grafana.py",
        BACKEND_SRC_DIR / "backup.py",
        BACKEND_SRC_DIR / "restore.py",
        BACKEND_SRC_DIR / "s3_storage.py",
        BACKEND_SRC_DIR / "hsm.py",
        BACKEND_SRC_DIR / "blockchain.py",
        BACKEND_SRC_DIR / "wallet.py",
        BACKEND_SRC_DIR / "payment.py",
        BACKEND_SRC_DIR / "tenant.py",
        BACKEND_SRC_DIR / "saas.py",
        BACKEND_SRC_DIR / "dashboard.py",
        BACKEND_SRC_DIR / "ui.py",
        BACKEND_SRC_DIR / "frontend.py",
        BACKEND_SRC_DIR / "sdk.py",
        BACKEND_SRC_DIR / "client.py",
        BACKEND_SRC_DIR / "deploy.py",
        BACKEND_SRC_DIR / "docker.py",
        BACKEND_SRC_DIR / "kubernetes.py",
        BACKEND_SRC_DIR / "helm.py",
        BACKEND_SRC_DIR / "terraform.py",
        BACKEND_SRC_DIR / "ci.py",
        BACKEND_SRC_DIR / "gitlab.py",
        BACKEND_SRC_DIR / "github.py",
    ]

    @classmethod
    def setUpClass(cls):
        cls.doc_path = cls.DOCS_DIR / "runtime_configuration_environment_model.md"
        cls.matrix_path = cls.EXAMPLE_DIR_GL066 / "runtime_environment_matrix.json"
        cls.catalog_path = cls.EXAMPLE_DIR_GL066 / "configuration_contract_catalog.json"

        cls.matrix_json = None
        cls.matrix_text = None
        if cls.matrix_path.exists():
            cls.matrix_text = cls.matrix_path.read_text(encoding="utf-8")
            cls.matrix_json = json.loads(cls.matrix_text)

        cls.catalog_json = None
        cls.catalog_text = None
        if cls.catalog_path.exists():
            cls.catalog_text = cls.catalog_path.read_text(encoding="utf-8")
            cls.catalog_json = json.loads(cls.catalog_text)

    # ── 1. Runtime config doc exists ────────────────────────────────
    def test_runtime_config_doc_exists(self):
        self.assertTrue(
            self.doc_path.exists(),
            "docs/runtime_configuration_environment_model.md must exist",
        )

    # ── 2. Runtime environment matrix JSON exists and parses ───────────
    def test_matrix_exists_and_parses(self):
        self.assertTrue(
            self.matrix_path.exists(),
            "docs/examples/gl066/runtime_environment_matrix.json must exist",
        )
        self.assertIsNotNone(self.matrix_json, "Matrix must parse as valid JSON")
        self.assertIsInstance(self.matrix_json, dict)

    # ── 3. Configuration contract catalog JSON exists and parses ──────
    def test_catalog_exists_and_parses(self):
        self.assertTrue(
            self.catalog_path.exists(),
            "docs/examples/gl066/configuration_contract_catalog.json must exist",
        )
        self.assertIsNotNone(self.catalog_json, "Catalog must parse as valid JSON")
        self.assertIsInstance(self.catalog_json, dict)

    # ── 4. Required product-foundation docs exist ───────────────────
    def test_required_product_foundation_docs_exist(self):
        required = [
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
            "product_architecture_extension_boundaries.md",
            "api_openapi_contract_hardening_review.md",
        ]
        missing = []
        for name in required:
            path = self.DOCS_DIR / name
            if not path.exists():
                missing.append(name)
        self.assertEqual(missing, [], f"Missing required docs: {missing}")

    # ── 5. GL-065 product architecture doc exists ───────────────────
    def test_gl065_product_architecture_doc_exists(self):
        path = self.DOCS_DIR / "product_architecture_extension_boundaries.md"
        self.assertTrue(path.exists(), "GL-065 product architecture doc must exist")

    # ── 6. GL-064 contract review doc exists ────────────────────────
    def test_gl064_contract_review_doc_exists(self):
        path = self.DOCS_DIR / "api_openapi_contract_hardening_review.md"
        self.assertTrue(path.exists(), "GL-064 contract review doc must exist")

    # ── 7. GL-063 production hardening roadmap exists ────────────────
    def test_gl063_production_hardening_roadmap_exists(self):
        path = self.DOCS_DIR / "production_hardening_roadmap.md"
        self.assertTrue(path.exists(), "GL-063 production hardening roadmap must exist")

    # ── 8. Runtime environment matrix includes required runtime modes ─
    def test_matrix_includes_required_runtime_modes(self):
        modes = self.matrix_json.get("runtimeModes", [])
        mode_names = {m.get("mode") for m in modes}
        for expected in self.REQUIRED_RUNTIME_MODES:
            with self.subTest(mode=expected):
                self.assertIn(
                    expected,
                    mode_names,
                    f"Matrix must include runtime mode '{expected}'",
                )

    # ── 9. Configuration catalog includes required categories ────────
    def test_catalog_includes_required_configuration_categories(self):
        categories = self.catalog_json.get("configurationCategories", [])
        category_names = {c.get("name") for c in categories}
        for expected in self.REQUIRED_CONFIGURATION_CATEGORIES:
            with self.subTest(category=expected):
                self.assertIn(
                    expected,
                    category_names,
                    f"Catalog must include configuration category '{expected}'",
                )

    # ── 10. Production runtime has productionClaimAllowed true only with explicit config ─
    def test_production_runtime_mode_claim_rules(self):
        modes = self.matrix_json.get("runtimeModes", [])
        production_mode = None
        for m in modes:
            if m.get("mode") == "production":
                production_mode = m
                break
        self.assertIsNotNone(production_mode, "Matrix must include a production runtime mode")
        self.assertTrue(
            production_mode.get("productionClaimAllowed"),
            "Production mode must allow production claims when explicitly configured",
        )
        self.assertEqual(
            production_mode.get("allowedDefaults", []),
            [],
            "Production mode must not allow any defaults",
        )
        required = production_mode.get("requiredExplicitSettings", [])
        self.assertTrue(len(required) > 0, "Production mode must require explicit settings")
        required_text = " ".join(required).lower()
        self.assertIn("runtime mode", required_text)
        self.assertIn("database", required_text)
        self.assertIn("auth", required_text)

    # ── 11. Production required configuration includes auth, secrets, database, observability, backup ─
    def test_production_required_configuration_coverage(self):
        required = self.matrix_json.get("productionRequiredConfiguration", [])
        required_text = " ".join(required).lower()
        self.assertIn("auth", required_text, "Production required config must include auth")
        self.assertIn("secret", required_text, "Production required config must include secrets")
        self.assertIn("database", required_text, "Production required config must include database")
        self.assertIn("observability", required_text, "Production required config must include observability")
        self.assertIn("backup", required_text, "Production required config must include backup")

    # ── 12. Document states local/test/demo defaults must not become production behavior ─
    def test_doc_states_local_defaults_not_production(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn(
            "local, test, and demo defaults must not accidentally become production behavior",
            content,
        )

    # ── 13. Document states production mode should fail closed if required config is missing ─
    def test_doc_states_production_fail_closed(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn(
            "production mode should fail closed if required configuration is missing",
            content,
        )

    # ── 14. No obvious secrets appear in JSON files ────────────────
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
            "demo admin tokens",
            "operator/admin access",
            "auth provider",
            "authentication provider",
            "demo tokens",
            "test keys",
            "secret source abstraction",
            "secret manager",
            "secret handling",
            "secret bearing",
            "sensitive value rules",
            "secrets must not",
        ]
        result = text.lower()
        for term in sorted(safe_terms, key=len, reverse=True):
            result = result.replace(term.lower(), "")
        return result

    def test_no_obvious_secrets_in_matrix(self):
        text_lower = self._sanitize_known_safe_terms(self.matrix_text)
        for pattern in self.SECRET_PATTERNS:
            self.assertNotIn(
                pattern,
                text_lower,
                f"Matrix may contain secret-like pattern: {pattern}",
            )

    def test_no_obvious_secrets_in_catalog(self):
        text_lower = self._sanitize_known_safe_terms(self.catalog_text)
        for pattern in self.SECRET_PATTERNS:
            self.assertNotIn(
                pattern,
                text_lower,
                f"Catalog may contain secret-like pattern: {pattern}",
            )

    # ── 15. Forbidden implementation files were not introduced ───────
    def test_no_forbidden_implementation_files_introduced(self):
        for forbidden in self.FORBIDDEN_PATH_PATTERNS:
            # Only check files that actually exist; if they don't, they weren't introduced
            if forbidden.exists():
                self.fail(
                    f"Forbidden implementation file must not exist: {forbidden}"
                )

    # ── Extra coherence checks ──────────────────────────────────────
    def test_matrix_has_id_and_version(self):
        self.assertEqual(
            self.matrix_json.get("matrixId"),
            "gl066-runtime-environment-matrix",
        )
        self.assertEqual(self.matrix_json.get("matrixVersion"), "1.0")

    def test_matrix_status_is_product_foundation_planning(self):
        self.assertEqual(self.matrix_json.get("status"), "product-foundation-planning")

    def test_catalog_has_id_and_version(self):
        self.assertEqual(
            self.catalog_json.get("catalogId"),
            "gl066-configuration-contract-catalog",
        )
        self.assertEqual(self.catalog_json.get("catalogVersion"), "1.0")

    def test_catalog_status_is_product_foundation_planning(self):
        self.assertEqual(self.catalog_json.get("status"), "product-foundation-planning")

    def test_matrix_includes_production_claim_rules(self):
        rules = self.matrix_json.get("productionClaimRules", [])
        self.assertTrue(len(rules) > 0, "Matrix must include productionClaimRules")

    def test_matrix_includes_safe_defaults(self):
        defaults = self.matrix_json.get("safeDefaults", [])
        self.assertTrue(len(defaults) > 0, "Matrix must include safeDefaults")

    def test_catalog_includes_fail_closed_rules(self):
        rules = self.catalog_json.get("failClosedRules", [])
        self.assertTrue(len(rules) > 0, "Catalog must include failClosedRules")
        rules_text = " ".join(rules).lower()
        self.assertIn("production mode must refuse to start", rules_text)

    def test_catalog_includes_sensitive_value_rules(self):
        rules = self.catalog_json.get("sensitiveValueRules", [])
        self.assertTrue(len(rules) > 0, "Catalog must include sensitiveValueRules")

    def test_catalog_includes_extension_configuration_boundaries(self):
        boundaries = self.catalog_json.get("extensionConfigurationBoundaries", [])
        self.assertTrue(len(boundaries) > 0, "Catalog must include extensionConfigurationBoundaries")

    def test_catalog_includes_implementation_non_goals(self):
        non_goals = self.catalog_json.get("implementationNonGoals", [])
        self.assertTrue(len(non_goals) > 0, "Catalog must include implementationNonGoals")
        non_goals_text = " ".join(non_goals).lower()
        self.assertIn("configuration loader", non_goals_text)
        self.assertIn("secret manager integration", non_goals_text)
        self.assertIn("auth provider integration", non_goals_text)

    def test_doc_includes_runtime_modes_section(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("runtime modes", content)

    def test_doc_includes_configuration_categories_section(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("configuration categories", content)

    def test_doc_includes_safe_defaults_section(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("safe local/test/demo defaults", content)

    def test_doc_includes_production_explicit_section(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("production-required explicit configuration", content)

    def test_doc_includes_configuration_boundaries_section(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("configuration boundaries", content)

    def test_doc_includes_future_implementation_expectations(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("future implementation expectations", content)

    def test_doc_includes_what_not_to_implement_yet(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("what not to implement yet", content)

    def test_doc_includes_decision_boundary(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("decision boundary", content)

    def test_doc_references_gl063(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("gl-063", content)

    def test_doc_references_gl064(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("gl-064", content)

    def test_doc_references_gl065(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("gl-065", content)

    def test_matrix_references_related_artifacts(self):
        artifacts = self.matrix_json.get("relatedArtifacts", [])
        self.assertTrue(len(artifacts) > 0, "Matrix must include relatedArtifacts")

    def test_catalog_references_related_artifacts(self):
        artifacts = self.catalog_json.get("relatedArtifacts", [])
        self.assertTrue(len(artifacts) > 0, "Catalog must include relatedArtifacts")


if __name__ == "__main__":
    unittest.main(verbosity=2)
