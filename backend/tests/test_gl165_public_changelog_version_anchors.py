"""GL-165 Public CHANGELOG / Version Anchors validation tests."""

import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"
README_PATH = REPO_ROOT / "README.md"
JSON_PATH = (
    REPO_ROOT
    / "docs"
    / "examples"
    / "gl165"
    / "public_changelog_version_anchors.json"
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _load_json():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestGL165ChangelogExists(unittest.TestCase):
    def test_changelog_exists(self):
        self.assertTrue(CHANGELOG_PATH.is_file(), f"Missing: {CHANGELOG_PATH}")

    def test_changelog_title(self):
        self.assertTrue(_read(CHANGELOG_PATH).startswith("# Changelog"))


class TestGL165ChangelogRequiredContent(unittest.TestCase):
    def setUp(self):
        self.content = _read(CHANGELOG_PATH)
        self.lower = self.content.lower()

    def test_developer_preview_gl01(self):
        self.assertIn("Developer Preview / GL-0.1", self.content)

    def test_public_repo_clean_snapshot(self):
        self.assertIn("public GitHub repository is a clean developer-facing snapshot", self.content)

    def test_internal_forgejo_source_of_truth(self):
        self.assertIn("Internal Forgejo remains the source of truth", self.content)

    def test_orientation_not_full_internal_history(self):
        self.assertIn("not a full internal history", self.lower)

    def test_current_public_snapshot_heading(self):
        self.assertIn("## GL-0.1 Developer Preview - Public Snapshot", self.content)

    def test_api_first_verification_layer(self):
        self.assertIn("API-first verification and audit layer", self.content)

    def test_evidence_persistence_verification(self):
        self.assertIn("Evidence persistence and verification", self.content)

    def test_decision_provenance(self):
        self.assertIn("Decision provenance", self.content)

    def test_audit_logs(self):
        self.assertIn("Audit logs", self.content)

    def test_compliance_readiness(self):
        self.assertIn("Compliance readiness", self.content)

    def test_operator_controls(self):
        self.assertIn("Operator controls", self.content)

    def test_tamper_evidence_concepts(self):
        self.assertIn("Tamper-evidence concepts", self.content)

    def test_auditor_export_concepts(self):
        self.assertIn("Auditor export concepts", self.content)

    def test_agent_docs_listed(self):
        for rel in [
            "AGENTS.md",
            "llms.txt",
            "llms-full.txt",
            "docs/agent_quickstart.md",
            "docs/agent_task_contract.md",
        ]:
            self.assertIn(rel, self.content)

    def test_python_sdk_preview(self):
        self.assertIn("Python SDK preview", self.content)

    def test_langgraph_langchain_example(self):
        self.assertIn("LangGraph/LangChain", self.content)

    def test_dashboard_developer_preview_demo_surface(self):
        self.assertIn("Dashboard as a developer-preview/demo surface", self.content)

    def test_public_snapshot_hygiene(self):
        self.assertIn("`backend/` is not published", self.content)
        self.assertIn("No real secrets or customer data", self.content)
        self.assertIn("`.env.example` uses placeholders only", self.content)
        self.assertIn("clean snapshot model", self.content)

    def test_recent_public_hardening_notes(self):
        for note in [
            "Public snapshot scanner-clean export",
            "Removal of backend-dependent public CI workflow",
            "Safe `.env.example`",
            "Dashboard XSS hardening",
            "Post-public intake triage workflow",
            "GitHub Linguist",
        ]:
            self.assertIn(note, self.content)

    def test_public_update_workflow(self):
        for step in [
            "internal issue",
            "internal branch",
            "validation",
            "internal `main`",
            "clean public snapshot",
            "scanner is clean",
            "Publish the public snapshot",
        ]:
            self.assertIn(step.lower(), self.lower)

    def test_roadmap_next_areas(self):
        for area in [
            "Developer feedback triage",
            "Documentation clarity",
            "SDK/API examples",
            "Integration examples",
            "Production-hardening planning",
            "Security and runtime hardening",
            "No dates are promised",
        ]:
            self.assertIn(area, self.content)


class TestGL165CaveatsAndSafety(unittest.TestCase):
    def setUp(self):
        self.content = _read(CHANGELOG_PATH)
        self.lower = self.content.lower()

    def test_not_production_saas(self):
        self.assertIn("not production SaaS", self.content)

    def test_tenant_isolation_not_implemented(self):
        self.assertIn("tenant isolation is not implemented", self.lower)

    def test_not_replacement_for_review(self):
        self.assertIn("not a replacement for auditors, legal review", self.lower)
        self.assertIn("institutional governance", self.lower)

    def test_no_real_secrets(self):
        self.assertIn("Do not use real secrets", self.content)

    def test_no_real_customer_data(self):
        self.assertIn("Do not use real customer data", self.content)

    def test_clean_snapshot_not_full_history(self):
        self.assertIn("clean snapshot, not the full internal history", self.lower)

    def test_no_production_readiness_claim(self):
        forbidden = [
            "production saas " + "ready",
            "production-ready " + "saas",
            "grantlayer is production " + "ready",
            "grantlayer is production-" + "ready",
            "enterprise complete",
            "full compliance",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, self.lower)

    def test_no_tenant_isolation_implemented_claim(self):
        forbidden = [
            "tenant isolation " + "implemented",
            "tenant isolation is " + "implemented",
            "tenant isolation has been " + "implemented",
            "full tenant isolation",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, self.lower)

    def test_no_private_hostnames_or_paths(self):
        forbidden = [
            "forge." + "hofercloud.eu",
            "terminal." + "hofercloud.eu",
            "forge." + "internal.invalid",
            "terminal." + "internal.invalid",
            "/home/" + "adminuser",
            "/home/" + "oai",
            "/mnt/" + "data",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, self.content)


class TestGL165JsonArtifact(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()

    def test_json_parses(self):
        self.assertIsInstance(self.data, dict)

    def test_required_values(self):
        self.assertEqual(self.data["issue"], "GL-165")
        self.assertEqual(self.data["status"], "developer-preview-version-anchors")
        self.assertEqual(self.data["changelogPath"], "CHANGELOG.md")
        self.assertTrue(self.data["publicSnapshotModel"])
        self.assertEqual(self.data["sourceOfTruth"], "internal-forgejo")

    def test_required_arrays(self):
        for key in [
            "caveats",
            "publicUpdateWorkflow",
            "publicHardeningNotes",
            "forbiddenClaims",
        ]:
            self.assertIn(key, self.data)
            self.assertIsInstance(self.data[key], list)
            self.assertGreater(len(self.data[key]), 0)

    def test_caveats_include_required_safety_phrases(self):
        caveats = " ".join(self.data["caveats"]).lower()
        self.assertIn("developer preview / gl-0.1", caveats)
        self.assertIn("not production saas", caveats)
        self.assertIn("tenant isolation is not implemented", caveats)
        self.assertIn("real secrets", caveats)
        self.assertIn("real customer data", caveats)
        self.assertIn("clean snapshot", caveats)

    def test_public_update_workflow_includes_required_steps(self):
        workflow = self.data["publicUpdateWorkflow"]
        for step in [
            "internal-issue",
            "internal-branch",
            "validation",
            "merge-to-internal-main",
            "build-clean-snapshot",
            "scanner-clean",
            "publish-public-snapshot",
        ]:
            self.assertIn(step, workflow)


class TestGL165ReadmeLink(unittest.TestCase):
    def test_readme_links_to_changelog(self):
        readme = _read(README_PATH)
        self.assertIn("[CHANGELOG.md](CHANGELOG.md)", readme)


class TestGL165ScopeGuard(unittest.TestCase):
    def test_no_forbidden_files_changed_on_gl165_branch(self):
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        if branch != "gl-165-public-changelog-version-anchors":
            self.skipTest("Not on GL-165 branch; skipping diff-based scope guard.")

        changed = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.splitlines()

        allowed = {
            "CHANGELOG.md",
            "README.md",
            "docs/examples/gl165/public_changelog_version_anchors.json",
            "backend/tests/test_gl165_public_changelog_version_anchors.py",
        }
        if changed:
            self.assertEqual(set(changed), allowed)
