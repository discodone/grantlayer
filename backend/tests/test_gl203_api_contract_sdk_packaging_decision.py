"""GL-203 API Contract / SDK Packaging Decision — regression tests.

Verifies:
- Documentation artifacts exist and are structurally valid.
- JSON artifact contains all required fields with allowed values.
- SDK/package recommendation does not claim official SDK/package.
- Prohibited claims are present in the JSON.
- Follow-up split includes GL-203B.
- Safety confirmations are met.
- Allowed file scope was respected.
- No backend/src changes, no API behavior changes, no OpenAPI changes.
"""

import json
import os
import subprocess
import unittest

_REPO = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

_DOC = os.path.join(_REPO, "docs", "api_contract_sdk_packaging_decision.md")
_JSON = os.path.join(
    _REPO, "docs", "examples", "gl203", "api_contract_sdk_packaging_decision.json"
)
_BRANCH_ALLOWED_FILES = {
    "docs/api_contract_sdk_packaging_decision.md",
    "docs/examples/gl203/api_contract_sdk_packaging_decision.json",
    "backend/tests/test_gl203_api_contract_sdk_packaging_decision.py",
}


def _load_json():
    with open(_JSON, encoding="utf-8") as f:
        return json.load(f)


def _doc_text():
    with open(_DOC, encoding="utf-8") as f:
        return f.read()


class TestGL203DocsExist(unittest.TestCase):

    def test_doc_file_exists(self):
        self.assertTrue(os.path.isfile(_DOC), f"Missing: {_DOC}")

    def test_json_artifact_exists(self):
        self.assertTrue(os.path.isfile(_JSON), f"Missing: {_JSON}")

    def test_json_is_valid(self):
        data = _load_json()
        self.assertIsInstance(data, dict)


