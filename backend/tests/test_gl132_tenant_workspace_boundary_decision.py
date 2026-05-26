"""Tests for GL-132: Tenant / Workspace Boundary Decision.

Ensures:
- docs/tenant_workspace_boundary_decision.md exists and covers required topics.
- docs/examples/gl132/tenant_workspace_boundary_decision.json exists and is valid.
- JSON issue_id is GL-132.
- JSON review_only is true.
- JSON tenant_implementation_added is false.
- JSON workspace_implementation_added is false.
- JSON production_code_changed is false.
- JSON db_schema_changed is false.
- JSON auth_semantics_changed is false.
- JSON production_multitenancy_implemented is false.
- JSON commercial_saas_complete is false.
- Markdown says no tenant/workspace implementation is added.
- Markdown says production multi-tenancy is not implemented.
- Markdown says shared SaaS for unrelated customers is not approved.
- Terms include tenant, workspace, operator, pilot environment, grant boundary,
  evidence boundary, audit boundary.
- Options include single-tenant pilot, operator-bounded workspace, full
  multi-tenant SaaS, defer implementation while forbidding multi-tenant claims.
- Recommended decision distinguishes controlled pilot from production SaaS.
- Production SaaS requirements are documented.
- Explicit non-claims are documented.
- Pilot go/no-go criteria are present.
- Follow-up issues include GL-133 through GL-138.
- Related gates include GL-128, GL-129, GL-130, GL-131.
- Markdown/JSON do not include obvious raw secret values.
- No forbidden scope changes.

No production code changes required.
No external services required.
"""

import json
import os
import pathlib
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

_MD_PATH = _REPO_ROOT / "docs" / "tenant_workspace_boundary_decision.md"
_JSON_PATH = (
    _REPO_ROOT
    / "docs"
    / "examples"
    / "gl132"
    / "tenant_workspace_boundary_decision.json"
)

_SECRET_PATTERNS = [
    re.compile(r"\bpassword\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bsecret\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bapi_key\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bprivate_key\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bpassphrase\s*=\s*\S", re.IGNORECASE),
]


class TestGl132ArtifactsExist(unittest.TestCase):
    """Verify the GL-132 artifacts are present."""

    def test_markdown_exists(self):
        self.assertTrue(
            _MD_PATH.exists(),
            f"docs/tenant_workspace_boundary_decision.md must exist at {_MD_PATH}",
        )

    def test_json_exists(self):
        self.assertTrue(
            _JSON_PATH.exists(),
            f"docs/examples/gl132/tenant_workspace_boundary_decision.json must exist at {_JSON_PATH}",
        )


class TestGl132JsonStructure(unittest.TestCase):
    """Verify GL-132 JSON structure and values."""

    @classmethod
    def setUpClass(cls):
        raw_json = _JSON_PATH.read_text(encoding="utf-8") if _JSON_PATH.exists() else "{}"
        cls.json_data = json.loads(raw_json)
        cls.json_str = raw_json.lower()

    def test_json_is_valid(self):
        self.assertIsInstance(self.json_data, dict, "JSON must be a top-level object")

    def test_json_issue_id(self):
        self.assertEqual(
            self.json_data.get("issue_id"),
            "GL-132",
            "JSON issue_id must be GL-132",
        )

    def test_json_review_only_is_true(self):
        self.assertIs(
            self.json_data.get("review_only"),
            True,
            "JSON review_only must be true",
        )

    def test_json_tenant_implementation_added_is_false(self):
        self.assertIs(
            self.json_data.get("tenant_implementation_added"),
            False,
            "JSON tenant_implementation_added must be false",
        )

    def test_json_workspace_implementation_added_is_false(self):
        self.assertIs(
            self.json_data.get("workspace_implementation_added"),
            False,
            "JSON workspace_implementation_added must be false",
        )

    def test_json_production_code_changed_is_false(self):
        self.assertIs(
            self.json_data.get("production_code_changed"),
            False,
            "JSON production_code_changed must be false",
        )

    def test_json_db_schema_changed_is_false(self):
        self.assertIs(
            self.json_data.get("db_schema_changed"),
            False,
            "JSON db_schema_changed must be false",
        )

    def test_json_auth_semantics_changed_is_false(self):
        self.assertIs(
            self.json_data.get("auth_semantics_changed"),
            False,
            "JSON auth_semantics_changed must be false",
        )

    def test_json_production_multitenancy_implemented_is_false(self):
        self.assertIs(
            self.json_data.get("production_multitenancy_implemented"),
            False,
            "JSON production_multitenancy_implemented must be false",
        )

    def test_json_commercial_saas_complete_is_false(self):
        self.assertIs(
            self.json_data.get("commercial_saas_complete"),
            False,
            "JSON commercial_saas_complete must be false",
        )

    def test_json_decision_type(self):
        self.assertEqual(
            self.json_data.get("decision_type"),
            "tenant_workspace_boundary_decision",
            "JSON decision_type must be tenant_workspace_boundary_decision",
        )


