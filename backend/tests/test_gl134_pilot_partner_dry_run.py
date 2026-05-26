"""Tests for GL-134: Pilot Partner Dry Run.

Ensures:
- docs/pilot_partner_dry_run.md exists and covers required topics.
- docs/examples/gl134/pilot_partner_dry_run.json exists and is valid.
- JSON issue_id is GL-134.
- JSON review_only is true.
- JSON dry_run_only is true.
- JSON real_pilot_started is false.
- JSON real_customer_data_used is false.
- JSON partner_approval_claimed is false.
- JSON production_saas_approved is false.
- JSON shared_multitenant_saas_approved is false.
- JSON production_code_changed is false.
- Markdown says no real pilot is started by GL-134.
- Markdown says no real customer data is used.
- Markdown says no partner approval is claimed.
- Markdown says production SaaS is not approved.
- Dry-run posture is documented.
- Simulated pilot partner profile is documented.
- Preflight checklist references GL-128 through GL-133.
- Dry-run agenda is documented.
- Step-by-step scenario is documented.
- Required validation commands include expected scripts and tests.
- Evidence capture includes date/time, dry-run owner, main commit, synthetic data
  confirmation, command results, secret-safe screenshots/logs, open caveats, final go/no-go.
- Monitoring/incident/security checkpoints are present.
- Tenant/workspace boundary checks include no unrelated customer data mixed,
  no shared SaaS claims, no multi-tenant isolation assumed.
- Pilot go/no-go criteria are present.
- Follow-up issues include GL-135, GL-136, GL-137, GL-138, GL-139.
- Related gates include GL-128, GL-129, GL-130, GL-131, GL-132, GL-133.
- Explicit non-goals are present.
- Markdown/JSON do not include obvious raw secret values.
- Scope guards for no forbidden changes.

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

_MD_PATH = _REPO_ROOT / "docs" / "pilot_partner_dry_run.md"
_JSON_PATH = (
    _REPO_ROOT
    / "docs"
    / "examples"
    / "gl134"
    / "pilot_partner_dry_run.json"
)

_SECRET_PATTERNS = [
    re.compile(r"\bpassword\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bsecret\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bapi_key\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bprivate_key\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bpassphrase\s*=\s*\S", re.IGNORECASE),
]


class TestGl134ArtifactsExist(unittest.TestCase):
    """Verify the GL-134 artifacts are present."""

    def test_markdown_exists(self):
        self.assertTrue(
            _MD_PATH.exists(),
            f"docs/pilot_partner_dry_run.md must exist at {_MD_PATH}",
        )

    def test_json_exists(self):
        self.assertTrue(
            _JSON_PATH.exists(),
            f"docs/examples/gl134/pilot_partner_dry_run.json must exist at {_JSON_PATH}",
        )


class TestGl134JsonStructure(unittest.TestCase):
    """Verify GL-134 JSON structure and values."""

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
            "GL-134",
            "JSON issue_id must be GL-134",
        )

    def test_json_review_only_is_true(self):
        self.assertIs(
            self.json_data.get("review_only"),
            True,
            "JSON review_only must be true",
        )

    def test_json_dry_run_only_is_true(self):
        self.assertIs(
            self.json_data.get("dry_run_only"),
            True,
            "JSON dry_run_only must be true",
        )

    def test_json_real_pilot_started_is_false(self):
        self.assertIs(
            self.json_data.get("real_pilot_started"),
            False,
            "JSON real_pilot_started must be false",
        )

    def test_json_real_customer_data_used_is_false(self):
        self.assertIs(
            self.json_data.get("real_customer_data_used"),
            False,
            "JSON real_customer_data_used must be false",
        )

    def test_json_partner_approval_claimed_is_false(self):
        self.assertIs(
            self.json_data.get("partner_approval_claimed"),
            False,
            "JSON partner_approval_claimed must be false",
        )

    def test_json_production_saas_approved_is_false(self):
        self.assertIs(
            self.json_data.get("production_saas_approved"),
            False,
            "JSON production_saas_approved must be false",
        )

    def test_json_shared_multitenant_saas_approved_is_false(self):
        self.assertIs(
            self.json_data.get("shared_multitenant_saas_approved"),
            False,
            "JSON shared_multitenant_saas_approved must be false",
        )

    def test_json_production_code_changed_is_false(self):
        self.assertIs(
            self.json_data.get("production_code_changed"),
            False,
            "JSON production_code_changed must be false",
        )

    def test_json_artifact_type(self):
        self.assertEqual(
            self.json_data.get("artifact_type"),
            "pilot_partner_dry_run",
            "JSON artifact_type must be pilot_partner_dry_run",
        )


class TestGl134MarkdownContent(unittest.TestCase):
    """Verify GL-134 markdown content meets baseline requirements."""

    @classmethod
    def setUpClass(cls):
        cls.md_content = _MD_PATH.read_text(encoding="utf-8") if _MD_PATH.exists() else ""
        cls.md_lower = cls.md_content.lower()

    # --- Core claims ---

    def test_markdown_says_no_real_pilot_started(self):
        lower = self.md_lower
        self.assertTrue(
            "no real pilot" in lower
            or "not a real pilot" in lower
            or "does not start a real pilot" in lower,
            "Markdown must state no real pilot is started by GL-134",
        )

    def test_markdown_says_no_real_customer_data_used(self):
        lower = self.md_lower
        self.assertTrue(
            "no real customer data" in lower
            or "not real customer data" in lower,
            "Markdown must state no real customer data is used",
        )

    def test_markdown_says_no_partner_approval_claimed(self):
        lower = self.md_lower
        self.assertTrue(
            "no partner approval" in lower
            or "not partner approval" in lower
            or "no external partner approval claimed" in lower,
            "Markdown must state no partner approval is claimed",
        )

    def test_markdown_says_production_saas_not_approved(self):
        lower = self.md_lower
        self.assertTrue(
            "production saas not approved" in lower
            or "production saas is not complete" in lower
            or "no production saas approval" in lower
            or "production saas not complete" in lower
            or "production saas remains incomplete" in lower,
            "Markdown must state production SaaS is not approved/complete",
        )

    # --- Dry-run posture ---

    def test_dry_run_posture_documented(self):
        lower = self.md_lower
        self.assertIn("dry-run posture", lower)
        self.assertIn("controlled dry run", lower)

    # --- Simulated partner profile ---

    def test_simulated_partner_profile_documented(self):
        lower = self.md_lower
        self.assertIn("simulated pilot partner profile", lower)
        self.assertIn("example pilot partner", lower)

    # --- Preflight checklist ---

    def test_preflight_checklist_references_gl128(self):
        self.assertIn("gl-128", self.md_lower)

    def test_preflight_checklist_references_gl129(self):
        self.assertIn("gl-129", self.md_lower)

    def test_preflight_checklist_references_gl130(self):
        self.assertIn("gl-130", self.md_lower)

    def test_preflight_checklist_references_gl131(self):
        self.assertIn("gl-131", self.md_lower)

    def test_preflight_checklist_references_gl132(self):
        self.assertIn("gl-132", self.md_lower)

    def test_preflight_checklist_references_gl133(self):
        self.assertIn("gl-133", self.md_lower)

    def test_preflight_checklist_documented(self):
        lower = self.md_lower
        self.assertIn("preflight checklist", lower)

    # --- Dry-run agenda ---

    def test_dry_run_agenda_documented(self):
        lower = self.md_lower
        self.assertIn("dry-run agenda", lower)

    # --- Step-by-step scenario ---

    def test_step_by_step_scenario_documented(self):
        lower = self.md_lower
        self.assertIn("step-by-step scenario", lower)

    # --- Required validation commands ---

    def test_validation_commands_include_full_suite_script(self):
        lower = self.md_lower
        self.assertIn("scripts/run-full-backend-suite.sh", lower)

    def test_validation_commands_include_production_runtime_gate(self):
        lower = self.md_lower
        self.assertIn("scripts/run-production-runtime-gate.sh", lower)

    def test_validation_commands_include_smoke_tests(self):
        lower = self.md_lower
        self.assertIn("scripts/run-operational-smoke-tests.sh", lower)

    def test_validation_commands_include_backup_restore_drill(self):
        lower = self.md_lower
        self.assertIn("scripts/run-backup-restore-drill.sh", lower)

    def test_validation_commands_include_security_boundary_regression(self):
        lower = self.md_lower
        self.assertIn("test_security_boundary_regression", lower)

    # --- Evidence capture ---

    def test_evidence_capture_includes_date_time(self):
        lower = self.md_lower
        self.assertIn("date / time", lower)

    def test_evidence_capture_includes_dry_run_owner(self):
        lower = self.md_lower
        self.assertIn("dry-run owner", lower)

    def test_evidence_capture_includes_main_commit(self):
        lower = self.md_lower
        self.assertIn("main commit", lower)

    def test_evidence_capture_includes_synthetic_data_confirmation(self):
        lower = self.md_lower
        self.assertIn("synthetic data confirmation", lower)

    def test_evidence_capture_includes_command_results(self):
        lower = self.md_lower
        self.assertIn("commands run and results", lower)

    def test_evidence_capture_includes_secret_safe_screenshots(self):
        lower = self.md_lower
        self.assertIn("screenshots", lower)
        self.assertIn("without secrets", lower)

    def test_evidence_capture_includes_open_caveats(self):
        lower = self.md_lower
        self.assertIn("open caveats", lower)

    def test_evidence_capture_includes_final_go_no_go(self):
        lower = self.md_lower
        self.assertIn("final go/no-go", lower)

    # --- Monitoring/incident/security checkpoints ---

    def test_monitoring_incident_security_checkpoints_present(self):
        lower = self.md_lower
        self.assertIn("monitoring / incident / security checkpoints", lower)

    # --- Tenant/workspace boundary checks ---

    def test_tenant_boundary_no_unrelated_customer_data(self):
        lower = self.md_lower
        self.assertIn("no unrelated customer data", lower)

    def test_tenant_boundary_no_shared_saas_claims(self):
        lower = self.md_lower
        self.assertIn("no shared saas claims", lower)

    def test_tenant_boundary_no_multi_tenant_isolation_assumed(self):
        lower = self.md_lower
        self.assertIn("no multi-tenant isolation assumed", lower)

    # --- Go/no-go criteria ---

    def test_pilot_go_no_go_criteria_present(self):
        lower = self.md_lower
        self.assertIn("go / no-go", lower)
        self.assertIn("no-go", lower)

    # --- Follow-up issues ---

    def test_follow_up_include_gl135(self):
        self.assertIn("gl-135", self.md_lower)

    def test_follow_up_include_gl136(self):
        self.assertIn("gl-136", self.md_lower)

    def test_follow_up_include_gl137(self):
        self.assertIn("gl-137", self.md_lower)

    def test_follow_up_include_gl138(self):
        self.assertIn("gl-138", self.md_lower)

    def test_follow_up_include_gl139(self):
        self.assertIn("gl-139", self.md_lower)

    # --- Related gates ---

    def test_related_gates_include_gl128(self):
        self.assertIn("gl-128", self.md_lower)

    def test_related_gates_include_gl129(self):
        self.assertIn("gl-129", self.md_lower)

    def test_related_gates_include_gl130(self):
        self.assertIn("gl-130", self.md_lower)

    def test_related_gates_include_gl131(self):
        self.assertIn("gl-131", self.md_lower)

    def test_related_gates_include_gl132(self):
        self.assertIn("gl-132", self.md_lower)

    def test_related_gates_include_gl133(self):
        self.assertIn("gl-133", self.md_lower)

    # --- Non-goals ---

    def test_non_goals_present(self):
        lower = self.md_lower
        self.assertIn("explicit non-goals", lower)

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


class TestGl134JsonContent(unittest.TestCase):
    """Verify GL-134 JSON arrays contain expected items."""

    @classmethod
    def setUpClass(cls):
        raw_json = _JSON_PATH.read_text(encoding="utf-8") if _JSON_PATH.exists() else "{}"
        cls.json_data = json.loads(raw_json)

    def _has_substring_in_array(self, key, substring):
        arr = self.json_data.get(key, [])
        return any(substring.lower() in str(item).lower() for item in arr)

    def test_dry_run_posture_includes_controlled_dry_run(self):
        posture = self.json_data.get("dry_run_posture", {})
        self.assertIs(posture.get("controlled_dry_run_only"), True)

    def test_simulated_partner_profile_has_partner_name(self):
        profile = self.json_data.get("simulated_partner_profile", {})
        self.assertIn("example pilot partner", profile.get("partner_name", "").lower())

    def test_preflight_checklist_includes_gl128(self):
        self.assertTrue(
            self._has_substring_in_array("preflight_checklist", "GL-128"),
            "preflight_checklist must include GL-128",
        )

    def test_preflight_checklist_includes_gl129(self):
        self.assertTrue(
            self._has_substring_in_array("preflight_checklist", "GL-129"),
            "preflight_checklist must include GL-129",
        )

    def test_preflight_checklist_includes_gl130(self):
        self.assertTrue(
            self._has_substring_in_array("preflight_checklist", "GL-130"),
            "preflight_checklist must include GL-130",
        )

    def test_preflight_checklist_includes_gl131(self):
        self.assertTrue(
            self._has_substring_in_array("preflight_checklist", "GL-131"),
            "preflight_checklist must include GL-131",
        )

    def test_preflight_checklist_includes_gl132(self):
        self.assertTrue(
            self._has_substring_in_array("preflight_checklist", "GL-132"),
            "preflight_checklist must include GL-132",
        )

    def test_preflight_checklist_includes_gl133(self):
        self.assertTrue(
            self._has_substring_in_array("preflight_checklist", "GL-133"),
            "preflight_checklist must include GL-133",
        )

    def test_dry_run_agenda_not_empty(self):
        arr = self.json_data.get("dry_run_agenda", [])
        self.assertTrue(len(arr) > 0, "dry_run_agenda must not be empty")

    def test_step_by_step_scenario_not_empty(self):
        arr = self.json_data.get("step_by_step_scenario", [])
        self.assertTrue(len(arr) > 0, "step_by_step_scenario must not be empty")

    def test_required_validation_commands_include_full_suite(self):
        self.assertTrue(
            self._has_substring_in_array("required_validation_commands", "run-full-backend-suite.sh"),
            "required_validation_commands must include run-full-backend-suite.sh",
        )

    def test_required_validation_commands_include_runtime_gate(self):
        self.assertTrue(
            self._has_substring_in_array("required_validation_commands", "run-production-runtime-gate.sh"),
            "required_validation_commands must include run-production-runtime-gate.sh",
        )

    def test_required_validation_commands_include_smoke_tests(self):
        self.assertTrue(
            self._has_substring_in_array("required_validation_commands", "run-operational-smoke-tests.sh"),
            "required_validation_commands must include run-operational-smoke-tests.sh",
        )

    def test_required_validation_commands_include_backup_restore(self):
        self.assertTrue(
            self._has_substring_in_array("required_validation_commands", "run-backup-restore-drill.sh"),
            "required_validation_commands must include run-backup-restore-drill.sh",
        )

    def test_required_validation_commands_include_security_boundary(self):
        self.assertTrue(
            self._has_substring_in_array("required_validation_commands", "test_security_boundary_regression"),
            "required_validation_commands must include test_security_boundary_regression",
        )

    def test_evidence_capture_includes_date_time(self):
        self.assertTrue(
            self._has_substring_in_array("evidence_capture_requirements", "date / time"),
            "evidence_capture_requirements must include date / time",
        )

    def test_evidence_capture_includes_dry_run_owner(self):
        self.assertTrue(
            self._has_substring_in_array("evidence_capture_requirements", "dry-run owner"),
            "evidence_capture_requirements must include dry-run owner",
        )

    def test_evidence_capture_includes_main_commit(self):
        self.assertTrue(
            self._has_substring_in_array("evidence_capture_requirements", "main commit"),
            "evidence_capture_requirements must include main commit",
        )

    def test_evidence_capture_includes_synthetic_data(self):
        self.assertTrue(
            self._has_substring_in_array("evidence_capture_requirements", "synthetic data"),
            "evidence_capture_requirements must include synthetic data",
        )

    def test_evidence_capture_includes_command_results(self):
        self.assertTrue(
            self._has_substring_in_array("evidence_capture_requirements", "commands run"),
            "evidence_capture_requirements must include commands run",
        )

    def test_evidence_capture_includes_screenshots(self):
        self.assertTrue(
            self._has_substring_in_array("evidence_capture_requirements", "screenshots"),
            "evidence_capture_requirements must include screenshots",
        )

    def test_evidence_capture_includes_open_caveats(self):
        self.assertTrue(
            self._has_substring_in_array("evidence_capture_requirements", "open caveats"),
            "evidence_capture_requirements must include open caveats",
        )

    def test_evidence_capture_includes_final_go_no_go(self):
        self.assertTrue(
            self._has_substring_in_array("evidence_capture_requirements", "final go/no-go"),
            "evidence_capture_requirements must include final go/no-go",
        )

    def test_monitoring_checkpoint_includes_owner(self):
        self.assertTrue(
            self._has_substring_in_array("monitoring_incident_security_checkpoints", "monitoring owner"),
            "monitoring_incident_security_checkpoints must include monitoring owner",
        )

    def test_monitoring_checkpoint_includes_incident_owner(self):
        self.assertTrue(
            self._has_substring_in_array("monitoring_incident_security_checkpoints", "incident owner"),
            "monitoring_incident_security_checkpoints must include incident owner",
        )

    def test_tenant_boundary_no_unrelated_customer_data(self):
        self.assertTrue(
            self._has_substring_in_array("tenant_workspace_boundary_checks", "no unrelated customer data"),
            "tenant_workspace_boundary_checks must include no unrelated customer data",
        )

    def test_tenant_boundary_no_shared_saas_claims(self):
        self.assertTrue(
            self._has_substring_in_array("tenant_workspace_boundary_checks", "no shared SaaS claims"),
            "tenant_workspace_boundary_checks must include no shared SaaS claims",
        )

    def test_tenant_boundary_no_multi_tenant_isolation(self):
        self.assertTrue(
            self._has_substring_in_array("tenant_workspace_boundary_checks", "no multi-tenant isolation assumed"),
            "tenant_workspace_boundary_checks must include no multi-tenant isolation assumed",
        )

    def test_pilot_go_criteria_present(self):
        arr = self.json_data.get("pilot_go_criteria", [])
        self.assertTrue(len(arr) > 0, "pilot_go_criteria must not be empty")

    def test_pilot_no_go_criteria_present(self):
        arr = self.json_data.get("pilot_no_go_criteria", [])
        self.assertTrue(len(arr) > 0, "pilot_no_go_criteria must not be empty")

    def test_follow_up_issues_include_gl135(self):
        arr = self.json_data.get("follow_up_issues", [])
        self.assertTrue(
            any("gl-135" in str(item).lower() for item in arr),
            "follow_up_issues must include GL-135",
        )

    def test_follow_up_issues_include_gl136(self):
        arr = self.json_data.get("follow_up_issues", [])
        self.assertTrue(
            any("gl-136" in str(item).lower() for item in arr),
            "follow_up_issues must include GL-136",
        )

    def test_follow_up_issues_include_gl137(self):
        arr = self.json_data.get("follow_up_issues", [])
        self.assertTrue(
            any("gl-137" in str(item).lower() for item in arr),
            "follow_up_issues must include GL-137",
        )

    def test_follow_up_issues_include_gl138(self):
        arr = self.json_data.get("follow_up_issues", [])
        self.assertTrue(
            any("gl-138" in str(item).lower() for item in arr),
            "follow_up_issues must include GL-138",
        )

    def test_follow_up_issues_include_gl139(self):
        arr = self.json_data.get("follow_up_issues", [])
        self.assertTrue(
            any("gl-139" in str(item).lower() for item in arr),
            "follow_up_issues must include GL-139",
        )

    def test_related_gates_include_gl128(self):
        arr = self.json_data.get("related_gates", [])
        self.assertIn("GL-128", arr)

    def test_related_gates_include_gl129(self):
        arr = self.json_data.get("related_gates", [])
        self.assertIn("GL-129", arr)

    def test_related_gates_include_gl130(self):
        arr = self.json_data.get("related_gates", [])
        self.assertIn("GL-130", arr)

    def test_related_gates_include_gl131(self):
        arr = self.json_data.get("related_gates", [])
        self.assertIn("GL-131", arr)

    def test_related_gates_include_gl132(self):
        arr = self.json_data.get("related_gates", [])
        self.assertIn("GL-132", arr)

    def test_related_gates_include_gl133(self):
        arr = self.json_data.get("related_gates", [])
        self.assertIn("GL-133", arr)

    def test_explicit_non_goals_present(self):
        arr = self.json_data.get("explicit_non_goals", [])
        self.assertTrue(len(arr) > 0, "explicit_non_goals must not be empty")

    def test_secret_safety_no_raw_tokens(self):
        ss = self.json_data.get("secret_safety", {})
        self.assertIs(ss.get("no_raw_tokens"), True)

    def test_secret_safety_no_raw_authorization_header(self):
        ss = self.json_data.get("secret_safety", {})
        self.assertIs(ss.get("no_raw_authorization_header"), True)

    def test_secret_safety_no_raw_request_bodies(self):
        ss = self.json_data.get("secret_safety", {})
        self.assertIs(ss.get("no_raw_request_bodies"), True)

    def test_secret_safety_no_db_passwords(self):
        ss = self.json_data.get("secret_safety", {})
        self.assertIs(ss.get("no_db_passwords"), True)

    def test_secret_safety_no_private_keys(self):
        ss = self.json_data.get("secret_safety", {})
        self.assertIs(ss.get("no_private_keys"), True)

    def test_secret_safety_no_backup_credentials(self):
        ss = self.json_data.get("secret_safety", {})
        self.assertIs(ss.get("no_backup_credentials"), True)

    def test_secret_safety_no_secrets_in_screenshots(self):
        ss = self.json_data.get("secret_safety", {})
        self.assertIs(ss.get("no_secrets_in_screenshots"), True)


class TestGl134ScopeGuard(unittest.TestCase):
    """Verify no forbidden files were changed by GL-134."""

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
                self.fail(f"GL-134 must not change production code: {line}")

    def test_no_openapi_changed(self):
        changed = self._changed_files()
        self.assertNotIn(
            "openapi.yaml",
            changed,
            "GL-134 must not change the OpenAPI specification",
        )

    def test_no_migration_files_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if "migrations/" in line:
                self.fail(f"GL-134 must not change migration files: {line}")

    def test_no_frontend_or_website_files_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("frontend/") or line.startswith("website/"):
                self.fail(f"GL-134 must not change frontend or website files: {line}")

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
                        f"GL-134 must not change dependency file '{token}': {line}"
                    )

    def test_no_db_schema_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if "schema" in line.lower() and line.endswith(".sql"):
                self.fail(f"GL-134 must not change DB schema: {line}")

    def test_no_scripts_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("scripts/"):
                self.fail(f"GL-134 must not change scripts: {line}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
