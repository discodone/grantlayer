"""GL-180: Public Docs Smoke Verification."""

import json
import os
import subprocess
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GL180_BRANCH = "gl-180-public-docs-smoke-verification"
REPORT_PATH = os.path.join(REPO_ROOT, "docs", "public_docs_smoke_verification.md")
JSON_PATH = os.path.join(
    REPO_ROOT, "docs", "examples", "gl180", "public_docs_smoke_verification.json"
)

ALLOWED_SMOKE_DECISIONS = {
    "public_docs_smoke_passed",
    "public_docs_smoke_passed_with_cautions",
    "public_docs_smoke_blocked",
}

ALLOWED_CHANGED_FILES = {
    "docs/public_docs_smoke_verification.md",
    "docs/examples/gl180/public_docs_smoke_verification.json",
    "backend/tests/test_gl180_public_docs_smoke_verification.py",
}

FORBIDDEN_PREFIXES = [
    "backend/src/",
    "docs/openapi.yaml",
    "backend/src/migrations/",
    "requirements.txt",
    "requirements-dev.txt",
    "scripts/",
    "frontend/",
    "website/",
    "design/",
    ".github/workflows/",
]


def _git_diff_files():
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    if branch.returncode == 0 and branch.stdout.strip() != GL180_BRANCH:
        return []
    result = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


class TestGL180ArtifactsExist(unittest.TestCase):
    def test_report_exists(self):
        self.assertTrue(
            os.path.isfile(REPORT_PATH),
            f"GL-180 report markdown not found: {REPORT_PATH}",
        )

    def test_json_exists(self):
        self.assertTrue(
            os.path.isfile(JSON_PATH),
            f"GL-180 JSON artifact not found: {JSON_PATH}",
        )


