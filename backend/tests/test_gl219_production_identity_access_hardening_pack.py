"""Tests for GL-219 Production Identity & Access Hardening Pack."""

from __future__ import annotations

import importlib
import json
import os
import py_compile
import subprocess
import sys
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "production_identity_access_hardening_pack.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl219",
    "production_identity_access_hardening_pack.json",
)
SCRIPT_PATH = os.path.join(REPO_ROOT, "scripts", "ops", "gl219_identity_access_gate.py")
IDENTITY_ACCESS_PATH = os.path.join(REPO_ROOT, "backend", "src", "identity_access.py")

REQUIRED_INPUT_SOURCES = [
    "docs/production_go_no_go_v5.md",
    "docs/examples/gl217/production_go_no_go_v5.json",
    "docs/production_iam_operator_control_completion.md",
    "docs/examples/gl214/production_iam_operator_control_completion.json",
    "docs/production_auth_secrets_config_hardening.md",
    "docs/examples/gl201/production_auth_secrets_config_hardening.json",
    "docs/admin_operator_tenant_control_plane.md",
    "docs/examples/gl206/admin_operator_tenant_control_plane.json",
    "docs/production_operations_hardening_pack.md",
    "docs/examples/gl216/production_operations_hardening_pack.json",
    "docs/tenant_workspace_production_guarantee.md",
    "docs/examples/gl215/tenant_workspace_production_guarantee.json",
    "docs/public_external_review_export_safety_pack.md",
    "docs/examples/gl218/public_external_review_export_safety_pack.json",
    "docs/runtime_abuse_incident_hardening.md",
    "docs/examples/gl208/runtime_abuse_incident_hardening.json",
    "docs/data_governance_audit_operations.md",
    "docs/examples/gl209/data_governance_audit_operations.json",
    "docs/openapi.yaml",
    "README.md",
    "SECURITY.md",
    "AGENTS.md",
    "llms.txt",
    "llms-full.txt",
    "backend/src/auth.py",
    "backend/src/config.py",
    "backend/src/operators.py",
    "backend/src/server.py",
    "backend/src/audit_log.py",
    "backend/src/db.py",
    "backend/src/models.py",
    "backend/tests/",
    "scripts/ops/gl216_production_operations_gate.py",
    "scripts/ops/gl218_public_export_safety_scan.py",
    "scripts/verify-first-output.sh",
    "examples/grant_lifecycle_evidence_bundle.py",
]

REQUIRED_JSON_KEYS = [
    "issue_id",
    "title",
    "result",
    "decision",
    "decision_rationale",
    "input_sources_reviewed",
    "current_admin_operator_auth_model",
    "identity_access_gap_assessment",
    "implemented_hardening_summary",
    "oauth_oidc_jwt_validation_posture",
    "issuer_audience_expiry_key_rotation_expectations",
    "static_admin_operator_token_safety",
    "fail_closed_behavior",
    "production_readiness_impact",
    "controlled_preview_impact",
    "remaining_identity_access_blockers",
    "risk_register",
    "findings",
    "safety_confirmations",
    "recommended_next_issues",
]

ALLOWED_CHANGED_FILES = {
    "backend/src/config.py",
    "backend/src/identity_access.py",
    "backend/tests/test_gl219_production_identity_access_hardening_pack.py",
    "docs/production_identity_access_hardening_pack.md",
    "docs/examples/gl219/production_identity_access_hardening_pack.json",
    "scripts/ops/gl219_identity_access_gate.py",
}


def _load_doc() -> str:
    with open(DOC_PATH, encoding="utf-8") as f:
        return f.read()


