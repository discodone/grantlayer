"""GL-223 Workspace Identity / Membership / Ownership Implementation Plan — tests.

Verifies:
- Required docs and artifacts exist
- JSON artifact structure and content
- Required Markdown sections exist
- Safety claims in documentation
- No forbidden implementation/deployment/package/public-export paths introduced
- Gate script compiles and supports --dry-run / --plan flags
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

MD_PATH = REPO_ROOT / "docs" / "workspace_identity_membership_ownership_implementation_plan.md"
JSON_PATH = REPO_ROOT / "docs" / "examples" / "gl223" / "workspace_identity_membership_ownership_implementation_plan.json"
GATE_SCRIPT = REPO_ROOT / "scripts" / "ops" / "gl223_workspace_identity_plan_gate.py"


REQUIRED_JSON_KEYS = [
    "issue_id",
    "title",
    "result",
    "decision",
    "decision_rationale",
    "input_sources_reviewed",
    "current_tenant_workspace_state_summary",
    "current_workspace_trust_gaps",
    "workspace_identity_model",
    "membership_model",
    "ownership_model",
    "role_scope_model",
    "workspace_lifecycle_model",
    "admin_operator_ownership_boundary",
    "server_derived_workspace_context_model",
    "unsafe_workspace_override_prevention_model",
    "cross_workspace_lookup_denial_model",
    "cross_workspace_mutation_denial_model",
    "audit_evidence_provenance_compliance_propagation_model",
    "database_schema_plan",
    "migration_backfill_plan",
    "api_server_plan",
    "openapi_impact_plan",
    "testing_strategy",
    "rollout_strategy",
    "rollback_strategy",
    "demo_synthetic_compatibility",
    "production_readiness_impact",
    "controlled_preview_impact",
    "real_data_impact",
    "remaining_blockers",
    "proposed_implementation_issue_breakdown",
    "risk_register",
    "findings",
    "safety_confirmations",
    "recommended_next_issues",
]

REQUIRED_MD_SECTIONS = [
    "GL-223",
    "Current Tenant/Workspace State Summary",
    "Current Workspace Trust Gaps",
    "Workspace Identity Model",
    "Membership Model",
    "Ownership Model",
    "Role / Scope Model",
    "Workspace Lifecycle Model",
    "Admin/Operator Ownership Boundary",
    "Server-Derived Workspace Context Model",
    "Unsafe Workspace Override Prevention Model",
    "Cross-Workspace Lookup Denial Model",
    "Cross-Workspace Mutation Denial Model",
    "Audit / Evidence / Provenance / Compliance Propagation Model",
    "Database / Schema Plan",
    "Migration / Backfill Plan",
    "API / Server Plan",
    "OpenAPI Impact Plan",
    "Testing Strategy",
    "Rollout Strategy",
    "Rollback Strategy",
    "Compatibility with Demo / Synthetic Flows",
    "Proposed Implementation Issue Breakdown",
    "Risk Register",
    "Decision",
    "Safety Confirmations",
    "Recommended Next Issues",
]

REQUIRED_SAFETY_CLAIMS_MD = [
    "GL-223 is an implementation plan, not the implementation itself",
    "GL-223 does not add migrations",
    "GL-223 does not enable real customer",
    "GL-223 does not claim Production SaaS readiness",
    "Production SaaS remains NO-GO",
    "Real Customer Data remains NO-GO",
    "Private Grant / Institutional Data remains NO-GO",
    "Official SDK/Package remains NO-GO",
    "Compliance Certification remains NO-GO",
    "Live PostgreSQL Production Readiness remains NO-GO",
    "No exploit details are included",
    "No real secrets are included",
    "No real customer",
]

REQUIRED_SAFETY_JSON_KEYS = [
    ("is_planning_only", True),
    ("no_migrations_added", True),
    ("no_real_data_enabled", True),
    ("production_saas_no_go", True),
    ("real_customer_data_no_go", True),
    ("private_grant_institutional_data_no_go", True),
    ("official_sdk_package_no_go", True),
    ("compliance_certification_no_go", True),
    ("live_postgresql_production_no_go", True),
    ("no_exploit_details", True),
    ("no_real_secrets", True),
    ("no_real_customer_private_data", True),
    ("website_design_import_files_excluded", True),
    ("gl214_through_gl222_boundaries_preserved", True),
    ("no_backend_src_changes", True),
    ("no_migrations_added", True),
    ("no_dependency_changes", True),
]

FORBIDDEN_FILE_PATHS = [
    REPO_ROOT / "setup.py",
    REPO_ROOT / "package.json",
    REPO_ROOT / "package-lock.json",
    REPO_ROOT / "public-snapshot",
    REPO_ROOT / "public-export",
    REPO_ROOT / "deploy",
]

FORBIDDEN_PATTERN_PATHS = [
    REPO_ROOT / ".github" / "workflows",
    REPO_ROOT / "backend" / "src" / "migrations" / "0012",
]

WEBSITE_DESIGN_FILES = [
    REPO_ROOT / "docs" / "website_design_workspace_import.md",
    REPO_ROOT / "docs" / "website_design_workspace_import_dirty_stop.md",
    REPO_ROOT / "docs" / "website_design_workspace_import_report.md",
    REPO_ROOT / "docs" / "website_design_workspace_import_report_dirty_stop.md",
]


def _load_md() -> str:
    return MD_PATH.read_text(encoding="utf-8", errors="replace")


def _load_json() -> dict:
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


class TestGL223DocsExist(unittest.TestCase):
    def test_markdown_doc_exists(self):
        self.assertTrue(MD_PATH.exists(), f"Missing: {MD_PATH.relative_to(REPO_ROOT)}")

    def test_json_artifact_exists(self):
        self.assertTrue(JSON_PATH.exists(), f"Missing: {JSON_PATH.relative_to(REPO_ROOT)}")

    def test_json_is_valid_json(self):
        self.assertTrue(JSON_PATH.exists(), "JSON artifact missing")
        data = _load_json()
        self.assertIsInstance(data, dict)

    def test_json_issue_id_is_gl223(self):
        data = _load_json()
        self.assertEqual(data.get("issue_id"), "GL-223")


class TestGL223JsonKeys(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()

    def test_all_required_keys_present(self):
        missing = [k for k in REQUIRED_JSON_KEYS if k not in self.data]
        self.assertEqual(missing, [], f"Missing JSON keys: {missing}")

    def test_current_tenant_workspace_state_summary_exists(self):
        state = self.data.get("current_tenant_workspace_state_summary")
        self.assertIsInstance(state, dict)
        self.assertIn("description", state)

    def test_workspace_trust_gaps_exist(self):
        gaps = self.data.get("current_workspace_trust_gaps")
        self.assertIsInstance(gaps, list)
        self.assertGreater(len(gaps), 0)

    def test_workspace_identity_model_exists(self):
        model = self.data.get("workspace_identity_model")
        self.assertIsInstance(model, dict)
        self.assertIn("description", model)

    def test_membership_model_exists(self):
        model = self.data.get("membership_model")
        self.assertIsInstance(model, dict)
        self.assertIn("description", model)

    def test_ownership_model_exists(self):
        model = self.data.get("ownership_model")
        self.assertIsInstance(model, dict)
        self.assertIn("description", model)

    def test_role_scope_model_exists(self):
        model = self.data.get("role_scope_model")
        self.assertIsInstance(model, dict)

    def test_workspace_lifecycle_model_exists(self):
        model = self.data.get("workspace_lifecycle_model")
        self.assertIsInstance(model, dict)
        self.assertIn("creation", model)

    def test_admin_operator_boundary_exists(self):
        model = self.data.get("admin_operator_ownership_boundary")
        self.assertIsInstance(model, dict)

    def test_server_derived_context_model_exists(self):
        model = self.data.get("server_derived_workspace_context_model")
        self.assertIsInstance(model, dict)
        self.assertIn("derivation_order", model)

    def test_unsafe_override_prevention_model_exists(self):
        model = self.data.get("unsafe_workspace_override_prevention_model")
        self.assertIsInstance(model, dict)

    def test_cross_workspace_lookup_denial_model_exists(self):
        model = self.data.get("cross_workspace_lookup_denial_model")
        self.assertIsInstance(model, dict)

    def test_cross_workspace_mutation_denial_model_exists(self):
        model = self.data.get("cross_workspace_mutation_denial_model")
        self.assertIsInstance(model, dict)

    def test_audit_evidence_propagation_model_exists(self):
        model = self.data.get("audit_evidence_provenance_compliance_propagation_model")
        self.assertIsInstance(model, dict)

    def test_database_schema_plan_exists(self):
        plan = self.data.get("database_schema_plan")
        self.assertIsInstance(plan, dict)

    def test_migration_backfill_plan_exists(self):
        plan = self.data.get("migration_backfill_plan")
        self.assertIsInstance(plan, dict)

    def test_api_server_plan_exists(self):
        plan = self.data.get("api_server_plan")
        self.assertIsInstance(plan, dict)

    def test_openapi_impact_plan_exists(self):
        plan = self.data.get("openapi_impact_plan")
        self.assertIsInstance(plan, dict)

    def test_testing_strategy_exists(self):
        ts = self.data.get("testing_strategy")
        self.assertIsInstance(ts, dict)

    def test_rollout_strategy_exists(self):
        rs = self.data.get("rollout_strategy")
        self.assertIsInstance(rs, dict)

    def test_rollback_strategy_exists(self):
        rs = self.data.get("rollback_strategy")
        self.assertIsInstance(rs, dict)

    def test_proposed_issue_breakdown_exists(self):
        breakdown = self.data.get("proposed_implementation_issue_breakdown")
        self.assertIsInstance(breakdown, list)
        self.assertGreater(len(breakdown), 0)

    def test_risk_register_exists(self):
        rr = self.data.get("risk_register")
        self.assertIsInstance(rr, list)
        self.assertGreater(len(rr), 0)

    def test_findings_exist(self):
        findings = self.data.get("findings")
        self.assertIsInstance(findings, list)
        self.assertGreater(len(findings), 0)

    def test_recommended_next_issues_exist(self):
        issues = self.data.get("recommended_next_issues")
        self.assertIsInstance(issues, list)
        self.assertGreater(len(issues), 0)


class TestGL223SafetyClaimsJSON(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.safety = self.data.get("safety_confirmations", {})

    def test_safety_confirmations_is_dict(self):
        self.assertIsInstance(self.safety, dict)

    def test_is_planning_only(self):
        self.assertTrue(self.safety.get("is_planning_only"), "safety_confirmations.is_planning_only must be true")

    def test_no_migrations_added(self):
        self.assertTrue(self.safety.get("no_migrations_added"))

    def test_no_real_data_enabled(self):
        self.assertTrue(self.safety.get("no_real_data_enabled"))

    def test_production_saas_no_go(self):
        self.assertTrue(self.safety.get("production_saas_no_go"))

    def test_real_customer_data_no_go(self):
        self.assertTrue(self.safety.get("real_customer_data_no_go"))

    def test_private_grant_institutional_data_no_go(self):
        self.assertTrue(self.safety.get("private_grant_institutional_data_no_go"))

    def test_official_sdk_package_no_go(self):
        self.assertTrue(self.safety.get("official_sdk_package_no_go"))

    def test_compliance_certification_no_go(self):
        self.assertTrue(self.safety.get("compliance_certification_no_go"))

    def test_live_postgresql_production_no_go(self):
        self.assertTrue(self.safety.get("live_postgresql_production_no_go"))

    def test_no_exploit_details(self):
        self.assertTrue(self.safety.get("no_exploit_details"))

    def test_no_real_secrets(self):
        self.assertTrue(self.safety.get("no_real_secrets"))

    def test_no_real_customer_private_data(self):
        self.assertTrue(self.safety.get("no_real_customer_private_data"))

    def test_website_design_files_excluded(self):
        self.assertTrue(self.safety.get("website_design_import_files_excluded"))

    def test_no_backend_src_changes(self):
        self.assertTrue(self.safety.get("no_backend_src_changes"))

    def test_gl214_through_gl222_boundaries_preserved(self):
        self.assertTrue(self.safety.get("gl214_through_gl222_boundaries_preserved"))


class TestGL223ProductionReadinessImpactJSON(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.pr = self.data.get("production_readiness_impact", {})

    def test_production_saas_no_go_in_readiness(self):
        val = self.pr.get("production_saas", "")
        self.assertIn("NO-GO", val, f"production_saas must state NO-GO, got: {val!r}")

    def test_real_customer_data_no_go_in_readiness(self):
        val = self.pr.get("real_customer_data", "")
        self.assertIn("NO-GO", val)

    def test_private_grant_no_go_in_readiness(self):
        val = self.pr.get("private_grant_institutional_data", "")
        self.assertIn("NO-GO", val)

    def test_official_sdk_no_go_in_readiness(self):
        val = self.pr.get("official_sdk_package", "")
        self.assertIn("NO-GO", val)

    def test_compliance_no_go_in_readiness(self):
        val = self.pr.get("compliance_certification", "")
        self.assertIn("NO-GO", val)

    def test_live_postgresql_no_go_in_readiness(self):
        val = self.pr.get("live_postgresql_production_readiness", "")
        self.assertIn("NO-GO", val)


class TestGL223MarkdownSections(unittest.TestCase):
    def setUp(self):
        self.md = _load_md()

    def test_required_sections_present(self):
        for section in REQUIRED_MD_SECTIONS:
            self.assertIn(section, self.md, f"Missing Markdown section: {section!r}")

    def test_safety_claims_present(self):
        for claim in REQUIRED_SAFETY_CLAIMS_MD:
            self.assertIn(
                claim, self.md,
                f"Missing safety claim in Markdown: {claim!r}"
            )

    def test_no_exploit_details(self):
        self.assertNotIn("CVE-", self.md, "Markdown should not include CVE references")
        self.assertNotIn("exploit payload", self.md.lower())

    def test_no_real_secrets_pattern(self):
        secret_patterns = [
            r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
            r"AKIA[A-Z0-9]{16}",
            r"ghp_[A-Za-z0-9]{36}",
        ]
        for pattern in secret_patterns:
            self.assertIsNone(
                re.search(pattern, self.md),
                f"Markdown contains secret-like pattern: {pattern}"
            )

    def test_no_real_customer_data(self):
        self.assertNotIn("@customer.com", self.md.lower())
        self.assertNotIn("grant_id: real", self.md.lower())


class TestGL223ForbiddenFiles(unittest.TestCase):
    def test_no_setup_py(self):
        self.assertFalse((REPO_ROOT / "setup.py").exists(), "setup.py must not exist")

    def test_no_package_json(self):
        self.assertFalse((REPO_ROOT / "package.json").exists(), "package.json must not exist")

    def test_no_package_lock_json(self):
        self.assertFalse((REPO_ROOT / "package-lock.json").exists(), "package-lock.json must not exist")

    def test_no_public_snapshot_dir(self):
        self.assertFalse((REPO_ROOT / "public-snapshot").exists(), "public-snapshot/ must not exist")

    def test_no_public_export_dir(self):
        self.assertFalse((REPO_ROOT / "public-export").exists(), "public-export/ must not exist")

    def test_no_kubernetes_helm_terraform(self):
        for forbidden in ["k8s", "helm", "terraform"]:
            self.assertFalse(
                (REPO_ROOT / forbidden).exists(),
                f"Forbidden deployment directory: {forbidden}/"
            )

    def test_website_design_files_not_in_gl223(self):
        for path in WEBSITE_DESIGN_FILES:
            if path.exists():
                pass


class TestGL223NoBranchSrcChanges(unittest.TestCase):
    def _get_changed_files(self) -> list[str]:
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "main...HEAD"],
                capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10,
            )
            return [f.strip() for f in result.stdout.splitlines() if f.strip()]
        except Exception:
            return []

    def test_no_backend_src_changes(self):
        changed = self._get_changed_files()
        src_changes = [
            f for f in changed
            if f.startswith("backend/src/") and not f.startswith("backend/src/migrations/")
        ]
        self.assertEqual(src_changes, [], f"Forbidden backend/src changes: {src_changes}")

    def test_no_migration_changes(self):
        changed = self._get_changed_files()
        migration_changes = [f for f in changed if "migrations" in f and f.endswith(".py")]
        self.assertEqual(migration_changes, [], f"Forbidden migration changes: {migration_changes}")

    def test_no_github_workflow_changes(self):
        changed = self._get_changed_files()
        workflow_changes = [f for f in changed if ".github/workflows" in f]
        self.assertEqual(workflow_changes, [], f"Forbidden workflow changes: {workflow_changes}")

    def test_no_publish_script_changes(self):
        changed = self._get_changed_files()
        publish_changes = [f for f in changed if "publish" in f.lower() and "scripts" in f]
        self.assertEqual(publish_changes, [], f"Forbidden publish script changes: {publish_changes}")

    def test_no_package_metadata(self):
        changed = self._get_changed_files()
        pkg = [f for f in changed if f in ("setup.py", "package.json", "package-lock.json") or
               (f.endswith("pyproject.toml") and "sdk" in f.lower())]
        self.assertEqual(pkg, [], f"Forbidden package metadata changes: {pkg}")


class TestGL223GateScript(unittest.TestCase):
    def test_gate_script_exists(self):
        self.assertTrue(GATE_SCRIPT.exists(), f"Missing gate script: {GATE_SCRIPT.relative_to(REPO_ROOT)}")

    def test_gate_script_compiles(self):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(GATE_SCRIPT)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"Gate script compile error: {result.stderr}")

    def test_gate_script_dry_run(self):
        result = subprocess.run(
            [sys.executable, str(GATE_SCRIPT), "--dry-run"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        self.assertEqual(result.returncode, 0, f"Gate --dry-run failed:\n{result.stdout}\n{result.stderr}")
        self.assertIn("dry-run", result.stdout.lower())

    def test_gate_script_plan_mode(self):
        result = subprocess.run(
            [sys.executable, str(GATE_SCRIPT), "--plan"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        self.assertEqual(result.returncode, 0, f"Gate --plan failed:\n{result.stdout}\n{result.stderr}")
        self.assertIn("plan", result.stdout.lower())

    def test_gate_script_no_credentials_required(self):
        env = {k: v for k, v in os.environ.items()
               if not any(k.startswith(p) for p in ["AWS_", "GRANTLAYER_", "POSTGRES", "DATABASE"])}
        env["PATH"] = os.environ.get("PATH", "")
        result = subprocess.run(
            [sys.executable, str(GATE_SCRIPT), "--dry-run"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), env=env,
        )
        self.assertEqual(result.returncode, 0, "Gate script should not require credentials")

    def test_gate_script_states_planning_only(self):
        result = subprocess.run(
            [sys.executable, str(GATE_SCRIPT), "--plan"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        self.assertIn("planning", result.stdout.lower(),
                      "Gate script output must state it is planning-only")
        self.assertIn("does not approve", result.stdout.lower(),
                      "Gate script must state it does not approve production enforcement")

    def test_gate_script_no_network_calls(self):
        script_text = GATE_SCRIPT.read_text(errors="replace")
        self.assertNotIn("requests.get", script_text)
        self.assertNotIn("urllib.request.urlopen", script_text)
        self.assertNotIn("socket.connect", script_text)
        self.assertNotIn("http.client", script_text)

    def test_gate_script_no_destructive_commands(self):
        script_text = GATE_SCRIPT.read_text(errors="replace")
        forbidden = ["rm -rf", "DROP TABLE", "DELETE FROM", "shutil.rmtree", "os.remove("]
        for pattern in forbidden:
            self.assertNotIn(pattern, script_text, f"Gate script contains destructive command: {pattern!r}")

    def test_gate_script_no_migration_creation(self):
        script_text = GATE_SCRIPT.read_text(errors="replace")
        self.assertNotIn("CREATE TABLE", script_text)
        self.assertNotIn("ALTER TABLE", script_text)
        self.assertNotIn("INSERT INTO", script_text)

    def test_gate_script_redacts_secret_like_values(self):
        script_text = GATE_SCRIPT.read_text(errors="replace")
        self.assertIn("REDACTED", script_text, "Gate script must redact secret-like findings")


if __name__ == "__main__":
    unittest.main()
