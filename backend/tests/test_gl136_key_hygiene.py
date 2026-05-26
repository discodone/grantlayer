"""GL-136 — Key Hygiene Gate.

Validates:
- No tracked files contain obvious private-key PEM markers.
- .gitignore covers key/secret/cert patterns.
- docs/key_hygiene.md exists and covers required topics.
- docs/examples/gl136/key_hygiene.json exists and is valid.
- Scope guard: no forbidden file changes on this branch.
"""

import json
import os
import pathlib
import subprocess
import sys
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


class TestGl136NoTrackedPrivateKeys(unittest.TestCase):
    """Fail if tracked files contain obvious PEM private key markers."""

    FORBIDDEN_MARKERS = [
        "-----BEGIN PRIVATE KEY-----",
        "-----BEGIN RSA PRIVATE KEY-----",
        "-----BEGIN EC PRIVATE KEY-----",
        "-----BEGIN OPENSSH PRIVATE KEY-----",
        "-----BEGIN DSA PRIVATE KEY-----",
    ]

    def test_tracked_files_contain_no_pem_private_key_markers(self):
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
        )
        files = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        # Exclude GL-136 gate files that legitimately document forbidden markers
        excluded = {
            "backend/tests/test_gl136_key_hygiene.py",
            "docs/examples/gl136/key_hygiene.json",
        }
        hits = []
        for name in files:
            if name in excluded:
                continue
            p = _REPO_ROOT / name
            try:
                if p.is_dir():
                    continue
                data = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if any(marker in data for marker in self.FORBIDDEN_MARKERS):
                hits.append(name)
        if hits:
            self.fail(
                f"Tracked files contain forbidden PEM private key markers: {hits}"
            )


class TestGl136GitignoreCoverage(unittest.TestCase):
    """Validate .gitignore includes required key hygiene patterns."""

    REQUIRED_PATTERNS = [
        "*.pem",
        "*.key",
        "*.p8",
        "*.p12",
        "*.crt",
        "*.cert",
        "*.csr",
        ".env",
        ".env.*",
        "!.env.example",
        "secrets/",
        "private/",
        "keys/",
        "certs/",
    ]

    def setUp(self):
        gitignore_path = _REPO_ROOT / ".gitignore"
        self.gitignore_text = (
            gitignore_path.read_text(encoding="utf-8")
            if gitignore_path.exists()
            else ""
        )

    def test_gitignore_exists(self):
        self.assertTrue(
            (_REPO_ROOT / ".gitignore").exists(),
            ".gitignore must exist",
        )

    def test_gitignore_covers_required_patterns(self):
        lines = [ln.strip() for ln in self.gitignore_text.splitlines()]
        for pattern in self.REQUIRED_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertIn(
                    pattern,
                    lines,
                    f".gitignore must contain pattern: {pattern}",
                )


class TestGl136DocumentationContract(unittest.TestCase):
    """Validate docs/key_hygiene.md exists and covers required topics."""

    def setUp(self):
        docs_path = _REPO_ROOT / "docs" / "key_hygiene.md"
        self.docs_text = docs_path.read_text(encoding="utf-8") if docs_path.exists() else ""

    def test_docs_exist(self):
        self.assertTrue(
            (_REPO_ROOT / "docs" / "key_hygiene.md").exists(),
            "docs/key_hygiene.md must exist",
        )

    def test_docs_mention_gl136(self):
        lower = self.docs_text.lower()
        self.assertIn("gl-136", lower)

    def test_docs_say_no_history_rewrite(self):
        lower = self.docs_text.lower()
        self.assertIn("does not rewrite git history", lower)

    def test_docs_say_no_force_push(self):
        lower = self.docs_text.lower()
        self.assertIn("no force push", lower)

    def test_docs_say_no_private_keys_in_git(self):
        lower = self.docs_text.lower()
        self.assertIn("no private keys in git", lower)

    def test_docs_say_public_github_blocked_if_gate_fails(self):
        lower = self.docs_text.lower()
        self.assertIn("public github", lower)
        self.assertIn("blocked", lower)
        self.assertIn("gate fails", lower)


class TestGl136JsonArtifact(unittest.TestCase):
    """Validate the JSON artifact exists, is valid, and contains required fields."""

    def setUp(self):
        self.json_path = _REPO_ROOT / "docs" / "examples" / "gl136" / "key_hygiene.json"
        self.data = None
        if self.json_path.exists():
            with open(self.json_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)

    def test_json_exists(self):
        self.assertTrue(self.json_path.exists(), "JSON artifact must exist")

    def test_json_is_valid(self):
        self.assertIsNotNone(self.data, "JSON must parse successfully")

    def test_json_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-136")

    def test_json_git_history_rewritten_is_false(self):
        self.assertIs(self.data.get("git_history_rewritten"), False)

    def test_json_force_push_used_is_false(self):
        self.assertIs(self.data.get("force_push_used"), False)

    def test_json_real_secrets_added_is_false(self):
        self.assertIs(self.data.get("real_secrets_added"), False)

    def test_json_private_key_patterns_guarded_is_true(self):
        self.assertIs(self.data.get("private_key_patterns_guarded"), True)

    def test_json_next_issue(self):
        self.assertEqual(
            self.data.get("next_issue"),
            "GL-137 Add Python Dependency Manifest",
        )


class TestGl136ScopeGuard(unittest.TestCase):
    """Verify no forbidden files were changed by GL-136."""

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

    def test_no_dependency_file_change(self):
        changed = self._changed_files()
        self.assertNotIn("pyproject.toml", changed)
        self.assertNotIn("requirements.txt", changed)
        self.assertNotIn("requirements-dev.txt", changed)
        self.assertNotIn("setup.py", changed)
        self.assertNotIn("Pipfile", changed)
        self.assertNotIn("poetry.lock", changed)
        self.assertNotIn("package.json", changed)
        self.assertNotIn("package-lock.json", changed)

    def test_no_db_schema_change(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if "schema" in line.lower() and line.endswith(".sql"):
                self.fail(f"GL-136 must not change DB schema: {line}")

    def test_branch_diff_limited_to_allowed_files(self):
        branch = self._branch_name()
        if branch != "gl-136-key-hygiene":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-136 feature branch"
            )
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            ".gitignore",
            "docs/key_hygiene.md",
            "docs/examples/gl136/key_hygiene.json",
            "backend/tests/test_gl136_key_hygiene.py",
            "backend/tests/test_gl045b_security_secrets_regression.py",
            "backend/tests/test_gl076_runtime_configuration_enforcement.py",
            "backend/tests/test_gl078_structured_logging_correlation_helper.py",
            "backend/tests/test_gl126_production_runtime_gate.py",
            "docs/examples/gl078/structured_logging_examples.json",
            "docs/security_remediation_intake_2026_05_26.md",
            "docs/production_hardening_roadmap.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-136 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
