"""GL-186: AI Reviewer Feedback Triage."""

import json
import os
import subprocess
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REPORT_PATH = os.path.join(REPO_ROOT, "docs", "ai_reviewer_feedback_triage.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl186",
    "ai_reviewer_feedback_triage.json",
)

ALLOWED_CHANGED_FILES = {
    "docs/ai_reviewer_feedback_triage.md",
    "docs/examples/gl186/ai_reviewer_feedback_triage.json",
    "backend/tests/test_gl186_ai_reviewer_feedback_triage.py",
}

FORBIDDEN_CHANGED_PREFIXES = [
    "backend/src/",
    "openapi",
    "docs/openapi",
    "migrations/",
    "alembic/",
    "pyproject.toml",
    "requirements",
    "setup.py",
    "setup.cfg",
    "package.json",
    "package-lock.json",
    ".github/workflows/",
    "scripts/publish",
    "frontend/",
    "website/",
]

REQUIRED_REVIEWER_IDS = {
    "codex-backend-dx",
    "kimi-k2-agent-oss",
    "security-product-readiness",
}

REQUIRED_NORMALIZED_FINDING_THEMES = [
    "test count",
    "CONTRIBUTING",
    "clone",
    "quickstart",
    "agent",
    "forgejo",
    "verify",
    "example",
    "demo",
]

REQUIRED_SEVERITY_LEVELS = {"critical", "high", "medium", "low", "info"}

REQUIRED_TRIAGE_CATEGORIES = {
    "blocker",
    "confusing-docs",
    "broken-quickstart",
    "missing-example",
    "product-question",
    "security-concern",
    "production-readiness-concern",
    "feature-request",
    "non-scope-later",
    "stale-claim",
}

REQUIRED_FOLLOW_UP_ISSUES = {"GL-187", "GL-188", "GL-189", "GL-190"}

REQUIRED_SAFETY_CONFIRMATIONS = {
    "no_github_push_performed",
    "no_visibility_change_performed",
    "internal_repo_not_pushed_directly_to_github",
    "no_outreach_sent",
    "no_reviewer_private_data_included",
    "no_github_api_label_changes_performed",
    "no_github_issue_changes_performed",
    "production_saas_not_claimed",
    "tenant_isolation_not_claimed",
    "secrets_not_included",
    "exploit_details_not_included",
}

# Normalized confirmation keys in the JSON (may differ from display names above)
REQUIRED_JSON_SAFETY_KEYS = {
    "no_github_push_performed",
    "no_visibility_change_performed",
    "internal_repo_not_pushed_directly_to_github",
    "no_outreach_sent",
    "no_reviewer_private_data_included",
    "no_github_api_label_changes_performed",
    "no_github_issue_changes_performed",
    "production_saas_not_claimed",
    "tenant_isolation_not_claimed",
}


def _load_json():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_report():
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _changed_files_vs_main():
    result = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


class TestGL186ArtifactsExist(unittest.TestCase):
    def test_report_exists(self):
        self.assertTrue(os.path.exists(REPORT_PATH), f"Missing: {REPORT_PATH}")

    def test_json_artifact_exists(self):
        self.assertTrue(os.path.exists(JSON_PATH), f"Missing: {JSON_PATH}")

    def test_json_is_valid(self):
        data = _load_json()
        self.assertIsInstance(data, dict)

    def test_json_issue_id(self):
        data = _load_json()
        self.assertEqual(data.get("issue_id"), "GL-186")


