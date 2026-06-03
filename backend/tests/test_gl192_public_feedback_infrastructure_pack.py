"""GL-192 public feedback infrastructure pack tests.

Verifies that the public feedback infrastructure docs, JSON artifact, and issue
templates are in place, safe, and confined to the allowed file scope.
"""

import json
import subprocess
import sys
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[2]

PACK_DOC = REPO_ROOT / "docs" / "public_feedback_infrastructure_pack.md"
ARTIFACT_PATH = (
    REPO_ROOT
    / "docs"
    / "examples"
    / "gl192"
    / "public_feedback_infrastructure_pack.json"
)
TEMPLATE_DIR = REPO_ROOT / ".github" / "ISSUE_TEMPLATE"

ALLOWED_CHANGED_FILES = {
    "docs/public_feedback_infrastructure_pack.md",
    "docs/examples/gl192/public_feedback_infrastructure_pack.json",
    "backend/tests/test_gl192_public_feedback_infrastructure_pack.py",
}

FORBIDDEN_PREFIXES = (
    "backend/src/",
    "sdk/",
    "examples/first_verifiable_output.py",
    "examples/grant_lifecycle_evidence_bundle.py",
    "examples/langgraph_langchain/",
    "frontend/",
    "website/",
    "dashboard/",
    ".github/workflows/",
    "scripts/build-clean-public-snapshot.sh",
    "migrations/",
    "requirements.txt",
    "requirements-dev.txt",
    "docker-compose",
    "Dockerfile",
)

FORBIDDEN_FILENAMES = {
    "docs/openapi.yaml",
    "data/grantlayer.db",
}

ALLOWED_RESULT_VALUES = {
    "public_feedback_infrastructure_complete",
    "public_feedback_templates_deferred",
    "blocked_unexpected_scope",
    "blocked_public_safety",
    "blocked_other_with_reason",
}

REQUIRED_FEEDBACK_CATEGORIES = {
    "quickstart-feedback",
    "first-output-feedback",
    "grant-lifecycle-example-feedback",
    "documentation-feedback",
    "developer-experience-feedback",
    "bug-report",
    "feature-request",
    "product-question",
    "security-sensitive-report",
}

REQUIRED_SEVERITY_LEVELS = {"critical", "high", "medium", "low", "info"}

REQUIRED_TYPE_LABELS = {"type:bug", "type:docs", "type:dx", "type:question", "type:feature"}
REQUIRED_AREA_LABELS = {"area:quickstart", "area:first-output", "area:grant-lifecycle-example"}
REQUIRED_SEVERITY_LABELS = {"severity:critical", "severity:high", "severity:medium", "severity:low"}
REQUIRED_STATUS_LABELS = {"status:needs-triage", "status:accepted", "status:deferred"}
REQUIRED_SAFETY_LABELS = {"safety:no-secrets", "safety:needs-advisory"}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path):
    return json.loads(_read_text(path))


def _changed_files() -> list[str]:
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout
    changed = []
    for entry in status.split("\0"):
        if entry.strip():
            changed.append(entry[3:].strip() if len(entry) > 3 else entry.strip())
    if changed:
        return changed

    diff = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout
    return [line.strip() for line in diff.splitlines() if line.strip()]


class TestGL192FilesExist(unittest.TestCase):
    def test_pack_doc_exists(self):
        self.assertTrue(PACK_DOC.is_file(), "docs/public_feedback_infrastructure_pack.md must exist")

    def test_artifact_exists(self):
        self.assertTrue(
            ARTIFACT_PATH.is_file(),
            "docs/examples/gl192/public_feedback_infrastructure_pack.json must exist",
        )


