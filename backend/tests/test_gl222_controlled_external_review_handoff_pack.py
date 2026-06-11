"""Tests for GL-222 Controlled External Technical Review Handoff Pack."""

from __future__ import annotations

import json
import os
import py_compile
import subprocess
import sys
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "controlled_external_review_handoff_pack.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl222",
    "controlled_external_review_handoff_pack.json",
)
SCRIPT_PATH = os.path.join(REPO_ROOT, "scripts", "ops", "gl222_controlled_review_handoff_gate.py")

REQUIRED_JSON_KEYS = [
    "issue_id",
    "title",
    "result",
    "decision",
    "decision_rationale",
    "input_sources_reviewed",
    "current_controlled_external_review_posture",
    "handoff_package_purpose",
    "reviewer_scope",
    "excluded_scope",
    "eligible_review_materials",
    "prohibited_materials",
    "allowed_claims",
    "prohibited_claims",
    "data_boundary_synthetic_demo_only",
    "real_customer_private_grant_institutional_data_boundary",
    "production_saas_boundary",
    "public_snapshot_export_publish_boundary",
    "official_sdk_package_boundary",
    "compliance_certification_boundary",
    "live_postgres_production_readiness_boundary",
    "identity_access_status_after_gl219",
    "runtime_infrastructure_status_after_gl220",
    "workspace_status_after_gl221",
    "public_export_safety_status_after_gl218",
    "known_limitations",
    "known_full_suite_false_positive_classes",
    "reviewer_safe_verification_commands",
    "security_sensitive_reporting_instructions",
    "optional_handoff_gate_script_summary",
    "production_readiness_impact",
    "controlled_preview_impact",
    "remaining_blockers",
    "risk_register",
    "findings",
    "safety_confirmations",
    "recommended_next_issues",
]

REQUIRED_SECTIONS = [
    "## Context",
    "## Scope",
    "## Non-Goals",
    "## Input Sources Reviewed",
    "## Current Controlled External Review Posture",
    "## Handoff Package Purpose",
    "## Reviewer Scope",
    "## Excluded Scope",
    "## Eligible Review Materials",
    "## Prohibited Materials",
    "## Allowed Claims",
    "## Prohibited Claims",
    "## Data Boundary: Synthetic / Demo Only",
    "## Real Customer / Private Grant / Institutional Data Boundary",
    "## Production SaaS Boundary",
    "## Public Snapshot / Export / Publish Boundary",
    "## Official SDK / Package Boundary",
    "## Compliance Certification Boundary",
    "## Live PostgreSQL Production Readiness Boundary",
    "## Identity / Access Status After GL-219",
    "## Runtime / Infrastructure Status After GL-220",
    "## Workspace Status After GL-221",
    "## Public / Export Safety Status After GL-218",
    "## Known Limitations",
    "## Known Full-Suite False-Positive Classes",
    "## Reviewer-Safe Verification Commands",
    "## Security-Sensitive Reporting Instructions",
    "## Optional Handoff Gate Script Summary",
    "## Production-Readiness Impact",
    "## Controlled-Preview Impact",
    "## Remaining Blockers",
    "## Risk Register",
    "## Decision",
    "## Decision Rationale",
    "## Safety Confirmations",
    "## Recommended Next Issues",
]

ALLOWED_CHANGED_FILES = {
    "backend/tests/test_gl222_controlled_external_review_handoff_pack.py",
    "docs/controlled_external_review_handoff_pack.md",
    "docs/examples/gl222/controlled_external_review_handoff_pack.json",
    "scripts/ops/gl222_controlled_review_handoff_gate.py",
}


def _load_doc() -> str:
    with open(DOC_PATH, encoding="utf-8") as f:
        return f.read()


