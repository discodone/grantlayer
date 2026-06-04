"""
GL-198 Controlled Preview Boundary Pack — test suite.

Verifies that the boundary pack doc and artifact exist, are internally
consistent, and that the controlled preview boundary definitions meet all
required criteria from the GL-198 issue specification.
"""

import json
import os
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "controlled_preview_boundary_pack.md")
JSON_PATH = os.path.join(
    REPO_ROOT, "docs", "examples", "gl198", "controlled_preview_boundary_pack.json"
)

ALLOWED_RESULTS = {
    "controlled_preview_boundary_pack_complete",
    "controlled_preview_blocked_pending_safety_fixes",
    "blocked_unexpected_scope",
    "blocked_public_claim_safety",
    "blocked_other_with_reason",
}

ALLOWED_DECISIONS = {
    "controlled_preview_allowed_with_strict_boundaries",
    "controlled_preview_allowed_docs_only_until_followups",
    "controlled_preview_blocked_pending_safety_fixes",
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
    "tenant_isolation_not_claimed",
    "official_sdk_package_not_claimed_unless_verified",
    "no_real_customer_data_requested",
    "no_private_grant_data_requested",
    "no_secrets_requested",
    "no_exploit_details_included",
    "security_sensitive_reports_routed_to_github_security_advisories",
]


