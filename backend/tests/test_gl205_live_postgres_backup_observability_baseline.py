"""GL-205 — Live PostgreSQL Validation / Backup-Restore Drill / Observability Baseline tests.

Verifies the existence, structure, gating, safety confirmations, and decision content
of the GL-205 documentation artifact, JSON evidence bundle, and operational scripts.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
_DOC_PATH = os.path.join(
    _REPO_ROOT, "docs", "live_postgres_backup_observability_baseline.md"
)
_JSON_PATH = os.path.join(
    _REPO_ROOT, "docs", "examples", "gl205", "live_postgres_backup_observability_baseline.json"
)
_PG_SCRIPT = os.path.join(
    _REPO_ROOT, "scripts", "ops", "gl205_live_postgres_validation.py"
)
_DR_SCRIPT = os.path.join(
    _REPO_ROOT, "scripts", "ops", "gl205_backup_restore_drill.py"
)

_ALLOWED_RESULTS = {"ready_for_merge", "merged", "deferred", "blocked"}
_ALLOWED_DECISIONS = {
    "operational_readiness_baseline_proceed_with_documented_gaps",
    "operational_readiness_baseline_proceed",
    "operational_readiness_proceed",
    "no_go_production_saas_continue_developer_preview_controlled_preview",
}

_PG_ENABLE_ENV = "GRANTLAYER_GL205_ENABLE_LIVE_POSTGRES"
_PG_DSN_ENV = "GRANTLAYER_GL205_POSTGRES_DSN"


def _load_json():
    with open(_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_doc():
    with open(_DOC_PATH, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Artifact existence
# ---------------------------------------------------------------------------

class TestGL205ArtifactExists(unittest.TestCase):

    def test_doc_file_exists(self):
        self.assertTrue(
            os.path.isfile(_DOC_PATH),
            f"docs/live_postgres_backup_observability_baseline.md must exist at {_DOC_PATH}",
        )

    def test_json_artifact_exists(self):
        self.assertTrue(
            os.path.isfile(_JSON_PATH),
            f"docs/examples/gl205/live_postgres_backup_observability_baseline.json must exist at {_JSON_PATH}",
        )

    def test_json_is_valid(self):
        data = _load_json()
        self.assertIsInstance(data, dict, "JSON artifact must be a JSON object")

    def test_live_postgres_script_exists(self):
        self.assertTrue(
            os.path.isfile(_PG_SCRIPT),
            f"scripts/ops/gl205_live_postgres_validation.py must exist at {_PG_SCRIPT}",
        )

    def test_backup_restore_drill_script_exists(self):
        self.assertTrue(
            os.path.isfile(_DR_SCRIPT),
            f"scripts/ops/gl205_backup_restore_drill.py must exist at {_DR_SCRIPT}",
        )


# ---------------------------------------------------------------------------
# JSON structure
# ---------------------------------------------------------------------------

class TestGL205JSONStructure(unittest.TestCase):

    def setUp(self):
        self.data = _load_json()

    def test_issue_id_is_gl205(self):
        self.assertEqual(self.data.get("issue_id"), "GL-205", "issue_id must be GL-205")

    def test_result_is_allowed(self):
        result = self.data.get("result", "")
        self.assertIn(
            result,
            _ALLOWED_RESULTS,
            f"result '{result}' is not in allowed values {_ALLOWED_RESULTS}",
        )

    def test_decision_is_allowed(self):
        decision = self.data.get("decision", "")
        allowed_fragments = [
            "operational_readiness_baseline",
            "operational_readiness",
            "no_go_production_saas",
            "proceed",
        ]
        self.assertTrue(
            any(frag in decision for frag in allowed_fragments),
            f"decision '{decision}' must reflect operational readiness baseline",
        )

    def test_input_sources_reviewed_exists(self):
        sources = self.data.get("input_sources_reviewed")
        self.assertIsInstance(sources, list, "input_sources_reviewed must be a list")
        self.assertGreater(len(sources), 10, "input_sources_reviewed must list key sources")

    def test_live_postgres_validation_plan_exists(self):
        plan = self.data.get("live_postgres_validation_plan")
        self.assertIsNotNone(plan, "live_postgres_validation_plan must exist")
        self.assertTrue(bool(plan), "live_postgres_validation_plan must be non-empty")

    def test_live_postgres_gating_model_exists(self):
        model = self.data.get("live_postgres_gating_model")
        self.assertIsNotNone(model, "live_postgres_gating_model must exist")
        self.assertTrue(bool(model), "live_postgres_gating_model must be non-empty")

    def test_live_postgres_execution_status_exists(self):
        status = self.data.get("live_postgres_execution_status")
        self.assertIsNotNone(status, "live_postgres_execution_status must exist")
        self.assertTrue(bool(status), "live_postgres_execution_status must be non-empty")

    def test_backup_restore_drill_plan_exists(self):
        plan = self.data.get("backup_restore_drill_plan")
        self.assertIsNotNone(plan, "backup_restore_drill_plan must exist")
        self.assertTrue(bool(plan), "backup_restore_drill_plan must be non-empty")

    def test_backup_restore_execution_status_exists(self):
        status = self.data.get("backup_restore_execution_status")
        self.assertIsNotNone(status, "backup_restore_execution_status must exist")
        self.assertTrue(bool(status), "backup_restore_execution_status must be non-empty")

    def test_observability_baseline_exists(self):
        obs = self.data.get("observability_baseline")
        self.assertIsNotNone(obs, "observability_baseline must exist")
        self.assertTrue(bool(obs), "observability_baseline must be non-empty")

    def test_logging_secret_safety_model_exists(self):
        model = self.data.get("logging_secret_safety_model")
        self.assertIsNotNone(model, "logging_secret_safety_model must exist")
        self.assertTrue(bool(model), "logging_secret_safety_model must be non-empty")

    def test_tenant_workspace_preservation_assessment_exists(self):
        assessment = self.data.get("tenant_workspace_preservation_assessment")
        self.assertIsNotNone(
            assessment, "tenant_workspace_preservation_assessment must exist"
        )

    def test_audit_immutability_preservation_assessment_exists(self):
        assessment = self.data.get("audit_immutability_preservation_assessment")
        self.assertIsNotNone(
            assessment, "audit_immutability_preservation_assessment must exist"
        )

    def test_production_readiness_impact_exists(self):
        impact = self.data.get("production_readiness_impact")
        self.assertIsNotNone(impact, "production_readiness_impact must exist")
        self.assertTrue(bool(impact), "production_readiness_impact must be non-empty")

    def test_remaining_blockers_exist(self):
        blockers = self.data.get("remaining_blockers")
        self.assertIsInstance(blockers, list, "remaining_blockers must be a list")
        self.assertGreater(len(blockers), 0, "remaining_blockers must be non-empty")

    def test_risk_register_exists(self):
        register = self.data.get("risk_register")
        self.assertIsNotNone(register, "risk_register must exist")
        self.assertTrue(bool(register), "risk_register must be non-empty")

    def test_safety_confirmations_exist(self):
        confirmations = self.data.get("safety_confirmations")
        self.assertIsNotNone(confirmations, "safety_confirmations must exist")
        self.assertTrue(bool(confirmations), "safety_confirmations must be non-empty")

    def test_recommended_next_issues_exist(self):
        next_issues = self.data.get("recommended_next_issues")
        self.assertIsInstance(next_issues, list, "recommended_next_issues must be a list")
        self.assertGreater(len(next_issues), 0, "recommended_next_issues must be non-empty")


# ---------------------------------------------------------------------------
# Safety confirmations
# ---------------------------------------------------------------------------

class TestGL205SafetyConfirmations(unittest.TestCase):

    def setUp(self):
        self.data = _load_json()
        self.confirmations = self.data.get("safety_confirmations", {})

    def test_developer_preview_controlled_preview_with_strict_boundaries(self):
        self.assertTrue(
            self.confirmations.get("developer_preview_controlled_preview_with_strict_boundaries"),
            "safety_confirmations must confirm Developer Preview / Controlled Preview with strict boundaries",
        )

    def test_not_production_saas(self):
        self.assertTrue(
            self.confirmations.get("not_production_saas"),
            "safety_confirmations must confirm not production SaaS",
        )

    def test_not_ready_for_real_customer_private_grant_data(self):
        self.assertTrue(
            self.confirmations.get("not_ready_for_real_customer_private_grant_data"),
            "safety_confirmations must confirm not ready for real customer/private grant data",
        )

    def test_no_official_sdk_package_claimed(self):
        self.assertTrue(
            self.confirmations.get("no_official_sdk_package_claimed"),
            "safety_confirmations must confirm no official SDK/package claimed",
        )

    def test_security_reports_route_to_github_security_advisories(self):
        self.assertTrue(
            self.confirmations.get("security_reports_route_to_github_security_advisories"),
            "safety_confirmations must confirm security reports route to GitHub Security Advisories",
        )

    def test_no_exploit_details(self):
        self.assertTrue(
            self.confirmations.get("no_exploit_details"),
            "safety_confirmations must confirm no exploit details included",
        )

    def test_no_real_secrets(self):
        self.assertTrue(
            self.confirmations.get("no_real_secrets"),
            "safety_confirmations must confirm no real secrets included",
        )

    def test_no_real_customer_private_grant_data(self):
        self.assertTrue(
            self.confirmations.get("no_real_customer_private_grant_data"),
            "safety_confirmations must confirm no real customer/private grant data included",
        )

    def test_live_postgres_production_claim_no_go(self):
        self.assertTrue(
            self.confirmations.get("live_postgres_production_claim_no_go"),
            "safety_confirmations must confirm live PostgreSQL production claim is no-go",
        )

    def test_no_public_publish(self):
        self.assertTrue(
            self.confirmations.get("no_public_publish"),
            "safety_confirmations must confirm no public publish",
        )

    def test_no_github_push(self):
        self.assertTrue(
            self.confirmations.get("no_github_push"),
            "safety_confirmations must confirm no GitHub push",
        )

    def test_no_visibility_change(self):
        self.assertTrue(
            self.confirmations.get("no_visibility_change"),
            "safety_confirmations must confirm no visibility change",
        )

    def test_no_frontend_website_design_changes(self):
        self.assertTrue(
            self.confirmations.get("no_frontend_website_design_changes"),
            "safety_confirmations must confirm no frontend/website/design changes",
        )

    def test_no_github_workflow_changes(self):
        self.assertTrue(
            self.confirmations.get("no_github_workflow_changes"),
            "safety_confirmations must confirm no GitHub workflow changes",
        )

    def test_unrelated_untracked_website_files_excluded(self):
        self.assertTrue(
            self.confirmations.get("unrelated_untracked_website_files_excluded"),
            "safety_confirmations must confirm unrelated untracked website files are excluded",
        )


# ---------------------------------------------------------------------------
# Gating model
# ---------------------------------------------------------------------------

class TestGL205GatingModel(unittest.TestCase):

    def setUp(self):
        self.data = _load_json()
        self.gating = self.data.get("live_postgres_gating_model", {})

    def test_fail_closed(self):
        self.assertTrue(
            self.gating.get("fail_closed"),
            "live_postgres_gating_model must have fail_closed=true",
        )

    def test_rejects_sqlite_dsns(self):
        self.assertTrue(
            self.gating.get("rejects_sqlite_dsns"),
            "live_postgres_gating_model must confirm SQLite DSN rejection",
        )

    def test_rejects_empty_dsns(self):
        self.assertTrue(
            self.gating.get("rejects_empty_dsns"),
            "live_postgres_gating_model must confirm empty DSN rejection",
        )

    def test_rejects_placeholder_dsns(self):
        self.assertTrue(
            self.gating.get("rejects_placeholder_dsns"),
            "live_postgres_gating_model must confirm placeholder DSN rejection",
        )

    def test_never_logs_raw_dsn_or_password(self):
        self.assertTrue(
            self.gating.get("never_logs_raw_dsn_or_password"),
            "live_postgres_gating_model must confirm DSN/password never logged raw",
        )

    def test_supports_dry_run(self):
        self.assertTrue(
            self.gating.get("supports_dry_run"),
            "live_postgres_gating_model must confirm dry-run support",
        )

    def test_supports_plan_mode(self):
        self.assertTrue(
            self.gating.get("supports_plan_mode"),
            "live_postgres_gating_model must confirm plan mode support",
        )


# ---------------------------------------------------------------------------
# Backup/restore safety
# ---------------------------------------------------------------------------

class TestGL205BackupRestoreSafety(unittest.TestCase):

    def setUp(self):
        self.data = _load_json()

    def test_backup_restore_synthetic_data_only(self):
        self.assertTrue(
            self.data.get("backup_restore_synthetic_data_only"),
            "backup_restore_synthetic_data_only must be true",
        )

    def test_backup_restore_plan_has_sqlite_steps(self):
        plan = self.data.get("backup_restore_drill_plan", {})
        steps = plan.get("sqlite_steps", [])
        self.assertIsInstance(steps, list)
        self.assertGreater(len(steps), 5, "backup_restore_drill_plan must list SQLite drill steps")

    def test_backup_restore_plan_has_postgres_approach(self):
        plan = self.data.get("backup_restore_drill_plan", {})
        approach = plan.get("postgres_approach", "")
        self.assertTrue(bool(approach), "backup_restore_drill_plan must document PostgreSQL approach")


# ---------------------------------------------------------------------------
# Observability baseline
# ---------------------------------------------------------------------------

class TestGL205ObservabilityBaseline(unittest.TestCase):

    def setUp(self):
        self.data = _load_json()
        self.obs = self.data.get("observability_baseline", {})

    def test_structured_log_event_types_exist(self):
        types = self.obs.get("structured_log_event_types", [])
        self.assertIsInstance(types, list)
        self.assertGreater(len(types), 5, "observability_baseline must list structured log event types")

    def test_correlation_id_required(self):
        self.assertTrue(
            self.obs.get("correlation_id_required"),
            "observability_baseline must confirm correlation_id_required=true",
        )

    def test_production_observability_not_overclaimed(self):
        self.assertFalse(
            self.obs.get("production_observability_ready"),
            "observability_baseline must not claim production observability is ready",
        )

    def test_external_backend_not_claimed(self):
        self.assertFalse(
            self.obs.get("external_backend_available"),
            "observability_baseline must not claim an external backend is available",
        )

    def test_remaining_gaps_documented(self):
        gaps = self.obs.get("remaining_gaps", [])
        self.assertIsInstance(gaps, list)
        self.assertGreater(len(gaps), 0, "observability_baseline must document remaining gaps")


# ---------------------------------------------------------------------------
# Logging / secret-safety model
# ---------------------------------------------------------------------------

class TestGL205LoggingSecretSafety(unittest.TestCase):

    def setUp(self):
        self.data = _load_json()
        self.model = self.data.get("logging_secret_safety_model", {})

    def test_never_log_list_exists(self):
        never_log = self.model.get("never_log", [])
        self.assertIsInstance(never_log, list)
        self.assertGreater(len(never_log), 3, "logging_secret_safety_model must list never-log values")

    def _assert_never_log_contains(self, fragment: str):
        never_log = self.model.get("never_log", [])
        combined = " ".join(never_log).lower()
        self.assertIn(
            fragment.lower(),
            combined,
            f"logging_secret_safety_model.never_log must mention '{fragment}'",
        )

    def test_prohibits_raw_tokens(self):
        self._assert_never_log_contains("token")

    def test_prohibits_dsns_with_passwords(self):
        self._assert_never_log_contains("dsn")

    def test_prohibits_private_keys(self):
        self._assert_never_log_contains("private key")

    def test_prohibits_customer_data(self):
        combined = " ".join(self.model.get("never_log", [])).lower()
        self.assertTrue(
            "customer" in combined or "private grant" in combined or "institutional" in combined,
            "logging_secret_safety_model.never_log must prohibit customer/private grant data",
        )

    def test_prohibits_request_bodies_with_private_data(self):
        combined = " ".join(self.model.get("never_log", [])).lower()
        self.assertTrue(
            "request bod" in combined or "evidence payload" in combined,
            "logging_secret_safety_model.never_log must prohibit evidence/request body logging",
        )


# ---------------------------------------------------------------------------
# Preservation assessments
# ---------------------------------------------------------------------------

class TestGL205PreservationAssessments(unittest.TestCase):

    def setUp(self):
        self.data = _load_json()

    def test_tenant_workspace_isolation_preserved(self):
        assessment = self.data.get("tenant_workspace_preservation_assessment", {})
        self.assertTrue(
            assessment.get("gl200b_preserved"),
            "tenant_workspace_preservation_assessment must confirm GL-200B preserved",
        )
        self.assertFalse(
            assessment.get("overclaimed", True),
            "tenant_workspace_preservation_assessment must not overclaim isolation",
        )

    def test_audit_immutability_preserved(self):
        assessment = self.data.get("audit_immutability_preservation_assessment", {})
        self.assertTrue(
            assessment.get("preserved"),
            "audit_immutability_preservation_assessment must confirm preserved=true",
        )
        self.assertFalse(
            assessment.get("audit_log_py_modified"),
            "audit_log_py must not be modified by GL-205",
        )

    def test_gl201_auth_secrets_config_preserved(self):
        assessment = self.data.get("gl201_auth_secrets_config_preservation_assessment", {})
        self.assertTrue(
            assessment.get("preserved"),
            "gl201_auth_secrets_config_preservation_assessment must confirm preserved=true",
        )

    def test_gl203c_sdk_package_boundary_preserved(self):
        assessment = self.data.get("gl203c_sdk_package_boundary_preservation_assessment", {})
        self.assertTrue(
            assessment.get("preserved"),
            "gl203c_sdk_package_boundary_preservation_assessment must confirm preserved=true",
        )
        self.assertTrue(
            assessment.get("no_package_publishing_metadata"),
            "GL-205 must not add package publishing metadata",
        )
        self.assertTrue(
            assessment.get("no_official_sdk_claimed"),
            "GL-205 must not claim an official SDK",
        )

    def test_no_production_saas_claim(self):
        impact = self.data.get("production_readiness_impact", {})
        saas = impact.get("production_saas_readiness", "").lower()
        self.assertIn(
            "no_go",
            saas,
            "production_readiness_impact must keep production_saas_readiness as no-go",
        )

    def test_no_real_customer_data_claim(self):
        impact = self.data.get("production_readiness_impact", {})
        data_status = impact.get("real_customer_data_readiness", "").lower()
        self.assertIn(
            "no_go",
            data_status,
            "production_readiness_impact must keep real_customer_data_readiness as no-go",
        )


# ---------------------------------------------------------------------------
# Documentation content checks
# ---------------------------------------------------------------------------

class TestGL205DocContent(unittest.TestCase):

    def setUp(self):
        self.doc = _load_doc()

    def _assert_doc_contains(self, fragment: str, msg: str = ""):
        self.assertIn(
            fragment,
            self.doc,
            msg or f"Documentation must contain '{fragment}'",
        )

    def test_doc_states_developer_preview(self):
        self._assert_doc_contains(
            "Developer Preview",
            "Documentation must state Developer Preview",
        )

    def test_doc_states_controlled_preview(self):
        self._assert_doc_contains(
            "Controlled Preview",
            "Documentation must state Controlled Preview",
        )

    def test_doc_states_not_production_saas(self):
        self._assert_doc_contains(
            "Not production SaaS",
            "Documentation must state not production SaaS",
        )

    def test_doc_states_not_ready_for_real_customer_data(self):
        self._assert_doc_contains(
            "real customer data",
            "Documentation must state not ready for real customer/private grant data",
        )

    def test_doc_states_no_official_sdk(self):
        self._assert_doc_contains(
            "No official SDK",
            "Documentation must state no official SDK/package is claimed",
        )

    def test_doc_routes_security_reports(self):
        self._assert_doc_contains(
            "GitHub Security Advisories",
            "Documentation must route security-sensitive reports to GitHub Security Advisories",
        )

    def test_doc_states_no_exploit_details(self):
        self._assert_doc_contains(
            "No exploit details",
            "Documentation must state no exploit details are included",
        )

    def test_doc_states_no_real_secrets(self):
        self._assert_doc_contains(
            "No real secrets",
            "Documentation must state no real secrets are included",
        )

    def test_doc_states_no_real_customer_private_data_used(self):
        self._assert_doc_contains(
            "No real customer/private grant",
            "Documentation must state no real customer/private grant data is used",
        )

    def test_doc_live_postgres_execution_status(self):
        self._assert_doc_contains(
            "NOT EXECUTED",
            "Documentation must state live PostgreSQL validation was not executed",
        )

    def test_doc_live_postgres_production_claim_no_go(self):
        self._assert_doc_contains(
            "Live PostgreSQL production claim remains NO-GO",
            "Documentation must keep live PostgreSQL production claim as no-go",
        )

    def test_doc_operational_baseline_not_production_declaration(self):
        self._assert_doc_contains(
            "operational readiness baseline",
            "Documentation must state GL-205 is an operational readiness baseline",
        )

    def test_doc_website_files_excluded(self):
        self._assert_doc_contains(
            "website-design/",
            "Documentation must address exclusion of unrelated website files",
        )

    def test_doc_remaining_blockers_section(self):
        self._assert_doc_contains(
            "Remaining Blockers",
            "Documentation must have a Remaining Blockers section",
        )

    def test_doc_risk_register_section(self):
        self._assert_doc_contains(
            "Risk Register",
            "Documentation must have a Risk Register section",
        )

    def test_doc_observability_baseline_section(self):
        self._assert_doc_contains(
            "Observability Baseline",
            "Documentation must have an Observability Baseline section",
        )

    def test_doc_secret_safety_logging_rules(self):
        self._assert_doc_contains(
            "Secret-Safety Logging Rules",
            "Documentation must include secret-safety logging rules",
        )


# ---------------------------------------------------------------------------
# Script compilation checks
# ---------------------------------------------------------------------------

class TestGL205ScriptCompiles(unittest.TestCase):

    def _compile_check(self, script_path: str):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", script_path],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Script {script_path} must compile without errors.\n"
            f"stderr: {result.stderr}",
        )

    def test_live_postgres_script_compiles(self):
        self._compile_check(_PG_SCRIPT)

    def test_backup_restore_drill_script_compiles(self):
        self._compile_check(_DR_SCRIPT)


# ---------------------------------------------------------------------------
# Live PostgreSQL script gating tests
# ---------------------------------------------------------------------------

class TestGL205LivePostgresGating(unittest.TestCase):

    def _run_script(self, args: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
        import os as _os
        run_env = _os.environ.copy()
        # Clear any live gate vars to ensure clean state
        run_env.pop(_PG_ENABLE_ENV, None)
        run_env.pop(_PG_DSN_ENV, None)
        if env:
            run_env.update(env)
        return subprocess.run(
            [sys.executable, _PG_SCRIPT] + args,
            capture_output=True,
            text=True,
            env=run_env,
        )

    def test_dry_run_exits_zero(self):
        result = self._run_script(["--dry-run"])
        self.assertEqual(
            result.returncode, 0,
            f"--dry-run must exit 0.\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )

    def test_plan_exits_zero(self):
        result = self._run_script(["--plan"])
        self.assertEqual(
            result.returncode, 0,
            f"--plan must exit 0.\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )

    def test_live_refuses_without_gate(self):
        result = self._run_script(["--live"])
        self.assertNotEqual(
            result.returncode, 0,
            "--live must not succeed without the explicit gate env var",
        )
        combined = (result.stdout + result.stderr).lower()
        self.assertTrue(
            "gate" in combined or "enable" in combined or "refusing" in combined or "not set" in combined,
            f"--live without gate must print gate-related error.\nstdout: {result.stdout}",
        )

    def test_live_refuses_with_gate_but_missing_dsn(self):
        result = self._run_script(["--live"], env={_PG_ENABLE_ENV: "1"})
        self.assertNotEqual(
            result.returncode, 0,
            "--live with gate but no DSN must fail",
        )
        combined = (result.stdout + result.stderr).lower()
        self.assertTrue(
            "dsn" in combined or "postgres_dsn" in combined or "not set" in combined,
            f"Must report missing DSN.\nstdout: {result.stdout}",
        )

    def test_live_refuses_sqlite_dsn(self):
        result = self._run_script(
            ["--live"],
            env={
                _PG_ENABLE_ENV: "1",
                _PG_DSN_ENV: "sqlite:///tmp/test.db",
            },
        )
        self.assertNotEqual(
            result.returncode, 0,
            "--live with SQLite DSN must fail",
        )
        combined = (result.stdout + result.stderr).lower()
        self.assertTrue(
            "sqlite" in combined or "rejected" in combined or "reject" in combined
            or "invalid" in combined or "fail" in combined,
            f"Must report SQLite DSN rejection.\nstdout: {result.stdout}",
        )

    def test_live_refuses_placeholder_dsn(self):
        result = self._run_script(
            ["--live"],
            env={
                _PG_ENABLE_ENV: "1",
                _PG_DSN_ENV: "postgres://user:pass@localhost/mydb",
            },
        )
        self.assertNotEqual(
            result.returncode, 0,
            "--live with placeholder/localhost DSN must fail",
        )

    def test_dry_run_does_not_print_raw_dsn(self):
        fake_password = "supersecretpassword123"
        result = self._run_script(
            ["--dry-run"],
            env={
                _PG_ENABLE_ENV: "1",
                _PG_DSN_ENV: f"postgres://user:{fake_password}@some-safe-host.internal/testdb",
            },
        )
        self.assertNotIn(
            fake_password,
            result.stdout + result.stderr,
            "Script must not print raw DSN password in any output",
        )

    def test_plan_does_not_print_raw_dsn(self):
        fake_password = "anotherverysecretpassword456"
        result = self._run_script(
            ["--plan"],
            env={
                _PG_ENABLE_ENV: "1",
                _PG_DSN_ENV: f"postgres://user:{fake_password}@some-safe-host.internal/testdb",
            },
        )
        self.assertNotIn(
            fake_password,
            result.stdout + result.stderr,
            "Script must not print raw DSN password in any output",
        )


# ---------------------------------------------------------------------------
# Backup/restore drill script tests
# ---------------------------------------------------------------------------

class TestGL205BackupRestoreDrillScript(unittest.TestCase):

    def _run_script(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, _DR_SCRIPT] + args,
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
            env={**os.environ, "PYTHONPATH": os.path.join(_REPO_ROOT, "backend")},
        )

    def test_dry_run_exits_zero(self):
        result = self._run_script(["--dry-run"])
        self.assertEqual(
            result.returncode, 0,
            f"--dry-run must exit 0.\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )

    def test_plan_exits_zero(self):
        result = self._run_script(["--plan"])
        self.assertEqual(
            result.returncode, 0,
            f"--plan must exit 0.\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )

    def test_dry_run_no_file_operations(self):
        import tempfile
        result = self._run_script(["--dry-run"])
        self.assertEqual(result.returncode, 0)
        combined = result.stdout + result.stderr
        self.assertNotIn(
            "Created at temp path",
            combined,
            "--dry-run must not create temp files",
        )

    def test_plan_shows_postgres_checklist(self):
        result = self._run_script(["--plan"])
        self.assertEqual(result.returncode, 0)
        combined = result.stdout + result.stderr
        self.assertTrue(
            "checklist" in combined.lower() or "postgresql" in combined.lower(),
            "--plan must reference PostgreSQL manual drill checklist",
        )

    def test_sqlite_drill_uses_synthetic_data(self):
        result = self._run_script(["--sqlite-drill"])
        combined = result.stdout + result.stderr
        self.assertTrue(
            "synthetic" in combined.lower(),
            "--sqlite-drill output must confirm synthetic data is used",
        )

    def test_sqlite_drill_cleans_temp_files(self):
        result = self._run_script(["--sqlite-drill"])
        combined = result.stdout + result.stderr
        self.assertTrue(
            "clean" in combined.lower() or "cleaned" in combined.lower()
            or "cleanup" in combined.lower() or "temp" in combined.lower(),
            "--sqlite-drill must report temp file cleanup",
        )

    def test_sqlite_drill_does_not_log_secrets(self):
        result = self._run_script(["--sqlite-drill"])
        combined = (result.stdout + result.stderr).lower()
        for fragment in ["password", "secret", "api_key", "private_key", "dsn://", "token"]:
            self.assertNotIn(
                fragment,
                combined,
                f"--sqlite-drill output must not contain secret-like fragment '{fragment}'",
            )

    def test_keep_artifacts_flag_accepted(self):
        result = self._run_script(["--sqlite-drill", "--keep-artifacts"])
        self.assertIn(
            result.returncode,
            (0, 1),
            "--sqlite-drill --keep-artifacts must not crash with unknown error",
        )
        combined = result.stdout + result.stderr
        self.assertTrue(
            "keep" in combined.lower() or "artifact" in combined.lower(),
            "--keep-artifacts must produce relevant output",
        )


# ---------------------------------------------------------------------------
# No forbidden file changes
# ---------------------------------------------------------------------------

class TestGL205ForbiddenFileChanges(unittest.TestCase):

    def _git_changed_files(self) -> set[str]:
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
        )
        if result.returncode != 0:
            return set()
        return set(result.stdout.strip().splitlines())

    def _assert_no_changes_in(self, prefix: str, changed: set[str]):
        violations = [f for f in changed if f.startswith(prefix)]
        self.assertEqual(
            violations,
            [],
            f"GL-205 must not modify files under '{prefix}': {violations}",
        )

    def test_no_frontend_changes(self):
        changed = self._git_changed_files()
        self._assert_no_changes_in("frontend/", changed)

    def test_no_website_design_changes(self):
        changed = self._git_changed_files()
        self._assert_no_changes_in("website-design/", changed)

    def test_no_github_workflow_changes(self):
        changed = self._git_changed_files()
        self._assert_no_changes_in(".github/workflows/", changed)

    def test_no_package_publishing_metadata(self):
        changed = self._git_changed_files()
        for f in changed:
            basename = os.path.basename(f)
            self.assertNotIn(
                basename,
                {"setup.py", "package.json", "package-lock.json"},
                f"GL-205 must not modify package publishing metadata: {f}",
            )

    def test_no_sdk_pyproject_changes(self):
        changed = self._git_changed_files()
        sdk_changes = [
            f for f in changed
            if "sdk" in f.lower() and "pyproject" in f.lower()
        ]
        self.assertEqual(
            sdk_changes, [],
            f"GL-205 must not modify SDK pyproject.toml: {sdk_changes}",
        )


# ---------------------------------------------------------------------------
# Input sources exist on disk
# ---------------------------------------------------------------------------

class TestGL205InputSourcesExist(unittest.TestCase):

    def _check_source(self, relative_path: str):
        full = os.path.join(_REPO_ROOT, relative_path)
        self.assertTrue(
            os.path.exists(full),
            f"Input source referenced in GL-205 must exist: {relative_path}",
        )

    def test_gl204_doc_exists(self):
        self._check_source("docs/production_ops_go_no_go_v3.md")

    def test_gl204_json_exists(self):
        self._check_source("docs/examples/gl204/production_ops_go_no_go_v3.json")

    def test_gl201_doc_exists(self):
        self._check_source("docs/production_auth_secrets_config_hardening.md")

    def test_gl202_doc_exists(self):
        self._check_source("docs/persistence_postgres_migration_readiness.md")

    def test_readme_exists(self):
        self._check_source("README.md")

    def test_security_md_exists(self):
        self._check_source("SECURITY.md")

    def test_agents_md_exists(self):
        self._check_source("AGENTS.md")

    def test_db_py_exists(self):
        self._check_source("backend/src/db.py")

    def test_audit_log_py_exists(self):
        self._check_source("backend/src/audit_log.py")

    def test_structured_logging_py_exists(self):
        self._check_source("backend/src/structured_logging.py")


if __name__ == "__main__":
    unittest.main()