class TestGL203JSONRequiredFields(unittest.TestCase):

    def setUp(self):
        self.data = _load_json()

    def test_issue_id_is_gl203(self):
        self.assertEqual(self.data["issue_id"], "GL-203")

    def test_title_exists(self):
        self.assertIn("title", self.data)
        self.assertTrue(self.data["title"])

    def test_result_is_allowed(self):
        allowed = {"ready_for_merge", "blocked"}
        self.assertIn(self.data["result"], allowed)

    def test_decision_exists(self):
        self.assertIn("decision", self.data)
        self.assertTrue(self.data["decision"])

    def test_decision_rationale_exists(self):
        self.assertIn("decision_rationale", self.data)
        self.assertTrue(self.data["decision_rationale"])

    def test_input_sources_reviewed_exists(self):
        self.assertIn("input_sources_reviewed", self.data)
        self.assertIsInstance(self.data["input_sources_reviewed"], list)
        self.assertGreater(len(self.data["input_sources_reviewed"]), 0)

    def test_current_api_contract_summary_exists(self):
        self.assertIn("current_api_contract_summary", self.data)
        self.assertTrue(self.data["current_api_contract_summary"])

    def test_openapi_alignment_assessment_exists(self):
        self.assertIn("openapi_alignment_assessment", self.data)
        self.assertTrue(self.data["openapi_alignment_assessment"])

    def test_endpoint_auth_boundary_assessment_exists(self):
        self.assertIn("endpoint_auth_boundary_assessment", self.data)
        self.assertTrue(self.data["endpoint_auth_boundary_assessment"])

    def test_tenant_workspace_contract_implications_exists(self):
        self.assertIn("tenant_workspace_contract_implications", self.data)
        self.assertTrue(self.data["tenant_workspace_contract_implications"])

    def test_auth_config_contract_implications_exists(self):
        self.assertIn("auth_config_contract_implications", self.data)
        self.assertTrue(self.data["auth_config_contract_implications"])

    def test_persistence_migration_contract_implications_exists(self):
        self.assertIn("persistence_migration_contract_implications", self.data)
        self.assertTrue(self.data["persistence_migration_contract_implications"])

    def test_sdk_package_options_include_a_through_e(self):
        options = self.data.get("sdk_package_options", [])
        option_labels = {o.get("option") for o in options}
        for letter in ["A", "B", "C", "D", "E"]:
            self.assertIn(letter, option_labels, f"SDK option {letter} missing")

    def test_selected_sdk_package_recommendation_exists(self):
        self.assertIn("selected_sdk_package_recommendation", self.data)
        rec = self.data["selected_sdk_package_recommendation"]
        self.assertTrue(rec)

    def test_agent_integration_implications_exists(self):
        self.assertIn("agent_integration_implications", self.data)
        self.assertTrue(self.data["agent_integration_implications"])

    def test_allowed_public_claims_exists(self):
        self.assertIn("allowed_public_claims", self.data)
        self.assertIsInstance(self.data["allowed_public_claims"], list)
        self.assertGreater(len(self.data["allowed_public_claims"]), 0)

    def test_prohibited_public_claims_exists(self):
        self.assertIn("prohibited_public_claims", self.data)
        self.assertIsInstance(self.data["prohibited_public_claims"], list)
        self.assertGreater(len(self.data["prohibited_public_claims"]), 0)

    def test_follow_up_implementation_split_exists(self):
        self.assertIn("follow_up_implementation_split", self.data)
        self.assertIsInstance(self.data["follow_up_implementation_split"], list)
        self.assertGreater(len(self.data["follow_up_implementation_split"]), 0)

    def test_production_readiness_impact_exists(self):
        self.assertIn("production_readiness_impact", self.data)
        self.assertTrue(self.data["production_readiness_impact"])

    def test_risk_register_exists(self):
        self.assertIn("risk_register", self.data)
        self.assertIsInstance(self.data["risk_register"], list)
        self.assertGreater(len(self.data["risk_register"]), 0)

    def test_findings_exist_and_have_required_fields(self):
        findings = self.data.get("findings", [])
        self.assertIsInstance(findings, list)
        self.assertGreater(len(findings), 0)
        for f in findings:
            self.assertIn("id", f, f"Finding missing 'id': {f}")
            self.assertIn("summary", f, f"Finding missing 'summary': {f}")

    def test_safety_confirmations_exist(self):
        self.assertIn("safety_confirmations", self.data)
        sc = self.data["safety_confirmations"]
        self.assertIsInstance(sc, dict)
        self.assertGreater(len(sc), 0)

    def test_recommended_next_issues_exist(self):
        self.assertIn("recommended_next_issues", self.data)
        self.assertIsInstance(self.data["recommended_next_issues"], list)
        self.assertGreater(len(self.data["recommended_next_issues"]), 0)


class TestGL203SDKRecommendation(unittest.TestCase):

    def setUp(self):
        self.data = _load_json()

    def test_no_official_sdk_claimed_now(self):
        rec = self.data.get("selected_sdk_package_recommendation", {})
        # Recommendation must not claim official SDK now (Option D rejected)
        self.assertTrue(
            rec.get("no_official_sdk_claimed", False),
            "Recommendation must confirm no official SDK claimed"
        )

    def test_no_package_publishing(self):
        rec = self.data.get("selected_sdk_package_recommendation", {})
        self.assertTrue(
            rec.get("no_package_publishing", False),
            "Recommendation must confirm no package publishing"
        )

    def test_selected_option_is_not_d(self):
        rec = self.data.get("selected_sdk_package_recommendation", {})
        selected = rec.get("selected_option", "")
        self.assertNotEqual(selected, "D", "Option D (official SDK now) must not be selected")

    def test_option_d_is_rejected_in_options(self):
        options = self.data.get("sdk_package_options", [])
        option_d = next((o for o in options if o.get("option") == "D"), None)
        self.assertIsNotNone(option_d, "Option D must be listed")
        assessment = option_d.get("assessment", "").upper()
        self.assertIn("REJECTED", assessment, "Option D must be explicitly REJECTED")


