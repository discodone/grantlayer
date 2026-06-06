"""GL-212 public / external review readiness gate pack tests."""

from __future__ import annotations

import json
import os
import re
import subprocess
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "public_external_review_readiness_gate_pack.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl212",
    "public_external_review_readiness_gate_pack.json",
)
CHECKLIST_PATH = os.path.join(REPO_ROOT, "docs", "public_snapshot_external_review_checklist.md")

ALLOWED_RESULTS = {
    "ready_for_merge",
    "blocked_public_snapshot_gate",
    "blocked_external_review_gate",
}
ALLOWED_DECISIONS = {
    "public_external_review_gate_approved_with_cautions",
    "public_external_review_gate_deferred",
    "public_external_review_gate_blocked",
}
ALLOWED_PUBLIC_SNAPSHOT_DECISIONS = {
    "public_snapshot_gate_blocked",
    "public_snapshot_gate_defer",
    "public_snapshot_gate_proceed_with_cautions",
}
ALLOWED_EXTERNAL_REVIEW_DECISIONS = {
    "external_review_blocked",
    "external_review_defer",
    "external_review_allowed_with_strict_boundaries",
}
ALLOWED_CHANGED_FILES = {
    "backend/tests/test_gl212_public_external_review_readiness_gate_pack.py",
    "docs/public_external_review_readiness_gate_pack.md",
    "docs/examples/gl212/public_external_review_readiness_gate_pack.json",
    "docs/public_snapshot_external_review_checklist.md",
}
PREEXISTING_UNTRACKED_EXCLUSIONS = {
    "docs/website_design_workspace_import_report.md",
    "docs/website_design_workspace_import_dirty_stop.md",
    "docs/website_design_workspace_import_report_dirty_stop.md",
    "docs/website-design-workspace-import-report.md",
    "docs/website-design-workspace-import-report-dirty-stop.md",
    "website-design/README.md",
    "website-design/IMPORT_CHECKLIST.md",
}


def _path(relpath: str) -> str:
    return os.path.join(REPO_ROOT, relpath)


def _read(relpath: str) -> str:
    with open(_path(relpath), encoding="utf-8") as f:
        return f.read()


def _load_doc() -> str:
    with open(DOC_PATH, encoding="utf-8") as f:
        return f.read()


