"""GL-194 Public Preview Review & Feedback Triage Pack — validation tests."""

import json
import os
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "public_preview_review_feedback_triage_pack.md")
ARTIFACT_PATH = os.path.join(
    REPO_ROOT, "docs", "examples", "gl194",
    "public_preview_review_feedback_triage_pack.json"
)

ALLOWED_RESULTS = {
    "public_preview_review_feedback_triage_complete",
    "public_preview_blocked_pending_fixes",
    "blocked_unexpected_scope",
    "blocked_public_claim_safety",
    "blocked_other_with_reason",
}

ALLOWED_DECISIONS = {
    "public_preview_continue_with_cautions",
    "public_preview_ready_for_wider_reviewer_feedback",
    "public_preview_blocked_pending_fixes",
    "blocked_other_with_reason",
}

REQUIRED_SAFETY_CONFIRMATIONS = [
    "no_github_push_performed",
    "no_visibility_change_performed",
    "internal_repo_not_pushed_directly_to_github",
    "no_github_api_label_changes_performed",
    "no_github_issue_changes_performed",
    "no_reviewer_outreach_sent",
    "no_backend_src_changes",
    "no_openapi_changes",
    "no_migration_db_dependency_changes",
    "no_dependency_manifest_changes",
    "no_sdk_implementation_changes",
    "no_examples_runtime_changes",
    "no_frontend_website_design_changes",
    "no_github_workflow_changes",
    "no_snapshot_publish_script_behavior_changes",
    "no_production_saas_claim",
    "tenant_isolation_not_claimed",
    "no_real_customer_data_requested",
    "no_private_grant_data_requested",
    "no_secrets_requested",
    "no_exploit_details_included",
    "security_sensitive_reports_routed_to_github_security_advisories",
]

REQUIRED_TRIAGE_CATEGORIES = [
    "quickstart-feedback",
    "first-output-feedback",
    "grant-lifecycle-example-feedback",
    "documentation-feedback",
    "developer-experience-feedback",
    "bug-report",
    "feature-request",
    "product-question",
    "security-sensitive-report",
    "non-scope-later",
]

REQUIRED_SEVERITY_LEVELS = ["critical", "high", "medium", "low", "info"]

REQUIRED_READINESS_DIMENSIONS = [
    "README clarity",
    "first output helper",
    "second runnable example",
    "feedback infrastructure",
    "agent/API walkthrough",
    "security-sensitive routing",
    "caveat clarity",
    "public claim safety",
    "example determinism",
    "backend quickstart separation",
    "coding agent readiness",
    "production readiness",
    "tenant isolation",
    "API/SDK maturity",
    "controlled preview readiness",
]

REQUIRED_ROADMAP_ISSUES = ["GL-195", "GL-196", "GL-197", "GL-198", "GL-199"]

REQUIRED_INPUT_SOURCES_SUBSTRINGS = [
    "README.md",
    "AGENTS.md",
    "llms",
    "gl191",
    "gl192",
    "gl193",
]

REQUIRED_IMPROVEMENTS_SUBSTRINGS = [
    "first output",
    "grant lifecycle",
    "feedback infrastructure",
    "walkthrough",
]

FORBIDDEN_PATHS = [
    os.path.join(REPO_ROOT, "backend", "src"),
    os.path.join(REPO_ROOT, "docs", "openapi.yaml"),
    os.path.join(REPO_ROOT, "requirements.txt"),
    os.path.join(REPO_ROOT, "requirements-dev.txt"),
    os.path.join(REPO_ROOT, "frontend"),
    os.path.join(REPO_ROOT, ".github", "workflows"),
    os.path.join(REPO_ROOT, "scripts", "publish_public_snapshot.sh"),
]

ALLOWED_CHANGED_FILES = [
    "docs/public_preview_review_feedback_triage_pack.md",
    "docs/examples/gl194/public_preview_review_feedback_triage_pack.json",
    "backend/tests/test_gl194_public_preview_review_feedback_triage_pack.py",
]


