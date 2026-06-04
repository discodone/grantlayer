"""
GL-199 Production Readiness Gap Report v2 — test suite.

Verifies that the gap report doc and artifact exist, are internally consistent,
and that all required readiness dimensions, findings, blockers, go/no-go
decisions, safety confirmations, and roadmap items meet the GL-199 specification.
"""

import json
import os
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "production_readiness_gap_report_v2.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl199",
    "production_readiness_gap_report_v2.json",
)

ALLOWED_RESULTS = {
    "production_readiness_gap_report_v2_complete",
    "production_readiness_review_blocked",
    "blocked_unexpected_scope",
    "blocked_public_claim_safety",
    "blocked_other_with_reason",
}

ALLOWED_DEVELOPER_PREVIEW_DECISIONS = {
    "developer_preview_continue",
    "developer_preview_pause_pending_fixes",
    "developer_preview_blocked",
}

ALLOWED_CONTROLLED_PREVIEW_DECISIONS = {
    "controlled_preview_continue_with_strict_boundaries",
    "controlled_preview_docs_only_until_fixes",
    "controlled_preview_blocked",
}

ALLOWED_PRODUCTION_SAAS_DECISIONS = {
    "production_saas_not_ready",
    "production_saas_blocked",
    "production_saas_ready_with_caveats",
    "production_saas_ready",
}

REQUIRED_READINESS_DIMENSIONS = [
    "public developer preview",
    "controlled preview boundary",
    "production SaaS",
    "tenant/workspace isolation",
    "auth and token handling",
    "production secrets/configuration",
    "persistence/database/Postgres readiness",
    "audit immutability/tamper evidence",
    "API contract/OpenAPI completeness",
    "SDK/package maturity",
    "agent workflow readiness",
    "demo endpoint safety",
    "data privacy/customer data readiness",
    "private grant/institutional data readiness",
    "observability/logging",
    "deployment/ops",
    "backup/restore/DR",
    "rate limiting/abuse prevention",
    "CORS/public exposure",
    "security reporting",
    "public claim consistency",
    "test suite health",
    "public snapshot safety",
]

REQUIRED_DIMENSION_FIELDS = {
    "status",
    "severity",
    "rationale",
    "evidence",
    "recommended_action",
    "recommended_issue",
}

ALLOWED_DIMENSION_STATUSES = {
    "ready",
    "ready_with_cautions",
    "needs_followup",
    "blocked",
    "not_ready",
}

ALLOWED_DIMENSION_SEVERITIES = {
    "critical",
    "high",
    "medium",
    "low",
    "info",
}

REQUIRED_FINDING_FIELDS = {
    "id",
    "severity",
    "category",
    "summary",
    "evidence",
    "blocking_for_developer_preview",
    "blocking_for_controlled_preview",
    "blocking_for_production",
    "recommended_action",
    "recommended_issue",
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
    "tenant_isolation_not_claimed",
    "official_sdk_package_not_claimed_unless_verified",
    "no_real_customer_data_requested",
    "no_private_grant_data_requested",
    "no_secrets_requested",
    "no_exploit_details_included",
    "security_sensitive_reports_routed_to_github_security_advisories",
]

REQUIRED_PRODUCTION_BLOCKER_NAMES_FRAGMENTS = [
    "tenant",
    "production saas",
]

REQUIRED_GO_NO_GO_KEYS = [
    "Developer Preview",
    "Controlled Preview",
    "Production SaaS",
    "Real customer data",
    "Private grant/institutional data",
    "Official SDK/package claim",
]

REQUIRED_ROADMAP_CATEGORIES = [
    "tenant",
    "production auth",
    "persistence",
    "API contract",
    "SDK",
    "controlled reviewer",
    "test-suite scope-guard",
    "production deployment",
]

FORBIDDEN_FILE_PREFIXES = [
    "backend/src/",
    "docs/openapi.yaml",
]

FORBIDDEN_MIGRATION_PATTERNS = [
    "migrations/",
    "schema.sql",
]


