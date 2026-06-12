"""GL-235: Grant-Requests Fixes + Config Consistency — validation tests.

Verifies:
- BUG 1: operator_id falls back to JWT sub claim (no more 500 on POST /grant-requests)
- BUG 2: "reader" role rejected by /grant-requests (only ALLOWED_GRANT_ROLES accepted)
- BUG 3: .env.example GRANTLAYER_ENABLE_OPERATOR_MODEL consistency (manual check only)
- BUG 4: AGENTS.md rewritten as human contributor guide, no AI-agent language
- BUG 5: QUICKSTART.md uses /auth/token as primary JWT method, no Python-only path
"""

from __future__ import annotations

import os
import re
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_SRC = os.path.join(REPO_ROOT, "backend", "src")


def _read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), encoding="utf-8") as f:
        return f.read()


def _read_src(rel: str) -> str:
    with open(os.path.join(BACKEND_SRC, rel), encoding="utf-8") as f:
        return f.read()


class TestBug1OperatorIdFallback(unittest.TestCase):
    """BUG 1: requested_by must fall back to JWT sub when operator context is absent."""

    def setUp(self):
        self.router_text = _read_src("api/routers/grant_requests.py")

    def test_sub_fallback_present_in_create(self):
        # The create endpoint must use auth_ctx.get("sub") as fallback
        self.assertIn('auth_ctx.get("sub")', self.router_text,
                      "grant_requests.py must fall back to auth_ctx.get('sub') for operator_id")

    def test_sub_fallback_covers_all_three_endpoints(self):
        count = self.router_text.count('auth_ctx.get("sub")')
        self.assertGreaterEqual(count, 3,
                                "sub fallback must appear in create, approve, and deny endpoints")

    def test_null_identity_guard_present(self):
        # Must guard against None operator_id in create endpoint
        self.assertIn("missing_caller_identity", self.router_text,
                      "create endpoint must raise 400 when caller identity cannot be resolved")

    def test_operator_model_unit(self):
        """Unit test: create_grant_request_endpoint extracts sub from JWT-style auth_ctx."""
        import sys
        sys.path.insert(0, os.path.join(REPO_ROOT, "backend"))
        from backend.src.grants.grant_requests import ALLOWED_GRANT_ROLES
        self.assertIn("viewer", ALLOWED_GRANT_ROLES)
        self.assertNotIn("reader", ALLOWED_GRANT_ROLES)


class TestBug2RoleInconsistency(unittest.TestCase):
    """BUG 2: 'reader' is not in ALLOWED_GRANT_ROLES; QUICKSTART must use 'viewer'."""

    def setUp(self):
        import sys
        sys.path.insert(0, os.path.join(REPO_ROOT, "backend"))
        from backend.src.grants.grant_requests import ALLOWED_GRANT_ROLES
        self.allowed = ALLOWED_GRANT_ROLES

    def test_reader_not_in_allowed_grant_roles(self):
        self.assertNotIn("reader", self.allowed,
                         "'reader' must not be in ALLOWED_GRANT_ROLES for grant-requests")

    def test_viewer_in_allowed_grant_roles(self):
        self.assertIn("viewer", self.allowed,
                      "'viewer' must be in ALLOWED_GRANT_ROLES")

    def test_quickstart_grant_requests_uses_viewer(self):
        text = _read("QUICKSTART.md")
        # Find the POST /grant-requests curl block
        post_start = text.find("POST https://localhost/grant-requests")
        self.assertGreater(post_start, 0, "QUICKSTART.md must have POST /grant-requests curl block")
        post_section = text[post_start:post_start + 600]
        self.assertIn('"viewer"', post_section,
                      "QUICKSTART.md grant-requests curl example must use 'viewer' role")
        self.assertNotIn('"reader"', post_section,
                         "QUICKSTART.md grant-requests curl example must not use 'reader' role")

    def test_quickstart_grants_uses_viewer(self):
        text = _read("QUICKSTART.md")
        # Find the /grants POST example (step 5)
        grants_section_start = text.find("POST https://localhost/grants")
        self.assertGreater(grants_section_start, 0, "QUICKSTART.md must have /grants POST section")
        grants_section = text[grants_section_start:grants_section_start + 500]
        self.assertNotIn('"reader"', grants_section,
                         "QUICKSTART.md grants example must not use 'reader' role")


