"""GL-175 public snapshot visibility decision gate artifact validation."""

import json
import os
import re
import subprocess
import unittest

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_ARTIFACT_MD = os.path.join(
    _REPO_ROOT, "docs", "public_snapshot_visibility_decision_gate.md"
)
_ARTIFACT_JSON = os.path.join(
    _REPO_ROOT,
    "docs",
    "examples",
    "gl175",
    "public_snapshot_visibility_decision_gate.json",
)

_EXPECTED_GITHUB_REPO = "https://github.com/discodone/grantlayer.git"
_ALLOWED_DECISION_VALUES = {
    "proceed_to_public_visibility_or_snapshot_publish",
    "proceed_with_cautions_to_public_visibility_or_snapshot_publish",
    "blocked_before_public_visibility_or_snapshot_publish",
}
_ALLOWED_CHANGED_FILES = {
    "README.md",
    "SECURITY.md",
    "llms.txt",
    "llms-full.txt",
    "docs/public_snapshot_visibility_decision_gate.md",
    "docs/examples/gl175/public_snapshot_visibility_decision_gate.json",
    "backend/tests/test_gl175_public_snapshot_visibility_decision_gate.py",
}
_FORBIDDEN_PATTERNS = [
    r"anton\.hofer@web\.de",
    r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.",
    r"ghp_[A-Za-z0-9_]{10,}",
    r"AKIA[0-9A-Z]{16}",
    r"-----BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY",
    r"192\.168\.\d+\.\d+",
    r"forgejo\.(local|internal|hofercloud)",
    r"/paperclip/",
    r"paperclip is used",
    r"paperclip api calls are required",
]
_STALE_PHRASES = [
    "public github release has not happened",
    "public github release | **not performed",
    "public github release | not performed",
    "not performed — requires explicit later approval",
    "gl-153 | license / contributing / security",
    "gl-154 | agents.md",
    "gl-155 | agent examples pack",
    "gl-156 | github issue templates",
    "this readme was polished in **gl-151",
    "this security.md was created in **gl-153",
]


class TestGL175ArtifactFilesExist(unittest.TestCase):
    def test_markdown_exists(self):
        self.assertTrue(os.path.isfile(_ARTIFACT_MD), f"Markdown not found: {_ARTIFACT_MD}")

    def test_json_exists(self):
        self.assertTrue(os.path.isfile(_ARTIFACT_JSON), f"JSON not found: {_ARTIFACT_JSON}")


