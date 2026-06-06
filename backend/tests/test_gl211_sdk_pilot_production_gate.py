"""GL-211 SDK / Pilot / Production Gate tests."""

from __future__ import annotations

import json
import os
import re
import subprocess
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "sdk_pilot_production_gate.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl211",
    "sdk_pilot_production_gate.json",
)
CHECKLIST_PATH = os.path.join(REPO_ROOT, "docs", "controlled_pilot_gate_checklist.md")

ALLOWED_RESULTS = {
    "approved_with_gaps",
    "ready_for_merge",
    "sdk_pilot_production_gate_approved_with_gaps",
}
ALLOWED_DECISIONS = {
    "approved_with_gaps",
    "sdk_pilot_production_gate_approved_with_gaps",
}
ALLOWED_CHANGED_FILES = {
    "backend/tests/test_gl211_sdk_pilot_production_gate.py",
    "docs/sdk_pilot_production_gate.md",
    "docs/examples/gl211/sdk_pilot_production_gate.json",
    "docs/controlled_pilot_gate_checklist.md",
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


def _combined_gl211_text() -> str:
    files = [
        "docs/sdk_pilot_production_gate.md",
        "docs/examples/gl211/sdk_pilot_production_gate.json",
        "docs/controlled_pilot_gate_checklist.md",
    ]
    return "\n".join(_read(path) for path in files if os.path.exists(_path(path)))


class TestGL211Artifacts(unittest.TestCase):
    def test_docs_file_exists(self):
        self.assertTrue(os.path.isfile(DOC_PATH))

    def test_json_artifact_exists_and_valid(self):
        self.assertTrue(os.path.isfile(JSON_PATH))
        self.assertIsInstance(_load_json(), dict)

    def test_issue_id_result_and_decision(self):
        data = _load_json()
        self.assertEqual(data.get("issue_id"), "GL-211")
        self.assertIn(data.get("result"), ALLOWED_RESULTS)
        self.assertIn(data.get("decision"), ALLOWED_DECISIONS)

    def test_required_json_sections_present(self):
        required = [
            "decision_rationale",
            "input_sources_reviewed",
            "current_state_summary",
            "sdk_gate_decision",
            "official_sdk_package_decision",
            "experimental_sdk_package_decision",
            "internal_sdk_prototype_boundary",
            "package_publishing_boundary",
            "pilot_gate_decision",
            "pilot_tier_matrix",
            "controlled_external_review_boundary",
            "first_external_controlled_pilot_boundary",
            "production_gate_decision",
            "production_no_go_rationale",
            "real_data_no_go_rationale",
            "live_postgres_blocker_status",
            "website_public_snapshot_gate",
            "public_claim_boundary_preservation",
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

    def test_current_state_summary_exists(self):
        summary = _load_json()["current_state_summary"]
        self.assertEqual(summary["posture"], "Developer Preview / Controlled Preview with strict boundaries")
        self.assertEqual(summary["production_saas"], "NO-GO")


class TestGL211GateDecisions(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()

    def test_sdk_gate_decision_exists(self):
        decision = json.dumps(self.data["sdk_gate_decision"]).lower()
        self.assertIn("official sdk/package", decision)
        self.assertIn("no-go", decision)

    def test_official_sdk_package_decision_is_no_go(self):
        decision = self.data["official_sdk_package_decision"]
        self.assertEqual(decision["decision"], "NO-GO")
        self.assertEqual(decision["package_registry_release"], "NO-GO")

    def test_experimental_sdk_package_decision_is_deferred_or_no_go(self):
        decision = json.dumps(self.data["experimental_sdk_package_decision"]).lower()
        self.assertTrue("deferred" in decision or "no-go" in decision)
        self.assertFalse(self.data["experimental_sdk_package_decision"]["implementation_in_gl211"])

    def test_internal_sdk_prototype_boundary_exists(self):
        boundary = self.data["internal_sdk_prototype_boundary"]
        self.assertTrue(boundary["allowed"])
        self.assertTrue(boundary["not_official"])
        self.assertTrue(boundary["not_published"])

    def test_package_publishing_boundary_exists(self):
        boundary = json.dumps(self.data["package_publishing_boundary"]).lower()
        for phrase in ["package_publishing", "setup_py", "sdk_pyproject_toml", "package_json"]:
            self.assertIn(phrase, boundary)
        self.assertIn("no-go", boundary)

    def test_pilot_gate_decision_exists(self):
        decision = self.data["pilot_gate_decision"]
        self.assertEqual(decision["first_external_controlled_pilot"], "CONDITIONAL")
        self.assertEqual(decision["real_data_pilot"], "NO-GO")
        self.assertEqual(decision["production_pilot"], "NO-GO")

    def test_pilot_tier_matrix_exists(self):
        tiers = {item["tier"]: item for item in self.data["pilot_tier_matrix"]}
        for tier in [
            "Internal demo",
            "Developer preview review",
            "Controlled external technical review",
            "First external controlled pilot",
            "Controlled preview expansion",
            "Real data pilot",
            "Production pilot",
        ]:
            self.assertIn(tier, tiers)
        self.assertEqual(tiers["Real data pilot"]["decision"], "NO-GO")
        self.assertEqual(tiers["Production pilot"]["decision"], "NO-GO")

    def test_controlled_external_review_boundary_exists(self):
        boundary = self.data["controlled_external_review_boundary"]
        self.assertEqual(boundary["decision"], "conditional")
        self.assertEqual(boundary["data_boundary"], "synthetic/demo only")
        self.assertEqual(boundary["security_reporting"], "GitHub Security Advisories")

    def test_first_external_controlled_pilot_boundary_exists(self):
        boundary = self.data["first_external_controlled_pilot_boundary"]
        self.assertEqual(boundary["decision"], "conditional")
        self.assertTrue(boundary["no_real_customer_data"])
        self.assertTrue(boundary["no_private_grant_institutional_data"])
        self.assertTrue(boundary["no_production_saas_claim"])

    def test_production_gate_decision_exists(self):
        decision = self.data["production_gate_decision"]
        for key in [
            "production_saas",
            "real_customer_data",
            "private_grant_institutional_data",
            "compliance_certification",
            "enterprise_readiness",
            "live_postgres_production_claim",
            "complete_tenant_isolation_claim",
            "complete_production_iam_claim",
        ]:
            self.assertEqual(decision[key], "NO-GO", key)

    def test_no_go_rationales_exist(self):
        self.assertGreater(len(self.data["production_no_go_rationale"]), 3)
        self.assertGreater(len(self.data["real_data_no_go_rationale"]), 2)

    def test_live_postgres_blocker_status_exists(self):
        status = self.data["live_postgres_blocker_status"]
        self.assertIn("pending", status["gl206b_status"])
        self.assertFalse(status["started_in_gl211"])
        self.assertEqual(status["production_claim"], "NO-GO")

    def test_website_public_snapshot_gate_exists(self):
        gate = self.data["website_public_snapshot_gate"]
        self.assertEqual(gate["public_publish"], "NO in GL-211")
        self.assertIn("deferred", gate["public_snapshot_update"])

    def test_public_claim_boundary_preservation_exists(self):
        boundary = self.data["public_claim_boundary_preservation"]
        for key, value in boundary.items():
            self.assertTrue(value, key)


class TestGL211DocumentationSafety(unittest.TestCase):
    def test_docs_required_no_go_language(self):
        doc = " ".join(_load_doc().split())
        required_phrases = [
            "Developer Preview / Controlled Preview with strict boundaries",
            "Production SaaS is no-go",
            "Real customer data, private grant data, and institutional data remain no-go",
            "internal SDK prototype is not an official SDK or package",
            "Experimental public SDK/package work remains deferred",
            "Live PostgreSQL production readiness is not claimed",
            "Public website publish remains no-go in this issue",
            "Compliance certification is not claimed",
            "Security-sensitive reports route to GitHub Security Advisories",
            "No exploit details are included",
            "No real secrets are included",
            "No real customer/private data is used",
        ]
        for phrase in required_phrases:
            self.assertIn(phrase, doc)

    def test_docs_do_not_overclaim_baselines(self):
        doc = " ".join(_load_doc().split())
        required = [
            "Tenant/workspace isolation baseline exists but is not production-complete",
            "Admin/operator tenant control-plane baseline exists but is not production-complete",
            "Runtime, IAM, abuse, and incident hardening baseline exists but is not production-complete",
            "Data governance/audit operations baseline exists but is not production-complete",
        ]
        for phrase in required:
            self.assertIn(phrase, doc)

    def test_json_safety_confirmations(self):
        safety = _load_json()["safety_confirmations"]
        for key in [
            "gate_decision_baseline_not_production_saas_readiness",
            "developer_preview_controlled_preview_only",
            "production_saas_not_claimed",
            "real_customer_private_grant_institutional_data_no_go",
            "official_sdk_package_no_go",
            "experimental_public_sdk_package_deferred_or_no_go",
            "internal_sdk_prototype_boundary_documented",
            "package_publishing_boundary_documented",
            "live_postgres_production_claim_no_go",
            "public_website_publish_no_go_in_gl211",
            "compliance_certification_not_claimed",
            "gdpr_soc2_iso_readiness_not_claimed",
            "enterprise_readiness_not_claimed",
            "tenant_workspace_isolation_not_overclaimed",
            "admin_operator_control_plane_not_overclaimed",
            "runtime_iam_abuse_incident_not_overclaimed",
            "data_governance_audit_operations_not_overclaimed",
            "website_public_publish_not_overclaimed",
            "controlled_preview_synthetic_demo_only",
            "package_publishing_avoided",
            "no_package_publishing_metadata",
            "security_reports_to_github_security_advisories",
            "no_exploit_details",
            "no_real_secrets",
            "no_real_customer_private_data",
            "no_backend_src_changes",
            "no_api_behavior_changes",
            "no_migrations_db_schema_dependency_changes",
            "no_github_workflow_changes",
            "no_snapshot_publish_script_changes",
            "no_public_github_push",
            "no_public_publish",
            "no_visibility_change",
            "unrelated_website_design_files_excluded",
        ]:
            self.assertTrue(safety.get(key), f"{key} must be true")

    def test_no_real_customer_private_data_or_secrets(self):
        combined = _combined_gl211_text()
        forbidden_patterns = [
            r"sk-[a-z0-9]{20,}",
            r"ghp_[a-z0-9]{20,}",
            r"postgres://[^\\s]+:[^\\s]+@",
            r"-----begin [a-z ]*private key-----",
            r"real customer data sample",
            r"private grant dossier",
            r"institutional confidential",
        ]
        for pattern in forbidden_patterns:
            self.assertIsNone(re.search(pattern, combined, re.IGNORECASE), pattern)

    def test_no_public_release_claim_phrases(self):
        combined = _combined_gl211_text().lower()
        prohibited_patterns = [
            r"(?<!not )production saas ready",
            r"(?<!not )enterprise ready",
            r"(?<!not )compliance certified",
            r"(?<!not )ready for real customer data",
            r"(?<!not )ready for private grant data",
            r"(?<!not )ready for institutional data",
            r"official sdk available",
            r"public sdk package available",
            r"production-ready sdk",
            r"live postgresql production ready",
            r"complete tenant/workspace production isolation",
        ]
        for pattern in prohibited_patterns:
            self.assertIsNone(re.search(pattern, combined), pattern)


class TestGL211ControlledPilotChecklist(unittest.TestCase):
    def test_internal_only_checklist_exists(self):
        self.assertTrue(os.path.isfile(CHECKLIST_PATH))

    def test_checklist_boundaries(self):
        checklist = " ".join(_read("docs/controlled_pilot_gate_checklist.md").split())
        required = [
            "Internal-only checklist",
            "synthetic/demo data only",
            "Confirm no real customer data is used",
            "Confirm no private grant data is used",
            "Confirm no institutional data is used",
            "Confirm no real secrets",
            "GitHub Security Advisories",
            "must not include exploit details",
            "not a public publish requirement",
        ]
        for phrase in required:
            self.assertIn(phrase, checklist)
        self.assertNotIn("join the pilot", checklist.lower())
        self.assertNotIn("sign up", checklist.lower())


class TestGL211ScopeGuards(unittest.TestCase):
    def test_branch_diff_only_contains_allowed_files(self):
        self.assertEqual(_branch_diff_files(), ALLOWED_CHANGED_FILES)

    def test_no_forbidden_changed_paths(self):
        forbidden_prefixes = [
            "backend/src/",
            "backend/src/migrations/",
            ".github/workflows/",
            "scripts/publish",
            "scripts/snapshot",
            "frontend/",
            "website/",
            "website-design/",
            "design/",
        ]
        forbidden_exact = {
            "package.json",
            "package-lock.json",
            "setup.py",
            "pyproject.toml",
            "requirements.txt",
            "requirements-dev.txt",
            "docs/openapi.yaml",
        }
        changed = _branch_diff_files()
        for path in changed:
            self.assertNotIn(path, forbidden_exact)
            self.assertFalse(any(path.startswith(prefix) for prefix in forbidden_prefixes), path)

    def test_no_package_publishing_metadata_added(self):
        changed = _branch_diff_files()
        forbidden_names = {
            "setup.py",
            "pyproject.toml",
            "package.json",
            "package-lock.json",
            "npm-shrinkwrap.json",
            "MANIFEST.in",
        }
        self.assertTrue(forbidden_names.isdisjoint({os.path.basename(path) for path in changed}))
        for relpath in [
            "setup.py",
            "pyproject.toml",
            "package.json",
            "package-lock.json",
            "examples/sdk_prototype/python/setup.py",
            "examples/sdk_prototype/python/pyproject.toml",
            "examples/sdk_prototype/python/package.json",
            "examples/sdk_prototype/python/package-lock.json",
        ]:
            self.assertFalse(os.path.exists(_path(relpath)), relpath)

    def test_no_github_workflow_snapshot_or_release_changes(self):
        changed = _branch_diff_files()
        for path in changed:
            lowered = path.lower()
            self.assertFalse(path.startswith(".github/workflows/"), path)
            self.assertFalse(path.startswith("scripts/") and "snapshot" in lowered, path)
            self.assertFalse(path.startswith("scripts/") and "publish" in lowered, path)
            self.assertFalse("release" in lowered and lowered.endswith((".md", ".json", ".yml", ".yaml")), path)

    def test_no_backend_src_api_migrations_db_schema_or_dependency_changes(self):
        changed = _branch_diff_files()
        for path in changed:
            self.assertFalse(path.startswith("backend/src/"), path)
            self.assertNotEqual(path, "docs/openapi.yaml")
            self.assertNotIn(path, {"requirements.txt", "requirements-dev.txt"})
            self.assertFalse("migration" in path.lower() and path.startswith("backend/src/"), path)
            self.assertFalse(path.endswith((".sql", ".db", ".sqlite", ".sqlite3")), path)

    def test_no_frontend_website_design_changes_except_internal_docs(self):
        changed = _branch_diff_files()
        for path in changed:
            self.assertFalse(path.startswith("frontend/"), path)
            self.assertFalse(path.startswith("website/"), path)
            self.assertFalse(path.startswith("website-design/"), path)
            self.assertFalse(path.startswith("design/"), path)

    def test_public_publish_github_visibility_behavior_not_changed(self):
        changed = _branch_diff_files()
        forbidden_fragments = [
            ".github/workflows/",
            "snapshot",
            "publish",
            "visibility",
            "deploy",
        ]
        for path in changed:
            lowered = path.lower()
            if path in ALLOWED_CHANGED_FILES:
                continue
            self.assertFalse(any(fragment in lowered for fragment in forbidden_fragments), path)

    def test_unrelated_website_design_files_excluded(self):
        changed = _branch_diff_files()
        self.assertFalse(any(path.startswith("website-design/") for path in changed))
        safety = _load_json()["safety_confirmations"]
        self.assertTrue(safety["unrelated_website_design_files_excluded"])
