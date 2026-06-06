"""Tests for GL-216 Production Operations Hardening Pack."""

from __future__ import annotations

import json
import os
import py_compile
import subprocess
import sys
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "production_operations_hardening_pack.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl216",
    "production_operations_hardening_pack.json",
)
SCRIPT_PATH = os.path.join(
    REPO_ROOT,
    "scripts",
    "ops",
    "gl216_production_operations_gate.py",
)

REQUIRED_INPUT_SOURCES = [
    "docs/production_readiness_gap_report_v4.md",
    "docs/examples/gl213/production_readiness_gap_report_v4.json",
    "docs/tenant_workspace_production_guarantee.md",
    "docs/examples/gl215/tenant_workspace_production_guarantee.json",
    "docs/production_iam_operator_control_completion.md",
    "docs/examples/gl214/production_iam_operator_control_completion.json",
    "docs/live_postgres_validation_execution_gl206b.md",
    "docs/examples/gl206b/live_postgres_validation_execution_gl206b.json",
    "docs/live_postgres_backup_observability_baseline.md",
    "docs/examples/gl205/live_postgres_backup_observability_baseline.json",
    "docs/data_governance_audit_operations.md",
    "docs/examples/gl209/data_governance_audit_operations.json",
    "docs/runtime_abuse_incident_hardening.md",
    "docs/examples/gl208/runtime_abuse_incident_hardening.json",
    "docs/admin_operator_tenant_control_plane.md",
    "docs/examples/gl206/admin_operator_tenant_control_plane.json",
    "docs/production_ops_go_no_go_v3.md",
    "docs/examples/gl204/production_ops_go_no_go_v3.json",
    "docs/persistence_postgres_migration_readiness.md",
    "docs/examples/gl202/persistence_postgres_migration_readiness.json",
    "docs/production_auth_secrets_config_hardening.md",
    "docs/examples/gl201/production_auth_secrets_config_hardening.json",
    "docs/public_external_review_readiness_gate_pack.md",
    "docs/examples/gl212/public_external_review_readiness_gate_pack.json",
    "docs/sdk_pilot_production_gate.md",
    "docs/examples/gl211/sdk_pilot_production_gate.json",
    "README.md",
    "SECURITY.md",
    "AGENTS.md",
    "llms.txt",
    "llms-full.txt",
    "docs/openapi.yaml",
]

REQUIRED_JSON_KEYS = [
    "issue_id",
    "title",
    "result",
    "decision",
    "decision_rationale",
    "input_sources_reviewed",
    "current_operations_state_summary",
    "production_operations_gap_assessment",
    "implemented_hardening_summary",
    "production_postgres_operations_posture",
    "migration_forward_rollback_strategy",
    "backup_restore_dr_posture",
    "observability_logging_correlation_posture",
    "alerting_monitoring_posture",
    "incident_response_posture",
    "abuse_rate_limit_operations_posture",
    "secret_key_rotation_lifecycle_posture",
    "retention_deletion_redaction_operations_posture",
    "audit_export_operations_posture",
    "tenant_workspace_operational_posture",
    "admin_operator_emergency_posture",
    "release_versioning_rollback_posture",
    "production_runbook_gate_checklist",
    "production_readiness_impact",
    "controlled_preview_impact",
    "remaining_operations_blockers",
    "risk_register",
    "findings",
    "safety_confirmations",
    "recommended_next_issues",
]

ALLOWED_RESULTS = {
    "ready_for_internal_review_with_blockers",
    "ready_for_merge_with_blockers",
    "blocked",
}
ALLOWED_DECISIONS = {
    "production_operations_hardening_pack_ready_for_internal_review_with_blockers",
    "production_operations_hardening_pack_ready_for_merge_with_blockers",
    "production_operations_hardening_pack_blocked",
}

ALLOWED_CHANGED_FILES = {
    "backend/tests/test_gl216_production_operations_hardening_pack.py",
    "docs/production_operations_hardening_pack.md",
    "docs/examples/gl216/production_operations_hardening_pack.json",
    "scripts/ops/gl216_production_operations_gate.py",
}