class TestGL175ArtifactJSON(unittest.TestCase):
    def setUp(self):
        with open(_ARTIFACT_JSON, encoding="utf-8") as fh:
            self._artifact = json.load(fh)

    def test_valid_json(self):
        self.assertIsInstance(self._artifact, dict)

    def test_issue_id(self):
        self.assertEqual(self._artifact.get("issue_id"), "GL-175")

    def test_public_repo_present(self):
        self.assertEqual(self._artifact.get("public_repo"), _EXPECTED_GITHUB_REPO)

    def test_gl174_review_decision_confirmed(self):
        self.assertEqual(
            self._artifact.get("gl174_review_decision"),
            "proceed_with_cautions_to_visibility_decision",
        )

    def test_visibility_decision_valid(self):
        decision = self._artifact.get("visibility_decision")
        self.assertIn(
            decision,
            _ALLOWED_DECISION_VALUES,
            f"visibility_decision '{decision}' is not one of {_ALLOWED_DECISION_VALUES}",
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

    def test_no_backend_src_or_api_changes(self):
        safety = self._artifact.get("safety_confirmations", {})
        for key in (
            "backend_src_changed",
            "openapi_changed",
            "migration_changed",
            "db_schema_changed",
            "dependencies_changed",
            "sdk_implementation_changed",
            "frontend_changed",
            "snapshot_publish_script_changed",
        ):
            self.assertFalse(
                safety.get(key, True),
                f"safety_confirmations.{key} must be false",
            )

    def test_f001_f002_f004_addressed(self):
        addressed = self._artifact.get("gl174_findings_addressed", [])
        ids = {f["id"] for f in addressed}
        for required in ("F-001", "F-002", "F-004"):
            self.assertIn(required, ids, f"GL-174 finding {required} not listed in gl174_findings_addressed")

    def test_f001_f002_f004_resolved(self):
        addressed = self._artifact.get("gl174_findings_addressed", [])
        for finding in addressed:
            if finding["id"] in ("F-001", "F-002", "F-004"):
                self.assertTrue(
                    finding.get("resolved"),
                    f"Finding {finding['id']} must be resolved=true in GL-175",
                )

    def test_f003_not_a_blocker(self):
        addressed = self._artifact.get("gl174_findings_addressed", [])
        f003 = next((f for f in addressed if f["id"] == "F-003"), None)
        if f003:
            self.assertFalse(
                f003.get("resolved"),
                "F-003 (future improvement) should not be marked resolved in GL-175",
            )

    def test_cleanup_changed_files_present(self):
        changed = self._artifact.get("cleanup_changed_files", [])
        self.assertIsInstance(changed, list)
        self.assertTrue(changed, "cleanup_changed_files must not be empty")

    def test_post_cleanup_checks_present(self):
        checks = self._artifact.get("post_cleanup_checks", {})
        self.assertIsInstance(checks, dict)
        self.assertGreater(len(checks), 0)

    def test_private_data_secret_safety_clean(self):
        pdss = self._artifact.get("private_data_secret_safety", {})
        decision = self._artifact.get("visibility_decision", "")
        if "proceed" in decision:
            self.assertTrue(pdss.get("no_real_secrets_found"))
            self.assertTrue(pdss.get("no_private_keys_found"))
            self.assertTrue(pdss.get("no_paperclip_references_found"))
            self.assertTrue(pdss.get("no_github_visibility_change_instructions_added"))

    def test_evidence_chain_present(self):
        chain = self._artifact.get("evidence_chain", [])
        self.assertIsInstance(chain, list)
        gates = {e["gate"] for e in chain}
        for required in ("GL-172", "GL-173", "GL-174"):
            self.assertIn(required, gates, f"Evidence chain missing gate {required}")

    def test_changed_files_within_scope(self):
        changed = self._artifact.get("changed_files", [])
        self.assertTrue(changed, "changed_files must not be empty")
        for path in changed:
            self.assertIn(
                path,
                _ALLOWED_CHANGED_FILES,
                f"Unexpected changed file outside allowed scope: {path}",
            )

    def test_no_forbidden_patterns_in_artifact(self):
        raw = json.dumps(self._artifact)
        for pattern in _FORBIDDEN_PATTERNS:
            self.assertIsNone(
                re.search(pattern, raw, re.IGNORECASE),
                f"Forbidden pattern found in JSON artifact: {pattern!r}",
            )

    def test_confidence_present(self):
        self.assertTrue(self._artifact.get("confidence"), "confidence must be present")

    def test_recommended_next_issue_present(self):
        self.assertTrue(
            self._artifact.get("recommended_next_issue"),
            "recommended_next_issue must be present",
        )


class TestGL175MarkdownContent(unittest.TestCase):
    def setUp(self):
        with open(_ARTIFACT_MD, encoding="utf-8") as fh:
            self._content = fh.read()
        self._lower = self._content.lower()

    def test_must_reference_issue_id(self):
        self.assertIn("GL-175", self._content)

    def test_must_reference_public_repo(self):
        self.assertIn(_EXPECTED_GITHUB_REPO, self._content)

    def test_must_state_no_github_push(self):
        self.assertIn("No GitHub push performed", self._content)

    def test_must_state_no_visibility_change(self):
        self.assertIn("No visibility change performed", self._content)

    def test_must_reference_visibility_decision(self):
        self.assertIn("Visibility Decision", self._content)
        self.assertIn("proceed_to_public_visibility_or_snapshot_publish", self._content)

    def test_must_reference_evidence_chain(self):
        self.assertIn("GL-172", self._content)
        self.assertIn("GL-173", self._content)
        self.assertIn("GL-174", self._content)

    def test_must_reference_f001_f002_f004_addressed(self):
        self.assertIn("F-001", self._content)
        self.assertIn("F-002", self._content)
        self.assertIn("F-004", self._content)

    def test_must_reference_f003_not_blocker(self):
        self.assertIn("F-003", self._content)
        self.assertIn("not a blocker", self._lower)

    def test_must_state_no_production_saas_claim(self):
        self.assertNotIn("production saas readiness claimed", self._lower)
        self.assertIsNone(re.search(r"production[- ]ready\s+saas", self._lower))

    def test_must_not_claim_tenant_isolation_implemented(self):
        self.assertNotIn("tenant isolation implemented", self._lower)

    def test_must_include_confidence(self):
        self.assertIn("Confidence", self._content)

    def test_must_include_recommended_next_issue(self):
        self.assertIn("Recommended Next Issue", self._content)

    def test_must_include_explicit_confirmations(self):
        self.assertIn("Explicit Confirmations", self._content)

    def test_must_reference_private_data_safety(self):
        self.assertIn("Private Data", self._content)

    def test_no_forbidden_patterns_in_markdown(self):
        for pattern in _FORBIDDEN_PATTERNS:
            self.assertIsNone(
                re.search(pattern, self._content, re.IGNORECASE),
                f"Forbidden pattern found in Markdown artifact: {pattern!r}",
            )


class TestGL175CleanupApplied(unittest.TestCase):
    """Verify the F-001/F-002/F-004 cleanup was actually applied in the codebase."""

    def _read(self, rel_path):
        path = os.path.join(_REPO_ROOT, rel_path)
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def test_readme_status_table_updated(self):
        content = self._read("README.md").lower()
        for phrase in _STALE_PHRASES[:4]:
            self.assertNotIn(
                phrase, content,
                f"Stale phrase still present in README.md: {phrase!r}",
            )

    def test_readme_footer_removed(self):
        content = self._read("README.md").lower()
        self.assertNotIn(
            "this readme was polished in **gl-151",
            content,
            "Internal workflow footnote still present in README.md",
        )

    def test_readme_stale_next_steps_removed(self):
        content = self._read("README.md").lower()
        for phrase in (
            "gl-153 | license",
            "gl-154 | agents.md",
            "gl-155 | agent examples pack",
            "gl-156 | github issue templates",
        ):
            self.assertNotIn(phrase, content, f"Stale next-steps entry still in README.md: {phrase!r}")

    def test_security_status_table_updated(self):
        content = self._read("SECURITY.md").lower()
        self.assertNotIn(
            "not performed — requires explicit later approval",
            content,
            "Stale 'not performed' still in SECURITY.md status table",
        )

    def test_security_footer_removed(self):
        content = self._read("SECURITY.md").lower()
        self.assertNotIn(
            "this security.md was created in **gl-153",
            content,
            "Internal workflow footnote still present in SECURITY.md",
        )

    def test_llms_txt_updated(self):
        content = self._read("llms.txt").lower()
        self.assertNotIn(
            "public github release has not happened",
            content,
            "Stale 'release has not happened' still in llms.txt",
        )

    def test_llms_full_txt_updated(self):
        content = self._read("llms-full.txt").lower()
        self.assertNotIn(
            "public github release | not performed",
            content,
            "Stale status row still in llms-full.txt",
        )
        self.assertNotIn(
            "public github release has not happened",
            content,
            "Stale caveat still in llms-full.txt",
        )

    def test_no_new_secrets_in_readme(self):
        content = self._read("README.md")
        for pattern in _FORBIDDEN_PATTERNS:
            self.assertIsNone(
                re.search(pattern, content, re.IGNORECASE),
                f"Forbidden pattern found in README.md after cleanup: {pattern!r}",
            )

    def test_no_new_secrets_in_security(self):
        content = self._read("SECURITY.md")
        for pattern in _FORBIDDEN_PATTERNS:
            self.assertIsNone(
                re.search(pattern, content, re.IGNORECASE),
                f"Forbidden pattern found in SECURITY.md after cleanup: {pattern!r}",
            )


class TestGL175ChangedFilesScope(unittest.TestCase):
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
        for path in changed:
            for prefix in forbidden_prefixes:
                self.assertFalse(
                    path.startswith(prefix),
                    f"Changed file '{path}' is in forbidden area '{prefix}'",
                )