class TestGl132MarkdownContent(unittest.TestCase):
    """Verify GL-132 markdown content meets baseline requirements."""

    @classmethod
    def setUpClass(cls):
        cls.md_content = _MD_PATH.read_text(encoding="utf-8") if _MD_PATH.exists() else ""
        cls.md_lower = cls.md_content.lower()

    def test_markdown_says_no_tenant_workspace_implementation_added(self):
        lower = self.md_lower
        self.assertTrue(
            "no tenant/workspace implementation is added" in lower
            or "not tenant implementation" in lower,
            "Markdown must state no tenant/workspace implementation is added",
        )

    def test_markdown_says_production_multitenancy_not_implemented(self):
        lower = self.md_lower
        self.assertTrue(
            "production multi-tenancy is not implemented" in lower
            or "no production multi-tenancy" in lower,
            "Markdown must state production multi-tenancy is not implemented",
        )

    def test_markdown_says_shared_saas_not_approved(self):
        lower = self.md_lower
        self.assertTrue(
            "does not approve a shared multi-tenant saas environment" in lower
            or "no shared saas environment approved" in lower,
            "Markdown must state shared SaaS for unrelated customers is not approved",
        )

    # --- Terms ---

    def test_terms_include_tenant(self):
        self.assertIn("tenant", self.md_lower)

    def test_terms_include_workspace(self):
        self.assertIn("workspace", self.md_lower)

    def test_terms_include_operator(self):
        self.assertIn("operator", self.md_lower)

    def test_terms_include_pilot_environment(self):
        lower = self.md_lower
        self.assertIn("pilot environment", lower)

    def test_terms_include_grant_boundary(self):
        lower = self.md_lower
        self.assertIn("grant boundary", lower)

    def test_terms_include_evidence_boundary(self):
        lower = self.md_lower
        self.assertIn("evidence boundary", lower)

    def test_terms_include_audit_boundary(self):
        lower = self.md_lower
        self.assertIn("audit boundary", lower)

    # --- Options considered ---

    def test_options_include_single_tenant_pilot(self):
        lower = self.md_lower
        self.assertIn("single-tenant pilot", lower)

    def test_options_include_operator_bounded_workspace(self):
        lower = self.md_lower
        self.assertIn("operator-bounded workspace", lower)

    def test_options_include_full_multi_tenant_saas(self):
        lower = self.md_lower
        self.assertIn("full multi-tenant saas", lower)

    def test_options_include_defer_forbid_claims(self):
        lower = self.md_lower
        self.assertIn("defer", lower)
        self.assertIn("forbid multi-tenant claims", lower)

    # --- Recommended decision ---

    def test_recommended_decision_distinguishes_pilot_from_saas(self):
        lower = self.md_lower
        self.assertIn("controlled pilot", lower)
        self.assertIn("production saas", lower)

    # --- Production SaaS requirements ---

    def test_production_saas_requirements_include_tenant_workspace_identity(self):
        lower = self.md_lower
        self.assertIn("tenant/workspace identity", lower)

    def test_production_saas_requirements_include_tenant_aware_authorization(self):
        lower = self.md_lower
        self.assertIn("tenant-aware authorization", lower)

    def test_production_saas_requirements_include_tenant_aware_operator_permissions(self):
        lower = self.md_lower
        self.assertIn("tenant-aware operator/admin permissions", lower)

    def test_production_saas_requirements_include_tenant_aware_grants_evidence_audit(self):
        lower = self.md_lower
        self.assertIn("tenant-aware grants", lower)
        self.assertIn("evidence", lower)
        self.assertIn("audit", lower)

    def test_production_saas_requirements_include_tenant_aware_export_report(self):
        lower = self.md_lower
        self.assertIn("export", lower)
        self.assertIn("report", lower)

    def test_production_saas_requirements_include_tenant_aware_backup_restore(self):
        lower = self.md_lower
        self.assertIn("backup/restore", lower)

    def test_production_saas_requirements_include_tenant_aware_logging_monitoring(self):
        lower = self.md_lower
        self.assertIn("log", lower)
        self.assertIn("monitoring", lower)

    def test_production_saas_requirements_include_cross_tenant_prevention_tests(self):
        lower = self.md_lower
        self.assertIn("cross-tenant access prevention tests", lower)

    # --- Explicit non-claims ---

    def test_non_claims_include_no_tenant_model(self):
        lower = self.md_lower
        self.assertIn("no tenant model", lower)

    def test_non_claims_include_no_workspace_model(self):
        lower = self.md_lower
        self.assertIn("no workspace model", lower)

    def test_non_claims_include_no_customer_account_model(self):
        lower = self.md_lower
        self.assertIn("no customer account model", lower)

    def test_non_claims_include_no_billing(self):
        lower = self.md_lower
        self.assertIn("no billing", lower)

    def test_non_claims_include_no_frontend_onboarding(self):
        lower = self.md_lower
        self.assertIn("no frontend onboarding", lower)

    def test_non_claims_include_no_shared_saas_unrelated_customers(self):
        lower = self.md_lower
        self.assertIn("no shared saas environment approved for unrelated customers", lower)

    # --- Pilot go/no-go criteria ---

    def test_pilot_go_no_go_criteria_present(self):
        lower = self.md_lower
        self.assertIn("go", lower)
        self.assertIn("no-go", lower)

    # --- Follow-up issues ---

    def test_follow_up_include_gl133(self):
        self.assertIn("gl-133", self.md_lower)

    def test_follow_up_include_gl134(self):
        self.assertIn("gl-134", self.md_lower)

    def test_follow_up_include_gl135(self):
        self.assertIn("gl-135", self.md_lower)

    def test_follow_up_include_gl136(self):
        self.assertIn("gl-136", self.md_lower)

    def test_follow_up_include_gl137(self):
        self.assertIn("gl-137", self.md_lower)

    def test_follow_up_include_gl138(self):
        self.assertIn("gl-138", self.md_lower)

    # --- Related gates ---

    def test_related_gates_include_gl128(self):
        self.assertIn("gl-128", self.md_lower)

    def test_related_gates_include_gl129(self):
        self.assertIn("gl-129", self.md_lower)

    def test_related_gates_include_gl130(self):
        self.assertIn("gl-130", self.md_lower)

    def test_related_gates_include_gl131(self):
        self.assertIn("gl-131", self.md_lower)

    # --- No raw secrets ---

    def test_markdown_no_raw_secrets(self):
        for pattern in _SECRET_PATTERNS:
            for line in self.md_content.splitlines():
                if pattern.search(line):
                    self.fail(
                        f"Markdown must not contain raw secret assignment: {line.strip()}"
                    )

    def test_json_no_raw_secrets(self):
        raw = _JSON_PATH.read_text(encoding="utf-8") if _JSON_PATH.exists() else ""
        for pattern in _SECRET_PATTERNS:
            for line in raw.splitlines():
                if pattern.search(line):
                    self.fail(
                        f"JSON must not contain raw secret assignment: {line.strip()}"
                    )