def _load_json() -> dict:
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_doc() -> str:
    with open(DOC_PATH, encoding="utf-8") as f:
        return f.read()


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
        if path.startswith("docs/website_design_") or path.startswith("website-design/"):
            continue
        changed.add(path)
    return changed


class TestGL216DocumentationArtifact(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.doc = _load_doc()

    def test_doc_and_json_exist_and_json_valid(self):
        self.assertTrue(os.path.isfile(DOC_PATH))
        self.assertTrue(os.path.isfile(JSON_PATH))
        self.assertIsInstance(self.data, dict)

    def test_issue_id_result_and_decision(self):
        self.assertEqual(self.data.get("issue_id"), "GL-216")
        self.assertIn(self.data.get("result"), ALLOWED_RESULTS)
        self.assertIn(self.data.get("decision"), ALLOWED_DECISIONS)

    def test_required_json_keys_exist(self):
        for key in REQUIRED_JSON_KEYS:
            self.assertIn(key, self.data)
            self.assertTrue(self.data[key] or self.data[key] is True, key)

    def test_input_sources_reviewed_exist(self):
        reviewed = set(self.data.get("input_sources_reviewed", []))
        for source in REQUIRED_INPUT_SOURCES:
            self.assertIn(source, reviewed)
            self.assertTrue(os.path.exists(os.path.join(REPO_ROOT, source)), source)

    def test_required_doc_sections_exist(self):
        required_phrases = [
            "Current Operations State Summary",
            "Production Operations Gap Assessment",
            "Implemented Hardening Summary",
            "Production PostgreSQL Operations Posture",
            "Migration Forward/Rollback Strategy",
            "Backup/Restore/DR Posture",
            "Observability/Logging/Correlation Posture",
            "Alerting/Monitoring Posture",
            "Incident Response Posture",
            "Abuse/Rate-Limit Operations Posture",
            "Secret/Key Rotation Lifecycle Posture",
            "Retention/Deletion/Redaction Operations Posture",
            "Audit Export/Operations Posture",
            "Tenant/Workspace Operational Posture",
            "Admin/Operator Emergency Posture",
            "Release/Versioning/Rollback Posture",
            "Production Runbook/Gate Checklist",
            "Production-Readiness Impact",
            "Controlled-Preview Impact",
            "Remaining Operations Blockers",
            "Risk Register",
            "Decision",
            "Decision Rationale",
            "Safety Confirmations",
            "Recommended Next Issues",
        ]
        for phrase in required_phrases:
            self.assertIn(phrase, self.doc)

    def test_docs_preserve_required_boundaries(self):
        required_text = [
            "Developer Preview / Controlled Preview with strict boundaries",
            "Production SaaS remains no-go",
            "Real customer data, private grant data, and institutional data remain no-go",
            "Official SDK/package remains no-go",
            "Compliance certification remains no-go",
            "Ephemeral live PostgreSQL validation passed, but production PostgreSQL readiness remains no-go",
            "Security-sensitive reports route to GitHub Security Advisories",
            "No exploit details are included",
            "No real secrets are included",
            "No real customer/private data is used",
        ]
        for text in required_text:
            self.assertIn(text, self.doc)

    def test_json_safety_confirmations(self):
        confirmations = self.data.get("safety_confirmations", {})
        required_true = [
            "developer_preview_controlled_preview_with_strict_boundaries",
            "controlled_preview_synthetic_demo_data_only",
            "not_production_saas",
            "real_customer_private_grant_institutional_data_no_go",
            "official_sdk_package_no_go",
            "compliance_certification_no_go",
            "ephemeral_live_postgres_not_production_postgres_readiness",
            "backup_restore_dr_not_overclaimed",
            "observability_incident_not_overclaimed",
            "security_reports_route_to_github_security_advisories",
            "no_exploit_details",
            "no_real_secrets",
            "no_real_customer_private_data",
        ]
        for key in required_true:
            self.assertTrue(confirmations.get(key), key)

    def test_docs_do_not_include_disallowed_claims_or_sensitive_data(self):
        forbidden_claims = [
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
            "production PostgreSQL ready",
        ]
        for phrase in forbidden_claims:
            self.assertNotIn(phrase, self.doc)
        secret_like_patterns = [
            "Bearer ",
            "BEGIN PRIVATE KEY",
            "postgres://user:",
            "postgresql://user:",
            "password=",
            "token_hash",
        ]
        for pattern in secret_like_patterns:
            self.assertNotIn(pattern, self.doc)


class TestGL216GateScript(unittest.TestCase):
    def _clean_env(self) -> dict[str, str]:
        env = os.environ.copy()
        for name in list(env):
            upper = name.upper()
            if (
                upper.startswith("GRANTLAYER")
                or upper in {"DATABASE_URL", "PGURL", "POSTGRES_URL"}
                or "TOKEN" in upper
                or "PASSWORD" in upper
                or "SECRET" in upper
                or "PRIVATE_KEY" in upper
            ):
                env.pop(name, None)
        return env

    def test_script_exists_and_compiles(self):
        self.assertTrue(os.path.isfile(SCRIPT_PATH))
        py_compile.compile(SCRIPT_PATH, doraise=True)

    def test_script_supports_dry_run_and_json_without_secrets(self):
        proc = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--dry-run", "--json"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            env=self._clean_env(),
            check=True,
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["issue_id"], "GL-216")
        self.assertTrue(data["not_production_readiness_certification"])
        self.assertFalse(data["external_services_contacted"])
        self.assertFalse(data["network_required"])
        self.assertFalse(data["credentials_required"])
        self.assertFalse(data["destructive_operations"])
        self.assertNotIn("secret-value", proc.stdout)

    def test_script_supports_plan(self):
        proc = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--plan"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            env=self._clean_env(),
            check=True,
        )
        self.assertIn("PLAN mode", proc.stdout)
        self.assertIn("No network calls are made", proc.stdout)
        self.assertIn("not production readiness certification", proc.stdout)

    def test_script_rejects_unsafe_production_like_dsn_and_redacts(self):
        env = self._clean_env()
        env["GRANTLAYER_DATABASE_URL"] = "postgres://user:secret-value@prod-db.example/app"
        proc = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--dry-run", "--json"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertEqual(data["result"], "blocked")
        self.assertTrue(data["unsafe_environment_findings"])
        self.assertIn("user:***@", proc.stdout)
        self.assertNotIn("secret-value", proc.stdout)


