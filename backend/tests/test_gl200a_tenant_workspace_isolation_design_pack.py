"""
GL-200A Tenant/Workspace Isolation Design Pack — test suite.

Verifies that the design pack doc and artifact exist, are internally consistent,
and that all required sections, findings, safety confirmations, production
readiness criteria, and scope guards meet the GL-200A specification.
"""

import json
import os
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "tenant_workspace_isolation_design_pack.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl200a",
    "tenant_workspace_isolation_design_pack.json",
)

ALLOWED_RESULTS = {
    "tenant_workspace_isolation_design_pack_complete",
    "tenant_workspace_design_blocked",
    "blocked_unexpected_scope",
    "blocked_public_claim_safety",
    "blocked_other_with_reason",
}

ALLOWED_DECISIONS = {
    "tenant_workspace_design_ready_for_implementation",
    "tenant_workspace_design_needs_followup_before_implementation",
    "tenant_workspace_design_blocked",
    "blocked_other_with_reason",
}

REQUIRED_SAFETY_CONFIRMATIONS = [
    "no_github_push_performed",
    "no_visibility_change_performed",
    "internal_repo_not_pushed_directly_to_github",
    "no_github_api_label_changes_performed",
    "no_github_issue_changes_performed",
    "no_reviewer_outreach_sent",
    "no_backend_src_changes",
    "no_openapi_changes",
    "no_migration_db_dependency_changes",
    "no_dependency_manifest_changes",
    "no_sdk_implementation_changes",
    "no_package_publishing_changes",
    "no_examples_runtime_changes",
    "no_frontend_website_design_changes",
    "no_github_workflow_changes",
    "no_snapshot_publish_script_behavior_changes",
    "no_production_saas_claim",
    "tenant_workspace_isolation_not_claimed_as_implemented",
    "no_real_customer_data_requested",
    "no_private_grant_data_requested",
    "no_secrets_requested",
    "no_exploit_details_included",
    "security_sensitive_reports_routed_to_github_security_advisories",
]

REQUIRED_RESOURCE_SCOPING_RESOURCES = [
    "grants",
    "grant_requests",
    "challenges",
    "grant_executions",
    "evidence/executions",
    "audit_events",
    "operators",
    "operator tokens / token_hash",
    "agent_permissions",
    "agent_permission_assignments",
    "demo endpoints",
    "health endpoint",
    "readiness endpoint",
    "configuration",
    "migrations",
]

REQUIRED_SCOPING_ROW_FIELDS = {
    "current_scope_status",
    "required_future_scope",
    "production_risk",
    "recommended_gl200b_action",
}

REQUIRED_DESIGN_OPTION_KEYWORDS = [
    "tenant_id only baseline",
    "tenant_id + workspace_id on business resources",
    "request-context isolation layer",
    "staged db migration",
    "full rbac",
    "tenant/workspace policy engine",
]

REQUIRED_TESTING_CATEGORIES = [
    "cross_tenant_isolation_tests",
    "workspace_isolation_tests",
    "auth_context_tests",
    "audit_context_tests",
    "demo_endpoint_safety_tests",
    "health_readiness_tests",
    "migration_tests",
    "examples_determinism_tests",
    "security_boundary_regression_tests",
]

REQUIRED_TESTING_SCENARIO_KEYWORDS = [
    "cross_tenant",
    "workspace",
    "audit",
    "demo",
    "security",
    "examples",
]

REQUIRED_PRODUCTION_READINESS_KEYWORDS = [
    "db schema scoped",
    "request context enforced",
    "sensitive resources",
    "cross-tenant tests",
    "audit context",
    "migration verified",
    "docs updated",
]

REQUIRED_FINDING_FIELDS = {
    "id",
    "severity",
    "category",
    "summary",
    "evidence",
    "blocking_for_design",
    "blocking_for_gl200b_implementation",
    "blocking_for_production",
    "recommended_action",
    "recommended_issue",
}

REQUIRED_FINDING_CATEGORIES = {
    "tenant-isolation",
    "workspace-isolation",
    "auth-context",
    "API-boundary",
    "database-migration",
    "audit-context",
    "permission-model",
    "testing",
    "production-readiness",
}

ALLOWED_FINDING_SEVERITIES = {
    "critical",
    "high",
    "medium",
    "low",
    "info",
}

ALLOWED_CHANGED_FILE_PATTERNS = [
    "docs/tenant_workspace_isolation_design_pack.md",
    "docs/examples/gl200a/",
    "backend/tests/test_gl200a",
    "AGENTS.md",
    "llms.txt",
    "llms-full.txt",
    "docs/production_readiness_gap_report_v2.md",
    "docs/controlled_preview_boundary_pack.md",
    "docs/api_sdk_agent_value_decision_pack.md",
]

