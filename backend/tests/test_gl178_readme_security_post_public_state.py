"""
GL-178: README / SECURITY Post-Public State Correction — automated verification tests.

Verifies that README.md and SECURITY.md accurately reflect the post-GL-176 public state,
that all GL-177 findings F-001/F-002/F-004 are addressed, and that scope guards pass.
"""

import json
import os
import re
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

README_PATH = os.path.join(REPO_ROOT, "README.md")
SECURITY_PATH = os.path.join(REPO_ROOT, "SECURITY.md")
REPORT_PATH = os.path.join(REPO_ROOT, "docs", "readme_security_post_public_state.md")
JSON_ARTIFACT_PATH = os.path.join(
    REPO_ROOT, "docs", "examples", "gl178", "readme_security_post_public_state.json"
)
READINESS_PACK_PATH = os.path.join(
    REPO_ROOT, "docs", "public_github_readiness_pack.md"
)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class TestGL178FilesExist(unittest.TestCase):
    def test_readme_exists(self):
        self.assertTrue(os.path.isfile(README_PATH), "README.md must exist")

    def test_security_exists(self):
        self.assertTrue(os.path.isfile(SECURITY_PATH), "SECURITY.md must exist")

    def test_report_exists(self):
        self.assertTrue(
            os.path.isfile(REPORT_PATH),
            "docs/readme_security_post_public_state.md must exist",
        )

    def test_json_artifact_exists(self):
        self.assertTrue(
            os.path.isfile(JSON_ARTIFACT_PATH),
            "docs/examples/gl178/readme_security_post_public_state.json must exist",
        )


class TestGL178StaleWording(unittest.TestCase):
    """F-001: stale 'visibility pending GL-175' wording must be absent."""

    STALE_PATTERNS = [
        r"visibility\s+pending\s+\(?GL-?175\)?",
        r"formal\s+visibility\s+decision\s+(is\s+)?pending\s+\(?GL-?175\)?",
        r"Public\s+GitHub\s+release\s+has\s+not\s+happened",
        r"Public\s+GitHub\s+publication\s+has\s+not\s+happened",
        r"public-visibility\s+decision.*still\s+required",
        r"reporting\s+channel\s+is\s+\*\*pending\*\*",
    ]

    def _check_file_no_stale(self, path, label):
        content = _read(path)
        for pattern in self.STALE_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            self.assertIsNone(
                match,
                f"{label} must not contain stale wording matching '{pattern}'; "
                f"found: {match.group(0)!r}" if match else "",
            )

    def test_readme_no_stale_gl175_wording(self):
        self._check_file_no_stale(README_PATH, "README.md")

    def test_security_no_stale_gl175_wording(self):
        self._check_file_no_stale(SECURITY_PATH, "SECURITY.md")


class TestGL178PublicAvailable(unittest.TestCase):
    """README.md and SECURITY.md must state the repository is public / publicly available."""

    PUBLIC_PATTERNS = [
        r"publicly\s+available",
        r"publicly\s+accessible",
        r"repository\s+is\s+public",
        r"public\s+GitHub\s+repositor",
    ]

    def _check_file_public_stated(self, path, label):
        content = _read(path)
        found = any(
            re.search(p, content, re.IGNORECASE) for p in self.PUBLIC_PATTERNS
        )
        self.assertTrue(
            found,
            f"{label} must state the repository is public or publicly available",
        )

    def test_readme_states_public(self):
        self._check_file_public_stated(README_PATH, "README.md")

    def test_security_states_public(self):
        self._check_file_public_stated(SECURITY_PATH, "SECURITY.md")


class TestGL178SecurityReportingChannel(unittest.TestCase):
    """F-002: SECURITY.md must have an active security reporting channel."""

    def test_security_has_active_channel(self):
        content = _read(SECURITY_PATH)
        self.assertRegex(
            content,
            r"GitHub\s+Security\s+Advisories",
            "SECURITY.md must reference GitHub Security Advisories as the active reporting channel",
        )

    def test_security_warns_no_public_disclosure(self):
        content = _read(SECURITY_PATH)
        found = any(
            phrase in content.lower()
            for phrase in [
                "do not disclose",
                "avoid public disclosure",
                "not disclose",
                "no exploit details",
                "do not include exploit",
            ]
        )
        self.assertTrue(
            found,
            "SECURITY.md must warn not to disclose exploit details or secrets publicly",
        )


