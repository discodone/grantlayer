"""GL-174 public snapshot human review gate artifact validation."""

import json
import os
import re
import subprocess
import unittest

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_ARTIFACT_MD = os.path.join(
    _REPO_ROOT,
    "docs",
    "public_snapshot_human_review_gate.md",
)
_ARTIFACT_JSON = os.path.join(
    _REPO_ROOT,
    "docs",
    "examples",
    "gl174",
    "public_snapshot_human_review_gate.json",
)

_EXPECTED_GITHUB_REPO = "https://github.com/discodone/grantlayer.git"
_ALLOWED_DECISION_VALUES = {
    "keep_private_for_now",
    "proceed_with_cautions_to_visibility_decision",
    "proceed_to_visibility_decision",
}
_ALLOWED_SEVERITIES = {"critical", "high", "medium", "low", "info"}
_ALLOWED_CHANGED_FILES = {
    "docs/public_snapshot_human_review_gate.md",
    "docs/examples/gl174/public_snapshot_human_review_gate.json",
    "backend/tests/test_gl174_public_snapshot_human_review_gate.py",
}
_FORBIDDEN_IN_ARTIFACTS = [
    r"anton\.hofer@web\.de",
    r"\+49[\s\-]?\d",
    r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.",
    r"ghp_[A-Za-z0-9_]{10,}",
    r"AKIA[0-9A-Z]{16}",
    r"-----BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY",
    r"192\.168\.\d+\.\d+",
    r"forgejo\.(local|internal|hofercloud)",
    r"/paperclip/",
    r"paperclip is used",
    r"use paperclip",
    r"paperclip api calls are required",
    r"call paperclip apis",
]


class TestGL174ArtifactFilesExist(unittest.TestCase):
    def test_markdown_exists(self):
        self.assertTrue(os.path.isfile(_ARTIFACT_MD), f"Markdown not found: {_ARTIFACT_MD}")

    def test_json_exists(self):
        self.assertTrue(os.path.isfile(_ARTIFACT_JSON), f"JSON not found: {_ARTIFACT_JSON}")


