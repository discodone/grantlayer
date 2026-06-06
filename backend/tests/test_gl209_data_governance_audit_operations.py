"""GL-209 Data Governance & Audit Operations tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "data_governance_audit_operations.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl209",
    "data_governance_audit_operations.json",
)
SCRIPT_PATH = os.path.join(REPO_ROOT, "scripts", "ops", "gl209_audit_export_check.py")

ALLOWED_RESULTS = {
    "approved_with_gaps",
    "ready_for_merge",
    "data_governance_audit_operations_baseline_approved_with_gaps",
}
ALLOWED_DECISIONS = {
    "approved_with_gaps",
    "data_governance_audit_operations_baseline_approved_with_gaps",
}


def _path(relpath: str) -> str:
    return os.path.join(REPO_ROOT, relpath)


def _load_doc() -> str:
    with open(DOC_PATH, encoding="utf-8") as f:
        return f.read()


def _load_json() -> dict:
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _branch_diff_files() -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {line for line in result.stdout.splitlines() if line.strip()}


class TestGL209Artifacts(unittest.TestCase):
    def test_docs_file_exists(self):
        self.assertTrue(os.path.isfile(DOC_PATH))

    def test_json_artifact_exists_and_valid(self):
        self.assertTrue(os.path.isfile(JSON_PATH))
        self.assertIsInstance(_load_json(), dict)

    def test_issue_id_result_and_decision(self):
        data = _load_json()
        self.assertEqual(data.get("issue_id"), "GL-209")
        self.assertIn(data.get("result"), ALLOWED_RESULTS)
        self.assertIn(data.get("decision"), ALLOWED_DECISIONS)

    def test_required_json_sections_present(self):
        required = [
            "decision_rationale",
            "input_sources_reviewed",
            "current_state_summary",
            "data_classification_baseline",
            "controlled_preview_data_boundary",
            "retention_policy_baseline",
            "deletion_policy_baseline",
            "redaction_policy_baseline",
            "audit_immutability_model",
            "audit_export_operations_baseline",
            "audit_hash_chain_operations",
            "evidence_bundle_operations",
            "backup_restore_governance_alignment",
            "postgres_backup_restore_status",
            "live_postgres_validation_status",
            "data_governance_risk_register",
            "compliance_non_goals",
            "implementation_summary",
            "controlled_preview_impact",
            "production_readiness_impact",
            "remaining_blockers",
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
        allowed_dirs = {
            "backend/src/migrations",
            "backend/tests",
            "scripts/ops",
            "scripts",
            "examples",
        }
        for source in _load_json()["input_sources_reviewed"]:
            rel = source.rstrip("/")
            if rel in allowed_dirs:
                continue
            if not os.path.exists(_path(rel)):
                missing.append(source)
        self.assertEqual(missing, [])


class TestGL209DocumentationSafety(unittest.TestCase):
    def test_docs_required_no_go_language(self):
        doc = " ".join(_load_doc().split())
        required_phrases = [
            "Developer Preview / Controlled Preview with strict boundaries",
            "Production SaaS is no-go",
            "Real customer data, private grant data, and institutional data remain no-go",
            "not an official SDK or package",
            "Live PostgreSQL production readiness is not claimed",
            "Compliance certification is not claimed",
            "GitHub Security Advisories",
            "No exploit details are included",
            "No real secrets are included",
            "No real customer/private data is used",
            "Source audit history must remain append-only and immutable",
            "Redaction applies to derived exports, views, reports, and diagnostics, not to source audit mutation",
            "Backup/restore production readiness is not claimed",
        ]
        for phrase in required_phrases:
            self.assertIn(phrase, doc)

    def test_json_safety_confirmations(self):
        safety = _load_json()["safety_confirmations"]
        for key in [
            "production_saas_not_claimed",
            "developer_preview_controlled_preview_only",
            "real_customer_private_grant_institutional_data_no_go",
            "official_sdk_package_no_go",
            "live_postgres_production_claim_no_go",
            "compliance_certification_not_claimed",
            "backup_restore_production_readiness_not_claimed",
            "security_reports_to_github_security_advisories",
            "no_exploit_details",
            "no_real_secrets",
            "no_real_customer_private_data",
            "audit_source_history_immutable",
            "redaction_derived_only_no_source_audit_mutation",
            "no_destructive_audit_deletion",
            "tenant_workspace_isolation_not_overclaimed",
            "admin_operator_control_plane_not_overclaimed",
            "controlled_preview_synthetic_demo_only",
            "package_publishing_avoided",
            "no_frontend_website_design_changes",
            "no_github_workflow_changes",
            "no_public_github_push",
            "no_public_publish",
            "no_visibility_change",
            "unrelated_website_files_excluded",
        ]:
            self.assertTrue(safety.get(key), f"{key} must be true")

    def test_no_prohibited_claims(self):
        combined = (_load_doc() + "\n" + json.dumps(_load_json())).lower()
        prohibited = [
            "production saas ready",
            "ready for real customer data",
            "ready for private grant data",
            "ready for institutional data",
            "official sdk/package available",
            "live postgresql production ready",
            "compliance certified",
            "gdpr ready",
            "soc2 ready",
            "iso ready",
        ]
        for phrase in prohibited:
            self.assertNotIn(phrase, combined)


class TestGL209AuditExportScript(unittest.TestCase):
    def test_script_exists(self):
        self.assertTrue(os.path.isfile(SCRIPT_PATH))

    def test_script_supports_plan_and_dry_run(self):
        for flag in ["--plan", "--dry-run"]:
            result = subprocess.run(
                [sys.executable, SCRIPT_PATH, flag],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = result.stdout.lower()
            self.assertIn("gl-209", output)
            self.assertIn("no db connection", output)
            self.assertNotIn("bearer ", output)
            self.assertNotIn("password=", output)
            self.assertNotIn("postgres://", output)

    def test_script_sample_manifest_is_safe(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            output_path = tmp.name
        try:
            result = subprocess.run(
                [sys.executable, SCRIPT_PATH, "--sample", "--output", output_path],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            with open(output_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["issue_id"], "GL-209")
            self.assertFalse(data["source_audit_mutated"])
            self.assertFalse(data["includes_tokens_or_hashes"])
            self.assertFalse(data["includes_real_customer_private_data"])
            serialized = json.dumps(data).lower()
            for forbidden in [
                "bearer ",
                "authorization",
                "token_hash",
                "postgres://",
                "password",
                "private key",
                "customer data",
                "private grant",
                "institutional data",
                "request body",
                "evidence payload",
            ]:
                self.assertNotIn(forbidden, serialized)
        finally:
            try:
                os.unlink(output_path)
            except OSError:
                pass

    def test_script_has_no_destructive_audit_sql(self):
        with open(SCRIPT_PATH, encoding="utf-8") as f:
            script = f.read().lower()
        forbidden = [
            "delete from audit_events",
            "update audit_events",
            "drop table audit_events",
            "truncate audit_events",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, script)


class TestGL209ScopeGuards(unittest.TestCase):
    def test_scope_diff_only_allowed_files(self):
        allowed = {
            "backend/tests/test_gl209_data_governance_audit_operations.py",
            "docs/data_governance_audit_operations.md",
            "docs/examples/gl209/data_governance_audit_operations.json",
            "scripts/ops/gl209_audit_export_check.py",
        }
        changed = _branch_diff_files()
        self.assertTrue(allowed.issuperset(changed), changed - allowed)

    def test_no_frontend_website_design_or_workflow_changes(self):
        changed = _branch_diff_files()
        forbidden_prefixes = (
            "frontend/",
            "website-design/",
            ".github/workflows/",
        )
        for path in changed:
            self.assertFalse(path.startswith(forbidden_prefixes), path)
        self.assertNotIn("docs/website_design_workspace_import_report.md", changed)
        self.assertNotIn("docs/website_design_workspace_import_dirty_stop.md", changed)

    def test_no_backend_src_openapi_migration_or_package_changes(self):
        changed = _branch_diff_files()
        forbidden = {
            "docs/openapi.yaml",
            "setup.py",
            "package.json",
            "package-lock.json",
            "pyproject.toml",
            "sdk/python/pyproject.toml",
        }
        self.assertTrue(forbidden.isdisjoint(changed))
        self.assertFalse(any(path.startswith("backend/src/") for path in changed))
        self.assertFalse(any(path.startswith("backend/src/migrations/") for path in changed))

    def test_no_public_publish_visibility_or_force_push_behavior(self):
        changed = _branch_diff_files()
        self.assertFalse(any("snapshot" in path.lower() for path in changed))
        combined = _load_doc().lower() + "\n" + json.dumps(_load_json()).lower()
        for phrase in [
            "git push github",
            "gh repo edit",
            "visibility public",
            "force push",
            "public publish performed",
        ]:
            self.assertNotIn(phrase, combined)


if __name__ == "__main__":
    unittest.main()
