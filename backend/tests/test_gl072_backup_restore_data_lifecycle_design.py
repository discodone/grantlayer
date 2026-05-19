"""Tests for GL-072 Backup, Restore, and Data Lifecycle Design.

Lightweight validation test proving the backup, restore, and data lifecycle design is:
- present as a human-readable document
- present as machine-readable JSON files
- explicitly defining backup/restore boundaries, data categories, lifecycle policies,
  retention baselines, immutability expectations, and security rules
- free of obvious secrets
- not introducing forbidden implementation files
"""

import json
import pathlib
import unittest


class TestGL072BackupRestoreDataLifecycleDesign(unittest.TestCase):
    """GL-072: Validate backup, restore, and data lifecycle design."""

    REPO_ROOT = pathlib.Path(__file__).with_suffix("").parent.parent.parent
    DOCS_DIR = REPO_ROOT / "docs"
    EXAMPLE_DIR_GL072 = DOCS_DIR / "examples" / "gl072"
    BACKEND_SRC_DIR = REPO_ROOT / "backend" / "src"

    REQUIRED_DATA_CATEGORIES = [
        "grant_requests",
        "grants",
        "grant_executions",
        "evidence_metadata",
        "evidence_payload_references",
        "provenance_events",
        "audit_events",
        "approval_records",
        "policy_requirement_results",
        "compliance_gap_reports",
        "configuration_records",
        "operational_logs",
        "secrets",
    ]

    REQUIRED_LIFECYCLE_STATES = [
        "active",
        "archived",
        "retained_for_audit",
        "retained_for_legal_hold",
        "expired",
        "deletion_pending",
        "deleted_or_purged",
    ]

    FORBIDDEN_PATH_PATTERNS = [
        BACKEND_SRC_DIR / "backup.py",
        BACKEND_SRC_DIR / "restore.py",
        BACKEND_SRC_DIR / "lifecycle.py",
        BACKEND_SRC_DIR / "retention.py",
        BACKEND_SRC_DIR / "scheduler.py",
        BACKEND_SRC_DIR / "s3_storage.py",
        BACKEND_SRC_DIR / "object_storage.py",
        BACKEND_SRC_DIR / "export.py",
        BACKEND_SRC_DIR / "import.py",
        BACKEND_SRC_DIR / "purge.py",
    ]

    @classmethod
    def setUpClass(cls):
        cls.doc_path = cls.DOCS_DIR / "backup_restore_data_lifecycle_design.md"
        cls.scope_matrix_path = cls.EXAMPLE_DIR_GL072 / "backup_restore_scope_matrix.json"
        cls.policy_catalog_path = cls.EXAMPLE_DIR_GL072 / "data_lifecycle_policy_catalog.json"

        cls.scope_matrix_json = None
        if cls.scope_matrix_path.exists():
            cls.scope_matrix_json = json.loads(cls.scope_matrix_path.read_text(encoding="utf-8"))

        cls.policy_catalog_json = None
        if cls.policy_catalog_path.exists():
            cls.policy_catalog_json = json.loads(cls.policy_catalog_path.read_text(encoding="utf-8"))

        cls.doc_text = ""
        if cls.doc_path.exists():
            cls.doc_text = cls.doc_path.read_text(encoding="utf-8")

    # ── 1. Design document exists ─────────────────────────────────────
    def test_design_doc_exists(self):
        self.assertTrue(
            self.doc_path.exists(),
            "docs/backup_restore_data_lifecycle_design.md must exist",
        )

    # ── 2. Backup/restore scope matrix JSON exists and parses ─────────
    def test_scope_matrix_exists_and_parses(self):
        self.assertTrue(
            self.scope_matrix_path.exists(),
            "docs/examples/gl072/backup_restore_scope_matrix.json must exist",
        )
        self.assertIsNotNone(self.scope_matrix_json, "Scope matrix must parse as valid JSON")
        self.assertIsInstance(self.scope_matrix_json, dict)

    # ── 3. Data lifecycle policy catalog JSON exists and parses ───────
    def test_policy_catalog_exists_and_parses(self):
        self.assertTrue(
            self.policy_catalog_path.exists(),
            "docs/examples/gl072/data_lifecycle_policy_catalog.json must exist",
        )
        self.assertIsNotNone(self.policy_catalog_json, "Policy catalog must parse as valid JSON")
        self.assertIsInstance(self.policy_catalog_json, dict)

    # ── 4. Scope matrix includes all required data categories ─────────
    def test_scope_matrix_includes_required_categories(self):
        categories = self.scope_matrix_json.get("dataCategories", [])
        found_categories = {c.get("category") for c in categories}
        for expected in self.REQUIRED_DATA_CATEGORIES:
            with self.subTest(category=expected):
                self.assertIn(
                    expected,
                    found_categories,
                    f"Scope matrix must include data category '{expected}'",
                )

    # ── 5. Scope matrix marks secrets as not eligible for ordinary backup
    def test_scope_matrix_secrets_not_ordinary_backup(self):
        categories = self.scope_matrix_json.get("dataCategories", [])
        secrets_entry = None
        for c in categories:
            if c.get("category") == "secrets":
                secrets_entry = c
                break
        self.assertIsNotNone(secrets_entry, "secrets category must exist")
        self.assertFalse(
            secrets_entry.get("backupRequired", True),
            "secrets must not be marked as backupRequired"
        )
        notes = (secrets_entry.get("backupNotes") or "").lower()
        self.assertIn("must not", notes, "secrets backupNotes must indicate exclusion")

    # ── 6. Lifecycle policy catalog includes all required lifecycle states
    def test_policy_catalog_includes_required_states(self):
        policies = self.policy_catalog_json.get("policies", [])
        found_states = {p.get("state") for p in policies}
        for expected in self.REQUIRED_LIFECYCLE_STATES:
            with self.subTest(state=expected):
                self.assertIn(
                    expected,
                    found_states,
                    f"Policy catalog must include lifecycle state '{expected}'",
                )

    # ── 7. Lifecycle policy catalog marks implementation as design_only / not implemented
    def test_policy_catalog_implementation_status_design_only(self):
        policies = self.policy_catalog_json.get("policies", [])
        for policy in policies:
            status = policy.get("implementationStatus", "").lower()
            self.assertIn(
                status,
                {"design_only", "not-implemented"},
                f"Policy '{policy.get('state')}' must have implementationStatus design_only or not-implemented",
            )

    # ── 8. Design doc states no backup implementation is added in GL-072
    def test_doc_states_no_backup_implementation(self):
        content = self.doc_text.lower()
        self.assertIn(
            "gl-072 adds no backup implementation",
            content,
        )

    # ── 9. Design doc states no restore implementation is added in GL-072
    def test_doc_states_no_restore_implementation(self):
        content = self.doc_text.lower()
        self.assertIn(
            "gl-072 adds no restore implementation",
            content,
        )

    # ── 10. Design doc states no lifecycle automation is added in GL-072
    def test_doc_states_no_lifecycle_automation(self):
        content = self.doc_text.lower()
        self.assertIn(
            "gl-072 adds no lifecycle automation",
            content,
        )

    # ── 11. Design doc states no retention job is added in GL-072
    def test_doc_states_no_retention_job(self):
        content = self.doc_text.lower()
        self.assertIn(
            "gl-072 adds no retention job",
            content,
        )

    # ── 12. Design doc distinguishes product data, audit records, provenance records,
    #         evidence metadata, runtime config, secrets, and operational logs
    def test_doc_distinguishes_data_domains(self):
        content = self.doc_text.lower()
        self.assertIn("product records", content)
        self.assertIn("audit records", content)
        self.assertIn("provenance records", content)
        self.assertIn("evidence metadata", content)
        self.assertIn("runtime configuration", content)
        self.assertIn("secrets", content)
        self.assertIn("operational logs", content)

    # ── 13. Design doc does not claim production-readiness
    def test_doc_does_not_claim_production_readiness(self):
        content = self.doc_text.lower()
        self.assertIn(
            "gl-072 does not make grantlayer production-ready",
            content,
        )

    # ── 14. No forbidden implementation files are created ─────────────
    def test_no_forbidden_implementation_files_created(self):
        for path in self.FORBIDDEN_PATH_PATTERNS:
            self.assertFalse(
                path.exists(),
                f"Forbidden implementation file must not exist: {path}",
            )
