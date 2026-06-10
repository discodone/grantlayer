"""GL-234 Public Repository Cleanup — validation tests.

Verifies:
- AGENTS.md is rewritten for external developers (no AI agent instruction language)
- GL-XXX references removed from public-facing files
- docs/internal/ directory exists with README
- docs/README.md external index exists
- backend/tests/README.md exists
- llms.txt and llms-full.txt have no GL-XXX issue table
- Safety phrases preserved in AGENTS.md
"""

from __future__ import annotations

import os
import re
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), encoding="utf-8") as f:
        return f.read()


class TestAgentsMdRewrite(unittest.TestCase):

    def setUp(self):
        self.text = _read("AGENTS.md")
        self.lower = self.text.lower()

    def test_agents_md_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(REPO_ROOT, "AGENTS.md")))

    def test_no_ai_agent_instruction_language(self):
        # Old AGENTS.md had "if you are an AI coding agent starting work"
        # and "coding agents write code, run targeted tests"
        bad_phrases = [
            "if you are an ai coding agent",
            "coding agents write code",
            "fast-merge agent",
            "provider_timeout_recovery_needed",
            "final report format",
        ]
        for phrase in bad_phrases:
            self.assertNotIn(
                phrase, self.lower,
                f"AGENTS.md should not contain AI agent instruction: '{phrase}'"
            )

    def test_no_internal_gl_issue_references(self):
        # Should not have GL-NNN references (internal ticket numbers)
        # except for the GitHub URL which legitimately contains the word "grantlayer"
        matches = re.findall(r'\bGL-\d+\b', self.text)
        self.assertEqual(
            matches, [],
            f"AGENTS.md should not reference internal issue numbers: {matches}"
        )

    def test_has_getting_started_section(self):
        self.assertIn("getting started", self.lower)

    def test_has_contributing_reference(self):
        self.assertIn("contributing", self.lower)

    def test_has_bug_reporting_reference(self):
        self.assertIn("bug", self.lower)

    def test_has_security_reporting_reference(self):
        self.assertIn("security", self.lower)

    def test_safety_phrases_preserved(self):
        # These phrases are checked by other tests and must remain
        self.assertIn("no real secrets", self.lower)
        self.assertIn("no real customer data", self.lower)
        self.assertIn("tenant/workspace isolation is not production-complete", self.lower)


class TestGlXxxRemovedFromPublicFiles(unittest.TestCase):

    def _check_no_gl_refs(self, rel_path: str):
        text = _read(rel_path)
        matches = re.findall(r'\bGL-\d+\b', text)
        self.assertEqual(
            matches, [],
            f"{rel_path} should not contain GL-XXX references but found: {matches}"
        )

    def test_readme_no_gl_refs(self):
        self._check_no_gl_refs("README.md")

    def test_quickstart_no_gl_refs(self):
        self._check_no_gl_refs("QUICKSTART.md")

    def test_contributing_no_gl_refs(self):
        self._check_no_gl_refs("CONTRIBUTING.md")

    def test_security_no_gl_refs(self):
        self._check_no_gl_refs("SECURITY.md")

    def test_docker_compose_no_gl_refs(self):
        self._check_no_gl_refs("docker-compose.yml")

    def test_llms_txt_no_gl_issue_table(self):
        text = _read("llms.txt")
        # Should not have GL-XXX issue table rows like "| GL-193 | ... | Complete |"
        issue_table = re.findall(r'\|\s*GL-\d+\s*\|', text)
        self.assertEqual(
            issue_table, [],
            f"llms.txt should not contain GL-XXX issue table rows: {issue_table}"
        )

    def test_llms_full_txt_no_gl_issue_table(self):
        text = _read("llms-full.txt")
        issue_table = re.findall(r'\|\s*GL-\d+\b', text)
        self.assertEqual(
            issue_table, [],
            f"llms-full.txt should not contain GL-XXX issue table rows: {issue_table}"
        )


class TestDocsStructure(unittest.TestCase):

    def test_docs_internal_dir_exists(self):
        self.assertTrue(
            os.path.isdir(os.path.join(REPO_ROOT, "docs", "internal")),
            "docs/internal/ directory must exist"
        )

    def test_docs_internal_readme_exists(self):
        self.assertTrue(
            os.path.isfile(os.path.join(REPO_ROOT, "docs", "internal", "README.md")),
            "docs/internal/README.md must exist"
        )

    def test_docs_readme_exists(self):
        self.assertTrue(
            os.path.isfile(os.path.join(REPO_ROOT, "docs", "README.md")),
            "docs/README.md external index must exist"
        )

    def test_docs_readme_has_external_section(self):
        text = _read("docs/README.md").lower()
        self.assertIn("external", text)
        self.assertIn("architecture", text)
        self.assertIn("openapi", text)

    def test_docs_internal_readme_explains_purpose(self):
        text = _read("docs/internal/README.md").lower()
        self.assertIn("internal", text)
        self.assertIn("not intended for external", text)

    def test_backend_tests_readme_exists(self):
        self.assertTrue(
            os.path.isfile(os.path.join(REPO_ROOT, "backend", "tests", "README.md")),
            "backend/tests/README.md must exist"
        )

    def test_backend_tests_readme_has_content(self):
        text = _read("backend/tests/README.md").lower()
        self.assertIn("functional", text)
        self.assertIn("run", text)


class TestLlmsTxtSafetyPhrases(unittest.TestCase):

    def test_llms_txt_has_safety_phrases(self):
        text = _read("llms.txt").lower()
        self.assertIn("not a production saas", text)
        self.assertIn("tenant/workspace isolation is not production-complete", text)

    def test_llms_full_txt_has_safety_phrase(self):
        text = _read("llms-full.txt").lower()
        self.assertIn("tenant/workspace isolation is not production-complete", text)
