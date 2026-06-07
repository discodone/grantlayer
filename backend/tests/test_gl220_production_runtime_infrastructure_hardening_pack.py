"""Tests for GL-220 Production Runtime & Infrastructure Hardening Pack."""

from __future__ import annotations

import json
import os
import py_compile
import subprocess
import sys
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "production_runtime_infrastructure_hardening_pack.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl220",
    "production_runtime_infrastructure_hardening_pack.json",
)
SCRIPT_PATH = os.path.join(REPO_ROOT, "scripts", "ops", "gl220_runtime_infrastructure_gate.py")

REQUIRED_INPUT_SOURCES = [
    "docs/production_go_no_go_v5.md",
    "docs/examples/gl217/production_go_no_go_v5.json",
    "docs/production_identity_access_hardening_pack.md",
    "docs/examples/gl219/production_identity_access_hardening_pack.json",
    "docs/public_external_review_export_safety_pack.md",
    "docs/examples/gl218/public_external_review_export_safety_pack.json",
    "docs/production_operations_hardening_pack.md",
    "docs/examples/gl216/production_operations_hardening_pack.json",
    "docs/tenant_workspace_production_guarantee.md",
    "docs/examples/gl215/tenant_workspace_production_guarantee.json",
    "docs/production_iam_operator_control_completion.md",
    "docs/examples/gl214/production_iam_operator_control_completion.json",
    "docs/runtime_abuse_incident_hardening.md",
    "docs/examples/gl208/runtime_abuse_incident_hardening.json",
    "docs/live_postgres_backup_observability_baseline.md",
    "docs/examples/gl205/live_postgres_backup_observability_baseline.json",
    "docs/production_ops_go_no_go_v3.md",
    "docs/examples/gl204/production_ops_go_no_go_v3.json",
    "README.md",
    "SECURITY.md",
    "AGENTS.md",
    "llms.txt",
    "llms-full.txt",
    "docs/openapi.yaml",
    "backend/src/server.py",
    "backend/src/config.py",
    "backend/src/auth.py",
    "backend/src/identity_access.py",
    "backend/src/operators.py",
    "backend/src/audit_log.py",
    "backend/src/db.py",
    "backend/src/models.py",
    "backend/tests/",
    "scripts/ops/gl216_production_operations_gate.py",
    "scripts/ops/gl218_public_export_safety_scan.py",
    "scripts/ops/gl219_identity_access_gate.py",
    "scripts/ops/gl205_live_postgres_validation.py",
    "scripts/ops/gl205_backup_restore_drill.py",
    "scripts/ops/gl209_audit_export_check.py",
    "scripts/run-full-backend-suite.sh",
    "examples/grant_lifecycle_evidence_bundle.py",
]

REQUIRED_JSON_KEYS = [
    "issue_id",
    "title",
    "result",
    "decision",
    "decision_rationale",
    "input_sources_reviewed",
    "current_runtime_infrastructure_state_summary",
    "production_runtime_infrastructure_gap_assessment",
    "implemented_hardening_summary",
    "tls_https_reverse_proxy_posture",
    "container_runtime_hardening_posture",
    "process_supervisor_service_model_posture",
    "runtime_environment_secret_handling_posture",
    "production_config_fail_closed_posture",
    "request_size_timeout_concurrency_posture",
    "rate_limit_runtime_abuse_posture",
    "network_exposure_ingress_posture",
    "health_readiness_runtime_posture",
    "logging_correlation_observability_posture",
    "external_monitoring_alerting_requirements",
    "backup_restore_dr_runtime_integration_posture",
    "postgres_runtime_connectivity_posture",
    "identity_access_runtime_dependency_posture",
    "tenant_workspace_runtime_enforcement_posture",
    "release_rollback_runtime_recovery_posture",
    "optional_runtime_gate_script_summary",
    "production_readiness_impact",
    "controlled_preview_impact",
    "remaining_runtime_infrastructure_blockers",
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
    "production_runtime_infrastructure_hardening_pack_ready_for_internal_review_with_blockers",
    "production_runtime_infrastructure_hardening_pack_ready_for_merge_with_blockers",
    "production_runtime_infrastructure_hardening_pack_blocked",
}

