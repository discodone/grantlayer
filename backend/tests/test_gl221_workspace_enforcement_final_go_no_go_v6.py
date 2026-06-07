"""Tests for GL-221 Workspace Enforcement & Final Go/No-Go v6."""

from __future__ import annotations

import json
import os
import py_compile
import subprocess
import sys
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "workspace_enforcement_final_go_no_go_v6.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl221",
    "workspace_enforcement_final_go_no_go_v6.json",
)
SCRIPT_PATH = os.path.join(REPO_ROOT, "scripts", "ops", "gl221_workspace_go_no_go_gate.py")

REQUIRED_INPUT_SOURCES = [
    "docs/production_go_no_go_v5.md",
    "docs/examples/gl217/production_go_no_go_v5.json",
    "docs/production_runtime_infrastructure_hardening_pack.md",
    "docs/examples/gl220/production_runtime_infrastructure_hardening_pack.json",
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
    "docs/admin_operator_tenant_control_plane.md",
    "docs/examples/gl206/admin_operator_tenant_control_plane.json",
    "docs/tenant_workspace_data_model_design.md",
    "docs/examples/gl144/tenant_workspace_data_model_design.json",
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
]

REQUIRED_JSON_KEYS = [
    "issue_id",
    "title",
    "result",
    "decision",
    "decision_rationale",
    "input_sources_reviewed",
    "current_workspace_enforcement_state_summary",
    "workspace_enforcement_gap_assessment",
    "implemented_hardening_summary",
    "workspace_id_derivation_trust_model",
    "tenant_workspace_relationship_model",
    "unsafe_workspace_override_prevention",
    "cross_workspace_lookup_denial_posture",
    "cross_workspace_mutation_denial_posture",
    "workspace_propagation_audit_evidence_provenance_compliance",
    "admin_operator_workspace_boundary",
    "demo_synthetic_workspace_boundary",
    "controlled_external_review_workspace_boundary",
    "production_readiness_impact",
    "controlled_preview_impact",
    "final_readiness_matrix_v6",
    "production_saas_decision",
    "real_customer_data_decision",
    "private_grant_institutional_data_decision",
    "controlled_external_review_decision",
    "public_snapshot_public_publish_decision",
    "official_sdk_package_decision",
    "live_postgres_production_readiness_decision",
    "iam_identity_decision_after_gl219",
    "runtime_infrastructure_decision_after_gl220",
    "public_export_decision_after_gl218",
    "remaining_blockers",
    "risk_register_v6",
    "compact_next_roadmap",
    "findings",
    "safety_confirmations",
    "recommended_next_issues",
]

REQUIRED_SECTIONS = [
    "## Context",
    "## Scope",
    "## Non-Goals",
    "## Input Sources Reviewed",
    "## Current Workspace Enforcement State Summary",
    "## Workspace Enforcement Gap Assessment",
    "## Implemented Hardening Summary",
    "## workspace_id Derivation/Trust Model",
    "## Tenant/Workspace Relationship Model",
    "## Unsafe Workspace Override Prevention",
    "## Cross-Workspace Lookup Denial Posture",
    "## Cross-Workspace Mutation Denial Posture",
    "## Workspace Propagation Into Audit/Evidence/Provenance/Compliance",
    "## Admin/Operator Workspace Boundary",
    "## Demo/Synthetic Workspace Boundary",
    "## Controlled External Review Workspace Boundary",
    "## Production-Readiness Impact",
    "## Controlled Preview Impact",
    "## Final Readiness Matrix v6",
    "## Production SaaS Decision",
    "## Real Customer Data Decision",
    "## Private Grant/Institutional Data Decision",
    "## Controlled External Review Decision",
    "## Public Snapshot/Public Publish Decision",
    "## Official SDK/Package Decision",
    "## Live PostgreSQL Production Readiness Decision",
    "## IAM/Identity Decision After GL-219",
    "## Runtime/Infrastructure Decision After GL-220",
    "## Public/Export Decision After GL-218",
    "## Remaining P0/P1/P2 Blockers",
    "## Risk Register v6",
    "## Compact Next Roadmap",
    "## Decision",
    "## Decision Rationale",
    "## Findings",
    "## Safety Confirmations",
    "## Recommended Next Issues",
]

