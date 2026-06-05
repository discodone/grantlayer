"""
GL-207 Claim Safety & Controlled Preview Boundary — test suite.

Verifies:
- docs/claim_safety_controlled_preview_boundary.md exists and has required content
- docs/examples/gl207/claim_safety_controlled_preview_boundary.json exists and is valid
- JSON fields required by the GL-207 spec are present and correct
- Claim safety: no prohibited claims, required no-go statements present
- Scope guard: no backend/src, no API behavior, no migrations, no SDK impl,
  no package metadata, no frontend/website/design, no GitHub workflow changes
- Unrelated website files excluded
"""

import json
import os
import subprocess
import unittest

_REPO = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)


def _path(*parts):
    return os.path.join(_REPO, *parts)


def _read(relpath):
    with open(_path(relpath), encoding="utf-8") as f:
        return f.read()


def _load_doc():
    return _read("docs/claim_safety_controlled_preview_boundary.md").lower()


def _load_json():
    with open(_path("docs/examples/gl207/claim_safety_controlled_preview_boundary.json"), encoding="utf-8") as f:
        return json.load(f)


def _branch_diff_files():
    result = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    return set(result.stdout.strip().splitlines())


class TestGL207DocExists(unittest.TestCase):
    def test_doc_file_exists(self):
        self.assertTrue(
            os.path.isfile(_path("docs/claim_safety_controlled_preview_boundary.md")),
            "docs/claim_safety_controlled_preview_boundary.md must exist",
        )

    def test_json_artifact_exists(self):
        self.assertTrue(
            os.path.isfile(_path("docs/examples/gl207/claim_safety_controlled_preview_boundary.json")),
            "docs/examples/gl207/claim_safety_controlled_preview_boundary.json must exist",
        )

    def test_json_is_valid(self):
        data = _load_json()
        self.assertIsInstance(data, dict)