ALLOWED_CHANGED_FILES = {
    "backend/tests/test_gl220_production_runtime_infrastructure_hardening_pack.py",
    "docs/production_runtime_infrastructure_hardening_pack.md",
    "docs/examples/gl220/production_runtime_infrastructure_hardening_pack.json",
    "scripts/ops/gl220_runtime_infrastructure_gate.py",
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


class TestGL220DocumentationArtifact(unittest.TestCase):
    def setUp(self):
        self.doc = _load_doc()
        self.data = _load_json()

    def test_files_exist_and_json_valid(self):
        self.assertTrue(os.path.isfile(DOC_PATH))
        self.assertTrue(os.path.isfile(JSON_PATH))
        self.assertIsInstance(self.data, dict)

    def test_issue_id_result_and_decision(self):
        self.assertEqual(self.data.get("issue_id"), "GL-220")
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
            self.assertTrue(os.path.exists(os.path.join(REPO_ROOT, source.rstrip("/"))), source)

    def test_required_doc_sections_exist(self):
        required_sections = [
            "## Context",
            "## Scope",
            "## Non-Goals",
            "## Input Sources Reviewed",
            "## Current Runtime/Infrastructure State Summary",
            "## Production Runtime/Infrastructure Gap Assessment",
            "## Implemented Hardening Summary",
            "## TLS / HTTPS / Reverse Proxy Posture",
            "## Container/Runtime Hardening Posture",
            "## Process Supervisor/Service Model Posture",
            "## Runtime Environment and Secret Handling Posture",
            "## Production Config Fail-Closed Posture",
            "## Request Size / Timeout / Concurrency Posture",
            "## Rate-Limit/Runtime Abuse Posture",
            "## Network Exposure / Ingress Posture",
            "## Health/Readiness Runtime Posture",
            "## Logging/Correlation/Observability Posture",
            "## External Monitoring/Alerting Requirements",
            "## Backup/Restore/DR Runtime Integration Posture",
            "## PostgreSQL Runtime Connectivity Posture",
            "## Identity/Access Runtime Dependency Posture",
            "## Tenant/Workspace Runtime Enforcement Posture",
            "## Release/Rollback/Runtime Recovery Posture",
            "## Optional Runtime Gate Script Summary",
            "## Production-Readiness Impact",
            "## Controlled-Preview Impact",
            "## Remaining Runtime/Infrastructure Blockers",
            "## Risk Register",
            "## Decision",
            "## Decision Rationale",
            "## Safety Confirmations",
            "## Recommended Next Issues",
        ]
        for section in required_sections:
            self.assertIn(section, self.doc)

    def test_required_safety_boundaries_are_documented(self):
        required_text = [
            "GL-220 is runtime/infrastructure hardening, not production SaaS readiness",
            "Developer Preview / Controlled Preview with strict boundaries",
            "Production SaaS remains NO-GO",
            "Real customer data, private grant data, and institutional data remain NO-GO",
            "Official SDK/package remains NO-GO",
            "Compliance certification remains NO-GO",
            "Live PostgreSQL production readiness remains NO-GO",
            "No real cloud, deployment, TLS certificate, external hostname, monitoring, or production secret rollout is performed by GL-220",
            "Security-sensitive reports route to GitHub Security Advisories",
            "No exploit details are included",
            "No real secrets are included",
            "No real customer/private data is used",
            "Unrelated website-design/import files were excluded from GL-220",
        ]
        for text in required_text:
            self.assertIn(text, self.doc)

    def test_json_safety_confirmations(self):
        confirmations = self.data.get("safety_confirmations", {})
        required_true = [
            "developer_preview_controlled_preview_with_strict_boundaries",
            "controlled_preview_synthetic_demo_data_only",
            "gl220_runtime_infrastructure_hardening_not_production_saas_readiness",
            "production_saas_no_go",
            "real_customer_private_grant_institutional_data_no_go",
            "official_sdk_package_no_go",
            "compliance_certification_no_go",
            "live_postgresql_production_no_go",
            "no_real_cloud_deployment_tls_external_hostname_monitoring_or_production_secret_rollout",
            "security_reports_route_to_github_security_advisories",
            "no_exploit_details",
            "no_real_secrets",
            "no_real_customer_private_data",
            "no_github_workflow_changes",
            "no_snapshot_publish_script_changes",
            "no_public_github_push",
            "no_public_publish",
            "no_visibility_change",
            "no_migrations_db_schema_dependency_changes",
            "no_package_publishing_metadata",
            "no_setup_py",
            "no_sdk_pyproject",
            "no_package_json_or_lock",
            "no_public_snapshot_export_directory",
            "no_production_deployment_config_cloud_kubernetes_terraform_helm",
            "no_tls_certificate_or_private_key_files",
            "gl216_operations_behavior_preserved",
            "gl218_public_export_safety_behavior_preserved",
            "gl219_identity_access_behavior_preserved",
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
            "GD" + "PR ready",
            "SO" + "C2 ready",
            "IS" + "O ready",
            "live PostgreSQL production ready",
            "production infrastructure certified",
            "BEGIN " + "PRIVATE KEY",
            "Bearer eyJ",
            "postgres" + "://user:",
            "postgresql" + "://user:",
            "password=",
        ]
        combined = self.doc + json.dumps(self.data, sort_keys=True)
        for phrase in forbidden:
            self.assertNotIn(phrase, combined)


class TestGL220RuntimeInfrastructureGateScript(unittest.TestCase):
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
                or upper.startswith(("AWS_", "GCP_", "AZURE_"))
            ):
                env.pop(name, None)
        return env

    def test_script_exists_and_compiles(self):
        self.assertTrue(os.path.isfile(SCRIPT_PATH))
        py_compile.compile(SCRIPT_PATH, doraise=True)
        py_compile.compile(__file__, doraise=True)

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
        self.assertIn("not production infrastructure certification", proc.stdout)

    def test_script_supports_dry_run_and_json_without_credentials(self):
        proc = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--dry-run", "--json"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            env=self._clean_env(),
            check=True,
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["issue_id"], "GL-220")
        self.assertTrue(data["not_production_infrastructure_certification"])
        self.assertFalse(data["external_services_contacted"])
        self.assertFalse(data["network_required"])
        self.assertFalse(data["credentials_required"])
        self.assertFalse(data["destructive_operations"])
        self.assertFalse(data["deployment_artifacts_created"])
        self.assertFalse(data["cloud_resources_created"])
        self.assertFalse(data["tls_certificates_or_private_keys_written"])
        self.assertNotIn("secret-value", proc.stdout)

    def test_script_flags_unsafe_production_like_env_and_redacts(self):
        env = self._clean_env()
        env["GRANTLAYER_PRODUCTION_DATABASE_URL"] = "unsafe-placeholder-value"
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
        self.assertIn('"redacted_value": "***"', proc.stdout)
        self.assertNotIn("unsafe-placeholder-value", proc.stdout)