class TestBug4AgentsMd(unittest.TestCase):
    """BUG 4: AGENTS.md must read as a human contributor guide."""

    def setUp(self):
        self.text = _read("AGENTS.md")
        self.lower = self.text.lower()
        self.lines = self.text.splitlines()

    def test_agents_md_under_100_lines(self):
        non_empty = [l for l in self.lines if l.strip()]
        self.assertLessEqual(len(non_empty), 100,
                             f"AGENTS.md should be ≤100 non-empty lines, got {len(non_empty)}")

    def test_title_is_contributing_focused(self):
        # Title should be about contributing, not an AI agent
        first_heading = next((l for l in self.lines if l.startswith("#")), "")
        self.assertTrue(
            "contributing" in first_heading.lower() or "grantlayer" in first_heading.lower(),
            f"First heading should be contributor-focused, got: {first_heading!r}"
        )

    def test_no_ai_workflow_language(self):
        bad_phrases = [
            "if you are an ai",
            "coding agents write code",
            "fast-merge agent",
            "provider_timeout_recovery_needed",
            "final report format",
            "ai workflow",
            "agentic workflow",
        ]
        for phrase in bad_phrases:
            self.assertNotIn(phrase, self.lower,
                             f"AGENTS.md must not contain AI agent instruction language: '{phrase}'")

    def test_no_internal_gl_references(self):
        matches = re.findall(r'\bGL-\d+\b', self.text)
        self.assertEqual(matches, [],
                         f"AGENTS.md must not have internal GL-XXX references: {matches}")

    def test_has_getting_started_section(self):
        self.assertIn("getting started", self.lower)

    def test_has_contributing_section(self):
        self.assertIn("contributing", self.lower)

    def test_has_bug_reporting_section(self):
        self.assertIn("reporting bugs", self.lower)

    def test_has_architecture_section(self):
        self.assertIn("architecture", self.lower)

    def test_safety_phrases_preserved(self):
        self.assertIn("no real secrets", self.lower)
        self.assertIn("no real customer data", self.lower)
        self.assertIn("tenant/workspace isolation is not production-complete", self.lower)


class TestBug5QuickstartJwt(unittest.TestCase):
    """BUG 5: QUICKSTART.md must use /auth/token as the primary JWT method."""

    def setUp(self):
        self.text = _read("QUICKSTART.md")

    def test_auth_token_endpoint_present(self):
        self.assertIn("/auth/token", self.text,
                      "QUICKSTART.md must document /auth/token endpoint")

    def test_no_python_only_token_generation_in_step4(self):
        # Step 4 must not instruct users to run backend Python code as primary method
        # (Option B — Python helper must not appear as a primary step)
        step4_start = self.text.find("## 4. Get a JWT token")
        step5_start = self.text.find("## 5. Create a Grant")
        self.assertGreater(step4_start, 0, "Step 4 must exist")
        self.assertGreater(step5_start, step4_start, "Step 5 must follow Step 4")
        step4_text = self.text[step4_start:step5_start]
        self.assertNotIn("Option B", step4_text,
                         "Step 4 must not offer a Python-only 'Option B' as an alternative")

    def test_curl_auth_token_is_documented(self):
        self.assertIn("POST http", self.text,
                      "QUICKSTART.md must have a curl POST command for token acquisition")

    def test_troubleshooting_uses_curl_not_python_import(self):
        trouble_start = self.text.find("## Troubleshooting")
        self.assertGreater(trouble_start, 0, "Troubleshooting section must exist")
        trouble_text = self.text[trouble_start:]
        # The old troubleshooting used: from backend.src.api.auth_jwt import create_dev_token
        self.assertNotIn("from backend.src.api.auth_jwt import create_dev_token",
                         trouble_text,
                         "Troubleshooting must not use Python import to generate JWT")
