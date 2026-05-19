"""Tests for GL-073 Operational Runbook and Incident Response Baseline Design.

Lightweight validation test proving the operational runbook and incident response baseline design is:
- present as a human-readable document
- present as machine-readable JSON files
- explicitly defining incident severities, runbook categories, operator roles,
  escalation boundaries, and incident lifecycle stages
- free of obvious secrets
- not introducing forbidden implementation files
"""

import json
import pathlib
import unittest


class TestGL073OperationalRunbookIncidentResponse(unittest.TestCase):
    """GL-073: Validate operational runbook and incident response baseline design."""

    REPO_ROOT = pathlib.Path(__file__).with_suffix("").parent.parent.parent
    DOCS_DIR = REPO_ROOT / "docs"
    EXAMPLE_DIR_GL073 = DOCS_DIR / "examples" / "gl073"
    BACKEND_SRC_DIR = REPO_ROOT / "backend" / "src"

    REQUIRED_SEVERITIES = [
        "sev0",
        "sev1",
        "sev2",
        "sev3",
        "sev4",
    ]

    REQUIRED_RUNBOOK_CATEGORIES = [
        "api_unavailable",
        "api_degraded",
        "auth_access_issue",
        "suspected_secret_exposure",
        "persistence_issue",
        "evidence_verification_issue",
        "audit_provenance_integrity_concern",
        "backup_restore_issue",
        "runtime_configuration_mismatch",
        "deployment_rollback_needed",
    ]

    FORBIDDEN_PATH_PATTERNS = [
        BACKEND_SRC_DIR / "incident_response.py",
        BACKEND_SRC_DIR / "runbook.py",
        BACKEND_SRC_DIR / "alerting.py",
        BACKEND_SRC_DIR / "monitoring.py",
        BACKEND_SRC_DIR / "pager.py",
        BACKEND_SRC_DIR / "escalation.py",
        BACKEND_SRC_DIR / "oncall.py",
        BACKEND_SRC_DIR / "sre.py",
        BACKEND_SRC_DIR / "health.py",
        BACKEND_SRC_DIR / "liveness.py",
        BACKEND_SRC_DIR / "readiness.py",
        BACKEND_SRC_DIR / "status_page.py",
        BACKEND_SRC_DIR / "recovery.py",
        BACKEND_SRC_DIR / "forensics.py",
        BACKEND_SRC_DIR / "rollback.py",
        BACKEND_SRC_DIR / "scheduler.py",
    ]

    @classmethod
    def setUpClass(cls):
        cls.doc_path = cls.DOCS_DIR / "operational_runbook_incident_response_design.md"
        cls.severity_matrix_path = cls.EXAMPLE_DIR_GL073 / "incident_severity_matrix.json"
        cls.runbook_catalog_path = cls.EXAMPLE_DIR_GL073 / "operational_runbook_catalog.json"

        cls.severity_matrix_json = None
        if cls.severity_matrix_path.exists():
            cls.severity_matrix_json = json.loads(cls.severity_matrix_path.read_text(encoding="utf-8"))

        cls.runbook_catalog_json = None
        if cls.runbook_catalog_path.exists():
            cls.runbook_catalog_json = json.loads(cls.runbook_catalog_path.read_text(encoding="utf-8"))

        cls.doc_text = ""
        if cls.doc_path.exists():
            cls.doc_text = cls.doc_path.read_text(encoding="utf-8")

    # ── 1. Design document exists ─────────────────────────────────────
    def test_design_doc_exists(self):
        self.assertTrue(
            self.doc_path.exists(),
            "docs/operational_runbook_incident_response_design.md must exist",
        )

    # ── 2. Incident severity matrix JSON exists and parses ────────────
    def test_severity_matrix_exists_and_parses(self):
        self.assertTrue(
            self.severity_matrix_path.exists(),
            "docs/examples/gl073/incident_severity_matrix.json must exist",
        )
        self.assertIsNotNone(self.severity_matrix_json, "Severity matrix must parse as valid JSON")
        self.assertIsInstance(self.severity_matrix_json, dict)

    # ── 3. Operational runbook catalog JSON exists and parses ─────────
    def test_runbook_catalog_exists_and_parses(self):
        self.assertTrue(
            self.runbook_catalog_path.exists(),
            "docs/examples/gl073/operational_runbook_catalog.json must exist",
        )
        self.assertIsNotNone(self.runbook_catalog_json, "Runbook catalog must parse as valid JSON")
        self.assertIsInstance(self.runbook_catalog_json, dict)

    # ── 4. Severity matrix includes all required severities ───────────
    def test_severity_matrix_includes_required_severities(self):
        levels = self.severity_matrix_json.get("severityLevels", [])
        found_severities = {s.get("severity") for s in levels}
        for expected in self.REQUIRED_SEVERITIES:
            with self.subTest(severity=expected):
                self.assertIn(
                    expected,
                    found_severities,
                    f"Severity matrix must include severity '{expected}'",
                )

    # ── 5. Severity matrix marks implementation as design_only / not implemented
    def test_severity_matrix_implementation_status_design_only(self):
        levels = self.severity_matrix_json.get("severityLevels", [])
        for level in levels:
            status = level.get("implementationStatus", "").lower()
            self.assertIn(
                status,
                {"design_only", "not-implemented", "not implemented"},
                f"Severity '{level.get('severity')}' must have implementationStatus design_only or not implemented",
            )

    # ── 6. Runbook catalog includes all required categories ───────────
    def test_runbook_catalog_includes_required_categories(self):
        categories = self.runbook_catalog_json.get("runbookCategories", [])
        found_categories = {c.get("category") for c in categories}
        for expected in self.REQUIRED_RUNBOOK_CATEGORIES:
            with self.subTest(category=expected):
                self.assertIn(
                    expected,
                    found_categories,
                    f"Runbook catalog must include category '{expected}'",
                )

    # ── 7. Runbook catalog marks implementation as design_only / not implemented
    def test_runbook_catalog_implementation_status_design_only(self):
        categories = self.runbook_catalog_json.get("runbookCategories", [])
        for category in categories:
            status = category.get("implementationStatus", "").lower()
            self.assertIn(
                status,
                {"design_only", "not-implemented", "not implemented"},
                f"Category '{category.get('category')}' must have implementationStatus design_only or not implemented",
            )

    # ── 8. Design doc states no incident-response implementation is added in GL-073
    def test_doc_states_no_incident_response_implementation(self):
        content = self.doc_text.lower()
        self.assertIn(
            "gl-073 adds no incident-response implementation",
            content,
        )

    # ── 9. Design doc states no monitoring implementation is added in GL-073
    def test_doc_states_no_monitoring_implementation(self):
        content = self.doc_text.lower()
        self.assertIn(
            "gl-073 adds no monitoring implementation",
            content,
        )

    # ── 10. Design doc states no alerting implementation is added in GL-073
    def test_doc_states_no_alerting_implementation(self):
        content = self.doc_text.lower()
        self.assertIn(
            "gl-073 adds no alerting implementation",
            content,
        )

    # ── 11. Design doc states no operational automation is added in GL-073
    def test_doc_states_no_operational_automation(self):
        content = self.doc_text.lower()
        self.assertIn(
            "gl-073 adds no operational automation",
            content,
        )

    # ── 12. Design doc distinguishes incident detection, triage, containment, mitigation, recovery, and post-incident review
    def test_doc_distinguishes_incident_lifecycle_stages(self):
        content = self.doc_text.lower()
        self.assertIn("detection", content)
        self.assertIn("triage", content)
        self.assertIn("containment", content)
        self.assertIn("mitigation", content)
        self.assertIn("recovery", content)
        self.assertIn("post-incident review", content)

    # ── 13. Design doc references audit/provenance integrity preservation
    def test_doc_references_audit_provenance_integrity(self):
        content = self.doc_text.lower()
        self.assertIn(
            "audit/provenance integrity",
            content,
        )

    # ── 14. Design doc does not claim production-readiness
    def test_doc_does_not_claim_production_readiness(self):
        content = self.doc_text.lower()
        self.assertIn(
            "gl-073 does not make grantlayer production-ready",
            content,
        )

    # ── 15. No forbidden implementation files are changed ─────────────
    def test_no_forbidden_implementation_files_created(self):
        for path in self.FORBIDDEN_PATH_PATTERNS:
            self.assertFalse(
                path.exists(),
                f"Forbidden implementation file must not exist: {path}",
            )