class TestGL199ProductionReadinessGapReportV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(JSON_PATH, encoding="utf-8") as f:
            cls.data = json.load(f)
        with open(DOC_PATH, encoding="utf-8") as f:
            cls.doc = f.read()

    # -------------------------------------------------------------------------
    # File existence
    # -------------------------------------------------------------------------

    def test_doc_exists(self):
        self.assertTrue(os.path.isfile(DOC_PATH), f"Missing: {DOC_PATH}")

    def test_json_exists(self):
        self.assertTrue(os.path.isfile(JSON_PATH), f"Missing: {JSON_PATH}")

    def test_json_valid(self):
        self.assertIsInstance(self.data, dict)

    # -------------------------------------------------------------------------
    # Issue ID and result
    # -------------------------------------------------------------------------

    def test_issue_id(self):
        self.assertEqual(self.data["issue_id"], "GL-199")

    def test_result_allowed(self):
        self.assertIn(self.data["result"], ALLOWED_RESULTS)

    # -------------------------------------------------------------------------
    # Decisions
    # -------------------------------------------------------------------------

    def test_decisions_exist(self):
        self.assertIn("decisions", self.data)

    def test_developer_preview_decision_present(self):
        self.assertIn("developer_preview_decision", self.data["decisions"])

    def test_developer_preview_decision_allowed(self):
        self.assertIn(
            self.data["decisions"]["developer_preview_decision"],
            ALLOWED_DEVELOPER_PREVIEW_DECISIONS,
        )

    def test_controlled_preview_decision_present(self):
        self.assertIn("controlled_preview_decision", self.data["decisions"])

    def test_controlled_preview_decision_allowed(self):
        self.assertIn(
            self.data["decisions"]["controlled_preview_decision"],
            ALLOWED_CONTROLLED_PREVIEW_DECISIONS,
        )

    def test_production_saas_decision_present(self):
        self.assertIn("production_saas_decision", self.data["decisions"])

    def test_production_saas_decision_allowed(self):
        self.assertIn(
            self.data["decisions"]["production_saas_decision"],
            ALLOWED_PRODUCTION_SAAS_DECISIONS,
        )

    # -------------------------------------------------------------------------
    # Readiness dimensions
    # -------------------------------------------------------------------------

    def test_readiness_dimensions_exist(self):
        self.assertIn("readiness_dimensions", self.data)
        self.assertIsInstance(self.data["readiness_dimensions"], list)
        self.assertGreater(len(self.data["readiness_dimensions"]), 0)

    def test_all_required_dimensions_present(self):
        dimension_names = {d["name"] for d in self.data["readiness_dimensions"]}
        for required in REQUIRED_READINESS_DIMENSIONS:
            self.assertIn(
                required,
                dimension_names,
                f"Missing required readiness dimension: '{required}'",
            )

    def test_each_dimension_has_required_fields(self):
        for dim in self.data["readiness_dimensions"]:
            for field in REQUIRED_DIMENSION_FIELDS:
                self.assertIn(
                    field,
                    dim,
                    f"Dimension '{dim.get('name', '?')}' missing field '{field}'",
                )

    def test_each_dimension_status_is_allowed(self):
        for dim in self.data["readiness_dimensions"]:
            self.assertIn(
                dim["status"],
                ALLOWED_DIMENSION_STATUSES,
                f"Dimension '{dim.get('name', '?')}' has invalid status '{dim['status']}'",
            )

    def test_each_dimension_severity_is_allowed(self):
        for dim in self.data["readiness_dimensions"]:
            self.assertIn(
                dim["severity"],
                ALLOWED_DIMENSION_SEVERITIES,
                f"Dimension '{dim.get('name', '?')}' has invalid severity '{dim['severity']}'",
            )

    # -------------------------------------------------------------------------
    # Findings
    # -------------------------------------------------------------------------

    def test_findings_exist(self):
        self.assertIn("findings", self.data)
        self.assertIsInstance(self.data["findings"], list)
        self.assertGreater(len(self.data["findings"]), 0)

    def test_each_finding_has_required_fields(self):
        for finding in self.data["findings"]:
            for field in REQUIRED_FINDING_FIELDS:
                self.assertIn(
                    field,
                    finding,
                    f"Finding '{finding.get('id', '?')}' missing field '{field}'",
                )

    def test_each_finding_id_starts_with_gl199(self):
        for finding in self.data["findings"]:
            self.assertTrue(
                finding["id"].startswith("GL-199-F"),
                f"Finding id '{finding['id']}' does not start with 'GL-199-F'",
            )

    def test_each_finding_blocking_fields_are_bool(self):
        for finding in self.data["findings"]:
            for field in (
                "blocking_for_developer_preview",
                "blocking_for_controlled_preview",
                "blocking_for_production",
            ):
                self.assertIsInstance(
                    finding[field],
                    bool,
                    f"Finding '{finding['id']}' field '{field}' must be bool",
                )

    # -------------------------------------------------------------------------
    # Production blockers
    # -------------------------------------------------------------------------

    def test_production_blockers_exist(self):
        self.assertIn("production_blockers", self.data)
        self.assertIsInstance(self.data["production_blockers"], list)
        self.assertGreater(len(self.data["production_blockers"]), 0)

    def test_production_blockers_include_tenant_isolation(self):
        blocker_names = " ".join(
            b.get("name", "").lower() for b in self.data["production_blockers"]
        )
        self.assertIn(
            "tenant",
            blocker_names,
            "Production blockers must include a tenant/workspace isolation blocker",
        )

    def test_production_blockers_include_production_saas(self):
        # The production SaaS not-ready posture should be reflected: check that
        # either a production-saas or auth/deployment blocker exists.
        blocker_names = " ".join(
            b.get("name", "").lower() for b in self.data["production_blockers"]
        )
        saas_related = any(
            term in blocker_names
            for term in ["production auth", "production saas", "deployment", "secret"]
        )
        self.assertTrue(
            saas_related,
            "Production blockers must include production SaaS readiness blocker (auth, deployment, or secret management)",
        )

    # -------------------------------------------------------------------------
    # Go/No-Go
    # -------------------------------------------------------------------------

    def test_go_no_go_exists(self):
        self.assertIn("go_no_go", self.data)

    def test_go_no_go_includes_required_keys(self):
        for key in REQUIRED_GO_NO_GO_KEYS:
            self.assertIn(
                key,
                self.data["go_no_go"],
                f"go_no_go missing key '{key}'",
            )

    def test_production_saas_is_no_go(self):
        verdict = self.data["go_no_go"].get("Production SaaS", "").lower()
        self.assertIn(
            "no",
            verdict,
            "Production SaaS go/no-go must be no-go",
        )

    def test_real_customer_data_is_no_go(self):
        verdict = self.data["go_no_go"].get("Real customer data", "").lower()
        self.assertIn(
            "no",
            verdict,
            "Real customer data go/no-go must be no-go",
        )

    def test_private_grant_institutional_data_is_no_go(self):
        verdict = self.data["go_no_go"].get(
            "Private grant/institutional data", ""
        ).lower()
        self.assertIn(
            "no",
            verdict,
            "Private grant/institutional data go/no-go must be no-go",
        )

    # -------------------------------------------------------------------------
    # Recommended post-GL-199 roadmap
    # -------------------------------------------------------------------------

    def test_recommended_roadmap_exists(self):
        self.assertIn("recommended_post_gl199_roadmap", self.data)
        self.assertIsInstance(self.data["recommended_post_gl199_roadmap"], list)
        self.assertGreater(len(self.data["recommended_post_gl199_roadmap"]), 0)

    def test_recommended_roadmap_covers_required_categories(self):
        roadmap_text = json.dumps(self.data["recommended_post_gl199_roadmap"]).lower()
        for category_fragment in REQUIRED_ROADMAP_CATEGORIES:
            self.assertIn(
                category_fragment.lower(),
                roadmap_text,
                f"Roadmap must cover '{category_fragment}'",
            )

    # -------------------------------------------------------------------------
    # Doc content checks
    # -------------------------------------------------------------------------

    def test_doc_states_developer_preview(self):
        doc_lower = self.doc.lower()
        self.assertTrue(
            "developer preview" in doc_lower or "technical preview" in doc_lower,
            "Doc must state Developer Preview / technical preview",
        )

    def test_doc_states_not_production_saas(self):
        doc_lower = self.doc.lower()
        self.assertIn(
            "not production saas",
            doc_lower,
            "Doc must state 'not production saas'",
        )

    def test_doc_states_tenant_isolation_not_implemented(self):
        doc_lower = self.doc.lower()
        self.assertIn(
            "tenant isolation is not implemented",
            doc_lower,
            "Doc must state 'tenant isolation is not implemented'",
        )

    def test_doc_states_no_real_secrets_customer_data(self):
        doc_lower = self.doc.lower()
        self.assertTrue(
            "no real secrets" in doc_lower or "no real customer data" in doc_lower,
            "Doc must state no real secrets / no real customer data",
        )

    def test_doc_states_official_sdk_not_claimed(self):
        doc_lower = self.doc.lower()
        self.assertTrue(
            "official sdk" in doc_lower or "no pip package" in doc_lower,
            "Doc must address official SDK/package not claimed",
        )

    def test_doc_routes_security_to_advisories(self):
        doc_lower = self.doc.lower()
        self.assertIn(
            "github security advisories",
            doc_lower,
            "Doc must route security-sensitive reports to GitHub Security Advisories",
        )

    def test_doc_excludes_exploit_details(self):
        doc_lower = self.doc.lower()
        exploit_phrases = [
            "proof-of-concept exploit",
            "bypass payload",
            "exploit code",
            "reproduction steps for cve",
        ]
        for phrase in exploit_phrases:
            self.assertNotIn(
                phrase,
                doc_lower,
                f"Doc must not include exploit details: found '{phrase}'",
            )

    # -------------------------------------------------------------------------
    # Safety confirmations
    # -------------------------------------------------------------------------

    def test_safety_confirmations_exist(self):
        self.assertIn("safety_confirmations", self.data)

    def test_safety_confirmations_include_required(self):
        confirmations = self.data["safety_confirmations"]
        for key in REQUIRED_SAFETY_CONFIRMATIONS:
            self.assertIn(
                key,
                confirmations,
                f"safety_confirmations missing key '{key}'",
            )

    def test_no_github_push_confirmed(self):
        self.assertTrue(
            self.data["safety_confirmations"]["no_github_push_performed"],
            "no_github_push_performed must be true",
        )

    def test_no_visibility_change_confirmed(self):
        self.assertTrue(
            self.data["safety_confirmations"]["no_visibility_change_performed"],
            "no_visibility_change_performed must be true",
        )

    def test_no_backend_src_changes_confirmed(self):
        self.assertTrue(
            self.data["safety_confirmations"]["no_backend_src_changes"],
            "no_backend_src_changes must be true",
        )

    def test_no_openapi_changes_confirmed(self):
        self.assertTrue(
            self.data["safety_confirmations"]["no_openapi_changes"],
            "no_openapi_changes must be true",
        )

    def test_no_sdk_implementation_changes_confirmed(self):
        self.assertTrue(
            self.data["safety_confirmations"]["no_sdk_implementation_changes"],
            "no_sdk_implementation_changes must be true",
        )

    def test_no_package_publishing_changes_confirmed(self):
        self.assertTrue(
            self.data["safety_confirmations"]["no_package_publishing_changes"],
            "no_package_publishing_changes must be true",
        )

    def test_no_production_saas_claim_confirmed(self):
        self.assertTrue(
            self.data["safety_confirmations"]["no_production_saas_claim"],
            "no_production_saas_claim must be true",
        )

    def test_tenant_isolation_not_claimed_confirmed(self):
        self.assertTrue(
            self.data["safety_confirmations"]["tenant_isolation_not_claimed"],
            "tenant_isolation_not_claimed must be true",
        )

    # -------------------------------------------------------------------------
    # Changed files scope
    # -------------------------------------------------------------------------

    def test_changed_files_exist_in_artifact(self):
        self.assertIn("changed_files", self.data)
        self.assertIsInstance(self.data["changed_files"], list)

    def test_no_backend_src_in_changed_files(self):
        for f in self.data["changed_files"]:
            self.assertFalse(
                f.startswith("backend/src/"),
                f"changed_files must not include backend/src/ changes: found '{f}'",
            )

    def test_no_openapi_in_changed_files(self):
        for f in self.data["changed_files"]:
            self.assertNotEqual(
                f,
                "docs/openapi.yaml",
                "changed_files must not include OpenAPI changes",
            )

    def test_no_migration_in_changed_files(self):
        for f in self.data["changed_files"]:
            for pattern in FORBIDDEN_MIGRATION_PATTERNS:
                self.assertNotIn(
                    pattern,
                    f,
                    f"changed_files must not include migration changes: found '{f}'",
                )

    def test_no_github_workflow_in_changed_files(self):
        for f in self.data["changed_files"]:
            self.assertFalse(
                f.startswith(".github/workflows/"),
                f"changed_files must not include GitHub workflow changes: found '{f}'",
            )

    def test_changed_files_within_allowed_scope(self):
        allowed_prefixes = (
            "docs/",
            "backend/tests/",
        )
        for f in self.data["changed_files"]:
            self.assertTrue(
                any(f.startswith(p) for p in allowed_prefixes),
                f"changed_file '{f}' is outside allowed scope (docs/ or backend/tests/)",
            )

    # -------------------------------------------------------------------------
    # Additional structural checks
    # -------------------------------------------------------------------------

    def test_executive_summary_present(self):
        self.assertIn("executive_summary", self.data)
        self.assertGreater(len(self.data["executive_summary"]), 10)

    def test_readiness_classification_present(self):
        self.assertIn("readiness_classification", self.data)

    def test_finding_counts_by_severity_present(self):
        self.assertIn("finding_counts_by_severity", self.data)

    def test_non_goals_present(self):
        self.assertIn("non_goals", self.data)
        self.assertIsInstance(self.data["non_goals"], list)

    def test_next_recommended_step_present(self):
        self.assertIn("next_recommended_step", self.data)

    def test_tests_field_present(self):
        self.assertIn("tests", self.data)


if __name__ == "__main__":
    unittest.main()