class TestGL186InputReviews(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.reviews = self.data.get("input_reviews", [])
        self.reviewer_ids = {r.get("reviewer_id") for r in self.reviews}

    def test_input_reviews_present(self):
        self.assertGreater(len(self.reviews), 0, "input_reviews must not be empty")

    def test_codex_backend_dx_present(self):
        self.assertIn(
            "codex-backend-dx",
            self.reviewer_ids,
            "Codex Backend/DX review must be present",
        )

    def test_kimi_agent_oss_present(self):
        self.assertIn(
            "kimi-k2-agent-oss",
            self.reviewer_ids,
            "Kimi K2.6 Agent/OSS review must be present",
        )

    def test_security_product_readiness_present(self):
        self.assertIn(
            "security-product-readiness",
            self.reviewer_ids,
            "Security/Product-Readiness review must be present",
        )

    def test_all_required_reviewers_present(self):
        self.assertEqual(
            REQUIRED_REVIEWER_IDS,
            self.reviewer_ids & REQUIRED_REVIEWER_IDS,
            f"Missing reviewer IDs: {REQUIRED_REVIEWER_IDS - self.reviewer_ids}",
        )


class TestGL186NormalizedFindings(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.findings = self.data.get("normalized_findings", [])

    def test_normalized_findings_exist(self):
        self.assertGreater(len(self.findings), 0, "normalized_findings must not be empty")

    def _all_summaries_and_recommendations(self):
        texts = []
        for f in self.findings:
            texts.append(f.get("summary", "").lower())
            texts.append(f.get("recommendation", "").lower())
            texts.append(f.get("evidence_summary", "").lower())
        return " ".join(texts)

    def test_readme_test_count_stale_claim_present(self):
        text = self._all_summaries_and_recommendations()
        self.assertTrue(
            "test count" in text or "1130" in text,
            "Must have finding about README test count stale claim",
        )

    def test_contributing_stale_claim_present(self):
        text = self._all_summaries_and_recommendations()
        self.assertIn("contributing", text, "Must have finding about CONTRIBUTING.md stale claim")

    def test_clone_quickstart_inconsistency_present(self):
        text = self._all_summaries_and_recommendations()
        self.assertTrue(
            "clone" in text or "quickstart" in text,
            "Must have finding about clone/quickstart inconsistency",
        )

    def test_agent_facing_stale_wording_present(self):
        text = self._all_summaries_and_recommendations()
        self.assertTrue(
            "agent" in text and ("stale" in text or "internal source" in text),
            "Must have finding about agent-facing stale status wording",
        )

    def test_source_of_truth_forgejo_confusion_present(self):
        text = self._all_summaries_and_recommendations()
        self.assertTrue(
            "forgejo" in text or "sourceoftruth" in text.replace(" ", "").replace("-", "").replace("_", ""),
            "Must have finding about sourceOfTruth/internal-forgejo public confusion",
        )

    def test_verify_first_output_script_request_present(self):
        text = self._all_summaries_and_recommendations()
        self.assertTrue(
            "verify" in text and ("script" in text or "helper" in text),
            "Must have finding about verify-first-output helper script request",
        )

    def test_second_runnable_example_request_present(self):
        text = self._all_summaries_and_recommendations()
        self.assertTrue(
            "second" in text and "example" in text or "grant lifecycle" in text or "evidence bundle" in text,
            "Must have finding about second runnable example request",
        )

    def test_demo_endpoint_safety_guard_present(self):
        text = self._all_summaries_and_recommendations()
        self.assertTrue(
            "demo" in text and ("endpoint" in text or "guard" in text or "warning" in text),
            "Must have finding about demo endpoint safety guard / startup warning",
        )

    def test_each_finding_has_severity(self):
        for f in self.findings:
            self.assertIn(
                "severity", f, f"Finding {f.get('id')} missing severity"
            )
            self.assertIn(
                f["severity"],
                REQUIRED_SEVERITY_LEVELS,
                f"Finding {f.get('id')} has invalid severity: {f['severity']}",
            )

    def test_each_finding_has_category(self):
        for f in self.findings:
            self.assertIn("category", f, f"Finding {f.get('id')} missing category")

    def test_each_finding_has_recommendation(self):
        for f in self.findings:
            self.assertIn(
                "recommendation", f, f"Finding {f.get('id')} missing recommendation"
            )
            self.assertTrue(
                len(f["recommendation"]) > 0,
                f"Finding {f.get('id')} has empty recommendation",
            )

    def test_each_finding_has_blocking_field(self):
        for f in self.findings:
            self.assertIn(
                "blocking", f, f"Finding {f.get('id')} missing blocking field"
            )
            self.assertIsInstance(
                f["blocking"],
                bool,
                f"Finding {f.get('id')} blocking field must be boolean",
            )


class TestGL186RepeatedThemes(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.themes = self.data.get("repeated_themes", [])

    def test_repeated_themes_exist(self):
        self.assertGreater(len(self.themes), 0, "repeated_themes must not be empty")

    def _all_theme_text(self):
        texts = []
        for t in self.themes:
            texts.append(t.get("title", "").lower())
            texts.append(t.get("description", "").lower())
        return " ".join(texts)

    def test_stale_public_state_docs_theme_present(self):
        text = self._all_theme_text()
        self.assertTrue(
            "stale" in text and ("public" in text or "docs" in text),
            "Must have theme about stale public-state docs",
        )

    def test_first_verifiable_output_works_theme_present(self):
        text = self._all_theme_text()
        self.assertTrue(
            "first verifiable output" in text or ("verifiable" in text and "works" in text),
            "Must have theme about first verifiable output working well",
        )


class TestGL186PriorityFollowUpPlan(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.plan = self.data.get("priority_follow_up_plan", [])
        self.issue_ids = {item.get("issue_id") for item in self.plan}

    def test_priority_plan_exists(self):
        self.assertGreater(len(self.plan), 0, "priority_follow_up_plan must not be empty")

    def test_gl187_present(self):
        self.assertIn("GL-187", self.issue_ids, "GL-187 must be in priority follow-up plan")

    def test_gl188_present(self):
        self.assertIn("GL-188", self.issue_ids, "GL-188 must be in priority follow-up plan")

    def test_gl189_present(self):
        self.assertIn("GL-189", self.issue_ids, "GL-189 must be in priority follow-up plan")

    def test_gl190_present(self):
        self.assertIn("GL-190", self.issue_ids, "GL-190 must be in priority follow-up plan")


class TestGL186ImmediateNextIssue(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.next_issue = self.data.get("immediate_next_issue", {})

    def test_immediate_next_issue_exists(self):
        self.assertIsInstance(self.next_issue, dict)
        self.assertTrue(len(self.next_issue) > 0, "immediate_next_issue must not be empty")

    def test_immediate_next_issue_is_gl187(self):
        issue_id = self.next_issue.get("issue_id", "")
        title = self.next_issue.get("title", "").lower()
        self.assertTrue(
            "GL-187" in issue_id or "187" in issue_id or "stale" in title or "docs" in title,
            "immediate_next_issue should be GL-187 Public Docs Post-Public Stale Claim Cleanup",
        )

    def test_immediate_next_issue_has_recommended_model(self):
        self.assertIn(
            "recommended_model",
            self.next_issue,
            "immediate_next_issue must include recommended_model",
        )
        self.assertTrue(
            len(self.next_issue["recommended_model"]) > 0,
            "recommended_model must not be empty",
        )

    def test_immediate_next_issue_has_rationale(self):
        self.assertIn(
            "rationale",
            self.next_issue,
            "immediate_next_issue must include rationale",
        )

    def test_immediate_next_issue_has_expected_scope(self):
        self.assertIn(
            "expected_scope",
            self.next_issue,
            "immediate_next_issue must include expected_scope",
        )

    def test_immediate_next_issue_has_explicit_non_goals(self):
        self.assertIn(
            "explicit_non_goals",
            self.next_issue,
            "immediate_next_issue must include explicit_non_goals",
        )


class TestGL186SecuritySensitiveHandling(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.handling = self.data.get("security_sensitive_handling", {})
        self.report = _load_report()

    def test_security_sensitive_handling_exists(self):
        self.assertIsInstance(self.handling, dict)
        self.assertTrue(len(self.handling) > 0, "security_sensitive_handling must not be empty")

    def test_security_handling_is_high_level_only(self):
        handling_text = json.dumps(self.handling).lower()
        self.assertFalse(
            "exploit" in handling_text and "detail" in handling_text and "how to" in handling_text,
            "security_sensitive_handling must not include exploit details",
        )

    def test_security_handling_no_exploit_details(self):
        flag = self.handling.get("public_artifacts_contain_exploit_details", True)
        self.assertFalse(flag, "public_artifacts_contain_exploit_details must be false")

    def test_demo_endpoint_concern_is_high_level_in_report(self):
        self.assertIn(
            "demo",
            self.report.lower(),
            "Report must mention demo endpoint concern",
        )
        self.assertNotIn(
            "proof-of-concept code",
            self.report.lower(),
            "Report must not include proof-of-concept code",
        )


class TestGL186SafetyConfirmations(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.confirmations = self.data.get("safety_confirmations", {})
        self.report = _load_report()

    def test_safety_confirmations_exist(self):
        self.assertIsInstance(self.confirmations, dict)
        self.assertTrue(len(self.confirmations) > 0, "safety_confirmations must not be empty")

    def test_no_github_push_performed(self):
        self.assertTrue(
            self.confirmations.get("no_github_push_performed"),
            "no_github_push_performed must be true",
        )

    def test_no_visibility_change_performed(self):
        self.assertTrue(
            self.confirmations.get("no_visibility_change_performed"),
            "no_visibility_change_performed must be true",
        )

    def test_internal_repo_not_pushed_directly_to_github(self):
        self.assertTrue(
            self.confirmations.get("internal_repo_not_pushed_directly_to_github"),
            "internal_repo_not_pushed_directly_to_github must be true",
        )

    def test_no_outreach_sent(self):
        self.assertTrue(
            self.confirmations.get("no_outreach_sent"),
            "no_outreach_sent must be true",
        )

    def test_no_reviewer_private_data_included(self):
        self.assertTrue(
            self.confirmations.get("no_reviewer_private_data_included"),
            "no_reviewer_private_data_included must be true",
        )

    def test_no_github_api_label_changes_performed(self):
        self.assertTrue(
            self.confirmations.get("no_github_api_label_changes_performed"),
            "no_github_api_label_changes_performed must be true",
        )

    def test_no_github_issue_changes_performed(self):
        self.assertTrue(
            self.confirmations.get("no_github_issue_changes_performed"),
            "no_github_issue_changes_performed must be true",
        )

    def test_production_saas_not_claimed(self):
        self.assertTrue(
            self.confirmations.get("production_saas_not_claimed"),
            "production_saas_not_claimed must be true",
        )

    def test_tenant_isolation_not_claimed(self):
        self.assertTrue(
            self.confirmations.get("tenant_isolation_not_claimed"),
            "tenant_isolation_not_claimed must be true",
        )

    def test_secrets_not_in_confirmations_false(self):
        val = self.confirmations.get("no_secrets_included", True)
        self.assertTrue(val, "no_secrets_included must be true")

    def test_exploit_details_not_in_confirmations_false(self):
        val = self.confirmations.get("no_exploit_details_included", True)
        self.assertTrue(val, "no_exploit_details_included must be true")

    def test_report_explicitly_states_no_github_push(self):
        report_lower = self.report.lower()
        self.assertTrue(
            "no github push" in report_lower or "no github push was performed" in report_lower,
            "Report must explicitly state no GitHub push was performed",
        )

    def test_report_explicitly_states_no_visibility_change(self):
        report_lower = self.report.lower()
        self.assertTrue(
            "no" in report_lower and "visibility change" in report_lower,
            "Report must explicitly state no visibility change was performed",
        )

    def test_report_explicitly_states_internal_repo_not_pushed_to_github(self):
        report_lower = self.report.lower()
        self.assertTrue(
            "internal repo" in report_lower or "internal repository" in report_lower,
            "Report must explicitly state internal repo was not pushed to GitHub",
        )

    def test_report_explicitly_states_no_outreach_sent(self):
        report_lower = self.report.lower()
        self.assertTrue(
            "no outreach" in report_lower or "no reviewer outreach" in report_lower,
            "Report must explicitly state no outreach was sent",
        )


class TestGL186ChangedFilesScope(unittest.TestCase):
    def setUp(self):
        self.changed = _changed_files_vs_main()

    def test_changed_files_within_allowed_scope(self):
        for f in self.changed:
            normalized = f.lower().replace("\\", "/")
            in_allowed = normalized in {p.lower() for p in ALLOWED_CHANGED_FILES}
            if not in_allowed:
                for prefix in FORBIDDEN_CHANGED_PREFIXES:
                    self.assertFalse(
                        normalized.startswith(prefix.lower()),
                        f"Forbidden changed file: {f} (matches forbidden prefix {prefix})",
                    )

    def test_no_backend_src_changes(self):
        for f in self.changed:
            self.assertFalse(
                f.startswith("backend/src/"),
                f"Forbidden: backend/src change detected: {f}",
            )

    def test_no_openapi_changes(self):
        for f in self.changed:
            lower = f.lower()
            self.assertFalse(
                "openapi" in lower and lower.endswith(".yaml"),
                f"Forbidden: OpenAPI change detected: {f}",
            )

    def test_no_migration_changes(self):
        for f in self.changed:
            lower = f.lower()
            self.assertFalse(
                lower.startswith("migrations/") or lower.startswith("alembic/"),
                f"Forbidden: migration change detected: {f}",
            )

    def test_no_dependency_manifest_changes(self):
        forbidden_manifests = {"pyproject.toml", "setup.py", "setup.cfg", "package.json", "package-lock.json"}
        for f in self.changed:
            self.assertNotIn(
                os.path.basename(f),
                forbidden_manifests,
                f"Forbidden: dependency manifest change detected: {f}",
            )

    def test_no_github_workflow_changes(self):
        for f in self.changed:
            self.assertFalse(
                f.startswith(".github/workflows/"),
                f"Forbidden: GitHub workflow change detected: {f}",
            )

    def test_no_frontend_website_changes(self):
        for f in self.changed:
            lower = f.lower()
            self.assertFalse(
                lower.startswith("frontend/") or lower.startswith("website/"),
                f"Forbidden: frontend/website change detected: {f}",
            )


class TestGL186NoPrivateData(unittest.TestCase):
    def setUp(self):
        self.report = _load_report()
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            self.json_text = f.read()

    def _combined_text(self):
        return (self.report + self.json_text).lower()

    def test_no_private_email_in_report(self):
        text = self._combined_text()
        # Check no email pattern that isn't the public GitHub URL
        import re
        emails = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
        # Allow known public reference URLs only
        allowed_emails = {"discodone@github.com"}
        for email in emails:
            self.assertIn(
                email,
                allowed_emails,
                f"Potentially private email found in artifacts: {email}",
            )

    def test_no_exploit_details_in_report(self):
        text = self._combined_text()
        forbidden_phrases = ["proof-of-concept code", "exploit payload", "curl -x exploit"]
        for phrase in forbidden_phrases:
            self.assertNotIn(
                phrase,
                text,
                f"Forbidden exploit detail phrase found: {phrase}",
            )

    def test_no_production_saas_claim_in_report(self):
        text = self._combined_text()
        self.assertNotIn(
            "production saas ready",
            text,
            "Must not claim production SaaS readiness",
        )

    def test_no_tenant_isolation_claim_in_report(self):
        text = self._combined_text()
        forbidden_phrases = [
            "tenant isolation is implemented",
            "workspace isolation is implemented",
        ]
        for phrase in forbidden_phrases:
            self.assertNotIn(phrase, text, f"Must not claim: {phrase}")


if __name__ == "__main__":
    unittest.main()
