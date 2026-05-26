"""Tests for GL-131: Pilot Environment Setup Checklist.

Ensures:
- docs/pilot_environment_setup_checklist.md exists and covers required topics.
- docs/examples/gl131/pilot_environment_setup_checklist.json exists and is valid.
- JSON issue_id is GL-131.
- JSON review_only is true.
- JSON deployment_automation_implemented is false.
- JSON infrastructure_provisioning_implemented is false.
- JSON monitoring_backend_implemented is false.
- JSON incident_automation_implemented is false.
- JSON production_code_changed is false.
- Markdown explicitly says no deployment automation is implemented.
- Markdown explicitly says no infrastructure provisioning is implemented.
- Markdown does not claim production SaaS complete.
- Environment identity, runtime/config, secret safety, database, operator,
  required validation commands, monitoring/alerting, incident response,
  backup/restore, pilot go/no-go criteria, related gates, recommended next steps,
  and non-goals are all documented.
- Markdown/JSON do not include obvious raw secret values.
- No forbidden scope changes.

No production code changes required.
No external services required.
"""

import json
import os
import pathlib
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

_MD_PATH = _REPO_ROOT / "docs" / "pilot_environment_setup_checklist.md"
_JSON_PATH = (
    _REPO_ROOT / "docs" / "examples" / "gl131" / "pilot_environment_setup_checklist.json"
)

_SECRET_PATTERNS = [
    re.compile(r"\bpassword\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bsecret\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bapi_key\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bprivate_key\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bpassphrase\s*=\s*\S", re.IGNORECASE),
]


class TestGl131ArtifactsExist(unittest.TestCase):
    """Verify the GL-131 artifacts are present."""

    def test_markdown_exists(self):
        self.assertTrue(
            _MD_PATH.exists(),
            f"docs/pilot_environment_setup_checklist.md must exist at {_MD_PATH}",
        )

    def test_json_exists(self):
        self.assertTrue(
            _JSON_PATH.exists(),
            f"docs/examples/gl131/pilot_environment_setup_checklist.json must exist at {_JSON_PATH}",
        )


class TestGl131JsonStructure(unittest.TestCase):
    """Verify GL-131 JSON structure and values."""

    @classmethod
    def setUpClass(cls):
        raw_json = _JSON_PATH.read_text(encoding="utf-8") if _JSON_PATH.exists() else "{}"
        cls.json_data = json.loads(raw_json)
        cls.json_str = raw_json.lower()

    def test_json_is_valid(self):
        self.assertIsInstance(self.json_data, dict, "JSON must be a top-level object")

    def test_json_issue_id(self):
        self.assertEqual(
            self.json_data.get("issue_id"),
            "GL-131",
            "JSON issue_id must be GL-131",
        )

    def test_json_review_only_is_true(self):
        self.assertIs(
            self.json_data.get("review_only"),
            True,
            "JSON review_only must be true",
        )

    def test_json_deployment_automation_implemented_is_false(self):
        self.assertIs(
            self.json_data.get("deployment_automation_implemented"),
            False,
            "JSON deployment_automation_implemented must be false",
        )

    def test_json_infrastructure_provisioning_implemented_is_false(self):
        self.assertIs(
            self.json_data.get("infrastructure_provisioning_implemented"),
            False,
            "JSON infrastructure_provisioning_implemented must be false",
        )

    def test_json_monitoring_backend_implemented_is_false(self):
        self.assertIs(
            self.json_data.get("monitoring_backend_implemented"),
            False,
            "JSON monitoring_backend_implemented must be false",
        )

    def test_json_incident_automation_implemented_is_false(self):
        self.assertIs(
            self.json_data.get("incident_automation_implemented"),
            False,
            "JSON incident_automation_implemented must be false",
        )

    def test_json_production_code_changed_is_false(self):
        self.assertIs(
            self.json_data.get("production_code_changed"),
            False,
            "JSON production_code_changed must be false",
        )

    def test_json_baseline_type(self):
        self.assertEqual(
            self.json_data.get("baseline_type"),
            "pilot_environment_setup_checklist",
            "JSON baseline_type must be pilot_environment_setup_checklist",
        )