ALLOWED_CHANGED_FILES = {
    "backend/tests/test_gl221_workspace_enforcement_final_go_no_go_v6.py",
    "docs/workspace_enforcement_final_go_no_go_v6.md",
    "docs/examples/gl221/workspace_enforcement_final_go_no_go_v6.json",
    "scripts/ops/gl221_workspace_go_no_go_gate.py",
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


class TestGL221DocumentationArtifact(unittest.TestCase):
    def setUp(self):
        self.doc = _load_doc()
        self.data = _load_json()
        self.combined = self.doc + "\n" + json.dumps(self.data, sort_keys=True)
        self.combined_lower = self.combined.lower()

    def test_files_exist_and_json_valid(self):
        self.assertTrue(os.path.isfile(DOC_PATH))
        self.assertTrue(os.path.isfile(JSON_PATH))
        self.assertIsInstance(self.data, dict)

    def test_issue_id_and_required_keys(self):
        self.assertEqual(self.data.get("issue_id"), "GL-221")
        for key in REQUIRED_JSON_KEYS:
            self.assertIn(key, self.data)
            self.assertTrue(self.data[key] or self.data[key] is True, key)

    def test_required_markdown_sections_exist(self):
        for section in REQUIRED_SECTIONS:
            self.assertIn(section, self.doc)

    def test_input_sources_reviewed_exist(self):
        reviewed = set(self.data["input_sources_reviewed"])
        for source in REQUIRED_INPUT_SOURCES:
            self.assertIn(source, reviewed)
            self.assertTrue(os.path.exists(os.path.join(REPO_ROOT, source)), source)

    def test_final_readiness_matrix_v6_is_conservative(self):
        matrix = self.data["final_readiness_matrix_v6"]
        self.assertEqual(matrix["developer_preview"], "GO / CONTINUE")
        self.assertEqual(matrix["controlled_external_technical_review"], "GO with strict boundaries")
        self.assertEqual(matrix["synthetic_demo_controlled_pilot"], "CONDITIONAL")
        self.assertIn("separate explicit gate", matrix["public_snapshot_preparation"])
        self.assertEqual(matrix["public_website_publish"], "DEFER / NO-GO")
        self.assertEqual(matrix["official_sdk_package"], "NO-GO")
        self.assertEqual(matrix["real_customer_data"], "NO-GO")
        self.assertEqual(matrix["private_grant_institutional_data"], "NO-GO")
        self.assertEqual(matrix["production_saas"], "NO-GO")
        self.assertEqual(matrix["compliance_certification"], "NO-GO")
        self.assertEqual(matrix["live_postgresql_production_readiness"], "NO-GO")

    def test_no_overclaimed_readiness(self):
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
            "live PostgreSQL production ready",
            "enterprise ready",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, self.combined)
        self.assertEqual(self.data["production_saas_decision"], "NO-GO")
        self.assertEqual(self.data["real_customer_data_decision"], "NO-GO")
        self.assertEqual(self.data["private_grant_institutional_data_decision"], "NO-GO")
        self.assertEqual(self.data["official_sdk_package_decision"], "NO-GO")
        self.assertEqual(self.data["live_postgres_production_readiness_decision"], "NO-GO")

    def test_required_boundaries_are_explicit(self):
        required = [
            "not an automatic production release",
            "Developer Preview / Controlled Preview with strict boundaries",
            "Public snapshot/export and public website publish remain separate-gate only",
            "Controlled external technical review remains GO with strict boundaries",
            "No exploit details are included",
            "No real secrets are included",
            "No real customer/private data is used",
            "workspace_id is reserved/nullable and not production-enforced",
        ]
        for phrase in required:
            self.assertIn(phrase.lower(), self.combined_lower)

    def test_risk_register_and_roadmap_shape(self):
        risks = self.data["risk_register_v6"]
        self.assertGreaterEqual(len(risks), 3)
        for risk in risks:
            for key in ("severity", "status", "mitigation", "remaining_work"):
                self.assertIn(key, risk)
                self.assertTrue(risk[key])
        self.assertGreaterEqual(len(self.data["compact_next_roadmap"]), 3)

    def test_docs_include_no_sensitive_content(self):
        forbidden = [
            "BEGIN " + "PRIVATE KEY",
            "Bearer eyJ",
            "postgres" + "://user:",
            "postgresql" + "://user:",
            "password=",
            "token_hash",
            "authorization:",
            "customer data sample",
            "private grant sample",
            "institutional data sample",
            "exploit steps",
            "proof of concept exploit",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase.lower(), self.combined_lower)

    def test_safety_confirmations(self):
        confirmations = self.data["safety_confirmations"]
        required_true = [
            "gl221_not_automatic_production_release",
            "developer_preview_controlled_preview_with_strict_boundaries",
            "production_saas_no_go",
            "real_customer_private_grant_institutional_data_no_go",
            "official_sdk_package_no_go",
            "compliance_certification_no_go",
            "live_postgresql_production_no_go",
            "public_snapshot_export_separate_gate_only",
            "public_website_publish_separate_gate_only",
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
            "unrelated_website_design_import_files_excluded",
            "gl215_tenant_workspace_behavior_preserved",
            "gl219_identity_access_behavior_preserved",
            "gl220_runtime_infrastructure_behavior_preserved",
        ]
        for key in required_true:
            self.assertTrue(confirmations.get(key), key)


class TestGL221GateScript(unittest.TestCase):
    def test_script_exists_and_compiles(self):
        self.assertTrue(os.path.isfile(SCRIPT_PATH))
        py_compile.compile(SCRIPT_PATH, doraise=True)
        py_compile.compile(__file__, doraise=True)

    def test_script_plan(self):
        proc = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--plan"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("PLAN mode", proc.stdout)
        self.assertIn("No network calls are made", proc.stdout)
        self.assertIn("not production readiness certification", proc.stdout)

    def test_script_dry_run_json(self):
        proc = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--dry-run", "--json"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["issue_id"], "GL-221")
        self.assertTrue(data["not_production_readiness_certification"])
        self.assertFalse(data["external_services_contacted"])
        self.assertFalse(data["credentials_required"])
        self.assertFalse(data["destructive_operations"])
        self.assertFalse(data["public_artifacts_created"])
        self.assertFalse(data["packages_published"])
        self.assertFalse(data["deployment_artifacts_created"])


class TestGL221ForbiddenChanges(unittest.TestCase):
    def test_only_allowed_files_changed_excluding_known_untracked_website_imports(self):
        changed = _branch_changed_files()
        unexpected = changed - ALLOWED_CHANGED_FILES
        self.assertFalse(unexpected, f"Unexpected GL-221 files changed: {sorted(unexpected)}")

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
            "backend/src/migrations/",
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


if __name__ == "__main__":
    unittest.main()