class TestGL220ForbiddenChanges(unittest.TestCase):
    def test_only_allowed_files_changed_excluding_known_untracked_website_imports(self):
        changed = _branch_changed_files()
        unexpected = changed - ALLOWED_CHANGED_FILES
        self.assertFalse(unexpected, f"Unexpected GL-220 files changed: {sorted(unexpected)}")

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
            "deployment/",
            "terraform/",
            "kubernetes/",
            "helm/",
            "cloud/",
        )
        forbidden_suffixes = (".tf", ".tfvars", ".pem", ".key", ".crt", ".cer", ".p12", ".pfx")
        for path in changed:
            self.assertNotIn(path, forbidden_exact)
            if path not in ALLOWED_CHANGED_FILES:
                self.assertFalse(path.startswith(forbidden_prefixes), path)
            self.assertFalse(path.lower().endswith(forbidden_suffixes), path)

    def test_unrelated_website_design_import_files_are_excluded(self):
        changed = _branch_changed_files()
        self.assertFalse(any(path.startswith("website-design/") for path in changed))
        self.assertFalse(any(path.startswith("docs/website_design_") for path in changed))
        self.assertFalse(any(path.startswith("docs/website-design-") for path in changed))

    def test_no_public_publish_package_deployment_or_visibility_behavior(self):
        combined = _load_doc() + json.dumps(_load_json(), sort_keys=True)
        forbidden = [
            "git push public",
            "gh repo edit",
            "visibility public",
            "public publish script",
            "package publishing enabled",
            "production deployment config added",
            "cloud provider integration added",
            "Kubernetes deployment added",
            "Terraform deployment added",
            "Helm deployment added",
            "TLS private key added",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, combined)


if __name__ == "__main__":
    unittest.main()