class TestGl131MarkdownContent(unittest.TestCase):
    """Verify GL-131 markdown content meets baseline requirements."""

    @classmethod
    def setUpClass(cls):
        cls.md_content = _MD_PATH.read_text(encoding="utf-8") if _MD_PATH.exists() else ""
        cls.md_lower = cls.md_content.lower()

    def test_markdown_says_no_deployment_automation_implemented(self):
        lower = self.md_lower
        self.assertTrue(
            "no deployment automation" in lower or "not deployment automation" in lower,
            "Markdown must state no deployment automation is implemented",
        )

    def test_markdown_says_no_infrastructure_provisioning_implemented(self):
        lower = self.md_lower
        self.assertTrue(
            "no infrastructure provisioning" in lower or "not infrastructure provisioning" in lower,
            "Markdown must state no infrastructure provisioning is implemented",
        )

    def test_markdown_does_not_claim_production_saas_complete(self):
        lower = self.md_lower
        # "production saas complete" may appear, but only as a negated denial
        idx = lower.find("production saas complete")
        if idx != -1:
            preceding = lower[max(0, idx - 25):idx]
            has_negation = any(
                neg in preceding
                for neg in ["not ", "never ", "no ", "isn't ", "is not ", "not"]
            )
            self.assertTrue(
                has_negation,
                "Markdown must not positively claim 'production SaaS complete'",
            )

    # --- Environment identity requirements ---

    def test_environment_identity_requirements_environment_name(self):
        lower = self.md_lower
        self.assertIn("pilot environment name", lower)

    def test_environment_identity_requirements_owner_operator(self):
        lower = self.md_lower
        self.assertIn("owner", lower)
        self.assertIn("operator", lower)

    def test_environment_identity_requirements_technical_responder(self):
        self.assertIn("technical responder", self.md_lower)

    def test_environment_identity_requirements_business_owner(self):
        self.assertIn("business", self.md_lower)

    def test_environment_identity_requirements_main_release_commit(self):
        lower = self.md_lower
        self.assertIn("main", lower)
        self.assertIn("commit", lower)

    def test_environment_identity_requirements_runtime_mode(self):
        self.assertIn("runtime mode", self.md_lower)

    def test_environment_identity_requirements_database_mode(self):
        self.assertIn("database mode", self.md_lower)

    def test_environment_identity_requirements_pilot_window(self):
        self.assertIn("pilot", self.md_lower)
        self.assertIn("window", self.md_lower)

    # --- Runtime/config checklist ---

    def test_runtime_config_production_like_mode(self):
        lower = self.md_lower
        self.assertIn("production-like", lower)
        self.assertIn("runtime mode", lower)

    def test_runtime_config_no_unapproved_local_test_demo(self):
        lower = self.md_lower
        self.assertIn("local", lower)
        self.assertIn("test", lower)
        self.assertIn("demo", lower)

    def test_runtime_config_startup_fail_closed(self):
        self.assertIn("fail-closed", self.md_lower)

    def test_runtime_config_unsafe_config_rejected(self):
        self.assertIn("unsafe config", self.md_lower)

    def test_runtime_config_runtime_gate(self):
        self.assertIn("run-production-runtime-gate", self.md_lower)

    # --- Secret safety checklist ---

    def test_secret_checklist_admin_token(self):
        self.assertIn("admin token", self.md_lower)

    def test_secret_checklist_operator_token(self):
        self.assertIn("operator token", self.md_lower)

    def test_secret_checklist_db_credentials(self):
        self.assertIn("db url", self.md_lower)
        self.assertIn("credential", self.md_lower)

    def test_secret_checklist_signing_private_keys(self):
        self.assertIn("private key", self.md_lower)
        self.assertIn("signing", self.md_lower)

    def test_secret_checklist_no_secrets_in_docs_logs_screenshots(self):
        lower = self.md_lower
        self.assertIn("no secrets", lower)
        self.assertIn("docs", lower)
        self.assertIn("logs", lower)
        self.assertIn("screenshots", lower)

    def test_secret_checklist_no_raw_authorization_tokens_bodies(self):
        lower = self.md_lower
        self.assertIn("no raw authorization", lower)
        self.assertIn("raw tokens", lower)
        self.assertIn("request bodies", lower)

    # --- Database checklist ---

    def test_database_checklist_sqlite_local_demo_test(self):
        lower = self.md_lower
        self.assertIn("sqlite", lower)
        self.assertIn("local", lower)
        self.assertIn("demo", lower)
        self.assertIn("test", lower)

    def test_database_checklist_postgresql_production_like(self):
        lower = self.md_lower
        self.assertIn("postgresql", lower)
        self.assertIn("production-like", lower)

    def test_database_checklist_migrations(self):
        self.assertIn("migrations", self.md_lower)

    def test_database_checklist_audit_immutability(self):
        self.assertIn("audit immutability", self.md_lower)

    def test_database_checklist_connection_pooling(self):
        self.assertIn("connection pooling", self.md_lower)

    def test_database_checklist_backup_method(self):
        self.assertIn("backup method", self.md_lower)

    # --- Operator checklist ---

    def test_operator_checklist_named_owner(self):
        self.assertIn("named operator owner", self.md_lower)

    def test_operator_checklist_token_expiry_rotation(self):
        self.assertIn("token expiry", self.md_lower)
        self.assertIn("rotation", self.md_lower)

    def test_operator_checklist_revoked_expired_behavior(self):
        self.assertIn("revoked", self.md_lower)
        self.assertIn("expired", self.md_lower)

    def test_operator_checklist_emergency_escalation(self):
        self.assertIn("emergency escalation", self.md_lower)
        self.assertIn("contact", self.md_lower)

    # --- Required validation commands ---

    def test_required_commands_runtime_gate(self):
        self.assertIn("scripts/run-production-runtime-gate.sh", self.md_content)

    def test_required_commands_smoke_tests(self):
        self.assertIn("scripts/run-operational-smoke-tests.sh", self.md_content)

    def test_required_commands_backup_restore_drill(self):
        self.assertIn("scripts/run-backup-restore-drill.sh", self.md_content)

    def test_required_commands_full_suite(self):
        self.assertIn("scripts/run-full-backend-suite.sh", self.md_content)

    # --- Monitoring/alerting checklist ---

    def test_monitoring_alerting_gl129_reference(self):
        self.assertIn("gl-129", self.md_lower)

    def test_monitoring_alerting_alert_owner(self):
        self.assertIn("alert owner", self.md_lower)

    def test_monitoring_alerting_alert_receiver_channel(self):
        lower = self.md_lower
        self.assertIn("alert receiver", lower)
        self.assertIn("channel", lower)

    def test_monitoring_alerting_review_cadence(self):
        self.assertIn("review cadence", self.md_lower)

    # --- Incident response checklist ---

    def test_incident_response_gl130_reference(self):
        self.assertIn("gl-130", self.md_lower)

    def test_incident_response_incident_owner(self):
        self.assertIn("incident owner", self.md_lower)

    def test_incident_response_escalation_path(self):
        self.assertIn("escalation path", self.md_lower)

    def test_incident_response_evidence_capture(self):
        self.assertIn("evidence capture", self.md_lower)

    # --- Backup/restore checklist ---

    def test_backup_restore_backup_method(self):
        self.assertIn("backup method", self.md_lower)

    def test_backup_restore_restore_drill(self):
        self.assertIn("restore drill", self.md_lower)

    def test_backup_restore_isolated_restore(self):
        self.assertIn("isolated restore", self.md_lower)

    def test_backup_restore_no_direct_restore(self):
        lower = self.md_lower
        self.assertIn("no direct restore", lower)
        self.assertIn("pilot", lower)
        self.assertIn("production", lower)

    # --- Pilot go/no-go criteria ---

    def test_pilot_go_no_go_criteria_present(self):
        lower = self.md_lower
        self.assertIn("go", lower)
        self.assertIn("no-go", lower)

    # --- Related gates ---

    def test_related_gates_include_gl125(self):
        self.assertIn("gl-125", self.md_lower)

    def test_related_gates_include_gl126(self):
        self.assertIn("gl-126", self.md_lower)

    def test_related_gates_include_gl127(self):
        self.assertIn("gl-127", self.md_lower)

    def test_related_gates_include_gl128(self):
        self.assertIn("gl-128", self.md_lower)

    def test_related_gates_include_gl129(self):
        self.assertIn("gl-129", self.md_lower)

    def test_related_gates_include_gl130(self):
        self.assertIn("gl-130", self.md_lower)

    # --- Recommended next steps ---

    def test_recommended_next_steps_include_gl132(self):
        self.assertIn("gl-132", self.md_lower)

    # --- Non-goals ---

    def test_explicit_non_goals_present(self):
        lower = self.md_lower
        self.assertIn("non-goals", lower)
        self.assertIn("no deployment automation", lower)
        self.assertIn("no infrastructure provisioning", lower)

    # --- No raw secrets ---

    def test_markdown_no_raw_secrets(self):
        for pattern in _SECRET_PATTERNS:
            for line in self.md_content.splitlines():
                if pattern.search(line):
                    self.fail(
                        f"Markdown must not contain raw secret assignment: {line.strip()}"
                    )

    def test_json_no_raw_secrets(self):
        raw = _JSON_PATH.read_text(encoding="utf-8") if _JSON_PATH.exists() else ""
        for pattern in _SECRET_PATTERNS:
            for line in raw.splitlines():
                if pattern.search(line):
                    self.fail(
                        f"JSON must not contain raw secret assignment: {line.strip()}"
                    )


