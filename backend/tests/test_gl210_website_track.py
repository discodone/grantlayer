"""GL-210 Website Track tests."""

from __future__ import annotations

import json
import os
import re
import subprocess
import unittest
from html.parser import HTMLParser

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "website_track.md")
JSON_PATH = os.path.join(REPO_ROOT, "docs", "examples", "gl210", "website_track.json")
WEBSITE_INDEX = os.path.join(REPO_ROOT, "website", "index.html")
WEBSITE_STYLES = os.path.join(REPO_ROOT, "website", "styles.css")
WEBSITE_README = os.path.join(REPO_ROOT, "website", "README.md")
PREEXISTING_UNTRACKED_EXCLUSIONS = {
    "docs/website_design_workspace_import_report.md",
    "docs/website_design_workspace_import_report_dirty_stop.md",
    "website-design/README.md",
    "website-design/IMPORT_CHECKLIST.md",
}

ALLOWED_RESULTS = {
    "approved_with_gaps",
    "ready_for_merge",
    "website_track_baseline_approved_with_gaps",
}
ALLOWED_DECISIONS = {
    "approved_with_gaps",
    "website_track_baseline_approved_with_gaps",
}


def _path(relpath: str) -> str:
    return os.path.join(REPO_ROOT, relpath)


def _read(relpath: str) -> str:
    with open(_path(relpath), encoding="utf-8") as f:
        return f.read()


def _load_doc() -> str:
    with open(DOC_PATH, encoding="utf-8") as f:
        return f.read()


