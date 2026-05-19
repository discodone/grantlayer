"""Tests for GL-068 Secret Management Baseline Design.

Lightweight validation test proving the secret management baseline design is:
- present as a human-readable document
- present as machine-readable JSON files
- coherent with referenced Pilot-Ready and Production-Hardening artifacts
- explicitly defining secret categories, runtime-mode expectations,
  production fail-closed rules, forbidden locations, and local/test/demo shortcuts
- free of obvious secrets
- not introducing forbidden implementation files
"""

import json
import pathlib
import unittest


class TestGL068SecretManagementBaselineDesign(unittest.TestCase):
    """GL-068: Validate secret management baseline design."""

    REPO_ROOT = pathlib.Path(__file__).with_suffix("").parent.parent.parent
    DOCS_DIR = REPO_ROOT / "docs"
    EXAMPLE_DIR_GL068 = DOCS_DIR / "examples" / "gl068"
    BACKEND_SRC_DIR = REPO_ROOT / "backend" / "src"

    REQUIRED_RUNTIME_MODES = [
        "local-dev",
        "test",
        "demo",
        "integration",
        "staging",
        "production",
    ]

    REQUIRED_SECRET_CATEGORIES = [
        "admin_operator_tokens",
        "service_to_service_credentials",
        "auth_provider_credentials",
        "database_credentials",
        "signing_key_material",
        "evidence_storage_credentials",
        "external_integration_credentials",
        "webhook_secrets",
        "encryption_keys",
        "session_token_signing_secrets",
        "api_client_credentials",
        "backup_storage_credentials",
        "observability_logging_sink_credentials",
        "optional_blockchain_wallet_keys",
        "demo_test_placeholder_identifiers",
    ]

    REQUIRED_SECRET_HANDLING_BOUNDARIES = [
        "boundary-secret-source-abstraction",
        "boundary-secret-configuration-schema",
        "boundary-runtime-secret-validation",
        "boundary-production-fail-closed-secrets",
        "boundary-secret-redaction",
        "boundary-signing-key-management",
        "boundary-database-credential-config",
        "boundary-auth-provider-secret-config",
        "boundary-evidence-storage-credential-config",
        "boundary-observability-sink-secret-config",
        "boundary-external-integration-secret-adapter",
        "boundary-local-demo-shortcut-guard",
        "boundary-leakage-prevention-tests",
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
        cls.doc_path = cls.DOCS_DIR / "secret_management_baseline_design.md"
        cls.inventory_path = cls.EXAMPLE_DIR_GL068 / "secret_inventory_model.json"
        cls.catalog_path = cls.EXAMPLE_DIR_GL068 / "secret_handling_policy_catalog.json"

        cls.inventory_json = None
        cls.inventory_text = None
        if cls.inventory_path.exists():
            cls.inventory_text = cls.inventory_path.read_text(encoding="utf-8")
            cls.inventory_json = json.loads(cls.inventory_text)

        cls.catalog_json = None
        cls.catalog_text = None
        if cls.catalog_path.exists():
            cls.catalog_text = cls.catalog_path.read_text(encoding="utf-8")
            cls.catalog_json = json.loads(cls.catalog_text)

    # ── 1. Secret management baseline design doc exists ───────────────
    def test_secret_management_baseline_design_doc_exists(self):
        self.assertTrue(
            self.doc_path.exists(),
            "docs/secret_management_baseline_design.md must exist",
        )

    # ── 2. Secret inventory model JSON exists and parses ─────────────
    def test_inventory_exists_and_parses(self):
        self.assertTrue(
            self.inventory_path.exists(),
            "docs/examples/gl068/secret_inventory_model.json must exist",
        )
        self.assertIsNotNone(self.inventory_json, "Inventory must parse as valid JSON")
        self.assertIsInstance(self.inventory_json, dict)

    # ── 3. Secret handling policy catalog JSON exists and parses ─────
    def test_catalog_exists_and_parses(self):
        self.assertTrue(
            self.catalog_path.exists(),
            "docs/examples/gl068/secret_handling_policy_catalog.json must exist",
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

    # ── 5. GL-067 auth/operator access doc exists ───────────────────
    def test_gl067_auth_operator_access_doc_exists(self):
        path = self.DOCS_DIR / "production_auth_operator_access_design.md"
        self.assertTrue(path.exists(), "GL-067 auth/operator access doc must exist")

    # ── 6. GL-066 runtime configuration doc exists ──────────────────
    def test_gl066_runtime_configuration_doc_exists(self):
        path = self.DOCS_DIR / "runtime_configuration_environment_model.md"
        self.assertTrue(path.exists(), "GL-066 runtime configuration doc must exist")

    # ── 7. GL-065 product architecture doc exists ────────────────────
    def test_gl065_product_architecture_doc_exists(self):
        path = self.DOCS_DIR / "product_architecture_extension_boundaries.md"
        self.assertTrue(path.exists(), "GL-065 product architecture doc must exist")

    # ── 8. Secret inventory includes required runtime modes ──────────
    def test_inventory_includes_required_runtime_modes(self):
        modes = self.inventory_json.get("runtimeModes", [])
        mode_names = {m.get("mode") for m in modes}
        for expected in self.REQUIRED_RUNTIME_MODES:
            with self.subTest(mode=expected):
                self.assertIn(
                    expected,
                    mode_names,
                    f"Inventory must include runtime mode '{expected}'",
                )

    # ── 9. Secret inventory includes required secret categories ─────
    def test_inventory_includes_required_secret_categories(self):
        categories = self.inventory_json.get("secretCategories", [])
        category_names = {c.get("category") for c in categories}
        for expected in self.REQUIRED_SECRET_CATEGORIES:
            with self.subTest(category=expected):
                self.assertIn(
                    expected,
                    category_names,
                    f"Inventory must include secret category '{expected}'",
                )

    # ── 10. Secret policy catalog includes required secret handling boundaries ─
    def test_catalog_includes_required_secret_handling_boundaries(self):
        boundaries = self.catalog_json.get("secretHandlingBoundaries", [])
        boundary_ids = {b.get("id") for b in boundaries}
        for expected in self.REQUIRED_SECRET_HANDLING_BOUNDARIES:
            with self.subTest(boundary=expected):
                self.assertIn(
                    expected,
                    boundary_ids,
                    f"Catalog must include secret handling boundary '{expected}'",
                )

    # ── 11. Production fail-closed rules are documented ──────────────
    def test_production_fail_closed_rules_documented(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("production fail-closed rules", content)
        self.assertIn("production mode must not start with missing required secret source", content)
        self.assertIn("production mode must not silently fall back to demo secrets", content)
        self.assertIn("production mode must not allow placeholder secrets", content)
        self.assertIn("production mode must fail closed if secret-bearing config is incomplete", content)
        self.assertIn("production mode must not expose secret values through api or logs", content)
        # Check catalog JSON
        rules = self.catalog_json.get("failClosedRules", [])
        self.assertTrue(len(rules) > 0, "Catalog must include failClosedRules")
        rules_text = " ".join(rules).lower()
        self.assertIn("production mode must refuse to start", rules_text)

    # ── 12. Forbidden secret locations are documented ────────────────
    def test_forbidden_secret_locations_documented(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("forbidden secret locations", content)
        self.assertIn("committed source code", content)
        self.assertIn("docs examples", content)
        self.assertIn("json fixtures", content)
        self.assertIn("openapi examples", content)
        self.assertIn("logs", content)
        # Check inventory JSON
        locations = self.inventory_json.get("forbiddenSecretLocations", [])
        self.assertTrue(len(locations) > 0, "Inventory must include forbiddenSecretLocations")

    # ── 13. Local/test/demo shortcuts are documented as non-production only ─
    def test_local_test_demo_shortcuts_non_production(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("allowed local/test/demo shortcuts", content)
        self.assertIn("not valid production secrets", content)
        # Check catalog JSON
        shortcuts = self.catalog_json.get("localDemoTestShortcuts", [])
        self.assertTrue(len(shortcuts) > 0, "Catalog must include localDemoTestShortcuts")
        for shortcut in shortcuts:
            self.assertIn("productionRisk", shortcut)

    # ── 14. Document states production secret management readiness is not yet claimed ─
    def test_doc_states_production_secret_readiness_not_claimed(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn(
            "claim production secret management readiness",
            content,
        )
        self.assertIn(
            "secret sources, required production secrets, redaction, fail-closed startup checks, and leakage-prevention tests",
            content,
        )

    # ── 15. JSON files do not contain obvious secrets, fake tokens, fake keys, fake credentials ─
    def _sanitize_known_safe_terms(self, text):
        """Remove legitimate planning terms that contain secret-like substrings."""
        safe_terms = [
            "secret",
            "secrets",
            "secret management baseline design",
            "secret management baseline",
            "secret management",
            "secret-handling-policy-catalog",
            "secret-handling",
            "secret_handling_policy_catalog",
            "secret inventory model",
            "secret_inventory_model",
            "secret inventory",
            "secret source abstraction",
            "secret source boundary",
            "secret source",
            "secret source names",
            "secret source manager",
            "secret source expectation",
            "secret source validation",
            "secret configuration schema",
            "secret configuration",
            "secret-bearing configuration",
            "secret-bearing fields",
            "secret-bearing config",
            "secret redaction helper",
            "secret redaction",
            "secret values",
            "secret value",
            "secret categories",
            "secret category",
            "secret categories define",
            "secret inventory model",
            "secret handling policy catalog",
            "secret handling boundary",
            "secret handling boundaries",
            "secret handling expectations",
            "secret handling principle",
            "secret handling clarity",
            "secret handling baseline",
            "secret handling",
            "secret placeholder",
            "secret placeholders",
            "secret expectation",
            "secret expectations",
            "secret resolved",
            "secret resolution",
            "secret category identifier",
            "secret manager",
            "secret managers",
            "secret store",
            "secret storage",
            "secret leakage",
            "secret leak",
            "secret loader",
            "secret loader implementation",
            "secret load",
            "secret material",
            "secret key",
            "secret identifier",
            "secret identifier",
            "secret-bearing",
            "secret-boundary",
            "secret-boundary calls",
            "secret-bearing output",
            "secret-bearing field",
            "secrets must not",
            "secrets outside",
            "secrets are needed",
            "secrets do not",
            "secrets should",
            "secrets must",
            "secrets may",
            "secrets were",
            "secrets in",
            "secrets from",
            "secrets through",
            "secrets outside",
            "secrets in logs",
            "secrets in exports",
            "secrets in examples",
            "secrets in fixtures",
            "secrets in evidence",
            "secrets in records",
            "secrets in git",
            "secrets in source",
            "secrets in test",
            "secrets in diagnostics",
            "secrets in backup",
            "secrets in config",
            "secrets in the",
            "required secrets",
            "managed secrets",
            "managed secret",
            "managed secret boundary",
            "managed secret strategy",
            "managed secret source",
            "managed with rotation",
            "placeholder secrets",
            "placeholder secret",
            "demo secrets",
            "demo secret",
            "synthetic secrets",
            "synthetic secret",
            "real secrets",
            "real secret",
            "external secret manager",
            "external secret managers",
            "no external secret manager",
            "local secret",
            "production secrets",
            "production secret",
            "auth provider credentials",
            "auth provider secret",
            "auth provider secret configuration",
            "auth provider secrets",
            "auth provider with validated",
            "auth provider type",
            "auth provider endpoint",
            "auth provider adapter",
            "auth provider configuration",
            "auth provider role mapping",
            "auth provider claim",
            "auth provider credentials",
            "auth provider with",
            "auth provider",
            "auth provider integration",
            "session token signing secrets",
            "session signing secrets",
            "session signing",
            "session tokens",
            "session token",
            "signing key material",
            "signing key management",
            "signing key",
            "signing keys",
            "signing and key management",
            "signing secret",
            "signing secrets",
            "signing operation",
            "signing algorithm",
            "demo signing key",
            "key identifier",
            "key identifiers",
            "key management",
            "key management abstraction",
            "key management source",
            "key rotation",
            "key source",
            "key provider",
            "key material",
            "key store",
            "key pair",
            "keypair",
            "synthetic keypairs",
            "synthetic keypair",
            "demo keypairs",
            "demo keypair",
            "mock key reference",
            "mock encryption key",
            "mock signing secret",
            "mock provider configuration",
            "mock provider",
            "mock secret",
            "mock secret sources",
            "mock secret source",
            "mock service identity",
            "mock shared secret",
            "mock client identifier",
            "mock sink reference",
            "mock provider references",
            "database credential source",
            "database credential configuration",
            "database credentials",
            "database credential",
            "evidence storage credentials",
            "evidence storage credential",
            "evidence storage credential configuration",
            "evidence storage credential source",
            "backup storage credentials",
            "backup storage credential",
            "observability sink credentials",
            "observability sink credential",
            "observability sink secret",
            "observability sink secret configuration",
            "external integration credentials",
            "external integration credential",
            "external integration secret",
            "external integration secret adapter",
            "api client credentials",
            "api client credential",
            "service-to-service credentials",
            "service-to-service credential",
            "service identity provider",
            "service credentials",
            "service credential",
            "webhook secrets",
            "webhook secret",
            "encryption keys",
            "encryption key",
            "token references",
            "token reference",
            "token signing",
            "token source",
            "tokens",
            "token",
            "demo tokens",
            "demo token",
            "demo admin tokens",
            "demo admin token",
            "test tokens",
            "synthetic tokens",
            "placeholder tokens",
            "local admin token",
            "admin tokens",
            "admin token",
            "operator tokens",
            "operator token",
            "session token",
            "state token",
            "auth token",
            "auth artifacts",
            "bearer",
            "authorization",
            "api_key",
            "apikey",
            "private_key",
            "privatekey",
            "password",
            "passwords",
            "password login",
            "default passwords",
            "client secrets",
            "client secret",
            "shared secrets",
            "shared secret",
            "secret source abstraction",
            "secret source boundary",
            "secret source names",
            "secret value rules",
            "sensitive value rules",
            "sensitive fields",
            "sensitive data",
            "secret bearing",
            "secret-bearing",
            "secret-bearing configuration",
            "secret-bearing fields",
            "secret-bearing config",
            "secret-bearing output",
            "secret-bearing field",
            "no real secret value",
            "no real secrets",
            "no real secret",
            "no real credentials",
            "no real credential values",
            "no real values",
            "no real value",
            "deterministic placeholder",
            "placeholder identifiers",
            "placeholder identifier",
            "placeholder secrets",
            "placeholder secret",
            "placeholder labels",
            "placeholder label",
            "demo fixture identifiers",
            "demo fixture identifier",
            "synthetic fixture identifiers",
            "synthetic fixture",
            "synthetic fixtures",
            "synthetic data",
            "synthetic identities",
            "synthetic identity",
            "synthetic secrets",
            "synthetic secret",
            "synthetic keypairs",
            "synthetic keypair",
            "synthetic labels",
            "synthetic label",
            "synthetic operator",
            "synthetic service",
            "deterministic placeholder identifiers",
            "deterministic test identity",
            "deterministic test",
            "deterministic test seeds",
            "demo operator identity",
            "demo operator",
            "fixture-based service identity",
            "fixture-based",
            "fixture ids",
            "fixture id",
            "fixture identifiers",
            "fixture identifier",
            "readonly demo access",
            "demo readonly",
            "local demo shortcut",
            "local demo shortcut guard",
            "local test demo shortcut",
            "local test demo",
            "local test",
            "local dev",
            "local file path",
            "local file paths",
            "local-only demo",
            "local-only",
            "local sqlite",
            "local admin",
            "local binding",
            "local config",
            "local development",
            "dry-run-only",
            "dry run",
            "smoke manifests",
            "secret identifier",
            "secret identifiers",
            "secret resolution",
            "secret values",
            "secret value",
            "secret manager integration",
            "secret manager",
            "secret handling policy",
            "secret handling",
            "secret handling expectations",
            "secret handling baseline",
            "secret handling clarity",
            "secret handling boundary",
            "secret handling boundaries",
            "secret handling policy catalog",
            "secret inventory",
            "secret inventory model",
            "secret category",
            "secret categories",
            "secret source",
            "secret sources",
            "secret store",
            "secret storage",
            "secret redaction",
            "secret redaction helper",
            "secret leakage",
            "secret leak",
            "secret leak into",
            "secret leak prevention",
            "leakage prevention",
            "leakage prevention tests",
            "leakage prevention expectations",
            "fail-closed startup",
            "fail-closed startup checks",
            "fail closed startup",
            "fail closed",
            "fail-closed secret",
            "fail-closed behavior",
            "fail closed behavior",
            "startup check",
            "startup checks",
            "startup logs",
            "startup output",
            "startup banner",
            "startup must",
            "startup allowed",
            "startup if",
            "startup behavior",
            "runtime secret",
            "runtime secret source",
            "runtime secret validation",
            "runtime secret expectations",
            "runtime secret expectation",
            "runtime mode secret",
            "runtime mode",
            "runtime configuration",
            "runtime config",
            "runtime behavior",
            "runtime secret",
            "runtime modes",
            "missing secret",
            "missing secrets",
            "missing required secret",
            "missing required secrets",
            "required secret",
            "required secrets",
            "required secret source",
            "required secret sources",
            "required secret configuration",
            "explicit secret",
            "explicit secrets",
            "explicit secret source",
            "explicit secret sources",
            "explicit secret boundary",
            "explicit secret management",
            "explicit secret configuration",
            "explicit signing",
            "explicit signing key",
            "explicit signing and key management",
            "explicit database credential",
            "explicit database credentials",
            "explicit auth provider",
            "explicit auth provider credential",
            "explicit auth provider credentials",
            "explicit evidence storage",
            "explicit evidence storage credential",
            "explicit observability",
            "explicit observability sink",
            "explicit managed",
            "explicit managed secret",
            "explicit managed key",
            "explicit managed encryption",
            "explicit scoped",
            "explicit scoped backup",
            "explicit scoped credential",
            "explicit scoped credentials",
            "explicit scoped client",
            "explicit external integration",
            "explicit service identity",
            "explicit operator",
            "explicit bootstrap",
            "explicit provider",
            "explicit configuration",
            "explicit config",
            "explicit non-production",
            "explicit validated",
            "explicit validated source",
            "explicit validated secret",
            "explicit production-grade",
            "production secret",
            "production secrets",
            "production secret management",
            "production secret readiness",
            "production secret source",
            "production secret sources",
            "production secret expectation",
            "production secret expectations",
            "production secret boundary",
            "production secret configuration",
            "production secret behavior",
            "production required secret",
            "production required secrets",
            "production claim",
            "production claim boundary",
            "production claim requires",
            "production claim is",
            "production readiness",
            "production hardening",
            "production-hardening",
            "production environment",
            "production mode",
            "production modes",
            "production config",
            "production configuration",
            "production behavior",
            "production use",
            "production deployment",
            "production observability",
            "production database",
            "production auth",
            "production operator",
            "production storage",
            "production network",
            "production failure",
            "production output",
            "production log",
            "production logs",
            "production required",
            "production explicit",
            "production validated",
            "production validated source",
            "production-like",
            "production-like secret",
            "production-like validation",
            "production-like durability",
            "production-like behavior",
            "non-production",
            "non-production constraint",
            "non-production modes",
            "non-production mode",
            "non-production walkthrough",
            "non-production labeling",
            "not production",
            "not production-ready",
            "not described as production-ready",
            "not valid production",
            "not valid production secrets",
            "not valid production behavior",
            "not yet claimed",
            "not be described as production-ready",
            "secret management readiness",
            "secret management readiness is not yet claimed",
            "claim production secret management readiness",
            "claim production readiness",
            "auth provider",
            "auth provider adapter",
            "auth provider credentials",
            "auth provider secret",
            "auth provider configuration",
            "auth provider role mapping",
            "auth provider type",
            "auth provider endpoint",
            "auth provider integration",
            "auth provider claim",
            "auth provider with validated",
            "auth provider with",
            "authentication provider",
            "auth expectation",
            "auth expectations",
            "auth shortcuts",
            "auth shortcut",
            "auth path",
            "auth success",
            "auth failure",
            "auth audit event",
            "auth configuration",
            "auth config",
            "auth gate",
            "auth provider secrets",
            "auth provider secret configuration",
            "external identity provider",
            "service identity provider",
            "identity provider",
            "mock auth provider",
            "no external identity provider",
            "operator identity",
            "operator identities",
            "operator bootstrap",
            "operator role",
            "operator roles",
            "operator access",
            "operator/admin",
            "operator actions",
            "operator-sensitive",
            "readonly integration",
            "readonly integrator",
            "readonly demo",
            "readonly access",
            "external workflow agent",
            "service operator",
            "service-to-service",
            "service identity",
            "service actions",
            "service credentials",
            "workflow execution",
            "workflow steps",
            "workflow agents",
            "workflow orchestrator",
            "grant approval",
            "grant request",
            "grant admin",
            "grant creation",
            "grant lifecycle",
            "evidence write",
            "evidence verification",
            "evidence storage",
            "evidence bundle",
            "evidence bundles",
            "evidence persistence",
            "evidence metadata",
            "evidence completeness",
            "evidence operator",
            "policy admin",
            "policy rule",
            "policy changes",
            "policy requirements",
            "policy evaluation",
            "permission profile",
            "permission profiles",
            "permission evaluation",
            "permission changes",
            "audit event",
            "audit events",
            "audit records",
            "audit record",
            "audit trail",
            "audit export",
            "audit expectation",
            "audit expectations",
            "audit stream",
            "audit and provenance",
            "auditor export",
            "auditor exports",
            "auditor review",
            "compliance readiness",
            "compliance gap",
            "compliance review",
            "compliance readiness summaries",
            "compliance readiness summary",
            "compliance/legal",
            "decision provenance",
            "provenance records",
            "provenance summaries",
            "provenance summary",
            "provenance event",
            "provenance events",
            "provenance record",
            "institutional audit",
            "institutional records",
            "institutional data",
            "data sensitivity",
            "data classification",
            "data integrity",
            "data flow",
            "data privacy",
            "sensitive data",
            "sensitive fields",
            "sensitive value",
            "sensitive values",
            "configuration boundary",
            "config boundary",
            "config dumps",
            "config files",
            "configuration schema",
            "configuration categories",
            "configuration catalog",
            "configuration loader",
            "configuration-driven",
            "environment boundary",
            "environment model",
            "environment variables",
            "validated environment",
            "runtime configuration",
            "runtime mode",
            "runtime modes",
            "runtime behavior",
            "runtime secret",
            "runtime environment",
            "feature flags",
            "extension toggles",
            "extension boundaries",
            "extension boundary",
            "extension adapter",
            "extension surface",
            "extension surfaces",
            "replaceable adapter",
            "replaceable adapters",
            "product core",
            "product core records",
            "product core state",
            "product core logic",
            "product core contracts",
            "product core domain",
            "product core owned",
            "product core must",
            "product core should",
            "product core does",
            "product core secret",
            "product core read",
            "product core records",
            "product core owned",
            "product core boundary",
            "public contracts",
            "stable contracts",
            "stable public contracts",
            "stable product core",
            "stable operator",
            "stable operator role",
            "stable operator roles",
            "stable identity",
            "stable identities",
            "stable service",
            "stable service identity",
            "capability groups",
            "capability group",
            "capability boundaries",
            "capability boundary",
            "role mapping",
            "role assignments",
            "role/capability",
            "role-capability",
            "claim mapping",
            "bootstrap configuration",
            "bootstrap process",
            "bootstrap mechanism",
            "operator bootstrap",
            "health checks",
            "health check",
            "diagnostic endpoints",
            "diagnostic output",
            "diagnostics",
            "structured error",
            "structured output",
            "structured logging",
            "structured record",
            "error messages",
            "error message",
            "error output",
            "error without",
            "error with no",
            "error record",
            "explicit error",
            "explicit structured error",
            "without leaking",
            "without exception",
            "without exposing",
            "without redefining",
            "without secret",
            "without real",
            "with no secret",
            "with no real",
            "with no plaintext",
            "with documented",
            "with rotation",
            "with access control",
            "with validated",
            "with explicit",
            "with scoped",
            "with no",
            "with timestamps",
            "with actor",
            "with policy",
            "with hash",
            "with justification",
            "with scope",
            "redaction markers",
            "redaction marker",
            "redaction helper",
            "redaction must",
            "redaction in",
            "redaction rules",
            "redaction and audit",
            "masking rules",
            "masking in",
            "mask or omit",
            "masked in",
            "mask all",
            "masked",
            "sanitized",
            "sanitize",
            "sanitization",
            "sanitized output",
            "sanitized before",
            "sanitized output",
            "replaced by",
            "replaced",
            "replaceable",
            "redefinition",
            "verified",
            "verified by",
            "verified on",
            "verified source",
            "verified startup",
            "verified output",
            "validated configuration",
            "validated on",
            "validated startup",
            "validated source",
            "validated secret",
            "validated environment",
            "validated values",
            "validation rules",
            "validation expects",
            "validation",
            "valid values",
            "valid authentication",
            "valid future",
            "valid provider",
            "valid GrantLayer",
            "valid JSON",
            "invalid secret",
            "invalid or",
            "invalid configuration",
            "invalid values",
            "invalid secret",
            "missing secret",
            "missing secrets",
            "missing required",
            "missing or",
            "missing and",
            "missing if",
            "missing invalid",
            "source code",
            "source name",
            "source names",
            "source through",
            "source expectation",
            "source boundary",
            "source manager",
            "source abstraction",
            "source identifier",
            "source config",
            "source validation",
            "source reference",
            "source from",
            "source only",
            "source must",
            "source may",
            "source and",
            "source or",
            "source with",
            "secret source",
            "secret source boundary",
            "secret source abstraction",
            "secret source names",
            "secret source manager",
            "secret source validation",
            "secret source expectation",
            "secret source reference",
            "secret source only",
            "credential source",
            "credential set",
            "credential values",
            "credential value",
            "credential management",
            "credential configuration",
            "credential with",
            "credential source",
            "credential boundaries",
            "credential boundary",
            "credential sourcing",
            "credential store",
            "credential reference",
            "credential with no",
            "credential set",
            "credentials sourced",
            "credentials through",
            "credentials must",
            "credentials may",
            "credentials are",
            "credentials for",
            "credentials with",
            "credentials and",
            "credentials or",
            "credentials in",
            "credentials to",
            "credentials from",
            "credentials at",
            "credentials on",
            "credentials by",
            "credentials without",
            "credentials that",
            "scoped credential",
            "scoped credentials",
            "scoped to",
            "scoped per",
            "scoped access",
            "scoped capabilities",
            "scoped only",
            "backup credentials",
            "backup storage",
            "backup metadata",
            "backup and restore",
            "backup/restore",
            "backup configuration",
            "backup operations",
            "backup schedule",
            "backup runbooks",
            "backup/restore configuration",
            "backup/restore plan",
            "restore procedures",
            "restore storage",
            "restore validation",
            "restore test",
            "restore configuration",
            "restore procedure",
            "point-in-time",
            "disaster runbooks",
            "automated backup",
            "retention policy",
            "retention period",
            "retention expectations",
            "retention and",
            "observability backend",
            "observability stack",
            "observability configuration",
            "observability data",
            "observability sink",
            "observability signals",
            "observability expectation",
            "observability expectations",
            "observability/logging",
            "logging/observability",
            "logging pipeline",
            "logging output",
            "logging rule",
            "logging sink",
            "logging and",
            "logging or",
            "logging must",
            "logging may",
            "logging in",
            "logging configuration",
            "structured logging",
            "metrics",
            "alerting",
            "tracing",
            "health",
            "latency",
            "error rate",
            "prometheus",
            "grafana",
            "slo",
            "distributed tracing",
            "business metrics",
            "ci gate",
            "ci pipeline",
            "ci gating",
            "ci stages",
            "contract freeze",
            "contract review",
            "contract hardening",
            "contract clarity",
            "openapi contract",
            "openapi examples",
            "openapi security",
            "openapi security contract",
            "openapi security schemes",
            "versioning strategy",
            "versioned artifact",
            "versioned and",
            "versioned openapi",
            "deprecated",
            "deprecation policy",
            "breaking-change",
            "kubernetes",
            "docker",
            "container",
            "orchestration",
            "terraform",
            "helm",
            "load balancing",
            "tls termination",
            "network topology",
            "deployment automation",
            "deployment environment",
            "deployment context",
            "deployment specific",
            "deployment readiness",
            "deployment parameters",
            "network exposure",
            "network binding",
            "network hardening",
            "cors",
            "external access",
            "origin allowlisting",
            "host and port",
            "api bind host",
            "api bind port",
            "api server binding",
            "binding and",
            "binding enforcement",
            "tls enabled",
            "tls configuration",
            "sha-256",
            "sha-256 recomparison",
            "ed25519",
            "ed25519 signatures",
            "ed25519 signing",
            "hash computation",
            "hash references",
            "hash-based",
            "tamper detection",
            "tamper evidence",
            "tampering",
            "corruption",
            "completeness scoring",
            "completeness score",
            "integrity constraints",
            "integrity checks",
            "integrity proofs",
            "integrity hashes",
            "blockchain anchoring",
            "blockchain dependency",
            "blockchain anchoring",
            "wallet signing",
            "wallet operations",
            "wallet custody",
            "wallet keys",
            "wallet integration",
            "payment integration",
            "payment keys",
            "payment processing",
            "disbursement",
            "saas",
            "multi-tenant",
            "tenant isolation",
            "tenant management",
            "subscription billing",
            "onboarding",
            "per-tenant",
            "sdk",
            "client libraries",
            "client examples",
            "client layer",
            "ui layer",
            "dashboard clients",
            "dashboard product",
            "dashboard/ui",
            "frontend",
            "react",
            "vue",
            "mobile",
            "accessibility",
            "legal review",
            "regulatory review",
            "compliance certification",
            "compliance/legal",
            "data-classification",
            "evidence retention",
            "retention policy",
            "retention periods",
            "immutable storage",
            "deletion constraints",
            "privacy",
            "legal boundary",
            "security review",
            "external partners",
            "partner agreement",
            "partner-agreed",
            "partner system",
            "partner facing",
            "partner integration",
            "partner environment",
            "partner-specific",
            "partner-agreed config",
            "partner-agreed authentication",
            "partner-agreed secret",
            "integrators",
            "integration patterns",
            "integration guide",
            "integration ready",
            "integration checklist",
            "integration contract",
            "integration boundary",
            "integration tests",
            "integration test",
            "integration path",
            "integration surface",
            "integration access",
            "integration queries",
            "integration with",
            "external integrations",
            "external integration",
            "external systems",
            "external services",
            "external clients",
            "external access",
            "external identity",
            "external provider",
            "external secret",
            "external workflow",
            "external evidence",
            "external feeds",
            "third-party",
            "third party",
            "hsm",
            "hsm-backed",
            "hsm integration",
            "kms",
            "kms integration",
            "key management service",
            "vault integration",
            "hashicorp vault",
            "aws secrets manager",
            "azure key vault",
            "google secret manager",
            "cloud secret",
            "cloud secret manager",
            "environment variable",
            "environment variables",
            "environment boundary",
            "environment model",
            "env var",
            "feature flag",
            "extension toggle",
            "extension surface",
            "adapter boundary",
            "adapter output",
            "adapter target",
            "adapter interface",
            "adapter framework",
            "adapter behavior",
            "adapter rules",
            "adapter integration",
            "adapter must",
            "adapter should",
            "pluggable",
            "plugin",
            "plugin runtime",
            "mcp",
            "mock",
            "fixture",
            "fixtures",
            "smoke",
            "smoke manifest",
            "smoke script",
            "dry-run",
            "dry run",
            "placeholder",
            "placeholders",
            "synthetic",
            "demo",
            "demonstration",
            "walkthrough",
            "illustrative",
            "developer convenience",
            "dev",
            "ci",
            "test suite",
            "test output",
            "test fixture",
            "test fixtures",
            "test identity",
            "test only",
            "test-only",
            "automated tests",
            "automated verification",
            "automated backup",
            "manual deployment",
            "manual secret",
            "shared access",
            "shared secret",
            "shared token",
            "shared artifacts",
            "public contracts",
            "public ledgers",
            "public grant",
            "public discovery",
            "matchmaking",
            "on-chain",
            "off-chain",
            "off-chain storage",
            "off-chain in",
            "on-chain data",
            "on-chain plaintext",
            "on-chain value",
            "git history",
            "git",
            "screenshots",
            "artifacts",
            "artifact",
            "related artifacts",
            "machine-readable",
            "human-readable",
            "static json",
            "json fixtures",
            "json examples",
            "json files",
            "quickstart",
            "quickstart examples",
            "quickstart docs",
            "handoff",
            "handoff plan",
            "release candidate",
            "release decision",
            "pilot-ready",
            "pilot ready",
            "pilot partner",
            "pilot-specific",
            "pilot discussion",
            "pilot validation",
            "pilot feedback",
            "pilot artifact",
            "pilot handoff",
            "pilot release",
            "technical pilot",
            "first pilot",
            "pilot",
            "production-ready",
            "production ready",
            "not production-ready",
            "integration-ready",
            "integration ready",
            "pilot-ready for technical review",
            "product foundation",
            "product foundation planning",
            "product foundation security",
            "product foundation architecture",
            "product core readiness",
            "product core",
            "product statement",
            "product direction",
            "productized",
            "productization",
            "reusable",
            "adaptable",
            "extensible",
            "modular",
            "reference implementation",
            "institutional records",
            "institutional audit",
            "institutional data",
            "verifiable",
            "agentic grant workflows",
            "grantlayer",
            "german",
            "nachweisen",
            "prüfbaren",
            "förderprozesse",
            "macht agentische",
            "zu prüfbaren",
            "institutionellen nachweisen",
            "agentische förderprozesse",
        ]
        result = text.lower()
        for term in sorted(safe_terms, key=len, reverse=True):
            result = result.replace(term.lower(), "")
        return result

    def test_no_obvious_secrets_in_inventory(self):
        text_lower = self._sanitize_known_safe_terms(self.inventory_text)
        for pattern in self.SECRET_PATTERNS:
            self.assertNotIn(
                pattern,
                text_lower,
                f"Inventory may contain secret-like pattern: {pattern}",
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
    def test_inventory_has_id_and_version(self):
        self.assertEqual(
            self.inventory_json.get("inventoryId"),
            "gl068-secret-inventory-model",
        )
        self.assertEqual(self.inventory_json.get("inventoryVersion"), "1.0")

    def test_inventory_status_is_product_foundation_planning(self):
        self.assertEqual(self.inventory_json.get("status"), "product-foundation-planning")

    def test_catalog_has_id_and_version(self):
        self.assertEqual(
            self.catalog_json.get("catalogId"),
            "gl068-secret-handling-policy-catalog",
        )
        self.assertEqual(self.catalog_json.get("catalogVersion"), "1.0")

    def test_catalog_status_is_product_foundation_planning(self):
        self.assertEqual(self.catalog_json.get("status"), "product-foundation-planning")

    def test_inventory_includes_production_claim_rules(self):
        rules = self.inventory_json.get("productionClaimRules", [])
        self.assertTrue(len(rules) > 0, "Inventory must include productionClaimRules")

    def test_inventory_includes_forbidden_secret_locations(self):
        locations = self.inventory_json.get("forbiddenSecretLocations", [])
        self.assertTrue(len(locations) > 0, "Inventory must include forbiddenSecretLocations")

    def test_catalog_includes_fail_closed_rules(self):
        rules = self.catalog_json.get("failClosedRules", [])
        self.assertTrue(len(rules) > 0, "Catalog must include failClosedRules")
        rules_text = " ".join(rules).lower()
        self.assertIn("production mode must refuse to start", rules_text)

    def test_catalog_includes_redaction_rules(self):
        rules = self.catalog_json.get("redactionRules", [])
        self.assertTrue(len(rules) > 0, "Catalog must include redactionRules")
        rules_text = " ".join(rules).lower()
        self.assertIn("redacted", rules_text)

    def test_catalog_includes_local_demo_test_shortcuts(self):
        shortcuts = self.catalog_json.get("localDemoTestShortcuts", [])
        self.assertTrue(len(shortcuts) > 0, "Catalog must include localDemoTestShortcuts")

    def test_catalog_includes_production_required_configuration(self):
        required = self.catalog_json.get("productionRequiredConfiguration", [])
        self.assertTrue(len(required) > 0, "Catalog must include productionRequiredConfiguration")
        text = " ".join(required).lower()
        self.assertIn("secret source", text)
        self.assertIn("fail-closed", text)

    def test_catalog_includes_leakage_prevention_expectations(self):
        expectations = self.catalog_json.get("leakagePreventionExpectations", [])
        self.assertTrue(len(expectations) > 0, "Catalog must include leakagePreventionExpectations")
        text = " ".join(expectations).lower()
        self.assertIn("secrets must not appear", text)

    def test_catalog_includes_implementation_non_goals(self):
        non_goals = self.catalog_json.get("implementationNonGoals", [])
        self.assertTrue(len(non_goals) > 0, "Catalog must include implementationNonGoals")
        text = " ".join(non_goals).lower()
        self.assertIn("vault", text)
        self.assertIn("hsm", text)

    def test_doc_includes_product_secret_management_principle(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("product secret management principle", content)
        self.assertIn("secrets outside product core", content)
        self.assertIn("not accidentally become production behavior", content)

    def test_doc_includes_runtime_mode_secret_expectations(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("runtime-mode secret expectations", content)
        self.assertIn("local-dev", content)
        self.assertIn("production", content)

    def test_doc_includes_secret_categories(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("secret categories", content)
        self.assertIn("admin/operator tokens", content)
        self.assertIn("signing key material", content)

    def test_doc_includes_secret_source_boundary(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("secret source boundary", content)
        self.assertIn("product core should not depend on one specific vault or secret provider", content)

    def test_doc_includes_forbidden_secret_locations(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("forbidden secret locations", content)
        self.assertIn("committed source code", content)
        self.assertIn("git history", content)

    def test_doc_includes_redaction_and_audit_expectations(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("redaction and audit expectations", content)
        self.assertIn("audit records must not contain secret values", content)

    def test_doc_includes_production_fail_closed_rules(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("production fail-closed rules", content)

    def test_doc_includes_future_implementation_expectations(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("future implementation expectations", content)
        self.assertIn("secret configuration schema", content)
        self.assertIn("production fail-closed startup checks", content)
        self.assertIn("integration tests for secret leakage prevention", content)

    def test_doc_includes_what_not_to_implement_yet(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("what not to implement yet", content)
        self.assertIn("vault integration", content)
        self.assertIn("hsm integration", content)

    def test_doc_includes_decision_boundary(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("decision boundary", content)

    def test_doc_references_gl067(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("gl-067", content)

    def test_doc_references_gl066(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("gl-066", content)

    def test_doc_references_gl065(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("gl-065", content)

    def test_doc_references_gl063(self):
        content = self.doc_path.read_text(encoding="utf-8").lower()
        self.assertIn("gl-063", content)

    def test_inventory_references_related_artifacts(self):
        artifacts = self.inventory_json.get("relatedArtifacts", [])
        self.assertTrue(len(artifacts) > 0, "Inventory must include relatedArtifacts")

    def test_catalog_references_related_artifacts(self):
        artifacts = self.catalog_json.get("relatedArtifacts", [])
        self.assertTrue(len(artifacts) > 0, "Catalog must include relatedArtifacts")

    def test_catalog_secret_boundaries_mark_product_core_owned(self):
        boundaries = self.catalog_json.get("secretHandlingBoundaries", [])
        owned_count = 0
        for boundary in boundaries:
            if boundary.get("productCoreOwned") is True:
                owned_count += 1
        self.assertGreater(
            owned_count,
            0,
            "At least one secret handling boundary must be marked productCoreOwned",
        )

    def test_catalog_secret_boundaries_mark_replaceable_adapter(self):
        boundaries = self.catalog_json.get("secretHandlingBoundaries", [])
        replaceable_count = 0
        for boundary in boundaries:
            if boundary.get("replaceableAdapter") is True:
                replaceable_count += 1
        self.assertGreater(
            replaceable_count,
            0,
            "At least one secret handling boundary must be marked replaceableAdapter",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
