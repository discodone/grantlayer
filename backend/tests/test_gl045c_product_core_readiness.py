"""GL-045-C — Final Product Core Readiness Check.

Verifies that all Product Core modules, builders, API routes, and
legacy-cleanup expectations are met after GL-037 through GL-045.

This test must not introduce new product features.
It must not introduce new API endpoints.
It must not introduce persistence, database schema changes, migrations,
UI, OAuth, JWT, SSO, blockchain, payments, or SaaS features.
"""

import os
import sys
import unittest
import tempfile
import importlib
import importlib.util

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestGl045cProductCoreReadiness(unittest.TestCase):
    """GL-045-C: Final Product Core Readiness Check."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_enable_demo = os.environ.get("GRANTLAYER_ENABLE_DEMO_ENDPOINTS")

        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN"] = "bootstrap-token"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "test-admin"

        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if self._orig_db is None:
            os.environ.pop("GRANTLAYER_DB", None)
        else:
            os.environ["GRANTLAYER_DB"] = self._orig_db

        for key, orig in [
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", self._orig_enable_demo),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    # ──────────────────────────────────────────────
    # 1. Expected product-core modules are importable
    # ──────────────────────────────────────────────
    def test_modules_importable(self):
        modules = [
            "backend.src.evidence_completeness",
            "backend.src.compliance_gap_report",
            "backend.src.agent_permissions",
            "backend.src.agent_permission_profiles",
            "backend.src.agent_permission_assignments",
            "backend.src.approval_rules",
            "backend.src.approval_lifecycle",
            "backend.src.decision_provenance",
            "backend.src.auditor_export",
            "backend.src.policy_requirements",
            "backend.src.compliance_readiness",
        ]
        for mod_name in modules:
            with self.subTest(module=mod_name):
                spec = importlib.util.find_spec(mod_name)
                self.assertIsNotNone(spec, f"Module {mod_name} not found")
                mod = importlib.import_module(mod_name)
                self.assertIsNotNone(mod)

    # ──────────────────────────────────────────────
    # 2. Expected builder/evaluator functions exist
    # ──────────────────────────────────────────────
    def test_evaluate_agent_permission_exists(self):
        from backend.src.agent_permissions import evaluate_agent_permission
        self.assertTrue(callable(evaluate_agent_permission))

    def test_expand_agent_permission_profiles_exists(self):
        from backend.src.agent_permission_profiles import expand_agent_permission_profiles
        self.assertTrue(callable(expand_agent_permission_profiles))

    def test_resolve_agent_permission_assignment_exists(self):
        from backend.src.agent_permission_assignments import resolve_agent_permission_assignment
        self.assertTrue(callable(resolve_agent_permission_assignment))

    def test_evaluate_approval_requirements_exists(self):
        from backend.src.approval_rules import evaluate_approval_requirements
        self.assertTrue(callable(evaluate_approval_requirements))

    def test_build_approval_request_lifecycle_exists(self):
        from backend.src.approval_lifecycle import build_approval_request_lifecycle
        self.assertTrue(callable(build_approval_request_lifecycle))

    def test_transition_approval_request_exists(self):
        from backend.src.approval_lifecycle import transition_approval_request
        self.assertTrue(callable(transition_approval_request))

    def test_build_decision_provenance_v2_exists(self):
        from backend.src.decision_provenance import build_decision_provenance_v2
        self.assertTrue(callable(build_decision_provenance_v2))

    def test_build_institutional_auditor_export_exists(self):
        from backend.src.auditor_export import build_institutional_auditor_export
        self.assertTrue(callable(build_institutional_auditor_export))

    def test_evaluate_policy_requirements_exists(self):
        from backend.src.policy_requirements import evaluate_policy_requirements
        self.assertTrue(callable(evaluate_policy_requirements))

    def test_build_compliance_readiness_summary_exists(self):
        from backend.src.compliance_readiness import build_compliance_readiness_summary
        self.assertTrue(callable(build_compliance_readiness_summary))

    # ──────────────────────────────────────────────
    # 3. Expected API paths are present in server.py
    # ──────────────────────────────────────────────
    def test_api_paths_present_in_server_py(self):
        server_path = os.path.join(os.path.dirname(__file__), "..", "src", "server.py")
        with open(server_path, "r", encoding="utf-8") as f:
            source = f.read()

        expected_paths = [
            '"/agent-permissions/evaluate"',
            '"/agent-permissions/profiles"',
            '"/agent-permissions/profiles/([^/]+)"',
            '"/agent-permissions/assignments/resolve"',
            '"/approvals/evaluate"',
            '"/approvals/lifecycle/build"',
            '"/approvals/lifecycle/transition"',
            '"/decision-provenance/v2/build"',
            '"/auditor/exports/build"',
            '"/policy-requirements/evaluate"',
            '"/compliance/readiness/build"',
            '"/evidence/executions/([^/]+)/verify"',
            '"/evidence/executions/([^/]+)/completeness"',
            '"/compliance/gaps/executions/([^/]+)"',
            '"/auditor/reports/executions/([^/]+)"',
        ]
        for path_literal in expected_paths:
            with self.subTest(path=path_literal):
                self.assertIn(path_literal, source, f"Expected path {path_literal} not found in server.py")

    # ──────────────────────────────────────────────
    # 4. Expected API paths are present in OpenAPI where documented
    # ──────────────────────────────────────────────
    def test_api_paths_present_in_openapi_yaml(self):
        openapi_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "openapi.yaml")
        with open(openapi_path, "r", encoding="utf-8") as f:
            source = f.read()

        # These must be documented in OpenAPI
        expected_openapi_paths = [
            "/agent-permissions/evaluate:",
            "/agent-permissions/profiles:",
            "/agent-permissions/profiles/{profileName}:",
            "/agent-permissions/assignments/resolve:",
            "/approvals/evaluate:",
            "/approvals/lifecycle/build:",
            "/approvals/lifecycle/transition:",
            "/decision-provenance/v2/build:",
            "/evidence/executions/{id}/verify:",
        ]
        for path_literal in expected_openapi_paths:
            with self.subTest(path=path_literal):
                self.assertIn(path_literal, source, f"Expected path {path_literal} not found in openapi.yaml")

        # These are also expected to be in OpenAPI (server.py has them)
        additional_paths = [
            "/auditor/exports/build:",
            "/policy-requirements/evaluate:",
            "/compliance/readiness/build:",
            "/evidence/executions/{id}/completeness:",
            "/compliance/gaps/executions/{id}:",
            "/auditor/reports/executions/{id}:",
        ]
        for path_literal in additional_paths:
            with self.subTest(path=path_literal):
                self.assertIn(path_literal, source, f"Expected path {path_literal} not found in openapi.yaml")

    # ──────────────────────────────────────────────
    # 5. Wrong/legacy files are absent
    # ──────────────────────────────────────────────
    def test_legacy_files_absent(self):
        repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
        forbidden = [
            "backend/src/institutional_auditor_export.py",
            "backend/tests/test_gl042a_institutional_auditor_export.py",
            "backend/src/agent_permission_assignment_resolver.py",
            "backend/tests/test_gl039c1_agent_permission_assignment_resolver.py",
            "backend/src/provenance_summary_v2.py",
            "backend/tests/test_gra111_gl045a_error_consistency.py",
        ]
        for rel_path in forbidden:
            full_path = os.path.join(repo_root, rel_path)
            with self.subTest(path=rel_path):
                self.assertFalse(os.path.exists(full_path), f"Forbidden legacy file must not exist: {rel_path}")

    # ──────────────────────────────────────────────
    # 6. docs/product_core_readiness.md exists and is valid
    # ──────────────────────────────────────────────
    def test_readiness_doc_exists(self):
        doc_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "product_core_readiness.md")
        self.assertTrue(os.path.isfile(doc_path), "docs/product_core_readiness.md must exist")

    def test_readiness_doc_content(self):
        doc_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "product_core_readiness.md")
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Must mention GL-037 through GL-045
        for sprint in ["GL-037", "GL-038", "GL-039", "GL-040", "GL-041", "GL-042", "GL-043", "GL-044", "GL-045"]:
            with self.subTest(sprint=sprint):
                self.assertIn(sprint, content, f"Readiness doc must mention {sprint}")

        # Must state no blockchain dependency
        self.assertIn("blockchain", content.lower())
        # Must state no UI is part of the API-layer product core
        self.assertIn("UI", content)
        # Must list completed product-core capabilities
        self.assertIn("Evidence", content)
        self.assertIn("Compliance", content)
        self.assertIn("Agent Permission", content)
        self.assertIn("Approval", content)
        self.assertIn("Decision Provenance", content)
        self.assertIn("Auditor", content)
        self.assertIn("Policy", content)

    # ──────────────────────────────────────────────
    # 7. Existing test suites still pass (import/load check)
    # ──────────────────────────────────────────────
    def test_gl045a_test_module_loads(self):
        import backend.tests.test_gl045a_api_contract_consistency as mod
        self.assertTrue(hasattr(mod, "TestGl045aApiContractConsistency"))

    def test_gl045b_test_module_loads(self):
        import backend.tests.test_gl045b_security_secrets_regression as mod
        self.assertTrue(hasattr(mod, "TestSecretContextLeakage"))

    def test_gl044a_test_module_loads(self):
        import backend.tests.test_gl044a_compliance_readiness as mod
        self.assertTrue(hasattr(mod, "TestComplianceReadinessBuilder"))

    def test_gl044b_test_module_loads(self):
        import backend.tests.test_gl044b_compliance_readiness_api as mod
        self.assertTrue(hasattr(mod, "TestComplianceReadinessDashboardAPI"))

    def test_gl043a_test_module_loads(self):
        import backend.tests.test_gl043a_policy_requirements as mod
        self.assertTrue(hasattr(mod, "TestModuleImportable"))

    def test_gl043b_test_module_loads(self):
        import backend.tests.test_gl043b_policy_requirements_api as mod
        self.assertTrue(hasattr(mod, "TestPolicyRequirementsAPI"))

    def test_gl042a_test_module_loads(self):
        import backend.tests.test_gl042a_auditor_export as mod
        self.assertTrue(hasattr(mod, "TestAuditorExportBuilder"))

    def test_gl042b_test_module_loads(self):
        import backend.tests.test_gl042b_auditor_export_api as mod
        self.assertTrue(hasattr(mod, "TestAuditorExportAPI"))

    def test_gl041a_test_module_loads(self):
        import backend.tests.test_gl041a_decision_provenance as mod
        self.assertTrue(hasattr(mod, "TestDecisionProvenanceV2"))

    def test_gl041b_test_module_loads(self):
        import backend.tests.test_gl041b_decision_provenance_api as mod
        self.assertTrue(hasattr(mod, "TestDecisionProvenanceV2API"))

    def test_gl040a1_test_module_loads(self):
        import backend.tests.test_gl040a1_approval_rules as mod
        self.assertTrue(hasattr(mod, "TestApprovalRulesImportable"))

    def test_gl040a2_test_module_loads(self):
        import backend.tests.test_gl040a2_approval_rule_api as mod
        self.assertTrue(hasattr(mod, "TestApprovalRuleEvaluationAPI"))

    def test_gl040b_test_module_loads(self):
        import backend.tests.test_gl040b_approval_lifecycle as mod
        self.assertTrue(hasattr(mod, "TestBuildApprovalRequestLifecycle"))

    def test_gl040c_test_module_loads(self):
        import backend.tests.test_gl040c_approval_lifecycle_api as mod
        self.assertTrue(hasattr(mod, "TestApprovalLifecycleAPI"))

    def test_gl039a1_test_module_loads(self):
        import backend.tests.test_gl039a1_agent_permissions as mod
        self.assertTrue(hasattr(mod, "TestAgentPermissionScopeEvaluator"))

    def test_gl039a2_test_module_loads(self):
        import backend.tests.test_gl039a2_agent_permission_api as mod
        self.assertTrue(hasattr(mod, "TestAgentPermissionEvaluationAPI"))

    def test_gl039b1_test_module_loads(self):
        import backend.tests.test_gl039b1_agent_permission_profiles as mod
        self.assertTrue(hasattr(mod, "TestAgentPermissionScopeProfiles"))

    def test_gl039b2_test_module_loads(self):
        import backend.tests.test_gl039b2_agent_permission_profiles_api as mod
        self.assertTrue(hasattr(mod, "TestAgentPermissionProfilesAPI"))

    def test_gl039c1_test_module_loads(self):
        import backend.tests.test_gl039c1_agent_permission_assignments as mod
        self.assertTrue(hasattr(mod, "TestAgentPermissionAssignments"))

    def test_gl039c2_test_module_loads(self):
        import backend.tests.test_gl039c2_agent_permission_assignments_api as mod
        self.assertTrue(hasattr(mod, "TestAgentPermissionAssignmentsAPI"))

    def test_gl038a1_test_module_loads(self):
        import backend.tests.test_gl038a1_evidence_completeness as mod
        self.assertTrue(hasattr(mod, "TestEvidenceCompletenessBuilder"))

    def test_gl038a2_test_module_loads(self):
        import backend.tests.test_gl038a2_evidence_completeness_api as mod
        self.assertTrue(hasattr(mod, "TestEvidenceCompletenessAPI"))

    def test_gl038b1_test_module_loads(self):
        import backend.tests.test_gl038b1_compliance_gap_report as mod
        self.assertTrue(hasattr(mod, "TestComplianceGapReportBuilder"))

    def test_gl038b2_test_module_loads(self):
        import backend.tests.test_gl038b2_compliance_gap_report_api as mod
        self.assertTrue(hasattr(mod, "TestComplianceGapReportAPI"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