class TestGL216ForbiddenChanges(unittest.TestCase):
    def test_only_allowed_files_changed_excluding_known_untracked_website_imports(self):
        changed = _branch_changed_files()
        unexpected = changed - ALLOWED_CHANGED_FILES
        self.assertFalse(unexpected, f"Unexpected GL-216 files changed: {sorted(unexpected)}")

    def test_forbidden_files_not_added_or_changed(self):
        changed = _branch_changed_files()
        forbidden_exact = {
            "setup.py",
            "package.json",
            "package-lock.json",
            "pyproject.toml",
            "sdk/pyproject.toml",
            "examples/sdk_prototype/python/pyproject.toml",
        }
        forbidden_prefixes = (
            ".github/workflows/",
            "website/",
            "frontend/",
            "website-design/",
            "backend/src/",
            "backend/src/migrations/",
            "scripts/public",
            "scripts/snapshot",
            "public-export/",
            "public_snapshot/",
            "dist/",
            "release/",
            "deploy/",
            "terraform/",
            "kubernetes/",
            "helm/",
            "cloud/",
        )
        for path in changed:
            self.assertNotIn(path, forbidden_exact)
            self.assertFalse(path.startswith(forbidden_prefixes), path)

    def test_unrelated_website_design_import_files_are_excluded(self):
        changed = _branch_changed_files()
        self.assertFalse(any(path.startswith("website-design/") for path in changed))
        self.assertFalse(any(path.startswith("docs/website_design_") for path in changed))

    def test_no_public_publish_or_visibility_behavior_in_gl216_files(self):
        combined = _load_doc() + json.dumps(_load_json(), sort_keys=True)
        forbidden = [
            "git push public",
            "gh repo edit",
            "visibility public",
            "public publish script",
            "package publishing enabled",
            "official SDK/package availability",
            "production deployment config added",
            "cloud provider integration added",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, combined)


if __name__ == "__main__":
    unittest.main()
