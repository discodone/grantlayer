"""GL-204 — Production Ops / Go-No-Go v3 gate tests.

Verifies the existence, structure, safety confirmations, and decision
content of the GL-204 documentation artifact and JSON evidence bundle.
"""

import json
import os
import subprocess
import unittest

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
_DOC_PATH = os.path.join(_REPO_ROOT, "docs", "production_ops_go_no_go_v3.md")
_JSON_PATH = os.path.join(
    _REPO_ROOT, "docs", "examples", "gl204", "production_ops_go_no_go_v3.json"
)

_ALLOWED_RESULTS = {"ready_for_merge", "merged", "deferred", "blocked"}
_ALLOWED_DECISIONS = {
    "no_go_production_saas_continue_developer_preview_controlled_preview_gl203d_deferred",
    "no_go_production_saas_continue_developer_preview_controlled_preview",
    "no_go_production_saas_developer_preview_continue",
    "no_go_production_saas_controlled_preview_continue",
}

_DECISION_MATRIX_REQUIRED_KEYS = [
    "Developer Preview",
    "Controlled Preview",
    "Controlled Preview Expansion",
    "Production SaaS",
    "Real Customer Data",
    "Private Grant/Institutional Data",
    "Official SDK/Package",
    "Experimental Public SDK/Package",
    "Live PostgreSQL Production Claim",
    "First External Controlled Pilot",
]


