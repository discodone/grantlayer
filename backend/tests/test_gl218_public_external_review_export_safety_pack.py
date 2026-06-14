"""Tests for GL-218 Public / External Review Export Safety Pack."""

from __future__ import annotations

import json
import os
import py_compile
import subprocess
import sys
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "public_external_review_export_safety_pack.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl218",
    "public_external_review_export_safety_pack.json",
)
SCAN_SCRIPT_PATH = os.path.join(
    REPO_ROOT, "scripts", "ops", "gl218_public_export_safety_scan.py"
)
EXPECTED_BRANCH = "gl-218-public-external-review-export-safety-pack"

REQUIRED_MD_SECTIONS = [
    "## Context",
    "## Scope",
    "## Non-Goals",
    "## Input Sources Reviewed",
    "## Current Public / External Review Posture",
    "## Export Candidate Safety Assessment",
    "## Eligible Public / External Review Materials",
    "## Excluded Materials",
    "## Allowed Public Claims",
    "## Prohibited Public Claims",
    "## No-Real-Data Safety Assessment",
    "## No-Secret Safety Assessment",
    "## Internal Infrastructure Leakage Assessment",
    "## Package / Publish Metadata Assessment",
    "## Public Snapshot / Export Boundary",
    "## Public Website Publish Boundary",
    "## Controlled External Review Boundary",
    "## Synthetic / Demo Data Only Boundary",
    "## Official SDK / Package Boundary",
    "## Production SaaS Boundary",
    "## Compliance Certification Boundary",
    "## Live PostgreSQL Production Readiness Boundary",
    "## Optional Scan Helper Summary",
    "## Production Readiness Impact",
    "## Controlled Preview Impact",
    "## Remaining Blockers",
    "## Risk Register",
    "## Decision",
    "## Decision Rationale",
    "## Safety Confirmations",
    "## Recommended Next Issues",
]

REQUIRED_JSON_KEYS = [
    "issue_id",
    "title",
    "result",
    "decision",
    "decision_rationale",
    "input_sources_reviewed",
    "current_public_external_review_posture",
    "export_candidate_safety_assessment",
    "eligible_public_external_review_materials",
    "excluded_materials",
    "allowed_public_claims",
    "prohibited_public_claims",
    "no_real_data_safety_assessment",
    "no_secret_safety_assessment",
    "internal_infrastructure_leakage_assessment",
    "package_publish_metadata_assessment",
    "public_snapshot_export_boundary",
    "public_website_publish_boundary",
    "controlled_external_review_boundary",
    "synthetic_demo_data_only_boundary",
    "official_sdk_package_boundary",
    "production_saas_boundary",
    "compliance_certification_boundary",
    "live_postgres_production_readiness_boundary",
    "optional_scan_helper_summary",
    "production_readiness_impact",
    "controlled_preview_impact",
    "remaining_blockers",
    "risk_register",
    "findings",
    "safety_confirmations",
    "recommended_next_issues",
]

REQUIRED_INPUT_SOURCES = [
    "docs/production_go_no_go_v5.md",
    "docs/examples/gl217/production_go_no_go_v5.json",
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
    "docs/claim_safety_controlled_preview_boundary.md",
    "docs/examples/gl207/claim_safety_controlled_preview_boundary.json",
    "README.md",
    "SECURITY.md",
    "AGENTS.md",
]

ALLOWED_CHANGED_FILES = {
    "docs/public_external_review_export_safety_pack.md",
    "docs/examples/gl218/public_external_review_export_safety_pack.json",
    "backend/tests/test_gl218_public_external_review_export_safety_pack.py",
    "scripts/ops/gl218_public_export_safety_scan.py",
}

FORBIDDEN_FILES_EXACT = {
    "setup.py",
    "package.json",
    "package-lock.json",
    "pyproject.toml",
    "sdk/pyproject.toml",
}

FORBIDDEN_FILE_PREFIXES = (
    ".github/workflows/",
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
]

FORBIDDEN_SENSITIVE_CONTENT = [
    "Bearer eyJ",
    "BEGIN PRIVATE KEY",
    "postgres://user:",
    "postgresql://user:",
]

FORBIDDEN_PUBLISH_PHRASES = [
    "git push public",
    "gh repo edit",
    "visibility public",
    "public publish script",
    "package publishing enabled",
    "production SaaS is ready",
    "production PostgreSQL ready",
]