class TestGl132ScopeGuard(unittest.TestCase):
    """Verify no forbidden files were changed by GL-132."""

    def _changed_files(self):
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        if result.returncode != 0:
            self.skipTest("git diff unavailable; skipping scope guard")
        return result.stdout.strip()

    def test_no_production_code_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("backend/src/"):
                self.fail(f"GL-132 must not change production code: {line}")

    def test_no_openapi_changed(self):
        changed = self._changed_files()
        self.assertNotIn(
            "openapi.yaml",
            changed,
            "GL-132 must not change the OpenAPI specification",
        )

    def test_no_migration_files_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if "migrations/" in line:
                self.fail(f"GL-132 must not change migration files: {line}")

    def test_no_frontend_or_website_files_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("frontend/") or line.startswith("website/"):
                self.fail(f"GL-132 must not change frontend or website files: {line}")

    def test_no_dependency_files_changed(self):
        changed = self._changed_files()
        forbidden = [
            "pyproject.toml",
            "setup.py",
            "requirements",
            "package.json",
            "package-lock.json",
        ]
        for token in forbidden:
            for line in changed.splitlines():
                if token in line:
                    self.fail(
                        f"GL-132 must not change dependency file '{token}': {line}"
                    )

    def test_no_db_schema_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if "schema" in line.lower() and line.endswith(".sql"):
                self.fail(f"GL-132 must not change DB schema: {line}")

    def test_no_scripts_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("scripts/"):
                self.fail(f"GL-132 must not change scripts: {line}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