def _load_json() -> dict:
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _git_lines(args: list[str]) -> set[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _branch_diff_files() -> set[str]:
    files = set()
    files.update(_git_lines(["diff", "--name-only", "main...HEAD"]))
    files.update(_git_lines(["diff", "--name-only", "--cached"]))
    files.update(_git_lines(["diff", "--name-only"]))
    files.update(_git_lines(["ls-files", "--others", "--exclude-standard"]))
    return {
        path
        for path in files
        if path not in PREEXISTING_UNTRACKED_EXCLUSIONS
        and not path.startswith("website-design/")
    }


def _combined_gl212_text() -> str:
    paths = [
        "docs/public_external_review_readiness_gate_pack.md",
        "docs/examples/gl212/public_external_review_readiness_gate_pack.json",
        "docs/public_snapshot_external_review_checklist.md",
    ]
    return "\n".join(_read(path) for path in paths if os.path.exists(_path(path)))


class TestGL212Artifacts(unittest.TestCase):
    def test_docs_file_exists(self):
        self.assertTrue(os.path.isfile(DOC_PATH))

    def test_json_artifact_exists_and_valid(self):
        self.assertTrue(os.path.isfile(JSON_PATH))
        self.assertIsInstance(_load_json(), dict)

    def test_issue_id_result_and_decision(self):
        data = _load_json()
        self.assertEqual(data.get("issue_id"), "GL-212")
        self.assertIn(data.get("result"), ALLOWED_RESULTS)
        self.assertIn(data.get("decision"), ALLOWED_DECISIONS)

    def test_required_json_sections_present(self):
        required = [
            "decision_rationale",
            "input_sources_reviewed",
            "current_state_summary",
            "public_snapshot_readiness_gate",
            "public_snapshot_decision",
            "external_review_readiness_gate",
            "external_review_decision",
            "export_safety_scan_checklist",
            "controlled_preview_handoff_boundary",
            "claim_safety_review",
            "allowed_claims",
            "prohibited_claims",
            "public_facing_file_assessment",
            "website_baseline_assessment",
            "sdk_package_boundary_assessment",
            "live_postgres_claim_boundary_assessment",
            "data_privacy_secret_safety_assessment",
            "production_readiness_impact",
            "remaining_blockers",
            "risk_register",
            "findings",
            "safety_confirmations",
            "recommended_next_issues",
        ]
        data = _load_json()
        for key in required:
            self.assertIn(key, data)
            self.assertTrue(data[key], key)

    def test_input_sources_reviewed_exist(self):
        missing = []
        for source in _load_json()["input_sources_reviewed"]:
            rel = source.rstrip("/")
            if not os.path.exists(_path(rel)):
                missing.append(source)
        self.assertEqual(missing, [])

    def test_optional_checklist_exists_and_is_internal_only(self):
        self.assertTrue(os.path.isfile(CHECKLIST_PATH))
        checklist = _read("docs/public_snapshot_external_review_checklist.md")
        self.assertIn("Internal-only dry-run checklist", checklist)
        self.assertIn("does not publish anything", checklist)


class TestGL212GateDecisions(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()

    def test_current_state_summary_exists(self):
        summary = self.data["current_state_summary"]
        self.assertEqual(summary["posture"], "Developer Preview / Controlled Preview with strict boundaries")
        self.assertEqual(summary["production_saas"], "NO-GO")
        self.assertEqual(summary["official_sdk_package"], "NO-GO")

    def test_public_snapshot_gate_and_decision(self):
        gate = self.data["public_snapshot_readiness_gate"]
        decision = self.data["public_snapshot_decision"]
        self.assertTrue(gate["completed"])
        self.assertIn(gate["decision"], ALLOWED_PUBLIC_SNAPSHOT_DECISIONS)
        self.assertIn(decision["decision"], ALLOWED_PUBLIC_SNAPSHOT_DECISIONS)
        self.assertFalse(gate["public_snapshot_created_in_gl212"])
        self.assertFalse(gate["public_github_push_in_gl212"])
        self.assertFalse(gate["visibility_change_in_gl212"])

    def test_external_review_gate_and_decision(self):
        gate = self.data["external_review_readiness_gate"]
        decision = self.data["external_review_decision"]
        self.assertTrue(gate["completed"])
        self.assertIn(gate["decision"], ALLOWED_EXTERNAL_REVIEW_DECISIONS)
        self.assertIn(decision["decision"], ALLOWED_EXTERNAL_REVIEW_DECISIONS)
        self.assertTrue(gate["synthetic_demo_data_only"])
        self.assertEqual(gate["security_sensitive_reports_route"], "GitHub Security Advisories")

    def test_export_safety_scan_checklist_exists(self):
        checklist = self.data["export_safety_scan_checklist"]
        for key in [
            "file_inclusion_exclusion_rules",
            "forbidden_files",
            "forbidden_content_patterns",
            "secret_scanning_required",
            "real_data_scanning_required",
            "claim_scanning_required",
            "package_metadata_scanning_required",
            "workflow_snapshot_publish_scanning_required",
            "website_static_asset_scanning_required",
            "internal_only_path_reference_scanning_required",
            "raw_dsn_token_private_key_password_auth_header_scanning_required",
            "paperclip_internal_host_private_operational_leakage_scanning_required",
        ]:
            self.assertTrue(checklist[key], key)
        self.assertFalse(checklist["public_export_created"])

    def test_controlled_preview_handoff_boundary_exists(self):
        boundary = self.data["controlled_preview_handoff_boundary"]
        self.assertEqual(boundary["controlled_external_review"], "allowed_with_strict_boundaries")
        self.assertEqual(boundary["real_data_pilot"], "NO-GO")
        self.assertEqual(boundary["production_pilot"], "NO-GO")
        self.assertEqual(boundary["official_sdk_package"], "NO-GO")

    def test_claim_safety_review_allowed_and_prohibited_claims(self):
        self.assertTrue(self.data["claim_safety_review"]["completed"])
        allowed = " ".join(self.data["allowed_claims"])
        prohibited = " ".join(self.data["prohibited_claims"])
        self.assertIn("Developer Preview", allowed)
        self.assertIn("Controlled Preview with strict boundaries", allowed)
        self.assertIn("ephemeral live PostgreSQL validation passed", allowed)
        self.assertIn("Production SaaS ready", prohibited)
        self.assertIn("official SDK/package available", prohibited)
        self.assertIn("production PostgreSQL ready", prohibited)

    def test_assessments_exist(self):
        self.assertTrue(self.data["public_facing_file_assessment"]["completed"])
        self.assertTrue(self.data["website_baseline_assessment"]["static_website_baseline_exists"])
        self.assertTrue(self.data["website_baseline_assessment"]["unrelated_website_design_import_files_excluded"])
        self.assertFalse(self.data["sdk_package_boundary_assessment"]["official_sdk_package_claimed"])
        self.assertFalse(self.data["live_postgres_claim_boundary_assessment"]["production_postgres_readiness_claimed"])
        self.assertTrue(self.data["data_privacy_secret_safety_assessment"]["no_real_secrets"])
        self.assertTrue(self.data["production_readiness_impact"]["gl213_should_proceed_next"])


class TestGL212SafetyWording(unittest.TestCase):
    def setUp(self):
        self.doc = _load_doc()
        self.data = _load_json()
        self.combined = _combined_gl212_text()
        self.combined_lower = self.combined.lower()

    def test_required_boundary_phrases(self):
        required = [
            "GL-212 is a gate/readiness pack, not a public publish",
            "No public GitHub push occurs",
            "No public snapshot is created",
            "No repository visibility change occurs",
            "Developer Preview / Controlled Preview with strict boundaries",
            "Production SaaS remains no-go",
            "Real customer data, private grant data, and institutional data remain no-go",
            "official SDK/package",
            "Compliance certification remains no-go",
            "Ephemeral live PostgreSQL validation passed, but production PostgreSQL readiness remains no-go",
            "Security-sensitive reports route to GitHub Security Advisories",
            "No exploit details are included",
            "No real secrets are included",
            "No real customer/private data is used",
        ]
        for phrase in required:
            self.assertIn(phrase, self.doc)

    def test_safety_confirmations(self):
        confirmations = self.data["safety_confirmations"]
        for key in [
            "gl212_gate_pack_not_public_publish",
            "no_public_github_push",
            "no_public_publish",
            "no_public_snapshot_created",
            "no_public_export_directory_created",
            "no_visibility_change",
            "developer_preview_controlled_preview_with_strict_boundaries",
            "production_saas_no_go",
            "real_customer_private_grant_institutional_data_no_go",
            "official_sdk_package_no_go",
            "compliance_certification_no_go",
            "live_postgres_production_claim_no_go",
            "ephemeral_live_postgres_validation_not_overclaimed",
            "controlled_preview_expansion_synthetic_demo_only",
            "package_publishing_avoided",
            "package_metadata_avoided",
            "security_reports_route_to_github_security_advisories",
            "no_exploit_details",
            "no_real_secrets",
            "no_real_customer_private_data",
            "no_backend_src_changes",
            "no_api_behavior_changes",
            "no_migrations_db_schema_dependency_changes",
            "no_github_workflow_changes",
            "no_snapshot_publish_script_changes",
            "unrelated_website_design_import_files_excluded",
        ]:
            self.assertTrue(confirmations.get(key), key)

    def test_docs_and_json_do_not_contain_raw_secret_values(self):
        forbidden_patterns = [
            r"postgres(ql)?://[^<\s]+",
            r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}",
            r"BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY",
            r"sk-[A-Za-z0-9]{20,}",
            r"ghp_[A-Za-z0-9]{20,}",
        ]
        for pattern in forbidden_patterns:
            self.assertIsNone(re.search(pattern, self.combined), pattern)

    def test_no_public_export_directory_created(self):
        forbidden_dirs = [
            "public-export",
            "public_export",
            "public-snapshot",
            "public_snapshot",
            "grantlayer-public-snapshot",
            "grantlayer-public-export",
        ]
        created = [path for path in forbidden_dirs if os.path.exists(_path(path))]
        self.assertEqual(created, [])

    def test_unrelated_website_design_import_files_excluded(self):
        changed = _branch_diff_files()
        self.assertFalse(any(path.startswith("website-design/") for path in changed))
        self.assertFalse(
            any("website_design_workspace_import" in path or "website-design-workspace-import" in path for path in changed)
        )


class TestGL212ScopeGuards(unittest.TestCase):
    def test_allowed_changed_files_only(self):
        changed = _branch_diff_files()
        unexpected = changed - ALLOWED_CHANGED_FILES
        self.assertEqual(unexpected, set())

    def test_no_backend_src_or_behavioral_changes(self):
        changed = _branch_diff_files()
        self.assertFalse(any(path.startswith("backend/src/") for path in changed))
        self.assertFalse(any(path.startswith("backend/src/migrations/") for path in changed))
        self.assertFalse(any(path.startswith("migrations/") for path in changed))
        self.assertFalse(any(path in {"docs/openapi.yaml", "openapi.yaml"} for path in changed))

    def test_no_github_workflow_or_snapshot_publish_script_changes(self):
        changed = _branch_diff_files()
        self.assertFalse(any(path.startswith(".github/workflows/") for path in changed))
        self.assertFalse(any("snapshot" in path.lower() and "publish" in path.lower() for path in changed))

    def test_no_package_publishing_metadata_added(self):
        changed = _branch_diff_files()
        forbidden_exact = {"setup.py", "package.json", "package-lock.json"}
        self.assertFalse(changed & forbidden_exact)
        self.assertFalse(any(path.endswith("/setup.py") for path in changed))
        self.assertFalse(any(path.endswith("/package.json") for path in changed))
        self.assertFalse(any(path.endswith("/package-lock.json") for path in changed))
        self.assertFalse(any(path == "sdk/pyproject.toml" or path.startswith("sdk/") and path.endswith("/pyproject.toml") for path in changed))

    def test_no_release_metadata_or_visibility_behavior_changes(self):
        changed = _branch_diff_files()
        forbidden_fragments = ["release", "visibility", "force-push", "force_push"]
        unsafe = [
            path
            for path in changed
            if path not in ALLOWED_CHANGED_FILES
            and any(fragment in path.lower() for fragment in forbidden_fragments)
        ]
        self.assertEqual(unsafe, [])
