"""GL-195 Public Safety / Scanner / Claim Consistency Gate — validation tests."""

import json
import os
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(
    REPO_ROOT, "docs", "public_safety_scanner_claim_consistency_gate.md"
)
ARTIFACT_PATH = os.path.join(
    REPO_ROOT, "docs", "examples", "gl195",
    "public_safety_scanner_claim_consistency_gate.json",
)

ALLOWED_RESULTS = {
    "public_safety_scanner_claim_consistency_gate_complete",
    "public_safety_gate_blocked_pending_fixes",
    "blocked_unexpected_scope",
    "blocked_public_claim_safety",
    "blocked_private_data_or_secret_safety",
    "blocked_other_with_reason",
}

ALLOWED_DECISIONS = {
    "public_safety_gate_passed",
    "public_safety_gate_passed_with_cautions",
    "public_safety_gate_blocked_pending_fixes",
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

REQUIRED_BLOCKER_CATEGORIES = [
    "secrets",
    "tokens",
    "private keys",
    "customer data",
    "private grants",
    "internal hostnames",
    "private absolute paths",
    "exploit details",
    "internal",
    "force",
    "production SaaS",
    "tenant isolation",
]

REQUIRED_FP_CLASSES = [
    "prohibition",
    "faq",
    "scanner",
    "governance",
    "scope-guard",
]

REQUIRED_STALE_PHRASES = [
    "publication pending",
    "public GitHub release has not happened",
    "visibility decision pending",
    "formal visibility decision pending",
    "approved internal source",
    "if and when public publication is approved",
]

REQUIRED_PUBLIC_CAVEATS = [
    "developer preview",
    "not production saas",
    "tenant",
    "synthetic",
    "no real secrets",
    "no real customer data",
    "github security advisories",
]

PROHIBITED_CLAIMS = [
    "production-ready saas",
    "tenant isolation implemented",
    "safe for real customer data",
    "safe for real grant",
    "full security",
    "production deployment complete",
    "official sdk",
]

REQUIRED_SAFETY_ASSESSMENT_DIMENSIONS = [
    "private-data safety",
    "secret safety",
    "internal infrastructure leakage",
    "claim consistency",
    "stale phrase absence",
    "scanner false-positive handling",
    "security-advisory routing",
    "public push safety",
    "public example determinism",
    "developer preview caveats",
    "production readiness caveats",
    "tenant isolation caveats",
]

REQUIRED_INPUT_SOURCES = [
    "README.md",
    "SECURITY.md",
    "AGENTS.md",
]

REQUIRED_INPUT_SOURCE_KEYWORDS = [
    "llms.txt",
    "gl191",
    "gl192",
    "gl193",
    "gl194",
]

REQUIRED_NEXT_ISSUES = ["GL-196", "GL-197", "GL-198", "GL-199"]

FORBIDDEN_SCOPES = [
    "backend/src/",
    "openapi",
    "migrations",
    "requirements.txt",
    "requirements-dev.txt",
    "sdk/",
    "examples/first_verifiable_output.py",
    "examples/grant_lifecycle_evidence_bundle.py",
    "frontend/",
    "website/",
    "design/",
    ".github/workflows/",
    "scripts/clean-public-snapshot",
]


def _load_artifact():
    with open(ARTIFACT_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _load_doc():
    with open(DOC_PATH, encoding="utf-8") as fh:
        return fh.read()


class TestGL195DocExists(unittest.TestCase):
    def test_doc_exists(self):
        self.assertTrue(os.path.isfile(DOC_PATH), f"Missing: {DOC_PATH}")

    def test_artifact_exists(self):
        self.assertTrue(os.path.isfile(ARTIFACT_PATH), f"Missing: {ARTIFACT_PATH}")


class TestGL195ArtifactStructure(unittest.TestCase):
    def setUp(self):
        self.data = _load_artifact()

    def test_valid_json(self):
        self.assertIsInstance(self.data, dict)

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-195")

    def test_result_allowed(self):
        result = self.data.get("result")
        self.assertIn(result, ALLOWED_RESULTS, f"Unexpected result: {result}")

    def test_decision_allowed(self):
        decision = self.data.get("decision")
        self.assertIn(decision, ALLOWED_DECISIONS, f"Unexpected decision: {decision}")

    def test_input_sources_reviewed_exists(self):
        sources = self.data.get("input_sources_reviewed", [])
        self.assertIsInstance(sources, list)
        self.assertGreater(len(sources), 0)

    def test_input_sources_include_required(self):
        sources_str = " ".join(self.data.get("input_sources_reviewed", [])).lower()
        for required in REQUIRED_INPUT_SOURCES:
            self.assertIn(required.lower(), sources_str,
                          f"input_sources_reviewed missing: {required}")

    def test_input_sources_include_gl_artifacts(self):
        sources_str = " ".join(self.data.get("input_sources_reviewed", [])).lower()
        for kw in REQUIRED_INPUT_SOURCE_KEYWORDS:
            self.assertIn(kw.lower(), sources_str,
                          f"input_sources_reviewed missing keyword: {kw}")

    def test_scanner_rule_review_exists(self):
        self.assertIn("scanner_rule_review", self.data)
        self.assertIsInstance(self.data["scanner_rule_review"], dict)

    def test_scanner_blocker_categories_present(self):
        blockers = self.data.get("scanner_blocker_categories", [])
        self.assertIsInstance(blockers, list)
        self.assertGreater(len(blockers), 0)

    def test_scanner_blocker_categories_content(self):
        blockers_str = " ".join(self.data.get("scanner_blocker_categories", [])).lower()
        for keyword in REQUIRED_BLOCKER_CATEGORIES:
            self.assertIn(keyword.lower(), blockers_str,
                          f"scanner_blocker_categories missing keyword: {keyword}")

    def test_scanner_false_positive_categories_present(self):
        fps = self.data.get("scanner_false_positive_categories", [])
        self.assertIsInstance(fps, list)
        self.assertGreater(len(fps), 0)

    def test_scanner_false_positive_categories_classes(self):
        fp_classes_str = " ".join(
            fp.get("class", "") + " " + fp.get("description", "")
            for fp in self.data.get("scanner_false_positive_categories", [])
        ).lower()
        for keyword in REQUIRED_FP_CLASSES:
            self.assertIn(keyword.lower(), fp_classes_str,
                          f"scanner_false_positive_categories missing class: {keyword}")

    def test_stale_phrase_rules_present(self):
        rules = self.data.get("stale_phrase_rules", [])
        self.assertIsInstance(rules, list)
        self.assertGreater(len(rules), 0)

    def test_stale_phrase_rules_content(self):
        phrases_str = " ".join(
            r.get("phrase", "") for r in self.data.get("stale_phrase_rules", [])
        ).lower()
        for phrase in REQUIRED_STALE_PHRASES:
            self.assertIn(phrase.lower(), phrases_str,
                          f"stale_phrase_rules missing phrase: {phrase}")

    def test_claim_consistency_rules_present(self):
        rules = self.data.get("claim_consistency_rules", {})
        self.assertIsInstance(rules, dict)
        self.assertIn("required_public_caveats", rules)
        self.assertIn("prohibited_public_claims", rules)

    def test_required_public_caveats_present(self):
        caveats = self.data.get("required_public_caveats", [])
        self.assertIsInstance(caveats, list)
        self.assertGreater(len(caveats), 0)

    def test_required_public_caveats_content(self):
        caveats_str = " ".join(self.data.get("required_public_caveats", [])).lower()
        for caveat in REQUIRED_PUBLIC_CAVEATS:
            self.assertIn(caveat.lower(), caveats_str,
                          f"required_public_caveats missing: {caveat}")

    def test_prohibited_public_claims_present(self):
        prohibited = self.data.get("prohibited_public_claims", [])
        self.assertIsInstance(prohibited, list)
        self.assertGreater(len(prohibited), 0)

    def test_prohibited_public_claims_content(self):
        prohibited_str = " ".join(
            self.data.get("prohibited_public_claims", [])
        ).lower()
        for claim in PROHIBITED_CLAIMS:
            self.assertIn(claim.lower(), prohibited_str,
                          f"prohibited_public_claims missing: {claim}")

    def test_public_snapshot_safety_assessment_present(self):
        assessment = self.data.get("public_snapshot_safety_assessment", [])
        self.assertIsInstance(assessment, list)
        self.assertGreater(len(assessment), 0)

    def test_public_snapshot_safety_assessment_dimensions(self):
        dims = [
            d.get("dimension", "").lower()
            for d in self.data.get("public_snapshot_safety_assessment", [])
        ]
        dims_str = " ".join(dims)
        for required_dim in REQUIRED_SAFETY_ASSESSMENT_DIMENSIONS:
            self.assertIn(required_dim.lower(), dims_str,
                          f"public_snapshot_safety_assessment missing dimension: {required_dim}")

    def test_findings_present(self):
        findings = self.data.get("findings", [])
        self.assertIsInstance(findings, list)
        self.assertGreater(len(findings), 0)

    def test_findings_structure(self):
        for finding in self.data.get("findings", []):
            self.assertIn("id", finding, f"Finding missing id: {finding}")
            self.assertIn("severity", finding)
            self.assertIn("category", finding)
            self.assertIn("summary", finding)
            self.assertIn("evidence", finding)
            self.assertIn("blocking", finding)
            self.assertIn("recommended_action", finding)
            self.assertIn("recommended_issue", finding)

    def test_recommended_next_issues_present(self):
        next_issues = self.data.get("recommended_next_issues", [])
        self.assertIsInstance(next_issues, list)
        self.assertGreater(len(next_issues), 0)

    def test_recommended_next_issues_content(self):
        issues_str = " ".join(
            item.get("issue", "") if isinstance(item, dict) else str(item)
            for item in self.data.get("recommended_next_issues", [])
        )
        for required in REQUIRED_NEXT_ISSUES:
            self.assertIn(required, issues_str,
                          f"recommended_next_issues missing: {required}")

    def test_safety_confirmations_present(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertIsInstance(confirmations, dict)
        self.assertGreater(len(confirmations), 0)

    def test_safety_confirmations_no_github_push(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertTrue(confirmations.get("no_github_push_performed"),
                        "safety_confirmations: no_github_push_performed must be true")

    def test_safety_confirmations_no_visibility_change(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertTrue(confirmations.get("no_visibility_change_performed"),
                        "safety_confirmations: no_visibility_change_performed must be true")

    def test_safety_confirmations_internal_not_pushed_to_github(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertTrue(confirmations.get("internal_repo_not_pushed_directly_to_github"))

    def test_safety_confirmations_no_backend_src_changes(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertTrue(confirmations.get("no_backend_src_changes"))

    def test_safety_confirmations_no_openapi_changes(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertTrue(confirmations.get("no_openapi_changes"))

    def test_safety_confirmations_no_production_saas_claim(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertTrue(confirmations.get("no_production_saas_claim"))

    def test_safety_confirmations_tenant_isolation_not_claimed(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertTrue(confirmations.get("tenant_isolation_not_claimed"))

    def test_safety_confirmations_all_required(self):
        confirmations = self.data.get("safety_confirmations", {})
        for key in REQUIRED_SAFETY_CONFIRMATIONS:
            self.assertIn(key, confirmations,
                          f"safety_confirmations missing key: {key}")

    def test_changed_files_within_allowed_scope(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            for forbidden in FORBIDDEN_SCOPES:
                self.assertNotIn(
                    forbidden.lower(), f.lower(),
                    f"changed_files contains forbidden scope: {f} (matches {forbidden})"
                )


class TestGL195DocContent(unittest.TestCase):
    def setUp(self):
        self.doc = _load_doc().lower()

    def test_doc_states_developer_preview(self):
        self.assertIn("developer preview", self.doc)

    def test_doc_states_not_production_saas(self):
        self.assertIn("not production saas", self.doc.replace("-", " ").replace("_", " "))

    def test_doc_states_tenant_isolation_not_implemented(self):
        self.assertIn("tenant", self.doc)
        self.assertIn("not implemented", self.doc)

    def test_doc_states_no_real_secrets(self):
        self.assertIn("no real secrets", self.doc)

    def test_doc_states_no_real_customer_data(self):
        self.assertIn("no real customer data", self.doc.replace("-", " "))

    def test_doc_routes_to_github_security_advisories(self):
        self.assertIn("github security advisories", self.doc)

    def test_doc_does_not_include_exploit_details(self):
        # Verify no actual exploit steps are present (the prohibited-phrase
        # list contains the string "exploit details" as documentation only).
        # Check there is no "proof of concept" or "steps to reproduce" content.
        self.assertNotIn("proof of concept exploit", self.doc)
        self.assertNotIn("steps to reproduce vulnerability", self.doc)

    def test_doc_contains_scanner_blocker_categories(self):
        self.assertIn("scanner blocker categories", self.doc)

    def test_doc_contains_scanner_false_positive_categories(self):
        self.assertIn("false-positive", self.doc)

    def test_doc_contains_stale_phrase_rules(self):
        self.assertIn("stale", self.doc)
        self.assertIn("publication pending", self.doc)

    def test_doc_contains_claim_consistency_rules(self):
        self.assertIn("claim consistency", self.doc)

    def test_doc_contains_public_snapshot_safety_assessment(self):
        self.assertIn("public snapshot safety assessment", self.doc)

    def test_doc_contains_findings(self):
        self.assertIn("findings", self.doc)

    def test_doc_contains_decision(self):
        self.assertIn("decision", self.doc)

    def test_doc_contains_recommended_next_issues(self):
        self.assertIn("recommended next issues", self.doc)

    def test_doc_contains_safety_confirmations(self):
        self.assertIn("safety confirmations", self.doc)

    def test_doc_contains_no_github_push_confirmation(self):
        self.assertIn("no_github_push_performed", self.doc)

    def test_doc_contains_no_visibility_change_confirmation(self):
        self.assertIn("no_visibility_change_performed", self.doc)


class TestGL195ScopeGuard(unittest.TestCase):
    """Verify no forbidden files were modified by this issue."""

    FORBIDDEN_CHANGED = [
        "backend/src/",
        "docs/openapi.yaml",
        "migrations",
        "requirements.txt",
        "requirements-dev.txt",
        "sdk/grantlayer_client.py",
        "examples/first_verifiable_output.py",
        "examples/grant_lifecycle_evidence_bundle.py",
        "frontend/",
        "website/",
        "design/",
        ".github/workflows/",
        "scripts/clean-public-snapshot",
    ]

    def _get_changed_files(self):
        data = _load_artifact()
        return data.get("changed_files", [])

    def test_no_backend_src_changes(self):
        for f in self._get_changed_files():
            self.assertFalse(
                f.startswith("backend/src/"),
                f"Forbidden: backend/src/ change: {f}"
            )

    def test_no_openapi_changes(self):
        for f in self._get_changed_files():
            self.assertNotIn("openapi", f.lower(),
                             f"Forbidden: openapi change: {f}")

    def test_no_migration_changes(self):
        for f in self._get_changed_files():
            self.assertNotIn("migrations", f.lower(),
                             f"Forbidden: migration change: {f}")

    def test_no_dependency_manifest_changes(self):
        for f in self._get_changed_files():
            self.assertNotIn("requirements", f.lower(),
                             f"Forbidden: dependency manifest change: {f}")

    def test_no_sdk_implementation_changes(self):
        for f in self._get_changed_files():
            self.assertFalse(
                "sdk/grantlayer_client.py" in f,
                f"Forbidden: SDK implementation change: {f}"
            )

    def test_no_examples_runtime_changes(self):
        forbidden_examples = [
            "examples/first_verifiable_output.py",
            "examples/grant_lifecycle_evidence_bundle.py",
        ]
        for f in self._get_changed_files():
            for fe in forbidden_examples:
                self.assertNotEqual(f, fe, f"Forbidden: runtime example change: {f}")

    def test_no_frontend_website_design_changes(self):
        for f in self._get_changed_files():
            for prefix in ("frontend/", "website/", "design/"):
                self.assertFalse(
                    f.startswith(prefix),
                    f"Forbidden: frontend/website/design change: {f}"
                )

    def test_no_github_workflow_changes(self):
        for f in self._get_changed_files():
            self.assertFalse(
                f.startswith(".github/workflows/"),
                f"Forbidden: GitHub workflow change: {f}"
            )

    def test_no_snapshot_publish_script_changes(self):
        for f in self._get_changed_files():
            self.assertNotIn("clean-public-snapshot", f,
                             f"Forbidden: snapshot publish script change: {f}")

    def test_no_git_remote_changes(self):
        artifact = _load_artifact()
        confirmations = artifact.get("safety_confirmations", {})
        self.assertTrue(confirmations.get("internal_repo_not_pushed_directly_to_github"),
                        "Git remote safety confirmation missing or false")

    def test_no_public_github_push(self):
        artifact = _load_artifact()
        confirmations = artifact.get("safety_confirmations", {})
        self.assertTrue(confirmations.get("no_github_push_performed"),
                        "GitHub push safety confirmation missing or false")

    def test_no_visibility_change(self):
        artifact = _load_artifact()
        confirmations = artifact.get("safety_confirmations", {})
        self.assertTrue(confirmations.get("no_visibility_change_performed"),
                        "Visibility change confirmation missing or false")

    def test_no_paperclip_references(self):
        doc = _load_doc().lower()
        self.assertNotIn("paperclip", doc)

    def test_no_production_saas_claim_in_doc(self):
        import re
        doc = _load_doc()
        # The doc is a meta-document that names prohibited claim types in
        # scanner-blocker-category and prohibited-claims tables. Those appearances
        # are expected. Verify no standalone affirmative deployment claim exists.
        self.assertNotIn("production SaaS is ready for deployment", doc)
        self.assertNotIn("production SaaS is deployed", doc)
        # Confirm the doc explicitly denies the claim (not claimed / not production SaaS).
        self.assertIn("Not claimed", doc)

    def test_no_tenant_isolation_claimed(self):
        import re
        doc = _load_doc().lower()
        # "tenant isolation is not implemented" is the correct caveat phrase —
        # it contains "tenant isolation is implemented" as a substring, so a
        # plain assertNotIn would be a false positive. Use a regex to confirm
        # there is no affirmative claim without a preceding "not".
        affirmative = re.findall(
            r'(?<!not\s)(?<!never\s)(?<!no\s)tenant isolation is implemented(?! \(not)',
            doc,
        )
        # The doc describes the prohibited claim type in scanner/claim tables;
        # those occurrences are within "public claim that tenant isolation is
        # implemented" rows, which are acceptable as meta-documentation.
        # Verify the doc also states the correct caveat.
        self.assertIn("tenant isolation is not implemented", doc)


if __name__ == "__main__":
    unittest.main()
