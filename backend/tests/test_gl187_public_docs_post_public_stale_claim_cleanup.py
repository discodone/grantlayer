"""
GL-187 Public Docs Post-Public Stale Claim Cleanup — regression tests.

Verifies that stale pre-publication claims have been removed and public clone
URLs / quickstart consistency corrections are in place.
"""

import json
import os
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _read(relative_path: str) -> str:
    with open(os.path.join(REPO_ROOT, relative_path), encoding="utf-8") as f:
        return f.read()


class TestGL187FilesExist(unittest.TestCase):
    def _assert_file_exists(self, relative_path: str):
        full = os.path.join(REPO_ROOT, relative_path)
        self.assertTrue(os.path.isfile(full), f"Expected file to exist: {relative_path}")

    def test_readme_exists(self):
        self._assert_file_exists("README.md")

    def test_contributing_exists(self):
        self._assert_file_exists("CONTRIBUTING.md")

    def test_agents_exists(self):
        self._assert_file_exists("AGENTS.md")

    def test_llms_full_exists(self):
        self._assert_file_exists("llms-full.txt")

    def test_ten_minute_quickstart_exists(self):
        self._assert_file_exists("docs/ten_minute_quickstart.md")

    def test_agent_quickstart_exists(self):
        self._assert_file_exists("docs/agent_quickstart.md")

    def test_report_markdown_exists(self):
        self._assert_file_exists("docs/public_docs_post_public_stale_claim_cleanup.md")

    def test_json_artifact_exists(self):
        self._assert_file_exists(
            "docs/examples/gl187/public_docs_post_public_stale_claim_cleanup.json"
        )

    def test_json_artifact_valid_json(self):
        content = _read("docs/examples/gl187/public_docs_post_public_stale_claim_cleanup.json")
        obj = json.loads(content)
        self.assertIsInstance(obj, dict)

    def test_json_artifact_issue_id_is_gl187(self):
        content = _read("docs/examples/gl187/public_docs_post_public_stale_claim_cleanup.json")
        obj = json.loads(content)
        self.assertEqual(obj.get("issue_id"), "GL-187")


class TestGL187StaleClaimsRemoved(unittest.TestCase):
    def test_readme_no_stale_test_count(self):
        readme = _read("README.md")
        self.assertNotIn(
            "1130 tests, 3 skipped, 0 failures",
            readme,
            "README must not contain stale 1130 test count claim",
        )

    def test_readme_no_1130_tests(self):
        readme = _read("README.md")
        self.assertNotIn(
            "1130 tests",
            readme,
            "README must not contain stale 1130 tests claim",
        )

    def test_readme_no_publication_pending(self):
        readme = _read("README.md")
        self.assertNotIn(
            "If and when public publication is approved",
            readme,
            "README must not imply publication is still pending",
        )

    def test_contributing_no_not_performed(self):
        contrib = _read("CONTRIBUTING.md")
        self.assertNotIn(
            "Not performed",
            contrib,
            "CONTRIBUTING.md must not say public GitHub release is Not performed",
        )

    def test_contributing_no_requires_explicit_approval(self):
        contrib = _read("CONTRIBUTING.md")
        self.assertNotIn(
            "requires explicit later approval",
            contrib,
            "CONTRIBUTING.md must not say public release requires explicit later approval",
        )

    def test_readme_metadata_section_no_hypothetical(self):
        readme = _read("README.md")
        self.assertNotIn(
            "If and when public publication is approved, the following metadata is recommended",
            readme,
            "README suggested metadata section must not use hypothetical publication framing",
        )

    def test_agents_no_not_performed(self):
        agents = _read("AGENTS.md")
        self.assertNotIn(
            "**Not performed**",
            agents,
            "AGENTS.md must not say public GitHub release is Not performed",
        )

    def test_llms_full_no_visibility_decision_pending(self):
        llms_full = _read("llms-full.txt")
        self.assertNotIn(
            "formal visibility decision pending",
            llms_full,
            "llms-full.txt must not say formal visibility decision pending",
        )

    def test_llms_full_no_gl175_pending(self):
        llms_full = _read("llms-full.txt")
        self.assertNotIn(
            "Synced — formal visibility decision pending (GL-175)",
            llms_full,
            "llms-full.txt must not contain stale GL-175 pending wording",
        )

    def test_ten_minute_quickstart_no_placeholder_clone_url(self):
        qs = _read("docs/ten_minute_quickstart.md")
        self.assertNotIn(
            "<ORG_OR_USER>",
            qs,
            "ten_minute_quickstart must not contain placeholder <ORG_OR_USER> clone URL",
        )

    def test_ten_minute_quickstart_no_approved_internal_source(self):
        qs = _read("docs/ten_minute_quickstart.md")
        self.assertNotIn(
            "approved internal source",
            qs,
            "ten_minute_quickstart must not tell users to use an approved internal source",
        )

    def test_agent_quickstart_no_approved_internal_source(self):
        aq = _read("docs/agent_quickstart.md")
        self.assertNotIn(
            "approved internal source",
            aq,
            "agent_quickstart must not tell agents to clone from an approved internal source",
        )

    def test_agent_quickstart_no_not_performed(self):
        aq = _read("docs/agent_quickstart.md")
        self.assertNotIn(
            "Public GitHub release is **not performed**",
            aq,
            "agent_quickstart must not say public GitHub release is not performed",
        )