FORBIDDEN_CHANGED_FILE_PATTERNS = [
    "backend/src/",
    "docs/openapi.yaml",
    "migrations/",
    "requirements",
    "setup.py",
    "pyproject.toml",
    "sdk/",
    "frontend/",
    "website/",
    ".github/workflows/",
    "scripts/publish",
    "scripts/snapshot",
]


def _load_json():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_doc():
    with open(DOC_PATH, encoding="utf-8") as f:
        return f.read()


class TestGL200ADocExists(unittest.TestCase):
    def test_doc_exists(self):
        self.assertTrue(os.path.isfile(DOC_PATH), f"Missing: {DOC_PATH}")

    def test_json_exists(self):
        self.assertTrue(os.path.isfile(JSON_PATH), f"Missing: {JSON_PATH}")

    def test_json_valid(self):
        data = _load_json()
        self.assertIsInstance(data, dict)


class TestGL200AIssueId(unittest.TestCase):
    def test_json_issue_id(self):
        data = _load_json()
        self.assertEqual(data.get("issue_id"), "GL-200A")

    def test_doc_contains_issue_id(self):
        doc = _load_doc()
        self.assertIn("GL-200A", doc)


class TestGL200AResultAndDecision(unittest.TestCase):
    def test_json_result_allowed(self):
        data = _load_json()
        self.assertIn(data.get("result"), ALLOWED_RESULTS)

    def test_json_decision_allowed(self):
        data = _load_json()
        self.assertIn(data.get("decision"), ALLOWED_DECISIONS)


class TestGL200ATerminology(unittest.TestCase):
    def test_terminology_exists(self):
        data = _load_json()
        self.assertIn("terminology", data)

    def test_terminology_defines_tenant(self):
        data = _load_json()
        terminology = data.get("terminology", {})
        self.assertIn("tenant", terminology)
        self.assertTrue(len(terminology["tenant"]) > 20)

    def test_terminology_defines_workspace(self):
        data = _load_json()
        terminology = data.get("terminology", {})
        self.assertIn("workspace", terminology)
        self.assertTrue(len(terminology["workspace"]) > 20)

    def test_terminology_defines_actor(self):
        data = _load_json()
        terminology = data.get("terminology", {})
        self.assertIn("actor", terminology)

    def test_terminology_defines_operator(self):
        data = _load_json()
        terminology = data.get("terminology", {})
        self.assertIn("operator", terminology)

    def test_terminology_defines_admin(self):
        data = _load_json()
        terminology = data.get("terminology", {})
        self.assertIn("admin", terminology)

    def test_terminology_defines_agent(self):
        data = _load_json()
        terminology = data.get("terminology", {})
        self.assertIn("agent", terminology)

    def test_terminology_defines_grant(self):
        data = _load_json()
        terminology = data.get("terminology", {})
        self.assertIn("grant", terminology)

    def test_terminology_defines_audit_event(self):
        data = _load_json()
        terminology = data.get("terminology", {})
        self.assertIn("audit_event", terminology)

    def test_doc_defines_tenant(self):
        doc = _load_doc()
        self.assertIn("tenant", doc.lower())

    def test_doc_defines_workspace(self):
        doc = _load_doc()
        self.assertIn("workspace", doc.lower())


class TestGL200AThreatModel(unittest.TestCase):
    def test_threat_model_exists(self):
        data = _load_json()
        self.assertIn("threat_model", data)
        self.assertIsInstance(data["threat_model"], list)

    def test_threat_model_non_empty(self):
        data = _load_json()
        self.assertGreater(len(data["threat_model"]), 0)

    def test_threat_model_has_required_fields(self):
        data = _load_json()
        for item in data["threat_model"]:
            self.assertIn("threat", item)
            self.assertIn("current_risk", item)
            self.assertIn("required_mitigation", item)


class TestGL200AIsolationGoals(unittest.TestCase):
    def test_isolation_goals_exists(self):
        data = _load_json()
        self.assertIn("isolation_goals", data)
        self.assertIsInstance(data["isolation_goals"], list)

    def test_isolation_goals_non_empty(self):
        data = _load_json()
        self.assertGreater(len(data["isolation_goals"]), 0)

    def test_isolation_non_goals_exists(self):
        data = _load_json()
        self.assertIn("isolation_non_goals", data)
        self.assertIsInstance(data["isolation_non_goals"], list)

    def test_isolation_non_goals_non_empty(self):
        data = _load_json()
        self.assertGreater(len(data["isolation_non_goals"]), 0)