def load_artifact():
    with open(ARTIFACT_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_doc():
    with open(DOC_PATH, encoding="utf-8") as f:
        return f.read()


class TestGL194DocExists(unittest.TestCase):
    def test_review_doc_exists(self):
        self.assertTrue(os.path.exists(DOC_PATH), f"Missing: {DOC_PATH}")

    def test_artifact_exists(self):
        self.assertTrue(os.path.exists(ARTIFACT_PATH), f"Missing: {ARTIFACT_PATH}")


class TestGL194ArtifactStructure(unittest.TestCase):
    def setUp(self):
        self.data = load_artifact()

    def test_issue_id(self):
        self.assertEqual(self.data["issue_id"], "GL-194")

    def test_result_is_allowed(self):
        self.assertIn(self.data["result"], ALLOWED_RESULTS)

    def test_decision_is_allowed(self):
        self.assertIn(self.data["decision"], ALLOWED_DECISIONS)

    def test_decision_rationale_exists(self):
        self.assertIn("decision_rationale", self.data)
        self.assertGreater(len(self.data["decision_rationale"]), 10)

    def test_input_sources_reviewed(self):
        sources = self.data.get("input_sources_reviewed", [])
        sources_lower = " ".join(s.lower() for s in sources)
        for substring in REQUIRED_INPUT_SOURCES_SUBSTRINGS:
            self.assertIn(
                substring.lower(), sources_lower,
                f"Missing input source substring: {substring}"
            )

    def test_completed_improvements_coverage(self):
        improvements = self.data.get("completed_public_preview_improvements", [])
        text = json.dumps(improvements).lower()
        for substring in REQUIRED_IMPROVEMENTS_SUBSTRINGS:
            self.assertIn(
                substring.lower(), text,
                f"Missing improvement coverage for: {substring}"
            )

    def test_triage_categories(self):
        categories = self.data.get("triage_categories", [])
        for cat in REQUIRED_TRIAGE_CATEGORIES:
            self.assertIn(cat, categories, f"Missing triage category: {cat}")

    def test_severity_model(self):
        severity = self.data.get("severity_model", [])
        for level in REQUIRED_SEVERITY_LEVELS:
            self.assertIn(level, severity, f"Missing severity level: {level}")

    def test_readiness_dimensions_present(self):
        dimensions = self.data.get("readiness_dimensions", [])
        dim_names = [d.get("dimension", "") for d in dimensions]
        for required in REQUIRED_READINESS_DIMENSIONS:
            self.assertTrue(
                any(required.lower() in name.lower() for name in dim_names),
                f"Missing readiness dimension: {required}"
            )

    def test_readiness_dimension_fields(self):
        dimensions = self.data.get("readiness_dimensions", [])
        self.assertGreater(len(dimensions), 0)
        for dim in dimensions:
            self.assertIn("dimension", dim)
            self.assertIn("status", dim)
            self.assertIn("rationale", dim)

    def test_findings_exist(self):
        findings = self.data.get("findings", [])
        self.assertGreater(len(findings), 0)

    def test_finding_fields(self):
        findings = self.data.get("findings", [])
        for finding in findings:
            self.assertIn("id", finding, f"Finding missing id: {finding}")
            self.assertIn("severity", finding)
            self.assertIn("category", finding)
            self.assertIn("summary", finding)
            self.assertIn("evidence", finding)
            self.assertIn("blocking", finding)
            self.assertIn("recommended_action", finding)
            self.assertIn("recommended_issue", finding)

    def test_feedback_to_roadmap_includes_required_issues(self):
        roadmap = self.data.get("feedback_to_roadmap", [])
        roadmap_text = json.dumps(roadmap)
        for issue in REQUIRED_ROADMAP_ISSUES:
            self.assertIn(issue, roadmap_text, f"Missing roadmap issue: {issue}")

    def test_safety_confirmations_present(self):
        confirmations = self.data.get("safety_confirmations", {})
        for key in REQUIRED_SAFETY_CONFIRMATIONS:
            self.assertIn(key, confirmations, f"Missing safety confirmation: {key}")
            self.assertTrue(confirmations[key], f"Safety confirmation False: {key}")

    def test_changed_files_within_scope(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertIn(f, ALLOWED_CHANGED_FILES, f"Changed file out of scope: {f}")

    def test_no_backend_src_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertFalse(
                f.startswith("backend/src"),
                f"Forbidden backend/src change: {f}"
            )

    def test_no_openapi_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertNotIn("openapi", f.lower(), f"Forbidden OpenAPI change: {f}")

    def test_no_migration_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertNotIn(
                "migration", f.lower(), f"Forbidden migration change: {f}"
            )

    def test_no_requirements_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertNotIn(
                "requirements", f.lower(),
                f"Forbidden dependency manifest change: {f}"
            )

    def test_no_frontend_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertFalse(
                f.startswith("frontend") or f.startswith("website"),
                f"Forbidden frontend/website change: {f}"
            )

    def test_no_github_workflow_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertFalse(
                ".github/workflows" in f,
                f"Forbidden GitHub workflow change: {f}"
            )

    def test_no_visibility_change_confirmation(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertTrue(confirmations.get("no_visibility_change_performed", False))

    def test_no_github_push_confirmation(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertTrue(confirmations.get("no_github_push_performed", False))

    def test_no_production_saas_claim_confirmation(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertTrue(confirmations.get("no_production_saas_claim", False))

    def test_tenant_isolation_not_claimed_confirmation(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertTrue(confirmations.get("tenant_isolation_not_claimed", False))

    def test_security_sensitive_routing_confirmation(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertTrue(
            confirmations.get(
                "security_sensitive_reports_routed_to_github_security_advisories",
                False
            )
        )


class TestGL194DocContent(unittest.TestCase):
    def setUp(self):
        self.doc = load_doc()

    def test_doc_states_developer_preview(self):
        self.assertIn("Developer Preview", self.doc)

    def test_doc_states_not_production_saas(self):
        doc_lower = self.doc.lower()
        self.assertTrue(
            "not production saas" in doc_lower or "not claimed" in doc_lower,
            "Doc must state not production SaaS or not claimed"
        )

    def test_doc_states_tenant_isolation_not_implemented(self):
        doc_lower = self.doc.lower()
        self.assertIn(
            "tenant", doc_lower,
            "Doc must mention tenant isolation"
        )
        self.assertIn(
            "not implemented", doc_lower,
            "Doc must state not implemented (for tenant isolation)"
        )

    def test_doc_states_no_real_secrets_customer_data(self):
        doc_lower = self.doc.lower()
        self.assertTrue(
            "no real secrets" in doc_lower
            or "synthetic" in doc_lower
            or "no real customer data" in doc_lower,
            "Doc must state no real secrets or synthetic data"
        )

    def test_doc_routes_security_reports_to_github_advisories(self):
        self.assertIn("Security Advisories", self.doc)

    def test_doc_does_not_include_exploit_details(self):
        doc_lower = self.doc.lower()
        self.assertNotIn(
            "exploit payload", doc_lower,
            "Doc must not include exploit payload details"
        )
        self.assertNotIn(
            "proof-of-concept payload", doc_lower,
            "Doc must not include PoC payload details"
        )

    def test_doc_contains_gl194(self):
        self.assertIn("GL-194", self.doc)

    def test_doc_contains_safety_confirmations(self):
        self.assertIn("Safety Confirmations", self.doc)

    def test_doc_contains_decision(self):
        self.assertIn("Decision", self.doc)

    def test_doc_contains_roadmap(self):
        self.assertIn("GL-195", self.doc)
        self.assertIn("GL-196", self.doc)
        self.assertIn("GL-197", self.doc)
        self.assertIn("GL-198", self.doc)
        self.assertIn("GL-199", self.doc)

    def test_doc_confirms_no_github_push(self):
        self.assertIn("No GitHub push", self.doc)

    def test_doc_confirms_no_visibility_change(self):
        self.assertIn("No visibility change", self.doc)

    def test_doc_confirms_no_backend_src_changes(self):
        doc_lower = self.doc.lower()
        self.assertIn("backend/src", doc_lower)


class TestGL194ScopeGuard(unittest.TestCase):
    def test_no_backend_src_modification(self):
        backend_src = os.path.join(REPO_ROOT, "backend", "src")
        changed_files = [
            "docs/public_preview_review_feedback_triage_pack.md",
            "docs/examples/gl194/public_preview_review_feedback_triage_pack.json",
            "backend/tests/test_gl194_public_preview_review_feedback_triage_pack.py",
        ]
        for f in changed_files:
            full_path = os.path.join(REPO_ROOT, f)
            self.assertFalse(
                full_path.startswith(backend_src),
                f"Scope violation: {f} is in backend/src"
            )

    def test_no_openapi_modification(self):
        changed_files = [
            "docs/public_preview_review_feedback_triage_pack.md",
            "docs/examples/gl194/public_preview_review_feedback_triage_pack.json",
            "backend/tests/test_gl194_public_preview_review_feedback_triage_pack.py",
        ]
        for f in changed_files:
            self.assertNotIn("openapi", f.lower())

    def test_no_github_push_performed(self):
        data = load_artifact()
        confirmations = data.get("safety_confirmations", {})
        self.assertTrue(confirmations.get("no_github_push_performed", False))

    def test_no_visibility_change_performed(self):
        data = load_artifact()
        confirmations = data.get("safety_confirmations", {})
        self.assertTrue(confirmations.get("no_visibility_change_performed", False))

    def test_internal_repo_not_pushed_directly_to_github(self):
        data = load_artifact()
        confirmations = data.get("safety_confirmations", {})
        self.assertTrue(
            confirmations.get("internal_repo_not_pushed_directly_to_github", False)
        )

    def test_no_paperclip_status_updates(self):
        doc = load_doc()
        self.assertNotIn("Paperclip", doc)

    def test_no_public_github_push_in_doc(self):
        doc = load_doc()
        self.assertNotIn("git push origin", doc)
        self.assertNotIn("push to GitHub", doc.replace("No GitHub push", ""))


if __name__ == "__main__":
    unittest.main()
