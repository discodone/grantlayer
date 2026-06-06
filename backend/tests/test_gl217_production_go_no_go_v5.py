"""Tests for GL-217 Production Go/No-Go v5."""

from __future__ import annotations

import json
import os
import py_compile
import subprocess
import sys
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "production_go_no_go_v5.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl217",
    "production_go_no_go_v5.json",
)

REQUIRED_MD_SECTIONS = [
    "## Context",
    "## Scope",
    "## Non-Goals",
    "## Input Sources Reviewed",
    "## Current State Summary",
    "## Progress Since GL-213",
    "### GL-214 Impact Summary",
    "### GL-215 Impact Summary",
    "### GL-216 Impact Summary",
    "## Readiness Tier Decision Matrix",
    "## Production SaaS Go/No-Go Decision",
    "## Real Customer Data Decision",
    "## Private Grant / Institutional Data Decision",
    "## Controlled External Review Decision",
    "## Public Snapshot / Public Publish Decision",
    "## Official SDK / Package Decision",
    "## Live PostgreSQL Readiness Decision",
    "## IAM / Operator Readiness Assessment",
    "## Tenant / Workspace Readiness Assessment",
    "## Production Operations Readiness Assessment",
    "## Backup / Restore / DR Readiness Assessment",
    "## Observability / Incident Readiness Assessment",
    "## Audit / Data Governance Readiness Assessment",
    "## Security / Compliance Readiness Assessment",
    "## Remaining P0 / P1 / P2 Blockers",
    "## Risk Register v5",
    "## Compact Next Roadmap",
    "## Final Decision",
    "## Decision Rationale",
    "## Safety Confirmations",
    "## Recommended Next Issues",
]

REQUIRED_JSON_KEYS = [
    "issue_id",
    "title",
    "result",
    "final_decision",
    "decision_rationale",
    "input_sources_reviewed",
    "current_state_summary",
    "progress_since_gl213",
    "readiness_tier_decision_matrix",
    "production_saas_decision",
    "real_customer_data_decision",
    "private_grant_institutional_data_decision",
    "controlled_external_review_decision",
    "public_snapshot_public_publish_decision",
    "official_sdk_package_decision",
    "live_postgres_readiness_decision",
    "iam_operator_readiness_assessment",
    "tenant_workspace_readiness_assessment",
    "production_operations_readiness_assessment",
    "backup_restore_dr_readiness_assessment",
    "observability_incident_readiness_assessment",
    "audit_data_governance_readiness_assessment",
    "security_compliance_readiness_assessment",
    "remaining_blockers",
    "risk_register_v5",
    "compact_next_roadmap",
    "findings",
    "safety_confirmations",
    "recommended_next_issues",
]

REQUIRED_INPUT_SOURCES = [
    "docs/production_operations_hardening_pack.md",
    "docs/examples/gl216/production_operations_hardening_pack.json",
    "docs/tenant_workspace_production_guarantee.md",
    "docs/examples/gl215/tenant_workspace_production_guarantee.json",
    "docs/production_iam_operator_control_completion.md",
    "docs/examples/gl214/production_iam_operator_control_completion.json",
    "docs/production_readiness_gap_report_v4.md",
    "docs/examples/gl213/production_readiness_gap_report_v4.json",
    "docs/public_external_review_readiness_gate_pack.md",
    "docs/examples/gl212/public_external_review_readiness_gate_pack.json",
    "docs/live_postgres_validation_execution_gl206b.md",
    "docs/examples/gl206b/live_postgres_validation_execution_gl206b.json",
    "docs/live_postgres_backup_observability_baseline.md",
    "docs/examples/gl205/live_postgres_backup_observability_baseline.json",
    "docs/production_ops_go_no_go_v3.md",
    "docs/examples/gl204/production_ops_go_no_go_v3.json",
    "README.md",
    "SECURITY.md",
    "AGENTS.md",
]

ALLOWED_CHANGED_FILES = {
    "docs/production_go_no_go_v5.md",
    "docs/examples/gl217/production_go_no_go_v5.json",
    "backend/tests/test_gl217_production_go_no_go_v5.py",
}

NO_GO_TIERS = {
    "production_saas",
    "official_sdk_package",
    "real_customer_data",
    "private_grant_institutional_data",
    "compliance_certification",
    "live_postgres_production_readiness",
}