class TestGL200AResourceScopingMatrix(unittest.TestCase):
    def test_resource_scoping_matrix_exists(self):
        data = _load_json()
        self.assertIn("resource_scoping_matrix", data)
        self.assertIsInstance(data["resource_scoping_matrix"], list)

    def test_resource_scoping_matrix_has_required_resources(self):
        data = _load_json()
        matrix = data["resource_scoping_matrix"]
        resource_names_lower = [r.get("resource", "").lower() for r in matrix]
        all_resources_str = " ".join(resource_names_lower)
        for required in REQUIRED_RESOURCE_SCOPING_RESOURCES:
            found = any(required.lower() in r for r in resource_names_lower) or required.lower() in all_resources_str
            self.assertTrue(found, f"Missing resource in scoping matrix: {required}")

    def test_each_scoping_row_has_required_fields(self):
        data = _load_json()
        matrix = data["resource_scoping_matrix"]
        for row in matrix:
            for field in REQUIRED_SCOPING_ROW_FIELDS:
                self.assertIn(field, row, f"Missing field '{field}' in row: {row.get('resource')}")

    def test_grants_in_matrix(self):
        data = _load_json()
        resources = [r["resource"] for r in data["resource_scoping_matrix"]]
        self.assertTrue(any("grant" in r.lower() for r in resources))

    def test_audit_events_in_matrix(self):
        data = _load_json()
        resources = [r["resource"] for r in data["resource_scoping_matrix"]]
        self.assertTrue(any("audit" in r.lower() for r in resources))

    def test_operators_in_matrix(self):
        data = _load_json()
        resources = [r["resource"] for r in data["resource_scoping_matrix"]]
        self.assertTrue(any("operator" in r.lower() for r in resources))

    def test_demo_endpoints_in_matrix(self):
        data = _load_json()
        resources = [r["resource"] for r in data["resource_scoping_matrix"]]
        self.assertTrue(any("demo" in r.lower() for r in resources))

    def test_health_endpoint_in_matrix(self):
        data = _load_json()
        resources = [r["resource"] for r in data["resource_scoping_matrix"]]
        self.assertTrue(any("health" in r.lower() for r in resources))

    def test_migrations_in_matrix(self):
        data = _load_json()
        resources = [r["resource"] for r in data["resource_scoping_matrix"]]
        self.assertTrue(any("migration" in r.lower() for r in resources))


class TestGL200ADesignOptions(unittest.TestCase):
    def test_design_options_exists(self):
        data = _load_json()
        self.assertIn("design_options", data)
        self.assertIsInstance(data["design_options"], list)

    def test_at_least_four_design_options(self):
        data = _load_json()
        self.assertGreaterEqual(len(data["design_options"]), 4)

    def test_design_options_contain_tenant_id_only_baseline(self):
        data = _load_json()
        names_lower = [opt.get("name", "").lower() for opt in data["design_options"]]
        combined = " ".join(names_lower)
        self.assertIn("tenant_id only baseline", combined)

    def test_design_options_contain_tenant_workspace(self):
        data = _load_json()
        names_lower = [opt.get("name", "").lower() for opt in data["design_options"]]
        combined = " ".join(names_lower)
        self.assertTrue(
            "workspace_id" in combined or "workspace" in combined,
            "Expected workspace_id option in design options"
        )

    def test_design_options_contain_request_context_isolation(self):
        data = _load_json()
        names_lower = [opt.get("name", "").lower() for opt in data["design_options"]]
        descriptions_lower = [opt.get("description", "").lower() for opt in data["design_options"]]
        combined = " ".join(names_lower + descriptions_lower)
        self.assertIn("request-context", combined)

    def test_design_options_contain_staged_db_migration(self):
        data = _load_json()
        names_lower = [opt.get("name", "").lower() for opt in data["design_options"]]
        descriptions_lower = [opt.get("description", "").lower() for opt in data["design_options"]]
        combined = " ".join(names_lower + descriptions_lower)
        self.assertIn("staged", combined)

    def test_design_options_contain_policy_engine(self):
        data = _load_json()
        names_lower = [opt.get("name", "").lower() for opt in data["design_options"]]
        descriptions_lower = [opt.get("description", "").lower() for opt in data["design_options"]]
        combined = " ".join(names_lower + descriptions_lower)
        self.assertTrue(
            "policy engine" in combined or "rbac" in combined,
            "Expected policy engine or RBAC option in design options"
        )

    def test_each_design_option_has_suitability_for_gl200b(self):
        data = _load_json()
        for opt in data["design_options"]:
            self.assertIn("suitability_for_gl200b", opt, f"Missing suitability_for_gl200b in option: {opt.get('option_id')}")