def _load_json() -> dict:
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _run_git(args: list[str]) -> list[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _branch_changed_files() -> set[str]:
    changed = set(_run_git(["diff", "--name-only", "main...HEAD"]))
    status_lines = _run_git(["status", "--porcelain", "--untracked-files=all"])
    for line in status_lines:
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        path = parts[1]
        if path.startswith("docs/website_design_") or path.startswith("docs/website-design-"):
            continue
        if path.startswith("website-design/"):
            continue
        changed.add(path)
    return changed


class TestGL219DocumentationArtifact(unittest.TestCase):
    def setUp(self):
        self.doc = _load_doc()
        self.data = _load_json()

    def test_files_exist_and_json_valid(self):
        self.assertTrue(os.path.isfile(DOC_PATH))
        self.assertTrue(os.path.isfile(JSON_PATH))
        self.assertIsInstance(self.data, dict)

    def test_issue_id_result_and_decision(self):
        self.assertEqual(self.data.get("issue_id"), "GL-219")
        self.assertEqual(self.data.get("result"), "ready_for_internal_review_with_blockers")
        self.assertEqual(
            self.data.get("decision"),
            "production_identity_access_hardening_pack_ready_for_internal_review_with_blockers",
        )

    def test_required_json_keys_exist(self):
        for key in REQUIRED_JSON_KEYS:
            self.assertIn(key, self.data)
            self.assertTrue(self.data[key] or self.data[key] is True, key)

    def test_input_sources_reviewed_exist(self):
        reviewed = set(self.data.get("input_sources_reviewed", []))
        for source in REQUIRED_INPUT_SOURCES:
            self.assertIn(source, reviewed)
            self.assertTrue(os.path.exists(os.path.join(REPO_ROOT, source.rstrip("/"))), source)

    def test_required_doc_sections_exist(self):
        required_sections = [
            "## Current Admin / Operator / Auth Model",
            "## Identity / Access Gap Assessment",
            "## Implemented Hardening Summary",
            "## OAuth / OIDC / JWT Validation Posture",
            "## Issuer / Audience / Expiry / Key Rotation Expectations",
            "## Static Admin / Operator Token Safety",
            "## Fail-Closed Behavior",
            "## Production-Readiness Impact",
            "## Controlled-Preview Impact",
            "## Remaining Identity / Access Blockers",
            "## Risk Register",
            "## Decision",
            "## Safety Confirmations",
        ]
        for section in required_sections:
            self.assertIn(section, self.doc)

    def test_docs_preserve_required_boundaries(self):
        required_text = [
            "Developer Preview / Controlled Preview with strict boundaries",
            "Production SaaS remains NO-GO",
            "Real customer data, private grant data, and institutional data remain NO-GO",
            "Official SDK/package remains NO-GO",
            "Live PostgreSQL production readiness remains NO-GO",
            "Compliance certification remains NO-GO",
            "Security-sensitive reports route to GitHub Security Advisories",
            "No exploit details are included",
            "No real secrets are included",
            "No real customer/private data is used",
            "synthetic/demo data only",
            "Unrelated website-design/import files were excluded from GL-219",
        ]
        for text in required_text:
            self.assertIn(text, self.doc)

    def test_json_safety_confirmations(self):
        confirmations = self.data.get("safety_confirmations", {})
        required_true = [
            "developer_preview_controlled_preview_with_strict_boundaries",
            "controlled_preview_synthetic_demo_data_only",
            "production_saas_no_go",
            "real_customer_private_grant_institutional_data_no_go",
            "official_sdk_package_no_go",
            "live_postgresql_production_no_go",
            "compliance_certification_no_go",
            "gdpr_soc2_iso_enterprise_readiness_not_claimed",
            "no_real_external_identity_provider_added",
            "no_oauth_oidc_saml_sso_mfa_user_account_ui_added",
            "no_third_party_dependencies_added",
            "no_migrations_added",
            "no_github_workflow_changes",
            "no_snapshot_publish_script_changes",
            "no_public_export_created",
            "no_raw_tokens_hashes_auth_headers_dsns_private_keys_credentials_included",
            "unrelated_website_design_import_files_excluded",
        ]
        for key in required_true:
            self.assertTrue(confirmations.get(key), key)

    def test_docs_do_not_include_forbidden_sensitive_or_overclaim_text(self):
        forbidden = [
            "Production SaaS is ready",
            "production-ready SaaS",
            "ready for real customer data",
            "ready for private grant data",
            "ready for institutional data",
            "official SDK is available",
            "compliance certified",
            "GDPR ready",
            "SOC2 ready",
            "ISO ready",
            "BEGIN PRIVATE KEY",
            "Bearer eyJ",
            "postgres://user:",
            "postgresql://user:",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, self.doc)

    def test_jwt_validation_requirements_are_represented(self):
        requirements = self.data["oauth_oidc_jwt_validation_posture"]
        expected = [
            "signature validation before claim trust",
            "explicit issuer allowlist with exact issuer match",
            "explicit audience allowlist with exact audience match",
            "expiration, not-before, and issued-at validation with bounded clock skew",
            "algorithm allowlist that rejects none and unexpected algorithms",
            "key rotation and retired-key handling with a documented overlap window",
        ]
        for item in expected:
            self.assertIn(item, requirements)


class TestGL219IdentityAccessHelpers(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, os.path.join(REPO_ROOT, "backend"))
        import src.identity_access as identity_access

        self.identity_access = importlib.reload(identity_access)

    def test_external_identity_config_fails_closed_in_production_like_mode(self):
        env = {
            "GRANTLAYER_ENABLE_OIDC": "true",
            "GRANTLAYER_OIDC_ISSUER": "issuer-placeholder",
            "GRANTLAYER_OIDC_AUDIENCE": "audience-placeholder",
        }
        errors = self.identity_access.external_identity_startup_errors(env, "production")
        self.assertEqual(len(errors), 2)
        joined = "\n".join(errors)
        self.assertIn("external_identity_provider_not_implemented", joined)
        self.assertIn("external_identity_config_present_without_validator", joined)
        self.assertNotIn("issuer-placeholder", joined)
        self.assertNotIn("audience-placeholder", joined)

    def test_external_identity_config_is_not_fatal_in_local_mode(self):
        env = {
            "GRANTLAYER_ENABLE_OIDC": "true",
            "GRANTLAYER_OIDC_ISSUER": "issuer-placeholder",
        }
        self.assertEqual(self.identity_access.external_identity_startup_errors(env, "local"), [])

    def test_posture_summary_is_safe_and_not_production_ready(self):
        env = {"GRANTLAYER_JWT_AUDIENCE": "audience-placeholder"}
        posture = self.identity_access.describe_identity_access_posture(env, "staging")
        self.assertFalse(posture["external_identity_provider_implemented"])
        self.assertEqual(posture["oauth_oidc_jwt_bearer_acceptance"], "not_implemented")
        self.assertFalse(posture["production_identity_ready"])
        self.assertFalse(posture["real_customer_private_data_ready"])
        self.assertIn("GRANTLAYER_JWT_AUDIENCE", posture["external_identity_config_vars_present"])
        self.assertNotIn("audience-placeholder", json.dumps(posture))

    def test_config_startup_errors_include_external_identity_gate(self):
        original_env = os.environ.copy()
        try:
            os.environ.clear()
            os.environ.update(
                {
                    "GRANTLAYER_RUNTIME_MODE": "production",
                    "GRANTLAYER_REQUIRE_ADMIN_TOKEN": "true",
                    "GRANTLAYER_ADMIN_TOKEN": "gl219-strong-admin-token-xyz123",
                    "GRANTLAYER_REQUIRE_CHALLENGE": "true",
                    "GRANTLAYER_ENABLE_DEMO_ENDPOINTS": "false",
                    "GRANTLAYER_ENABLE_OPERATOR_MODEL": "true",
                    "GRANTLAYER_ENABLE_JWT_AUTH": "true",
                }
            )
            import src.config as config_mod

            config_mod = importlib.reload(config_mod)
            errors = config_mod.startup_errors()
            self.assertTrue(any("external_identity_provider_not_implemented" in e for e in errors))
        finally:
            os.environ.clear()
            os.environ.update(original_env)


class TestGL219ScriptAndScope(unittest.TestCase):
    def test_new_python_files_compile(self):
        py_compile.compile(IDENTITY_ACCESS_PATH, doraise=True)
        py_compile.compile(SCRIPT_PATH, doraise=True)
        py_compile.compile(__file__, doraise=True)

    def test_gate_plan_and_json_dry_run(self):
        plan = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--plan"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("No network calls are made", plan.stdout)
        self.assertIn("not production readiness certification", plan.stdout)

        dry_run = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--dry-run", "--json"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(dry_run.stdout)
        self.assertEqual(payload["issue_id"], "GL-219")
        self.assertFalse(payload["external_services_contacted"])
        self.assertFalse(payload["tokens_read_or_logged"])
        self.assertFalse(payload["identity_access_posture"]["production_identity_ready"])

    def test_branch_scope_excludes_unrelated_website_design_files(self):
        if _run_git(["rev-parse", "--abbrev-ref", "HEAD"])[0] != "gl-219-production-identity-access-hardening-pack":
            return
        changed = _branch_changed_files()
        unexpected = changed - ALLOWED_CHANGED_FILES
        self.assertFalse(unexpected, f"Unexpected GL-219 changed files: {sorted(unexpected)}")
        self.assertNotIn("website-design/", changed)
        self.assertNotIn("docs/website_design_workspace_import_report.md", changed)
