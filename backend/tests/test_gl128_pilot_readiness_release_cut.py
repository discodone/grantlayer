"""Tests for GL-128: Pilot Readiness Review / Release Cut.

Ensures:
- docs/pilot_readiness_release_cut.md exists and covers required topics.
- docs/examples/gl128/pilot_readiness_release_cut.json exists and is valid.
- JSON disposition is pilot_ready_with_caveats.
- Baseline references GL-127 and correct suite counts.
- All GL-116 through GL-127 completed gates are listed.
- Markdown distinguishes pilot-ready backend from production-ready SaaS and commercial SaaS.
- Markdown includes accepted caveats, production SaaS blockers, go/no-go criteria.
- Markdown includes required pre-pilot commands.
- Markdown includes recommended next issues GL-129 through GL-134.
- No overclaiming: commercial SaaS complete is not asserted.
- No raw secrets in artifacts.
- No forbidden scope changes.

No production code changes required.
No external services required.
"""

import json
import os
import pathlib
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

_MD_PATH = _REPO_ROOT / "docs" / "pilot_readiness_release_cut.md"
_JSON_PATH = (
    _REPO_ROOT / "docs" / "examples" / "gl128" / "pilot_readiness_release_cut.json"
)

_EXPECTED_GATES = {
    "GL-116",
    "GL-117",
    "GL-118",
    "GL-119",
    "GL-120",
    "GL-121",
    "GL-123",
    "GL-124",
    "GL-125",
    "GL-126",
    "GL-127",
}

_VALID_DISPOSITIONS = {
    "pilot_ready_with_caveats",
    "pilot_ready_blocked",
    "not_pilot_ready",
    "needs_manual_review",
}

_REQUIRED_COMMANDS = [
    "scripts/run-production-runtime-gate.sh",
    "scripts/run-operational-smoke-tests.sh",
    "scripts/run-backup-restore-drill.sh",
    "scripts/run-full-backend-suite.sh",
]

_RECOMMENDED_NEXT_ISSUES = [
    "GL-129",
    "GL-130",
    "GL-131",
    "GL-132",
    "GL-133",
    "GL-134",
]

_SECRET_PATTERNS = [
    re.compile(r"\bpassword\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bsecret\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bapi_key\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bprivate_key\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bpassphrase\s*=\s*\S", re.IGNORECASE),
]


class TestGl128ArtifactsExist(unittest.TestCase):
    """Verify the GL-128 artifacts are present."""

    def test_markdown_review_exists(self):
        self.assertTrue(
            _MD_PATH.exists(),
            f"docs/pilot_readiness_release_cut.md must exist at {_MD_PATH}",
        )

    def test_json_release_cut_exists(self):
        self.assertTrue(
            _JSON_PATH.exists(),
            f"docs/examples/gl128/pilot_readiness_release_cut.json must exist at {_JSON_PATH}",
        )


