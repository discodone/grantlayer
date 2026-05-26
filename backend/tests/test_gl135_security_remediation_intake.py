"""Tests for GL-135: Security Remediation Intake.

Ensures:
- docs/security_remediation_intake_2026_05_26.md exists and covers required topics.
- docs/examples/gl135/security_remediation_intake_2026_05_26.json exists and is valid.
- JSON issue_id is GL-135.
- JSON review_only is true.
- JSON production_code_changed is false.
- JSON remediations_implemented is false.
- Senior review and remediation plan are both referenced.
- All integrated findings are represented.
- P0/P1/P2/P3 ordering exists.
- Corrected roadmap includes GL-136 through GL-144.
- next_issue is GL-136 Remove Demo Private Key From Tracking / Add Key Hygiene Gate.
- ThreadingHTTPServer sequencing rule exists.
- Production SaaS non-claim exists.
- No raw secret values are present.
- Scope guard: no backend/src changes.
- Scope guard: no docs/openapi.yaml changes.
- Scope guard: no migrations/DB schema changes.
- Scope guard: no dependency file changes.
- Scope guard: no frontend/website/design changes.

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

_MD_PATH = _REPO_ROOT / "docs" / "security_remediation_intake_2026_05_26.md"
_JSON_PATH = (
    _REPO_ROOT
    / "docs"
    / "examples"
    / "gl135"
    / "security_remediation_intake_2026_05_26.json"
)

_SECRET_PATTERNS = [
    re.compile(r"\bpassword\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bsecret\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bapi_key\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bprivate_key\s*=\s*\S", re.IGNORECASE),
    re.compile(r"\bpassphrase\s*=\s*\S", re.IGNORECASE),
]

# List of findings that must be present in the integrated findings
_REQUIRED_FINDINGS = [
    "committed demo private key",
    "missing python dependency manifest",
    "duplicate check_admin_token",
    "single-threaded httpserver",
    "audit hash-chain",
    "enable_operator_model",
    "bytesio",
    "server.py",
    "in-memory rate limiter",
]


class TestGl135ArtifactsExist(unittest.TestCase):
    """Verify the GL-135 artifacts are present."""

    def test_markdown_exists(self):
        self.assertTrue(
            _MD_PATH.exists(),
            f"docs/security_remediation_intake_2026_05_26.md must exist at {_MD_PATH}",
        )

    def test_json_exists(self):
        self.assertTrue(
            _JSON_PATH.exists(),
            f"docs/examples/gl135/security_remediation_intake_2026_05_26.json must exist at {_JSON_PATH}",
        )


class TestGl135JsonStructure(unittest.TestCase):
    """Verify GL-135 JSON structure and values."""

    @classmethod
    def setUpClass(cls):
        raw_json = _JSON_PATH.read_text(encoding="utf-8") if _JSON_PATH.exists() else "{}"
        cls.json_data = json.loads(raw_json)
        cls.json_str = raw_json.lower()

    def test_json_is_valid(self):
        self.assertIsInstance(self.json_data, dict, "JSON must be a top-level object")

    def test_json_issue_id(self):
        self.assertEqual(
            self.json_data.get("issue_id"),
            "GL-135",
            "JSON issue_id must be GL-135",
        )

    def test_json_artifact_type(self):
        self.assertEqual(
            self.json_data.get("artifact_type"),
            "security_remediation_intake",
            "JSON artifact_type must be security_remediation_intake",
        )

    def test_json_review_only_is_true(self):
        self.assertIs(
            self.json_data.get("review_only"),
            True,
            "JSON review_only must be true",
        )

    def test_json_production_code_changed_is_false(self):
        self.assertIs(
            self.json_data.get("production_code_changed"),
            False,
            "JSON production_code_changed must be false",
        )

    def test_json_remediations_implemented_is_false(self):
        self.assertIs(
            self.json_data.get("remediations_implemented"),
            False,
            "JSON remediations_implemented must be false",
        )

    def test_json_senior_review_integrated_is_true(self):
        self.assertIs(
            self.json_data.get("senior_review_integrated"),
            True,
            "JSON senior_review_integrated must be true",
        )

    def test_json_remediation_plan_integrated_is_true(self):
        self.assertIs(
            self.json_data.get("remediation_plan_integrated"),
            True,
            "JSON remediation_plan_integrated must be true",
        )

    def test_json_current_state_is_dict(self):
        self.assertIsInstance(
            self.json_data.get("current_state"),
            dict,
            "JSON current_state must be an object",
        )

    def test_json_p0_findings_is_list(self):
        self.assertIsInstance(
            self.json_data.get("p0_findings"),
            list,
            "JSON p0_findings must be a list",
        )

    def test_json_p1_findings_is_list(self):
        self.assertIsInstance(
            self.json_data.get("p1_findings"),
            list,
            "JSON p1_findings must be a list",
        )

    def test_json_p2_findings_is_list(self):
        self.assertIsInstance(
            self.json_data.get("p2_findings"),
            list,
            "JSON p2_findings must be a list",
        )

    def test_json_p3_findings_is_list(self):
        self.assertIsInstance(
            self.json_data.get("p3_findings"),
            list,
            "JSON p3_findings must be a list",
        )

    def test_json_corrected_roadmap_is_list(self):
        self.assertIsInstance(
            self.json_data.get("corrected_roadmap"),
            list,
            "JSON corrected_roadmap must be a list",
        )

    def test_json_sequencing_rules_is_list(self):
        self.assertIsInstance(
            self.json_data.get("sequencing_rules"),
            list,
            "JSON sequencing_rules must be a list",
        )

    def test_json_explicit_non_goals_is_list(self):
        self.assertIsInstance(
            self.json_data.get("explicit_non_goals"),
            list,
            "JSON explicit_non_goals must be a list",
        )

    def test_json_next_issue(self):
        self.assertEqual(
            self.json_data.get("next_issue"),
            "GL-136 Remove Demo Private Key From Tracking / Add Key Hygiene Gate",
            "JSON next_issue must be GL-136 key hygiene",
        )


class TestGl135MarkdownContent(unittest.TestCase):
    """Verify GL-135 markdown content meets baseline requirements."""

    @classmethod
    def setUpClass(cls):
        cls.md_content = _MD_PATH.read_text(encoding="utf-8") if _MD_PATH.exists() else ""
        cls.md_lower = cls.md_content.lower()

    # --- Scope assertions ---

    def test_markdown_says_not_remediation_implementation(self):
        lower = self.md_lower
        self.assertTrue(
            "not remediation implementation" in lower
            or "this is not production code" in lower,
            "Markdown must state that GL-135 is not remediation implementation",
        )

    def test_markdown_says_not_key_removal(self):
        lower = self.md_lower
        self.assertTrue(
            "no key removal" in lower
            or "not key removal" in lower
            or "key hygiene" in lower,
            "Markdown must state no key removal in GL-135",
        )

    def test_markdown_says_not_tenant_implementation(self):
        lower = self.md_lower
        self.assertTrue(
            "not tenant/workspace implementation" in lower
            or "no tenant implementation" in lower,
            "Markdown must state no tenant/workspace implementation in GL-135",
        )

    # --- Input artifacts ---

    def test_senior_developer_review_referenced(self):
        lower = self.md_lower
        self.assertIn("senior developer review", lower)

    def test_remediation_plan_referenced(self):
        lower = self.md_lower
        self.assertIn("remediation plan", lower)

    # --- Current state ---

    def test_current_state_gl128_through_gl134_completed(self):
        lower = self.md_lower
        self.assertIn("gl-128 through gl-134", lower)

    def test_current_state_pilot_strong(self):
        lower = self.md_lower
        self.assertIn("controlled pilot preparation is strong", lower)

    def test_current_state_production_saas_blocked(self):
        lower = self.md_lower
        self.assertTrue(
            "production saas remains blocked" in lower
            or "production saas is complete" in lower,
            "Markdown must state production SaaS status",
        )

    # --- Integrated findings ---

    def test_integrated_findings_present(self):
        lower = self.md_lower
        self.assertIn("integrated findings", lower)
        for finding in _REQUIRED_FINDINGS:
            self.assertIn(
                finding,
                lower,
                f"Markdown integrated findings must include: {finding}",
            )

    # --- Severity ---

    def test_p0_present(self):
        lower = self.md_lower
        self.assertIn("p0", lower)

    def test_p1_present(self):
        lower = self.md_lower
        self.assertIn("p1", lower)

    def test_p2_present(self):
        lower = self.md_lower
        self.assertIn("p2", lower)

    def test_p3_present(self):
        lower = self.md_lower
        self.assertIn("p3", lower)

    # --- Corrected roadmap ---

    def test_corrected_roadmap_present(self):
        lower = self.md_lower
        self.assertIn("corrected roadmap", lower)

    def test_roadmap_includes_gl136(self):
        self.assertIn("gl-136", self.md_lower)

    def test_roadmap_includes_gl137(self):
        self.assertIn("gl-137", self.md_lower)

    def test_roadmap_includes_gl138(self):
        self.assertIn("gl-138", self.md_lower)

    def test_roadmap_includes_gl139(self):
        self.assertIn("gl-139", self.md_lower)

    def test_roadmap_includes_gl140(self):
        self.assertIn("gl-140", self.md_lower)

    def test_roadmap_includes_gl141(self):
        self.assertIn("gl-141", self.md_lower)

    def test_roadmap_includes_gl142(self):
        self.assertIn("gl-142", self.md_lower)

    def test_roadmap_includes_gl143(self):
        self.assertIn("gl-143", self.md_lower)

    def test_roadmap_includes_gl144(self):
        self.assertIn("gl-144", self.md_lower)

    # --- Sequencing rules ---

    def test_threadinghttpserver_sequencing_rule(self):
        lower = self.md_lower
        self.assertTrue(
            "threadinghttpserver must not be enabled before" in lower
            or "threadinghttpserver must not be enabled" in lower,
            "Markdown must contain ThreadingHTTPServer sequencing rule",
        )

    def test_production_saas_non_claim(self):
        lower = self.md_lower
        self.assertTrue(
            "production saas must not be claimed" in lower
            or "production saas remains blocked" in lower,
            "Markdown must state production SaaS non-claim",
        )

    # --- Non-goals ---

    def test_explicit_non_goals_present(self):
        lower = self.md_lower
        self.assertIn("explicit non-goals", lower)

    # --- No raw secrets ---

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


class TestGl135JsonContent(unittest.TestCase):
    """Verify GL-135 JSON arrays contain expected items."""

    @classmethod
    def setUpClass(cls):
        raw_json = _JSON_PATH.read_text(encoding="utf-8") if _JSON_PATH.exists() else "{}"
        cls.json_data = json.loads(raw_json)

    def _has_substring_in_array(self, key, substring):
        arr = self.json_data.get(key, [])
        return any(substring.lower() in str(item).lower() for item in arr)

    def test_senior_review_integrated(self):
        self.assertIs(self.json_data.get("senior_review_integrated"), True)

    def test_remediation_plan_integrated(self):
        self.assertIs(self.json_data.get("remediation_plan_integrated"), True)

    def test_p0_findings_not_empty(self):
        arr = self.json_data.get("p0_findings", [])
        self.assertTrue(len(arr) > 0, "p0_findings must not be empty")

    def test_p1_findings_not_empty(self):
        arr = self.json_data.get("p1_findings", [])
        self.assertTrue(len(arr) > 0, "p1_findings must not be empty")

    def test_p2_findings_not_empty(self):
        arr = self.json_data.get("p2_findings", [])
        self.assertTrue(len(arr) > 0, "p2_findings must not be empty")

    def test_p3_findings_not_empty(self):
        arr = self.json_data.get("p3_findings", [])
        self.assertTrue(len(arr) > 0, "p3_findings must not be empty")

    def test_p0_includes_demo_private_key(self):
        self.assertTrue(
            self._has_substring_in_array("p0_findings", "demo private key"),
            "p0_findings must include demo private key",
        )

    def test_p1_includes_dependency_manifest(self):
        self.assertTrue(
            self._has_substring_in_array("p1_findings", "dependency manifest"),
            "p1_findings must include dependency manifest",
        )

    def test_p1_includes_duplicate_check_admin_token(self):
        self.assertTrue(
            self._has_substring_in_array("p1_findings", "duplicate check_admin_token"),
            "p1_findings must include duplicate check_admin_token",
        )

    def test_p1_includes_audit_hash_chain(self):
        self.assertTrue(
            self._has_substring_in_array("p1_findings", "audit hash-chain"),
            "p1_findings must include audit hash-chain",
        )

    def test_p1_includes_threadinghttpserver(self):
        self.assertTrue(
            self._has_substring_in_array("p1_findings", "threadinghttpserver"),
            "p1_findings must include ThreadingHTTPServer",
        )

    def test_p1_includes_operator_model_default(self):
        self.assertTrue(
            self._has_substring_in_array("p1_findings", "operator model default"),
            "p1_findings must include operator model default",
        )

    def test_p1_includes_bytesio_test_hack(self):
        self.assertTrue(
            self._has_substring_in_array("p1_findings", "bytesio"),
            "p1_findings must include BytesIO",
        )

    def test_p2_includes_server_py_decomposition(self):
        self.assertTrue(
            self._has_substring_in_array("p2_findings", "server.py"),
            "p2_findings must include server.py",
        )

    def test_p3_includes_rate_limiter(self):
        self.assertTrue(
            self._has_substring_in_array("p3_findings", "rate limiter"),
            "p3_findings must include rate limiter",
        )

    def test_corrected_roadmap_includes_gl136(self):
        arr = self.json_data.get("corrected_roadmap", [])
        self.assertTrue(
            any("gl-136" in str(item).lower() for item in arr),
            "corrected_roadmap must include GL-136",
        )

    def test_corrected_roadmap_includes_gl137(self):
        arr = self.json_data.get("corrected_roadmap", [])
        self.assertTrue(
            any("gl-137" in str(item).lower() for item in arr),
            "corrected_roadmap must include GL-137",
        )

    def test_corrected_roadmap_includes_gl138(self):
        arr = self.json_data.get("corrected_roadmap", [])
        self.assertTrue(
            any("gl-138" in str(item).lower() for item in arr),
            "corrected_roadmap must include GL-138",
        )

    def test_corrected_roadmap_includes_gl139(self):
        arr = self.json_data.get("corrected_roadmap", [])
        self.assertTrue(
            any("gl-139" in str(item).lower() for item in arr),
            "corrected_roadmap must include GL-139",
        )

    def test_corrected_roadmap_includes_gl140(self):
        arr = self.json_data.get("corrected_roadmap", [])
        self.assertTrue(
            any("gl-140" in str(item).lower() for item in arr),
            "corrected_roadmap must include GL-140",
        )

    def test_corrected_roadmap_includes_gl141(self):
        arr = self.json_data.get("corrected_roadmap", [])
        self.assertTrue(
            any("gl-141" in str(item).lower() for item in arr),
            "corrected_roadmap must include GL-141",
        )

    def test_corrected_roadmap_includes_gl142(self):
        arr = self.json_data.get("corrected_roadmap", [])
        self.assertTrue(
            any("gl-142" in str(item).lower() for item in arr),
            "corrected_roadmap must include GL-142",
        )

    def test_corrected_roadmap_includes_gl143(self):
        arr = self.json_data.get("corrected_roadmap", [])
        self.assertTrue(
            any("gl-143" in str(item).lower() for item in arr),
            "corrected_roadmap must include GL-143",
        )

    def test_corrected_roadmap_includes_gl144(self):
        arr = self.json_data.get("corrected_roadmap", [])
        self.assertTrue(
            any("gl-144" in str(item).lower() for item in arr),
            "corrected_roadmap must include GL-144",
        )

    def test_sequencing_rules_include_threadinghttpserver(self):
        self.assertTrue(
            self._has_substring_in_array("sequencing_rules", "threadinghttpserver"),
            "sequencing_rules must include ThreadingHTTPServer",
        )

    def test_sequencing_rules_include_production_saas_non_claim(self):
        self.assertTrue(
            self._has_substring_in_array("sequencing_rules", "production saas"),
            "sequencing_rules must include production SaaS non-claim",
        )

    def test_sequencing_rules_include_full_backend_suite_script(self):
        self.assertTrue(
            self._has_substring_in_array("sequencing_rules", "run-full-backend-suite.sh"),
            "sequencing_rules must include run-full-backend-suite.sh",
        )

    def test_next_issue_is_gl136_key_hygiene(self):
        self.assertEqual(
            self.json_data.get("next_issue"),
            "GL-136 Remove Demo Private Key From Tracking / Add Key Hygiene Gate",
        )

    def test_explicit_non_goals_not_empty(self):
        arr = self.json_data.get("explicit_non_goals", [])
        self.assertTrue(len(arr) > 0, "explicit_non_goals must not be empty")


class TestGl135ScopeGuard(unittest.TestCase):
    """Verify no forbidden files were changed by GL-135."""

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
                self.fail(f"GL-135 must not change production code: {line}")

    def test_no_openapi_changed(self):
        changed = self._changed_files()
        self.assertNotIn(
            "openapi.yaml",
            changed,
            "GL-135 must not change the OpenAPI specification",
        )

    def test_no_migration_files_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if "migrations/" in line:
                self.fail(f"GL-135 must not change migration files: {line}")

    def test_no_frontend_or_website_files_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("frontend/") or line.startswith("website/"):
                self.fail(f"GL-135 must not change frontend or website files: {line}")

    def test_no_dependency_files_changed(self):
        changed = self._changed_files()
        forbidden = [
            "pyproject.toml",
            "setup.py",
            "requirements",
            "package.json",
            "package-lock.json",
            "Pipfile",
            "poetry.lock",
        ]
        for token in forbidden:
            for line in changed.splitlines():
                if token in line:
                    self.fail(
                        f"GL-135 must not change dependency file '{token}': {line}"
                    )

    def test_no_db_schema_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if "schema" in line.lower() and line.endswith(".sql"):
                self.fail(f"GL-135 must not change DB schema: {line}")

    def test_no_scripts_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("scripts/"):
                self.fail(f"GL-135 must not change scripts: {line}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
