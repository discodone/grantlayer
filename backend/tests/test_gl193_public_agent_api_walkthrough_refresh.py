"""GL-193 public agent/API walkthrough refresh tests.

Verifies that the GL-193 walkthrough doc, JSON artifact, and cross-links are
in place, safe, and confined to the allowed file scope.
"""

import json
import subprocess
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[2]

README_PATH = REPO_ROOT / "README.md"
AGENTS_PATH = REPO_ROOT / "AGENTS.md"
LLMS_PATH = REPO_ROOT / "llms.txt"
LLMS_FULL_PATH = REPO_ROOT / "llms-full.txt"
DOC_PATH = REPO_ROOT / "docs" / "public_agent_api_walkthrough_refresh.md"
ARTIFACT_PATH = (
    REPO_ROOT / "docs" / "examples" / "gl193" / "public_agent_api_walkthrough_refresh.json"
)

ALLOWED_CHANGED_FILES = {
    "README.md",
    "AGENTS.md",
    "llms.txt",
    "llms-full.txt",
    "docs/agent_quickstart.md",
    "docs/ten_minute_quickstart.md",
    "docs/public_agent_api_walkthrough_refresh.md",
    "docs/examples/gl193/public_agent_api_walkthrough_refresh.json",
    "backend/tests/test_gl193_public_agent_api_walkthrough_refresh.py",
}

FORBIDDEN_PREFIXES = (
    "backend/src/",
    "docs/openapi.yaml",
    "migrations/",
    "requirements.txt",
    "requirements-dev.txt",
    "scripts/",
    "frontend/",
    "website/",
    "design/",
    "examples/langgraph_langchain/",
    "sdk/python/grantlayer_client.py",
)

FORBIDDEN_PHRASES = (
    "publication pending",
    "public GitHub release has not happened",
    "approved internal source",
    "visibility decision pending",
)

ALLOWED_RESULTS = {
    "public_agent_api_walkthrough_refresh_complete",
    "blocked_unexpected_scope",
    "blocked_public_claim_safety",
    "blocked_other_with_reason",
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path):
    return json.loads(_read_text(path))


def _changed_files() -> list[str]:
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout
    changed = []
    for entry in status.split("\0"):
        if entry.strip():
            changed.append(entry[3:].strip() if len(entry) > 3 else entry.strip())
    if changed:
        return changed

    diff = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout
    return [line.strip() for line in diff.splitlines() if line.strip()]


class TestGL193FilesExist(unittest.TestCase):
    def test_doc_exists(self):
        self.assertTrue(DOC_PATH.is_file(), "docs/public_agent_api_walkthrough_refresh.md must exist")

    def test_artifact_exists(self):
        self.assertTrue(
            ARTIFACT_PATH.is_file(),
            "docs/examples/gl193/public_agent_api_walkthrough_refresh.json must exist",
        )


class TestGL193Artifact(unittest.TestCase):
    def setUp(self):
        self.artifact = _read_json(ARTIFACT_PATH)

    def test_artifact_valid_json(self):
        self.assertIsInstance(self.artifact, dict)

    def test_issue_id(self):
        self.assertEqual(self.artifact["issue_id"], "GL-193")

    def test_result_is_allowed(self):
        self.assertIn(self.artifact["result"], ALLOWED_RESULTS)

    def test_changed_files_within_scope(self):
        changed = set(self.artifact.get("changed_files", []))
        extra = changed - ALLOWED_CHANGED_FILES
        self.assertEqual(extra, set(), f"Unexpected files in artifact changed_files: {extra}")

    def test_safety_confirmations_present(self):
        sc = self.artifact.get("safety_confirmations", {})
        self.assertIsInstance(sc, dict)

    def test_safety_confirmations_true(self):
        sc = self.artifact["safety_confirmations"]
        required_true = [
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
        for key in required_true:
            with self.subTest(key=key):
                self.assertTrue(sc.get(key), f"{key} must be true")

    def test_no_forbidden_phrases_in_artifact(self):
        text = json.dumps(self.artifact).lower()
        for phrase in FORBIDDEN_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase.lower(), text)