def _load_json() -> dict:
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _branch_diff_files() -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    files = {line for line in result.stdout.splitlines() if line.strip()}
    if not files:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        merge_commit = subprocess.run(
            ["git", "log", "--merges", "--grep", "Merge GL-210", "-n", "1", "--format=%H"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        if branch == "main" and merge_commit:
            merged = subprocess.run(
                ["git", "diff", "--name-only", f"{merge_commit}^1...{merge_commit}"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            files = {line for line in merged.stdout.splitlines() if line.strip()}
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    files.update(
        line
        for line in untracked.stdout.splitlines()
        if line.strip() and line.strip() not in PREEXISTING_UNTRACKED_EXCLUSIONS
    )
    return files


def _all_tracked_and_branch_text() -> str:
    files = [
        "docs/website_track.md",
        "docs/examples/gl210/website_track.json",
        "website/index.html",
        "website/README.md",
    ]
    return "\n".join(_read(path) for path in files if os.path.exists(_path(path))).lower()


class _TagCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag.lower(), {k.lower(): v or "" for k, v in attrs}))


class TestGL210Artifacts(unittest.TestCase):
    def test_docs_file_exists(self):
        self.assertTrue(os.path.isfile(DOC_PATH))

    def test_json_artifact_exists_and_valid(self):
        self.assertTrue(os.path.isfile(JSON_PATH))
        self.assertIsInstance(_load_json(), dict)

    def test_issue_id_result_and_decision(self):
        data = _load_json()
        self.assertEqual(data.get("issue_id"), "GL-210")
        self.assertIn(data.get("result"), ALLOWED_RESULTS)
        self.assertIn(data.get("decision"), ALLOWED_DECISIONS)

    def test_required_json_sections_present(self):
        required = [
            "decision_rationale",
            "input_sources_reviewed",
            "existing_website_design_inspection",
            "website_claim_boundary",
            "allowed_website_claims",
            "prohibited_website_claims",
            "static_website_implementation_summary",
            "website_file_list",
            "public_publish_status",
            "no_public_publish_confirmation",
            "no_analytics_tracking_forms_confirmation",
            "security_reporting_model",
            "controlled_preview_boundary",
            "production_readiness_impact",
            "remaining_blockers",
            "risk_register",
            "findings",
            "safety_confirmations",
            "recommended_next_issues",
        ]
        data = _load_json()
        for key in required:
            self.assertIn(key, data)
            self.assertTrue(data[key], key)

    def test_input_sources_reviewed_exist(self):
        missing = []
        allowed_dirs = {"website-design"}
        for source in _load_json()["input_sources_reviewed"]:
            rel = source.rstrip("/")
            if rel in allowed_dirs:
                self.assertTrue(os.path.isdir(_path(rel)))
                continue
            if not os.path.exists(_path(rel)):
                missing.append(source)
        self.assertEqual(missing, [])

    def test_existing_website_design_inspection_result(self):
        inspection = _load_json()["existing_website_design_inspection"]
        self.assertTrue(inspection["inspected"])
        self.assertFalse(inspection["adopted"])
        self.assertEqual(inspection["decision"], "excluded")
        self.assertIn("incomplete", inspection["reason"].lower())

    def test_static_website_files_exist_when_implemented(self):
        summary = _load_json()["static_website_implementation_summary"]
        if summary.get("implemented"):
            self.assertTrue(os.path.isfile(WEBSITE_INDEX))
            self.assertTrue(os.path.isfile(WEBSITE_STYLES))
            self.assertTrue(os.path.isfile(WEBSITE_README))


class TestGL210WebsiteCopySafety(unittest.TestCase):
    def setUp(self):
        self.copy = " ".join(_read("website/index.html").split())
        self.copy_lower = self.copy.lower()

    def test_required_preview_boundary_copy(self):
        required = [
            "Developer Preview",
            "Controlled Preview is possible only with strict boundaries",
            "synthetic/demo data",
            "not production SaaS",
            "Not ready for real customer data",
            "Not ready for private grant or institutional data",
            "No official SDK or public SDK package is available",
            "Live PostgreSQL production readiness is not claimed",
            "Compliance certification is not claimed",
            "GitHub Security Advisories",
        ]
        for phrase in required:
            self.assertIn(phrase, self.copy)

    def test_baselines_are_not_overclaimed(self):
        required = [
            "Tenant/workspace isolation baseline is implemented, but it is not production-complete",
            "Admin/operator tenant control-plane baseline exists, but it is not a complete production tenant-management plane",
            "Runtime, IAM, abuse, and incident hardening baseline exists, but it is not a complete production hardening program",
            "Data governance and audit operations baseline exists, but it is not production-complete",
        ]
        for phrase in required:
            self.assertIn(phrase, self.copy)

    def test_no_prohibited_public_claims(self):
        prohibited_patterns = [
            r"(?<!not )production saas ready",
            r"(?<!not )enterprise ready",
            r"(?<!not )compliance certified",
            r"(?<!not )gdpr ready",
            r"(?<!not )soc2 ready",
            r"(?<!not )iso ready",
            r"(?<!not )ready for real customer data",
            r"(?<!not )ready for private grant data",
            r"(?<!not )ready for institutional data",
            r"official sdk available",
            r"public sdk package available",
            r"production-ready sdk",
            r"live postgresql production ready",
            r"complete tenant/workspace production isolation",
            r"complete production admin/operator tenant-management plane",
            r"complete production observability stack",
            r"complete production backup/restore/dr readiness",
            r"complete incident response program",
        ]
        for pattern in prohibited_patterns:
            self.assertIsNone(re.search(pattern, self.copy_lower), pattern)

    def test_no_forms_scripts_external_calls_or_tracking(self):
        parser = _TagCollector()
        parser.feed(_read("website/index.html"))
        tags = parser.tags
        self.assertNotIn("form", [tag for tag, _attrs in tags])
        self.assertNotIn("script", [tag for tag, _attrs in tags])

        for tag, attrs in tags:
            for attr in ("src", "href", "action"):
                value = attrs.get(attr, "")
                self.assertFalse(
                    value.startswith(("http://", "https://", "//")),
                    f"external reference not allowed: <{tag} {attr}={value!r}>",
                )

        website_text = (_read("website/index.html") + "\n" + _read("website/styles.css")).lower()
        forbidden = [
            "@import",
            "google-analytics",
            "googletagmanager",
            "gtag(",
            "analytics",
            "tracking",
            "cookie",
            "fetch(",
            "xmlhttprequest",
            "sendbeacon",
            "api_key",
            "apikey",
            "password=",
            "bearer ",
            "private key",
        ]
        for token in forbidden:
            self.assertNotIn(token, website_text)

    def test_no_real_customer_private_data_or_secrets(self):
        combined = _all_tracked_and_branch_text()
        forbidden_patterns = [
            r"sk-[a-z0-9]{20,}",
            r"ghp_[a-z0-9]{20,}",
            r"postgres://[^\\s]+:[^\\s]+@",
            r"-----begin [a-z ]*private key-----",
            r"real customer data sample",
            r"private grant dossier",
            r"institutional confidential",
        ]
        for pattern in forbidden_patterns:
            self.assertIsNone(re.search(pattern, combined, re.IGNORECASE), pattern)


class TestGL210DocumentationSafety(unittest.TestCase):
    def test_docs_route_security_sensitive_reports_to_advisories(self):
        doc = " ".join(_load_doc().split())
        self.assertIn("Security-sensitive reports route to GitHub Security Advisories", doc)
        self.assertIn("No exploit details are included", doc)

    def test_json_safety_confirmations(self):
        safety = _load_json()["safety_confirmations"]
        for key in [
            "production_saas_not_claimed",
            "enterprise_readiness_not_claimed",
            "compliance_certification_not_claimed",
            "gdpr_soc2_iso_readiness_not_claimed",
            "real_customer_private_grant_institutional_data_no_go",
            "developer_preview_controlled_preview_only",
            "controlled_preview_synthetic_demo_only",
            "tenant_workspace_isolation_not_overclaimed",
            "admin_operator_control_plane_not_overclaimed",
            "runtime_iam_abuse_incident_not_overclaimed",
            "data_governance_audit_operations_not_overclaimed",
            "official_sdk_package_no_go",
            "live_postgres_production_claim_no_go",
            "package_publishing_avoided",
            "no_package_publishing_metadata",
            "no_analytics_tracking_forms",
            "no_external_scripts_assets_api_calls",
            "security_reports_to_github_security_advisories",
            "no_exploit_details",
            "no_real_secrets",
            "no_real_customer_private_data",
            "no_backend_src_changes",
            "no_api_behavior_changes",
            "no_migrations_db_schema_dependency_changes",
            "no_github_workflow_changes",
            "no_snapshot_publish_script_changes",
            "no_public_github_push",
            "no_public_publish",
            "no_visibility_change",
            "unrelated_website_design_files_excluded",
        ]:
            self.assertTrue(safety.get(key), f"{key} must be true")


class TestGL210ScopeGuards(unittest.TestCase):
    def test_branch_diff_only_contains_allowed_files(self):
        allowed = {
            "website/index.html",
            "website/styles.css",
            "website/README.md",
            "docs/website_track.md",
            "docs/examples/gl210/website_track.json",
            "backend/tests/test_gl210_website_track.py",
        }
        self.assertEqual(_branch_diff_files(), allowed)

    def test_no_forbidden_changed_paths(self):
        forbidden_prefixes = [
            "backend/src/",
            "backend/src/migrations/",
            ".github/workflows/",
            "scripts/publish",
            "scripts/snapshot",
            "sdk/python/pyproject.toml",
        ]
        forbidden_exact = {
            "package.json",
            "package-lock.json",
            "setup.py",
            "pyproject.toml",
            "requirements.txt",
            "requirements-dev.txt",
            "docs/openapi.yaml",
        }
        changed = _branch_diff_files()
        for path in changed:
            self.assertNotIn(path, forbidden_exact)
            self.assertFalse(any(path.startswith(prefix) for prefix in forbidden_prefixes), path)

    def test_no_package_json_or_build_system_added(self):
        changed = _branch_diff_files()
        forbidden_names = {"package.json", "package-lock.json", "vite.config.js", "webpack.config.js"}
        self.assertTrue(forbidden_names.isdisjoint({os.path.basename(path) for path in changed}))

    def test_unrelated_website_design_files_excluded(self):
        changed = _branch_diff_files()
        self.assertFalse(any(path.startswith("website-design/") for path in changed))
        inspection = _load_json()["existing_website_design_inspection"]
        self.assertEqual(inspection["decision"], "excluded")