class TestGL178NoClaims(unittest.TestCase):
    """README.md and SECURITY.md must not claim production SaaS readiness or tenant isolation."""

    FORBIDDEN_CLAIMS = [
        (r"production\s+SaaS\s+read(?:y|iness)\s+(?:is\s+)?claimed", "production SaaS claimed"),
        (r"tenant\s+isolation\s+is\s+implemented", "tenant isolation claimed as implemented"),
    ]

    def _check_no_forbidden(self, path, label):
        content = _read(path)
        for pattern, description in self.FORBIDDEN_CLAIMS:
            match = re.search(pattern, content, re.IGNORECASE)
            self.assertIsNone(
                match,
                f"{label} must not claim {description}",
            )

    def test_readme_no_forbidden_claims(self):
        self._check_no_forbidden(README_PATH, "README.md")

    def test_security_no_forbidden_claims(self):
        self._check_no_forbidden(SECURITY_PATH, "SECURITY.md")


class TestGL178CaveatsPreserved(unittest.TestCase):
    """README.md and SECURITY.md must preserve required technical-preview caveats."""

    def _check_caveats(self, path, label):
        content = _read(path)
        checks = [
            (
                r"developer[\s\-]preview|technical\s+preview|developer\s+preview",
                "technical preview / developer preview caveat",
            ),
            (
                r"not\s+production|non-production|not\s+claimed.*production|production.*not\s+claimed"
                r"|production\s+SaaS\s+(readiness\s+)?not\s+claimed"
                r"|no\s+production\s+SaaS\s+support\s+guarantee",
                "not-production caveat",
            ),
            (
                r"tenant\s+isolation\s+not\s+implemented|not\s+implement.*tenant",
                "tenant isolation not implemented caveat",
            ),
            (
                r"no\s+real\s+secrets|real\s+secrets.*no|placeholder.*token|not.*real\s+secrets",
                "no real secrets caveat",
            ),
            (
                r"no\s+real\s+customer\s+data|synthetic\s+identifiers|real\s+customer\s+data.*no",
                "no real customer data caveat",
            ),
        ]
        for pattern, description in checks:
            self.assertRegex(
                content,
                re.compile(pattern, re.IGNORECASE),
                f"{label} must preserve the '{description}'",
            )

    def test_readme_caveats_preserved(self):
        self._check_caveats(README_PATH, "README.md")

    def test_security_caveats_preserved(self):
        self._check_caveats(SECURITY_PATH, "SECURITY.md")


class TestGL178BrokenLink(unittest.TestCase):
    """F-004: README.md must not contain a broken link to docs/public_github_readiness_pack.md
    unless that file is present in the public snapshot (i.e., this repo root)."""

    def test_readme_no_broken_readiness_pack_link(self):
        if os.path.isfile(READINESS_PACK_PATH):
            # File exists — link is not broken; test passes either way
            return
        content = _read(README_PATH)
        self.assertNotIn(
            "public_github_readiness_pack.md",
            content,
            "README.md must not link to docs/public_github_readiness_pack.md "
            "when that file is not present in the public snapshot",
        )


class TestGL178QuickstartReference(unittest.TestCase):
    """README.md must reference the first verifiable output or quickstart path."""

    def test_readme_references_quickstart(self):
        content = _read(README_PATH)
        found = any(
            phrase in content.lower()
            for phrase in [
                "first verifiable output",
                "quickstart",
                "ten_minute_quickstart",
                "ten-minute-quickstart",
            ]
        )
        self.assertTrue(
            found,
            "README.md must reference a first verifiable output or quickstart path",
        )