def _load_json() -> dict:
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _run_git(args: list[str]) -> list[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _branch_changed_files() -> set[str]:
    changed = set(_run_git(["diff", "--name-only", "main...HEAD"]))
    status_lines = _run_git(["status", "--porcelain", "--untracked-files=all"])
    for line in status_lines:
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        path = parts[1]
        if path.startswith("docs/website_design_") or path.startswith("docs/website-design-"):
            continue
        if path.startswith("website-design/"):
            continue
        changed.add(path)
    return changed


class TestGL222DocumentationArtifact(unittest.TestCase):
    def setUp(self):
        self.doc = _load_doc()
        self.data = _load_json()
        self.combined = self.doc + "\n" + json.dumps(self.data, sort_keys=True)
        self.combined_lower = self.combined.lower()

    def test_files_exist_and_json_valid(self):
        self.assertTrue(os.path.isfile(DOC_PATH), f"Missing doc: {DOC_PATH}")
        self.assertTrue(os.path.isfile(JSON_PATH), f"Missing JSON: {JSON_PATH}")
        self.assertIsInstance(self.data, dict)

    def test_issue_id_gl222(self):
        self.assertEqual(self.data.get("issue_id"), "GL-222")

    def test_required_json_keys_exist(self):
        for key in REQUIRED_JSON_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, self.data, f"Missing JSON key: {key}")

    def test_required_markdown_sections_exist(self):
        for section in REQUIRED_SECTIONS:
            with self.subTest(section=section):
                self.assertIn(section, self.doc, f"Missing section: {section}")

    def test_controlled_external_review_strict_boundaries(self):
        posture = self.data.get("current_controlled_external_review_posture", {})
        review = posture.get("controlled_external_technical_review", "")
        self.assertIn("strict boundaries", review.lower(),
                      "Controlled external review must be strict-boundaries only")
        self.assertIn("strict boundaries", self.combined_lower,
                      "Doc must state strict boundaries for controlled external review")

    def test_synthetic_demo_only_boundary_exists(self):
        boundary = self.data.get("data_boundary_synthetic_demo_only", {})
        self.assertTrue(boundary.get("synthetic_demo_only") is True,
                        "data_boundary_synthetic_demo_only.synthetic_demo_only must be true")
        self.assertIn("synthetic", self.combined_lower)
        self.assertIn("demo only", self.combined_lower)

    def test_production_saas_is_no_go(self):
        posture = self.data.get("current_controlled_external_review_posture", {})
        self.assertEqual(posture.get("production_saas"), "NO-GO",
                         "production_saas must be NO-GO in posture")
        boundary = self.data.get("production_saas_boundary", {})
        self.assertEqual(boundary.get("status"), "NO-GO",
                         "production_saas_boundary.status must be NO-GO")
        safety = self.data.get("safety_confirmations", {})
        self.assertTrue(safety.get("production_saas_no_go") is True,
                        "safety_confirmations.production_saas_no_go must be true")
        self.assertIn("production saas remains no-go", self.combined_lower)

    def test_real_customer_private_grant_institutional_data_is_no_go(self):
        posture = self.data.get("current_controlled_external_review_posture", {})
        self.assertEqual(posture.get("real_customer_data"), "NO-GO")
        self.assertEqual(posture.get("private_grant_institutional_data"), "NO-GO")
        safety = self.data.get("safety_confirmations", {})
        self.assertTrue(safety.get("real_customer_private_grant_institutional_data_no_go") is True)
        self.assertIn("real customer", self.combined_lower)
        self.assertIn("no-go", self.combined_lower)

    def test_official_sdk_package_is_no_go(self):
        posture = self.data.get("current_controlled_external_review_posture", {})
        self.assertEqual(posture.get("official_sdk_package"), "NO-GO")
        safety = self.data.get("safety_confirmations", {})
        self.assertTrue(safety.get("official_sdk_package_no_go") is True)
        self.assertIn("official sdk/package remains no-go", self.combined_lower)

    def test_compliance_certification_is_no_go(self):
        posture = self.data.get("current_controlled_external_review_posture", {})
        self.assertEqual(posture.get("compliance_certification"), "NO-GO")
        safety = self.data.get("safety_confirmations", {})
        self.assertTrue(safety.get("compliance_certification_no_go") is True)
        self.assertIn("compliance certification remains no-go", self.combined_lower)

    def test_live_postgresql_production_readiness_is_no_go(self):
        posture = self.data.get("current_controlled_external_review_posture", {})
        self.assertEqual(posture.get("live_postgres_production_readiness"), "NO-GO")
        safety = self.data.get("safety_confirmations", {})
        self.assertTrue(safety.get("live_postgresql_production_readiness_no_go") is True)
        self.assertIn("live postgresql production readiness remains no-go", self.combined_lower)

    def test_public_snapshot_requires_later_explicit_approval(self):
        boundary = self.data.get("public_snapshot_export_publish_boundary", {})
        self.assertTrue(boundary.get("gl222_does_not_approve") is True)
        self.assertTrue(boundary.get("gl222_does_not_initiate") is True)
        self.assertIn("separate explicit gate", self.combined_lower)

    def test_docs_do_not_create_or_approve_public_export(self):
        safety = self.data.get("safety_confirmations", {})
        self.assertTrue(safety.get("gl222_does_not_create_public_export") is True)
        self.assertNotIn("public export directory created: true", self.combined_lower)
        self.assertNotIn("gl222 creates a public export", self.combined_lower)
        self.assertNotIn("gl222 approves public export", self.combined_lower)

    def test_docs_do_not_include_reviewer_outreach_as_action(self):
        safety = self.data.get("safety_confirmations", {})
        self.assertTrue(safety.get("gl222_is_internal_handoff_pack_not_reviewer_outreach") is True)
        self.assertIn("does not contact", self.combined_lower)
        self.assertIn("not reviewer outreach", self.combined_lower)

    def test_security_sensitive_reporting_instructions_exist(self):
        reporting = self.data.get("security_sensitive_reporting_instructions", {})
        self.assertIn("github security advisories", reporting.get("route_to", "").lower())
        self.assertIn("github security advisories", self.combined_lower)

    def test_known_false_positive_classes_documented(self):
        classes = self.data.get("known_full_suite_false_positive_classes", [])
        self.assertGreater(len(classes), 0, "Known false-positive classes must be documented")
        class_names = [c.get("class", "") for c in classes]
        self.assertTrue(any("scope_guard" in c or "scope-guard" in c for c in class_names),
                        "Must document stale scope-guard false positives")
        for c in classes:
            self.assertFalse(c.get("real_regression", True),
                             f"False-positive class must have real_regression: false: {c}")

    def test_reviewer_safe_verification_commands_documented(self):
        commands = self.data.get("reviewer_safe_verification_commands", [])
        self.assertGreater(len(commands), 0, "Reviewer-safe verification commands must be documented")
        commands_str = " ".join(commands)
        self.assertIn("test_gl222", commands_str)
        self.assertIn("grant_lifecycle_evidence_bundle", commands_str)
        self.assertIn("--dry-run", commands_str)
        self.assertIn("--plan", commands_str)

    def test_risk_register_has_required_fields(self):
        register = self.data.get("risk_register", [])
        self.assertGreater(len(register), 0, "Risk register must be non-empty")
        for entry in register:
            with self.subTest(risk=entry.get("risk")):
                self.assertIn("severity", entry)
                self.assertIn("status", entry)
                self.assertIn("mitigation", entry)
                self.assertIn("remaining_work", entry)

    def test_no_exploit_details(self):
        safety = self.data.get("safety_confirmations", {})
        self.assertTrue(safety.get("no_exploit_details") is True)
        self.assertIn("no exploit details", self.combined_lower)
        for term in ["exploit code", "proof of concept exploit", "0day", "zero-day exploit"]:
            self.assertNotIn(term, self.combined_lower, f"Must not include: {term}")

    def test_no_real_secrets(self):
        safety = self.data.get("safety_confirmations", {})
        self.assertTrue(safety.get("no_real_secrets") is True)
        self.assertIn("no real secrets", self.combined_lower)
        import re
        self.assertIsNone(re.search(r"-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----", self.combined))
        self.assertIsNone(re.search(r"postgres(?:ql)?://[^@\s]+:[^@\s]+@[^\s]+", self.combined))

    def test_no_real_customer_private_data(self):
        safety = self.data.get("safety_confirmations", {})
        self.assertTrue(safety.get("no_real_customer_private_data") is True)
        self.assertIn("no real customer", self.combined_lower)