class TestGL174ArtifactJSON(unittest.TestCase):
    def setUp(self):
        with open(_ARTIFACT_JSON, encoding="utf-8") as fh:
            self._artifact = json.load(fh)

    def test_valid_json(self):
        self.assertIsInstance(self._artifact, dict)

    def test_issue_id(self):
        self.assertEqual(self._artifact.get("issue_id"), "GL-174")

    def test_public_repo_present(self):
        self.assertEqual(
            self._artifact.get("public_repo"),
            _EXPECTED_GITHUB_REPO,
        )

    def test_public_commit_reviewed_present(self):
        commit = self._artifact.get("public_commit_reviewed")
        self.assertTrue(commit, "public_commit_reviewed must be present and non-empty")
        self.assertIsInstance(commit, str)
        self.assertGreater(len(commit), 10)

    def test_internal_base_commit_present(self):
        commit = self._artifact.get("internal_base_commit")
        self.assertTrue(commit, "internal_base_commit must be present and non-empty")

    def test_reviewer_personas_present(self):
        personas = self._artifact.get("reviewer_personas")
        self.assertIsInstance(personas, list)
        self.assertGreater(len(personas), 0)

    def test_checks_performed_present(self):
        checks = self._artifact.get("checks_performed")
        self.assertIsInstance(checks, list)
        self.assertGreater(len(checks), 0)

    def test_review_decision_valid(self):
        decision = self._artifact.get("review_decision")
        self.assertIn(
            decision,
            _ALLOWED_DECISION_VALUES,
            f"review_decision '{decision}' is not one of {_ALLOWED_DECISION_VALUES}",
        )

    def test_findings_have_required_fields(self):
        findings = self._artifact.get("findings")
        self.assertIsInstance(findings, list)
        for finding in findings:
            self.assertIn("id", finding, "Finding missing 'id' field")
            self.assertIn("severity", finding, "Finding missing 'severity' field")
            self.assertIn("status", finding, "Finding missing 'status' field")
            self.assertIn("area", finding, "Finding missing 'area' field")
            self.assertIn("summary", finding, "Finding missing 'summary' field")
            self.assertIn("recommendation", finding, "Finding missing 'recommendation' field")

    def test_findings_have_allowed_severities(self):
        findings = self._artifact.get("findings", [])
        for finding in findings:
            severity = finding.get("severity")
            self.assertIn(
                severity,
                _ALLOWED_SEVERITIES,
                f"Finding severity '{severity}' is not allowed",
            )

    def test_finding_counts_match_findings(self):
        counts = self._artifact.get("finding_counts_by_severity", {})
        findings = self._artifact.get("findings", [])
        self.assertEqual(
            counts.get("total"),
            len(findings),
            f"finding_counts_by_severity.total {counts.get('total')} != len(findings) {len(findings)}",
        )
        for severity in ("critical", "high", "medium", "low"):
            expected = counts.get(severity, 0)
            actual = sum(1 for f in findings if f.get("severity") == severity)
            self.assertEqual(
                expected,
                actual,
                f"Count mismatch for severity '{severity}': expected {expected}, got {actual}",
            )

    def test_critical_findings_require_keep_private(self):
        counts = self._artifact.get("finding_counts_by_severity", {})
        decision = self._artifact.get("review_decision")
        if counts.get("critical", 0) > 0:
            self.assertEqual(
                decision,
                "keep_private_for_now",
                "Critical findings present but decision is not keep_private_for_now",
            )

    def test_no_github_push_performed(self):
        safety = self._artifact.get("safety_confirmations", {})
        self.assertFalse(
            safety.get("github_push_performed", True),
            "safety_confirmations.github_push_performed must be false",
        )

    def test_no_visibility_change(self):
        safety = self._artifact.get("safety_confirmations", {})
        self.assertFalse(
            safety.get("visibility_changed", True),
            "safety_confirmations.visibility_changed must be false",
        )

    def test_no_backend_src_changes(self):
        safety = self._artifact.get("safety_confirmations", {})
        self.assertFalse(
            safety.get("backend_src_changed", True),
            "safety_confirmations.backend_src_changed must be false",
        )

    def test_no_openapi_migration_db_dependency_frontend_changes(self):
        safety = self._artifact.get("safety_confirmations", {})
        for key in ("openapi_changed", "migration_changed", "db_schema_changed",
                    "dependencies_changed", "frontend_changed",
                    "snapshot_publish_script_changed"):
            self.assertFalse(
                safety.get(key, True),
                f"safety_confirmations.{key} must be false",
            )

    def test_first_output_assessment_exists_and_references_first_output(self):
        foa = self._artifact.get("first_output_assessment")
        self.assertIsInstance(foa, dict, "first_output_assessment must be a dict")
        raw = json.dumps(foa).lower()
        self.assertIn(
            "first_verifiable_output",
            raw,
            "first_output_assessment must reference first verifiable output",
        )
        self.assertIn("assessment", foa, "first_output_assessment must include 'assessment'")

    def test_audience_clarity_assessment_exists(self):
        aca = self._artifact.get("audience_clarity_assessment")
        self.assertIsInstance(aca, dict, "audience_clarity_assessment must be a dict")
        self.assertTrue(len(aca) > 0)

    def test_public_code_surface_assessment_exists(self):
        pcsa = self._artifact.get("public_code_surface_assessment")
        self.assertIsInstance(pcsa, dict, "public_code_surface_assessment must be a dict")
        self.assertIn("assessment", pcsa)

    def test_private_data_secret_safety_exists_and_confirms_no_secrets_when_proceeding(self):
        pdss = self._artifact.get("private_data_secret_safety")
        self.assertIsInstance(pdss, dict, "private_data_secret_safety must be a dict")
        decision = self._artifact.get("review_decision")
        if decision in ("proceed_to_visibility_decision",
                        "proceed_with_cautions_to_visibility_decision"):
            self.assertTrue(
                pdss.get("no_real_secrets_found"),
                "private_data_secret_safety.no_real_secrets_found must be true when proceeding",
            )
            self.assertTrue(
                pdss.get("no_private_keys_found"),
                "private_data_secret_safety.no_private_keys_found must be true when proceeding",
            )
            self.assertTrue(
                pdss.get("no_paperclip_references_found"),
                "private_data_secret_safety.no_paperclip_references_found must be true when proceeding",
            )

    def test_readme_security_canonical_handling_referenced(self):
        aca = self._artifact.get("audience_clarity_assessment", {})
        self.assertIn(
            "readme_canonical_status_source",
            aca,
            "audience_clarity_assessment must reference readme_canonical_status_source",
        )
        self.assertIn(
            "security_canonical_caveat_source",
            aca,
            "audience_clarity_assessment must reference security_canonical_caveat_source",
        )

    def test_changed_files_within_allowed_scope(self):
        changed_files = self._artifact.get("changed_files", [])
        self.assertTrue(changed_files, "changed_files must not be empty")
        for path in changed_files:
            self.assertIn(
                path,
                _ALLOWED_CHANGED_FILES,
                f"Unexpected changed file outside allowed scope: {path}",
            )

    def test_no_production_saas_readiness_claim(self):
        raw = json.dumps(self._artifact).lower()
        self.assertNotIn("production saas readiness claimed", raw)
        self.assertIsNone(re.search(r"production[- ]ready\s+saas", raw))

    def test_no_tenant_isolation_implemented_claim(self):
        raw = json.dumps(self._artifact).lower()
        self.assertNotIn("tenant isolation implemented", raw)

    def test_no_forbidden_content_in_artifact(self):
        raw = json.dumps(self._artifact)
        for pattern in _FORBIDDEN_IN_ARTIFACTS:
            match = re.search(pattern, raw, re.IGNORECASE)
            self.assertIsNone(
                match,
                f"Forbidden pattern found in JSON artifact: {pattern!r}",
            )

    def test_recommended_next_issue_present(self):
        next_issue = self._artifact.get("recommended_next_issue")
        self.assertTrue(next_issue, "recommended_next_issue must be present and non-empty")

    def test_confidence_present(self):
        confidence = self._artifact.get("confidence")
        self.assertTrue(confidence, "confidence must be present and non-empty")