class TestGL203ProhibitedClaims(unittest.TestCase):

    def setUp(self):
        self.data = _load_json()

    def _prohibited_lower(self):
        return [c.lower() for c in self.data.get("prohibited_public_claims", [])]

    def test_production_saas_readiness_prohibited(self):
        prohibited = self._prohibited_lower()
        self.assertTrue(
            any("production saas" in c for c in prohibited),
            "Prohibited claims must include production SaaS readiness"
        )

    def test_real_customer_data_readiness_prohibited(self):
        prohibited = self._prohibited_lower()
        self.assertTrue(
            any("real customer" in c or "customer data" in c for c in prohibited),
            "Prohibited claims must include real customer data readiness"
        )

    def test_private_grant_data_readiness_prohibited(self):
        prohibited = self._prohibited_lower()
        self.assertTrue(
            any("private grant" in c or "institutional data" in c for c in prohibited),
            "Prohibited claims must include private grant/institutional data readiness"
        )

    def test_official_sdk_package_availability_prohibited(self):
        prohibited = self._prohibited_lower()
        self.assertTrue(
            any("official sdk" in c or "package available" in c for c in prohibited),
            "Prohibited claims must include official SDK/package availability"
        )

    def test_complete_tenant_workspace_production_guarantee_prohibited(self):
        prohibited = self._prohibited_lower()
        self.assertTrue(
            any("tenant" in c and ("isolation" in c or "production" in c) for c in prohibited),
            "Prohibited claims must include complete tenant/workspace production guarantee"
        )


class TestGL203FollowUpSplit(unittest.TestCase):

    def setUp(self):
        self.data = _load_json()

    def test_follow_up_includes_gl203b_openapi_contract_cleanup(self):
        issues = self.data.get("follow_up_implementation_split", [])
        issue_ids = [str(i.get("issue", "")).upper() for i in issues]
        descriptions = [str(i.get("description", "")).lower() for i in issues]
        has_gl203b = any("GL-203B" in iid for iid in issue_ids)
        has_openapi = any("openapi" in d or "contract" in d for d in descriptions)
        self.assertTrue(
            has_gl203b or has_openapi,
            "Follow-up split must include GL-203B or equivalent OpenAPI/contract cleanup"
        )

    def test_recommended_next_issues_include_gl204_or_gl203b_first(self):
        next_issues = self.data.get("recommended_next_issues", [])
        issue_labels = [str(i.get("issue", "")).upper() for i in next_issues]
        has_gl204 = any("GL-204" in label for label in issue_labels)
        has_gl203b = any("GL-203B" in label for label in issue_labels)
        self.assertTrue(
            has_gl204 or has_gl203b,
            "Recommended next issues must include GL-204 or explain that GL-203B comes first"
        )