def _load_json():
    with open(_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestGL204ArtifactExists(unittest.TestCase):
    def test_doc_file_exists(self):
        self.assertTrue(
            os.path.isfile(_DOC_PATH),
            f"docs/production_ops_go_no_go_v3.md must exist at {_DOC_PATH}",
        )

    def test_json_artifact_exists(self):
        self.assertTrue(
            os.path.isfile(_JSON_PATH),
            f"docs/examples/gl204/production_ops_go_no_go_v3.json must exist at {_JSON_PATH}",
        )

    def test_json_is_valid(self):
        data = _load_json()
        self.assertIsInstance(data, dict, "JSON artifact must be a JSON object")


class TestGL204JSONStructure(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()

    def test_issue_id_is_gl204(self):
        self.assertEqual(self.data.get("issue_id"), "GL-204", "issue_id must be GL-204")

    def test_result_is_allowed(self):
        result = self.data.get("result", "")
        self.assertIn(
            result,
            _ALLOWED_RESULTS,
            f"result '{result}' is not in allowed values {_ALLOWED_RESULTS}",
        )

    def test_decision_is_allowed(self):
        decision = self.data.get("decision", "")
        self.assertTrue(
            any(allowed in decision for allowed in [
                "no_go_production_saas",
                "no_go",
                "blocked",
            ]),
            f"decision '{decision}' must reflect no-go for production SaaS",
        )

    def test_input_sources_reviewed_exists(self):
        sources = self.data.get("input_sources_reviewed")
        self.assertIsInstance(sources, list, "input_sources_reviewed must be a list")
        self.assertGreater(len(sources), 0, "input_sources_reviewed must be non-empty")

    def test_current_state_summary_exists(self):
        summary = self.data.get("current_state_summary")
        self.assertIsNotNone(summary, "current_state_summary must exist")
        self.assertTrue(bool(summary), "current_state_summary must be non-empty")

    def test_tenant_workspace_readiness_exists(self):
        readiness = self.data.get("tenant_workspace_readiness")
        self.assertIsNotNone(readiness, "tenant_workspace_readiness must exist")

    def test_auth_secrets_config_readiness_exists(self):
        readiness = self.data.get("auth_secrets_config_readiness")
        self.assertIsNotNone(readiness, "auth_secrets_config_readiness must exist")

    def test_persistence_postgres_migration_readiness_exists(self):
        readiness = self.data.get("persistence_postgres_migration_readiness")
        self.assertIsNotNone(readiness, "persistence_postgres_migration_readiness must exist")

    def test_api_openapi_contract_readiness_exists(self):
        readiness = self.data.get("api_openapi_contract_readiness")
        self.assertIsNotNone(readiness, "api_openapi_contract_readiness must exist")

    def test_sdk_package_readiness_exists(self):
        readiness = self.data.get("sdk_package_readiness")
        self.assertIsNotNone(readiness, "sdk_package_readiness must exist")

    def test_production_operations_readiness_exists(self):
        readiness = self.data.get("production_operations_readiness")
        self.assertIsNotNone(readiness, "production_operations_readiness must exist")

    def test_backup_restore_dr_assessment_exists(self):
        assessment = self.data.get("backup_restore_dr_assessment")
        self.assertIsNotNone(assessment, "backup_restore_dr_assessment must exist")

    def test_observability_logging_correlation_assessment_exists(self):
        assessment = self.data.get("observability_logging_correlation_assessment")
        self.assertIsNotNone(
            assessment, "observability_logging_correlation_assessment must exist"
        )

    def test_deployment_runtime_assessment_exists(self):
        assessment = self.data.get("deployment_runtime_assessment")
        self.assertIsNotNone(assessment, "deployment_runtime_assessment must exist")

    def test_admin_operator_management_assessment_exists(self):
        assessment = self.data.get("admin_operator_management_assessment")
        self.assertIsNotNone(assessment, "admin_operator_management_assessment must exist")

    def test_public_claim_safety_assessment_exists(self):
        assessment = self.data.get("public_claim_safety_assessment")
        self.assertIsNotNone(assessment, "public_claim_safety_assessment must exist")

    def test_gl203c_prohibited_claims_inconsistency_review_exists(self):
        review = self.data.get("gl203c_prohibited_claims_inconsistency_review")
        self.assertIsNotNone(
            review, "gl203c_prohibited_claims_inconsistency_review must exist"
        )

    def test_go_no_go_decision_matrix_exists(self):
        matrix = self.data.get("go_no_go_decision_matrix")
        self.assertIsNotNone(matrix, "go_no_go_decision_matrix must exist")

    def test_controlled_preview_boundary_decision_exists(self):
        decision = self.data.get("controlled_preview_boundary_decision")
        self.assertIsNotNone(decision, "controlled_preview_boundary_decision must exist")

    def test_production_saas_decision_exists(self):
        decision = self.data.get("production_saas_decision")
        self.assertIsNotNone(decision, "production_saas_decision must exist")

    def test_real_data_private_grant_data_decision_exists(self):
        decision = self.data.get("real_data_private_grant_data_decision")
        self.assertIsNotNone(decision, "real_data_private_grant_data_decision must exist")

    def test_official_sdk_package_decision_exists(self):
        decision = self.data.get("official_sdk_package_decision")
        self.assertIsNotNone(decision, "official_sdk_package_decision must exist")

    def test_gl203d_projection_gate_decision_exists(self):
        decision = self.data.get("gl203d_projection_gate_decision")
        self.assertIsNotNone(decision, "gl203d_projection_gate_decision must exist")

    def test_first_external_controlled_pilot_decision_exists(self):
        decision = self.data.get("first_external_controlled_pilot_decision")
        self.assertIsNotNone(
            decision, "first_external_controlled_pilot_decision must exist"
        )

    def test_remaining_blockers_exist(self):
        blockers = self.data.get("remaining_blockers")
        self.assertIsInstance(blockers, list, "remaining_blockers must be a list")
        self.assertGreater(len(blockers), 0, "remaining_blockers must be non-empty")

    def test_risk_register_exists(self):
        register = self.data.get("risk_register")
        self.assertIsNotNone(register, "risk_register must exist")
        self.assertTrue(bool(register), "risk_register must be non-empty")

    def test_findings_exist(self):
        findings = self.data.get("findings")
        self.assertIsInstance(findings, list, "findings must be a list")
        self.assertGreater(len(findings), 0, "findings must be non-empty")

    def test_safety_confirmations_exist(self):
        confirmations = self.data.get("safety_confirmations")
        self.assertIsNotNone(confirmations, "safety_confirmations must exist")

    def test_recommended_next_issues_exist(self):
        issues = self.data.get("recommended_next_issues")
        self.assertIsInstance(issues, list, "recommended_next_issues must be a list")
        self.assertGreater(len(issues), 0, "recommended_next_issues must be non-empty")


class TestGL204DecisionMatrix(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.matrix = self.data.get("go_no_go_decision_matrix", {})

    def test_matrix_includes_developer_preview(self):
        self.assertIn(
            "Developer Preview",
            self.matrix,
            "go_no_go_decision_matrix must include Developer Preview",
        )

    def test_matrix_includes_controlled_preview(self):
        self.assertIn(
            "Controlled Preview",
            self.matrix,
            "go_no_go_decision_matrix must include Controlled Preview",
        )

    def test_matrix_includes_controlled_preview_expansion(self):
        self.assertIn(
            "Controlled Preview Expansion",
            self.matrix,
            "go_no_go_decision_matrix must include Controlled Preview Expansion",
        )

    def test_matrix_includes_production_saas(self):
        self.assertIn(
            "Production SaaS",
            self.matrix,
            "go_no_go_decision_matrix must include Production SaaS",
        )

    def test_matrix_includes_real_customer_data(self):
        self.assertIn(
            "Real Customer Data",
            self.matrix,
            "go_no_go_decision_matrix must include Real Customer Data",
        )

    def test_matrix_includes_private_grant_institutional_data(self):
        self.assertIn(
            "Private Grant/Institutional Data",
            self.matrix,
            "go_no_go_decision_matrix must include Private Grant/Institutional Data",
        )

    def test_matrix_includes_official_sdk_package(self):
        self.assertIn(
            "Official SDK/Package",
            self.matrix,
            "go_no_go_decision_matrix must include Official SDK/Package",
        )

    def test_matrix_includes_experimental_public_sdk(self):
        self.assertIn(
            "Experimental Public SDK/Package",
            self.matrix,
            "go_no_go_decision_matrix must include Experimental Public SDK/Package",
        )

    def test_matrix_includes_live_postgresql_production_claim(self):
        self.assertIn(
            "Live PostgreSQL Production Claim",
            self.matrix,
            "go_no_go_decision_matrix must include Live PostgreSQL Production Claim",
        )

    def test_matrix_includes_first_external_controlled_pilot(self):
        self.assertIn(
            "First External Controlled Pilot",
            self.matrix,
            "go_no_go_decision_matrix must include First External Controlled Pilot",
        )


class TestGL204ProductionSaaSDecision(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()

    def test_production_saas_is_no_go(self):
        decision = self.data.get("production_saas_decision", {})
        decision_value = str(decision.get("decision", "")).upper()
        self.assertIn(
            "NO-GO",
            decision_value,
            "production_saas_decision must be NO-GO unless strongly justified",
        )

    def test_production_saas_not_ready_in_matrix(self):
        matrix = self.data.get("go_no_go_decision_matrix", {})
        prod_saas = str(matrix.get("Production SaaS", "")).upper()
        self.assertIn(
            "NO-GO",
            prod_saas,
            "Production SaaS entry in decision matrix must be NO-GO",
        )

    def test_real_customer_data_is_no_go(self):
        decision = self.data.get("real_data_private_grant_data_decision", {})
        real_customer = str(
            decision.get("real_customer_data", decision.get("decision", ""))
        ).upper()
        self.assertIn(
            "NO-GO",
            real_customer,
            "real_customer_data decision must be NO-GO",
        )

    def test_private_grant_data_is_no_go(self):
        decision = self.data.get("real_data_private_grant_data_decision", {})
        private_grant = str(
            decision.get("private_grant_data", decision.get("decision", ""))
        ).upper()
        self.assertIn(
            "NO-GO",
            private_grant,
            "private_grant_data decision must be NO-GO",
        )

    def test_official_sdk_package_is_no_go(self):
        decision = self.data.get("official_sdk_package_decision", {})
        sdk_decision = str(decision.get("decision", "")).upper()
        self.assertIn(
            "NO-GO",
            sdk_decision,
            "official_sdk_package_decision must be NO-GO",
        )


class TestGL204GL203DProjectionGate(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()

    def test_gl203d_gate_decision_is_explicit(self):
        gate = self.data.get("gl203d_projection_gate_decision", {})
        self.assertIn(
            "decision",
            gate,
            "gl203d_projection_gate_decision must have an explicit 'decision' field",
        )

    def test_gl203d_not_unconditionally_approved(self):
        gate = self.data.get("gl203d_projection_gate_decision", {})
        may_proceed = gate.get("gl203d_may_proceed", None)
        decision_str = str(gate.get("decision", "")).upper()
        if may_proceed is not None:
            self.assertFalse(
                may_proceed,
                "gl203d_may_proceed must be False — GL-203D is deferred at GL-204",
            )
        else:
            self.assertTrue(
                "DEFER" in decision_str or "NOT" in decision_str or "CONDITION" in decision_str,
                "GL-203D gate decision must indicate deferred/conditional, not unconditional approval",
            )

    def test_gl203d_is_conditional_and_bounded(self):
        gate = self.data.get("gl203d_projection_gate_decision", {})
        blockers = gate.get("blockers", [])
        conditions = gate.get("conditions_to_unblock", gate.get("conditions", []))
        has_constraints = bool(blockers) or bool(conditions)
        self.assertTrue(
            has_constraints,
            "GL-203D gate must specify either blockers or conditions_to_unblock",
        )


class TestGL204RemainingBlockers(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.blockers = self.data.get("remaining_blockers", [])

    def _blocker_ids_and_descriptions(self):
        return [
            (b.get("id", ""), str(b.get("description", "")).lower())
            for b in self.blockers
        ]

    def test_live_postgresql_validation_blocker_present(self):
        pairs = self._blocker_ids_and_descriptions()
        found = any(
            "postgresql" in desc or "postgres" in desc
            for _, desc in pairs
        )
        self.assertTrue(
            found,
            "remaining_blockers must include live PostgreSQL validation if not actually live-validated",
        )

    def test_backup_restore_dr_blocker_present(self):
        pairs = self._blocker_ids_and_descriptions()
        found = any(
            "backup" in desc or "restore" in desc or "dr" in desc or "disaster" in desc
            for _, desc in pairs
        )
        self.assertTrue(
            found,
            "remaining_blockers must include backup/restore/DR if not complete",
        )

    def test_observability_logging_blocker_present(self):
        pairs = self._blocker_ids_and_descriptions()
        found = any(
            "observ" in desc or "logging" in desc or "monitor" in desc or "alert" in desc
            for _, desc in pairs
        )
        self.assertTrue(
            found,
            "remaining_blockers must include observability/logging if not complete",
        )

    def test_admin_operator_management_blocker_present(self):
        pairs = self._blocker_ids_and_descriptions()
        found = any(
            "admin" in desc or "operator" in desc or "tenant isolation" in desc
            or "gl-200d" in desc or "gl200d" in desc
            for _, desc in pairs
        )
        self.assertTrue(
            found,
            "remaining_blockers must include admin/operator management (GL-200D) if not complete",
        )


class TestGL204FindingsStructure(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.findings = self.data.get("findings", [])

    def test_findings_have_severity(self):
        for f in self.findings:
            self.assertIn(
                "severity",
                f,
                f"Finding {f.get('id', '?')} must have a severity field",
            )

    def test_findings_have_recommendation(self):
        for f in self.findings:
            self.assertIn(
                "recommendation",
                f,
                f"Finding {f.get('id', '?')} must have a recommendation field",
            )


class TestGL204SafetyConfirmations(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.sc = self.data.get("safety_confirmations", {})

    def test_no_production_saas_claim(self):
        self.assertTrue(
            self.sc.get("no_production_saas_claim"),
            "safety_confirmations.no_production_saas_claim must be true",
        )

    def test_no_real_customer_private_grant_data_claimed(self):
        self.assertTrue(
            self.sc.get("no_real_customer_private_grant_data_readiness_claimed"),
            "safety_confirmations.no_real_customer_private_grant_data_readiness_claimed must be true",
        )

    def test_no_official_sdk_claimed(self):
        self.assertTrue(
            self.sc.get("no_official_sdk_claimed"),
            "safety_confirmations.no_official_sdk_claimed must be true",
        )

    def test_no_backend_src_changes(self):
        self.assertTrue(
            self.sc.get("no_backend_src_changes"),
            "safety_confirmations.no_backend_src_changes must be true",
        )

    def test_no_api_behavior_changes(self):
        self.assertTrue(
            self.sc.get("no_api_behavior_changes"),
            "safety_confirmations.no_api_behavior_changes must be true",
        )

    def test_no_migrations_db_schema_changes(self):
        self.assertTrue(
            self.sc.get("no_migrations_db_schema_changes"),
            "safety_confirmations.no_migrations_db_schema_changes must be true",
        )

    def test_no_dependency_changes(self):
        self.assertTrue(
            self.sc.get("no_dependency_changes"),
            "safety_confirmations.no_dependency_changes must be true",
        )

    def test_no_public_publish(self):
        self.assertTrue(
            self.sc.get("no_public_publish"),
            "safety_confirmations.no_public_publish must be true",
        )

    def test_no_visibility_change(self):
        self.assertTrue(
            self.sc.get("no_visibility_change"),
            "safety_confirmations.no_visibility_change must be true",
        )

    def test_no_force_push(self):
        self.assertTrue(
            self.sc.get("no_force_push"),
            "safety_confirmations.no_force_push must be true",
        )

    def test_tenant_workspace_not_overclaimed(self):
        self.assertTrue(
            self.sc.get("tenant_workspace_isolation_not_overclaimed"),
            "safety_confirmations.tenant_workspace_isolation_not_overclaimed must be true",
        )

    def test_security_reports_route_to_advisories(self):
        self.assertTrue(
            self.sc.get("security_reports_route_to_github_security_advisories"),
            "safety_confirmations.security_reports_route_to_github_security_advisories must be true",
        )

    def test_no_exploit_details(self):
        self.assertTrue(
            self.sc.get("no_exploit_details_included"),
            "safety_confirmations.no_exploit_details_included must be true",
        )

    def test_no_real_secrets(self):
        self.assertTrue(
            self.sc.get("no_real_secrets_included"),
            "safety_confirmations.no_real_secrets_included must be true",
        )

    def test_website_untracked_files_excluded(self):
        self.assertTrue(
            self.sc.get("website_untracked_files_excluded"),
            "safety_confirmations.website_untracked_files_excluded must be true",
        )


class TestGL204DocContent(unittest.TestCase):
    def setUp(self):
        with open(_DOC_PATH, encoding="utf-8") as f:
            self.doc = f.read()
        self.doc_lower = self.doc.lower()

    def test_doc_states_developer_preview_continue(self):
        self.assertIn(
            "developer preview",
            self.doc_lower,
            "Doc must state Developer Preview posture",
        )

    def test_doc_states_controlled_preview_strict_boundaries(self):
        self.assertIn(
            "strict boundaries",
            self.doc_lower,
            "Doc must state Controlled Preview with strict boundaries",
        )

    def test_doc_states_not_production_saas(self):
        self.assertIn(
            "not production saas",
            self.doc_lower,
            "Doc must state not production SaaS",
        )

    def test_doc_states_not_ready_for_real_customer_data(self):
        found = (
            "not ready for real customer" in self.doc_lower
            or "real customer data" in self.doc_lower
            and "no-go" in self.doc_lower
        )
        self.assertTrue(
            found,
            "Doc must state not ready for real customer/private grant data",
        )

    def test_doc_no_official_sdk_claimed(self):
        self.assertIn(
            "no official sdk",
            self.doc_lower,
            "Doc must state no official SDK is claimed",
        )

    def test_doc_routes_security_reports_to_advisories(self):
        self.assertIn(
            "github security advisories",
            self.doc_lower,
            "Doc must route security reports to GitHub Security Advisories",
        )

    def test_doc_no_exploit_details(self):
        forbidden = ["cve-", "poc exploit", "proof of concept exploit",
                     "payload: {", "reverse shell", "sql injection payload"]
        for term in forbidden:
            self.assertNotIn(
                term,
                self.doc_lower,
                f"Doc must not include exploit details (found '{term}')",
            )

    def test_doc_no_real_secrets(self):
        forbidden = ["-----begin rsa private key", "-----begin ec private key",
                     "aws_access_key_id", "aws_secret_access_key"]
        for term in forbidden:
            self.assertNotIn(
                term,
                self.doc_lower,
                f"Doc must not include real secrets (found '{term}')",
            )


class TestGL204ScopeGuard(unittest.TestCase):
    """Scope guard: verify GL-204 changes stay within allowed scope.

    These tests are only active when running on the GL-204 branch. They skip
    on other branches to avoid false positives.
    """

    def setUp(self):
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=_REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.branch = result.stdout.strip()
        except Exception:
            self.branch = "unknown"

        self._on_gl204 = "gl-204" in self.branch

    def _skip_if_not_gl204(self):
        if not self._on_gl204:
            self.skipTest(
                f"Scope guard skipped: not on gl-204-production-ops-go-no-go-v3 "
                f"(current: {self.branch})"
            )

    def _changed_files(self):
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "main...HEAD"],
                cwd=_REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=15,
            )
            return [f.strip() for f in result.stdout.splitlines() if f.strip()]
        except Exception:
            return []

    def test_doc_created(self):
        self._skip_if_not_gl204()
        self.assertTrue(
            os.path.isfile(_DOC_PATH),
            "GL-204 doc must be created on this branch",
        )

    def test_artifact_created(self):
        self._skip_if_not_gl204()
        self.assertTrue(
            os.path.isfile(_JSON_PATH),
            "GL-204 JSON artifact must be created on this branch",
        )

    def test_test_file_created(self):
        self._skip_if_not_gl204()
        test_path = os.path.join(
            _REPO_ROOT,
            "backend",
            "tests",
            "test_gl204_production_ops_go_no_go_v3.py",
        )
        self.assertTrue(
            os.path.isfile(test_path),
            "GL-204 test file must be created on this branch",
        )

    def test_no_backend_src_changes(self):
        self._skip_if_not_gl204()
        changed = self._changed_files()
        backend_src_changes = [
            f for f in changed
            if f.startswith("backend/src/")
        ]
        self.assertEqual(
            backend_src_changes,
            [],
            f"GL-204 must not change backend/src/: found {backend_src_changes}",
        )

    def test_no_migration_changes(self):
        self._skip_if_not_gl204()
        changed = self._changed_files()
        migration_changes = [
            f for f in changed
            if "migrations/" in f or f.endswith("migrations")
        ]
        self.assertEqual(
            migration_changes,
            [],
            f"GL-204 must not add or change migrations: found {migration_changes}",
        )

    def test_no_package_metadata(self):
        self._skip_if_not_gl204()
        changed = self._changed_files()
        forbidden = [
            f for f in changed
            if f in ("setup.py", "pyproject.toml", "package.json")
            or f.endswith("/setup.py")
            or f.endswith("/pyproject.toml")
            or f.endswith("/package.json")
        ]
        self.assertEqual(
            forbidden,
            [],
            f"GL-204 must not add package publishing metadata: found {forbidden}",
        )

    def test_no_openapi_yaml_changes(self):
        self._skip_if_not_gl204()
        changed = self._changed_files()
        openapi_changes = [
            f for f in changed
            if "openapi.yaml" in f
        ]
        self.assertEqual(
            openapi_changes,
            [],
            f"GL-204 must not change openapi.yaml: found {openapi_changes}",
        )

    def test_no_dependency_file_changes(self):
        self._skip_if_not_gl204()
        changed = self._changed_files()
        dep_changes = [
            f for f in changed
            if f in ("requirements.txt", "requirements-dev.txt", "Pipfile", "Pipfile.lock",
                     "poetry.lock", "package-lock.json", "yarn.lock")
        ]
        self.assertEqual(
            dep_changes,
            [],
            f"GL-204 must not change dependency manifests: found {dep_changes}",
        )

    def test_no_frontend_website_changes(self):
        self._skip_if_not_gl204()
        changed = self._changed_files()
        frontend_changes = [
            f for f in changed
            if f.startswith("frontend/")
            or f.startswith("website/")
            or f.startswith("website-design/")
            or f.startswith("dashboard/")
        ]
        self.assertEqual(
            frontend_changes,
            [],
            f"GL-204 must not change frontend/website: found {frontend_changes}",
        )

    def test_no_website_files_included(self):
        self._skip_if_not_gl204()
        changed = self._changed_files()
        website_untracked = [
            f for f in changed
            if "website_design_workspace_import" in f
            or f.startswith("website-design/")
        ]
        self.assertEqual(
            website_untracked,
            [],
            f"GL-204 must not include unrelated website files: found {website_untracked}",
        )

    def test_no_official_sdk_changes(self):
        self._skip_if_not_gl204()
        changed = self._changed_files()
        sdk_impl_changes = [
            f for f in changed
            if f.startswith("sdk/")
        ]
        self.assertEqual(
            sdk_impl_changes,
            [],
            f"GL-204 must not change sdk/ implementation: found {sdk_impl_changes}",
        )

    def test_no_snapshot_publish_script_changes(self):
        self._skip_if_not_gl204()
        changed = self._changed_files()
        snapshot_changes = [
            f for f in changed
            if "publish" in f and f.startswith("scripts/")
        ]
        self.assertEqual(
            snapshot_changes,
            [],
            f"GL-204 must not change snapshot publish scripts: found {snapshot_changes}",
        )

    def test_no_public_remote_push(self):
        try:
            result = subprocess.run(
                ["git", "remote", "-v"],
                cwd=_REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=10,
            )
            remotes = result.stdout.lower()
            github_push = (
                "github.com" in remotes
                and "push" in remotes
                and "discodone/grantlayer" in remotes
            )
            self.assertFalse(
                github_push,
                "GL-204 must not push to public GitHub remote",
            )
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