class TestGL198BoundaryPackExists(unittest.TestCase):
    def test_doc_exists(self):
        self.assertTrue(
            os.path.exists(DOC_PATH),
            f"docs/controlled_preview_boundary_pack.md not found at {DOC_PATH}",
        )

    def test_json_exists(self):
        self.assertTrue(
            os.path.exists(JSON_PATH),
            f"docs/examples/gl198/controlled_preview_boundary_pack.json not found at {JSON_PATH}",
        )

    def test_json_is_valid(self):
        with open(JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)

    def test_json_issue_id(self):
        with open(JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["issue_id"], "GL-198")

    def test_json_result_is_allowed(self):
        with open(JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn(data["result"], ALLOWED_RESULTS)

    def test_json_decision_is_allowed(self):
        with open(JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn(data["decision"], ALLOWED_DECISIONS)


class TestGL198InputSources(unittest.TestCase):
    def setUp(self):
        with open(JSON_PATH, encoding="utf-8") as f:
            self.data = json.load(f)
        self.sources = self.data.get("input_sources_reviewed", [])

    def test_readme_reviewed(self):
        self.assertTrue(
            any("README.md" in s for s in self.sources),
            "README.md not in input_sources_reviewed",
        )

    def test_security_md_reviewed(self):
        self.assertTrue(
            any("SECURITY.md" in s for s in self.sources),
            "SECURITY.md not in input_sources_reviewed",
        )

    def test_agents_md_reviewed(self):
        self.assertTrue(
            any("AGENTS.md" in s for s in self.sources),
            "AGENTS.md not in input_sources_reviewed",
        )

    def test_llms_txt_reviewed(self):
        self.assertTrue(
            any("llms.txt" in s or "llms-full.txt" in s for s in self.sources),
            "Neither llms.txt nor llms-full.txt in input_sources_reviewed",
        )

    def test_gl190_reviewed(self):
        self.assertTrue(
            any("gl190" in s.lower() or "demo_endpoint_safety_guard" in s.lower() for s in self.sources),
            "GL-190 or demo_endpoint_safety_guard not in input_sources_reviewed",
        )

    def test_gl197_reviewed(self):
        self.assertTrue(
            any("gl197" in s.lower() or "api_sdk_agent_value_decision_pack" in s.lower() for s in self.sources),
            "GL-197 or api_sdk_agent_value_decision_pack not in input_sources_reviewed",
        )

    def test_gl196_reviewed(self):
        self.assertTrue(
            any("gl196" in s.lower() or "public_smoke_matrix_pack" in s.lower() for s in self.sources),
            "GL-196 or public_smoke_matrix_pack not in input_sources_reviewed",
        )

    def test_gl195_reviewed(self):
        self.assertTrue(
            any("gl195" in s.lower() or "public_safety_scanner" in s.lower() for s in self.sources),
            "GL-195 or public_safety_scanner not in input_sources_reviewed",
        )

    def test_gl194_reviewed(self):
        self.assertTrue(
            any("gl194" in s.lower() or "public_preview_review_feedback_triage" in s.lower() for s in self.sources),
            "GL-194 or public_preview_review_feedback_triage not in input_sources_reviewed",
        )


class TestGL198BoundaryContent(unittest.TestCase):
    def setUp(self):
        with open(JSON_PATH, encoding="utf-8") as f:
            self.data = json.load(f)

    def test_controlled_preview_purpose_exists(self):
        self.assertIn("controlled_preview_purpose", self.data)
        self.assertTrue(len(self.data["controlled_preview_purpose"]) > 20)

    def test_controlled_preview_audience_exists(self):
        self.assertIn("controlled_preview_audience", self.data)
        self.assertTrue(len(self.data["controlled_preview_audience"]) > 10)

    def test_allowed_participant_profiles_include_external_developer(self):
        profiles = self.data.get("allowed_participant_profiles", [])
        self.assertTrue(
            any("external developer reviewer" in p.lower() for p in profiles),
            "allowed_participant_profiles missing 'external developer reviewer'",
        )

    def test_allowed_participant_profiles_include_ai_agent_reviewer(self):
        profiles = self.data.get("allowed_participant_profiles", [])
        self.assertTrue(
            any("ai" in p.lower() or "coding-agent" in p.lower() or "coding agent" in p.lower() for p in profiles),
            "allowed_participant_profiles missing AI/coding-agent reviewer",
        )

    def test_allowed_participant_profiles_include_grant_compliance_reviewer(self):
        profiles = self.data.get("allowed_participant_profiles", [])
        self.assertTrue(
            any("grant" in p.lower() or "compliance" in p.lower() for p in profiles),
            "allowed_participant_profiles missing grant/compliance domain reviewer",
        )

    def test_allowed_participant_profiles_include_security_reviewer(self):
        profiles = self.data.get("allowed_participant_profiles", [])
        self.assertTrue(
            any("security" in p.lower() for p in profiles),
            "allowed_participant_profiles missing security-minded reviewer",
        )

    def test_disallowed_participant_profiles_include_real_customer_pilot(self):
        profiles = self.data.get("disallowed_participant_profiles", [])
        self.assertTrue(
            any("real customer" in p.lower() or "private data" in p.lower() for p in profiles),
            "disallowed_participant_profiles missing real customer pilot with private data",
        )

    def test_disallowed_participant_profiles_include_production_operator(self):
        profiles = self.data.get("disallowed_participant_profiles", [])
        self.assertTrue(
            any("production grant" in p.lower() or "production workflow" in p.lower() for p in profiles),
            "disallowed_participant_profiles missing production grant workflow operator",
        )

    def test_disallowed_participant_profiles_include_institutional_deployment(self):
        profiles = self.data.get("disallowed_participant_profiles", [])
        self.assertTrue(
            any("institutional" in p.lower() for p in profiles),
            "disallowed_participant_profiles missing institutional deployment",
        )

    def test_disallowed_participant_profiles_include_tenant_isolation_validation(self):
        profiles = self.data.get("disallowed_participant_profiles", [])
        self.assertTrue(
            any("tenant" in p.lower() for p in profiles),
            "disallowed_participant_profiles missing tenant-isolation validation with real tenants",
        )

    def test_allowed_data_includes_synthetic_demo_grant_data(self):
        allowed = self.data.get("allowed_data", [])
        self.assertTrue(
            any("synthetic" in d.lower() or "demo grant" in d.lower() for d in allowed),
            "allowed_data missing synthetic/demo grant data",
        )

    def test_allowed_data_includes_repository_sample_json(self):
        allowed = self.data.get("allowed_data", [])
        self.assertTrue(
            any("json" in d.lower() or "sample" in d.lower() or "repository" in d.lower() for d in allowed),
            "allowed_data missing repository sample JSON",
        )

    def test_allowed_data_includes_generated_local_example_outputs(self):
        allowed = self.data.get("allowed_data", [])
        self.assertTrue(
            any("generated" in d.lower() or "local example" in d.lower() for d in allowed),
            "allowed_data missing generated local example outputs",
        )

    def test_allowed_data_includes_public_docs_feedback(self):
        allowed = self.data.get("allowed_data", [])
        self.assertTrue(
            any("docs feedback" in d.lower() or "public docs" in d.lower() for d in allowed),
            "allowed_data missing public docs feedback",
        )

    def test_forbidden_data_includes_real_customer_data(self):
        forbidden = self.data.get("forbidden_data", [])
        self.assertTrue(
            any("real customer" in d.lower() for d in forbidden),
            "forbidden_data missing real customer data",
        )

    def test_forbidden_data_includes_private_grants(self):
        forbidden = self.data.get("forbidden_data", [])
        self.assertTrue(
            any("private grant" in d.lower() for d in forbidden),
            "forbidden_data missing private grants",
        )

    def test_forbidden_data_includes_institutional_records(self):
        forbidden = self.data.get("forbidden_data", [])
        self.assertTrue(
            any("institutional" in d.lower() for d in forbidden),
            "forbidden_data missing institutional records",
        )

    def test_forbidden_data_includes_pii(self):
        forbidden = self.data.get("forbidden_data", [])
        self.assertTrue(
            any("pii" in d.lower() or "personally identifiable" in d.lower() for d in forbidden),
            "forbidden_data missing PII",
        )

    def test_forbidden_data_includes_secrets(self):
        forbidden = self.data.get("forbidden_data", [])
        self.assertTrue(
            any("secret" in d.lower() for d in forbidden),
            "forbidden_data missing secrets",
        )

    def test_forbidden_data_includes_tokens_api_keys(self):
        forbidden = self.data.get("forbidden_data", [])
        self.assertTrue(
            any("token" in d.lower() or "api key" in d.lower() or "password" in d.lower() for d in forbidden),
            "forbidden_data missing tokens/API keys/passwords/private keys",
        )

    def test_forbidden_data_includes_internal_hostnames(self):
        forbidden = self.data.get("forbidden_data", [])
        self.assertTrue(
            any("internal host" in d.lower() or "hostname" in d.lower() or "remote" in d.lower() for d in forbidden),
            "forbidden_data missing internal hostnames/remotes",
        )

    def test_forbidden_data_includes_exploit_details(self):
        forbidden = self.data.get("forbidden_data", [])
        self.assertTrue(
            any("exploit" in d.lower() for d in forbidden),
            "forbidden_data missing exploit details in public issues",
        )


class TestGL198AllowedForbiddenActivities(unittest.TestCase):
    def setUp(self):
        with open(JSON_PATH, encoding="utf-8") as f:
            self.data = json.load(f)

    def test_allowed_activities_include_verify_first_output(self):
        activities = self.data.get("allowed_activities", [])
        self.assertTrue(
            any("verify-first-output.sh" in a or "verify_first_output" in a.lower() for a in activities),
            "allowed_activities missing scripts/verify-first-output.sh",
        )

    def test_allowed_activities_include_grant_lifecycle_bundle(self):
        activities = self.data.get("allowed_activities", [])
        self.assertTrue(
            any("grant_lifecycle_evidence_bundle" in a.lower() for a in activities),
            "allowed_activities missing examples/grant_lifecycle_evidence_bundle.py",
        )

    def test_forbidden_activities_include_production_deployment(self):
        activities = self.data.get("forbidden_activities", [])
        self.assertTrue(
            any("production deployment" in a.lower() for a in activities),
            "forbidden_activities missing production deployment",
        )

    def test_forbidden_activities_include_real_grant_data(self):
        activities = self.data.get("forbidden_activities", [])
        self.assertTrue(
            any("real grant" in a.lower() or "real customer" in a.lower() for a in activities),
            "forbidden_activities missing processing real grant or customer data",
        )

    def test_forbidden_activities_include_tenant_isolation_testing(self):
        activities = self.data.get("forbidden_activities", [])
        self.assertTrue(
            any("tenant isolation" in a.lower() for a in activities),
            "forbidden_activities missing testing tenant isolation with real tenants",
        )

    def test_forbidden_activities_include_uploading_secrets(self):
        activities = self.data.get("forbidden_activities", [])
        self.assertTrue(
            any("secret" in a.lower() or "private grant data" in a.lower() for a in activities),
            "forbidden_activities missing uploading secrets/private grant data/PII",
        )

    def test_forbidden_activities_include_treating_examples_as_sdk(self):
        activities = self.data.get("forbidden_activities", [])
        self.assertTrue(
            any("production sdk" in a.lower() or "treating examples" in a.lower() for a in activities),
            "forbidden_activities missing treating examples as production SDK",
        )

    def test_forbidden_activities_include_publishing_exploit_details(self):
        activities = self.data.get("forbidden_activities", [])
        self.assertTrue(
            any("exploit" in a.lower() for a in activities),
            "forbidden_activities missing publishing exploit details publicly",
        )


class TestGL198EnvironmentBoundaries(unittest.TestCase):
    def setUp(self):
        with open(JSON_PATH, encoding="utf-8") as f:
            self.data = json.load(f)

    def test_allowed_environments_exist(self):
        self.assertIn("allowed_environments", self.data)
        self.assertGreater(len(self.data["allowed_environments"]), 0)

    def test_forbidden_environments_exist(self):
        self.assertIn("forbidden_environments", self.data)
        self.assertGreater(len(self.data["forbidden_environments"]), 0)


class TestGL198SpecialBoundaries(unittest.TestCase):
    def setUp(self):
        with open(JSON_PATH, encoding="utf-8") as f:
            self.data = json.load(f)

    def test_demo_endpoint_boundary_references_gl190(self):
        boundary = self.data.get("demo_endpoint_boundary", {})
        ref = boundary.get("reference", "")
        self.assertTrue(
            "GL-190" in ref or "demo_endpoint_safety_guard" in ref.lower(),
            "demo_endpoint_boundary does not reference GL-190 or demo_endpoint_safety_guard",
        )

    def test_api_sdk_agent_boundary_references_gl197(self):
        boundary = self.data.get("api_sdk_agent_boundary", {})
        ref = boundary.get("reference", "")
        self.assertTrue(
            "GL-197" in ref or "api_sdk_agent_value_decision_pack" in ref.lower(),
            "api_sdk_agent_boundary does not reference GL-197 or api_sdk_agent_value_decision_pack",
        )

    def test_api_sdk_agent_boundary_has_decision(self):
        boundary = self.data.get("api_sdk_agent_boundary", {})
        self.assertIn("decision", boundary)
        self.assertIn("api_first", boundary["decision"])

    def test_security_reporting_routes_to_github_security_advisories(self):
        boundary = self.data.get("security_sensitive_reporting_boundary", {})
        route = boundary.get("route", "").lower()
        self.assertIn("security advisories", route)

    def test_public_claim_boundary_prohibits_production_saas(self):
        boundary = self.data.get("public_claim_boundary", {})
        forbidden = boundary.get("forbidden_claims", [])
        self.assertTrue(
            any("production saas" in c.lower() or "production-ready" in c.lower() for c in forbidden),
            "public_claim_boundary does not prohibit production SaaS claim",
        )

    def test_public_claim_boundary_prohibits_tenant_isolation_claim(self):
        boundary = self.data.get("public_claim_boundary", {})
        forbidden = boundary.get("forbidden_claims", [])
        self.assertTrue(
            any("tenant" in c.lower() for c in forbidden),
            "public_claim_boundary does not prohibit tenant isolation claim",
        )


class TestGL198PreviewCriteria(unittest.TestCase):
    def setUp(self):
        with open(JSON_PATH, encoding="utf-8") as f:
            self.data = json.load(f)

    def test_preview_entry_criteria_include_first_output_helper(self):
        criteria = self.data.get("preview_entry_criteria", [])
        self.assertTrue(
            any("first output" in c.lower() or "verify-first-output" in c.lower() for c in criteria),
            "preview_entry_criteria missing first output helper works",
        )

    def test_preview_entry_criteria_include_grant_lifecycle_example(self):
        criteria = self.data.get("preview_entry_criteria", [])
        self.assertTrue(
            any("grant lifecycle" in c.lower() for c in criteria),
            "preview_entry_criteria missing grant lifecycle example works",
        )

    def test_preview_entry_criteria_include_feedback_infrastructure(self):
        criteria = self.data.get("preview_entry_criteria", [])
        self.assertTrue(
            any("feedback" in c.lower() for c in criteria),
            "preview_entry_criteria missing feedback infrastructure exists",
        )

    def test_preview_entry_criteria_include_security_advisory_routing(self):
        criteria = self.data.get("preview_entry_criteria", [])
        self.assertTrue(
            any("security advisory" in c.lower() or "advisory routing" in c.lower() for c in criteria),
            "preview_entry_criteria missing security advisory routing exists",
        )

    def test_preview_entry_criteria_include_smoke_matrix(self):
        criteria = self.data.get("preview_entry_criteria", [])
        self.assertTrue(
            any("smoke matrix" in c.lower() for c in criteria),
            "preview_entry_criteria missing smoke matrix exists",
        )

    def test_preview_exit_criteria_exist(self):
        self.assertIn("preview_exit_criteria", self.data)
        self.assertGreater(len(self.data["preview_exit_criteria"]), 0)


class TestGL198Findings(unittest.TestCase):
    def setUp(self):
        with open(JSON_PATH, encoding="utf-8") as f:
            self.data = json.load(f)

    def test_findings_exist(self):
        findings = self.data.get("findings", [])
        self.assertGreater(len(findings), 0, "No findings in artifact")

    def test_each_finding_has_required_fields(self):
        findings = self.data.get("findings", [])
        required = {"id", "severity", "category", "summary", "evidence", "blocking", "recommended_action", "recommended_issue"}
        for finding in findings:
            for field in required:
                self.assertIn(field, finding, f"Finding {finding.get('id', '?')} missing field: {field}")

    def test_recommended_next_issues_include_gl199(self):
        next_issues = self.data.get("recommended_next_issues", [])
        self.assertTrue(
            any("GL-199" in str(i) for i in next_issues),
            "recommended_next_issues does not include GL-199",
        )


class TestGL198DocContent(unittest.TestCase):
    def setUp(self):
        with open(DOC_PATH, encoding="utf-8") as f:
            self.doc = f.read().lower()

    def test_doc_states_developer_preview(self):
        self.assertTrue(
            "developer preview" in self.doc or "technical preview" in self.doc,
            "Doc does not state Developer Preview / technical preview",
        )

    def test_doc_states_not_production_saas(self):
        self.assertTrue(
            "not production saas" in self.doc
            or "production saas readiness" in self.doc
            or "not a production saas" in self.doc,
            "Doc does not state not production SaaS",
        )

    def test_doc_states_tenant_isolation_not_implemented(self):
        self.assertIn(
            "tenant isolation is not implemented",
            self.doc,
            "Doc does not include exact phrase 'tenant isolation is not implemented'",
        )

    def test_doc_states_no_real_secrets(self):
        self.assertIn(
            "no real secrets",
            self.doc,
            "Doc does not include exact phrase 'no real secrets'",
        )

    def test_doc_states_no_real_customer_data(self):
        self.assertIn(
            "no real customer data",
            self.doc,
            "Doc does not include exact phrase 'no real customer data'",
        )

    def test_doc_states_official_sdk_package_not_claimed(self):
        self.assertTrue(
            "official sdk" in self.doc or "no pip package" in self.doc or "not claimed" in self.doc,
            "Doc does not state official SDK/package not claimed unless verified",
        )

    def test_doc_routes_security_reports_to_github_security_advisories(self):
        self.assertTrue(
            "github security advisories" in self.doc,
            "Doc does not route security-sensitive reports to GitHub Security Advisories",
        )

    def test_doc_does_not_include_exploit_details(self):
        exploit_keywords = [
            "proof of concept",
            "poc exploit",
            "bypass steps",
            "sql injection payload",
            "remote code execution payload",
        ]
        for kw in exploit_keywords:
            self.assertNotIn(kw, self.doc, f"Doc contains exploit details: {kw}")


class TestGL198SafetyConfirmations(unittest.TestCase):
    def setUp(self):
        with open(JSON_PATH, encoding="utf-8") as f:
            self.data = json.load(f)

    def test_safety_confirmations_exist(self):
        self.assertIn("safety_confirmations", self.data)

    def test_all_required_confirmations_present(self):
        confirmations = self.data.get("safety_confirmations", {})
        for key in REQUIRED_SAFETY_CONFIRMATIONS:
            self.assertIn(key, confirmations, f"safety_confirmations missing: {key}")

    def test_no_github_push_confirmed(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertEqual(confirmations.get("no_github_push_performed"), "confirmed")

    def test_no_visibility_change_confirmed(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertEqual(confirmations.get("no_visibility_change_performed"), "confirmed")

    def test_no_backend_src_changes_confirmed(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertEqual(confirmations.get("no_backend_src_changes"), "confirmed")

    def test_no_openapi_changes_confirmed(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertEqual(confirmations.get("no_openapi_changes"), "confirmed")

    def test_no_sdk_implementation_changes_confirmed(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertEqual(confirmations.get("no_sdk_implementation_changes"), "confirmed")

    def test_no_package_publishing_changes_confirmed(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertEqual(confirmations.get("no_package_publishing_changes"), "confirmed")

    def test_no_production_saas_claim_confirmed(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertEqual(confirmations.get("no_production_saas_claim"), "confirmed")

    def test_tenant_isolation_not_claimed_confirmed(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertEqual(confirmations.get("tenant_isolation_not_claimed"), "confirmed")


class TestGL198ScopeGuard(unittest.TestCase):
    """Verify that only allowed files were touched in this issue."""

    ALLOWED_CHANGED_FILES = {
        "docs/controlled_preview_boundary_pack.md",
        "docs/examples/gl198/controlled_preview_boundary_pack.json",
        "backend/tests/test_gl198_controlled_preview_boundary_pack.py",
    }

    FORBIDDEN_PATTERNS = [
        "backend/src/",
        "openapi.yaml",
        "migrations/",
        "requirements",
        "setup.py",
        "pyproject.toml",
        "sdk/python/grantlayer_client.py",
        ".github/workflows/",
        "publish_snapshot",
    ]

    def setUp(self):
        with open(JSON_PATH, encoding="utf-8") as f:
            self.data = json.load(f)

    def test_changed_files_within_allowed_scope(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertIn(
                f,
                self.ALLOWED_CHANGED_FILES,
                f"changed_files contains a file outside allowed scope: {f}",
            )

    def test_no_backend_src_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertFalse(
                f.startswith("backend/src/"),
                f"changed_files contains backend/src/ path: {f}",
            )

    def test_no_openapi_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertNotIn("openapi", f.lower(), f"changed_files contains OpenAPI path: {f}")

    def test_no_migration_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertNotIn("migration", f.lower(), f"changed_files contains migration path: {f}")

    def test_no_sdk_implementation_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertFalse(
                "sdk/python/grantlayer_client.py" in f,
                f"changed_files contains SDK implementation: {f}",
            )

    def test_no_package_publishing_metadata_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertFalse(
                "pyproject.toml" in f or "setup.py" in f,
                f"changed_files contains package publishing metadata: {f}",
            )

    def test_no_github_workflow_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertNotIn(".github/workflows", f, f"changed_files contains GitHub workflow: {f}")

    def test_no_snapshot_publish_script_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertNotIn("publish_snapshot", f, f"changed_files contains snapshot publish script: {f}")

    def test_no_examples_runtime_implementation_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            if "examples/" in f and f.endswith(".py"):
                self.fail(f"changed_files contains examples runtime Python file: {f}")

    def test_no_frontend_website_design_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertFalse(
                any(kw in f.lower() for kw in ["frontend/", "website/", "design/"]),
                f"changed_files contains frontend/website/design path: {f}",
            )

    def test_no_git_remote_changes(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertEqual(
            confirmations.get("internal_repo_not_pushed_directly_to_github"), "confirmed"
        )

    def test_no_public_github_push(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertEqual(confirmations.get("no_github_push_performed"), "confirmed")

    def test_no_visibility_change(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertEqual(confirmations.get("no_visibility_change_performed"), "confirmed")

    def test_no_paperclip_status_in_data(self):
        raw = json.dumps(self.data).lower()
        self.assertNotIn("paperclip", raw, "JSON artifact references Paperclip")


if __name__ == "__main__":
    unittest.main()