class TestGL222ScopeViolations(unittest.TestCase):
    def setUp(self):
        self.changed = _branch_changed_files()

    def test_no_backend_src_changes(self):
        violations = [f for f in self.changed if f.startswith("backend/src/")]
        self.assertEqual(violations, [], f"No backend/src changes allowed: {violations}")

    def test_no_migrations_db_schema_dependency_changes(self):
        forbidden_prefixes = ["backend/migrations/", "migrations/", "alembic/"]
        forbidden_names = ["setup.py", "requirements.txt", "Pipfile", "pyproject.toml"]
        violations = []
        for f in self.changed:
            if any(f.startswith(p) for p in forbidden_prefixes):
                violations.append(f)
            name = os.path.basename(f)
            if name in forbidden_names and "sdk" not in f.lower():
                violations.append(f)
        self.assertEqual(violations, [], f"No migration/DB/schema/dependency changes allowed: {violations}")

    def test_no_github_workflow_changes(self):
        violations = [f for f in self.changed if f.startswith(".github/workflows/")]
        self.assertEqual(violations, [], f"No GitHub workflow changes allowed: {violations}")

    def test_no_snapshot_publish_script_changes(self):
        violations = [f for f in self.changed
                      if "snapshot" in f.lower() and "publish" in f.lower() and f.endswith(".py")]
        self.assertEqual(violations, [], f"No snapshot publish script changes allowed: {violations}")

    def test_no_package_metadata(self):
        forbidden = {"setup.py", "package.json", "package-lock.json"}
        violations = [f for f in self.changed if os.path.basename(f) in forbidden]
        self.assertEqual(violations, [], f"No package metadata allowed: {violations}")

    def test_no_public_export_directory(self):
        for candidate in ["public-export", "public_export", "snapshot-export", "snapshot_export"]:
            path = os.path.join(REPO_ROOT, candidate)
            self.assertFalse(os.path.isdir(path), f"No public export directory: {path}")

    def test_no_public_snapshot_worktree(self):
        for candidate in ["public-snapshot", "public_snapshot", "snapshot-worktree"]:
            path = os.path.join(REPO_ROOT, candidate)
            self.assertFalse(os.path.isdir(path), f"No public snapshot worktree: {path}")

    def test_no_deployment_cloud_kubernetes_terraform_helm_files(self):
        forbidden_terms = ["kubernetes", "terraform", "helm", "k8s"]
        violations = [f for f in self.changed
                      if any(t in f.lower() for t in forbidden_terms)]
        self.assertEqual(violations, [], f"No deployment/cloud/Kubernetes/Terraform/Helm changes: {violations}")

    def test_no_tls_certificate_private_key_files(self):
        forbidden_extensions = {".pem", ".crt", ".cer", ".key", ".p12", ".pfx"}
        violations = [f for f in self.changed
                      if os.path.splitext(f)[1].lower() in forbidden_extensions]
        self.assertEqual(violations, [], f"No TLS cert/private key files: {violations}")

    def test_only_allowed_files_changed(self):
        if _run_git(["rev-parse", "--abbrev-ref", "HEAD"])[0] != "gl-222-controlled-external-review-handoff-pack":
            return
        unexpected = self.changed - ALLOWED_CHANGED_FILES
        unexpected = {
            f for f in unexpected
            if not f.startswith("docs/website_design_")
            and not f.startswith("docs/website-design-")
            and not f.startswith("website-design/")
        }
        self.assertEqual(unexpected, set(),
                         f"Unexpected files changed in GL-222: {sorted(unexpected)}")

    def test_unrelated_website_design_import_files_excluded(self):
        forbidden_files = [
            "website-design/",
            "docs/website_design_workspace_import_report.md",
            "docs/website_design_workspace_import_report_dirty_stop.md",
            "docs/website-design-workspace-import-report.md",
            "docs/website-design-workspace-import-report-dirty-stop.md",
        ]
        for f in forbidden_files:
            self.assertNotIn(f, self.changed,
                             f"Unrelated website-design file must not be in GL-222 changes: {f}")


