"""GL-171 Public Release / GitHub Snapshot Readiness + Private Data Safety Review Gate."""

import json
import os
import re
import unittest

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_REVIEW_MD = os.path.join(_REPO_ROOT, "docs", "public_release_github_snapshot_readiness_review.md")
_ARTIFACT_JSON = os.path.join(
    _REPO_ROOT,
    "docs",
    "examples",
    "gl171",
    "public_release_github_snapshot_readiness_review.json",
)

_ALLOWED_REVIEW_DECISIONS = {
    "proceed_to_public_snapshot_publish",
    "proceed_with_cautions_to_public_snapshot_publish",
    "blocked_before_public_snapshot_publish",
}

_PRIVATE_PATTERNS = [
    r"anton\.hofer@",
    r"hofercloud\.eu",
    r"192\.168\.\d+\.\d+",
    r"100\.109\.",
    r"tapWjoj",
    r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----",
    r"ghp_[A-Za-z0-9]{36}",
    r"github_pat_[A-Za-z0-9_]{82}",
    r"AKIA[0-9A-Z]{16}",
]

_FORBIDDEN_SCOPE_PATTERNS = [
    r"^backend/src/",
    r"openapi",
    r"migration",
    r"schema",
    r"dependency",
    r"frontend",
    r"website",
    r"design",
    r"visibility.change",
    r"force.push",
    r"paperclip",
]


class TestGL171ReviewMarkdownExists(unittest.TestCase):
    def test_review_markdown_exists(self):
        self.assertTrue(os.path.isfile(_REVIEW_MD), f"Review markdown not found: {_REVIEW_MD}")

    def test_artifact_json_exists(self):
        self.assertTrue(os.path.isfile(_ARTIFACT_JSON), f"Artifact JSON not found: {_ARTIFACT_JSON}")


class TestGL171ArtifactJSON(unittest.TestCase):
    def setUp(self):
        with open(_ARTIFACT_JSON) as fh:
            self._artifact = json.load(fh)

    def test_valid_json(self):
        self.assertIsInstance(self._artifact, dict)

    def test_issue_id(self):
        self.assertEqual(self._artifact.get("issue_id"), "GL-171")

    def test_readiness_decision_is_valid(self):
        decision = self._artifact.get("readiness_decision")
        self.assertIn(
            decision,
            _ALLOWED_REVIEW_DECISIONS,
            f"readiness_decision '{decision}' is not one of {_ALLOWED_REVIEW_DECISIONS}",
        )

    def test_findings_have_required_fields(self):
        findings = self._artifact.get("findings", [])
        self.assertIsInstance(findings, list)
        self.assertGreater(len(findings), 0, "findings list must not be empty")
        for f in findings:
            self.assertIn("severity", f, f"Finding missing 'severity': {f}")
            self.assertIn("status", f, f"Finding missing 'status': {f}")
            self.assertIn("recommendation", f, f"Finding missing 'recommendation': {f}")

    def test_finding_counts_match_findings(self):
        counts = self._artifact.get("finding_counts_by_severity", {})
        findings = self._artifact.get("findings", [])
        reported_total = counts.get("total", -1)
        self.assertEqual(
            reported_total,
            len(findings),
            f"finding_counts_by_severity.total ({reported_total}) != len(findings) ({len(findings)})",
        )
        for severity in ("critical", "high", "medium", "low"):
            expected = counts.get(severity, 0)
            actual = sum(1 for f in findings if f.get("severity") == severity)
            self.assertEqual(
                expected,
                actual,
                f"Count mismatch for severity '{severity}': counts say {expected}, actual {actual}",
            )

    def test_artifact_contains_private_data_snapshot_safety(self):
        self.assertIn("private_data_public_snapshot_safety", self._artifact)
        pdps = self._artifact["private_data_public_snapshot_safety"]
        self.assertIsInstance(pdps, dict)

    def test_private_data_snapshot_safety_has_scan_scope(self):
        pdps = self._artifact["private_data_public_snapshot_safety"]
        self.assertIn("scan_scope", pdps)
        self.assertTrue(len(pdps["scan_scope"]) > 0)

    def test_private_data_snapshot_safety_has_checks_performed(self):
        pdps = self._artifact["private_data_public_snapshot_safety"]
        self.assertIn("checks_performed", pdps)
        self.assertTrue(len(pdps["checks_performed"]) > 0)

    def test_private_data_snapshot_safety_states_private_data_found(self):
        pdps = self._artifact["private_data_public_snapshot_safety"]
        self.assertIn("private_data_found", pdps)
        self.assertIsInstance(pdps["private_data_found"], bool)

    def test_private_data_snapshot_safety_states_secret_material_found(self):
        pdps = self._artifact["private_data_public_snapshot_safety"]
        self.assertIn("secret_material_found", pdps)
        self.assertIsInstance(pdps["secret_material_found"], bool)

    def test_private_data_snapshot_safety_states_synthetic_demo_data(self):
        pdps = self._artifact["private_data_public_snapshot_safety"]
        self.assertIn("public_examples_use_synthetic_demo_data_only", pdps)
        self.assertIsInstance(pdps["public_examples_use_synthetic_demo_data_only"], bool)

    def test_blocked_decision_if_critical_private_data_found(self):
        pdps = self._artifact["private_data_public_snapshot_safety"]
        private_data_found = pdps.get("private_data_found", False)
        secret_material_found = pdps.get("secret_material_found", False)
        findings = self._artifact.get("findings", [])
        has_critical = any(f.get("severity") == "critical" for f in findings)
        decision = self._artifact.get("readiness_decision", "")
        if private_data_found or secret_material_found or has_critical:
            self.assertEqual(
                decision,
                "blocked_before_public_snapshot_publish",
                "readiness_decision must be blocked_before_public_snapshot_publish when critical private data or secret material is reported",
            )