class TestGL180ArtifactJSON(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(JSON_PATH, encoding="utf-8") as f:
            cls.data = json.load(f)

    def test_valid_json(self):
        self.assertIsInstance(self.data, dict)

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-180")

    def test_public_repository_url(self):
        self.assertEqual(
            self.data.get("public_repository_url"),
            "https://github.com/Discodone/grantlayer.git",
        )

    def test_expected_public_commit_prefix(self):
        self.assertEqual(self.data.get("expected_public_commit_prefix"), "d10bb09")

    def test_actual_public_clone_head_present(self):
        head = self.data.get("actual_public_clone_head", "")
        self.assertIsInstance(head, str)
        self.assertGreater(len(head), 0, "actual_public_clone_head must be non-empty")
        self.assertTrue(
            head.startswith("d10bb09"),
            "actual_public_clone_head must start with the expected public commit prefix",
        )

    def test_smoke_decision_valid(self):
        decision = self.data.get("smoke_decision")
        self.assertIn(
            decision,
            ALLOWED_SMOKE_DECISIONS,
            f"smoke_decision '{decision}' must be one of {ALLOWED_SMOKE_DECISIONS}",
        )

    def test_readme_public_state_exists(self):
        state = self.data.get("readme_public_state")
        self.assertIsInstance(state, dict, "readme_public_state must be a dict")

    def test_readme_public_state_flags(self):
        state = self.data.get("readme_public_state", {})
        self.assertTrue(state.get("readme_present"))
        if self.data.get("smoke_decision") != "public_docs_smoke_blocked":
            self.assertTrue(state.get("stale_gl175_wording_absent"))
            self.assertTrue(state.get("broken_readiness_pack_link_absent"))

    def test_security_public_state_exists(self):
        state = self.data.get("security_public_state")
        self.assertIsInstance(state, dict, "security_public_state must be a dict")

    def test_security_public_state_flags(self):
        state = self.data.get("security_public_state", {})
        self.assertTrue(state.get("security_present"))
        self.assertIn("advisory_channel_url", state)
        if self.data.get("smoke_decision") != "public_docs_smoke_blocked":
            self.assertTrue(state.get("advisory_channel_present"))
            self.assertTrue(state.get("public_disclosure_warning_present"))

    def test_gl177_findings_closure_exists(self):
        closure = self.data.get("gl177_findings_closure")
        self.assertIsInstance(closure, dict, "gl177_findings_closure must be a dict")

    def test_gl177_findings_closed_or_context(self):
        closure = self.data.get("gl177_findings_closure", {})
        self.assertEqual(closure.get("F001_status"), "closed")
        self.assertEqual(closure.get("F002_status"), "closed")
        self.assertEqual(closure.get("F004_status"), "closed")
        self.assertIn("F003_context", closure)
        self.assertIn("F005_context", closure)

    def test_first_verifiable_output_exists(self):
        fvo = self.data.get("first_verifiable_output")
        self.assertIsInstance(fvo, dict, "first_verifiable_output must be a dict")

    def test_first_verifiable_output_files_present(self):
        fvo = self.data.get("first_verifiable_output", {})
        self.assertTrue(fvo.get("files_present"))
        self.assertEqual(fvo.get("exit_code"), 0)
        self.assertTrue(fvo.get("deterministic_match"))

    def test_private_data_secret_smoke_exists(self):
        smoke = self.data.get("private_data_secret_smoke")
        self.assertIsInstance(
            smoke, dict, "private_data_secret_smoke must be a dict"
        )

    def test_private_data_secret_smoke_flags(self):
        smoke = self.data.get("private_data_secret_smoke", {})
        self.assertIn("private_data_found", smoke)
        self.assertIn("secret_material_found", smoke)
        self.assertIn("internal_infrastructure_found", smoke)
        self.assertIn("blockers_found", smoke)
        if smoke.get("blockers_found"):
            self.assertEqual(
                self.data.get("smoke_decision"),
                "public_docs_smoke_blocked",
                "if blockers_found is true, smoke_decision must be public_docs_smoke_blocked",
            )

    def test_findings_structure(self):
        findings = self.data.get("findings", [])
        self.assertIsInstance(findings, list)
        for finding in findings:
            for field in ("id", "severity", "area", "status", "recommendation", "blocking"):
                self.assertIn(
                    field,
                    finding,
                    f"each finding must include field '{field}', missing in {finding.get('id', '?')}",
                )

    def test_findings_counts_match(self):
        findings = self.data.get("findings", [])
        counts = self.data.get("finding_counts_by_severity", {})
        actual_counts = {}
        for finding in findings:
            sev = finding.get("severity", "unknown")
            actual_counts[sev] = actual_counts.get(sev, 0) + 1
        for sev, count in actual_counts.items():
            self.assertEqual(
                counts.get(sev, 0),
                count,
                f"finding_counts_by_severity['{sev}'] must match findings",
            )
        self.assertEqual(counts.get("total"), len(findings))

    def test_report_and_json_state_no_push_or_visibility_change(self):
        non_goals = " ".join(self.data.get("non_goals", [])).lower()
        self.assertIn("no github push", non_goals)
        self.assertIn("no visibility change", non_goals)
        self.assertIn("internal repo was not pushed directly to github", non_goals)

    def test_changed_files_within_scope(self):
        changed_files = self.data.get("changed_files", [])
        self.assertIsInstance(changed_files, list)
        self.assertEqual(set(changed_files), ALLOWED_CHANGED_FILES)
        for path in changed_files:
            for prefix in FORBIDDEN_PREFIXES:
                self.assertFalse(
                    path.startswith(prefix),
                    f"changed file '{path}' must not be in forbidden scope '{prefix}'",
                )


class TestGL180ReportContent(unittest.TestCase):
    def setUp(self):
        with open(REPORT_PATH, encoding="utf-8") as f:
            self.content = f.read()

    def test_mentions_issue_id(self):
        self.assertIn("GL-180", self.content)

    def test_mentions_public_repository_url(self):
        self.assertIn("https://github.com/Discodone/grantlayer.git", self.content)

    def test_mentions_clone_result(self):
        self.assertIn("d10bb09", self.content)
        self.assertIn("/tmp/grantlayer-public-docs-smoke-gl180", self.content)

    def test_states_no_github_push(self):
        lower = self.content.lower()
        self.assertIn("no github push performed", lower)

    def test_states_no_visibility_change(self):
        lower = self.content.lower()
        self.assertIn("no visibility change performed", lower)

    def test_states_internal_repo_not_pushed_directly(self):
        self.assertIn("internal repo was not pushed directly to GitHub", self.content)

    def test_states_public_state_verification(self):
        self.assertIn("README.md", self.content)
        self.assertIn("SECURITY.md", self.content)
        self.assertIn("GitHub Security Advisories", self.content)

    def test_states_first_verifiable_output(self):
        self.assertIn("first verifiable output", self.content.lower())
        self.assertIn("deterministic", self.content.lower())

    def test_states_smoke_decision(self):
        self.assertIn("public_docs_smoke_passed_with_cautions", self.content)

    def test_states_next_recommended_issue(self):
        self.assertIn("GL-181", self.content)

    def test_no_forbidden_path_changes(self):
        forbidden = [
            "backend/src/",
            "docs/openapi.yaml",
            "backend/src/migrations/",
            "requirements.txt",
            "requirements-dev.txt",
            "frontend/",
            "website/",
            "design/",
            ".github/workflows/",
        ]
        for pattern in forbidden:
            with self.subTest(pattern=pattern):
                self.assertNotIn(pattern, self.content)


class TestGL180ScopeGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.diff_files = _git_diff_files()

    def test_changed_files_within_allowed_scope(self):
        for path in self.diff_files:
            self.assertIn(
                path,
                ALLOWED_CHANGED_FILES,
                f"changed file '{path}' is outside allowed GL-180 scope",
            )

    def test_no_backend_src_changes(self):
        for path in self.diff_files:
            self.assertFalse(
                path.startswith("backend/src/"),
                f"backend/src change not allowed for GL-180: {path}",
            )

    def test_no_openapi_changes(self):
        for path in self.diff_files:
            self.assertNotEqual(path, "docs/openapi.yaml")

    def test_no_migration_changes(self):
        for path in self.diff_files:
            self.assertFalse(
                path.startswith("backend/src/migrations/"),
                f"migration change not allowed for GL-180: {path}",
            )

    def test_no_dependency_changes(self):
        for path in self.diff_files:
            self.assertNotIn(path, {"requirements.txt", "requirements-dev.txt"})

    def test_no_frontend_or_website_changes(self):
        for path in self.diff_files:
            self.assertFalse(path.startswith("frontend/"))
            self.assertFalse(path.startswith("website/"))
            self.assertFalse(path.startswith("design/"))

    def test_no_github_workflow_changes(self):
        for path in self.diff_files:
            self.assertFalse(path.startswith(".github/workflows/"))
