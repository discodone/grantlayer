"""GL-206B live PostgreSQL validation execution artifact tests."""

from __future__ import annotations

import json
import os
import re
import subprocess
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "live_postgres_validation_execution_gl206b.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl206b",
    "live_postgres_validation_execution_gl206b.json",
)

ALLOWED_RESULTS = {
    "ready_for_merge",
    "blocked_no_safe_ephemeral_postgres",
    "blocked_ephemeral_postgres_setup",
    "blocked_real_live_postgres_regression",
}
ALLOWED_DECISIONS = ALLOWED_RESULTS

ALLOWED_CHANGED_FILES = {
    "backend/tests/test_gl206b_live_postgres_validation_execution.py",
    "docs/live_postgres_validation_execution_gl206b.md",
    "docs/examples/gl206b/live_postgres_validation_execution_gl206b.json",
    "scripts/ops/gl205_live_postgres_validation.py",
}

PREEXISTING_UNTRACKED_EXCLUSIONS = {
    "docs/website_design_workspace_import_report.md",
    "docs/website_design_workspace_import_dirty_stop.md",
    "docs/website_design_workspace_import_report_dirty_stop.md",
    "docs/website-design-workspace-import-report.md",
    "docs/website-design-workspace-import-report-dirty-stop.md",
}


def _path(relpath: str) -> str:
    return os.path.join(REPO_ROOT, relpath)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _load_doc() -> str:
    return _read(DOC_PATH)


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