class TestGL192Artifact(unittest.TestCase):
    def setUp(self):
        self.artifact = _read_json(ARTIFACT_PATH)

    def test_artifact_valid_json(self):
        self.assertIsInstance(self.artifact, dict)

    def test_issue_id(self):
        self.assertEqual(self.artifact["issue_id"], "GL-192")

    def test_decision_is_valid(self):
        decision = self.artifact.get("decision")
        self.assertIn(
            decision,
            ("templates_added", "templates_deferred"),
            "decision must be templates_added or templates_deferred",
        )

    def test_result_is_allowed(self):
        self.assertIn(self.artifact["result"], ALLOWED_RESULT_VALUES)

    def test_public_feedback_categories_present(self):
        cats = self.artifact.get("public_feedback_categories")
        self.assertIsInstance(cats, list)
        self.assertGreater(len(cats), 0)

    def test_required_feedback_categories_present(self):
        cats = self.artifact.get("public_feedback_categories", [])
        names = {c["name"] for c in cats if isinstance(c, dict)}
        missing = REQUIRED_FEEDBACK_CATEGORIES - names
        self.assertEqual(
            missing,
            set(),
            f"Missing required feedback categories: {missing}",
        )

    def test_severity_model_present(self):
        sm = self.artifact.get("severity_model", {})
        levels = set(sm.get("levels", []))
        missing = REQUIRED_SEVERITY_LEVELS - levels
        self.assertEqual(missing, set(), f"Missing severity levels: {missing}")

    def test_label_taxonomy_type_labels(self):
        plan = self.artifact.get("label_taxonomy_plan", {})
        labels = set(plan.get("type_labels", []))
        missing = REQUIRED_TYPE_LABELS - labels
        self.assertEqual(missing, set(), f"Missing type labels: {missing}")

    def test_label_taxonomy_area_labels(self):
        plan = self.artifact.get("label_taxonomy_plan", {})
        labels = set(plan.get("area_labels", []))
        missing = REQUIRED_AREA_LABELS - labels
        self.assertEqual(missing, set(), f"Missing area labels: {missing}")

    def test_label_taxonomy_severity_labels(self):
        plan = self.artifact.get("label_taxonomy_plan", {})
        labels = set(plan.get("severity_labels", []))
        missing = REQUIRED_SEVERITY_LABELS - labels
        self.assertEqual(missing, set(), f"Missing severity labels: {missing}")

    def test_label_taxonomy_status_labels(self):
        plan = self.artifact.get("label_taxonomy_plan", {})
        labels = set(plan.get("status_labels", []))
        missing = REQUIRED_STATUS_LABELS - labels
        self.assertEqual(missing, set(), f"Missing status labels: {missing}")

    def test_label_taxonomy_safety_labels(self):
        plan = self.artifact.get("label_taxonomy_plan", {})
        labels = set(plan.get("safety_labels", []))
        missing = REQUIRED_SAFETY_LABELS - labels
        self.assertEqual(missing, set(), f"Missing safety labels: {missing}")

    def test_label_taxonomy_is_recommended_manual_only(self):
        plan = self.artifact.get("label_taxonomy_plan", {})
        status = plan.get("taxonomy_status", "")
        note = plan.get("note", "")
        self.assertTrue(
            "recommended" in status.lower() or "manual" in status.lower()
            or "recommended" in note.lower() or "manual" in note.lower(),
            "label taxonomy must be documented as recommended/manual only, not API-applied",
        )

    def test_security_sensitive_routing_to_advisories(self):
        routing = self.artifact.get("security_sensitive_routing", {})
        channel = routing.get("channel", "")
        url = routing.get("url", "")
        self.assertIn(
            "Security Advisories",
            channel,
            "security_sensitive_routing channel must reference GitHub Security Advisories",
        )
        self.assertIn("security/advisories", url)

    def test_no_github_api_label_changes_performed(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_github_api_label_changes_performed"))

    def test_no_github_issue_changes_performed(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_github_issue_changes_performed"))

    def test_no_reviewer_outreach_sent(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_reviewer_outreach_sent"))

    def test_no_github_push_confirmation(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_github_push_performed"))

    def test_no_visibility_change_confirmation(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_visibility_change_performed"))

    def test_internal_repo_not_pushed_directly(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("internal_repo_not_pushed_directly_to_github"))

    def test_no_backend_src_changes(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_backend_src_changes"))

    def test_no_openapi_changes(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_openapi_changes"))

    def test_no_migration_db_dependency_changes(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_migration_db_dependency_changes"))

    def test_no_frontend_website_design_changes(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_frontend_website_design_changes"))

    def test_no_github_workflow_changes(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_github_workflow_changes"))

    def test_no_snapshot_publish_script_behavior_changes(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_snapshot_publish_script_behavior_changes"))

    def test_no_production_saas_claim(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_production_saas_claim"))

    def test_tenant_isolation_not_claimed(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("tenant_isolation_not_claimed"))

    def test_no_real_customer_data_requested(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_real_customer_data_requested"))

    def test_no_private_grant_data_requested(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_private_grant_data_requested"))

    def test_no_secrets_requested(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_secrets_requested"))

    def test_no_exploit_details_included(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_exploit_details_included"))

    def test_security_sensitive_routed_to_advisories_confirmation(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("security_sensitive_reports_routed_to_github_security_advisories"))

    def test_round_2_reviewer_guidance_present(self):
        guidance = self.artifact.get("round_2_reviewer_guidance", {})
        self.assertIsInstance(guidance, dict)
        self.assertIn("what_reviewers_can_try", guidance)

    def test_round_2_no_outreach_sent(self):
        guidance = self.artifact.get("round_2_reviewer_guidance", {})
        self.assertTrue(guidance.get("no_outreach_sent"))

    def test_changed_files_within_scope(self):
        changed = set(self.artifact.get("changed_files", []))
        extra = changed - ALLOWED_CHANGED_FILES
        self.assertEqual(extra, set(), f"Unexpected files in artifact changed_files: {extra}")


class TestGL192DocContent(unittest.TestCase):
    def setUp(self):
        self.doc = _read_text(PACK_DOC)
        self.doc_lower = self.doc.lower()

    def test_doc_references_issue_id(self):
        self.assertIn("GL-192", self.doc)

    def test_doc_has_feedback_categories_section(self):
        self.assertTrue(
            "feedback" in self.doc_lower and "categor" in self.doc_lower,
            "doc must have a feedback categories section",
        )

    def test_doc_has_severity_model(self):
        self.assertIn("severity", self.doc_lower)

    def test_doc_has_label_taxonomy(self):
        self.assertIn("label", self.doc_lower)

    def test_doc_has_security_advisory_routing(self):
        self.assertIn("security advisories", self.doc_lower)

    def test_doc_no_production_saas_claim(self):
        lower = self.doc_lower
        self.assertFalse(
            "production saas ready" in lower or "production-ready saas" in lower,
            "doc must not claim production SaaS readiness",
        )

    def test_doc_no_tenant_isolation_claim(self):
        # The doc must include the correct caveat and must not make a bare positive claim.
        import re
        self.assertTrue(
            re.search(r"tenant isolation is not implemented", self.doc_lower),
            "doc must include 'tenant isolation is not implemented' caveat",
        )
        # Strip all recognised negation/non-goal contexts before checking for bare claim.
        cleaned = self.doc_lower
        for pattern in (
            r"tenant isolation is not implemented",
            r"do not assume tenant isolation is implemented",
            r"claiming(?:[^.]*?)tenant isolation is implemented",
            r"or tenant isolation is implemented",
        ):
            cleaned = re.sub(pattern, "", cleaned)
        self.assertNotIn(
            "tenant isolation is implemented",
            cleaned,
            "doc must not make a bare positive claim that tenant isolation is implemented",
        )

    def test_doc_states_no_secrets(self):
        self.assertTrue(
            "secret" in self.doc_lower or "no secrets" in self.doc_lower,
            "doc must state no secrets policy",
        )

    def test_doc_states_no_customer_data(self):
        self.assertTrue(
            "customer data" in self.doc_lower or "no real customer" in self.doc_lower,
            "doc must state no real customer data policy",
        )

    def test_doc_states_no_private_grants(self):
        self.assertTrue(
            "private grant" in self.doc_lower or "institutional" in self.doc_lower,
            "doc must state no private grant/institutional data policy",
        )

    def test_doc_states_no_exploit_details_publicly(self):
        self.assertTrue(
            "exploit" in self.doc_lower or "exploit details" in self.doc_lower,
            "doc must mention exploit details routing",
        )

    def test_doc_states_synthetic_demo_data_only(self):
        self.assertTrue(
            "synthetic" in self.doc_lower or "demo data" in self.doc_lower,
            "doc must state synthetic/demo data only",
        )

    def test_doc_has_round_2_reviewer_guidance(self):
        self.assertTrue(
            "round-2" in self.doc_lower or "reviewer" in self.doc_lower,
            "doc must include round-2 reviewer guidance",
        )

    def test_doc_states_no_outreach_sent(self):
        self.assertTrue(
            "no outreach" in self.doc_lower or "outreach is not sent" in self.doc_lower
            or "not sent" in self.doc_lower,
            "doc must state no outreach is sent by this issue",
        )

    def test_doc_has_non_goals(self):
        self.assertIn("non-goal", self.doc_lower)

    def test_doc_has_safety_confirmations(self):
        self.assertIn("safety confirmation", self.doc_lower)


class TestGL192IssueTemplates(unittest.TestCase):
    """Verify that existing issue templates meet GL-192 safety requirements."""

    def setUp(self):
        self.artifact = _read_json(ARTIFACT_PATH)
        self.templates_added = self.artifact.get("templates_added", False)

    def _read_template(self, filename: str) -> str:
        path = TEMPLATE_DIR / filename
        if path.is_file():
            return path.read_text(encoding="utf-8")
        return ""

    @unittest.skipUnless(
        (Path(__file__).resolve().parents[2] / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml").is_file(),
        "bug_report.yml not present",
    )
    def test_bug_report_template_has_no_secrets_warning(self):
        content = self._read_template("bug_report.yml")
        self.assertTrue(
            "real secrets" in content.lower() or "no secrets" in content.lower()
            or "not include real secrets" in content.lower(),
            "bug_report.yml must warn against including real secrets",
        )

    @unittest.skipUnless(
        (Path(__file__).resolve().parents[2] / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml").is_file(),
        "bug_report.yml not present",
    )
    def test_bug_report_template_has_no_customer_data_warning(self):
        content = self._read_template("bug_report.yml")
        self.assertTrue(
            "customer data" in content.lower() or "real customer" in content.lower(),
            "bug_report.yml must warn against including real customer data",
        )

    @unittest.skipUnless(
        (Path(__file__).resolve().parents[2] / ".github" / "ISSUE_TEMPLATE" / "developer_feedback.yml").is_file(),
        "developer_feedback.yml not present",
    )
    def test_developer_feedback_template_has_safety_checklist(self):
        content = self._read_template("developer_feedback.yml")
        self.assertIn(
            "safety_checklist",
            content,
            "developer_feedback.yml must have a safety_checklist section",
        )

    @unittest.skipUnless(
        (Path(__file__).resolve().parents[2] / ".github" / "ISSUE_TEMPLATE" / "developer_feedback.yml").is_file(),
        "developer_feedback.yml not present",
    )
    def test_developer_feedback_template_has_no_secrets_warning(self):
        content = self._read_template("developer_feedback.yml")
        self.assertTrue(
            "real secrets" in content.lower() or "not include real secrets" in content.lower(),
            "developer_feedback.yml must warn against including real secrets",
        )

    @unittest.skipUnless(
        (Path(__file__).resolve().parents[2] / ".github" / "ISSUE_TEMPLATE" / "documentation_feedback.yml").is_file(),
        "documentation_feedback.yml not present",
    )
    def test_documentation_feedback_template_has_safety_checklist(self):
        content = self._read_template("documentation_feedback.yml")
        self.assertIn(
            "safety_checklist",
            content,
            "documentation_feedback.yml must have a safety_checklist section",
        )

    @unittest.skipUnless(
        (Path(__file__).resolve().parents[2] / ".github" / "ISSUE_TEMPLATE" / "security_report.md").is_file(),
        "security_report.md not present",
    )
    def test_security_report_template_routes_to_advisories(self):
        content = self._read_template("security_report.md")
        self.assertTrue(
            "Security Advisories" in content or "security/advisories" in content,
            "security_report.md must route to GitHub Security Advisories",
        )

    @unittest.skipUnless(
        (Path(__file__).resolve().parents[2] / ".github" / "ISSUE_TEMPLATE" / "security_report.md").is_file(),
        "security_report.md not present",
    )
    def test_security_report_template_prohibits_public_issue(self):
        content = self._read_template("security_report.md")
        lower = content.lower()
        self.assertTrue(
            "do not open a public" in lower or "not open a public issue" in lower,
            "security_report.md must instruct reporters not to open public issues for sensitive findings",
        )

    @unittest.skipUnless(
        (Path(__file__).resolve().parents[2] / ".github" / "ISSUE_TEMPLATE" / "config.yml").is_file(),
        "config.yml not present",
    )
    def test_config_yml_disables_blank_issues(self):
        content = self._read_template("config.yml")
        self.assertIn(
            "blank_issues_enabled: false",
            content,
            "config.yml must disable blank issues",
        )

    def test_no_github_workflow_added(self):
        """GL-192 must not add any .github/workflows/ files."""
        changed = _changed_files()
        workflow_changes = [f for f in changed if f.startswith(".github/workflows/")]
        self.assertEqual(
            workflow_changes,
            [],
            f"GL-192 must not add GitHub workflow files: {workflow_changes}",
        )


class TestGL192ScopeGuard(unittest.TestCase):
    def test_changed_files_within_allowed_scope(self):
        changed = _changed_files()
        violations = []
        for f in changed:
            if f in ALLOWED_CHANGED_FILES:
                continue
            # Allow .github/ISSUE_TEMPLATE/* but not .github/workflows/*
            if f.startswith(".github/ISSUE_TEMPLATE/"):
                continue
            for prefix in FORBIDDEN_PREFIXES:
                if f.startswith(prefix):
                    violations.append(f)
                    break
            if f in FORBIDDEN_FILENAMES:
                violations.append(f)
        self.assertEqual(
            violations,
            [],
            f"Forbidden files changed: {violations}",
        )

    def test_no_backend_src_changes(self):
        changed = _changed_files()
        violations = [f for f in changed if f.startswith("backend/src/")]
        self.assertEqual(violations, [], f"backend/src/ files changed: {violations}")

    def test_no_openapi_changes(self):
        changed = _changed_files()
        violations = [f for f in changed if "openapi" in f.lower()]
        self.assertEqual(violations, [], f"OpenAPI files changed: {violations}")

    def test_no_migration_changes(self):
        changed = _changed_files()
        violations = [f for f in changed if "migration" in f.lower()]
        self.assertEqual(violations, [], f"Migration files changed: {violations}")

    def test_no_db_schema_changes(self):
        changed = _changed_files()
        violations = [f for f in changed if "schema" in f.lower() or f.endswith(".sql")]
        self.assertEqual(violations, [], f"DB/schema files changed: {violations}")

    def test_no_dependency_manifest_changes(self):
        changed = _changed_files()
        violations = [
            f for f in changed
            if f in (
                "requirements.txt",
                "requirements-dev.txt",
                "pyproject.toml",
                "setup.py",
                "setup.cfg",
            )
        ]
        self.assertEqual(violations, [], f"Dependency manifests changed: {violations}")

    def test_no_sdk_implementation_changes(self):
        changed = _changed_files()
        violations = [f for f in changed if f.startswith("sdk/")]
        self.assertEqual(violations, [], f"SDK files changed: {violations}")

    def test_no_examples_runtime_implementation_changes(self):
        changed = _changed_files()
        violations = [
            f for f in changed
            if f.startswith("examples/") and f.endswith(".py")
        ]
        self.assertEqual(violations, [], f"Example runtime .py files changed: {violations}")

    def test_no_frontend_website_design_changes(self):
        changed = _changed_files()
        violations = [
            f for f in changed
            if f.startswith("frontend/") or f.startswith("website/") or f.startswith("dashboard/")
        ]
        self.assertEqual(violations, [], f"Frontend/website/design files changed: {violations}")

    def test_no_github_workflow_changes(self):
        changed = _changed_files()
        violations = [f for f in changed if f.startswith(".github/workflows/")]
        self.assertEqual(violations, [], f"GitHub workflow files changed: {violations}")

    def test_no_snapshot_publish_script_behavior_changes(self):
        changed = _changed_files()
        violations = [
            f for f in changed
            if "build-clean-public-snapshot" in f or "github-private-mirror" in f
        ]
        self.assertEqual(violations, [], f"Snapshot publish script changed: {violations}")


if __name__ == "__main__":
    unittest.main()