class TestGL203SafetyConfirmations(unittest.TestCase):

    def setUp(self):
        self.data = _load_json()

    def test_no_production_saas_claim(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertTrue(sc.get("no_production_saas_claim", False))

    def test_tenant_workspace_not_overclaimed(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertTrue(sc.get("tenant_workspace_isolation_not_overclaimed", False))

    def test_no_real_customer_private_grant_data_readiness(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertTrue(sc.get("no_real_customer_private_grant_data_readiness_claimed", False))

    def test_security_reports_route_to_github_security_advisories(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertTrue(sc.get("security_reports_route_to_github_security_advisories", False))

    def test_no_exploit_details(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertTrue(sc.get("no_exploit_details_included", False))

    def test_no_real_secrets(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertTrue(sc.get("no_real_secrets_included", False))

    def test_no_backend_src_changes(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertTrue(sc.get("no_backend_src_changes", False))

    def test_no_api_behavior_changes(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertTrue(sc.get("no_api_behavior_changes", False))

    def test_no_openapi_changes(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertTrue(sc.get("no_openapi_changes", False))

    def test_no_official_sdk_claimed(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertTrue(sc.get("no_official_sdk_claimed", False))

    def test_no_package_publishing(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertTrue(sc.get("no_package_publishing", False))

    def test_no_public_publish(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertTrue(sc.get("no_public_publish", False))

    def test_no_visibility_change(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertTrue(sc.get("no_visibility_change", False))

    def test_developer_preview_posture_preserved(self):
        sc = self.data.get("safety_confirmations", {})
        self.assertTrue(sc.get("developer_preview_controlled_preview_posture_preserved", False))


class TestGL203DocContent(unittest.TestCase):

    def setUp(self):
        self.text = _doc_text()

    def test_doc_states_developer_preview(self):
        self.assertIn("Developer Preview", self.text)

    def test_doc_states_controlled_preview(self):
        self.assertIn("Controlled Preview", self.text)

    def test_doc_states_not_production_saas(self):
        text_lower = self.text.lower()
        self.assertTrue(
            "not production saas" in text_lower
            or "not a production saas" in text_lower
            or ("not" in text_lower and "production saas" in text_lower),
            "Doc must state not production SaaS"
        )

    def test_doc_states_not_ready_real_customer_data(self):
        self.assertIn("real customer", self.text.lower())

    def test_doc_states_no_official_sdk_claimed(self):
        text_lower = self.text.lower()
        self.assertTrue(
            "no official sdk" in text_lower or "not claimed" in text_lower,
            "Doc must state no official SDK is claimed"
        )

    def test_doc_routes_security_to_github_security_advisories(self):
        self.assertIn("GitHub Security Advisories", self.text)

    def test_doc_includes_no_exploit_details_statement(self):
        self.assertIn("exploit", self.text.lower())
        self.assertIn("No exploit details", self.text)

    def test_doc_includes_no_real_secrets_statement(self):
        self.assertIn("No real secrets", self.text)

    def test_doc_includes_issue_id_gl203(self):
        self.assertIn("GL-203", self.text)

    def test_doc_contains_sdk_options(self):
        for label in ["Option A", "Option B", "Option C", "Option D", "Option E"]:
            self.assertIn(label, self.text, f"Doc must discuss {label}")


class TestGL203InputSourcesExist(unittest.TestCase):
    """Verify that the input sources the decision claims to have reviewed actually exist."""

    REQUIRED_SOURCES = [
        "docs/persistence_postgres_migration_readiness.md",
        "docs/examples/gl202/persistence_postgres_migration_readiness.json",
        "docs/production_auth_secrets_config_hardening.md",
        "docs/examples/gl201/production_auth_secrets_config_hardening.json",
        "docs/tenant_workspace_api_audit_regression_completion.md",
        "docs/examples/gl200c/tenant_workspace_api_audit_regression_completion.json",
        "docs/tenant_workspace_isolation_implementation_baseline.md",
        "docs/examples/gl200b/tenant_workspace_isolation_implementation_baseline.json",
        "docs/tenant_workspace_isolation_design_pack.md",
        "docs/examples/gl200a/tenant_workspace_isolation_design_pack.json",
        "docs/production_readiness_gap_report_v2.md",
        "docs/examples/gl199/production_readiness_gap_report_v2.json",
        "docs/api_sdk_agent_value_decision_pack.md",
        "docs/examples/gl197/api_sdk_agent_value_decision_pack.json",
        "docs/controlled_preview_boundary_pack.md",
        "docs/examples/gl198/controlled_preview_boundary_pack.json",
        "README.md",
        "SECURITY.md",
        "AGENTS.md",
        "llms.txt",
        "docs/openapi.yaml",
    ]

    def test_input_sources_exist(self):
        for rel in self.REQUIRED_SOURCES:
            path = os.path.join(_REPO, rel)
            self.assertTrue(
                os.path.isfile(path),
                f"Required input source does not exist: {rel}"
            )


class TestGL203FileScope(unittest.TestCase):
    """Verify that changed files on this branch stay within the allowed scope."""

    def _get_changed_files(self):
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "main...HEAD"],
                capture_output=True, text=True, cwd=_REPO, timeout=30,
            )
            if result.returncode != 0:
                return None
            return set(result.stdout.strip().splitlines())
        except Exception:
            return None

    def test_no_backend_src_changes(self):
        changed = self._get_changed_files()
        if changed is None:
            self.skipTest("Could not determine changed files via git")
        src_changes = [f for f in changed if f.startswith("backend/src/")]
        self.assertEqual(
            src_changes, [],
            f"backend/src changes detected — not allowed: {src_changes}"
        )

    def test_no_openapi_changes(self):
        changed = self._get_changed_files()
        if changed is None:
            self.skipTest("Could not determine changed files via git")
        openapi_changes = [f for f in changed if "openapi.yaml" in f]
        self.assertEqual(
            openapi_changes, [],
            f"OpenAPI changes detected — not allowed in GL-203: {openapi_changes}"
        )

    def test_no_sdk_implementation_changes(self):
        changed = self._get_changed_files()
        if changed is None:
            self.skipTest("Could not determine changed files via git")
        sdk_impl_changes = [
            f for f in changed
            if f.startswith("sdk/") and f.endswith(".py")
        ]
        self.assertEqual(
            sdk_impl_changes, [],
            f"SDK implementation changes detected — not allowed: {sdk_impl_changes}"
        )

    def test_no_package_publishing_metadata_changes(self):
        changed = self._get_changed_files()
        if changed is None:
            self.skipTest("Could not determine changed files via git")
        package_meta = [
            f for f in changed
            if any(f.endswith(ext) for ext in ["setup.py", "setup.cfg", "pyproject.toml", "package.json", "MANIFEST.in"])
        ]
        self.assertEqual(
            package_meta, [],
            f"Package publishing metadata changes detected: {package_meta}"
        )

    def test_no_frontend_design_changes(self):
        changed = self._get_changed_files()
        if changed is None:
            self.skipTest("Could not determine changed files via git")
        frontend = [
            f for f in changed
            if f.startswith("website-design/") or f.startswith("dashboard/")
        ]
        self.assertEqual(
            frontend, [],
            f"Frontend/design changes detected — not allowed: {frontend}"
        )

    def test_no_github_workflow_changes(self):
        changed = self._get_changed_files()
        if changed is None:
            self.skipTest("Could not determine changed files via git")
        workflows = [f for f in changed if f.startswith(".github/")]
        self.assertEqual(
            workflows, [],
            f"GitHub workflow changes detected — not allowed: {workflows}"
        )

    def test_changed_files_within_allowed_scope(self):
        changed = self._get_changed_files()
        if changed is None:
            self.skipTest("Could not determine changed files via git")
        unexpected = changed - _BRANCH_ALLOWED_FILES
        scope_guard_patterns = [
            "backend/src/",
            "sdk/",
            ".github/",
            "website-design/",
            "dashboard/",
            "scripts/publish",
            "openapi.yaml",
        ]
        problematic = [
            f for f in unexpected
            if any(p in f for p in scope_guard_patterns)
        ]
        self.assertEqual(
            problematic, [],
            f"Files outside allowed scope changed: {problematic}"
        )


class TestGL203NoSecretContent(unittest.TestCase):
    """Verify no real secrets are embedded in GL-203 artifacts."""

    SECRET_PATTERNS = [
        "BEGIN RSA PRIVATE KEY",
        "BEGIN EC PRIVATE KEY",
        "BEGIN OPENSSH PRIVATE KEY",
        "PRIVATE KEY-----",
        "sk-",
        "ghp_",
        "github_pat_",
        "glpat-",
    ]

    def _artifacts_text(self):
        texts = []
        for path in [_DOC, _JSON]:
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    texts.append(f.read())
        return "\n".join(texts)

    def test_no_secret_patterns_in_artifacts(self):
        text = self._artifacts_text()
        for pattern in self.SECRET_PATTERNS:
            self.assertNotIn(
                pattern, text,
                f"Potential secret pattern found in GL-203 artifacts: {pattern}"
            )


if __name__ == "__main__":
    unittest.main()