class TestGl128ReviewContent(unittest.TestCase):
    """Verify GL-128 artifact content meets release-cut requirements."""

    @classmethod
    def setUpClass(cls):
        cls.md_content = _MD_PATH.read_text(encoding="utf-8") if _MD_PATH.exists() else ""
        cls.md_lower = cls.md_content.lower()
        raw_json = _JSON_PATH.read_text(encoding="utf-8") if _JSON_PATH.exists() else "{}"
        cls.json_data = json.loads(raw_json)
        cls.json_str = raw_json.lower()

    # --- JSON structural tests ---

    def test_json_is_valid(self):
        self.assertIsInstance(self.json_data, dict, "JSON must be a top-level object")

    def test_json_issue_id(self):
        self.assertEqual(
            self.json_data.get("issue_id"),
            "GL-128",
            "JSON issue_id must be GL-128",
        )

    def test_json_disposition_valid(self):
        disposition = self.json_data.get("disposition", "")
        self.assertIn(
            disposition,
            _VALID_DISPOSITIONS,
            f"disposition '{disposition}' is not in {_VALID_DISPOSITIONS}",
        )

    def test_json_disposition_is_pilot_ready_with_caveats(self):
        self.assertEqual(
            self.json_data.get("disposition"),
            "pilot_ready_with_caveats",
            "Expected disposition to be pilot_ready_with_caveats",
        )

    def test_json_baseline_includes_gl127(self):
        baseline = self.json_data.get("baseline", {})
        main_after = baseline.get("main_after", "")
        self.assertIn(
            "GL-127",
            main_after,
            "baseline.main_after must reference GL-127",
        )

    def test_json_baseline_suite_counts(self):
        suite = self.json_data.get("baseline", {}).get("full_backend_suite", {})
        self.assertEqual(suite.get("total_or_passed"), 3312, "total_or_passed must be 3312")
        self.assertEqual(suite.get("skipped"), 43, "skipped must be 43")
        self.assertEqual(suite.get("failures"), 0, "failures must be 0")
        self.assertEqual(suite.get("errors"), 0, "errors must be 0")

    def test_json_completed_gates_coverage(self):
        gates = self.json_data.get("completed_gates", [])
        found_ids = {g.get("issue_id") for g in gates if isinstance(g, dict)}
        for expected_id in _EXPECTED_GATES:
            with self.subTest(issue_id=expected_id):
                self.assertIn(
                    expected_id,
                    found_ids,
                    f"completed_gates must include {expected_id}",
                )

    # --- Markdown content tests ---

    def test_markdown_distinguishes_pilot_vs_production_saas(self):
        lower = self.md_lower
        self.assertIn(
            "production saas",
            lower,
            "Markdown must distinguish pilot-ready backend from production SaaS",
        )
        self.assertIn(
            "pilot",
            lower,
            "Markdown must reference pilot readiness",
        )

    def test_markdown_accepted_pilot_caveats(self):
        self.assertIn(
            "caveat",
            self.md_lower,
            "Markdown must include accepted pilot caveats",
        )

    def test_markdown_production_saas_blockers(self):
        lower = self.md_lower
        has_blocker = "blocker" in lower or "not yet complete" in lower or "not complete" in lower
        self.assertTrue(
            has_blocker,
            "Markdown must list production SaaS blockers",
        )

    def test_markdown_go_no_go_criteria(self):
        lower = self.md_lower
        self.assertIn("go", lower)
        self.assertIn("no-go", lower)

    def test_markdown_required_commands(self):
        for cmd in _REQUIRED_COMMANDS:
            with self.subTest(command=cmd):
                self.assertIn(
                    cmd,
                    self.md_content,
                    f"Markdown must include required pre-pilot command: {cmd}",
                )

    def test_markdown_recommended_next_issues(self):
        for issue_id in _RECOMMENDED_NEXT_ISSUES:
            with self.subTest(issue_id=issue_id):
                self.assertIn(
                    issue_id,
                    self.md_content,
                    f"Markdown must include recommended next issue: {issue_id}",
                )

    def test_markdown_no_commercial_saas_complete_claim(self):
        lower = self.md_lower
        # "commercial saas complete" may appear, but only as a negated denial
        # (e.g. "not commercial saas complete"). A bare positive claim is forbidden.
        idx = lower.find("commercial saas complete")
        if idx != -1:
            preceding = lower[max(0, idx - 25):idx]
            has_negation = any(
                neg in preceding
                for neg in ["not ", "never ", "no ", "isn't ", "is not "]
            )
            self.assertTrue(
                has_negation,
                "Markdown must not positively claim 'commercial SaaS complete'; "
                f"found without negation at context: '...{lower[max(0, idx-25):idx+30]}...'",
            )

    def test_markdown_monitoring_alerting_as_blocker_not_complete(self):
        lower = self.md_lower
        if "monitoring" in lower or "alerting" in lower:
            self.assertNotIn(
                "monitoring complete",
                lower,
                "Markdown must not claim monitoring is complete",
            )
            self.assertNotIn(
                "alerting complete",
                lower,
                "Markdown must not claim alerting is complete",
            )

    def test_markdown_no_raw_secrets(self):
        for pattern in _SECRET_PATTERNS:
            for line in self.md_content.splitlines():
                if pattern.search(line):
                    self.fail(
                        f"Markdown must not contain raw secret assignment: {line.strip()}"
                    )

    def test_json_no_raw_secrets(self):
        raw = _JSON_PATH.read_text(encoding="utf-8") if _JSON_PATH.exists() else ""
        for pattern in _SECRET_PATTERNS:
            for line in raw.splitlines():
                if pattern.search(line):
                    self.fail(
                        f"JSON must not contain raw secret assignment: {line.strip()}"
                    )


class TestGl128ScopeGuard(unittest.TestCase):
    """Verify no forbidden files were changed by GL-128."""

    def _changed_files(self):
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        if result.returncode != 0:
            self.skipTest("git diff unavailable; skipping scope guard")
        return result.stdout.strip()

    def test_no_production_code_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("backend/src/"):
                self.fail(f"GL-128 must not change production code: {line}")

    def test_no_openapi_changed(self):
        changed = self._changed_files()
        self.assertNotIn(
            "openapi.yaml",
            changed,
            "GL-128 must not change the OpenAPI specification",
        )

    def test_no_migration_files_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if "migrations/" in line:
                self.fail(f"GL-128 must not change migration files: {line}")

    def test_no_frontend_or_website_files_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("frontend/") or line.startswith("website/"):
                self.fail(f"GL-128 must not change frontend or website files: {line}")

    def test_no_dependency_files_changed(self):
        changed = self._changed_files()
        forbidden = [
            "pyproject.toml",
            "setup.py",
            "requirements",
            "package.json",
            "package-lock.json",
        ]
        for token in forbidden:
            for line in changed.splitlines():
                if token in line:
                    self.fail(
                        f"GL-128 must not change dependency file '{token}': {line}"
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