class TestGL206BArtifacts(unittest.TestCase):
    def test_doc_exists(self):
        self.assertTrue(os.path.isfile(DOC_PATH))

    def test_json_artifact_exists_and_valid(self):
        self.assertTrue(os.path.isfile(JSON_PATH))
        self.assertIsInstance(_load_json(), dict)

    def test_issue_id_result_and_decision(self):
        data = _load_json()
        self.assertEqual(data.get("issue_id"), "GL-206B")
        self.assertIn(data.get("result"), ALLOWED_RESULTS)
        self.assertIn(data.get("decision"), ALLOWED_DECISIONS)

    def test_required_json_sections_present(self):
        required = [
            "decision_rationale",
            "input_sources_reviewed",
            "ephemeral_postgres_safety_assessment",
            "live_validation_execution_status",
            "command_class_without_raw_dsn",
            "live_validation_result",
            "migration_readiness_result",
            "backup_restore_governance_alignment",
            "audit_governance_alignment",
            "tenant_workspace_preservation_assessment",
            "admin_operator_preservation_assessment",
            "secret_safety_confirmation",
            "production_readiness_impact",
            "controlled_preview_impact",
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


class TestGL206BExecutionResult(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()

    def test_ephemeral_postgres_safety_assessment(self):
        assessment = self.data["ephemeral_postgres_safety_assessment"]
        self.assertTrue(assessment["ephemeral_postgres_available"])
        self.assertFalse(assessment["production_staging_shared_database_used"])
        self.assertTrue(assessment["synthetic_demo_data_only"])
        self.assertTrue(assessment["raw_dsn_avoided_in_artifacts"])
        self.assertTrue(assessment["container_cleanup_confirmed"])

    def test_live_validation_executed_and_gated(self):
        status = self.data["live_validation_execution_status"]
        self.assertTrue(status["executed"])
        self.assertEqual(status["mode"], "true_live_mode")
        self.assertTrue(status["gated"])
        self.assertEqual(status["enable_env_var"], "GRANTLAYER_GL205_ENABLE_LIVE_POSTGRES")
        self.assertEqual(status["dsn_env_var"], "GRANTLAYER_GL205_POSTGRES_DSN")

    def test_command_class_omits_raw_dsn(self):
        command = self.data["command_class_without_raw_dsn"]
        self.assertIn("GRANTLAYER_GL205_ENABLE_LIVE_POSTGRES=1", command)
        self.assertIn("GRANTLAYER_GL205_POSTGRES_DSN=<safe_ephemeral_postgres_dsn>", command)
        self.assertIn("scripts/ops/gl205_live_postgres_validation.py --live", command)
        self.assertNotRegex(command, r"postgres(ql)?://")

    def test_live_validation_result(self):
        result = self.data["live_validation_result"]
        self.assertEqual(result["result"], "passed_with_cleanup_caveat")
        self.assertTrue(result["postgres_reachable"])
        self.assertTrue(result["migrations_applied"])
        self.assertTrue(result["migration_idempotency_confirmed"])
        self.assertTrue(result["tenant_workspace_columns_verified"])
        self.assertTrue(result["audit_hash_chain_verified"])
        self.assertFalse(result["production_postgres_readiness_claimed"])

    def test_migration_backup_audit_and_preservation_results(self):
        self.assertTrue(self.data["migration_readiness_result"]["ephemeral_postgres_migrations_apply"])
        self.assertTrue(self.data["backup_restore_governance_alignment"]["gl205_backup_restore_dry_run_and_plan_safe"])
        self.assertFalse(self.data["backup_restore_governance_alignment"]["postgres_live_backup_restore_executed"])
        self.assertTrue(self.data["audit_governance_alignment"]["immutability_preserved"])
        self.assertTrue(self.data["tenant_workspace_preservation_assessment"]["tenant_columns_present_where_tested"])
        self.assertFalse(self.data["admin_operator_preservation_assessment"]["api_behavior_changed"])


class TestGL206BSafetyWording(unittest.TestCase):
    def setUp(self):
        self.doc = _load_doc()
        self.data = _load_json()
        self.combined = self.doc + "\n" + json.dumps(self.data, sort_keys=True)
        self.lower = self.combined.lower()

    def test_required_boundary_phrases(self):
        for phrase in [
            "Developer Preview / Controlled Preview with strict boundaries",
            "Production SaaS is no-go",
            "Real customer data, private grant data, and institutional data remain no-go",
            "official SDK or package",
            "Compliance certification",
            "not production PostgreSQL readiness",
            "Security-sensitive reports route to GitHub Security Advisories",
            "No exploit details are included",
            "No real secrets are included",
            "No real customer/private data is used",
        ]:
            self.assertIn(phrase, self.doc)

    def test_safety_confirmations(self):
        confirmations = self.data["safety_confirmations"]
        for key in [
            "developer_preview_controlled_preview_with_strict_boundaries",
            "production_saas_no_go",
            "real_customer_private_grant_institutional_data_no_go",
            "official_sdk_package_no_go",
            "compliance_certification_no_go",
            "live_postgres_production_claim_no_go",
            "successful_ephemeral_validation_not_production_readiness",
            "raw_dsn_avoided",
            "credentials_avoided_in_docs_logs_artifacts",
            "no_production_staging_shared_db_used",
            "synthetic_demo_data_only",
            "package_publishing_avoided",
            "security_reports_route_to_github_security_advisories",
            "no_exploit_details",
            "no_real_secrets",
            "no_real_customer_private_data",
            "no_public_github_push",
            "no_public_publish",
            "no_visibility_change",
            "no_github_workflow_changes",
            "no_snapshot_publish_script_changes",
            "no_backend_src_changes",
            "no_api_behavior_changes",
            "no_migrations_db_schema_dependency_changes",
        ]:
            self.assertTrue(confirmations.get(key), key)

    def test_docs_and_json_do_not_contain_raw_secret_values(self):
        forbidden_patterns = [
            r"postgres(ql)?://[^<\s]+",
            r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}",
            r"Authorization:\s*Bearer",
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
            r"password\s*[:=]\s*['\"][^'\"]+['\"]",
            r"token\s*[:=]\s*['\"][^'\"]+['\"]",
            r"auth[_ -]?header\s*[:=]\s*['\"][^'\"]+['\"]",
            r"private[_ -]?key\s*[:=]\s*['\"][^'\"]+['\"]",
        ]
        for pattern in forbidden_patterns:
            self.assertIsNone(re.search(pattern, self.combined, re.IGNORECASE), pattern)

    def test_no_real_data_or_public_publish_claims(self):
        self.assertNotIn("production saas readiness: ready", self.lower)
        self.assertNotIn("production postgres readiness: ready", self.lower)
        self.assertNotIn("real customer data ready", self.lower)
        self.assertNotIn("private grant data ready", self.lower)
        self.assertNotIn("official sdk/package available", self.lower)
        self.assertNotIn("compliance certified", self.lower)
        self.assertNotIn("public publish complete", self.lower)


class TestGL206BScopeGuard(unittest.TestCase):
    def test_changed_files_stay_in_gl206b_scope(self):
        unexpected = _branch_diff_files() - ALLOWED_CHANGED_FILES
        self.assertEqual(unexpected, set())

    def test_no_forbidden_file_changes(self):
        changed = _branch_diff_files()
        forbidden_prefixes = (
            ".github/workflows/",
            "frontend/",
            "frontend/website/design/",
            "website-design/",
            "scripts/snapshot",
            "sdk/",
        )
        forbidden_exact = {
            "package.json",
            "package-lock.json",
            "setup.py",
            "pyproject.toml",
            "requirements.txt",
            "requirements-dev.txt",
        }
        offenders = {
            path
            for path in changed
            if path in forbidden_exact or any(path.startswith(prefix) for prefix in forbidden_prefixes)
        }
        self.assertEqual(offenders, set())


if __name__ == "__main__":
    unittest.main()