class TestGL174MarkdownContent(unittest.TestCase):
    def setUp(self):
        with open(_ARTIFACT_MD, encoding="utf-8") as fh:
            self._content = fh.read()
        self._lower = self._content.lower()

    def test_must_reference_issue_id(self):
        self.assertIn("GL-174", self._content)

    def test_must_reference_public_repo(self):
        self.assertIn(_EXPECTED_GITHUB_REPO, self._content)

    def test_must_reference_public_commit(self):
        self.assertIn("4b42f7f00b11a12413d4e4bdce99c4ea921dfa0d", self._content)

    def test_must_reference_internal_commit(self):
        self.assertIn("24c8f8a8a22609f89afe3d1b40b94bbb593e8d4f", self._content)

    def test_must_reference_review_scope(self):
        self.assertIn("Review Scope", self._content)

    def test_must_reference_reviewer_personas(self):
        self.assertIn("Reviewer Personas", self._content)

    def test_must_reference_findings_table(self):
        self.assertIn("Findings", self._content)

    def test_must_reference_finding_counts(self):
        self.assertIn("Finding Counts", self._content)

    def test_must_include_review_decision(self):
        self.assertIn("Review Decision", self._content)
        self.assertIn("proceed_with_cautions_to_visibility_decision", self._content)

    def test_must_include_confidence(self):
        self.assertIn("Confidence", self._content)

    def test_must_include_recommended_next_issue(self):
        self.assertIn("Recommended Next Issue", self._content)

    def test_must_state_no_github_push(self):
        self.assertIn("No GitHub push performed", self._content)

    def test_must_state_no_visibility_change(self):
        self.assertIn("No visibility change performed", self._content)

    def test_must_state_no_production_backend_src_changes(self):
        self.assertIn("No backend/src changes", self._content)

    def test_must_include_first_output_assessment(self):
        self.assertIn("First-Output Assessment", self._content)
        self.assertIn("first verifiable output", self._lower)

    def test_must_include_audience_clarity_assessment(self):
        self.assertIn("Audience Clarity Assessment", self._content)

    def test_must_include_public_code_surface_assessment(self):
        self.assertIn("Public Code Surface Assessment", self._content)

    def test_must_include_private_data_assessment(self):
        self.assertIn("Private Data", self._content)

    def test_must_reference_readme_and_security_canonical_sources(self):
        self.assertIn("README.md", self._content)
        self.assertIn("SECURITY.md", self._content)
        self.assertIn("canonical", self._lower)

    def test_must_not_claim_production_saas_readiness(self):
        self.assertNotIn("production saas readiness claimed", self._lower)
        self.assertIsNone(re.search(r"production[- ]ready\s+saas", self._lower))

    def test_must_not_claim_tenant_isolation_implemented(self):
        self.assertNotIn("tenant isolation implemented", self._lower)

    def test_no_forbidden_content_in_markdown(self):
        for pattern in _FORBIDDEN_IN_ARTIFACTS:
            match = re.search(pattern, self._content, re.IGNORECASE)
            self.assertIsNone(
                match,
                f"Forbidden pattern found in Markdown artifact: {pattern!r}",
            )

    def test_must_include_human_readable_summary(self):
        self.assertIn("Human-Readable Summary", self._content)

    def test_must_include_explicit_confirmations(self):
        self.assertIn("Explicit Confirmations", self._content)


class TestGL174ChangedFilesScope(unittest.TestCase):
    def test_changed_files_within_scope(self):
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            self.skipTest(f"git diff failed: {result.stderr.strip()}")
        changed = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        forbidden_prefixes = (
            "backend/src/",
            "docs/openapi",
            "migrations/",
            "requirements",
        )
        forbidden_files = {
            "README.md",
            "SECURITY.md",
            "AGENTS.md",
            "llms.txt",
            "llms-full.txt",
        }
        for path in changed:
            for prefix in forbidden_prefixes:
                self.assertFalse(
                    path.startswith(prefix),
                    f"Changed file '{path}' is in forbidden area '{prefix}'",
                )
            if path in forbidden_files:
                self.fail(f"Changed file '{path}' is in the forbidden files list for GL-174")

    def test_no_github_push_confirmed_via_git_status(self):
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            self.skipTest(f"git status failed: {result.stderr.strip()}")
        output = result.stdout.strip()
        self.assertNotIn("ahead of 'origin'", output)
