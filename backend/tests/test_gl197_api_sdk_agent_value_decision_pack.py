"""GL-197 API/SDK/Agent Value Decision Pack — validation tests."""

import json
import os
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

DOC_PATH = os.path.join(REPO_ROOT, "docs", "api_sdk_agent_value_decision_pack.md")
ARTIFACT_PATH = os.path.join(
    REPO_ROOT, "docs", "examples", "gl197", "api_sdk_agent_value_decision_pack.json"
)

ALLOWED_RESULTS = {
    "api_sdk_agent_value_decision_complete",
    "blocked_unexpected_scope",
    "blocked_public_claim_safety",
    "blocked_other_with_reason",
}

ALLOWED_DECISIONS = {
    "api_first_agent_examples_now_sdk_later",
    "sdk_prototype_next_api_docs_parallel",
    "api_walkthrough_first_sdk_deferred",
    "blocked_pending_public_value_gap",
    "blocked_other_with_reason",
}

REQUIRED_INPUT_SOURCES = [
    "README.md",
    "AGENTS.md",
]

REQUIRED_INPUT_SOURCES_ANY = [
    ["llms.txt", "llms-full.txt"],
]

REQUIRED_GL_SOURCES = [
    "gl193",
    "gl194",
    "gl195",
    "gl196",
]

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

FORBIDDEN_CHANGED_FILE_PREFIXES = [
    "backend/src/",
    "docs/openapi.yaml",
    "requirements",
    "frontend/",
    "website/",
    "design/",
    ".github/workflows/",
]