class TestGL207JSONFields(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-207")

    def test_result_present(self):
        self.assertIn("result", self.data)
        self.assertTrue(self.data["result"])

    def test_decision_present(self):
        self.assertIn("decision", self.data)
        self.assertTrue(self.data["decision"])

    def test_decision_rationale_present(self):
        self.assertIn("decision_rationale", self.data)
        self.assertTrue(self.data["decision_rationale"])

    def test_input_sources_reviewed(self):
        sources = self.data.get("input_sources_reviewed", [])
        self.assertIsInstance(sources, list)
        self.assertGreater(len(sources), 0, "input_sources_reviewed must not be empty")

    def test_claim_inventory_summary_present(self):
        self.assertIn("claim_inventory_summary", self.data)
        self.assertIsInstance(self.data["claim_inventory_summary"], dict)

    def test_controlled_preview_boundary_present(self):
        self.assertIn("controlled_preview_boundary", self.data)
        boundary = self.data["controlled_preview_boundary"]
        self.assertIn("allowed", boundary)
        self.assertIn("no_go", boundary)

    def test_allowed_claims_present(self):
        claims = self.data.get("allowed_claims", [])
        self.assertIsInstance(claims, list)
        self.assertGreater(len(claims), 0)

    def test_prohibited_claims_present(self):
        claims = self.data.get("prohibited_claims", [])
        self.assertIsInstance(claims, list)
        self.assertGreater(len(claims), 0)

    def test_stale_claim_corrections_present(self):
        corrections = self.data.get("stale_claim_corrections", [])
        self.assertIsInstance(corrections, list)
        self.assertGreater(len(corrections), 0)

    def test_public_docs_impact_present(self):
        self.assertIn("public_docs_impact", self.data)
        self.assertIsInstance(self.data["public_docs_impact"], dict)

    def test_openapi_claim_impact_present(self):
        self.assertIn("openapi_claim_impact", self.data)
        self.assertIsInstance(self.data["openapi_claim_impact"], dict)

    def test_sdk_claim_boundary_present(self):
        self.assertIn("sdk_claim_boundary", self.data)
        self.assertIsInstance(self.data["sdk_claim_boundary"], dict)

    def test_tenant_workspace_claim_boundary_present(self):
        self.assertIn("tenant_workspace_claim_boundary", self.data)
        self.assertIsInstance(self.data["tenant_workspace_claim_boundary"], dict)

    def test_admin_operator_claim_boundary_present(self):
        self.assertIn("admin_operator_claim_boundary", self.data)
        self.assertIsInstance(self.data["admin_operator_claim_boundary"], dict)

    def test_live_postgres_claim_boundary_present(self):
        self.assertIn("live_postgres_claim_boundary", self.data)
        self.assertIsInstance(self.data["live_postgres_claim_boundary"], dict)

    def test_backup_restore_dr_claim_boundary_present(self):
        self.assertIn("backup_restore_dr_claim_boundary", self.data)
        self.assertIsInstance(self.data["backup_restore_dr_claim_boundary"], dict)

    def test_observability_claim_boundary_present(self):
        self.assertIn("observability_claim_boundary", self.data)
        self.assertIsInstance(self.data["observability_claim_boundary"], dict)

    def test_first_external_controlled_pilot_boundary_present(self):
        self.assertIn("first_external_controlled_pilot_boundary", self.data)
        self.assertIsInstance(self.data["first_external_controlled_pilot_boundary"], dict)

    def test_website_marketing_deferral_present(self):
        self.assertIn("website_marketing_deferral", self.data)
        self.assertIsInstance(self.data["website_marketing_deferral"], dict)

    def test_production_readiness_impact_present(self):
        self.assertIn("production_readiness_impact", self.data)
        self.assertIsInstance(self.data["production_readiness_impact"], dict)

    def test_remaining_gaps_present(self):
        gaps = self.data.get("remaining_gaps", [])
        self.assertIsInstance(gaps, list)
        self.assertGreater(len(gaps), 0)

    def test_risk_register_present(self):
        register = self.data.get("risk_register", [])
        self.assertIsInstance(register, list)
        self.assertGreater(len(register), 0)

    def test_findings_present(self):
        findings = self.data.get("findings", [])
        self.assertIsInstance(findings, list)
        self.assertGreater(len(findings), 0)

    def test_safety_confirmations_present(self):
        self.assertIn("safety_confirmations", self.data)
        self.assertIsInstance(self.data["safety_confirmations"], dict)

    def test_recommended_next_issues_present(self):
        issues = self.data.get("recommended_next_issues", [])
        self.assertIsInstance(issues, list)
        self.assertGreater(len(issues), 0)


class TestGL207JSONSafetyConfirmations(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.safety = self.data.get("safety_confirmations", {})

    def test_no_exploit_details(self):
        self.assertTrue(self.safety.get("no_exploit_details"), "no_exploit_details must be true")

    def test_no_real_secrets(self):
        self.assertTrue(self.safety.get("no_real_secrets"), "no_real_secrets must be true")

    def test_no_real_customer_data(self):
        self.assertTrue(self.safety.get("no_real_customer_data"), "no_real_customer_data must be true")

    def test_no_private_grant_data(self):
        self.assertTrue(self.safety.get("no_private_grant_institutional_data"), "no_private_grant_institutional_data must be true")

    def test_production_saas_not_claimed(self):
        self.assertTrue(self.safety.get("production_saas_not_claimed"), "production_saas_not_claimed must be true")

    def test_real_customer_data_not_claimed_ready(self):
        self.assertTrue(self.safety.get("real_customer_data_not_claimed_ready"), "real_customer_data_not_claimed_ready must be true")

    def test_official_sdk_not_claimed(self):
        self.assertTrue(self.safety.get("official_sdk_not_claimed"), "official_sdk_not_claimed must be true")

    def test_live_postgres_not_claimed(self):
        self.assertTrue(self.safety.get("live_postgres_production_not_claimed"), "live_postgres_production_not_claimed must be true")

    def test_tenant_isolation_not_overclaimed(self):
        self.assertTrue(self.safety.get("tenant_isolation_not_overclaimed"), "tenant_isolation_not_overclaimed must be true")

    def test_admin_operator_not_overclaimed(self):
        self.assertTrue(self.safety.get("admin_operator_not_overclaimed"), "admin_operator_not_overclaimed must be true")

    def test_no_backend_src_changes(self):
        self.assertTrue(self.safety.get("no_backend_src_changes"), "no_backend_src_changes must be true")

    def test_no_api_behavior_changes(self):
        self.assertTrue(self.safety.get("no_api_behavior_changes"), "no_api_behavior_changes must be true")

    def test_no_migrations_changes(self):
        self.assertTrue(self.safety.get("no_migrations_db_schema_dependency_changes"), "no_migrations_db_schema_dependency_changes must be true")

    def test_no_sdk_implementation_changes(self):
        self.assertTrue(self.safety.get("no_sdk_implementation_changes"), "no_sdk_implementation_changes must be true")

    def test_no_package_publishing_metadata(self):
        self.assertTrue(self.safety.get("no_package_publishing_metadata"), "no_package_publishing_metadata must be true")

    def test_no_frontend_website_changes(self):
        self.assertTrue(self.safety.get("no_frontend_website_design_changes"), "no_frontend_website_design_changes must be true")

    def test_no_github_workflow_changes(self):
        self.assertTrue(self.safety.get("no_github_workflow_changes"), "no_github_workflow_changes must be true")

    def test_no_public_github_push(self):
        self.assertTrue(self.safety.get("no_public_github_push"), "no_public_github_push must be true")

    def test_no_visibility_change(self):
        self.assertTrue(self.safety.get("no_visibility_change"), "no_visibility_change must be true")

    def test_unrelated_website_files_excluded(self):
        self.assertTrue(self.safety.get("unrelated_website_files_excluded"), "unrelated_website_files_excluded must be true")


class TestGL207NoBoundaryViolations(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()

    def test_production_saas_no_go(self):
        impact = self.data.get("production_readiness_impact", {})
        self.assertEqual(impact.get("production_saas"), "NO-GO")

    def test_real_customer_data_no_go(self):
        impact = self.data.get("production_readiness_impact", {})
        self.assertEqual(impact.get("real_customer_data"), "NO-GO")

    def test_private_grant_data_no_go(self):
        impact = self.data.get("production_readiness_impact", {})
        self.assertEqual(impact.get("private_grant_institutional_data"), "NO-GO")

    def test_official_sdk_no_go(self):
        impact = self.data.get("production_readiness_impact", {})
        self.assertEqual(impact.get("official_sdk_package"), "NO-GO")

    def test_live_postgres_no_go(self):
        impact = self.data.get("production_readiness_impact", {})
        self.assertEqual(impact.get("live_postgresql_production"), "NO-GO")

    def test_developer_preview_confirmed(self):
        impact = self.data.get("production_readiness_impact", {})
        self.assertEqual(impact.get("developer_preview"), "CONFIRMED")

    def test_controlled_preview_confirmed(self):
        impact = self.data.get("production_readiness_impact", {})
        self.assertEqual(impact.get("controlled_preview_strict_boundaries"), "CONFIRMED")

    def test_sdk_not_official(self):
        sdk = self.data.get("sdk_claim_boundary", {})
        self.assertFalse(sdk.get("official_sdk"), "official_sdk must be false")

    def test_sdk_not_published(self):
        sdk = self.data.get("sdk_claim_boundary", {})
        self.assertFalse(sdk.get("package_published"), "package_published must be false")

    def test_live_postgres_not_executed(self):
        postgres = self.data.get("live_postgres_claim_boundary", {})
        self.assertFalse(postgres.get("live_validation_executed"), "live_validation_executed must be false")

    def test_production_dr_not_ready(self):
        dr = self.data.get("backup_restore_dr_claim_boundary", {})
        self.assertFalse(dr.get("production_dr_ready"), "production_dr_ready must be false")

    def test_pilot_not_started(self):
        pilot = self.data.get("first_external_controlled_pilot_boundary", {})
        self.assertFalse(pilot.get("pilot_started"), "pilot_started must be false")

    def test_website_files_excluded(self):
        web = self.data.get("website_marketing_deferral", {})
        self.assertTrue(web.get("unrelated_website_files_excluded"), "unrelated_website_files_excluded must be true")


class TestGL207DocContent(unittest.TestCase):
    def setUp(self):
        self.doc = _load_doc()

    def test_doc_has_issue_id(self):
        self.assertIn("gl-207", self.doc)

    def test_doc_states_developer_preview(self):
        self.assertIn("developer preview", self.doc)

    def test_doc_states_controlled_preview_strict_boundaries(self):
        self.assertIn("controlled preview", self.doc)
        self.assertIn("strict boundaries", self.doc)

    def test_doc_states_production_saas_no_go(self):
        self.assertIn("production saas", self.doc)
        self.assertIn("no-go", self.doc)

    def test_doc_states_real_customer_data_no_go(self):
        self.assertIn("real customer data", self.doc)

    def test_doc_states_private_grant_data_no_go(self):
        self.assertIn("private grant", self.doc)

    def test_doc_states_official_sdk_no_go(self):
        self.assertIn("official sdk", self.doc)

    def test_doc_states_live_postgres_no_go(self):
        self.assertIn("live postgresql", self.doc)

    def test_doc_states_internal_sdk_not_official(self):
        self.assertIn("not an official sdk", self.doc)

    def test_doc_states_controlled_preview_expansion_synthetic(self):
        self.assertIn("synthetic", self.doc)
        self.assertIn("demo data", self.doc)

    def test_doc_states_tenant_isolation_baseline_not_production_complete(self):
        self.assertIn("baseline implemented", self.doc)
        self.assertIn("not production-complete", self.doc)

    def test_doc_states_admin_operator_not_production_complete(self):
        self.assertIn("admin/operator", self.doc)
        self.assertIn("not a production tenant-management ui", self.doc)

    def test_doc_routes_security_to_advisories(self):
        self.assertIn("github security advisories", self.doc)

    def test_doc_has_no_exploit_details(self):
        import re
        # "no exploit details" and "No exploit details included" are safe safety confirmations.
        # Flag only affirmative exploit-detail content.
        affirmative = re.findall(r'(?<!no\s)(?<!not\s)exploit detail', self.doc)
        self.assertEqual(
            affirmative, [],
            "Doc must not contain affirmative exploit details",
        )
        self.assertNotIn("0day", self.doc)
        self.assertNotIn("zero-day", self.doc)

    def test_doc_has_no_real_secrets(self):
        for pattern in ["-----begin rsa private key", "-----begin ec private key",
                        "sk-", "eyjaaaaaa"]:
            self.assertNotIn(pattern, self.doc, f"Doc must not contain secret pattern: {pattern}")

    def test_doc_has_no_real_customer_data(self):
        self.assertNotIn("customer_id: real", self.doc)
        self.assertNotIn("real_customer", self.doc)

    def test_doc_has_controlled_preview_boundary_section(self):
        self.assertIn("controlled preview boundary", self.doc)

    def test_doc_has_allowed_claims_section(self):
        self.assertIn("allowed claims", self.doc)

    def test_doc_has_prohibited_claims_section(self):
        self.assertIn("prohibited claims", self.doc)

    def test_doc_has_stale_claim_corrections_section(self):
        self.assertIn("stale claim corrections", self.doc)

    def test_doc_has_sdk_claim_boundary_section(self):
        self.assertIn("sdk claim boundary", self.doc)

    def test_doc_has_tenant_workspace_claim_section(self):
        self.assertIn("tenant/workspace claim boundary", self.doc)

    def test_doc_has_admin_operator_claim_section(self):
        self.assertIn("admin/operator claim boundary", self.doc)

    def test_doc_has_live_postgres_claim_section(self):
        self.assertIn("live postgresql claim boundary", self.doc)

    def test_doc_has_backup_restore_dr_section(self):
        self.assertIn("backup/restore/dr claim boundary", self.doc)

    def test_doc_has_observability_section(self):
        self.assertIn("observability claim boundary", self.doc)

    def test_doc_has_first_external_pilot_section(self):
        self.assertIn("first external controlled pilot boundary", self.doc)

    def test_doc_has_website_marketing_deferral_section(self):
        self.assertIn("website/marketing deferral", self.doc)

    def test_doc_has_production_readiness_impact_section(self):
        self.assertIn("production readiness impact", self.doc)

    def test_doc_has_remaining_gaps_section(self):
        self.assertIn("remaining gaps", self.doc)

    def test_doc_has_risk_register_section(self):
        self.assertIn("risk register", self.doc)

    def test_doc_has_decision_section(self):
        self.assertIn("decision", self.doc)

    def test_doc_has_safety_confirmations_section(self):
        self.assertIn("safety confirmations", self.doc)

    def test_doc_has_recommended_next_issues_section(self):
        self.assertIn("recommended next issues", self.doc)

    def test_new_tenant_isolation_phrase_present(self):
        self.assertIn(
            "tenant/workspace isolation is not production-complete",
            self.doc,
            "Doc must include updated safety phrase: 'tenant/workspace isolation is not production-complete'",
        )


class TestGL207InputSourcesExist(unittest.TestCase):
    """Verify that the declared input sources actually exist in the repo."""

    def _check_exists(self, relpath):
        self.assertTrue(
            os.path.exists(_path(relpath)),
            f"Input source must exist: {relpath}",
        )

    def test_gl206_doc_exists(self):
        self._check_exists("docs/admin_operator_tenant_control_plane.md")

    def test_gl206_json_exists(self):
        self._check_exists("docs/examples/gl206/admin_operator_tenant_control_plane.json")

    def test_gl205_doc_exists(self):
        self._check_exists("docs/live_postgres_backup_observability_baseline.md")

    def test_gl205_json_exists(self):
        self._check_exists("docs/examples/gl205/live_postgres_backup_observability_baseline.json")

    def test_gl204_doc_exists(self):
        self._check_exists("docs/production_ops_go_no_go_v3.md")

    def test_gl204_json_exists(self):
        self._check_exists("docs/examples/gl204/production_ops_go_no_go_v3.json")

    def test_gl203c_doc_exists(self):
        self._check_exists("docs/sdk_prototype_packaging_boundary.md")

    def test_gl203b_doc_exists(self):
        self._check_exists("docs/openapi_api_contract_cleanup.md")

    def test_gl203_doc_exists(self):
        self._check_exists("docs/api_contract_sdk_packaging_decision.md")

    def test_gl202_doc_exists(self):
        self._check_exists("docs/persistence_postgres_migration_readiness.md")

    def test_gl201_doc_exists(self):
        self._check_exists("docs/production_auth_secrets_config_hardening.md")

    def test_gl200c_doc_exists(self):
        self._check_exists("docs/tenant_workspace_api_audit_regression_completion.md")

    def test_gl200b_doc_exists(self):
        self._check_exists("docs/tenant_workspace_isolation_implementation_baseline.md")

    def test_gl200a_doc_exists(self):
        self._check_exists("docs/tenant_workspace_isolation_design_pack.md")

    def test_gl199_doc_exists(self):
        self._check_exists("docs/production_readiness_gap_report_v2.md")

    def test_gl198_doc_exists(self):
        self._check_exists("docs/controlled_preview_boundary_pack.md")

    def test_readme_exists(self):
        self._check_exists("README.md")

    def test_security_exists(self):
        self._check_exists("SECURITY.md")

    def test_agents_exists(self):
        self._check_exists("AGENTS.md")

    def test_llms_txt_exists(self):
        self._check_exists("llms.txt")

    def test_llms_full_txt_exists(self):
        self._check_exists("llms-full.txt")

    def test_openapi_yaml_exists(self):
        self._check_exists("docs/openapi.yaml")


class TestGL207ReadmeClaimConsistency(unittest.TestCase):
    """README must reflect accurate post-GL-206 tenant isolation claim."""

    def setUp(self):
        self.readme = _read("README.md").lower()

    def test_readme_no_production_saas_claim(self):
        self.assertNotIn("production saas ready", self.readme)
        self.assertNotIn("production saas readiness: ready", self.readme)

    def test_readme_no_official_sdk_claim(self):
        self.assertNotIn("official sdk available", self.readme)
        self.assertNotIn("official sdk package", self.readme)

    def test_readme_no_live_postgres_production_claim(self):
        self.assertNotIn("live postgresql production ready", self.readme)

    def test_readme_tenant_isolation_not_simply_not_implemented(self):
        # After GL-207, README should NOT simply say "Not implemented" for tenant isolation
        # The status table row must use the updated accurate claim
        self.assertNotIn("tenant/workspace isolation | **not implemented**", self.readme)

    def test_readme_has_controlled_preview_or_developer_preview(self):
        self.assertTrue(
            "developer preview" in self.readme or "controlled preview" in self.readme,
            "README must mention Developer Preview or Controlled Preview posture",
        )


class TestGL207SecurityMdClaimConsistency(unittest.TestCase):
    """SECURITY.md must reflect accurate post-GL-206 tenant isolation claim."""

    def setUp(self):
        self.doc = _read("SECURITY.md").lower()

    def test_security_routes_to_advisories(self):
        self.assertIn("github security advisories", self.doc)

    def test_security_no_production_saas_claim(self):
        self.assertNotIn("production saas ready", self.doc)

    def test_security_tenant_isolation_not_simply_not_implemented(self):
        # After GL-207, SECURITY.md should NOT simply say "Not implemented"
        self.assertNotIn("tenant/workspace isolation | **not implemented**", self.doc)


class TestGL207AgentsMdClaimConsistency(unittest.TestCase):
    """AGENTS.md must reflect accurate post-GL-206 tenant isolation claim."""

    def setUp(self):
        self.doc = _read("AGENTS.md").lower()

    def test_agents_md_has_developer_preview(self):
        self.assertIn("developer preview", self.doc)

    def test_agents_md_no_production_saas_claim(self):
        self.assertNotIn("production saas ready", self.doc)
        self.assertIn("not a production saas", self.doc)

    def test_agents_md_has_updated_tenant_safety_phrase(self):
        self.assertIn(
            "tenant/workspace isolation is not production-complete",
            self.doc,
            "AGENTS.md must include updated safety phrase 'tenant/workspace isolation is not production-complete'",
        )

    def test_agents_md_tenant_isolation_not_simply_not_implemented_in_status_table(self):
        self.assertNotIn("tenant/workspace isolation | **not implemented**", self.doc)


class TestGL207LlmsTxtClaimConsistency(unittest.TestCase):
    """llms.txt must reflect accurate post-GL-206 tenant isolation claim."""

    def setUp(self):
        self.doc = _read("llms.txt").lower()

    def test_llms_txt_has_not_production_saas(self):
        self.assertIn("not a production saas", self.doc)

    def test_llms_txt_has_updated_safety_phrase(self):
        self.assertIn(
            "tenant/workspace isolation is not production-complete",
            self.doc,
            "llms.txt must include updated safety phrase 'tenant/workspace isolation is not production-complete'",
        )


class TestGL207OpenAPIClaimConsistency(unittest.TestCase):
    """docs/openapi.yaml must not contain production/official-SDK/live-postgres overclaims."""

    def setUp(self):
        self.doc = _read("docs/openapi.yaml").lower()

    def test_openapi_has_developer_preview(self):
        self.assertIn("developer preview", self.doc)

    def test_openapi_has_not_production_saas(self):
        self.assertIn("not a production saas", self.doc)

    def test_openapi_no_official_sdk_overclaim(self):
        import re
        # "No official SDK/package is claimed" is the correct caveat — not an overclaim.
        # Only flag an affirmative claim that an official SDK is available.
        affirmative = re.findall(
            r'(?<!no\s)(?<!not\s)(?<!never\s)official sdk(?!/package is claimed)',
            self.doc,
        )
        self.assertEqual(
            affirmative, [],
            "OpenAPI must not affirmatively claim an official SDK is available",
        )

    def test_openapi_no_live_postgres_production_overclaim(self):
        self.assertNotIn("live postgresql production ready", self.doc)


class TestGL207ScopeGuard(unittest.TestCase):
    """Verify no backend/src, migration, SDK implementation, dependency, or workflow changes."""

    def setUp(self):
        self.changed = _branch_diff_files()

    def test_no_backend_src_changes(self):
        violations = [f for f in self.changed if f.startswith("backend/src/")]
        self.assertEqual(
            violations, [],
            f"GL-207 must not change backend/src: {violations}",
        )

    def test_no_migration_changes(self):
        violations = [f for f in self.changed if "migrations" in f]
        self.assertEqual(
            violations, [],
            f"GL-207 must not change migrations: {violations}",
        )

    def test_no_dependency_manifest_changes(self):
        forbidden = {"requirements.txt", "requirements-dev.txt", "setup.py",
                     "pyproject.toml", "package.json", "package-lock.json"}
        violations = [f for f in self.changed if os.path.basename(f) in forbidden]
        self.assertEqual(
            violations, [],
            f"GL-207 must not change dependency manifests: {violations}",
        )

    def test_no_sdk_implementation_changes(self):
        violations = [f for f in self.changed
                      if "sdk_prototype" in f and f.endswith(".py")]
        self.assertEqual(
            violations, [],
            f"GL-207 must not change SDK prototype implementation: {violations}",
        )

    def test_no_github_workflow_changes(self):
        violations = [f for f in self.changed if f.startswith(".github/")]
        self.assertEqual(
            violations, [],
            f"GL-207 must not change GitHub workflows: {violations}",
        )

    def test_no_frontend_website_design_changes(self):
        violations = [f for f in self.changed
                      if f.startswith(("frontend/", "website/", "design/"))]
        self.assertEqual(
            violations, [],
            f"GL-207 must not change frontend/website/design: {violations}",
        )

    def test_no_unrelated_website_files(self):
        unrelated = {
            "website-design/",
            "docs/website_design_workspace_import_report.md",
            "docs/website_design_workspace_import_report_dirty_stop.md",
        }
        for entry in unrelated:
            for f in self.changed:
                self.assertFalse(
                    f.startswith(entry) or f == entry,
                    f"Unrelated website file must not be included in GL-207: {f}",
                )

    def test_allowed_files_only(self):
        allowed_prefixes = (
            "docs/claim_safety_controlled_preview_boundary.md",
            "docs/examples/gl207/",
            "backend/tests/test_gl207_",
            "README.md",
            "SECURITY.md",
            "AGENTS.md",
            "llms.txt",
            "llms-full.txt",
            "docs/openapi.yaml",
        )
        for f in self.changed:
            is_allowed = any(
                f == prefix or f.startswith(prefix)
                for prefix in allowed_prefixes
            )
            self.assertTrue(
                is_allowed,
                f"Changed file not in GL-207 allowed scope: {f}",
            )


if __name__ == "__main__":
    unittest.main()
