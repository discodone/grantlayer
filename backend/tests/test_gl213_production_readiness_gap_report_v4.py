"""Tests for GL-213 Production Readiness Gap Report v4."""

import json
import os
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MD_PATH = os.path.join(REPO_ROOT, "docs", "production_readiness_gap_report_v4.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl213",
    "production_readiness_gap_report_v4.json",
)


def _load_json():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_md():
    with open(MD_PATH, encoding="utf-8") as f:
        return f.read()


class TestGL213FilesExist(unittest.TestCase):
    def test_markdown_exists(self):
        self.assertTrue(os.path.isfile(MD_PATH), f"Missing: {MD_PATH}")

    def test_json_exists(self):
        self.assertTrue(os.path.isfile(JSON_PATH), f"Missing: {JSON_PATH}")

    def test_json_valid(self):
        data = _load_json()
        self.assertIsInstance(data, dict)


class TestGL213JSONFields(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()

    def test_issue_id(self):
        self.assertEqual(self.data["issue_id"], "GL-213")

    def test_result_present_and_allowed(self):
        allowed = {"ready_for_merge", "blocked"}
        self.assertIn(self.data["result"], allowed)

    def test_decision_present(self):
        self.assertIn("decision", self.data)
        self.assertTrue(len(self.data["decision"]) > 0)

    def test_input_sources_reviewed(self):
        self.assertIn("input_sources_reviewed", self.data)
        self.assertIsInstance(self.data["input_sources_reviewed"], list)
        self.assertGreater(len(self.data["input_sources_reviewed"]), 0)

    def test_current_state_summary(self):
        self.assertIn("current_state_summary", self.data)
        self.assertIsInstance(self.data["current_state_summary"], dict)

    def test_readiness_tier_summary(self):
        self.assertIn("readiness_tier_summary", self.data)
        self.assertIsInstance(self.data["readiness_tier_summary"], dict)

    def test_progress_since_prior_gap_reports(self):
        self.assertIn("progress_since_prior_gap_reports", self.data)
        self.assertIsInstance(self.data["progress_since_prior_gap_reports"], dict)

    def test_production_blocker_matrix(self):
        self.assertIn("production_blocker_matrix", self.data)
        self.assertIsInstance(self.data["production_blocker_matrix"], dict)

    def test_production_go_no_go_matrix(self):
        self.assertIn("production_go_no_go_matrix", self.data)
        self.assertIsInstance(self.data["production_go_no_go_matrix"], dict)

    def test_real_data_readiness_assessment(self):
        self.assertIn("real_data_readiness_assessment", self.data)

    def test_private_grant_institutional_data_assessment(self):
        self.assertIn("private_grant_institutional_data_assessment", self.data)

    def test_production_saas_readiness_assessment(self):
        self.assertIn("production_saas_readiness_assessment", self.data)

    def test_public_snapshot_readiness_assessment(self):
        self.assertIn("public_snapshot_readiness_assessment", self.data)

    def test_external_review_readiness_assessment(self):
        self.assertIn("external_review_readiness_assessment", self.data)

    def test_sdk_package_readiness_assessment(self):
        self.assertIn("sdk_package_readiness_assessment", self.data)

    def test_live_postgres_readiness_assessment(self):
        self.assertIn("live_postgres_readiness_assessment", self.data)

    def test_observability_incident_readiness_assessment(self):
        self.assertIn("observability_incident_readiness_assessment", self.data)

    def test_backup_restore_dr_readiness_assessment(self):
        self.assertIn("backup_restore_dr_readiness_assessment", self.data)

    def test_tenant_workspace_readiness_assessment(self):
        self.assertIn("tenant_workspace_readiness_assessment", self.data)

    def test_admin_operator_readiness_assessment(self):
        self.assertIn("admin_operator_readiness_assessment", self.data)

    def test_data_governance_audit_readiness_assessment(self):
        self.assertIn("data_governance_audit_readiness_assessment", self.data)

    def test_security_compliance_readiness_assessment(self):
        self.assertIn("security_compliance_readiness_assessment", self.data)

    def test_risk_register_v4(self):
        self.assertIn("risk_register_v4", self.data)
        self.assertIsInstance(self.data["risk_register_v4"], list)
        self.assertGreater(len(self.data["risk_register_v4"]), 0)

    def test_recommended_compact_roadmap(self):
        self.assertIn("recommended_compact_roadmap", self.data)
        self.assertIsInstance(self.data["recommended_compact_roadmap"], dict)

    def test_findings(self):
        self.assertIn("findings", self.data)
        self.assertIsInstance(self.data["findings"], list)
        self.assertGreater(len(self.data["findings"]), 0)

    def test_safety_confirmations(self):
        self.assertIn("safety_confirmations", self.data)
        self.assertIsInstance(self.data["safety_confirmations"], dict)

    def test_recommended_next_issues(self):
        self.assertIn("recommended_next_issues", self.data)
        self.assertIsInstance(self.data["recommended_next_issues"], list)
        self.assertGreater(len(self.data["recommended_next_issues"]), 0)


class TestGL213JSONSafetyConfirmations(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.sc = self.data["safety_confirmations"]

    def test_no_production_saas_claim(self):
        self.assertTrue(self.sc.get("production_saas_no_go", False))

    def test_no_real_customer_private_grant_data_claim(self):
        self.assertTrue(
            self.sc.get("real_customer_private_grant_institutional_data_no_go", False)
        )

    def test_no_official_sdk_package_claim(self):
        self.assertTrue(self.sc.get("official_sdk_package_no_go", False))

    def test_no_compliance_certification_claim(self):
        self.assertTrue(self.sc.get("compliance_certification_no_go", False))

    def test_ephemeral_postgres_not_overclaimed(self):
        self.assertTrue(
            self.sc.get("ephemeral_postgres_validation_not_overclaimed", False)
        )

    def test_public_publish_no_go(self):
        self.assertTrue(self.sc.get("public_publish_no_go_in_gl213", False))

    def test_public_snapshot_requires_separate_issue(self):
        self.assertTrue(
            self.sc.get(
                "public_snapshot_requires_separate_issue_and_explicit_approval", False
            )
        )

    def test_security_sensitive_reports_routed(self):
        self.assertTrue(
            self.sc.get(
                "security_sensitive_reports_route_to_github_security_advisories", False
            )
        )

    def test_no_exploit_details(self):
        self.assertTrue(self.sc.get("no_exploit_details_included", False))

    def test_no_real_secrets(self):
        self.assertTrue(self.sc.get("no_real_secrets_included", False))

    def test_no_real_customer_private_data(self):
        self.assertTrue(self.sc.get("no_real_customer_private_data_included", False))

    def test_no_backend_src_changes(self):
        self.assertTrue(self.sc.get("no_backend_src_changes", False))

    def test_no_api_behavior_changes(self):
        self.assertTrue(self.sc.get("no_api_behavior_changes", False))

    def test_no_migrations_db_schema_dependency_changes(self):
        self.assertTrue(
            self.sc.get("no_migrations_db_schema_dependency_changes", False)
        )

    def test_no_github_workflow_changes(self):
        self.assertTrue(self.sc.get("no_github_workflow_changes", False))

    def test_no_snapshot_publish_script_changes(self):
        self.assertTrue(self.sc.get("no_snapshot_publish_script_changes", False))

    def test_no_package_publishing_metadata(self):
        self.assertTrue(self.sc.get("no_package_publishing_metadata", False))

    def test_no_sdk_package_metadata(self):
        self.assertTrue(self.sc.get("no_sdk_package_metadata", False))

    def test_no_setup_py(self):
        self.assertTrue(self.sc.get("no_setup_py", False))

    def test_no_sdk_pyproject_toml(self):
        self.assertTrue(self.sc.get("no_sdk_pyproject_toml", False))

    def test_no_package_json(self):
        self.assertTrue(self.sc.get("no_package_json", False))

    def test_unrelated_website_design_import_files_excluded(self):
        self.assertTrue(
            self.sc.get("unrelated_website_design_import_files_excluded", False)
        )

    def test_developer_preview_controlled_preview_boundary(self):
        self.assertTrue(
            self.sc.get(
                "developer_preview_controlled_preview_with_strict_boundaries", False
            )
        )

    def test_controlled_external_review_strict_boundaries_only(self):
        self.assertTrue(
            self.sc.get(
                "controlled_external_review_allowed_with_strict_boundaries_only", False
            )
        )


class TestGL213JSONGoNoGoMatrix(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.matrix = self.data["production_go_no_go_matrix"]

    def test_production_saas_no_go(self):
        self.assertIn("NO-GO", self.matrix["production_saas"]["decision"])

    def test_real_customer_data_no_go(self):
        self.assertIn("NO-GO", self.matrix["real_customer_data_pilot"]["decision"])

    def test_official_sdk_no_go(self):
        self.assertIn("NO-GO", self.matrix["official_sdk_package"]["decision"])

    def test_controlled_external_review_allowed(self):
        self.assertIn(
            "GO", self.matrix["controlled_external_technical_review"]["decision"]
        )

    def test_developer_preview_go(self):
        self.assertIn("GO", self.matrix["developer_preview"]["decision"])

    def test_private_grant_institutional_no_go(self):
        self.assertIn(
            "NO-GO",
            self.matrix["private_grant_institutional_data_pilot"]["decision"],
        )


class TestGL213RiskRegister(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.risks = self.data["risk_register_v4"]

    def test_all_risks_have_severity(self):
        for r in self.risks:
            self.assertIn("severity", r, f"Risk {r.get('id')} missing severity")

    def test_all_risks_have_current_status(self):
        for r in self.risks:
            self.assertIn(
                "current_status", r, f"Risk {r.get('id')} missing current_status"
            )

    def test_all_risks_have_mitigation_completed(self):
        for r in self.risks:
            self.assertIn(
                "mitigation_completed",
                r,
                f"Risk {r.get('id')} missing mitigation_completed",
            )

    def test_all_risks_have_blocks_production_saas(self):
        for r in self.risks:
            self.assertIn(
                "blocks_production_saas",
                r,
                f"Risk {r.get('id')} missing blocks_production_saas",
            )


class TestGL213ProductionBlockerMatrix(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.matrix = self.data["production_blocker_matrix"]

    def test_p0_blockers_present(self):
        self.assertIn("p0_production_blockers", self.matrix)
        self.assertIsInstance(self.matrix["p0_production_blockers"], list)
        self.assertGreater(len(self.matrix["p0_production_blockers"]), 0)

    def test_p1_blockers_present(self):
        self.assertIn("p1_production_hardening_blockers", self.matrix)

    def test_p2_blockers_present(self):
        self.assertIn("p2_maturity_blockers", self.matrix)


class TestGL213MarkdownContent(unittest.TestCase):
    def setUp(self):
        self.md = _load_md()

    def test_contains_gl213_id(self):
        self.assertIn("GL-213", self.md)

    def test_states_developer_preview_controlled_preview(self):
        lower = self.md.lower()
        self.assertIn("developer preview", lower)
        self.assertIn("controlled preview", lower)

    def test_states_production_saas_no_go(self):
        lower = self.md.lower()
        self.assertIn("production saas remains no-go", lower)

    def test_states_real_customer_private_grant_data_no_go(self):
        lower = self.md.lower()
        self.assertIn("real customer", lower)
        self.assertIn("no-go", lower)

    def test_states_official_sdk_package_no_go(self):
        lower = self.md.lower()
        self.assertIn("official sdk", lower)
        self.assertIn("no-go", lower)

    def test_states_compliance_certification_no_go(self):
        lower = self.md.lower()
        self.assertIn("compliance certification", lower)
        self.assertIn("no-go", lower)

    def test_states_ephemeral_postgres_not_production_readiness(self):
        lower = self.md.lower()
        self.assertIn("ephemeral", lower)
        self.assertIn("production postgresql readiness remains no-go", lower)

    def test_states_public_publish_no_go(self):
        lower = self.md.lower()
        # phrase may span a line-wrap; check both components
        self.assertIn("public publish", lower)
        self.assertIn("no-go in gl-213", lower)

    def test_states_public_snapshot_requires_separate_issue(self):
        lower = self.md.lower()
        self.assertIn("separate", lower)
        self.assertIn("explicit approval", lower)

    def test_routes_security_reports_to_advisories(self):
        lower = self.md.lower()
        self.assertIn("github security advisories", lower)

    def test_no_exploit_details(self):
        lower = self.md.lower()
        self.assertIn("no exploit details", lower)

    def test_no_real_secrets(self):
        lower = self.md.lower()
        self.assertIn("no real secrets", lower)

    def test_no_real_customer_private_data(self):
        lower = self.md.lower()
        self.assertIn("no real customer/private data", lower)

    def test_gap_report_not_declaration(self):
        lower = self.md.lower()
        self.assertIn("readiness gap report, not a production readiness declaration", lower)

    def test_unrelated_website_design_excluded(self):
        lower = self.md.lower()
        self.assertIn("website-design", lower)
        self.assertIn("excluded", lower)


class TestGL213ForbiddenArtifacts(unittest.TestCase):
    """Verify that GL-213 did not create forbidden files or directories."""

    def test_no_public_export_directory(self):
        forbidden_dirs = [
            os.path.join(REPO_ROOT, "public-export"),
            os.path.join(REPO_ROOT, "public_export"),
            os.path.join(REPO_ROOT, "dist"),
            os.path.join(REPO_ROOT, "release"),
        ]
        for d in forbidden_dirs:
            self.assertFalse(
                os.path.isdir(d), f"Forbidden public export directory exists: {d}"
            )

    def test_no_setup_py(self):
        self.assertFalse(
            os.path.isfile(os.path.join(REPO_ROOT, "setup.py")),
            "setup.py must not exist",
        )

    def test_no_sdk_pyproject_toml(self):
        pyproject = os.path.join(REPO_ROOT, "pyproject.toml")
        if os.path.isfile(pyproject):
            with open(pyproject, encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("[build-system]", content, "pyproject.toml must not contain [build-system] (SDK packaging)")

    def test_no_package_json_at_root(self):
        self.assertFalse(
            os.path.isfile(os.path.join(REPO_ROOT, "package.json")),
            "package.json must not exist at repo root",
        )

    def test_no_package_lock_json_at_root(self):
        self.assertFalse(
            os.path.isfile(os.path.join(REPO_ROOT, "package-lock.json")),
            "package-lock.json must not exist at repo root",
        )


class TestGL213PublicSnapshotSafety(unittest.TestCase):
    """Verify no public snapshot export directory was created."""

    def test_no_gl181_snapshot_directory_in_tree(self):
        for name in os.listdir(REPO_ROOT):
            self.assertFalse(
                name.startswith("gl181-public-snapshot"),
                f"Public snapshot directory found: {name}",
            )

    def test_no_public_snapshot_subdir(self):
        for name in os.listdir(REPO_ROOT):
            lower = name.lower()
            self.assertFalse(
                "public-snapshot" in lower and os.path.isdir(
                    os.path.join(REPO_ROOT, name)
                ),
                f"Public snapshot directory found: {name}",
            )


if __name__ == "__main__":
    unittest.main()