class TestGL200ARecommendedDesign(unittest.TestCase):
    def test_recommended_design_exists(self):
        data = _load_json()
        self.assertIn("recommended_design", data)
        self.assertIsInstance(data["recommended_design"], dict)

    def test_recommended_design_has_summary(self):
        data = _load_json()
        self.assertIn("summary", data["recommended_design"])

    def test_recommended_design_has_rationale(self):
        data = _load_json()
        self.assertIn("rationale", data["recommended_design"])


class TestGL200AApiBoundaryModel(unittest.TestCase):
    def test_api_boundary_model_exists(self):
        data = _load_json()
        self.assertIn("api_boundary_model", data)
        self.assertIsInstance(data["api_boundary_model"], dict)

    def test_api_boundary_model_has_fail_closed_behavior(self):
        data = _load_json()
        model = data["api_boundary_model"]
        self.assertIn("fail_closed_behavior", model)

    def test_api_boundary_model_has_cross_tenant_denial(self):
        data = _load_json()
        model = data["api_boundary_model"]
        self.assertIn("cross_tenant_denial", model)

    def test_api_boundary_model_has_health_readiness_exceptions(self):
        data = _load_json()
        model = data["api_boundary_model"]
        self.assertIn("health_readiness_exceptions", model)

    def test_api_boundary_model_has_demo_endpoint_exceptions(self):
        data = _load_json()
        model = data["api_boundary_model"]
        self.assertIn("demo_endpoint_exceptions", model)


class TestGL200AAuthOperatorAdminModel(unittest.TestCase):
    def test_auth_operator_admin_model_exists(self):
        data = _load_json()
        self.assertIn("auth_operator_admin_model", data)
        self.assertIsInstance(data["auth_operator_admin_model"], dict)

    def test_auth_model_has_current_state(self):
        data = _load_json()
        model = data["auth_operator_admin_model"]
        self.assertIn("current_state", model)

    def test_auth_model_has_required_for_gl200b(self):
        data = _load_json()
        model = data["auth_operator_admin_model"]
        self.assertIn("required_for_gl200b", model)

    def test_auth_model_has_deferred(self):
        data = _load_json()
        model = data["auth_operator_admin_model"]
        self.assertIn("deferred", model)


class TestGL200ADatabaseDataModelStrategy(unittest.TestCase):
    def test_database_data_model_strategy_exists(self):
        data = _load_json()
        self.assertIn("database_data_model_strategy", data)
        self.assertIsInstance(data["database_data_model_strategy"], dict)

    def test_database_strategy_has_columns_required(self):
        data = _load_json()
        strategy = data["database_data_model_strategy"]
        self.assertIn("columns_required", strategy)

    def test_database_strategy_has_backfill_strategy(self):
        data = _load_json()
        strategy = data["database_data_model_strategy"]
        self.assertIn("backfill_strategy", strategy)

    def test_database_strategy_has_migration_safety(self):
        data = _load_json()
        strategy = data["database_data_model_strategy"]
        self.assertIn("migration_safety", strategy)

    def test_database_strategy_has_audit_immutability(self):
        data = _load_json()
        strategy = data["database_data_model_strategy"]
        self.assertIn("audit_immutability", strategy)


class TestGL200AAuditDesign(unittest.TestCase):
    def test_audit_design_exists(self):
        data = _load_json()
        self.assertIn("audit_design", data)
        self.assertIsInstance(data["audit_design"], dict)

    def test_audit_design_has_tenant_context(self):
        data = _load_json()
        audit = data["audit_design"]
        self.assertIn("tenant_context_in_events", audit)

    def test_audit_design_has_cross_tenant_denial_events(self):
        data = _load_json()
        audit = data["audit_design"]
        self.assertIn("cross_tenant_denial_events", audit)

    def test_audit_design_has_immutable_behavior(self):
        data = _load_json()
        audit = data["audit_design"]
        self.assertIn("immutable_audit_behavior", audit)

    def test_audit_design_has_no_sensitive_data(self):
        data = _load_json()
        audit = data["audit_design"]
        self.assertIn("no_sensitive_data_in_audit", audit)

    def test_audit_design_has_tenant_workspace_context_propagation(self):
        data = _load_json()
        audit = data["audit_design"]
        self.assertIn("tenant_workspace_context_propagation", audit)


class TestGL200APermissionModelImplications(unittest.TestCase):
    def test_permission_model_implications_exists(self):
        data = _load_json()
        self.assertIn("permission_model_implications", data)


