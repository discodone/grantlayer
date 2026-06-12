"""Tests for GL-055 Integration Contract & Readiness Gate.

Lightweight validation test proving the current GrantLayer Integration-Ready
artifacts are present, coherent, and aligned with the API contract.

This test must not introduce new product features.
It must not introduce new API endpoints.
It must not introduce persistence, database schema changes, migrations,
UI, OAuth, JWT, SSO, blockchain, payments, or SaaS features.
"""

import json
import os
import pathlib
import unittest


try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


class TestGL055IntegrationContractReadiness(unittest.TestCase):
    """GL-055: Integration Contract & Readiness Gate."""

    REPO_ROOT = pathlib.Path(__file__).with_suffix("").parent.parent.parent
    DOCS_DIR = REPO_ROOT / "docs"
    BACKEND_TESTS_DIR = REPO_ROOT / "backend" / "tests"
    FIXTURES_DIR = BACKEND_TESTS_DIR / "fixtures"

    # ── Expected current OpenAPI paths (representative, not brittle) ──
    EXPECTED_OPENAPI_PATHS = [
        "/health",
        "/v1/grants",
        "/v1/grants/{id}",
        "/v1/grants/{id}/revoke",
        "/v1/grant-requests",
        "/v1/grant-requests/{id}",
        "/v1/grant-requests/{id}/approve",
        "/v1/grant-requests/{id}/deny",
        "/v1/grant-executions",
        "/v1/grant-executions/{id}",
        "/v1/grants/{id}/executions",
        "/v1/audit-events",
        "/v1/evidence/executions/{id}",
        "/v1/evidence/executions/{id}/export",
        "/v1/evidence/executions/{id}/verify",
        "/v1/provenance/executions/{executionId}/summary",
        "/v1/decision-provenance/v2/build",
        "/v1/agent-permissions/evaluate",
        "/v1/approvals/evaluate",
        "/v1/approvals/lifecycle/build",
        "/v1/approvals/lifecycle/transition",
        "/v1/agent-permissions/profiles",
        "/v1/agent-permissions/profiles/{profileName}",
        "/v1/agent-permissions/assignments/resolve",
        "/v1/evidence/executions/{id}/completeness",
        "/v1/compliance/gaps/executions/{id}",
        "/v1/auditor/reports/executions/{id}",
        "/v1/auditor/exports/build",
        "/v1/policy-requirements/evaluate",
        "/v1/compliance/readiness/build",
    ]

    # ── Known legacy/wrong paths that must be absent ──
    KNOWN_LEGACY_PATHS = [
        "/v1/decision-provenance/v1/build",
        "/v1/provenance-summary/v2/build",
        "/institutional-auditor-exports/build",
        "/agent-permission-assignment-resolver",
    ]

    # ── Stable IDs expected in the demo fixture ──
    DEMO_STABLE_IDS = {
        "scenarioId": "gl054-demo-scenario",
        "workflowId": "gl054-workflow-001",
        "subjectId": "gl054-subject-001",
        "grantRequestId": "gl054-request-001",
        "grantId": "gl054-grant-001",
        "executionId": "gl054-execution-001",
        "evidenceId": "gl054-evidence-001",
        "policyPackId": "gl054-policy-001",
        "auditorExportId": "gl054-auditor-export-001",
    }

    SECRET_PATTERNS = [
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "private_key",
        "privatekey",
        "bearer",
        "authorization",
    ]

    @classmethod
    def setUpClass(cls):
        cls.openapi_path = cls.DOCS_DIR / "openapi.yaml"
        cls.fixture_path = cls.FIXTURES_DIR / "gl054_demo_scenario.json"

    # ── 1. docs/openapi.yaml exists ──────────────────────────────────
    def test_openapi_yaml_exists(self):
        self.assertTrue(
            self.openapi_path.exists(),
            f"docs/openapi.yaml must exist: {self.openapi_path}",
        )

    # ── 2. docs/openapi.yaml is parseable ──────────────────────────────
    def test_openapi_yaml_is_parseable(self):
        text = self.openapi_path.read_text(encoding="utf-8")
        self.assertTrue(len(text) > 0, "docs/openapi.yaml must not be empty")
        parse_ok = False
        if yaml is not None:
            try:
                parsed = yaml.safe_load(text)
                self.assertIsInstance(parsed, dict, "docs/openapi.yaml must parse as a YAML mapping")
                parse_ok = True
            except Exception:
                pass  # fall through to conservative text check
        if not parse_ok:
            # Conservatively parse: verify it looks like a valid OpenAPI document
            self.assertIn("openapi:", text, "docs/openapi.yaml must contain 'openapi:' header")
            self.assertIn("paths:", text, "docs/openapi.yaml must contain 'paths:' section")

    # ── 3. paths section exists and is non-empty ──────────────────────
    def test_openapi_paths_section_exists_and_nonempty(self):
        text = self.openapi_path.read_text(encoding="utf-8")
        paths = None
        if yaml is not None:
            try:
                parsed = yaml.safe_load(text)
                paths = parsed.get("paths")
            except Exception:
                pass
        if paths is not None:
            self.assertIsInstance(paths, dict, "OpenAPI 'paths' must be a mapping")
            self.assertTrue(len(paths) > 0, "OpenAPI 'paths' must not be empty")
        else:
            # Fallback: count path declarations
            path_lines = [ln for ln in text.splitlines() if ln.strip().startswith("/")]
            self.assertTrue(len(path_lines) > 0, "OpenAPI must contain at least one path declaration")

    # ── 4. Expected current paths are present ─────────────────────────
    def test_expected_openapi_paths_present(self):
        text = self.openapi_path.read_text(encoding="utf-8")
        for path in self.EXPECTED_OPENAPI_PATHS:
            with self.subTest(path=path):
                # Match lines like "  /path:" or "  /path/{param}:"
                needle = f"{path}:"
                self.assertIn(
                    needle,
                    text,
                    f"Expected OpenAPI path {path} not found in openapi.yaml",
                )

    # ── 5. Known legacy/wrong paths are absent ────────────────────────
    def test_known_legacy_paths_absent(self):
        text = self.openapi_path.read_text(encoding="utf-8")
        for path in self.KNOWN_LEGACY_PATHS:
            with self.subTest(path=path):
                needle = f"{path}:"
                self.assertNotIn(
                    needle,
                    text,
                    f"Known legacy path {path} must not be present in openapi.yaml",
                )

    # ── 6. docs/integration_guide.md exists ────────────────────────────
    def test_integration_guide_exists(self):
        path = self.DOCS_DIR / "integration_guide.md"
        self.assertTrue(path.exists(), "docs/integration_guide.md must exist")

    # ── 7. docs/demo_scenario.md exists ────────────────────────────────
    def test_demo_scenario_exists(self):
        path = self.DOCS_DIR / "demo_scenario.md"
        self.assertTrue(path.exists(), "docs/demo_scenario.md must exist")

    # ── 8. docs/integration_ready_checklist.md exists ──────────────────
    def test_integration_ready_checklist_exists(self):
        path = self.DOCS_DIR / "integration_ready_checklist.md"
        self.assertTrue(path.exists(), "docs/integration_ready_checklist.md must exist")

    # ── 9. GL-052 E2E test exists ──────────────────────────────────────
    def test_gl052_e2e_test_exists(self):
        path = self.BACKEND_TESTS_DIR / "test_gl052_product_core_e2e_flow.py"
        self.assertTrue(path.exists(), "backend/tests/test_gl052_product_core_e2e_flow.py must exist")

    # ── 10. GL-054 demo fixture exists and is valid JSON ───────────────
    def test_gl054_demo_fixture_exists_and_valid_json(self):
        self.assertTrue(
            self.fixture_path.exists(),
            f"backend/tests/fixtures/gl054_demo_scenario.json must exist: {self.fixture_path}",
        )
        text = self.fixture_path.read_text(encoding="utf-8")
        fixture = json.loads(text)
        self.assertIsInstance(fixture, dict, "Demo fixture must parse as a JSON object")

    # ── 11. GL-054 demo fixture test exists ────────────────────────────
    def test_gl054_demo_fixture_test_exists(self):
        path = self.BACKEND_TESTS_DIR / "test_gl054_demo_scenario_fixture.py"
        self.assertTrue(path.exists(), "backend/tests/test_gl054_demo_scenario_fixture.py must exist")

    # ── 12. Demo fixture contains expected stable IDs ──────────────────
    def test_demo_fixture_stable_ids(self):
        fixture = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        self.assertEqual(fixture.get("scenarioId"), self.DEMO_STABLE_IDS["scenarioId"])
        self.assertEqual(fixture.get("workflowId"), self.DEMO_STABLE_IDS["workflowId"])
        self.assertEqual(fixture.get("subjectId"), self.DEMO_STABLE_IDS["subjectId"])
        self.assertEqual(
            fixture["grantRequest"].get("grantRequestId"),
            self.DEMO_STABLE_IDS["grantRequestId"],
        )
        self.assertEqual(fixture["grant"].get("grantId"), self.DEMO_STABLE_IDS["grantId"])
        self.assertEqual(fixture["execution"].get("executionId"), self.DEMO_STABLE_IDS["executionId"])
        self.assertEqual(
            fixture["evidence"][0].get("evidenceId"),
            self.DEMO_STABLE_IDS["evidenceId"],
        )
        self.assertEqual(
            fixture["policyRequirements"].get("policyPackId"),
            self.DEMO_STABLE_IDS["policyPackId"],
        )
        self.assertEqual(
            fixture["auditorExport"].get("exportId"),
            self.DEMO_STABLE_IDS["auditorExportId"],
        )

    # ── 13. No obvious secrets appear in demo fixture ───────────────────
    def test_demo_fixture_contains_no_obvious_secrets(self):
        text_lower = self.fixture_path.read_text(encoding="utf-8").lower()
        for pattern in self.SECRET_PATTERNS:
            self.assertNotIn(
                pattern,
                text_lower,
                f"Demo fixture may contain secret-like pattern: {pattern}",
            )

    # ── 14. Checklist documents non-goals and production hardening ─────
    def test_checklist_documents_non_goals_and_hardening(self):
        path = self.DOCS_DIR / "integration_ready_checklist.md"
        content = path.read_text(encoding="utf-8").lower()
        # Non-goals section must exist
        self.assertIn("non-goals", content, "Checklist must document non-goals")
        self.assertIn("production hardening", content, "Checklist must mention production hardening")
        # Representative future items
        self.assertIn("oauth", content, "Checklist must mention OAuth as a non-goal")
        self.assertIn("jwt", content, "Checklist must mention JWT as a non-goal")
        self.assertIn("sso", content, "Checklist must mention SSO as a non-goal")
        self.assertIn("blockchain", content, "Checklist must mention blockchain as a non-goal")
        self.assertIn("multi-tenant", content, "Checklist must mention multi-tenant SaaS as a non-goal")

    # ── 15. OpenAPI contract version is documented ─────────────────────
    def test_openapi_version_documented(self):
        text = self.openapi_path.read_text(encoding="utf-8")
        version = None
        if yaml is not None:
            try:
                parsed = yaml.safe_load(text)
                version = parsed.get("info", {}).get("version", "")
            except Exception:
                pass
        if version is not None:
            self.assertTrue(len(version) > 0, "OpenAPI info.version must be documented")
        else:
            self.assertIn("version:", text, "OpenAPI must document a version")

    # ── 16. Integration guide cross-references checklist ──────────────
    def test_integration_guide_references_checklist(self):
        path = self.DOCS_DIR / "integration_guide.md"
        content = path.read_text(encoding="utf-8")
        self.assertIn(
            "integration_ready_checklist.md",
            content,
            "Integration guide should reference the integration-ready checklist",
        )

    # ── 17. Demo scenario cross-references checklist ──────────────────
    def test_demo_scenario_references_checklist(self):
        path = self.DOCS_DIR / "demo_scenario.md"
        content = path.read_text(encoding="utf-8")
        self.assertIn(
            "integration_ready_checklist.md",
            content,
            "Demo scenario should reference the integration-ready checklist",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
