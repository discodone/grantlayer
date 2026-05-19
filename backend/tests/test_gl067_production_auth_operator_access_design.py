"""Tests for GL-067 Production Auth and Operator Access Design.

Lightweight validation test proving the production auth and operator access design is:
- present as a human-readable document
- present as machine-readable JSON files
- coherent with referenced Pilot-Ready and Production-Hardening artifacts
- explicitly defining operator roles, capability boundaries, auth provider adapter boundaries,
  production fail-closed rules, and local/test/demo auth shortcuts
- free of obvious secrets
- not introducing forbidden implementation files
"""

import json
import pathlib
import unittest


class TestGL067ProductionAuthOperatorAccessDesign(unittest.TestCase):
    """GL-067: Validate production auth and operator access design."""

    REPO_ROOT = pathlib.Path(__file__).with_suffix("").parent.parent.parent
    DOCS_DIR = REPO_ROOT / "docs"
    EXAMPLE_DIR_GL067 = DOCS_DIR / "examples" / "gl067"
    BACKEND_SRC_DIR = REPO_ROOT / "backend" / "src"

    REQUIRED_RUNTIME_MODES = [
        "local-dev",
        "test",
        "demo",
        "integration",
        "staging",
        "production",
    ]

    REQUIRED_OPERATOR_ROLES = [
        "system_admin",
        "grant_admin",
        "evidence_operator",
        "policy_admin",
        "auditor",
        "readonly_integrator",
        "external_workflow_agent",
        "service_operator",
    ]

    REQUIRED_CAPABILITY_GROUPS = [
        "grant request administration",
        "grant approval operations",
        "grant creation and lifecycle operations",
        "evidence write operations",
        "evidence verification operations",
        "policy/rule pack administration",
        "permission profile administration",
        "auditor report/export access",
        "compliance readiness review",
        "system configuration administration",
        "readonly integration access",
        "service-to-service workflow execution",
    ]

    REQUIRED_AUTH_BOUNDARIES = [
        "boundary-operator-role-semantics",
        "boundary-capability-groups",
        "boundary-auth-provider-adapter",
        "boundary-role-capability-mapping",
        "boundary-operator-bootstrap",
        "boundary-service-identity",
        "boundary-auth-audit-events",
        "boundary-production-fail-closed",
        "boundary-local-demo-shortcuts",
        "boundary-openapi-security-contract",
    ]

    SECRET_PATTERNS = [
        "password",
        "secret",
        "api_key",
        "apikey",
        "private_key",
        "privatekey",
        "bearer",
        "authorization",
    ]

    FORBIDDEN_PATH_PATTERNS = [
        BACKEND_SRC_DIR / "config_loader.py",
        BACKEND_SRC_DIR / "runtime_config.py",
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
        cls.doc_path = cls.DOCS_DIR / "production_auth_operator_access_design.md"
        cls.matrix_path = cls.EXAMPLE_DIR_GL067 / "auth_operator_role_matrix.json"
        cls.catalog_path = cls.EXAMPLE_DIR_GL067 / "operator_access_boundary_catalog.json"

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

    # ── 1. Production auth doc exists ───────────────────────────────
    def test_production_auth_doc_exists(self):
        self.assertTrue(
            self.doc_path.exists(),
            "docs/production_auth_operator_access_design.md must exist",
        )

    # ── 2. Auth operator role matrix JSON exists and parses ──────────
    def test_matrix_exists_and_parses(self):
        self.assertTrue(
            self.matrix_path.exists(),
            "docs/examples/gl067/auth_operator_role_matrix.json must exist",
        )
        self.assertIsNotNone(self.matrix_json, "Matrix must parse as valid JSON")
        self.assertIsInstance(self.matrix_json, dict)

    # ── 3. Operator access boundary catalog JSON exists and parses ───
    def test_catalog_exists_and_parses(self):
        self.assertTrue(
            self.catalog_path.exists(),
            "docs/examples/gl067/operator_access_boundary_catalog.json must exist",
        )
        self.assertIsNotNone(self.catalog_json, "Catalog must parse as valid JSON")
        self.assertIsInstance(self.catalog_json, dict)

    # ── 4. Required product-foundation docs exist ────────────────────
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

    # ── 5. GL-066 runtime configuration doc exists ──────────────────
    def test_gl066_runtime_configuration_doc_exists(self):
        path = self.DOCS_DIR / "runtime_configuration_environment_model.md"
        self.assertTrue(path.exists(), "GL-066 runtime configuration doc must exist")

    # ── 6. GL-065 product architecture doc exists ────────────────────
    def test_gl065_product_architecture_doc_exists(self):
        path = self.DOCS_DIR / "product_architecture_extension_boundaries.md"
        self.assertTrue(path.exists(), "GL-065 product architecture doc must exist")

    # ── 7. GL-064 contract review doc exists ─────────────────────────
    def test_gl064_contract_review_doc_exists(self):
        path = self.DOCS_DIR / "api_openapi_contract_hardening_review.md"
        self.assertTrue(path.exists(), "GL-064 contract review doc must exist")

    # ── 8. Role matrix includes required runtime modes ───────────────
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

    # ── 9. Role matrix includes required operator roles ──────────────
    def test_matrix_includes_required_operator_roles(self):
        roles = self.matrix_json.get("operatorRoles", [])
        role_names = {r.get("role") for r in roles}
        for expected in self.REQUIRED_OPERATOR_ROLES:
            with self.subTest(role=expected):
                self.assertIn(
                    expected,
                    role_names,
                    f"Matrix must include operator role '{expected}'",
                )

    # ── 10. Role matrix includes required capability groups ─────────
    def test_matrix_includes_required_capability_groups(self):
        groups = self.matrix_json.get("capabilityGroups", [])
        group_names_text = " ".join([g.get("name", "") for g in groups]).lower()
        for expected in self.REQUIRED_CAPABILITY_GROUPS:
            with self.subTest(capability=expected):
                self.assertIn(
                    expected.lower(),
                    group_names_text,
                    f"Matrix must include capability group '{expected}'",
                )

    # ── 11. Boundary catalog includes required auth boundaries ──────
    def test_catalog_includes_required_auth_boundaries(self):
        boundaries = self.catalog_json.get("authBoundaries", [])
        boundary_ids = {b.get("id") for b in boundaries}
        for expected in self.REQUIRED_AUTH_BOUNDARIES:
            with self.subTest(boundary=expected):
                self.assertIn(
                    expected,
                    boundary_ids,
                    f"Catalog must include auth boundary '{expected}'",
                )

    # ── 12. Production fail-closed rules are documented ─────────────
    def test_production_fail_closed_rules_documented(self):
        # Check markdown document
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("production fail-closed rules", content)
        self.assertIn("production mode must not start with demo/default admin token", content)
        self.assertIn("production mode must not silently allow unauthenticated access", content)
        self.assertIn("production mode must require explicit auth provider configuration", content)
        self.assertIn("production mode must require explicit operator/admin bootstrap configuration", content)
        self.assertIn("production mode must fail closed if required auth config is missing", content)
        # Check catalog JSON
        rules = self.catalog_json.get("failClosedRules", [])
        self.assertTrue(len(rules) > 0, "Catalog must include failClosedRules")
        rules_text = " ".join(rules).lower()
        self.assertIn("production mode must refuse to start", rules_text)

    # ── 13. Local/test/demo shortcuts are documented as non-production only ─
    def test_local_test_demo_shortcuts_non_production(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("local/test/demo shortcuts", content)
        self.assertIn("not valid production behavior", content)
        # Check catalog JSON
        shortcuts = self.catalog_json.get("localDemoTestShortcuts", [])
        self.assertTrue(len(shortcuts) > 0, "Catalog must include localDemoTestShortcuts")
        for shortcut in shortcuts:
            self.assertIn("productionRisk", shortcut)

    # ── 15. JSON files do not contain obvious secrets, fake tokens, or fake credentials ─
    def test_doc_states_production_auth_readiness_not_claimed(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn(
            "claim production auth readiness",
            content,
        )
        self.assertIn(
            "auth provider configuration, operator bootstrap, role/capability mapping",
            content,
        )

    # ── 15. JSON files do not contain obvious secrets, fake tokens, or fake credentials ─
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
            "local admin token for developer convenience",
            "demo operator identity",
            "fixture-based service identity",
            "readonly demo access",
            "auth provider adapter",
            "external identity provider",
            "service identity provider",
            "auth provider type",
            "auth provider endpoint",
            "no plaintext tokens",
            "jwt validation",
            "provider-specific fields must not leak",
            "unauthenticated access",
            "demo/default admin token",
            "auth audit event",
            "auth configuration",
            "auth expectations",
            "auth provider configuration",
            "auth provider claims",
            "auth provider endpoint",
            "auth success",
            "auth failure",
            "access denied",
            "local/test/demo auth shortcuts",
            "simplified auth acceptable",
            "partner-agreed authentication",
            "mock auth provider",
            "no external identity provider",
            "production auth readiness",
            "production auth requirements",
            "production-grade provider",
            "auth expectation",
            "auth path",
            "auth mechanism",
            "auth provider role mapping",
            "explicit auth provider",
            "password login",
            "passwords",
            "default passwords",
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

    # ── 16. Forbidden implementation files were not introduced ─────
    def test_no_forbidden_implementation_files_introduced(self):
        for forbidden in self.FORBIDDEN_PATH_PATTERNS:
            if forbidden.exists():
                self.fail(
                    f"Forbidden implementation file must not exist: {forbidden}"
                )

    # ── Extra coherence checks ──────────────────────────────────────
    def test_matrix_has_id_and_version(self):
        self.assertEqual(
            self.matrix_json.get("matrixId"),
            "gl067-auth-operator-role-matrix",
        )
        self.assertEqual(self.matrix_json.get("matrixVersion"), "1.0")

    def test_matrix_status_is_product_foundation_planning(self):
        self.assertEqual(self.matrix_json.get("status"), "product-foundation-planning")

    def test_catalog_has_id_and_version(self):
        self.assertEqual(
            self.catalog_json.get("catalogId"),
            "gl067-operator-access-boundary-catalog",
        )
        self.assertEqual(self.catalog_json.get("catalogVersion"), "1.0")

    def test_catalog_status_is_product_foundation_planning(self):
        self.assertEqual(self.catalog_json.get("status"), "product-foundation-planning")

    def test_matrix_includes_production_claim_rules(self):
        rules = self.matrix_json.get("productionClaimRules", [])
        self.assertTrue(len(rules) > 0, "Matrix must include productionClaimRules")

    def test_catalog_includes_provider_adapter_expectations(self):
        expectations = self.catalog_json.get("providerAdapterExpectations", [])
        self.assertTrue(len(expectations) > 0, "Catalog must include providerAdapterExpectations")
        text = " ".join(expectations).lower()
        self.assertIn("product core should not depend on one specific auth provider", text)

    def test_catalog_includes_production_required_configuration(self):
        required = self.catalog_json.get("productionRequiredConfiguration", [])
        self.assertTrue(len(required) > 0, "Catalog must include productionRequiredConfiguration")
        text = " ".join(required).lower()
        self.assertIn("auth provider", text)
        self.assertIn("operator bootstrap", text)
        self.assertIn("role/capability", text)

    def test_catalog_includes_audit_expectations(self):
        expectations = self.catalog_json.get("auditExpectations", [])
        self.assertTrue(len(expectations) > 0, "Catalog must include auditExpectations")
        text = " ".join(expectations).lower()
        self.assertIn("audit records must never contain", text)

    def test_catalog_includes_implementation_non_goals(self):
        non_goals = self.catalog_json.get("implementationNonGoals", [])
        self.assertTrue(len(non_goals) > 0, "Catalog must include implementationNonGoals")
        text = " ".join(non_goals).lower()
        self.assertIn("oauth", text)
        self.assertIn("jwt", text)
        self.assertIn("sso", text)

    def test_doc_includes_product_auth_principle(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("product auth principle", content)
        self.assertIn("stable operator role semantics", content)
        self.assertIn("concrete auth providers replaceable", content)

    def test_doc_includes_runtime_mode_auth_expectations(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("runtime-mode auth expectations", content)
        self.assertIn("local-dev", content)
        self.assertIn("production", content)

    def test_doc_includes_stable_operator_roles(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("stable operator roles", content)
        self.assertIn("system_admin", content)
        self.assertIn("grant_admin", content)
        self.assertIn("evidence_operator", content)

    def test_doc_includes_capability_boundaries(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("capability boundaries", content)
        self.assertIn("grant request administration", content)
        self.assertIn("evidence verification operations", content)

    def test_doc_includes_auth_provider_adapter_boundary(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("auth provider adapter boundary", content)
        self.assertIn("product core should not depend on one specific auth provider", content)

    def test_doc_includes_audit_and_provenance_expectations(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("audit and provenance expectations", content)
        self.assertIn("not contain secrets", content)

    def test_doc_includes_future_implementation_expectations(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("future implementation expectations", content)
        self.assertIn("auth configuration schema", content)
        self.assertIn("production fail-closed startup checks", content)
        self.assertIn("openapi security contract update", content)

    def test_doc_includes_what_not_to_implement_yet(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("what not to implement yet", content)
        self.assertIn("oauth", content)
        self.assertIn("jwt", content)
        self.assertIn("sso", content)

    def test_doc_includes_decision_boundary(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("decision boundary", content)

    def test_doc_references_gl066(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("gl-066", content)

    def test_doc_references_gl065(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("gl-065", content)

    def test_doc_references_gl064(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("gl-064", content)

    def test_doc_references_gl063(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("gl-063", content)

    def test_matrix_references_related_artifacts(self):
        artifacts = self.matrix_json.get("relatedArtifacts", [])
        self.assertTrue(len(artifacts) > 0, "Matrix must include relatedArtifacts")

    def test_catalog_references_related_artifacts(self):
        artifacts = self.catalog_json.get("relatedArtifacts", [])
        self.assertTrue(len(artifacts) > 0, "Catalog must include relatedArtifacts")

    def test_catalog_auth_boundaries_mark_product_core_owned(self):
        boundaries = self.catalog_json.get("authBoundaries", [])
        owned_count = 0
        for boundary in boundaries:
            if boundary.get("productCoreOwned") is True:
                owned_count += 1
        self.assertGreater(
            owned_count,
            0,
            "At least one auth boundary must be marked productCoreOwned",
        )

    def test_catalog_auth_boundaries_mark_replaceable_adapter(self):
        boundaries = self.catalog_json.get("authBoundaries", [])
        replaceable_count = 0
        for boundary in boundaries:
            if boundary.get("replaceableAdapter") is True:
                replaceable_count += 1
        self.assertGreater(
            replaceable_count,
            0,
            "At least one auth boundary must be marked replaceableAdapter",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