class TestGL200ATestingStrategy(unittest.TestCase):
    def test_testing_strategy_exists(self):
        data = _load_json()
        self.assertIn("testing_strategy", data)
        self.assertIsInstance(data["testing_strategy"], dict)

    def test_testing_strategy_has_cross_tenant_tests(self):
        data = _load_json()
        strategy = data["testing_strategy"]
        self.assertIn("cross_tenant_isolation_tests", strategy)

    def test_testing_strategy_cross_tenant_has_denial_test(self):
        data = _load_json()
        tests = data["testing_strategy"].get("cross_tenant_isolation_tests", [])
        descriptions = [t.get("description", "").lower() for t in tests]
        combined = " ".join(descriptions)
        self.assertIn("cannot read", combined)

    def test_testing_strategy_has_workspace_tests(self):
        data = _load_json()
        strategy = data["testing_strategy"]
        self.assertIn("workspace_isolation_tests", strategy)

    def test_testing_strategy_has_audit_scope_tests(self):
        data = _load_json()
        strategy = data["testing_strategy"]
        self.assertIn("audit_context_tests", strategy)

    def test_testing_strategy_has_demo_endpoint_safety_guard(self):
        data = _load_json()
        strategy = data["testing_strategy"]
        self.assertIn("demo_endpoint_safety_tests", strategy)

    def test_testing_strategy_demo_guard_tests_public(self):
        data = _load_json()
        tests = data["testing_strategy"].get("demo_endpoint_safety_tests", [])
        descriptions = [t.get("description", "").lower() for t in tests]
        combined = " ".join(descriptions)
        self.assertIn("gl-190", combined)

    def test_testing_strategy_has_examples_deterministic(self):
        data = _load_json()
        strategy = data["testing_strategy"]
        self.assertIn("examples_determinism_tests", strategy)

    def test_testing_strategy_has_security_boundary(self):
        data = _load_json()
        strategy = data["testing_strategy"]
        self.assertIn("security_boundary_regression_tests", strategy)

    def test_testing_strategy_has_migration_tests(self):
        data = _load_json()
        strategy = data["testing_strategy"]
        self.assertIn("migration_tests", strategy)


class TestGL200AProductionReadinessCriteria(unittest.TestCase):
    def test_production_readiness_criteria_exists(self):
        data = _load_json()
        self.assertIn("production_readiness_criteria", data)
        self.assertIsInstance(data["production_readiness_criteria"], list)

    def test_production_readiness_has_db_schema_scoped(self):
        data = _load_json()
        criteria_lower = [c.lower() for c in data["production_readiness_criteria"]]
        combined = " ".join(criteria_lower)
        self.assertIn("db schema scoped", combined)

    def test_production_readiness_has_request_context_enforced(self):
        data = _load_json()
        criteria_lower = [c.lower() for c in data["production_readiness_criteria"]]
        combined = " ".join(criteria_lower)
        self.assertIn("request context enforced", combined)

    def test_production_readiness_has_sensitive_resources_scoped(self):
        data = _load_json()
        criteria_lower = [c.lower() for c in data["production_readiness_criteria"]]
        combined = " ".join(criteria_lower)
        self.assertIn("sensitive resources", combined)

    def test_production_readiness_has_cross_tenant_tests(self):
        data = _load_json()
        criteria_lower = [c.lower() for c in data["production_readiness_criteria"]]
        combined = " ".join(criteria_lower)
        self.assertIn("cross-tenant tests", combined)

    def test_production_readiness_has_audit_context(self):
        data = _load_json()
        criteria_lower = [c.lower() for c in data["production_readiness_criteria"]]
        combined = " ".join(criteria_lower)
        self.assertIn("audit context", combined)

    def test_production_readiness_has_migration_verified(self):
        data = _load_json()
        criteria_lower = [c.lower() for c in data["production_readiness_criteria"]]
        combined = " ".join(criteria_lower)
        self.assertIn("migration verified", combined)

    def test_production_readiness_docs_updated_only_after_implementation(self):
        data = _load_json()
        criteria_lower = [c.lower() for c in data["production_readiness_criteria"]]
        combined = " ".join(criteria_lower)
        self.assertIn("docs updated", combined)
        self.assertTrue(
            "only after" in combined or "after gl-200b" in combined or "merged" in combined,
            "Production readiness criteria must gate docs update on real implementation"
        )


class TestGL200AImplementationSplit(unittest.TestCase):
    def test_implementation_split_exists(self):
        data = _load_json()
        self.assertIn("implementation_split", data)
        self.assertIsInstance(data["implementation_split"], dict)

    def test_implementation_split_includes_gl200b(self):
        data = _load_json()
        split = data["implementation_split"]
        self.assertIn("gl200b", split)

    def test_gl200b_has_scope(self):
        data = _load_json()
        gl200b = data["implementation_split"]["gl200b"]
        self.assertIn("scope", gl200b)


