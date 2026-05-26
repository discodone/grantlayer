"""Tests for GL-129: Monitoring / Alerting Baseline.

Ensures:
- docs/monitoring_alerting_baseline.md exists and covers required topics.
- docs/examples/gl129/monitoring_alerting_baseline.json exists and is valid.
- JSON issue_id is GL-129.
- JSON monitoring_backend_implemented is false.
- JSON production_code_changed is false.
- Markdown explicitly says monitoring backend integration is not implemented.
- Signal categories, required log fields, secret safety rules, alert categories,
  pilot go/no-go criteria, related gates, recommended next steps, and non-goals
  are all documented.
- Markdown does not claim production observability complete.
- Markdown does not claim commercial SaaS complete.
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

_MD_PATH = _REPO_ROOT / "docs" / "monitoring_alerting_baseline.md"
_JSON_PATH = (
    _REPO_ROOT / "docs" / "examples" / "gl129" / "monitoring_alerting_baseline.json"
)

_SECRET_PATTERNS = [
    re.compile(r"\bpassword\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bsecret\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bapi_key\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bprivate_key\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bpassphrase\s*=\s*\S", re.IGNORECASE),
]


class TestGl129ArtifactsExist(unittest.TestCase):
    """Verify the GL-129 artifacts are present."""

    def test_markdown_exists(self):
        self.assertTrue(
            _MD_PATH.exists(),
            f"docs/monitoring_alerting_baseline.md must exist at {_MD_PATH}",
        )

    def test_json_exists(self):
        self.assertTrue(
            _JSON_PATH.exists(),
            f"docs/examples/gl129/monitoring_alerting_baseline.json must exist at {_JSON_PATH}",
        )


class TestGl129JsonStructure(unittest.TestCase):
    """Verify GL-129 JSON structure and values."""

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
            "GL-129",
            "JSON issue_id must be GL-129",
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
            "monitoring_alerting_baseline",
            "JSON baseline_type must be monitoring_alerting_baseline",
        )

    def test_json_review_only_is_true(self):
        self.assertIs(
            self.json_data.get("review_only"),
            True,
            "JSON review_only must be true",
        )


class TestGl129MarkdownContent(unittest.TestCase):
    """Verify GL-129 markdown content meets baseline requirements."""

    @classmethod
    def setUpClass(cls):
        cls.md_content = _MD_PATH.read_text(encoding="utf-8") if _MD_PATH.exists() else ""
        cls.md_lower = cls.md_content.lower()

    def test_markdown_says_monitoring_backend_not_implemented(self):
        lower = self.md_lower
        self.assertTrue(
            "not implemented" in lower or "not complete" in lower,
            "Markdown must state monitoring backend integration is not implemented",
        )

    def test_signal_categories_include_availability(self):
        self.assertIn("availability", self.md_lower)

    def test_signal_categories_include_readiness(self):
        self.assertIn("readiness", self.md_lower)

    def test_signal_categories_include_request_latency(self):
        self.assertIn("latency", self.md_lower)

    def test_signal_categories_include_error_rate(self):
        self.assertIn("error rate", self.md_lower)

    def test_signal_categories_include_auth_failures(self):
        self.assertIn("auth failure", self.md_lower)

    def test_signal_categories_include_rate_limit_events(self):
        self.assertIn("rate-limit", self.md_lower)

    def test_signal_categories_include_invalid_payload_events(self):
        self.assertIn("invalid payload", self.md_lower)

    def test_signal_categories_include_audit_write_failures(self):
        self.assertIn("audit write", self.md_lower)

    def test_signal_categories_include_audit_hash_chain_issues(self):
        self.assertIn("hash-chain", self.md_lower)

    def test_signal_categories_include_db_connectivity_pool_pressure(self):
        self.assertIn("database connectivity", self.md_lower)
        self.assertIn("pool pressure", self.md_lower)

    def test_signal_categories_include_runtime_gate_failures(self):
        self.assertIn("runtime gate", self.md_lower)

    def test_signal_categories_include_smoke_failures(self):
        self.assertIn("operational smoke", self.md_lower)

    def test_signal_categories_include_backup_restore_drill_failures(self):
        self.assertIn("backup/restore drill", self.md_lower)

    def test_signal_categories_include_unexpected_exceptions(self):
        self.assertIn("unexpected exception", self.md_lower)

    def test_required_log_fields_include_timestamp(self):
        self.assertIn("timestamp", self.md_lower)

    def test_required_log_fields_include_level(self):
        self.assertIn("level", self.md_lower)

    def test_required_log_fields_include_component(self):
        self.assertIn("component", self.md_lower)

    def test_required_log_fields_include_event_action(self):
        self.assertIn("event", self.md_lower)

    def test_required_log_fields_include_correlation_id(self):
        self.assertIn("correlation_id", self.md_lower)

    def test_required_log_fields_include_method_path_status(self):
        self.assertIn("method", self.md_lower)
        self.assertIn("path", self.md_lower)
        self.assertIn("status_code", self.md_lower)

    def test_required_log_fields_include_reason_code(self):
        self.assertIn("reason_code", self.md_lower)

    def test_secret_safety_rules_include_no_raw_authorization_header(self):
        self.assertIn("no raw authorization header", self.md_lower)

    def test_secret_safety_rules_include_no_raw_tokens(self):
        self.assertIn("no raw tokens", self.md_lower)

    def test_secret_safety_rules_include_no_raw_request_bodies(self):
        self.assertIn("no raw request bodies", self.md_lower)

    def test_secret_safety_rules_include_no_db_passwords(self):
        self.assertIn("no db passwords", self.md_lower)

    def test_secret_safety_rules_include_no_private_keys_passphrases(self):
        self.assertIn("no private keys", self.md_lower)
        self.assertIn("passphrases", self.md_lower)

    def test_secret_safety_rules_include_no_backup_credentials(self):
        self.assertIn("no backup credentials", self.md_lower)

    def test_alert_categories_include_health_failure(self):
        self.assertIn("health failure", self.md_lower)

    def test_alert_categories_include_readiness_failure(self):
        self.assertIn("readiness failure", self.md_lower)

    def test_alert_categories_include_elevated_5xx(self):
        self.assertIn("5xx", self.md_lower)

    def test_alert_categories_include_repeated_auth_failures(self):
        self.assertIn("repeated auth", self.md_lower)

    def test_alert_categories_include_repeated_forbidden_role_failures(self):
        self.assertIn("forbidden", self.md_lower)
        self.assertIn("role", self.md_lower)

    def test_alert_categories_include_repeated_rate_limit_events(self):
        self.assertIn("repeated rate-limit", self.md_lower)

    def test_alert_categories_include_repeated_invalid_payloads(self):
        self.assertIn("repeated invalid payload", self.md_lower)

    def test_alert_categories_include_audit_write_failure(self):
        self.assertIn("audit write failure", self.md_lower)

    def test_alert_categories_include_audit_hash_chain_anomaly(self):
        self.assertIn("audit/hash-chain anomaly", self.md_lower)

    def test_alert_categories_include_db_connectivity_pool_failure(self):
        self.assertIn("db connectivity/pool failure", self.md_lower)

    def test_alert_categories_include_postgresql_immutability_guard_failure(self):
        self.assertIn("postgresql immutability guard failure", self.md_lower)

    def test_alert_categories_include_runtime_gate_failure(self):
        self.assertIn("runtime gate failure", self.md_lower)

    def test_alert_categories_include_smoke_failure(self):
        self.assertIn("smoke test failure", self.md_lower)

    def test_alert_categories_include_backup_restore_drill_failure(self):
        self.assertIn("backup/restore drill failure", self.md_lower)

    def test_alert_categories_include_unexpected_exception_spike(self):
        self.assertIn("unexpected exception spike", self.md_lower)

    def test_pilot_go_criteria_present(self):
        lower = self.md_lower
        self.assertIn("go", lower)
        self.assertIn("no-go", lower)
        self.assertIn("alert owner", lower)

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

    def test_recommended_next_steps_include_monitoring_backend(self):
        self.assertIn("choose monitoring backend", self.md_lower)

    def test_recommended_next_steps_include_log_aggregation(self):
        self.assertIn("wire log aggregation", self.md_lower)

    def test_recommended_next_steps_include_alert_receivers(self):
        self.assertIn("define alert receivers", self.md_lower)

    def test_recommended_next_steps_include_alert_delivery_test(self):
        self.assertIn("test alert delivery", self.md_lower)

    def test_recommended_next_steps_include_gl130(self):
        self.assertIn("gl-130", self.md_lower)

    def test_markdown_does_not_claim_production_observability_complete(self):
        lower = self.md_lower
        self.assertNotIn(
            "production observability complete",
            lower,
            "Markdown must not claim production observability is complete",
        )

    def test_markdown_does_not_claim_commercial_saas_complete(self):
        lower = self.md_lower
        idx = lower.find("commercial saas complete")
        if idx != -1:
            preceding = lower[max(0, idx - 25):idx]
            has_negation = any(
                neg in preceding
                for neg in ["not ", "never ", "no ", "isn't ", "is not "]
            )
            self.assertTrue(
                has_negation,
                "Markdown must not positively claim 'commercial SaaS complete'",
            )

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


class TestGl129ScopeGuard(unittest.TestCase):
    """Verify no forbidden files were changed by GL-129."""

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
                self.fail(f"GL-129 must not change production code: {line}")

    def test_no_openapi_changed(self):
        changed = self._changed_files()
        self.assertNotIn(
            "openapi.yaml",
            changed,
            "GL-129 must not change the OpenAPI specification",
        )

    def test_no_migration_files_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if "migrations/" in line:
                self.fail(f"GL-129 must not change migration files: {line}")

    def test_no_frontend_or_website_files_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("frontend/") or line.startswith("website/"):
                self.fail(f"GL-129 must not change frontend or website files: {line}")

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
                        f"GL-129 must not change dependency file '{token}': {line}"
                    )

    def test_no_db_schema_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if "schema" in line.lower() and line.endswith(".sql"):
                self.fail(f"GL-129 must not change DB schema: {line}")

    def test_no_scripts_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("scripts/"):
                self.fail(f"GL-129 must not change scripts: {line}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