class TestGL171ReviewMarkdownContent(unittest.TestCase):
    def setUp(self):
        with open(_REVIEW_MD) as fh:
            self._content = fh.read()

    def test_no_github_push_performed_stated(self):
        self.assertIn(
            "No GitHub push performed",
            self._content,
            "Review must explicitly state 'No GitHub push performed'",
        )

    def test_no_visibility_change_performed_stated(self):
        self.assertIn(
            "No visibility change performed",
            self._content,
            "Review must explicitly state 'No visibility change performed'",
        )

    def test_does_not_claim_production_saas_readiness(self):
        overclaim_patterns = [
            r"production[- ]ready\s+saas",
            r"production saas readiness\s+claimed",
            r"is production saas ready",
            r"production saas is ready",
        ]
        for pattern in overclaim_patterns:
            self.assertIsNone(
                re.search(pattern, self._content, re.IGNORECASE),
                f"Review must not claim production SaaS readiness (matched: '{pattern}')",
            )

    def test_does_not_claim_tenant_isolation_implemented(self):
        lower = self._content.lower()
        self.assertNotIn(
            "tenant isolation implemented",
            lower,
            "Review must not claim tenant isolation is implemented",
        )

    def test_identifies_canonical_status_sources(self):
        self.assertIn("README.md", self._content)
        self.assertIn("SECURITY.md", self._content)
        lower = self._content.lower()
        self.assertTrue(
            "canonical" in lower or "canonical status" in lower or "status source" in lower,
            "Review must identify README.md and SECURITY.md as canonical status sources",
        )

    def test_references_first_verifiable_output(self):
        self.assertTrue(
            "first_verifiable_output" in self._content or "first verifiable output" in self._content.lower(),
            "Review must reference the first verifiable output quickstart/example",
        )

    def test_no_private_email_in_review(self):
        for pattern in [r"anton\.hofer@", r"hofercloud\.eu"]:
            self.assertIsNone(
                re.search(pattern, self._content, re.IGNORECASE),
                f"Review must not contain private email or hostname matching '{pattern}'",
            )

    def test_no_raw_tokens_in_review(self):
        for pattern in _PRIVATE_PATTERNS:
            self.assertIsNone(
                re.search(pattern, self._content),
                f"Review must not contain private/secret material matching pattern '{pattern}'",
            )


class TestGL171ArtifactNoPrivateData(unittest.TestCase):
    def setUp(self):
        with open(_ARTIFACT_JSON) as fh:
            self._raw = fh.read()

    def test_no_private_patterns_in_artifact(self):
        for pattern in _PRIVATE_PATTERNS:
            self.assertIsNone(
                re.search(pattern, self._raw),
                f"Artifact must not contain private/secret material matching '{pattern}'",
            )


class TestGL171SafetyConfirmations(unittest.TestCase):
    def setUp(self):
        with open(_ARTIFACT_JSON) as fh:
            self._artifact = json.load(fh)

    def test_no_github_push(self):
        sc = self._artifact.get("safety_confirmations", {})
        self.assertTrue(
            sc.get("no_github_push_performed", False),
            "safety_confirmations.no_github_push_performed must be true",
        )

    def test_no_visibility_change(self):
        sc = self._artifact.get("safety_confirmations", {})
        self.assertTrue(
            sc.get("no_visibility_change_performed", False),
            "safety_confirmations.no_visibility_change_performed must be true",
        )

    def test_no_production_changes(self):
        sc = self._artifact.get("safety_confirmations", {})
        self.assertTrue(
            sc.get("no_production_backend_src_changes", False),
            "safety_confirmations.no_production_backend_src_changes must be true",
        )

    def test_no_openapi_migration_changes(self):
        sc = self._artifact.get("safety_confirmations", {})
        self.assertTrue(
            sc.get("no_openapi_migration_db_dependency_changes", False),
            "safety_confirmations.no_openapi_migration_db_dependency_changes must be true",
        )

    def test_changes_within_allowed_scope(self):
        sc = self._artifact.get("safety_confirmations", {})
        self.assertTrue(
            sc.get("changes_within_allowed_scope", False),
            "safety_confirmations.changes_within_allowed_scope must be true",
        )


class TestGL171ChangedFilesScope(unittest.TestCase):
    def setUp(self):
        with open(_ARTIFACT_JSON) as fh:
            self._artifact = json.load(fh)

    def test_changed_files_within_allowed_scope(self):
        changed = self._artifact.get("changed_files", [])
        self.assertIsInstance(changed, list)
        self.assertGreater(len(changed), 0, "changed_files must not be empty")
        for path in changed:
            lower = path.lower()
            for pattern in _FORBIDDEN_SCOPE_PATTERNS:
                self.assertIsNone(
                    re.search(pattern, lower),
                    f"Changed file '{path}' matches forbidden scope pattern '{pattern}'",
                )

    def test_no_backend_src_in_changed_files(self):
        changed = self._artifact.get("changed_files", [])
        for path in changed:
            self.assertFalse(
                path.startswith("backend/src/"),
                f"backend/src/ must not be in changed_files: '{path}'",
            )


if __name__ == "__main__":
    unittest.main()