class TestGL187PublicCloneConsistency(unittest.TestCase):
    PUBLIC_CLONE_URL = "https://github.com/Discodone/grantlayer.git"

    def test_readme_includes_public_clone_url(self):
        readme = _read("README.md")
        self.assertIn(
            self.PUBLIC_CLONE_URL,
            readme,
            "README.md must include the public clone URL",
        )

    def test_ten_minute_quickstart_includes_public_clone_url(self):
        qs = _read("docs/ten_minute_quickstart.md")
        self.assertIn(
            self.PUBLIC_CLONE_URL,
            qs,
            "ten_minute_quickstart.md must include the public clone URL",
        )

    def test_agent_quickstart_includes_public_clone_url_or_public_note(self):
        aq = _read("docs/agent_quickstart.md")
        self.assertTrue(
            self.PUBLIC_CLONE_URL in aq or "Public repository" in aq,
            "agent_quickstart.md must include public clone URL or note it is a public repository",
        )

    def test_readme_cd_grantlayer_consistent(self):
        readme = _read("README.md")
        # After cloning grantlayer.git the directory is grantlayer, not grantlayer-mvp
        # The cd grantlayer-mvp was the stale inconsistency — it should be gone
        self.assertNotIn(
            "cd grantlayer-mvp",
            readme,
            "README.md must not use cd grantlayer-mvp after cloning grantlayer.git",
        )

    def test_readme_separates_first_output_from_backend_quickstart(self):
        readme = _read("README.md")
        # "Choose your path" or "Path A" guidance should be present
        has_choose = "Choose your path" in readme or "Path A" in readme
        self.assertTrue(
            has_choose,
            "README.md must clearly separate first verifiable output from backend quickstart",
        )


class TestGL187CaveatsPreserved(unittest.TestCase):
    def test_readme_developer_preview_caveat(self):
        readme = _read("README.md")
        self.assertTrue(
            "Developer Preview" in readme or "developer-preview" in readme or "developer preview" in readme.lower(),
            "README.md must preserve developer/technical preview caveat",
        )

    def test_readme_not_production_saas(self):
        readme = _read("README.md")
        self.assertIn(
            "Not claimed",
            readme,
            "README.md must preserve 'Production SaaS readiness | Not claimed' caveat",
        )

    def test_readme_tenant_isolation_not_implemented(self):
        readme = _read("README.md")
        self.assertIn(
            "Not implemented",
            readme,
            "README.md must preserve 'Tenant/workspace isolation | Not implemented' caveat",
        )

    def test_readme_no_real_secrets(self):
        readme = _read("README.md")
        self.assertTrue(
            "no real secrets" in readme.lower() or "Do not use real secrets" in readme,
            "README.md must preserve no real secrets caveat",
        )

    def test_readme_no_real_customer_data(self):
        readme = _read("README.md")
        self.assertTrue(
            "no real customer data" in readme.lower() or "Do not use real customer data" in readme,
            "README.md must preserve no real customer data caveat",
        )

    def test_security_advisories_referenced(self):
        contributing = _read("CONTRIBUTING.md")
        security_ok = (
            "security" in contributing.lower() and "advisories" in contributing.lower()
        )
        self.assertTrue(
            security_ok,
            "CONTRIBUTING.md must direct security-sensitive reports to GitHub Security Advisories",
        )

    def test_docs_no_production_saas_claim(self):
        for path in [
            "README.md",
            "CONTRIBUTING.md",
            "AGENTS.md",
            "docs/ten_minute_quickstart.md",
            "docs/agent_quickstart.md",
        ]:
            content = _read(path)
            self.assertNotIn(
                "production SaaS ready",
                content.lower(),
                f"{path} must not claim production SaaS readiness",
            )

    def test_docs_no_tenant_isolation_claim(self):
        # Check affirmative-claim docs only.
        # AGENTS.md and agent_quickstart.md intentionally contain
        # "Claim tenant isolation is implemented" in their FORBIDDEN lists,
        # which is the correct guardian phrasing — not an affirmative claim.
        for path in [
            "README.md",
            "docs/ten_minute_quickstart.md",
        ]:
            content = _read(path)
            self.assertNotIn(
                "tenant isolation is implemented",
                content.lower(),
                f"{path} must not claim tenant isolation is implemented",
            )


