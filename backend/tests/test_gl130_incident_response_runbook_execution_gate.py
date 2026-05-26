"""Tests for GL-130: Incident Response / Operational Runbook Execution Gate.

Ensures:
- docs/incident_response_runbook_execution_gate.md exists and covers required topics.
- docs/examples/gl130/incident_response_runbook_execution_gate.json exists and is valid.
- JSON issue_id is GL-130.
- JSON review_only is true.
- JSON incident_automation_implemented is false.
- JSON monitoring_backend_implemented is false.
- JSON production_code_changed is false.
- Markdown explicitly says incident automation is not implemented.
- Markdown does not claim production incident response is fully automated.
- Incident categories, severity levels, first-response checklist, evidence capture,
  secret safety rules, escalation roles, required commands, pilot go/no-go criteria,
  related gates, recommended next steps, and non-goals are all documented.
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

_MD_PATH = _REPO_ROOT / "docs" / "incident_response_runbook_execution_gate.md"
_JSON_PATH = (
    _REPO_ROOT / "docs" / "examples" / "gl130" / "incident_response_runbook_execution_gate.json"
)

_SECRET_PATTERNS = [
    re.compile(r"\bpassword\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bsecret\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bapi_key\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bprivate_key\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bpassphrase\s*=\s*\S", re.IGNORECASE),
]


class TestGl130ArtifactsExist(unittest.TestCase):
    """Verify the GL-130 artifacts are present."""

    def test_markdown_exists(self):
        self.assertTrue(
            _MD_PATH.exists(),
            f"docs/incident_response_runbook_execution_gate.md must exist at {_MD_PATH}",
        )

    def test_json_exists(self):
        self.assertTrue(
            _JSON_PATH.exists(),
            f"docs/examples/gl130/incident_response_runbook_execution_gate.json must exist at {_JSON_PATH}",
        )


class TestGl130JsonStructure(unittest.TestCase):
    """Verify GL-130 JSON structure and values."""

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
            "GL-130",
            "JSON issue_id must be GL-130",
        )

    def test_json_review_only_is_true(self):
        self.assertIs(
            self.json_data.get("review_only"),
            True,
            "JSON review_only must be true",
        )

    def test_json_incident_automation_implemented_is_false(self):
        self.assertIs(
            self.json_data.get("incident_automation_implemented"),
            False,
            "JSON incident_automation_implemented must be false",
        )

    def test_json_monitoring_backend_implemented_is_false(self):
        self.assertIs(
            self.json_data.get("monitoring_backend_implemented"),
            False,
            "JSON monitoring_backend_implemented must be false",
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
            "incident_response_runbook_execution_gate",
            "JSON baseline_type must be incident_response_runbook_execution_gate",
        )


class TestGl130MarkdownContent(unittest.TestCase):
    """Verify GL-130 markdown content meets baseline requirements."""

    @classmethod
    def setUpClass(cls):
        cls.md_content = _MD_PATH.read_text(encoding="utf-8") if _MD_PATH.exists() else ""
        cls.md_lower = cls.md_content.lower()

    def test_markdown_says_incident_automation_not_implemented(self):
        lower = self.md_lower
        self.assertTrue(
            "not implemented" in lower or "not complete" in lower,
            "Markdown must state incident automation is not implemented",
        )

    def test_markdown_does_not_claim_production_incident_response_fully_automated(self):
        lower = self.md_lower
        # Reject a positive claim that production incident response IS fully automated
        self.assertNotIn(
            "production incident response is fully automated",
            lower,
            "Markdown must not claim production incident response is fully automated",
        )
        # Also check it doesn't claim "fully automated" positively near incident response
        if "fully automated" in lower:
            idx = lower.find("fully automated")
            preceding = lower[max(0, idx - 40):idx]
            following = lower[idx + len("fully automated"):idx + len("fully automated") + 20]
            has_negation = any(
                neg in preceding
                for neg in ["not ", "never ", "no ", "isn't ", "is not "]
            ) or any(
                neg in following
                for neg in ["| **no**", " not ", " no "]
            )
            self.assertTrue(
                has_negation,
                "Markdown must not positively claim incident response is fully automated",
            )

    # --- Incident categories ---

    def test_incident_category_service_unavailable(self):
        self.assertIn("service unavailable", self.md_lower)

    def test_incident_category_readiness_failure(self):
        self.assertIn("readiness failure", self.md_lower)

    def test_incident_category_elevated_5xx(self):
        self.assertIn("5xx", self.md_lower)
        self.assertIn("error rate", self.md_lower)

    def test_incident_category_repeated_auth_failures(self):
        self.assertIn("repeated auth", self.md_lower)

    def test_incident_category_repeated_forbidden_role_failures(self):
        self.assertIn("forbidden", self.md_lower)
        self.assertIn("operator-role", self.md_lower)

    def test_incident_category_repeated_rate_limit_events(self):
        self.assertIn("rate-limit", self.md_lower)

    def test_incident_category_invalid_payload_rejection_spike(self):
        self.assertIn("invalid payload", self.md_lower)
        self.assertIn("rejection", self.md_lower)

    def test_incident_category_audit_write_failure(self):
        self.assertIn("audit write failure", self.md_lower)

    def test_incident_category_audit_hash_chain_anomaly(self):
        self.assertIn("hash-chain", self.md_lower)
        self.assertIn("anomaly", self.md_lower)

    def test_incident_category_database_connectivity_pool_failure(self):
        self.assertIn("database connectivity", self.md_lower)
        self.assertIn("pool", self.md_lower)

    def test_incident_category_postgresql_audit_immutability_guard_failure(self):
        self.assertIn("postgresql audit immutability", self.md_lower)
        self.assertIn("guard failure", self.md_lower)

    def test_incident_category_runtime_gate_failure(self):
        self.assertIn("runtime gate failure", self.md_lower)

    def test_incident_category_operational_smoke_failure(self):
        self.assertIn("operational smoke failure", self.md_lower)

    def test_incident_category_backup_restore_drill_failure(self):
        self.assertIn("backup/restore drill failure", self.md_lower)

    def test_incident_category_unexpected_exception_spike(self):
        self.assertIn("unexpected exception spike", self.md_lower)

    def test_incident_category_suspected_secret_exposure(self):
        self.assertIn("secret exposure", self.md_lower)

    # --- Severity levels ---

    def test_severity_levels_include_sev1(self):
        self.assertIn("sev1", self.md_lower)

    def test_severity_levels_include_sev2(self):
        self.assertIn("sev2", self.md_lower)

    def test_severity_levels_include_sev3(self):
        self.assertIn("sev3", self.md_lower)

    def test_severity_levels_include_sev4(self):
        self.assertIn("sev4", self.md_lower)

    # --- First-response checklist ---

    def test_first_response_checklist_owner_assignment(self):
        self.assertIn("assign incident owner", self.md_lower)

    def test_first_response_checklist_freeze_risky_deploys(self):
        self.assertIn("freeze risky deploys", self.md_lower)

    def test_first_response_checklist_timestamp_and_commit(self):
        lower = self.md_lower
        self.assertIn("start time", lower)
        self.assertIn("main commit", lower)

    def test_first_response_checklist_correlation_id_capture(self):
        self.assertIn("correlation_id", self.md_lower)

    def test_first_response_checklist_health_readiness(self):
        lower = self.md_lower
        self.assertIn("health", lower)
        self.assertIn("readiness", lower)

    def test_first_response_checklist_structured_logs(self):
        self.assertIn("structured logs", self.md_lower)

    def test_first_response_checklist_smoke_tests_reference(self):
        self.assertIn("run-operational-smoke-tests", self.md_lower)

    def test_first_response_checklist_runtime_gate_reference(self):
        self.assertIn("run-production-runtime-gate", self.md_lower)

    def test_first_response_checklist_backup_drill_reference(self):
        self.assertIn("backup/restore drill", self.md_lower)

    def test_first_response_checklist_evidence_preservation(self):
        self.assertIn("preserve evidence", self.md_lower)

    # --- Evidence capture ---

    def test_evidence_capture_timestamps(self):
        self.assertIn("timestamps", self.md_lower)

    def test_evidence_capture_correlation_id(self):
        self.assertIn("correlation_id", self.md_lower)

    def test_evidence_capture_safe_logs(self):
        self.assertIn("safe log", self.md_lower)

    def test_evidence_capture_status_reason_codes(self):
        lower = self.md_lower
        self.assertIn("status codes", lower)
        self.assertIn("reason codes", lower)

    def test_evidence_capture_command_outputs(self):
        self.assertIn("command outputs", self.md_lower)

    def test_evidence_capture_main_commit(self):
        self.assertIn("git/main commit", self.md_lower)

    def test_evidence_capture_runtime_config_without_secrets(self):
        lower = self.md_lower
        self.assertIn("runtime mode", lower)
        self.assertIn("without secrets", lower)

    # --- Secret safety rules ---

    def test_secret_safety_no_raw_authorization_header(self):
        self.assertIn("no raw authorization header", self.md_lower)

    def test_secret_safety_no_raw_tokens(self):
        self.assertIn("no raw tokens", self.md_lower)

    def test_secret_safety_no_raw_request_bodies(self):
        self.assertIn("no raw request bodies", self.md_lower)

    def test_secret_safety_no_db_passwords(self):
        self.assertIn("no db passwords", self.md_lower)

    def test_secret_safety_no_private_keys_passphrases(self):
        lower = self.md_lower
        self.assertIn("no private keys", lower)
        self.assertIn("passphrases", lower)

    def test_secret_safety_no_backup_credentials(self):
        self.assertIn("no backup credentials", self.md_lower)

    # --- Escalation roles ---

    def test_escalation_roles_incident_owner(self):
        self.assertIn("incident owner", self.md_lower)

    def test_escalation_roles_technical_responder(self):
        self.assertIn("technical responder", self.md_lower)

    def test_escalation_roles_operator_business_owner(self):
        self.assertIn("operator/business owner", self.md_lower)

    def test_escalation_roles_security_data_integrity(self):
        self.assertIn("security/data-integrity escalation", self.md_lower)

    # --- Required commands ---

    def test_required_commands_runtime_gate(self):
        self.assertIn("scripts/run-production-runtime-gate.sh", self.md_content)

    def test_required_commands_smoke_tests(self):
        self.assertIn("scripts/run-operational-smoke-tests.sh", self.md_content)

    def test_required_commands_backup_restore_drill(self):
        self.assertIn("scripts/run-backup-restore-drill.sh", self.md_content)

    def test_required_commands_full_suite(self):
        self.assertIn("scripts/run-full-backend-suite.sh", self.md_content)

    # --- Pilot go/no-go ---

    def test_pilot_go_no_go_criteria_present(self):
        lower = self.md_lower
        self.assertIn("go", lower)
        self.assertIn("no-go", lower)

    # --- Related gates ---

    def test_related_gates_include_gl117(self):
        self.assertIn("gl-117", self.md_lower)

    def test_related_gates_include_gl118(self):
        self.assertIn("gl-118", self.md_lower)

    def test_related_gates_include_gl120(self):
        self.assertIn("gl-120", self.md_lower)

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

    # --- Recommended next steps ---

    def test_recommended_next_steps_include_gl131(self):
        self.assertIn("gl-131", self.md_lower)

    # --- Non-goals ---

    def test_explicit_non_goals_present(self):
        lower = self.md_lower
        self.assertIn("non-goals", lower)
        self.assertIn("no incident automation", lower)

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


class TestGl130ScopeGuard(unittest.TestCase):
    """Verify no forbidden files were changed by GL-130."""

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
                self.fail(f"GL-130 must not change production code: {line}")

    def test_no_openapi_changed(self):
        changed = self._changed_files()
        self.assertNotIn(
            "openapi.yaml",
            changed,
            "GL-130 must not change the OpenAPI specification",
        )

    def test_no_migration_files_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if "migrations/" in line:
                self.fail(f"GL-130 must not change migration files: {line}")

    def test_no_frontend_or_website_files_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("frontend/") or line.startswith("website/"):
                self.fail(f"GL-130 must not change frontend or website files: {line}")

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
                        f"GL-130 must not change dependency file '{token}': {line}"
                    )

    def test_no_db_schema_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if "schema" in line.lower() and line.endswith(".sql"):
                self.fail(f"GL-130 must not change DB schema: {line}")

    def test_no_scripts_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("scripts/"):
                self.fail(f"GL-130 must not change scripts: {line}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
