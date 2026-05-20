"""Tests for GL-071 Observability and Structured Logging Baseline Design.

Lightweight validation test proving the observability and structured logging baseline design is:
- present as a human-readable document
- present as machine-readable JSON files
- explicitly defining observability boundaries, structured logging rules, correlation IDs,
  event categories, field catalogs, and redaction policies
- free of obvious secrets
- not introducing forbidden implementation files
"""

import json
import pathlib
import unittest


class TestGL071ObservabilityStructuredLoggingBaseline(unittest.TestCase):
    """GL-071: Validate observability and structured logging baseline design."""

    REPO_ROOT = pathlib.Path(__file__).with_suffix("").parent.parent.parent
    DOCS_DIR = REPO_ROOT / "docs"
    EXAMPLE_DIR_GL071 = DOCS_DIR / "examples" / "gl071"
    BACKEND_SRC_DIR = REPO_ROOT / "backend" / "src"
    BACKEND_MIGRATIONS_DIR = REPO_ROOT / "backend" / "src" / "migrations"

    REQUIRED_EVENT_CATEGORIES = [
        "api_request",
        "api_error",
        "auth_event",
        "permission_decision",
        "evidence_verification",
        "approval_transition",
        "policy_evaluation",
        "persistence_operation",
        "configuration_event",
        "operator_action",
    ]

    REQUIRED_CORRELATION_FIELDS = [
        "requestId",
        "correlationId",
        "workflowId",
        "executionId",
        "actorId",
        "agentId",
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
        BACKEND_SRC_DIR / "logging.py",
        BACKEND_SRC_DIR / "logger.py",
        BACKEND_SRC_DIR / "tracing.py",
        BACKEND_SRC_DIR / "opentelemetry.py",
        BACKEND_SRC_DIR / "monitoring.py",
        BACKEND_SRC_DIR / "alerting.py",
        BACKEND_SRC_DIR / "health.py",
        BACKEND_SRC_DIR / "liveness.py",
        BACKEND_SRC_DIR / "readiness.py",
    ]

    @classmethod
    def setUpClass(cls):
        cls.doc_path = cls.DOCS_DIR / "observability_structured_logging_baseline_design.md"
        cls.event_model_path = cls.EXAMPLE_DIR_GL071 / "observability_event_model.json"
        cls.field_catalog_path = cls.EXAMPLE_DIR_GL071 / "structured_logging_field_catalog.json"

        cls.event_model_json = None
        cls.event_model_text = None
        if cls.event_model_path.exists():
            cls.event_model_text = cls.event_model_path.read_text(encoding="utf-8")
            cls.event_model_json = json.loads(cls.event_model_text)

        cls.field_catalog_json = None
        cls.field_catalog_text = None
        if cls.field_catalog_path.exists():
            cls.field_catalog_text = cls.field_catalog_path.read_text(encoding="utf-8")
            cls.field_catalog_json = json.loads(cls.field_catalog_text)

        cls.doc_text = ""
        if cls.doc_path.exists():
            cls.doc_text = cls.doc_path.read_text(encoding="utf-8")

    # ── 1. Design document exists ─────────────────────────────────────
    def test_design_doc_exists(self):
        self.assertTrue(
            self.doc_path.exists(),
            "docs/observability_structured_logging_baseline_design.md must exist",
        )

    # ── 2. Event model JSON exists and parses ─────────────────────────
    def test_event_model_exists_and_parses(self):
        self.assertTrue(
            self.event_model_path.exists(),
            "docs/examples/gl071/observability_event_model.json must exist",
        )
        self.assertIsNotNone(self.event_model_json, "Event model must parse as valid JSON")
        self.assertIsInstance(self.event_model_json, dict)

    # ── 3. Field catalog JSON exists and parses ───────────────────────
    def test_field_catalog_exists_and_parses(self):
        self.assertTrue(
            self.field_catalog_path.exists(),
            "docs/examples/gl071/structured_logging_field_catalog.json must exist",
        )
        self.assertIsNotNone(self.field_catalog_json, "Field catalog must parse as valid JSON")
        self.assertIsInstance(self.field_catalog_json, dict)

    # ── 4. Event model includes all required event categories ─────────
    def test_event_model_includes_required_categories(self):
        event_types = self.event_model_json.get("eventTypeDefinitions", [])
        found_types = {e.get("eventType") for e in event_types}
        for expected in self.REQUIRED_EVENT_CATEGORIES:
            with self.subTest(category=expected):
                self.assertIn(
                    expected,
                    found_types,
                    f"Event model must include event type '{expected}'",
                )

    # ── 5. Field catalog includes required correlation fields ─────────
    def test_field_catalog_includes_correlation_fields(self):
        correlation_fields = self.field_catalog_json.get("fieldDefinitions", {}).get("correlationFields", [])
        found_fields = {f.get("fieldName") for f in correlation_fields}
        for expected in self.REQUIRED_CORRELATION_FIELDS:
            with self.subTest(field=expected):
                self.assertIn(
                    expected,
                    found_fields,
                    f"Field catalog must include correlation field '{expected}'",
                )

    # ── 6. Field catalog explicitly forbids secrets/tokens/private keys
    def test_field_catalog_forbids_secrets_tokens_private_keys(self):
        forbidden = self.field_catalog_json.get("fieldDefinitions", {}).get("forbiddenFields", [])
        forbidden_names = {f.get("fieldName") for f in forbidden}
        self.assertIn("rawSecret", forbidden_names, "rawSecret must be forbidden")
        self.assertIn("accessToken", forbidden_names, "accessToken must be forbidden")
        self.assertIn("privateKey", forbidden_names, "privateKey must be forbidden")
        self.assertIn("fullEvidencePayload", forbidden_names, "fullEvidencePayload must be forbidden")

    # ── 7. Design doc states no observability implementation is added in GL-071
    def test_doc_states_no_observability_implementation(self):
        content = self.doc_text.lower()
        self.assertIn(
            "gl-071 does not implement any observability",
            content,
        )

    # ── 8. Design doc states no logging implementation is added in GL-071
    def test_doc_states_no_logging_implementation(self):
        content = self.doc_text.lower()
        self.assertIn(
            "gl-071 does not implement any logging",
            content,
        )

    # ── 9. Design doc states no metrics/tracing implementation is added in GL-071
    def test_doc_states_no_metrics_tracing_implementation(self):
        content = self.doc_text.lower()
        self.assertIn(
            "gl-071 does not implement any logging, metrics, tracing",
            content,
        )

    # ── 10. Design doc distinguishes operational logs from audit/provenance records
    def test_doc_distinguishes_operational_and_audit_provenance(self):
        content = self.doc_text.lower()
        self.assertIn(
            "operational logs are separate from product audit/provenance records",
            content,
        )

    # ── 11. Design doc documents redaction/sensitive-data rules
    def test_doc_documents_redaction_rules(self):
        content = self.doc_text.lower()
        self.assertIn(
            "sensitive data and secret redaction rules",
            content,
        )
        self.assertIn(
            "secrets, tokens, private keys, and full sensitive payloads must never be logged",
            content,
        )

    # ── 12. Design doc does not claim production-readiness
    def test_doc_does_not_claim_production_readiness(self):
        content = self.doc_text.lower()
        self.assertIn(
            "gl-071 does not make grantlayer production-ready",
            content,
        )

    # ── 13. No forbidden implementation files are changed ─────────────
    def test_no_forbidden_implementation_files_created(self):
        for path in self.FORBIDDEN_PATH_PATTERNS:
            self.assertFalse(
                path.exists(),
                f"Forbidden implementation file must not exist: {path}",
            )