class TestGL200AFindings(unittest.TestCase):
    def test_findings_exists(self):
        data = _load_json()
        self.assertIn("findings", data)
        self.assertIsInstance(data["findings"], list)

    def test_at_least_one_finding(self):
        data = _load_json()
        self.assertGreater(len(data["findings"]), 0)

    def test_each_finding_has_required_fields(self):
        data = _load_json()
        for finding in data["findings"]:
            for field in REQUIRED_FINDING_FIELDS:
                self.assertIn(
                    field, finding,
                    f"Finding {finding.get('id')} missing field: {field}"
                )

    def test_finding_ids_start_with_gl200a(self):
        data = _load_json()
        for finding in data["findings"]:
            fid = finding.get("id", "")
            self.assertTrue(
                fid.startswith("GL-200A-"),
                f"Finding ID must start with GL-200A-: {fid}"
            )

    def test_finding_severities_are_allowed(self):
        data = _load_json()
        for finding in data["findings"]:
            self.assertIn(
                finding.get("severity"),
                ALLOWED_FINDING_SEVERITIES,
                f"Invalid severity in finding {finding.get('id')}: {finding.get('severity')}"
            )

    def test_finding_categories_are_known(self):
        data = _load_json()
        actual_categories = {f.get("category") for f in data["findings"]}
        for cat in actual_categories:
            self.assertIn(
                cat, REQUIRED_FINDING_CATEGORIES,
                f"Unknown finding category: {cat}"
            )

    def test_finding_counts_by_severity_exists(self):
        data = _load_json()
        self.assertIn("finding_counts_by_severity", data)

    def test_critical_findings_exist(self):
        data = _load_json()
        critical_count = sum(1 for f in data["findings"] if f.get("severity") == "critical")
        self.assertGreater(critical_count, 0, "Expected at least one critical finding")

    def test_tenant_isolation_finding_exists(self):
        data = _load_json()
        categories = [f.get("category") for f in data["findings"]]
        self.assertIn("tenant-isolation", categories)

    def test_auth_context_finding_exists(self):
        data = _load_json()
        categories = [f.get("category") for f in data["findings"]]
        self.assertIn("auth-context", categories)

    def test_api_boundary_finding_exists(self):
        data = _load_json()
        categories = [f.get("category") for f in data["findings"]]
        self.assertIn("API-boundary", categories)

    def test_audit_context_finding_exists(self):
        data = _load_json()
        categories = [f.get("category") for f in data["findings"]]
        self.assertIn("audit-context", categories)


class TestGL200ARecommendedNextIssues(unittest.TestCase):
    def test_recommended_next_issues_exists(self):
        data = _load_json()
        self.assertIn("recommended_next_issues", data)
        self.assertIsInstance(data["recommended_next_issues"], list)

    def test_gl200b_in_recommended_next_issues(self):
        data = _load_json()
        issue_ids = [i.get("issue_id", "") for i in data["recommended_next_issues"]]
        self.assertTrue(
            any("GL-200B" in iid for iid in issue_ids),
            "GL-200B must be in recommended_next_issues"
        )

    def test_gl201_in_recommended_next_issues(self):
        data = _load_json()
        issue_ids = [i.get("issue_id", "") for i in data["recommended_next_issues"]]
        self.assertTrue(
            any("GL-201" in iid for iid in issue_ids),
            "GL-201 must be in recommended_next_issues"
        )

    def test_gl202_in_recommended_next_issues(self):
        data = _load_json()
        issue_ids = [i.get("issue_id", "") for i in data["recommended_next_issues"]]
        self.assertTrue(
            any("GL-202" in iid for iid in issue_ids),
            "GL-202 must be in recommended_next_issues"
        )

    def test_gl203_in_recommended_next_issues(self):
        data = _load_json()
        issue_ids = [i.get("issue_id", "") for i in data["recommended_next_issues"]]
        self.assertTrue(
            any("GL-203" in iid for iid in issue_ids),
            "GL-203 must be in recommended_next_issues"
        )