class TestGL187DeferredFollowUps(unittest.TestCase):
    def _artifact(self):
        return json.loads(
            _read("docs/examples/gl187/public_docs_post_public_stale_claim_cleanup.json")
        )

    def test_gl188_deferred(self):
        artifact = self._artifact()
        deferred_ids = [d.get("issue") for d in artifact.get("deferred_follow_ups", [])]
        self.assertIn("GL-188", deferred_ids, "JSON artifact must defer GL-188")

    def test_gl189_deferred(self):
        artifact = self._artifact()
        deferred_ids = [d.get("issue") for d in artifact.get("deferred_follow_ups", [])]
        self.assertIn("GL-189", deferred_ids, "JSON artifact must defer GL-189")

    def test_gl190_deferred(self):
        artifact = self._artifact()
        deferred_ids = [d.get("issue") for d in artifact.get("deferred_follow_ups", [])]
        self.assertIn("GL-190", deferred_ids, "JSON artifact must defer GL-190")

    def test_backend_src_not_modified_recorded(self):
        artifact = self._artifact()
        findings = artifact.get("findings", {})
        self.assertTrue(
            findings.get("backend_src_not_modified"),
            "JSON artifact must record that backend/src was not modified",
        )


class TestGL187SafetyConfirmations(unittest.TestCase):
    def _safety(self):
        artifact = json.loads(
            _read("docs/examples/gl187/public_docs_post_public_stale_claim_cleanup.json")
        )
        return artifact.get("safety_confirmations", {})

    def test_no_github_push_performed(self):
        self.assertTrue(self._safety().get("no_github_push_performed"))

    def test_no_visibility_change_performed(self):
        self.assertTrue(self._safety().get("no_visibility_change_performed"))

    def test_internal_repo_not_pushed_directly_to_github(self):
        self.assertTrue(self._safety().get("internal_repo_not_pushed_directly_to_github"))

    def test_no_outreach_sent(self):
        self.assertTrue(self._safety().get("no_outreach_sent"))

    def test_no_secrets_included(self):
        self.assertTrue(self._safety().get("secrets_not_included"))

    def test_no_exploit_details(self):
        self.assertTrue(self._safety().get("exploit_details_not_included"))

    def test_production_saas_not_claimed(self):
        self.assertTrue(self._safety().get("production_saas_not_claimed"))

    def test_tenant_isolation_not_claimed(self):
        self.assertTrue(self._safety().get("tenant_isolation_not_claimed"))

    def test_no_reviewer_private_data(self):
        self.assertTrue(self._safety().get("no_reviewer_private_data_included"))

    def test_no_github_api_label_changes(self):
        self.assertTrue(self._safety().get("no_github_api_label_changes_performed"))

    def test_no_github_issue_changes(self):
        self.assertTrue(self._safety().get("no_github_issue_changes_performed"))

    def test_real_customer_data_not_requested(self):
        self.assertTrue(self._safety().get("real_customer_data_not_requested"))

    def test_private_grant_data_not_requested(self):
        self.assertTrue(self._safety().get("private_grant_data_not_requested"))


class TestGL187ScopeGuard(unittest.TestCase):
    FORBIDDEN_PATTERNS = [
        ("backend/src/", "backend source code"),
        ("docs/openapi.yaml", "OpenAPI contract"),
        ("requirements.txt", "dependency manifest"),
        ("requirements-dev.txt", "dev dependency manifest"),
    ]

    def test_changed_files_within_allowed_scope(self):
        artifact = json.loads(
            _read("docs/examples/gl187/public_docs_post_public_stale_claim_cleanup.json")
        )
        changed = artifact.get("changed_files", [])
        for f in changed:
            for forbidden_prefix, label in self.FORBIDDEN_PATTERNS:
                self.assertFalse(
                    f.startswith(forbidden_prefix),
                    f"Changed file '{f}' must not be in forbidden scope ({label})",
                )

    def test_result_is_complete(self):
        artifact = json.loads(
            _read("docs/examples/gl187/public_docs_post_public_stale_claim_cleanup.json")
        )
        self.assertEqual(
            artifact.get("result"),
            "public_docs_stale_claim_cleanup_complete",
        )


if __name__ == "__main__":
    unittest.main()