PRODUCTION_SAAS_NO_GO_INDICATORS = {
    "NO-GO",
    "no_go",
    "not_production_saas",
    "no-go",
}

FORBIDDEN_OVERCLAIMS = [
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
    "live PostgreSQL production ready",
    "PostgreSQL production readiness: GO",
    "PostgreSQL production readiness: ready",
]

FORBIDDEN_SENSITIVE_CONTENT = [
    "Bearer ",
    "BEGIN PRIVATE KEY",
    "postgres://user:",
    "postgresql://user:",
    "password=",
]

FORBIDDEN_FILES_EXACT = {
    "setup.py",
    "package.json",
    "package-lock.json",
    "pyproject.toml",
    "sdk/pyproject.toml",
    "examples/sdk_prototype/python/pyproject.toml",
}

FORBIDDEN_FILE_PREFIXES = (
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

FORBIDDEN_PUBLISH_PHRASES = [
    "git push public",
    "gh repo edit",
    "visibility public",
    "public publish script",
    "package publishing enabled",
    "official SDK/package availability",
    "production deployment config added",
    "cloud provider integration added",
    "production SaaS is ready",
    "production PostgreSQL ready",
]


def _branch_changed_files() -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1...HEAD"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )
    lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    excluded_prefixes = (
        "website-design/",
        "docs/website_design_",
        "docs/website-design-",
    )
    return {
        f for f in lines if not any(f.startswith(p) for p in excluded_prefixes)
    }


def _load_doc() -> str:
    with open(DOC_PATH, encoding="utf-8") as f:
        return f.read()


def _load_json() -> dict:
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestGL217FilesExist(unittest.TestCase):
    def test_markdown_file_exists(self):
        self.assertTrue(os.path.isfile(DOC_PATH), f"Missing: {DOC_PATH}")

    def test_json_file_exists(self):
        self.assertTrue(os.path.isfile(JSON_PATH), f"Missing: {JSON_PATH}")

    def test_json_is_valid(self):
        data = _load_json()
        self.assertIsInstance(data, dict)

    def test_issue_id_is_gl217(self):
        data = _load_json()
        self.assertEqual(data.get("issue_id"), "GL-217")

    def test_this_file_compiles(self):
        py_compile.compile(__file__, doraise=True)


class TestGL217MarkdownSections(unittest.TestCase):
    def setUp(self):
        self.doc = _load_doc()

    def test_all_required_sections_present(self):
        for section in REQUIRED_MD_SECTIONS:
            self.assertIn(section, self.doc, f"Missing section: {section}")

    def test_decision_matrix_present(self):
        self.assertIn("Readiness Tier Decision Matrix", self.doc)
        self.assertIn("Production SaaS", self.doc)
        self.assertIn("Developer Preview", self.doc)

    def test_risk_register_v5_present(self):
        self.assertIn("Risk Register v5", self.doc)

    def test_compact_roadmap_present(self):
        self.assertIn("Compact Next Roadmap", self.doc)
        self.assertIn("Track", self.doc)

    def test_production_saas_no_go_in_doc(self):
        self.assertIn("NO-GO", self.doc)
        self.assertIn("Production SaaS", self.doc)

    def test_real_customer_data_no_go_in_doc(self):
        self.assertIn("Real Customer Data", self.doc)
        self.assertIn("NO-GO", self.doc)

    def test_private_grant_institutional_data_no_go_in_doc(self):
        self.assertIn("Private Grant", self.doc)
        self.assertIn("Institutional Data", self.doc)
        self.assertIn("NO-GO", self.doc)

    def test_official_sdk_package_no_go_in_doc(self):
        self.assertIn("Official SDK", self.doc)
        self.assertIn("NO-GO", self.doc)

    def test_compliance_certification_no_go_in_doc(self):
        self.assertIn("Compliance", self.doc)
        self.assertIn("NO-GO", self.doc)

    def test_live_postgres_production_readiness_no_go_in_doc(self):
        self.assertIn("Live PostgreSQL Readiness Decision", self.doc)
        self.assertIn("NO-GO", self.doc)

    def test_controlled_external_review_requires_strict_boundaries(self):
        self.assertIn("Controlled External Review", self.doc)
        self.assertIn("strict boundaries", self.doc)

    def test_public_snapshot_requires_separate_gate(self):
        self.assertIn("Public Snapshot", self.doc)
        combined = "separate" in self.doc and "approval" in self.doc
        self.assertTrue(combined, "Public snapshot section must mention separate approval")

    def test_no_forbidden_overclaims_in_doc(self):
        for phrase in FORBIDDEN_OVERCLAIMS:
            self.assertNotIn(phrase, self.doc, f"Forbidden overclaim found: {phrase}")

    def test_no_sensitive_content_in_doc(self):
        for pattern in FORBIDDEN_SENSITIVE_CONTENT:
            self.assertNotIn(pattern, self.doc, f"Sensitive content found: {pattern}")

    def test_required_boundary_text_present(self):
        required_texts = [
            "Developer Preview / Controlled Preview with strict boundaries",
            "Production SaaS remains no-go",
            "Real customer data, private grant data, and institutional data remain no-go",
            "Official SDK/package remains no-go",
            "Compliance certification remains no-go",
            "Ephemeral live PostgreSQL validation passed",
            "production PostgreSQL readiness remains no-go",
            "Security-sensitive reports route to GitHub Security Advisories",
            "No exploit details are included",
            "No real secrets are included",
            "No real customer/private data is used",
            "Unrelated website-design/import files were excluded",
        ]
        for text in required_texts:
            self.assertIn(text, self.doc, f"Missing required text: {text}")


class TestGL217JsonStructure(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()

    def test_all_required_json_keys_present(self):
        for key in REQUIRED_JSON_KEYS:
            self.assertIn(key, self.data, f"Missing JSON key: {key}")

    def test_issue_id_correct(self):
        self.assertEqual(self.data["issue_id"], "GL-217")

    def test_decision_matrix_exists_and_has_tiers(self):
        matrix = self.data.get("readiness_tier_decision_matrix", {})
        self.assertIsInstance(matrix, dict)
        self.assertIn("developer_preview", matrix)
        self.assertIn("production_saas", matrix)
        self.assertIn("official_sdk_package", matrix)
        self.assertIn("real_customer_data", matrix)

    def test_production_saas_decision_is_no_go(self):
        decision = self.data.get("production_saas_decision", {})
        decision_str = json.dumps(decision).lower()
        self.assertTrue(
            any(ind in decision_str for ind in PRODUCTION_SAAS_NO_GO_INDICATORS),
            f"Production SaaS decision must be NO-GO, got: {decision_str[:200]}",
        )

    def test_production_saas_tier_in_matrix_is_no_go(self):
        matrix = self.data.get("readiness_tier_decision_matrix", {})
        prod_saas = matrix.get("production_saas", {})
        decision_str = json.dumps(prod_saas).upper()
        self.assertIn(
            "NO-GO",
            decision_str,
            f"Production SaaS tier must be NO-GO, got: {decision_str[:200]}",
        )

    def test_real_customer_data_decision_is_no_go(self):
        decision = self.data.get("real_customer_data_decision", {})
        decision_str = json.dumps(decision).upper()
        self.assertIn("NO-GO", decision_str)

    def test_private_grant_institutional_data_decision_is_no_go(self):
        decision = self.data.get("private_grant_institutional_data_decision", {})
        decision_str = json.dumps(decision).upper()
        self.assertIn("NO-GO", decision_str)

    def test_official_sdk_package_decision_is_no_go(self):
        decision = self.data.get("official_sdk_package_decision", {})
        decision_str = json.dumps(decision).upper()
        self.assertIn("NO-GO", decision_str)

    def test_official_sdk_package_tier_in_matrix_is_no_go(self):
        matrix = self.data.get("readiness_tier_decision_matrix", {})
        sdk = matrix.get("official_sdk_package", {})
        decision_str = json.dumps(sdk).upper()
        self.assertIn("NO-GO", decision_str)

    def test_compliance_certification_tier_is_no_go(self):
        matrix = self.data.get("readiness_tier_decision_matrix", {})
        compliance = matrix.get("compliance_certification", {})
        decision_str = json.dumps(compliance).upper()
        self.assertIn("NO-GO", decision_str)

    def test_live_postgres_production_readiness_is_no_go(self):
        decision = self.data.get("live_postgres_readiness_decision", {})
        decision_str = json.dumps(decision).upper()
        self.assertIn("NO-GO", decision_str)

    def test_live_postgres_tier_in_matrix_is_no_go(self):
        matrix = self.data.get("readiness_tier_decision_matrix", {})
        pg = matrix.get("live_postgres_production_readiness", {})
        decision_str = json.dumps(pg).upper()
        self.assertIn("NO-GO", decision_str)

    def test_controlled_external_review_requires_strict_boundaries(self):
        decision = self.data.get("controlled_external_review_decision", {})
        decision_str = json.dumps(decision).lower()
        self.assertIn("strict", decision_str)

    def test_public_snapshot_publish_requires_separate_gate(self):
        decision = self.data.get("public_snapshot_public_publish_decision", {})
        decision_str = json.dumps(decision).lower()
        self.assertTrue(
            "separate" in decision_str or "conditional" in decision_str,
            "Public snapshot/publish decision must mention separate gate or conditional",
        )

    def test_risk_register_v5_has_required_fields(self):
        rr = self.data.get("risk_register_v5", [])
        self.assertIsInstance(rr, list)
        self.assertTrue(len(rr) > 0, "risk_register_v5 must not be empty")
        for entry in rr:
            self.assertIn("risk", entry, f"Risk entry missing 'risk': {entry}")
            self.assertIn("severity", entry, f"Risk entry missing 'severity': {entry}")
            self.assertIn("status", entry, f"Risk entry missing 'status': {entry}")
            self.assertIn(
                "mitigation_completed",
                entry,
                f"Risk entry missing 'mitigation_completed': {entry}",
            )
            self.assertIn(
                "remaining_work",
                entry,
                f"Risk entry missing 'remaining_work': {entry}",
            )

    def test_compact_roadmap_exists_and_not_empty(self):
        roadmap = self.data.get("compact_next_roadmap", {})
        self.assertIsInstance(roadmap, dict)
        self.assertTrue(len(roadmap) > 0, "compact_next_roadmap must not be empty")

    def test_input_sources_reviewed_includes_required(self):
        sources = self.data.get("input_sources_reviewed", [])
        for source in REQUIRED_INPUT_SOURCES:
            self.assertIn(
                source,
                sources,
                f"Missing required input source: {source}",
            )

    def test_safety_confirmations_all_true(self):
        sc = self.data.get("safety_confirmations", {})
        required_true = [
            "developer_preview_controlled_preview_with_strict_boundaries",
            "controlled_preview_synthetic_demo_data_only",
            "not_production_saas",
            "real_customer_private_grant_institutional_data_no_go",
            "official_sdk_package_no_go",
            "compliance_certification_no_go",
            "gdpr_soc2_iso_enterprise_readiness_not_claimed",
            "ephemeral_live_postgres_not_production_postgres_readiness",
            "backup_restore_dr_not_overclaimed",
            "observability_incident_not_overclaimed",
            "security_reports_route_to_github_security_advisories",
            "no_exploit_details",
            "no_real_secrets",
            "no_real_customer_private_data",
            "no_public_publish",
            "no_public_snapshot_export",
            "no_package_publishing",
            "no_package_metadata",
            "no_github_workflow_changes",
            "no_snapshot_publish_script_changes",
            "no_backend_src_changes",
            "no_migration_db_schema_dependency_changes",
            "no_public_github_push",
            "no_visibility_change",
            "unrelated_website_design_import_files_excluded",
        ]
        for key in required_true:
            self.assertTrue(sc.get(key), f"safety_confirmation must be True: {key}")

    def test_remaining_blockers_has_p0_p1_p2(self):
        rb = self.data.get("remaining_blockers", {})
        self.assertIn("p0_production_blockers", rb)
        self.assertIn("p1_hardening_blockers", rb)
        self.assertIn("p2_maturity_blockers", rb)
        self.assertTrue(len(rb["p0_production_blockers"]) > 0)

    def test_no_forbidden_overclaims_in_json(self):
        combined = json.dumps(self.data, sort_keys=True).lower()
        forbidden_lower = [phrase.lower() for phrase in FORBIDDEN_OVERCLAIMS]
        for phrase in forbidden_lower:
            self.assertNotIn(
                phrase,
                combined,
                f"Forbidden overclaim found in JSON: {phrase}",
            )

    def test_no_exploit_details_in_json(self):
        combined = json.dumps(self.data)
        for pattern in FORBIDDEN_SENSITIVE_CONTENT:
            self.assertNotIn(pattern, combined)


class TestGL217ForbiddenChanges(unittest.TestCase):
    def test_only_allowed_files_changed(self):
        changed = _branch_changed_files()
        unexpected = changed - ALLOWED_CHANGED_FILES
        self.assertFalse(
            unexpected,
            f"Unexpected files changed in GL-217: {sorted(unexpected)}",
        )

    def test_forbidden_files_not_added_or_changed(self):
        changed = _branch_changed_files()
        for path in changed:
            self.assertNotIn(path, FORBIDDEN_FILES_EXACT, f"Forbidden file changed: {path}")
            self.assertFalse(
                path.startswith(FORBIDDEN_FILE_PREFIXES),
                f"Forbidden path changed: {path}",
            )

    def test_no_backend_src_changes(self):
        changed = _branch_changed_files()
        backend_src = [f for f in changed if f.startswith("backend/src/")]
        self.assertFalse(backend_src, f"backend/src/ changes found: {backend_src}")

    def test_no_migration_db_schema_dependency_changes(self):
        changed = _branch_changed_files()
        forbidden = [
            f
            for f in changed
            if "migration" in f
            or "schema" in f
            or f in {"requirements.txt", "Pipfile", "Pipfile.lock", "poetry.lock"}
        ]
        self.assertFalse(forbidden, f"Migration/DB/schema/dependency changes: {forbidden}")

    def test_no_github_workflow_changes(self):
        changed = _branch_changed_files()
        workflow_changes = [f for f in changed if f.startswith(".github/workflows/")]
        self.assertFalse(workflow_changes, f"GitHub workflow changes: {workflow_changes}")

    def test_no_snapshot_publish_script_changes(self):
        changed = _branch_changed_files()
        snapshot_changes = [
            f
            for f in changed
            if "snapshot" in f.lower() and "script" in f.lower()
            or f.startswith("scripts/public")
            or f.startswith("scripts/snapshot")
        ]
        self.assertFalse(
            snapshot_changes, f"Snapshot publish script changes: {snapshot_changes}"
        )

    def test_no_public_export_directory_changes(self):
        changed = _branch_changed_files()
        public_export = [
            f
            for f in changed
            if f.startswith("public-export/")
            or f.startswith("public_snapshot/")
            or f.startswith("dist/")
        ]
        self.assertFalse(public_export, f"Public export directory changes: {public_export}")

    def test_no_package_metadata_changes(self):
        changed = _branch_changed_files()
        pkg = [f for f in changed if f in FORBIDDEN_FILES_EXACT]
        self.assertFalse(pkg, f"Package metadata changes: {pkg}")

    def test_unrelated_website_design_import_files_excluded(self):
        changed = _branch_changed_files()
        website = [
            f
            for f in changed
            if f.startswith("website-design/")
            or f.startswith("docs/website_design_")
            or f.startswith("docs/website-design-")
        ]
        self.assertFalse(
            website, f"Website-design/import files included: {website}"
        )

    def test_no_frontend_website_design_changes(self):
        changed = _branch_changed_files()
        frontend = [
            f
            for f in changed
            if f.startswith("website/")
            or f.startswith("frontend/")
            or f.startswith("website-design/")
        ]
        self.assertFalse(frontend, f"Frontend/website/design changes: {frontend}")

    def test_no_public_publish_or_visibility_behavior_in_gl217_files(self):
        combined = _load_doc() + json.dumps(_load_json(), sort_keys=True)
        for phrase in FORBIDDEN_PUBLISH_PHRASES:
            self.assertNotIn(phrase, combined, f"Forbidden phrase in GL-217: {phrase}")

    def test_no_production_deployment_config_in_changed_files(self):
        changed = _branch_changed_files()
        deployment_paths = [
            f
            for f in changed
            if f.startswith("deploy/")
            or f.startswith("terraform/")
            or f.startswith("kubernetes/")
            or f.startswith("helm/")
            or f.startswith("cloud/")
        ]
        self.assertFalse(deployment_paths, f"Deployment config changes: {deployment_paths}")


if __name__ == "__main__":
    unittest.main()