class TestGL193DocContent(unittest.TestCase):
    def setUp(self):
        self.doc = _read_text(DOC_PATH)
        self.readme = _read_text(README_PATH)
        self.agents = _read_text(AGENTS_PATH)
        self.llms = _read_text(LLMS_PATH)
        self.llms_full = _read_text(LLMS_FULL_PATH)

    def test_references_readme(self):
        self.assertIn("README.md", self.doc)

    def test_references_agents(self):
        self.assertIn("AGENTS.md", self.doc)

    def test_references_llms(self):
        self.assertTrue("llms.txt" in self.doc or "llms-full.txt" in self.doc)

    def test_references_first_output_helper(self):
        self.assertIn("scripts/verify-first-output.sh", self.doc)
        self.assertIn("docs/first_output_verify_helper.md", self.doc)

    def test_references_grant_lifecycle_example(self):
        self.assertIn("examples/grant_lifecycle_evidence_bundle.py", self.doc)
        self.assertIn("docs/grant_lifecycle_evidence_bundle.md", self.doc)

    def test_references_public_feedback_pack(self):
        self.assertIn("docs/public_feedback_infrastructure_pack.md", self.doc)

    def test_includes_public_and_agent_entry_points(self):
        self.assertIn("Public Developer Entry Points", self.doc)
        self.assertIn("Coding Agent Entry Points", self.doc)

    def test_includes_api_server_path_overview(self):
        self.assertIn("API / Server Path Overview", self.doc)
        self.assertIn("docs/ten_minute_quickstart.md", self.doc)

    def test_separates_no_install_examples_from_backend_quickstart(self):
        lower = self.doc.lower()
        self.assertIn("no-install", lower)
        self.assertIn("backend quickstart", lower)
        self.assertIn("prerequisites", lower)

    def test_states_developer_preview_caveat(self):
        lower = self.doc.lower()
        self.assertTrue("developer preview" in lower or "developer-preview" in lower)

    def test_states_not_production_saas(self):
        lower = self.doc.lower()
        self.assertIn("not production saas", lower)

    def test_states_tenant_isolation_not_implemented(self):
        lower = self.doc.lower()
        self.assertIn("tenant/workspace isolation not implemented", lower)

    def test_states_no_real_secrets_customer_data_private_grants(self):
        lower = self.doc.lower()
        self.assertIn("no real secrets", lower)
        self.assertIn("customer data", lower)
        self.assertIn("private grants", lower)

    def test_routes_security_sensitive_reports_to_advisories(self):
        lower = self.doc.lower()
        self.assertIn("github security advisories", lower)
        self.assertIn("security/advisories", lower)

    def test_no_forbidden_public_state_phrases(self):
        lower = self.doc.lower()
        for phrase in FORBIDDEN_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase.lower(), lower)

    def test_agent_docs_include_current_helper_and_example_refs(self):
        self.assertIn("docs/public_agent_api_walkthrough_refresh.md", self.agents)
        self.assertIn("docs/first_output_verify_helper.md", self.agents)
        self.assertIn("examples/grant_lifecycle_evidence_bundle.py", self.agents)
        self.assertIn("docs/public_feedback_infrastructure_pack.md", self.agents)
        self.assertIn("docs/public_agent_api_walkthrough_refresh.md", self.llms)
        self.assertIn("examples/grant_lifecycle_evidence_bundle.py", self.llms)
        self.assertIn("docs/public_agent_api_walkthrough_refresh.md", self.llms_full)
        self.assertIn("examples/grant_lifecycle_evidence_bundle.py", self.llms_full)

    def test_changed_files_match_allowed_scope(self):
        changed = set(_changed_files())
        extra = changed - ALLOWED_CHANGED_FILES
        self.assertEqual(extra, set(), f"Unexpected changed files: {extra}")

    def test_no_forbidden_paths_changed(self):
        changed = _changed_files()
        for path in changed:
            with self.subTest(path=path):
                for prefix in FORBIDDEN_PREFIXES:
                    self.assertFalse(path.startswith(prefix), f"Forbidden path changed: {path}")


if __name__ == "__main__":
    unittest.main()
