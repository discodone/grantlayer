"""GL-326 — Developer Portal + API Documentation Site.

Covers:
- mkdocs.yml exists with material theme
- mkdocs.yml uses slate palette (dark theme)
- docs/ directory with required files
- docs/index.md exists with GrantLayer title
- docs/getting-started.md exists
- docs/authentication.md exists
- docs/webhooks.md exists
- docs/sdk-python.md exists
- docs/sdk-js.md exists
- docs/self-hosting.md exists
- docs/contributing.md exists
- Makefile has docs and docs-serve targets
- .github/workflows/docs.yml exists and deploys to gh-pages
- CHANGELOG.md updated with GL-308 through GL-326
- mkdocs.yml nav includes all required pages
"""

from __future__ import annotations

import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_DOCS_DIR = _REPO_ROOT / "docs"


class TestMkdocsYaml(unittest.TestCase):
    def setUp(self):
        self.mkdocs_path = _REPO_ROOT / "mkdocs.yml"
        self.content = self.mkdocs_path.read_text()

    def test_mkdocs_yml_exists(self):
        self.assertTrue(self.mkdocs_path.exists())

    def test_uses_material_theme(self):
        self.assertIn("material", self.content)

    def test_uses_slate_dark_palette(self):
        self.assertIn("slate", self.content)

    def test_has_site_name(self):
        self.assertIn("site_name", self.content)
        self.assertIn("GrantLayer", self.content)

    def test_nav_has_required_pages(self):
        required = [
            "index.md",
            "getting-started.md",
            "authentication.md",
            "webhooks.md",
            "sdk-python.md",
            "sdk-js.md",
            "self-hosting.md",
            "contributing.md",
        ]
        for page in required:
            self.assertIn(page, self.content, f"Missing nav entry: {page}")


class TestDocsDirectory(unittest.TestCase):
    def test_docs_dir_exists(self):
        self.assertTrue(_DOCS_DIR.exists())

    def test_index_exists(self):
        self.assertTrue((_DOCS_DIR / "index.md").exists())

    def test_getting_started_exists(self):
        self.assertTrue((_DOCS_DIR / "getting-started.md").exists())

    def test_authentication_exists(self):
        self.assertTrue((_DOCS_DIR / "authentication.md").exists())

    def test_webhooks_exists(self):
        self.assertTrue((_DOCS_DIR / "webhooks.md").exists())

    def test_sdk_python_exists(self):
        self.assertTrue((_DOCS_DIR / "sdk-python.md").exists())

    def test_sdk_js_exists(self):
        self.assertTrue((_DOCS_DIR / "sdk-js.md").exists())

    def test_self_hosting_exists(self):
        self.assertTrue((_DOCS_DIR / "self-hosting.md").exists())

    def test_contributing_exists(self):
        self.assertTrue((_DOCS_DIR / "contributing.md").exists())


class TestDocsContent(unittest.TestCase):
    def test_index_has_grantlayer_title(self):
        content = (_DOCS_DIR / "index.md").read_text()
        self.assertIn("GrantLayer", content)

    def test_auth_mentions_rate_limiting(self):
        content = (_DOCS_DIR / "authentication.md").read_text()
        self.assertIn("rate", content.lower())

    def test_auth_mentions_api_keys(self):
        content = (_DOCS_DIR / "authentication.md").read_text()
        self.assertIn("gl_live_", content)

    def test_self_hosting_mentions_docker(self):
        content = (_DOCS_DIR / "self-hosting.md").read_text()
        self.assertIn("docker", content.lower())

    def test_self_hosting_mentions_env_vars(self):
        content = (_DOCS_DIR / "self-hosting.md").read_text()
        self.assertIn("GRANTLAYER_ADMIN_TOKEN", content)


class TestMakefileDocTargets(unittest.TestCase):
    def setUp(self):
        self.makefile = (_REPO_ROOT / "Makefile").read_text()

    def test_makefile_has_docs_target(self):
        self.assertIn("docs:", self.makefile)

    def test_makefile_has_docs_serve_target(self):
        self.assertIn("docs-serve:", self.makefile)

    def test_makefile_docs_uses_mkdocs(self):
        self.assertIn("mkdocs", self.makefile)


class TestGithubActionsWorkflow(unittest.TestCase):
    def setUp(self):
        self.workflow_path = _REPO_ROOT / ".github" / "workflows" / "docs.yml"

    def test_docs_workflow_exists(self):
        self.assertTrue(self.workflow_path.exists())

    def test_workflow_deploys_to_gh_pages(self):
        content = self.workflow_path.read_text()
        self.assertIn("gh-pages", content)

    def test_workflow_triggers_on_main(self):
        content = self.workflow_path.read_text()
        self.assertIn("main", content)

    def test_workflow_uses_mkdocs(self):
        content = self.workflow_path.read_text()
        self.assertIn("mkdocs", content)


class TestChangelog(unittest.TestCase):
    def setUp(self):
        self.changelog = (_REPO_ROOT / "CHANGELOG.md").read_text()

    def test_changelog_exists(self):
        self.assertTrue((_REPO_ROOT / "CHANGELOG.md").exists())

    def test_changelog_has_tiered_rate_limiting(self):
        self.assertIn("Tiered Rate Limiting", self.changelog)

    def test_changelog_has_api_key_management(self):
        self.assertIn("API Key Management", self.changelog)

    def test_changelog_has_gdpr(self):
        self.assertIn("GDPR", self.changelog)

    def test_changelog_has_performance_benchmarking(self):
        self.assertIn("Performance Benchmarking", self.changelog)

    def test_changelog_has_helm_chart(self):
        self.assertIn("Helm Chart", self.changelog)

    def test_changelog_has_audit_compliance(self):
        self.assertIn("Audit Log Compliance", self.changelog)

    def test_changelog_has_typescript_sdk(self):
        self.assertIn("TypeScript", self.changelog)

    def test_changelog_has_opa(self):
        self.assertIn("OPA Policy Engine", self.changelog)

    def test_changelog_has_grant_templates(self):
        self.assertIn("Grant Templates", self.changelog)

    def test_changelog_has_developer_portal(self):
        self.assertIn("Developer Portal", self.changelog)
