"""GL-137 — Dependency Manifest Gate.

Validates:
- requirements.txt and requirements-dev.txt exist and have correct structure.
- docs/dependency_manifest.md exists and covers required topics.
- docs/examples/gl137/dependency_manifest.json exists, is valid, and has required fields.
- Manifests/docs/json contain no obvious secrets.
- Manifests do not list stdlib-only modules.
- Manifests include discovered runtime non-stdlib dependencies.
- Scope guard: no forbidden file changes on this branch.
- Branch-scope guard: skips branch diff assertions when not on the feature branch.
"""

import json
import os
import pathlib
import subprocess
import sys
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


class TestGl137ManifestFilesExist(unittest.TestCase):
    """Core file existence and structure checks."""

    def test_requirements_txt_exists(self):
        self.assertTrue(
            (_REPO_ROOT / "requirements.txt").exists(),
            "requirements.txt must exist",
        )

    def test_requirements_dev_txt_exists(self):
        self.assertTrue(
            (_REPO_ROOT / "requirements-dev.txt").exists(),
            "requirements-dev.txt must exist",
        )

    def test_requirements_dev_includes_runtime_manifest(self):
        text = (_REPO_ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
        self.assertIn("-r requirements.txt", text)

    def test_docs_dependency_manifest_exists(self):
        self.assertTrue(
            (_REPO_ROOT / "docs" / "dependency_manifest.md").exists(),
            "docs/dependency_manifest.md must exist",
        )

    def test_json_artifact_exists(self):
        self.assertTrue(
            (_REPO_ROOT / "docs" / "examples" / "gl137" / "dependency_manifest.json").exists(),
            "JSON artifact must exist",
        )


class TestGl137JsonArtifact(unittest.TestCase):
    """Validate JSON artifact content."""

    def setUp(self):
        self.json_path = (
            _REPO_ROOT / "docs" / "examples" / "gl137" / "dependency_manifest.json"
        )
        self.data = None
        if self.json_path.exists():
            with open(self.json_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)

    def test_json_is_valid(self):
        self.assertIsNotNone(self.data, "JSON must parse successfully")

    def test_json_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-137")

    def test_json_runtime_manifest_added(self):
        self.assertIs(self.data.get("runtime_manifest_added"), True)

    def test_json_dev_manifest_added(self):
        self.assertIs(self.data.get("dev_manifest_added"), True)

    def test_json_production_code_changed_false(self):
        self.assertIs(self.data.get("production_code_changed"), False)

    def test_json_package_published_false(self):
        self.assertIs(self.data.get("package_published"), False)

    def test_json_pyproject_added_false(self):
        self.assertIs(self.data.get("pyproject_added"), False)

    def test_json_dependencies_vendored_false(self):
        self.assertIs(self.data.get("dependencies_vendored"), False)

    def test_json_secrets_added_false(self):
        self.assertIs(self.data.get("secrets_added"), False)

    def test_json_public_github_readiness_improved_true(self):
        self.assertIs(self.data.get("public_github_readiness_improved"), True)

    def test_json_developer_setup_documented_true(self):
        self.assertIs(self.data.get("developer_setup_documented"), True)

    def test_json_next_issue(self):
        self.assertEqual(
            self.data.get("next_issue"),
            "GL-138 Remove Duplicate check_admin_token Stub",
        )


class TestGl137DocumentationContract(unittest.TestCase):
    """Validate docs/dependency_manifest.md covers required topics."""

    def setUp(self):
        docs_path = _REPO_ROOT / "docs" / "dependency_manifest.md"
        self.docs_text = docs_path.read_text(encoding="utf-8") if docs_path.exists() else ""

    def test_docs_exist(self):
        self.assertTrue(
            (_REPO_ROOT / "docs" / "dependency_manifest.md").exists(),
            "docs/dependency_manifest.md must exist",
        )

    def test_docs_mention_public_github_readiness(self):
        lower = self.docs_text.lower()
        self.assertIn("public github", lower)
        self.assertIn("readiness", lower)

    def test_docs_say_no_package_publishing(self):
        lower = self.docs_text.lower()
        self.assertIn("no package publishing", lower)

    def test_docs_mention_next_issue_gl138(self):
        lower = self.docs_text.lower()
        self.assertIn("gl-138", lower)
        self.assertIn("check_admin_token", lower)


class TestGl137NoSecretsInManifests(unittest.TestCase):
    """Ensure dependency manifests and docs contain no obvious secrets."""

    FORBIDDEN_SUBSTRINGS = [
        "BEGIN PRIVATE KEY",
        "password=",
        "token=",
        "secret=",
        "api_key=",
    ]

    def _manifest_and_doc_paths(self):
        return [
            _REPO_ROOT / "requirements.txt",
            _REPO_ROOT / "requirements-dev.txt",
            _REPO_ROOT / "docs" / "dependency_manifest.md",
            _REPO_ROOT / "docs" / "examples" / "gl137" / "dependency_manifest.json",
        ]

    def test_no_obvious_secrets_in_manifests(self):
        for path in self._manifest_and_doc_paths():
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for sub in self.FORBIDDEN_SUBSTRINGS:
                with self.subTest(file=path.name, substring=sub):
                    self.assertNotIn(
                        sub,
                        text,
                        f"{path.name} must not contain '{sub}'",
                    )


class TestGl137ManifestContentQuality(unittest.TestCase):
    """Ensure runtime manifest lists actual non-stdlib deps and not stdlib-only modules."""

    STDLIB_MODULES = {
        "os", "sys", "json", "sqlite3", "unittest", "re", "datetime",
        "time", "hashlib", "hmac", "base64", "uuid", "pathlib", "logging",
        "io", "tempfile", "subprocess", "threading", "inspect", "copy",
        "functools", "collections", "typing", "dataclasses", "enum",
        "warnings", "importlib", "ast", "stat", "numbers", "decimal",
        "fractions", "abc", "contextlib", "string", "random", "secrets",
        "binascii", "csv", "html", "xml", "http", "urllib", "email",
        "calendar", "unitest",
    }

    REQUIRED_RUNTIME_DEPS = {
        "cryptography",
        "psycopg2-binary",
    }

    def test_no_stdlib_modules_in_requirements_txt(self):
        text = (_REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
        for line in lines:
            # Extract package name (strip version specifiers)
            pkg = line.split("=")[0].split("<")[0].split(">")[0].split("[")[0].strip().lower()
            with self.subTest(package=pkg):
                self.assertNotIn(
                    pkg,
                    self.STDLIB_MODULES,
                    f"requirements.txt must not list stdlib module: {pkg}",
                )

    def test_runtime_dependencies_present(self):
        """Assert that discovered runtime non-stdlib deps are listed."""
        text = (_REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
        lines = [ln.strip().lower() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
        for required in self.REQUIRED_RUNTIME_DEPS:
            found = any(required.lower() in line for line in lines)
            with self.subTest(required=required):
                self.assertTrue(
                    found,
                    f"requirements.txt must include runtime dependency: {required}",
                )


class TestGl137ScopeGuard(unittest.TestCase):
    """Verify no forbidden files were changed by GL-137."""

    def _changed_files(self):
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        return result.stdout.strip()

    def _branch_name(self):
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        return result.stdout.strip()

    def test_no_backend_src_changes(self):
        changed = self._changed_files()
        self.assertNotIn("backend/src/", changed)

    def test_no_openapi_change(self):
        changed = self._changed_files()
        self.assertNotIn("openapi.yaml", changed)

    def test_no_migration_change(self):
        changed = self._changed_files()
        self.assertNotIn("migrations/", changed)

    def test_no_frontend_or_website_change(self):
        changed = self._changed_files()
        self.assertNotIn("frontend/", changed)
        self.assertNotIn("website/", changed)

    def test_no_db_schema_change(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if "schema" in line.lower() and line.endswith(".sql"):
                self.fail(f"GL-137 must not change DB schema: {line}")

    def test_no_scripts_changed(self):
        changed = self._changed_files()
        self.assertNotIn("scripts/", changed)

    def test_branch_diff_limited_to_allowed_files(self):
        branch = self._branch_name()
        if branch != "gl-137-dependency-manifest":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-137 feature branch"
            )
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "requirements.txt",
            "requirements-dev.txt",
            "docs/dependency_manifest.md",
            "docs/examples/gl137/dependency_manifest.json",
            "backend/tests/test_gl137_dependency_manifest.py",
            "README.md",
            "docs/external_security_review_preparation.md",
            "docs/key_hygiene.md",
            "docs/production_hardening_roadmap.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-137 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