class TestGl131ScopeGuard(unittest.TestCase):
    """Verify no forbidden files were changed by GL-131."""

    def _changed_files(self):
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        if result.returncode != 0:
            self.skipTest("git diff unavailable; skipping scope guard")
        return result.stdout.strip()

    def test_no_production_code_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("backend/src/"):
                self.fail(f"GL-131 must not change production code: {line}")

    def test_no_openapi_changed(self):
        changed = self._changed_files()
        self.assertNotIn(
            "openapi.yaml",
            changed,
            "GL-131 must not change the OpenAPI specification",
        )

    def test_no_migration_files_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if "migrations/" in line:
                self.fail(f"GL-131 must not change migration files: {line}")

    def test_no_frontend_or_website_files_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("frontend/") or line.startswith("website/"):
                self.fail(f"GL-131 must not change frontend or website files: {line}")

    def test_no_dependency_files_changed(self):
        changed = self._changed_files()
        forbidden = [
            "pyproject.toml",
            "setup.py",
            "requirements",
            "package.json",
            "package-lock.json",
        ]
        for token in forbidden:
            for line in changed.splitlines():
                if token in line:
                    self.fail(
                        f"GL-131 must not change dependency file '{token}': {line}"
                    )

    def test_no_db_schema_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if "schema" in line.lower() and line.endswith(".sql"):
                self.fail(f"GL-131 must not change DB schema: {line}")

    def test_no_scripts_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("scripts/"):
                self.fail(f"GL-131 must not change scripts: {line}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