class TestGL222HandoffGateScript(unittest.TestCase):
    def test_script_exists(self):
        self.assertTrue(os.path.isfile(SCRIPT_PATH), f"Gate script missing: {SCRIPT_PATH}")

    def test_script_compiles(self):
        py_compile.compile(SCRIPT_PATH, doraise=True)

    def _run_script(self, *flags: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, SCRIPT_PATH, *flags],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )

    def test_dry_run_flag(self):
        result = self._run_script("--dry-run")
        output = result.stdout + result.stderr
        self.assertIn("dry-run", output.lower(),
                      "--dry-run must print mode indicator")

    def test_plan_flag(self):
        result = self._run_script("--plan")
        output = result.stdout + result.stderr
        self.assertIn("plan", output.lower(),
                      "--plan must print mode indicator")

    def test_not_approval_to_publish_stated(self):
        result = self._run_script("--plan")
        output = result.stdout + result.stderr
        self.assertIn("not approval to publish", output.lower(),
                      "Script must state it is NOT approval to publish")

    def test_not_full_security_audit_stated(self):
        result = self._run_script("--plan")
        output = result.stdout + result.stderr
        self.assertIn("not a full security audit", output.lower(),
                      "Script must state it is NOT a full security audit")

    def test_does_not_create_public_export_directories(self):
        forbidden = [
            os.path.join(REPO_ROOT, "public-export"),
            os.path.join(REPO_ROOT, "public_export"),
            os.path.join(REPO_ROOT, "public-snapshot"),
            os.path.join(REPO_ROOT, "public_snapshot"),
        ]
        self._run_script("--dry-run")
        for path in forbidden:
            self.assertFalse(os.path.isdir(path),
                             f"Script must not create: {path}")

    def test_does_not_require_credentials(self):
        env = {k: v for k, v in os.environ.items()
               if not any(k.startswith(p) for p in
                          ["POSTGRES", "DATABASE", "DB_", "SECRET", "TOKEN", "AWS", "SMTP"])}
        result = subprocess.run(
            [sys.executable, SCRIPT_PATH, "--dry-run"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertNotEqual(result.returncode, 2,
                            "Script must not fail with usage error when no credentials provided")

    def test_does_not_contact_network(self):
        import ast
        with open(SCRIPT_PATH, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        forbidden_network = {"requests", "urllib.request", "httpx", "aiohttp", "socket"}
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
        for mod in forbidden_network:
            self.assertNotIn(mod, imports,
                             f"Script must not import network module: {mod}")

    def test_does_not_run_destructive_commands(self):
        with open(SCRIPT_PATH, encoding="utf-8") as f:
            source = f.read()
        for term in ["rm -rf", "DROP TABLE", "git push", "git reset --hard",
                     "shutil.rmtree", "os.remove", "os.unlink"]:
            self.assertNotIn(term, source,
                             f"Script must not contain destructive operation: {term}")

    def test_redacts_secret_like_values(self):
        with open(SCRIPT_PATH, encoding="utf-8") as f:
            source = f.read()
        self.assertIn("REDACTED", source,
                      "Script must contain redaction logic for secret-like values")