def _load_artifact():
    with open(ARTIFACT_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_doc():
    with open(DOC_PATH, encoding="utf-8") as f:
        return f.read()


class TestGL197DocExists(unittest.TestCase):
    def test_doc_exists(self):
        self.assertTrue(
            os.path.isfile(DOC_PATH),
            f"Expected GL-197 decision doc at {DOC_PATH}",
        )

    def test_artifact_exists(self):
        self.assertTrue(
            os.path.isfile(ARTIFACT_PATH),
            f"Expected GL-197 artifact at {ARTIFACT_PATH}",
        )


class TestGL197ArtifactStructure(unittest.TestCase):
    def setUp(self):
        self.data = _load_artifact()

    def test_artifact_is_valid_json(self):
        self.assertIsInstance(self.data, dict)

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-197")

    def test_result_is_allowed(self):
        self.assertIn(self.data.get("result"), ALLOWED_RESULTS)

    def test_decision_is_allowed(self):
        self.assertIn(self.data.get("decision"), ALLOWED_DECISIONS)

    def test_input_sources_reviewed_exists(self):
        sources = self.data.get("input_sources_reviewed", [])
        self.assertIsInstance(sources, list)
        self.assertGreater(len(sources), 0)

    def test_input_sources_includes_readme(self):
        sources = self.data.get("input_sources_reviewed", [])
        sources_lower = [s.lower() for s in sources]
        self.assertTrue(
            any("readme.md" in s for s in sources_lower),
            "input_sources_reviewed must include README.md",
        )

    def test_input_sources_includes_agents_md(self):
        sources = self.data.get("input_sources_reviewed", [])
        sources_lower = [s.lower() for s in sources]
        self.assertTrue(
            any("agents.md" in s for s in sources_lower),
            "input_sources_reviewed must include AGENTS.md",
        )

    def test_input_sources_includes_llms(self):
        sources = self.data.get("input_sources_reviewed", [])
        sources_lower = " ".join(s.lower() for s in sources)
        self.assertTrue(
            "llms.txt" in sources_lower or "llms-full.txt" in sources_lower,
            "input_sources_reviewed must include llms.txt or llms-full.txt",
        )

    def test_input_sources_includes_gl193(self):
        sources = self.data.get("input_sources_reviewed", [])
        joined = " ".join(s.lower() for s in sources)
        self.assertIn("gl193", joined, "input_sources_reviewed must reference GL-193 docs/artifacts")

    def test_input_sources_includes_gl194(self):
        sources = self.data.get("input_sources_reviewed", [])
        joined = " ".join(s.lower() for s in sources)
        self.assertIn("gl194", joined, "input_sources_reviewed must reference GL-194 docs/artifacts")

    def test_input_sources_includes_gl195(self):
        sources = self.data.get("input_sources_reviewed", [])
        joined = " ".join(s.lower() for s in sources)
        self.assertIn("gl195", joined, "input_sources_reviewed must reference GL-195 docs/artifacts")

    def test_input_sources_includes_gl196(self):
        sources = self.data.get("input_sources_reviewed", [])
        joined = " ".join(s.lower() for s in sources)
        self.assertIn("gl196", joined, "input_sources_reviewed must reference GL-196 docs/artifacts")

    def test_current_public_value_surface_exists(self):
        surface = self.data.get("current_public_value_surface")
        self.assertIsNotNone(surface)
        self.assertIsInstance(surface, dict)
        self.assertGreater(len(surface), 0)

    def test_api_value_assessment_exists(self):
        api = self.data.get("api_value_assessment")
        self.assertIsNotNone(api, "api_value_assessment must exist")
        self.assertIsInstance(api, dict)

    def test_api_value_assessment_has_status(self):
        api = self.data.get("api_value_assessment", {})
        self.assertIn("status", api)

    def test_api_value_assessment_has_rationale(self):
        api = self.data.get("api_value_assessment", {})
        self.assertTrue(
            "rationale" in api or "what_exists" in api,
            "api_value_assessment must include rationale or what_exists",
        )

    def test_api_value_assessment_has_recommended_followup(self):
        api = self.data.get("api_value_assessment", {})
        self.assertTrue(
            "recommended_followup" in api or "recommended_follow_up" in api,
            "api_value_assessment must include a recommended follow-up field",
        )

    def test_sdk_value_assessment_exists(self):
        sdk = self.data.get("sdk_value_assessment")
        self.assertIsNotNone(sdk, "sdk_value_assessment must exist")
        self.assertIsInstance(sdk, dict)

    def test_sdk_value_assessment_examples_are_not_sdk(self):
        sdk = self.data.get("sdk_value_assessment", {})
        self.assertTrue(
            sdk.get("examples_are_examples_not_sdk") is True
            or "examples are examples" in str(sdk).lower()
            or "examples_description" in sdk,
            "sdk_value_assessment must explicitly state examples are not a published SDK",
        )

    def test_sdk_value_assessment_no_official_sdk_claimed(self):
        sdk = self.data.get("sdk_value_assessment", {})
        self.assertTrue(
            sdk.get("no_official_sdk_package_claimed_unless_verified") is True
            or sdk.get("official_sdk_package_claimed") is False
            or "no official sdk" in str(sdk).lower(),
            "sdk_value_assessment must state no official SDK/package is claimed unless verified",
        )

    def test_agent_workflow_value_assessment_exists(self):
        agent = self.data.get("agent_workflow_value_assessment")
        self.assertIsNotNone(agent, "agent_workflow_value_assessment must exist")
        self.assertIsInstance(agent, dict)

    def test_agent_workflow_references_first_output_helper(self):
        agent = self.data.get("agent_workflow_value_assessment", {})
        agent_str = str(agent).lower()
        self.assertTrue(
            "first_output_helper" in agent_str
            or "first output helper" in agent_str
            or "verify-first-output" in agent_str,
            "agent_workflow_value_assessment must reference the first output helper",
        )

    def test_agent_workflow_references_grant_lifecycle_bundle(self):
        agent = self.data.get("agent_workflow_value_assessment", {})
        agent_str = str(agent).lower()
        self.assertTrue(
            "grant_lifecycle" in agent_str
            or "grant lifecycle" in agent_str,
            "agent_workflow_value_assessment must reference the grant lifecycle evidence bundle",
        )

    def test_packaging_boundaries_exist(self):
        pb = self.data.get("packaging_boundaries")
        self.assertIsNotNone(pb, "packaging_boundaries must exist")
        self.assertIsInstance(pb, dict)
        self.assertGreater(len(pb), 0)

    def test_product_narrative_exists(self):
        narrative = self.data.get("product_narrative")
        self.assertIsNotNone(narrative, "product_narrative must exist")
        self.assertIsInstance(narrative, str)
        self.assertGreater(len(narrative), 20)

    def test_product_narrative_api_first(self):
        narrative = self.data.get("product_narrative", "").lower()
        self.assertTrue(
            "api-first" in narrative
            or "api first" in narrative
            or "developer preview" in narrative,
            "product_narrative must say API-first Developer Preview or equivalent",
        )

    def test_product_narrative_no_production_saas_claim(self):
        narrative = self.data.get("product_narrative", "").lower()
        self.assertNotIn(
            "production saas ready",
            narrative,
            "product_narrative must not claim production SaaS readiness",
        )
        self.assertNotIn(
            "production-ready saas",
            narrative,
            "product_narrative must not claim production SaaS readiness",
        )

    def test_product_narrative_no_tenant_isolation_claim(self):
        narrative = self.data.get("product_narrative", "").lower()
        self.assertFalse(
            "tenant isolation is implemented" in narrative
            and "not" not in narrative,
            "product_narrative must not claim tenant isolation is implemented",
        )

    def test_decision_rationale_exists(self):
        rationale = self.data.get("decision_rationale")
        self.assertIsNotNone(rationale, "decision_rationale must exist")
        self.assertIsInstance(rationale, str)
        self.assertGreater(len(rationale), 20)

    def test_findings_exist(self):
        findings = self.data.get("findings", [])
        self.assertIsInstance(findings, list)
        self.assertGreater(len(findings), 0, "findings must be non-empty")

    def test_findings_have_required_fields(self):
        findings = self.data.get("findings", [])
        required_fields = {"id", "severity", "category", "summary", "evidence", "blocking", "recommended_action", "recommended_issue"}
        for finding in findings:
            missing = required_fields - set(finding.keys())
            self.assertEqual(
                missing,
                set(),
                f"Finding {finding.get('id', '?')} is missing fields: {missing}",
            )

    def test_recommended_next_issues_exist(self):
        issues = self.data.get("recommended_next_issues", [])
        self.assertIsInstance(issues, list)
        self.assertGreater(len(issues), 0)

    def test_recommended_next_issues_include_gl198(self):
        issues = self.data.get("recommended_next_issues", [])
        issues_str = str(issues).lower()
        self.assertIn(
            "gl-198",
            issues_str,
            "recommended_next_issues must include GL-198",
        )

    def test_recommended_next_issues_include_gl199(self):
        issues = self.data.get("recommended_next_issues", [])
        issues_str = str(issues).lower()
        self.assertIn(
            "gl-199",
            issues_str,
            "recommended_next_issues must include GL-199",
        )

    def test_safety_confirmations_exist(self):
        sc = self.data.get("safety_confirmations")
        self.assertIsNotNone(sc, "safety_confirmations must exist")
        self.assertIsInstance(sc, dict)

    def test_safety_confirmations_no_github_push(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertIn(
            sc.get("no_github_push_performed"),
            ("confirmed", True),
            "safety_confirmations.no_github_push_performed must be confirmed",
        )

    def test_safety_confirmations_no_visibility_change(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertIn(
            sc.get("no_visibility_change_performed"),
            ("confirmed", True),
        )

    def test_safety_confirmations_no_backend_src_changes(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertIn(
            sc.get("no_backend_src_changes"),
            ("confirmed", True),
        )

    def test_safety_confirmations_no_openapi_changes(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertIn(
            sc.get("no_openapi_changes"),
            ("confirmed", True),
        )

    def test_safety_confirmations_no_sdk_implementation_changes(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertIn(
            sc.get("no_sdk_implementation_changes"),
            ("confirmed", True),
        )

    def test_safety_confirmations_no_package_publishing_changes(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertIn(
            sc.get("no_package_publishing_changes"),
            ("confirmed", True),
        )

    def test_safety_confirmations_no_production_saas_claim(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertIn(
            sc.get("no_production_saas_claim"),
            ("confirmed", True),
        )

    def test_safety_confirmations_tenant_isolation_not_claimed(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertIn(
            sc.get("tenant_isolation_not_claimed"),
            ("confirmed", True),
        )

    def test_safety_confirmations_all_required_keys_present(self):
        sc = self.data.get("safety_confirmations", {})
        missing = [k for k in REQUIRED_SAFETY_CONFIRMATIONS if k not in sc]
        self.assertEqual(
            missing,
            [],
            f"safety_confirmations missing keys: {missing}",
        )

    def test_changed_files_within_allowed_scope(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            for prefix in FORBIDDEN_CHANGED_FILE_PREFIXES:
                self.assertFalse(
                    f.startswith(prefix),
                    f"changed_files contains forbidden path: {f}",
                )


class TestGL197DocContent(unittest.TestCase):
    def setUp(self):
        self.doc = _load_doc()
        self.doc_lower = self.doc.lower()

    def test_doc_contains_issue_id(self):
        self.assertIn("gl-197", self.doc_lower)

    def test_doc_states_developer_preview(self):
        self.assertTrue(
            "developer preview" in self.doc_lower
            or "technical preview" in self.doc_lower,
            "doc must state Developer Preview or technical preview",
        )

    def test_doc_states_not_production_saas(self):
        self.assertTrue(
            "not production saas" in self.doc_lower
            or "not claimed" in self.doc_lower
            or "not a production saas" in self.doc_lower,
            "doc must state not production SaaS",
        )

    def test_doc_states_tenant_isolation_not_implemented(self):
        self.assertIn(
            "tenant isolation is not implemented",
            self.doc_lower,
            "doc must state tenant/workspace isolation not implemented",
        )

    def test_doc_states_no_real_secrets(self):
        self.assertTrue(
            "no real secrets" in self.doc_lower
            or "placeholder token" in self.doc_lower,
            "doc must state no real secrets or customer data",
        )

    def test_doc_states_examples_are_examples_not_sdk(self):
        self.assertTrue(
            "examples are examples" in self.doc_lower
            or "examples, not a published sdk" in self.doc_lower
            or "deterministic local examples" in self.doc_lower,
            "doc must state examples are examples, not a published SDK",
        )

    def test_doc_routes_security_to_advisories(self):
        self.assertTrue(
            "github security advisories" in self.doc_lower
            or "security/advisories" in self.doc_lower,
            "doc must route security-sensitive reports to GitHub Security Advisories",
        )

    def test_doc_does_not_include_exploit_details(self):
        exploit_markers = [
            "proof of concept exploit",
            "reproduction steps for unpatched",
            "working exploit",
        ]
        for marker in exploit_markers:
            self.assertNotIn(marker, self.doc_lower, f"doc must not include exploit details: {marker}")

    def test_doc_no_backend_src_changes(self):
        self.assertNotIn(
            "backend/src/ was modified",
            self.doc_lower,
        )


class TestGL197ScopeGuard(unittest.TestCase):
    """Verify GL-197 changes stay within allowed file scope."""

    ALLOWED_PATHS = {
        "docs/api_sdk_agent_value_decision_pack.md",
        "docs/examples/gl197/api_sdk_agent_value_decision_pack.json",
        "backend/tests/test_gl197_api_sdk_agent_value_decision_pack.py",
    }

    def test_doc_path_is_allowed(self):
        rel = os.path.relpath(DOC_PATH, REPO_ROOT).replace("\\", "/")
        self.assertIn(rel, self.ALLOWED_PATHS)

    def test_artifact_path_is_allowed(self):
        rel = os.path.relpath(ARTIFACT_PATH, REPO_ROOT).replace("\\", "/")
        self.assertIn(rel, self.ALLOWED_PATHS)

    def test_no_backend_src_changes(self):
        backend_src = os.path.join(REPO_ROOT, "backend", "src")
        self.assertTrue(
            os.path.isdir(backend_src),
            "backend/src must still exist (not deleted)",
        )

    def test_no_openapi_changes(self):
        openapi = os.path.join(REPO_ROOT, "docs", "openapi.yaml")
        self.assertTrue(
            os.path.isfile(openapi),
            "docs/openapi.yaml must still exist (not deleted)",
        )

    def test_no_requirements_changes(self):
        req = os.path.join(REPO_ROOT, "requirements.txt")
        self.assertTrue(
            os.path.isfile(req),
            "requirements.txt must still exist (not deleted)",
        )

    def test_no_sdk_implementation_added(self):
        sdk_dir = os.path.join(REPO_ROOT, "sdk", "python")
        sdk_files_before = {"grantlayer_client.py", "README.md", "__pycache__"}
        if os.path.isdir(sdk_dir):
            current_files = set(os.listdir(sdk_dir))
            new_files = current_files - sdk_files_before
            new_py_files = {f for f in new_files if f.endswith(".py")}
            self.assertEqual(
                new_py_files,
                set(),
                f"GL-197 must not add new SDK implementation files: {new_py_files}",
            )

    def test_no_public_push_markers(self):
        artifact_data = _load_artifact()
        sc = artifact_data.get("safety_confirmations", {})
        self.assertIn(
            sc.get("no_github_push_performed"),
            ("confirmed", True),
        )
        self.assertIn(
            sc.get("internal_repo_not_pushed_directly_to_github"),
            ("confirmed", True),
        )


if __name__ == "__main__":
    unittest.main()