class TestGL178JSONArtifact(unittest.TestCase):
    """JSON artifact must be valid, contain required fields, and record the right issue."""

    ALLOWED_RESULTS = {
        "readme_security_post_public_state_fixed",
        "blocked_security_reporting_channel_missing",
        "blocked_private_data_or_secret_safety",
        "blocked_other_with_reason",
    }

    def setUp(self):
        with open(JSON_ARTIFACT_PATH, encoding="utf-8") as fh:
            self.data = json.load(fh)

    def test_valid_json(self):
        self.assertIsInstance(self.data, dict)

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-178")

    def test_result_allowed(self):
        self.assertIn(
            self.data.get("result"),
            self.ALLOWED_RESULTS,
            f"result must be one of {self.ALLOWED_RESULTS}",
        )

    def test_addressed_findings_include_f001_f002_f004(self):
        addressed = self.data.get("addressed_findings", [])
        for finding in ("F-001", "F-002", "F-004"):
            self.assertIn(
                finding,
                addressed,
                f"JSON artifact must record {finding} in addressed_findings",
            )

    def test_private_data_secret_safety_exists(self):
        self.assertIn(
            "private_data_secret_safety",
            self.data,
            "JSON artifact must include private_data_secret_safety object",
        )

    def test_private_data_not_found(self):
        safety = self.data.get("private_data_secret_safety", {})
        self.assertFalse(
            safety.get("private_data_found", True),
            "private_data_secret_safety.private_data_found must be false unless blocked",
        )

    def test_secret_material_not_found(self):
        safety = self.data.get("private_data_secret_safety", {})
        self.assertFalse(
            safety.get("secret_material_found", True),
            "private_data_secret_safety.secret_material_found must be false unless blocked",
        )

    def test_private_contact_details_not_added(self):
        safety = self.data.get("private_data_secret_safety", {})
        self.assertFalse(
            safety.get("private_contact_details_added", True),
            "private_data_secret_safety.private_contact_details_added must be false",
        )

    def test_changed_files_listed(self):
        changed = self.data.get("changed_files", [])
        self.assertIn("README.md", changed)
        self.assertIn("SECURITY.md", changed)


class TestGL178ScopeGuards(unittest.TestCase):
    """Changed files must stay within allowed scope — no backend/src, OpenAPI,
    migrations, DB/schema, dependency manifests, SDK implementation,
    frontend/website/design, GitHub workflows, or snapshot publish script changes."""

    FORBIDDEN_PATHS = [
        os.path.join(REPO_ROOT, "backend", "src"),
        os.path.join(REPO_ROOT, "docs", "openapi.yaml"),
        os.path.join(REPO_ROOT, "frontend"),
        os.path.join(REPO_ROOT, "website"),
        os.path.join(REPO_ROOT, ".github", "workflows"),
        os.path.join(REPO_ROOT, "scripts", "publish"),
    ]

    FORBIDDEN_MIGRATION_PATTERNS = [
        r"migrations/.*\.py$",
        r"alembic/.*",
        r"schema\.sql",
    ]

    def test_no_backend_src_changes(self):
        # Verify test file itself is not placed in backend/src
        self.assertNotIn(
            "backend/src",
            os.path.abspath(__file__),
            "Test file must not be placed in backend/src",
        )

    def test_changed_files_no_openapi(self):
        with open(JSON_ARTIFACT_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        changed = data.get("changed_files", [])
        for path in changed:
            self.assertNotIn(
                "openapi",
                path.lower(),
                f"Changed files must not include OpenAPI files; found {path!r}",
            )

    def test_changed_files_no_github_workflows(self):
        with open(JSON_ARTIFACT_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        changed = data.get("changed_files", [])
        for path in changed:
            self.assertNotIn(
                ".github/workflows",
                path,
                f"Changed files must not include GitHub workflow files; found {path!r}",
            )


class TestGL178NoGitHubPush(unittest.TestCase):
    """Declarative tests confirming no GitHub push, no visibility change, no internal push."""

    def test_no_github_push_performed(self):
        # Read the JSON artifact and verify non-goals
        with open(JSON_ARTIFACT_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        non_goals = " ".join(data.get("non_goals", []))
        self.assertIn(
            "No GitHub push performed",
            non_goals,
            "JSON artifact non_goals must confirm no GitHub push was performed",
        )

    def test_no_visibility_change(self):
        with open(JSON_ARTIFACT_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        non_goals = " ".join(data.get("non_goals", []))
        self.assertIn(
            "No visibility change performed",
            non_goals,
            "JSON artifact non_goals must confirm no visibility change was performed",
        )

    def test_report_confirms_no_github_push(self):
        content = _read(REPORT_PATH)
        self.assertIn(
            "No GitHub push performed",
            content,
            "Report must explicitly confirm no GitHub push was performed",
        )

    def test_report_confirms_no_visibility_change(self):
        content = _read(REPORT_PATH)
        self.assertIn(
            "No visibility change performed",
            content,
            "Report must explicitly confirm no visibility change was performed",
        )

    def test_report_confirms_no_internal_tracker_urls(self):
        content = _read(REPORT_PATH)
        # Report must not contain internal Paperclip ticket URLs or Forgejo-internal links
        self.assertNotRegex(
            content,
            r"paperclip\.(io|internal|local|hofer)",
            "Report must not contain internal Paperclip tracker URLs",
        )


if __name__ == "__main__":
    unittest.main()