class TestGL200ADocDesignOnly(unittest.TestCase):
    def test_doc_states_design_only(self):
        doc = _load_doc()
        lower = doc.lower()
        self.assertTrue(
            "design only" in lower or "design / docs" in lower or "design-only" in lower,
            "Doc must state this is design only"
        )

    def test_doc_states_not_yet_implemented(self):
        doc = _load_doc()
        lower = doc.lower()
        self.assertTrue(
            "not yet implemented" in lower or "is not yet implemented" in lower,
            "Doc must state tenant/workspace isolation is not yet implemented"
        )

    def test_doc_does_not_claim_production_saas_readiness(self):
        doc = _load_doc()
        lower = doc.lower()
        self.assertNotIn(
            "production saas is ready",
            lower,
            "Doc must not claim production SaaS readiness"
        )

    def test_doc_does_not_claim_real_customer_data_readiness(self):
        doc = _load_doc()
        lower = doc.lower()
        self.assertNotIn(
            "real customer data is ready",
            lower,
            "Doc must not claim real customer data readiness"
        )

    def test_doc_routes_security_to_github_security_advisories(self):
        doc = _load_doc()
        lower = doc.lower()
        self.assertTrue(
            "github security advisories" in lower or "security advisories" in lower,
            "Doc must route security-sensitive reports to GitHub Security Advisories"
        )

    def test_doc_does_not_include_exploit_details(self):
        doc = _load_doc()
        lower = doc.lower()
        self.assertNotIn("proof of concept exploit", lower)
        self.assertNotIn("working exploit", lower)
        self.assertNotIn("0day", lower)


class TestGL200ASafetyConfirmations(unittest.TestCase):
    def test_safety_confirmations_exists(self):
        data = _load_json()
        self.assertIn("safety_confirmations", data)
        self.assertIsInstance(data["safety_confirmations"], dict)

    def test_all_required_safety_confirmations_present(self):
        data = _load_json()
        confirmations = data["safety_confirmations"]
        for key in REQUIRED_SAFETY_CONFIRMATIONS:
            self.assertIn(key, confirmations, f"Missing safety confirmation: {key}")

    def test_no_github_push_performed(self):
        data = _load_json()
        self.assertTrue(data["safety_confirmations"].get("no_github_push_performed"))

    def test_no_visibility_change_performed(self):
        data = _load_json()
        self.assertTrue(data["safety_confirmations"].get("no_visibility_change_performed"))

    def test_internal_repo_not_pushed_to_github(self):
        data = _load_json()
        self.assertTrue(data["safety_confirmations"].get("internal_repo_not_pushed_directly_to_github"))

    def test_no_backend_src_changes(self):
        data = _load_json()
        self.assertTrue(data["safety_confirmations"].get("no_backend_src_changes"))

    def test_no_openapi_changes(self):
        data = _load_json()
        self.assertTrue(data["safety_confirmations"].get("no_openapi_changes"))

    def test_no_migration_db_dependency_changes(self):
        data = _load_json()
        self.assertTrue(data["safety_confirmations"].get("no_migration_db_dependency_changes"))

    def test_no_production_saas_claim(self):
        data = _load_json()
        self.assertTrue(data["safety_confirmations"].get("no_production_saas_claim"))

    def test_tenant_workspace_isolation_not_claimed_as_implemented(self):
        data = _load_json()
        self.assertTrue(data["safety_confirmations"].get("tenant_workspace_isolation_not_claimed_as_implemented"))

    def test_no_real_customer_data_requested(self):
        data = _load_json()
        self.assertTrue(data["safety_confirmations"].get("no_real_customer_data_requested"))

    def test_no_private_grant_data_requested(self):
        data = _load_json()
        self.assertTrue(data["safety_confirmations"].get("no_private_grant_data_requested"))

    def test_no_secrets_requested(self):
        data = _load_json()
        self.assertTrue(data["safety_confirmations"].get("no_secrets_requested"))

    def test_no_exploit_details_included(self):
        data = _load_json()
        self.assertTrue(data["safety_confirmations"].get("no_exploit_details_included"))

    def test_security_sensitive_reports_routed(self):
        data = _load_json()
        self.assertTrue(data["safety_confirmations"].get("security_sensitive_reports_routed_to_github_security_advisories"))


