"""Tests for GL-133: External Security Review Preparation.

Ensures:
- docs/external_security_review_preparation.md exists and covers required topics.
- docs/examples/gl133/external_security_review_preparation.json exists and is valid.
- JSON issue_id is GL-133.
- JSON review_only is true.
- JSON external_review_completed is false.
- JSON penetration_test_completed is false.
- JSON security_controls_implemented is false.
- JSON production_code_changed is false.
- JSON production_saas_complete is false.
- JSON commercial_saas_complete is false.
- JSON production_multitenancy_implemented is false.
- JSON shared_saas_for_unrelated_customers_approved is false.
- Markdown says GL-133 prepares external review but does not complete one.
- Markdown says no penetration test is completed by GL-133.
- Markdown says production SaaS is not complete.
- Markdown says multi-tenant isolation is not implemented.
- Review scope includes all required areas.
- Security-sensitive components include all required items.
- Threat-model review areas include all required items.
- Reviewer checklist includes all required items.
- Evidence artifacts include all required items.
- Required validation commands include all required items.
- Expected reviewer outputs include all required items.
- Go/no-go criteria are present.
- Related gates include GL-128, GL-129, GL-130, GL-131, GL-132.
- Recommended next steps include GL-134.
- Markdown/JSON do not include obvious raw secret values.
- Scope guards for no forbidden changes.

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

_MD_PATH = _REPO_ROOT / "docs" / "external_security_review_preparation.md"
_JSON_PATH = (
    _REPO_ROOT
    / "docs"
    / "examples"
    / "gl133"
    / "external_security_review_preparation.json"
)

_SECRET_PATTERNS = [
    re.compile(r"\bpassword\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bsecret\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bapi_key\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bprivate_key\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bpassphrase\s*=\s*\S", re.IGNORECASE),
]


class TestGl133ArtifactsExist(unittest.TestCase):
    """Verify the GL-133 artifacts are present."""

    def test_markdown_exists(self):
        self.assertTrue(
            _MD_PATH.exists(),
            f"docs/external_security_review_preparation.md must exist at {_MD_PATH}",
        )

    def test_json_exists(self):
        self.assertTrue(
            _JSON_PATH.exists(),
            f"docs/examples/gl133/external_security_review_preparation.json must exist at {_JSON_PATH}",
        )


class TestGl133JsonStructure(unittest.TestCase):
    """Verify GL-133 JSON structure and values."""

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
            "GL-133",
            "JSON issue_id must be GL-133",
        )

    def test_json_review_only_is_true(self):
        self.assertIs(
            self.json_data.get("review_only"),
            True,
            "JSON review_only must be true",
        )

    def test_json_external_review_completed_is_false(self):
        self.assertIs(
            self.json_data.get("external_review_completed"),
            False,
            "JSON external_review_completed must be false",
        )

    def test_json_penetration_test_completed_is_false(self):
        self.assertIs(
            self.json_data.get("penetration_test_completed"),
            False,
            "JSON penetration_test_completed must be false",
        )

    def test_json_security_controls_implemented_is_false(self):
        self.assertIs(
            self.json_data.get("security_controls_implemented"),
            False,
            "JSON security_controls_implemented must be false",
        )

    def test_json_production_code_changed_is_false(self):
        self.assertIs(
            self.json_data.get("production_code_changed"),
            False,
            "JSON production_code_changed must be false",
        )

    def test_json_production_saas_complete_is_false(self):
        self.assertIs(
            self.json_data.get("production_saas_complete"),
            False,
            "JSON production_saas_complete must be false",
        )

    def test_json_commercial_saas_complete_is_false(self):
        self.assertIs(
            self.json_data.get("commercial_saas_complete"),
            False,
            "JSON commercial_saas_complete must be false",
        )

    def test_json_production_multitenancy_implemented_is_false(self):
        self.assertIs(
            self.json_data.get("production_multitenancy_implemented"),
            False,
            "JSON production_multitenancy_implemented must be false",
        )

    def test_json_shared_saas_for_unrelated_customers_approved_is_false(self):
        self.assertIs(
            self.json_data.get("shared_saas_for_unrelated_customers_approved"),
            False,
            "JSON shared_saas_for_unrelated_customers_approved must be false",
        )

    def test_json_artifact_type(self):
        self.assertEqual(
            self.json_data.get("artifact_type"),
            "external_security_review_preparation",
            "JSON artifact_type must be external_security_review_preparation",
        )


class TestGl133MarkdownContent(unittest.TestCase):
    """Verify GL-133 markdown content meets baseline requirements."""

    @classmethod
    def setUpClass(cls):
        cls.md_content = _MD_PATH.read_text(encoding="utf-8") if _MD_PATH.exists() else ""
        cls.md_lower = cls.md_content.lower()

    # --- Core claims ---

    def test_markdown_says_gl133_prepares_external_review_but_does_not_complete_one(self):
        lower = self.md_lower
        self.assertTrue(
            "gl-133 prepares external review" in lower
            or "prepares an independent external security review" in lower
            or "prepares grantlayer for an independent external security review" in lower,
            "Markdown must state GL-133 prepares external review",
        )
        self.assertTrue(
            "does not complete one" in lower
            or "does not perform or complete one" in lower
            or "gl-133 completes external review" in lower
            and "no" in lower,
            "Markdown must state GL-133 does not complete external review",
        )

    def test_markdown_says_no_penetration_test_completed(self):
        lower = self.md_lower
        self.assertTrue(
            "no penetration test" in lower
            or "not a penetration test" in lower,
            "Markdown must state no penetration test is completed by GL-133",
        )

    def test_markdown_says_production_saas_not_complete(self):
        lower = self.md_lower
        self.assertTrue(
            "production saas is not complete" in lower
            or "production saas complete" in lower
            and "no" in lower,
            "Markdown must state production SaaS is not complete",
        )

    def test_markdown_says_multi_tenant_isolation_not_implemented(self):
        lower = self.md_lower
        self.assertTrue(
            "multi-tenant isolation is not implemented" in lower
            or "multi_tenant isolation is not implemented" in lower
            or "not implemented" in lower
            and "multi-tenant" in lower,
            "Markdown must state multi-tenant isolation is not implemented",
        )

    # --- Review scope ---

    def test_review_scope_includes_backend_api_security(self):
        lower = self.md_lower
        self.assertIn("backend api security", lower)

    def test_review_scope_includes_operator_auth(self):
        lower = self.md_lower
        self.assertIn("operator authentication", lower)
        self.assertIn("authorization", lower)

    def test_review_scope_includes_token_expiry_rotation(self):
        lower = self.md_lower
        self.assertIn("token expiry", lower)
        self.assertIn("rotation", lower)

    def test_review_scope_includes_startup_fail_closed(self):
        lower = self.md_lower
        self.assertIn("fail-closed", lower)
        self.assertIn("startup", lower)

    def test_review_scope_includes_request_validation(self):
        lower = self.md_lower
        self.assertIn("request body", lower)
        self.assertIn("payload validation", lower)

    def test_review_scope_includes_rate_limiting(self):
        lower = self.md_lower
        self.assertIn("rate limiting", lower)

    def test_review_scope_includes_logging_correlation_secret_safety(self):
        lower = self.md_lower
        self.assertIn("structured logging", lower)
        self.assertIn("correlation", lower)
        self.assertIn("secret safety", lower)

    def test_review_scope_includes_audit_hash_chain_postgres(self):
        lower = self.md_lower
        self.assertIn("audit", lower)
        self.assertIn("hash-chain", lower)
        self.assertIn("postgre", lower)
        self.assertIn("immutability", lower)

    def test_review_scope_includes_postgres_connection_pooling(self):
        lower = self.md_lower
        self.assertIn("connection pooling", lower)

    def test_review_scope_includes_backup_restore(self):
        lower = self.md_lower
        self.assertIn("backup", lower)
        self.assertIn("restore", lower)

    def test_review_scope_includes_runtime_smoke_tests(self):
        lower = self.md_lower
        self.assertIn("runtime gate", lower)
        self.assertIn("smoke", lower)

    def test_review_scope_includes_monitoring_alerting(self):
        lower = self.md_lower
        self.assertIn("monitoring", lower)
        self.assertIn("alerting", lower)

    def test_review_scope_includes_incident_response(self):
        lower = self.md_lower
        self.assertIn("incident response", lower)

    def test_review_scope_includes_tenant_workspace_boundary(self):
        lower = self.md_lower
        self.assertIn("tenant", lower)
        self.assertIn("workspace", lower)
        self.assertIn("boundary", lower)

    # --- Security-sensitive components ---

    def test_security_sensitive_includes_auth_token_handling(self):
        lower = self.md_lower
        self.assertIn("auth", lower)
        self.assertIn("token handling", lower)

    def test_security_sensitive_includes_permission_checks(self):
        lower = self.md_lower
        self.assertIn("permission", lower)
        self.assertIn("checks", lower)

    def test_security_sensitive_includes_request_parsing_validation(self):
        lower = self.md_lower
        self.assertIn("request parsing", lower)
        self.assertIn("validation", lower)

    def test_security_sensitive_includes_rate_limiting(self):
        lower = self.md_lower
        self.assertIn("rate limiting", lower)

    def test_security_sensitive_includes_audit_persistence(self):
        lower = self.md_lower
        self.assertIn("audit", lower)
        self.assertIn("persistence", lower)

    def test_security_sensitive_includes_cryptographic_signing(self):
        lower = self.md_lower
        self.assertIn("cryptographic signing", lower)
        self.assertIn("signature", lower)

    def test_security_sensitive_includes_secret_source_boundary(self):
        lower = self.md_lower
        self.assertIn("secret source", lower)
        self.assertIn("boundary", lower)

    def test_security_sensitive_includes_db_config_postgres(self):
        lower = self.md_lower
        self.assertIn("database", lower)
        self.assertIn("postgre", lower)

    def test_security_sensitive_includes_backup_restore(self):
        lower = self.md_lower
        self.assertIn("backup", lower)
        self.assertIn("restore", lower)

    def test_security_sensitive_includes_logs_correlation_ids(self):
        lower = self.md_lower
        self.assertIn("logs", lower)
        self.assertIn("correlation", lower)

    # --- Threat-model review areas ---

    def test_threat_model_includes_unauthenticated_access(self):
        lower = self.md_lower
        self.assertIn("unauthenticated access", lower)

    def test_threat_model_includes_unauthorized_operator_access(self):
        lower = self.md_lower
        self.assertIn("unauthorized operator", lower)

    def test_threat_model_includes_token_expiry_rotation_failure(self):
        lower = self.md_lower
        self.assertIn("token expiry", lower)
        self.assertIn("rotation", lower)
        self.assertIn("failure", lower)

    def test_threat_model_includes_malformed_oversized_payloads(self):
        lower = self.md_lower
        self.assertIn("malformed", lower)
        self.assertIn("oversized", lower)
        self.assertIn("payload", lower)

    def test_threat_model_includes_state_mutation_after_rejection(self):
        lower = self.md_lower
        self.assertIn("state mutation", lower)
        self.assertIn("rejection", lower)

    def test_threat_model_includes_audit_tampering(self):
        lower = self.md_lower
        self.assertIn("audit tampering", lower)

    def test_threat_model_includes_secret_leakage(self):
        lower = self.md_lower
        self.assertIn("secret leakage", lower)

    def test_threat_model_includes_db_config_failures(self):
        lower = self.md_lower
        self.assertIn("db connectivity", lower)
        self.assertIn("config failures", lower)

    def test_threat_model_includes_backup_misuse(self):
        lower = self.md_lower
        self.assertIn("backup", lower)
        self.assertIn("restore misuse", lower)

    def test_threat_model_includes_tenant_workspace_ambiguity(self):
        lower = self.md_lower
        self.assertIn("tenant", lower)
        self.assertIn("workspace", lower)
        self.assertIn("ambiguity", lower)

    # --- Reviewer checklist ---

    def test_reviewer_checklist_present(self):
        lower = self.md_lower
        self.assertIn("reviewer checklist", lower)

    def test_reviewer_checklist_includes_auth_fail_closed(self):
        lower = self.md_lower
        self.assertIn("auth fail-closed", lower)

    def test_reviewer_checklist_includes_role_permission_boundaries(self):
        lower = self.md_lower
        self.assertIn("role", lower)
        self.assertIn("permission boundaries", lower)

    def test_reviewer_checklist_includes_token_expiry_rotation(self):
        lower = self.md_lower
        self.assertIn("token expiry", lower)
        self.assertIn("rotation", lower)

    def test_reviewer_checklist_includes_unsafe_startup(self):
        lower = self.md_lower
        self.assertIn("unsafe startup", lower)

    def test_reviewer_checklist_includes_payload_validation(self):
        lower = self.md_lower
        self.assertIn("payload", lower)
        self.assertIn("malformed json", lower)

    def test_reviewer_checklist_includes_rate_limit_no_mutation(self):
        lower = self.md_lower
        self.assertIn("rate limiting", lower)
        self.assertIn("mutate state", lower)

    def test_reviewer_checklist_includes_secret_safe_logs(self):
        lower = self.md_lower
        self.assertIn("logs do not expose secrets", lower)

    def test_reviewer_checklist_includes_audit_immutability(self):
        lower = self.md_lower
        self.assertIn("audit immutability", lower)

    def test_reviewer_checklist_includes_backup_restore(self):
        lower = self.md_lower
        self.assertIn("backup", lower)
        self.assertIn("restore", lower)

    def test_reviewer_checklist_includes_tenant_non_claims(self):
        lower = self.md_lower
        self.assertIn("tenant", lower)
        self.assertIn("non-claims", lower)

    # --- Evidence artifacts ---

    def test_evidence_artifacts_include_gl128(self):
        self.assertIn("gl-128", self.md_lower)

    def test_evidence_artifacts_include_gl129(self):
        self.assertIn("gl-129", self.md_lower)

    def test_evidence_artifacts_include_gl130(self):
        self.assertIn("gl-130", self.md_lower)

    def test_evidence_artifacts_include_gl131(self):
        self.assertIn("gl-131", self.md_lower)

    def test_evidence_artifacts_include_gl132(self):
        self.assertIn("gl-132", self.md_lower)

    def test_evidence_artifacts_include_security_boundary_regression(self):
        lower = self.md_lower
        self.assertIn("security boundary regression", lower)

    def test_evidence_artifacts_include_full_backend_suite_runner(self):
        lower = self.md_lower
        self.assertIn("full backend suite", lower)
        self.assertIn("runner", lower)

    # --- Required validation commands ---

    def test_validation_commands_include_full_suite_script(self):
        lower = self.md_lower
        self.assertIn("scripts/run-full-backend-suite.sh", lower)

    def test_validation_commands_include_security_boundary_regression(self):
        lower = self.md_lower
        self.assertIn("test_security_boundary_regression", lower)

    def test_validation_commands_include_gl128(self):
        lower = self.md_lower
        self.assertIn("test_gl128", lower)

    def test_validation_commands_include_gl129(self):
        lower = self.md_lower
        self.assertIn("test_gl129", lower)

    def test_validation_commands_include_gl130(self):
        lower = self.md_lower
        self.assertIn("test_gl130", lower)

    def test_validation_commands_include_gl131(self):
        lower = self.md_lower
        self.assertIn("test_gl131", lower)

    def test_validation_commands_include_gl132(self):
        lower = self.md_lower
        self.assertIn("test_gl132", lower)

    # --- Expected reviewer outputs ---

    def test_expected_outputs_include_findings_by_severity(self):
        lower = self.md_lower
        self.assertIn("findings by severity", lower)

    def test_expected_outputs_include_must_fix_before_pilot(self):
        lower = self.md_lower
        self.assertIn("must-fix-before-pilot", lower)

    def test_expected_outputs_include_must_fix_before_production_saas(self):
        lower = self.md_lower
        self.assertIn("must-fix-before-production-saas", lower)

    def test_expected_outputs_include_acceptable_caveats(self):
        lower = self.md_lower
        self.assertIn("acceptable pilot caveats", lower)

    def test_expected_outputs_include_recommended_follow_up_issues(self):
        lower = self.md_lower
        self.assertIn("recommended follow-up issues", lower)

    # --- Go/no-go criteria ---

    def test_go_no_go_criteria_present(self):
        lower = self.md_lower
        self.assertIn("go", lower)
        self.assertIn("no-go", lower)
        self.assertIn("for review usage", lower)

    # --- Related gates ---

    def test_related_gates_include_gl128(self):
        self.assertIn("gl-128", self.md_lower)

    def test_related_gates_include_gl129(self):
        self.assertIn("gl-129", self.md_lower)

    def test_related_gates_include_gl130(self):
        self.assertIn("gl-130", self.md_lower)

    def test_related_gates_include_gl131(self):
        self.assertIn("gl-131", self.md_lower)

    def test_related_gates_include_gl132(self):
        self.assertIn("gl-132", self.md_lower)

    # --- Recommended next steps ---

    def test_recommended_next_steps_include_gl134(self):
        self.assertIn("gl-134", self.md_lower)

    # --- Non-goals ---

    def test_non_goals_present(self):
        lower = self.md_lower
        self.assertIn("explicit non-goals", lower)

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


class TestGl133JsonContent(unittest.TestCase):
    """Verify GL-133 JSON arrays contain expected items."""

    @classmethod
    def setUpClass(cls):
        raw_json = _JSON_PATH.read_text(encoding="utf-8") if _JSON_PATH.exists() else "{}"
        cls.json_data = json.loads(raw_json)

    def _has_substring_in_array(self, key, substring):
        arr = self.json_data.get(key, [])
        return any(substring.lower() in str(item).lower() for item in arr)

    def test_review_scope_includes_backend_api_security(self):
        self.assertTrue(
            self._has_substring_in_array("review_scope", "backend api security"),
            "review_scope must include backend API security",
        )

    def test_review_scope_includes_operator_auth(self):
        self.assertTrue(
            self._has_substring_in_array("review_scope", "operator authentication"),
            "review_scope must include operator authentication",
        )

    def test_review_scope_includes_token_expiry_rotation(self):
        self.assertTrue(
            self._has_substring_in_array("review_scope", "token expiry"),
            "review_scope must include token expiry",
        )

    def test_review_scope_includes_startup_fail_closed(self):
        self.assertTrue(
            self._has_substring_in_array("review_scope", "startup fail-closed"),
            "review_scope must include startup fail-closed",
        )

    def test_review_scope_includes_request_validation(self):
        self.assertTrue(
            self._has_substring_in_array("review_scope", "payload validation"),
            "review_scope must include payload validation",
        )

    def test_review_scope_includes_rate_limiting(self):
        self.assertTrue(
            self._has_substring_in_array("review_scope", "rate limiting"),
            "review_scope must include rate limiting",
        )

    def test_review_scope_includes_logging_correlation(self):
        self.assertTrue(
            self._has_substring_in_array("review_scope", "structured logging"),
            "review_scope must include structured logging",
        )

    def test_review_scope_includes_audit_hash_chain(self):
        self.assertTrue(
            self._has_substring_in_array("review_scope", "hash-chain"),
            "review_scope must include hash-chain",
        )

    def test_security_sensitive_includes_auth_token_handling(self):
        self.assertTrue(
            self._has_substring_in_array("security_sensitive_components", "auth"),
            "security_sensitive_components must include auth",
        )

    def test_security_sensitive_includes_permission_checks(self):
        self.assertTrue(
            self._has_substring_in_array("security_sensitive_components", "permission"),
            "security_sensitive_components must include permission checks",
        )

    def test_security_sensitive_includes_request_parsing(self):
        self.assertTrue(
            self._has_substring_in_array("security_sensitive_components", "request parsing"),
            "security_sensitive_components must include request parsing",
        )

    def test_security_sensitive_includes_rate_limiting(self):
        self.assertTrue(
            self._has_substring_in_array("security_sensitive_components", "rate limiting"),
            "security_sensitive_components must include rate limiting",
        )

    def test_security_sensitive_includes_audit_persistence(self):
        self.assertTrue(
            self._has_substring_in_array("security_sensitive_components", "audit"),
            "security_sensitive_components must include audit",
        )

    def test_security_sensitive_includes_cryptographic_signing(self):
        self.assertTrue(
            self._has_substring_in_array("security_sensitive_components", "cryptographic signing"),
            "security_sensitive_components must include cryptographic signing",
        )

    def test_security_sensitive_includes_secret_source_boundary(self):
        self.assertTrue(
            self._has_substring_in_array("security_sensitive_components", "secret source"),
            "security_sensitive_components must include secret source boundary",
        )

    def test_security_sensitive_includes_db_config(self):
        self.assertTrue(
            self._has_substring_in_array("security_sensitive_components", "database"),
            "security_sensitive_components must include database configuration",
        )

    def test_security_sensitive_includes_backup_restore(self):
        self.assertTrue(
            self._has_substring_in_array("security_sensitive_components", "backup"),
            "security_sensitive_components must include backup/restore",
        )

    def test_security_sensitive_includes_logs_correlation(self):
        self.assertTrue(
            self._has_substring_in_array("security_sensitive_components", "logs"),
            "security_sensitive_components must include logs/correlation",
        )

    def test_threat_model_includes_unauthenticated_access(self):
        self.assertTrue(
            self._has_substring_in_array("threat_model_review_areas", "unauthenticated access"),
            "threat_model_review_areas must include unauthenticated access",
        )

    def test_threat_model_includes_unauthorized_operator_access(self):
        self.assertTrue(
            self._has_substring_in_array("threat_model_review_areas", "unauthorized operator"),
            "threat_model_review_areas must include unauthorized operator access",
        )

    def test_threat_model_includes_token_expiry_rotation_failure(self):
        self.assertTrue(
            self._has_substring_in_array("threat_model_review_areas", "token expiry"),
            "threat_model_review_areas must include token expiry/rotation failure",
        )

    def test_threat_model_includes_malformed_oversized_payloads(self):
        self.assertTrue(
            self._has_substring_in_array("threat_model_review_areas", "malformed"),
            "threat_model_review_areas must include malformed/oversized payloads",
        )

    def test_threat_model_includes_state_mutation_after_rejection(self):
        self.assertTrue(
            self._has_substring_in_array("threat_model_review_areas", "state mutation"),
            "threat_model_review_areas must include state mutation after rejection",
        )

    def test_threat_model_includes_audit_tampering(self):
        self.assertTrue(
            self._has_substring_in_array("threat_model_review_areas", "audit tampering"),
            "threat_model_review_areas must include audit tampering",
        )

    def test_threat_model_includes_secret_leakage(self):
        self.assertTrue(
            self._has_substring_in_array("threat_model_review_areas", "secret leakage"),
            "threat_model_review_areas must include secret leakage",
        )

    def test_threat_model_includes_db_config_failures(self):
        self.assertTrue(
            self._has_substring_in_array("threat_model_review_areas", "DB connectivity"),
            "threat_model_review_areas must include DB connectivity/config failures",
        )

    def test_threat_model_includes_backup_misuse(self):
        self.assertTrue(
            self._has_substring_in_array("threat_model_review_areas", "backup"),
            "threat_model_review_areas must include backup/restore misuse",
        )

    def test_threat_model_includes_tenant_workspace_ambiguity(self):
        self.assertTrue(
            self._has_substring_in_array("threat_model_review_areas", "tenant"),
            "threat_model_review_areas must include tenant/workspace ambiguity",
        )

    def test_reviewer_checklist_includes_auth_fail_closed(self):
        self.assertTrue(
            self._has_substring_in_array("reviewer_checklist", "auth fail-closed"),
            "reviewer_checklist must include auth fail-closed",
        )

    def test_reviewer_checklist_includes_role_permission_boundaries(self):
        self.assertTrue(
            self._has_substring_in_array("reviewer_checklist", "permission boundaries"),
            "reviewer_checklist must include role/permission boundaries",
        )

    def test_reviewer_checklist_includes_token_expiry_rotation(self):
        self.assertTrue(
            self._has_substring_in_array("reviewer_checklist", "token expiry"),
            "reviewer_checklist must include token expiry/rotation",
        )

    def test_reviewer_checklist_includes_unsafe_startup(self):
        self.assertTrue(
            self._has_substring_in_array("reviewer_checklist", "unsafe startup"),
            "reviewer_checklist must include unsafe startup",
        )

    def test_reviewer_checklist_includes_payload_validation(self):
        self.assertTrue(
            self._has_substring_in_array("reviewer_checklist", "malformed JSON"),
            "reviewer_checklist must include malformed JSON rejection",
        )

    def test_reviewer_checklist_includes_rate_limit_no_mutation(self):
        self.assertTrue(
            self._has_substring_in_array("reviewer_checklist", "mutate state"),
            "reviewer_checklist must include rate-limit no-mutation",
        )

    def test_reviewer_checklist_includes_secret_safe_logs(self):
        self.assertTrue(
            self._has_substring_in_array("reviewer_checklist", "logs do not expose secrets"),
            "reviewer_checklist must include secret-safe logs",
        )

    def test_reviewer_checklist_includes_audit_immutability(self):
        self.assertTrue(
            self._has_substring_in_array("reviewer_checklist", "audit immutability"),
            "reviewer_checklist must include audit immutability",
        )

    def test_reviewer_checklist_includes_backup_restore(self):
        self.assertTrue(
            self._has_substring_in_array("reviewer_checklist", "backup"),
            "reviewer_checklist must include backup/restore",
        )

    def test_reviewer_checklist_includes_tenant_non_claims(self):
        self.assertTrue(
            self._has_substring_in_array("reviewer_checklist", "non-claims"),
            "reviewer_checklist must include tenant non-claims",
        )

    def test_evidence_artifacts_include_gl128(self):
        self.assertTrue(
            self._has_substring_in_array("evidence_artifacts", "GL-128"),
            "evidence_artifacts must include GL-128",
        )

    def test_evidence_artifacts_include_gl129(self):
        self.assertTrue(
            self._has_substring_in_array("evidence_artifacts", "GL-129"),
            "evidence_artifacts must include GL-129",
        )

    def test_evidence_artifacts_include_gl130(self):
        self.assertTrue(
            self._has_substring_in_array("evidence_artifacts", "GL-130"),
            "evidence_artifacts must include GL-130",
        )

    def test_evidence_artifacts_include_gl131(self):
        self.assertTrue(
            self._has_substring_in_array("evidence_artifacts", "GL-131"),
            "evidence_artifacts must include GL-131",
        )

    def test_evidence_artifacts_include_gl132(self):
        self.assertTrue(
            self._has_substring_in_array("evidence_artifacts", "GL-132"),
            "evidence_artifacts must include GL-132",
        )

    def test_evidence_artifacts_include_security_boundary_regression(self):
        self.assertTrue(
            self._has_substring_in_array("evidence_artifacts", "security boundary regression"),
            "evidence_artifacts must include security boundary regression tests",
        )

    def test_evidence_artifacts_include_full_backend_suite_runner(self):
        self.assertTrue(
            self._has_substring_in_array("evidence_artifacts", "full backend suite runner"),
            "evidence_artifacts must include full backend suite runner",
        )

    def test_required_validation_commands_include_full_suite_script(self):
        self.assertTrue(
            self._has_substring_in_array("required_validation_commands", "run-full-backend-suite.sh"),
            "required_validation_commands must include full suite script",
        )

    def test_required_validation_commands_include_security_boundary_regression(self):
        self.assertTrue(
            self._has_substring_in_array("required_validation_commands", "test_security_boundary_regression"),
            "required_validation_commands must include security boundary regression",
        )

    def test_required_validation_commands_include_gl128(self):
        self.assertTrue(
            self._has_substring_in_array("required_validation_commands", "test_gl128"),
            "required_validation_commands must include GL-128",
        )

    def test_required_validation_commands_include_gl129(self):
        self.assertTrue(
            self._has_substring_in_array("required_validation_commands", "test_gl129"),
            "required_validation_commands must include GL-129",
        )

    def test_required_validation_commands_include_gl130(self):
        self.assertTrue(
            self._has_substring_in_array("required_validation_commands", "test_gl130"),
            "required_validation_commands must include GL-130",
        )

    def test_required_validation_commands_include_gl131(self):
        self.assertTrue(
            self._has_substring_in_array("required_validation_commands", "test_gl131"),
            "required_validation_commands must include GL-131",
        )

    def test_required_validation_commands_include_gl132(self):
        self.assertTrue(
            self._has_substring_in_array("required_validation_commands", "test_gl132"),
            "required_validation_commands must include GL-132",
        )

    def test_expected_reviewer_outputs_include_findings_by_severity(self):
        self.assertTrue(
            self._has_substring_in_array("expected_reviewer_outputs", "findings by severity"),
            "expected_reviewer_outputs must include findings by severity",
        )

    def test_expected_reviewer_outputs_include_must_fix_before_pilot(self):
        self.assertTrue(
            self._has_substring_in_array("expected_reviewer_outputs", "must-fix-before-pilot"),
            "expected_reviewer_outputs must include must-fix-before-pilot",
        )

    def test_expected_reviewer_outputs_include_must_fix_before_production_saas(self):
        self.assertTrue(
            self._has_substring_in_array("expected_reviewer_outputs", "must-fix-before-production-SaaS"),
            "expected_reviewer_outputs must include must-fix-before-production-SaaS",
        )

    def test_expected_reviewer_outputs_include_acceptable_caveats(self):
        self.assertTrue(
            self._has_substring_in_array("expected_reviewer_outputs", "acceptable pilot caveats"),
            "expected_reviewer_outputs must include acceptable pilot caveats",
        )

    def test_expected_reviewer_outputs_include_recommended_follow_up_issues(self):
        self.assertTrue(
            self._has_substring_in_array("expected_reviewer_outputs", "recommended follow-up issues"),
            "expected_reviewer_outputs must include recommended follow-up issues",
        )

    def test_go_criteria_present(self):
        arr = self.json_data.get("review_go_criteria", [])
        self.assertTrue(len(arr) > 0, "review_go_criteria must not be empty")

    def test_no_go_criteria_present(self):
        arr = self.json_data.get("review_no_go_criteria", [])
        self.assertTrue(len(arr) > 0, "review_no_go_criteria must not be empty")

    def test_related_gates_include_gl128(self):
        arr = self.json_data.get("related_gates", [])
        self.assertIn("GL-128", arr)

    def test_related_gates_include_gl129(self):
        arr = self.json_data.get("related_gates", [])
        self.assertIn("GL-129", arr)

    def test_related_gates_include_gl130(self):
        arr = self.json_data.get("related_gates", [])
        self.assertIn("GL-130", arr)

    def test_related_gates_include_gl131(self):
        arr = self.json_data.get("related_gates", [])
        self.assertIn("GL-131", arr)

    def test_related_gates_include_gl132(self):
        arr = self.json_data.get("related_gates", [])
        self.assertIn("GL-132", arr)

    def test_recommended_next_steps_include_gl134(self):
        arr = self.json_data.get("recommended_next_steps", [])
        self.assertTrue(
            any("gl-134" in str(item).lower() for item in arr),
            "recommended_next_steps must include GL-134",
        )

    def test_secret_safety_no_raw_tokens(self):
        ss = self.json_data.get("secret_safety", {})
        self.assertIs(ss.get("no_raw_tokens"), True)

    def test_secret_safety_no_raw_authorization_header(self):
        ss = self.json_data.get("secret_safety", {})
        self.assertIs(ss.get("no_raw_authorization_header"), True)

    def test_secret_safety_no_raw_request_bodies(self):
        ss = self.json_data.get("secret_safety", {})
        self.assertIs(ss.get("no_raw_request_bodies"), True)

    def test_secret_safety_no_db_passwords(self):
        ss = self.json_data.get("secret_safety", {})
        self.assertIs(ss.get("no_db_passwords"), True)

    def test_secret_safety_no_private_keys(self):
        ss = self.json_data.get("secret_safety", {})
        self.assertIs(ss.get("no_private_keys"), True)

    def test_secret_safety_no_backup_credentials(self):
        ss = self.json_data.get("secret_safety", {})
        self.assertIs(ss.get("no_backup_credentials"), True)


class TestGl133ScopeGuard(unittest.TestCase):
    """Verify no forbidden files were changed by GL-133."""

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
                self.fail(f"GL-133 must not change production code: {line}")

    def test_no_openapi_changed(self):
        changed = self._changed_files()
        self.assertNotIn(
            "openapi.yaml",
            changed,
            "GL-133 must not change the OpenAPI specification",
        )

    def test_no_migration_files_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if "migrations/" in line:
                self.fail(f"GL-133 must not change migration files: {line}")

    def test_no_frontend_or_website_files_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("frontend/") or line.startswith("website/"):
                self.fail(f"GL-133 must not change frontend or website files: {line}")

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
                        f"GL-133 must not change dependency file '{token}': {line}"
                    )

    def test_no_db_schema_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if "schema" in line.lower() and line.endswith(".sql"):
                self.fail(f"GL-133 must not change DB schema: {line}")

    def test_no_scripts_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("scripts/"):
                self.fail(f"GL-133 must not change scripts: {line}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