REQUIRED_SAFETY_CONFIRMATION_KEYS = [
    "gl218_does_not_create_public_export",
    "gl218_does_not_push_to_public_github",
    "gl218_does_not_change_visibility",
    "production_saas_is_no_go",
    "real_customer_private_grant_institutional_data_is_no_go",
    "official_sdk_package_is_no_go",
    "compliance_certification_is_no_go",
    "live_postgres_production_readiness_is_no_go",
    "controlled_external_review_requires_strict_boundaries_and_synthetic_demo_data",
    "public_snapshot_export_requires_later_explicit_gate_and_approval",
    "no_exploit_details_included",
    "no_real_secrets_included",
    "no_real_customer_private_data_included",
    "no_backend_src_changes",
    "no_github_workflow_changes",
    "unrelated_website_design_import_files_excluded",
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
    return {f for f in lines if not any(f.startswith(p) for p in excluded_prefixes)}


def _load_doc() -> str:
    with open(DOC_PATH, encoding="utf-8") as f:
        return f.read()


def _load_json() -> dict:
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestGL218FilesExist(unittest.TestCase):
    def test_markdown_file_exists(self):
        self.assertTrue(os.path.isfile(DOC_PATH), f"Missing: {DOC_PATH}")

    def test_json_file_exists(self):
        self.assertTrue(os.path.isfile(JSON_PATH), f"Missing: {JSON_PATH}")

    def test_json_is_valid(self):
        data = _load_json()
        self.assertIsInstance(data, dict)

    def test_issue_id_is_gl218(self):
        data = _load_json()
        self.assertEqual(data.get("issue_id"), "GL-218")

    def test_this_file_compiles(self):
        py_compile.compile(__file__, doraise=True)

    def test_scan_script_exists(self):
        self.assertTrue(
            os.path.isfile(SCAN_SCRIPT_PATH), f"Missing: {SCAN_SCRIPT_PATH}"
        )

    def test_scan_script_compiles(self):
        py_compile.compile(SCAN_SCRIPT_PATH, doraise=True)


class TestGL218MarkdownSections(unittest.TestCase):
    def setUp(self):
        self.doc = _load_doc()

    def test_all_required_sections_present(self):
        for section in REQUIRED_MD_SECTIONS:
            self.assertIn(section, self.doc, f"Missing section: {section}")

    def test_current_public_external_review_posture_exists(self):
        self.assertIn("Current Public / External Review Posture", self.doc)

    def test_export_candidate_safety_assessment_exists(self):
        self.assertIn("Export Candidate Safety Assessment", self.doc)

    def test_eligible_materials_exist(self):
        self.assertIn("Eligible Public / External Review Materials", self.doc)
        self.assertIn("README.md", self.doc)

    def test_excluded_materials_exist(self):
        self.assertIn("Excluded Materials", self.doc)
        self.assertIn("website-design/", self.doc)

    def test_allowed_public_claims_exist(self):
        self.assertIn("Allowed Public Claims", self.doc)
        self.assertIn("Developer Preview", self.doc)

    def test_prohibited_public_claims_exist(self):
        self.assertIn("Prohibited Public Claims", self.doc)
        self.assertIn("Production SaaS ready", self.doc)

    def test_no_real_data_safety_assessment_exists(self):
        self.assertIn("No-Real-Data Safety Assessment", self.doc)

    def test_no_secret_safety_assessment_exists(self):
        self.assertIn("No-Secret Safety Assessment", self.doc)

    def test_internal_infrastructure_leakage_assessment_exists(self):
        self.assertIn("Internal Infrastructure Leakage Assessment", self.doc)

    def test_package_publish_metadata_assessment_exists(self):
        self.assertIn("Package / Publish Metadata Assessment", self.doc)

    def test_public_snapshot_export_boundary_exists(self):
        self.assertIn("Public Snapshot / Export Boundary", self.doc)

    def test_public_website_publish_boundary_exists(self):
        self.assertIn("Public Website Publish Boundary", self.doc)

    def test_controlled_external_review_boundary_exists(self):
        self.assertIn("Controlled External Review Boundary", self.doc)

    def test_synthetic_demo_data_only_boundary_exists(self):
        self.assertIn("Synthetic / Demo Data Only Boundary", self.doc)

    def test_official_sdk_package_boundary_exists(self):
        self.assertIn("Official SDK / Package Boundary", self.doc)

    def test_production_saas_boundary_exists(self):
        self.assertIn("Production SaaS Boundary", self.doc)

    def test_compliance_certification_boundary_exists(self):
        self.assertIn("Compliance Certification Boundary", self.doc)

    def test_live_postgres_production_readiness_boundary_exists(self):
        self.assertIn("Live PostgreSQL Production Readiness Boundary", self.doc)

    def test_production_readiness_impact_exists(self):
        self.assertIn("Production Readiness Impact", self.doc)

    def test_controlled_preview_impact_exists(self):
        self.assertIn("Controlled Preview Impact", self.doc)

    def test_remaining_blockers_exist(self):
        self.assertIn("Remaining Blockers", self.doc)
        self.assertIn("PB-001", self.doc)

    def test_risk_register_exists(self):
        self.assertIn("Risk Register", self.doc)
        self.assertIn("RR-001", self.doc)

    def test_safety_confirmations_exist(self):
        self.assertIn("Safety Confirmations", self.doc)

    def test_recommended_next_issues_exist(self):
        self.assertIn("Recommended Next Issues", self.doc)
        self.assertIn("GL-219", self.doc)

    def test_doc_states_no_public_export_created(self):
        self.assertIn(
            "GL-218 is a safety pack, not a public export or publish", self.doc
        )
        self.assertIn(
            "No public\nsnapshot or export directory is created by GL-218", self.doc
        )

    def test_doc_states_no_public_github_push(self):
        self.assertIn("No public GitHub push is performed by GL-218", self.doc)

    def test_doc_states_no_public_publish(self):
        self.assertIn("not a public export or publish", self.doc)

    def test_doc_states_no_visibility_change(self):
        self.assertIn(
            "No repository visibility change is performed by GL-218", self.doc
        )

    def test_doc_states_production_saas_no_go(self):
        self.assertIn("Production SaaS remains NO-GO", self.doc)

    def test_doc_states_real_data_no_go(self):
        self.assertIn("Real\ncustomer/private grant/institutional data remains NO-GO", self.doc)

    def test_doc_states_official_sdk_no_go(self):
        self.assertIn("Official SDK/package\nremains NO-GO", self.doc)

    def test_doc_states_compliance_no_go(self):
        self.assertIn("Compliance certification remains NO-GO", self.doc)

    def test_doc_states_live_postgres_no_go(self):
        self.assertIn("Live PostgreSQL\nproduction readiness remains NO-GO", self.doc)

    def test_doc_states_external_review_strict_boundaries(self):
        self.assertIn("strict boundaries", self.doc)
        self.assertIn("Controlled external technical review", self.doc)

    def test_doc_states_synthetic_demo_data_only(self):
        self.assertIn("synthetic/demo-data only", self.doc)

    def test_doc_states_public_snapshot_requires_approval(self):
        self.assertIn("separate explicit gate", self.doc)
        self.assertIn("explicit gate and approval", self.doc)

    def test_doc_excludes_no_exploit_details(self):
        self.assertIn("No exploit\ndetails are included", self.doc)

    def test_doc_excludes_no_real_secrets(self):
        self.assertIn("No real secrets are included", self.doc)

    def test_doc_excludes_no_real_customer_private_data(self):
        self.assertIn("No real customer/private\ndata is included", self.doc)

    def test_no_forbidden_overclaims_in_doc(self):
        for phrase in FORBIDDEN_OVERCLAIMS:
            self.assertNotIn(phrase, self.doc, f"Forbidden overclaim found: {phrase}")

    def test_no_sensitive_content_in_doc(self):
        for pattern in FORBIDDEN_SENSITIVE_CONTENT:
            self.assertNotIn(pattern, self.doc, f"Sensitive content found: {pattern}")

    def test_unrelated_website_design_import_files_excluded_mentioned(self):
        self.assertIn("website-design/import files", self.doc)
        self.assertIn("excluded from GL-218", self.doc)

    def test_security_advisories_routing_mentioned(self):
        self.assertIn("GitHub Security Advisories", self.doc)


class TestGL218JsonStructure(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()

    def test_all_required_json_keys_present(self):
        for key in REQUIRED_JSON_KEYS:
            self.assertIn(key, self.data, f"Missing JSON key: {key}")

    def test_issue_id_correct(self):
        self.assertEqual(self.data["issue_id"], "GL-218")

    def test_result_is_allowed_value(self):
        allowed = {"safety_pack_complete", "approved_with_blockers", "ready_for_merge"}
        self.assertIn(self.data.get("result"), allowed)

    def test_decision_is_allowed_value(self):
        allowed = {
            "ready_for_merge",
            "safety_pack_complete",
            "approved_with_cautions",
        }
        self.assertIn(self.data.get("decision"), allowed)

    def test_input_sources_reviewed_contains_required(self):
        reviewed = self.data.get("input_sources_reviewed", [])
        for source in REQUIRED_INPUT_SOURCES:
            self.assertIn(source, reviewed, f"Missing input source: {source}")

    def test_current_posture_exists(self):
        posture = self.data.get("current_public_external_review_posture", {})
        self.assertIsInstance(posture, dict)
        self.assertIn("posture", posture)

    def test_export_candidate_safety_assessment_exists(self):
        assessment = self.data.get("export_candidate_safety_assessment", {})
        self.assertIsInstance(assessment, dict)
        self.assertFalse(
            assessment.get("export_candidate_created_by_gl218", True),
            "export_candidate_created_by_gl218 must be false",
        )

    def test_eligible_materials_is_non_empty_list(self):
        materials = self.data.get("eligible_public_external_review_materials", [])
        self.assertIsInstance(materials, list)
        self.assertGreater(len(materials), 0)

    def test_excluded_materials_exists(self):
        excluded = self.data.get("excluded_materials", {})
        self.assertIsInstance(excluded, dict)
        self.assertIn("secrets_and_credentials", excluded)
        self.assertIn("real_data", excluded)
        self.assertIn("internal_infrastructure", excluded)
        self.assertIn("forbidden_files_and_paths", excluded)

    def test_allowed_public_claims_non_empty(self):
        claims = self.data.get("allowed_public_claims", [])
        self.assertIsInstance(claims, list)
        self.assertGreater(len(claims), 0)

    def test_prohibited_public_claims_non_empty(self):
        claims = self.data.get("prohibited_public_claims", [])
        self.assertIsInstance(claims, list)
        self.assertGreater(len(claims), 0)

    def test_no_real_data_assessment_all_true(self):
        assessment = self.data.get("no_real_data_safety_assessment", {})
        self.assertTrue(assessment.get("all_examples_use_synthetic_identifiers"))
        self.assertTrue(assessment.get("no_real_customer_data_in_tracked_files"))
        self.assertTrue(assessment.get("no_real_private_grant_institutional_data_in_tracked_files"))

    def test_no_secret_assessment_all_true(self):
        assessment = self.data.get("no_secret_safety_assessment", {})
        self.assertTrue(assessment.get("no_raw_dsns_with_real_credentials"))
        self.assertTrue(assessment.get("no_raw_tokens_auth_headers_bearer_tokens"))
        self.assertTrue(assessment.get("no_pem_private_key_blocks"))

    def test_internal_infra_assessment_exists(self):
        assessment = self.data.get("internal_infrastructure_leakage_assessment", {})
        self.assertIsInstance(assessment, dict)
        self.assertTrue(assessment.get("no_internal_forgejo_urls_in_export_files"))

    def test_package_publish_metadata_assessment_all_true(self):
        assessment = self.data.get("package_publish_metadata_assessment", {})
        self.assertTrue(assessment.get("no_setup_py"))
        self.assertTrue(assessment.get("no_sdk_pyproject_toml"))
        self.assertTrue(assessment.get("no_package_json_or_lock"))
        self.assertTrue(assessment.get("no_github_workflow_changes_in_gl218"))

    def test_public_snapshot_export_boundary_no_export_created(self):
        boundary = self.data.get("public_snapshot_export_boundary", {})
        self.assertFalse(
            boundary.get("public_snapshot_created_by_gl218", True),
            "public_snapshot_created_by_gl218 must be false",
        )

    def test_public_website_publish_boundary_no_go(self):
        boundary = self.data.get("public_website_publish_boundary", {})
        self.assertEqual(boundary.get("public_website_publish_decision"), "DEFER / NO-GO")

    def test_controlled_external_review_boundary_strict(self):
        boundary = self.data.get("controlled_external_review_boundary", {})
        self.assertTrue(boundary.get("synthetic_demo_data_only"))
        self.assertTrue(boundary.get("no_real_customer_data"))

    def test_synthetic_demo_only_boundary_exists(self):
        boundary = self.data.get("synthetic_demo_data_only_boundary", {})
        self.assertIsInstance(boundary, dict)
        self.assertTrue(boundary.get("synthetic_identifiers_only"))

    def test_official_sdk_boundary_no_go(self):
        boundary = self.data.get("official_sdk_package_boundary", {})
        self.assertEqual(boundary.get("decision"), "NO-GO")
        self.assertTrue(boundary.get("not_an_official_sdk"))

    def test_production_saas_boundary_no_go(self):
        boundary = self.data.get("production_saas_boundary", {})
        self.assertEqual(boundary.get("decision"), "NO-GO")

    def test_compliance_certification_boundary_no_go(self):
        boundary = self.data.get("compliance_certification_boundary", {})
        self.assertEqual(boundary.get("decision"), "NO-GO")

    def test_live_postgres_boundary_no_go(self):
        boundary = self.data.get("live_postgres_production_readiness_boundary", {})
        self.assertEqual(boundary.get("decision"), "NO-GO")
        self.assertTrue(boundary.get("ephemeral_validation_passed_gl206b"))
        self.assertTrue(boundary.get("production_postgresql_not_claimed"))

    def test_production_readiness_impact_is_none(self):
        impact = self.data.get("production_readiness_impact", {})
        self.assertFalse(impact.get("backend_src_changes", True))
        self.assertFalse(impact.get("migration_schema_dependency_changes", True))
        self.assertFalse(impact.get("new_production_controls_added", True))

    def test_controlled_preview_impact_exists(self):
        impact = self.data.get("controlled_preview_impact", {})
        self.assertIsInstance(impact, dict)

    def test_remaining_blockers_is_non_empty_list(self):
        blockers = self.data.get("remaining_blockers", [])
        self.assertIsInstance(blockers, list)
        self.assertGreater(len(blockers), 0)

    def test_risk_register_is_non_empty_list(self):
        risks = self.data.get("risk_register", [])
        self.assertIsInstance(risks, list)
        self.assertGreater(len(risks), 0)

    def test_findings_is_non_empty_list(self):
        findings = self.data.get("findings", [])
        self.assertIsInstance(findings, list)
        self.assertGreater(len(findings), 0)

    def test_safety_confirmations_all_true(self):
        confirmations = self.data.get("safety_confirmations", {})
        for key in REQUIRED_SAFETY_CONFIRMATION_KEYS:
            self.assertTrue(
                confirmations.get(key),
                f"Safety confirmation not True: {key}",
            )

    def test_recommended_next_issues_non_empty(self):
        next_issues = self.data.get("recommended_next_issues", [])
        self.assertIsInstance(next_issues, list)
        self.assertGreater(len(next_issues), 0)

    def test_no_forbidden_overclaims_in_json(self):
        dumped = json.dumps(self.data, sort_keys=True)
        for phrase in FORBIDDEN_OVERCLAIMS:
            self.assertNotIn(phrase, dumped, f"Forbidden overclaim in JSON: {phrase}")

    def test_no_sensitive_content_in_json(self):
        dumped = json.dumps(self.data, sort_keys=True)
        for pattern in FORBIDDEN_SENSITIVE_CONTENT:
            self.assertNotIn(pattern, dumped, f"Sensitive content in JSON: {pattern}")

    def test_optional_scan_helper_summary_added(self):
        summary = self.data.get("optional_scan_helper_summary", {})
        self.assertTrue(summary.get("added"), "Scan helper must be marked as added")
        self.assertTrue(summary.get("local_only"))
        self.assertTrue(summary.get("dry_run_scan_only_by_default"))
        self.assertTrue(summary.get("does_not_create_public_export_directory"))
        self.assertTrue(summary.get("does_not_push_anywhere"))
        self.assertTrue(summary.get("does_not_contact_external_services"))
        self.assertTrue(summary.get("does_not_require_credentials"))
        self.assertTrue(summary.get("supports_dry_run"))
        self.assertTrue(summary.get("supports_plan"))
        self.assertTrue(summary.get("states_not_complete_security_audit"))
        self.assertTrue(summary.get("states_not_approval_to_publish"))


class TestGL218ScanScript(unittest.TestCase):
    def test_scan_script_compiles(self):
        py_compile.compile(SCAN_SCRIPT_PATH, doraise=True)

    def test_scan_script_supports_plan(self):
        result = subprocess.run(
            [sys.executable, SCAN_SCRIPT_PATH, "--plan"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, f"--plan failed: {result.stderr}")
        self.assertIn("PLAN MODE", result.stdout)

    def test_scan_script_supports_dry_run(self):
        result = subprocess.run(
            [sys.executable, SCAN_SCRIPT_PATH, "--dry-run"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertIn(result.returncode, {0, 1}, "dry-run must exit 0 or 1")
        self.assertIn("SCAN", result.stdout.upper())

    def test_scan_script_states_not_approval_to_publish(self):
        result = subprocess.run(
            [sys.executable, SCAN_SCRIPT_PATH, "--dry-run"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        combined = result.stdout + result.stderr
        self.assertIn("NOT approval to publish", combined)

    def test_scan_script_states_not_complete_security_audit(self):
        result = subprocess.run(
            [sys.executable, SCAN_SCRIPT_PATH, "--dry-run"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        combined = result.stdout + result.stderr
        self.assertIn("NOT a complete security audit", combined)

    def test_scan_script_does_not_create_export_directory(self):
        forbidden_dirs = [
            os.path.join(REPO_ROOT, "public-export"),
            os.path.join(REPO_ROOT, "public_snapshot"),
            os.path.join(REPO_ROOT, "dist"),
        ]
        subprocess.run(
            [sys.executable, SCAN_SCRIPT_PATH, "--dry-run"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        for d in forbidden_dirs:
            self.assertFalse(
                os.path.isdir(d), f"Script must not create directory: {d}"
            )

    def test_scan_script_redacts_secret_values(self):
        result = subprocess.run(
            [sys.executable, SCAN_SCRIPT_PATH, "--dry-run"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        combined = result.stdout + result.stderr
        self.assertNotIn("BEGIN PRIVATE KEY", combined)
        self.assertNotIn("Bearer eyJ", combined)


class TestGL218ScopeGuards(unittest.TestCase):
    def setUp(self):
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()
        if branch != EXPECTED_BRANCH:
            self.skipTest(
                f"Scope guard skipped: not on {EXPECTED_BRANCH} (current: {branch})"
            )

    def test_only_allowed_files_changed(self):
        changed = _branch_changed_files()
        unexpected = changed - ALLOWED_CHANGED_FILES
        self.assertFalse(
            unexpected,
            f"Unexpected files changed in GL-218 branch: {unexpected}",
        )

    def test_forbidden_files_not_added_or_changed(self):
        changed = _branch_changed_files()
        for path in changed:
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
            if ("snapshot" in f.lower() and "script" in f.lower())
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
        self.assertFalse(website, f"Website-design/import files included: {website}")

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

    def test_no_public_export_directory_exists(self):
        for d in ["public-export", "public_snapshot"]:
            self.assertFalse(
                os.path.isdir(os.path.join(REPO_ROOT, d)),
                f"Forbidden directory exists: {d}",
            )

    def test_no_public_snapshot_worktree_created(self):
        result = subprocess.run(
            ["git", "worktree", "list"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        for line in result.stdout.splitlines():
            # Extract the worktree path (first field) — the branch name column may contain
            # "public" legitimately (e.g. "gl-218-public-..."); we only flag paths that
            # look like actual public-snapshot export directories.
            path_field = line.split()[0] if line.strip() else ""
            path_lower = path_field.lower()
            self.assertFalse(
                "public_snapshot" in path_lower or "public-snapshot" in path_lower,
                f"Public snapshot worktree found: {line}",
            )
            self.assertFalse(
                "public-export" in path_lower or "public_export" in path_lower,
                f"Public export worktree found: {line}",
            )

    def test_no_setup_py_added(self):
        self.assertFalse(
            os.path.isfile(os.path.join(REPO_ROOT, "setup.py")),
            "setup.py must not exist",
        )

    def test_no_sdk_pyproject_toml_added(self):
        self.assertFalse(
            os.path.isfile(os.path.join(REPO_ROOT, "sdk", "pyproject.toml")),
            "sdk/pyproject.toml must not exist",
        )

    def test_no_package_json_added(self):
        self.assertFalse(
            os.path.isfile(os.path.join(REPO_ROOT, "package.json")),
            "package.json must not exist",
        )

    def test_no_package_lock_json_added(self):
        self.assertFalse(
            os.path.isfile(os.path.join(REPO_ROOT, "package-lock.json")),
            "package-lock.json must not exist",
        )

    def test_no_production_deployment_config_added(self):
        for d in ["deploy", "terraform", "kubernetes", "helm", "cloud"]:
            self.assertFalse(
                os.path.isdir(os.path.join(REPO_ROOT, d)),
                f"Deployment config directory must not exist: {d}",
            )

    def test_no_public_publish_or_visibility_behavior_in_gl218_files(self):
        combined = _load_doc() + json.dumps(_load_json(), sort_keys=True)
        for phrase in FORBIDDEN_PUBLISH_PHRASES:
            self.assertNotIn(phrase, combined, f"Forbidden phrase in GL-218: {phrase}")


if __name__ == "__main__":
    unittest.main()