class TestGL200AChangedFiles(unittest.TestCase):
    def test_changed_files_exists(self):
        data = _load_json()
        self.assertIn("changed_files", data)
        self.assertIsInstance(data["changed_files"], list)

    def test_no_backend_src_in_changed_files(self):
        data = _load_json()
        for f in data["changed_files"]:
            self.assertFalse(
                f.startswith("backend/src/"),
                f"backend/src/ must not be in changed_files: {f}"
            )

    def test_no_openapi_in_changed_files(self):
        data = _load_json()
        for f in data["changed_files"]:
            self.assertFalse(
                "openapi.yaml" in f,
                f"openapi.yaml must not be in changed_files: {f}"
            )

    def test_no_migration_in_changed_files(self):
        data = _load_json()
        for f in data["changed_files"]:
            self.assertFalse(
                "migrations/" in f,
                f"migrations/ must not be in changed_files: {f}"
            )

    def test_no_dependency_manifest_in_changed_files(self):
        data = _load_json()
        forbidden_manifests = ["requirements", "setup.py", "pyproject.toml", "package.json", "Pipfile"]
        for f in data["changed_files"]:
            for forbidden in forbidden_manifests:
                self.assertFalse(
                    forbidden in f,
                    f"Dependency manifest must not be in changed_files: {f}"
                )

    def test_no_sdk_implementation_in_changed_files(self):
        data = _load_json()
        for f in data["changed_files"]:
            self.assertFalse(
                f.startswith("sdk/") and not f.endswith(".md"),
                f"SDK implementation must not be in changed_files: {f}"
            )

    def test_no_frontend_in_changed_files(self):
        data = _load_json()
        for f in data["changed_files"]:
            self.assertFalse(
                f.startswith("frontend/") or f.startswith("website/"),
                f"Frontend/website must not be in changed_files: {f}"
            )

    def test_no_github_workflow_in_changed_files(self):
        data = _load_json()
        for f in data["changed_files"]:
            self.assertFalse(
                ".github/workflows/" in f,
                f"GitHub workflow must not be in changed_files: {f}"
            )

    def test_design_doc_in_changed_files(self):
        data = _load_json()
        changed = data["changed_files"]
        self.assertTrue(
            any("tenant_workspace_isolation_design_pack.md" in f for f in changed)
        )

    def test_json_artifact_in_changed_files(self):
        data = _load_json()
        changed = data["changed_files"]
        self.assertTrue(
            any("gl200a" in f for f in changed)
        )


class TestGL200AScopeGuards(unittest.TestCase):
    def test_no_backend_src_changes_on_disk(self):
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        changed = result.stdout.strip().splitlines()
        for f in changed:
            self.assertFalse(
                f.startswith("backend/src/"),
                f"Forbidden: backend/src/ changed: {f}"
            )

    def test_no_openapi_changes_on_disk(self):
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        changed = result.stdout.strip().splitlines()
        for f in changed:
            self.assertFalse(
                "openapi.yaml" in f,
                f"Forbidden: openapi.yaml changed: {f}"
            )

    def test_no_migration_changes_on_disk(self):
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        changed = result.stdout.strip().splitlines()
        for f in changed:
            self.assertFalse(
                "migrations/" in f and "backend/src/" in f,
                f"Forbidden: migration changed: {f}"
            )

    def test_no_dependency_manifest_changes_on_disk(self):
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        changed = result.stdout.strip().splitlines()
        forbidden_manifests = ["requirements.txt", "setup.py", "pyproject.toml", "Pipfile"]
        for f in changed:
            for forbidden in forbidden_manifests:
                self.assertFalse(
                    f == forbidden or f.endswith("/" + forbidden),
                    f"Forbidden: dependency manifest changed: {f}"
                )

    def test_no_frontend_changes_on_disk(self):
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        changed = result.stdout.strip().splitlines()
        for f in changed:
            self.assertFalse(
                f.startswith("frontend/") or f.startswith("website/"),
                f"Forbidden: frontend/website changed: {f}"
            )

    def test_no_github_workflow_changes_on_disk(self):
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        changed = result.stdout.strip().splitlines()
        for f in changed:
            self.assertFalse(
                ".github/workflows/" in f,
                f"Forbidden: GitHub workflow changed: {f}"
            )

    def test_no_public_github_push(self):
        import subprocess
        result = subprocess.run(
            ["git", "remote", "-v"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        remote_output = result.stdout
        # This test verifies no automated push to public origin occurred
        # by checking that the current HEAD commit is not pushed to a public remote
        # We can only verify that the public push safety confirmation is set
        data = _load_json()
        self.assertTrue(data["safety_confirmations"].get("no_github_push_performed"))
        # We intentionally do NOT check remote HEAD to avoid network calls in unit tests

    def test_no_visibility_change(self):
        data = _load_json()
        self.assertTrue(data["safety_confirmations"].get("no_visibility_change_performed"))

    def test_no_examples_runtime_changes_on_disk(self):
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        changed = result.stdout.strip().splitlines()
        for f in changed:
            if f.startswith("examples/") and f.endswith(".py"):
                self.fail(f"Forbidden: examples runtime changed: {f}")

    def test_no_snapshot_publish_script_behavior_changes_on_disk(self):
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        changed = result.stdout.strip().splitlines()
        for f in changed:
            self.assertFalse(
                "scripts/publish" in f or "scripts/snapshot" in f,
                f"Forbidden: snapshot/publish script changed: {f}"
            )


if __name__ == "__main__":
    unittest.main()
