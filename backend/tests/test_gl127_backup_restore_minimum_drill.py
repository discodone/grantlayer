"""Tests for GL-127: Backup / Restore Minimum Drill.

Ensures:
- scripts/run-backup-restore-drill.sh exists and is well-formed.
- Script uses safe bash settings, resolves repo root, and runs GL-127 tests.
- Script preserves exit codes and does not hide failures.
- Script does not perform real backup/restore or require external services.
- Script does not print secrets.
- docs/backup_restore_minimum_drill.md exists and covers required topics.
- No forbidden files are changed.

No production code changes required.
No external services required.
No real backup/restore operations performed.
"""

import os
import pathlib
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


class TestGl127ScriptContract(unittest.TestCase):
    """Verify the backup/restore drill runner script meets its contract."""

    @classmethod
    def setUpClass(cls):
        cls.script_path = _REPO_ROOT / "scripts" / "run-backup-restore-drill.sh"
        cls.script_text = cls.script_path.read_text() if cls.script_path.exists() else ""

    def test_script_exists(self):
        self.assertTrue(
            self.script_path.exists(),
            "run-backup-restore-drill.sh must exist",
        )

    def test_script_is_executable(self):
        self.assertTrue(
            os.access(self.script_path, os.X_OK),
            "run-backup-restore-drill.sh must be executable",
        )

    def test_script_has_shebang(self):
        lines = self.script_text.splitlines()
        self.assertTrue(lines, "Script must not be empty")
        self.assertTrue(
            lines[0].startswith("#!/usr/bin/env bash"),
            f"Expected bash shebang, got: {lines[0]}",
        )

    def test_script_uses_strict_mode(self):
        self.assertIn("set -euo pipefail", self.script_text)

    def test_script_resolves_repo_root(self):
        self.assertIn("REPO_ROOT", self.script_text)

    def test_script_runs_gl127_test_module(self):
        self.assertIn(
            "python3 -m unittest backend.tests.test_gl127_backup_restore_minimum_drill -v",
            self.script_text,
        )

    def test_script_preserves_exit_code(self):
        self.assertIn("EXIT_CODE=", self.script_text)
        self.assertIn('exit "${EXIT_CODE}"', self.script_text)

    def test_script_avoids_tail_grep_head_as_sole_validation(self):
        for bad in ["| tail", "| grep", "| head"]:
            self.assertNotIn(
                bad,
                self.script_text,
                f"Script must not pipe unittest output through {bad} as sole validation",
            )

    def test_script_does_not_invoke_external_backup_tools(self):
        forbidden = ["pg_dump", "psql", "rm -rf", "aws ", "gcloud ", "az "]
        lower = self.script_text.lower()
        for tool in forbidden:
            self.assertNotIn(tool, lower, f"Script must not invoke external backup tool: {tool}")

    def test_script_does_not_print_secrets(self):
        forbidden_patterns = [
            r"password\s*=\s*[^\s]",
            r"secret\s*=\s*[^\s]",
            r"api_key\s*=\s*[^\s]",
            r"token\s*=\s*[^\s]",
            r"private_key\s*=\s*[^\s]",
            r"passphrase\s*=\s*[^\s]",
        ]
        for pattern in forbidden_patterns:
            for line in self.script_text.splitlines():
                if re.search(pattern, line, re.IGNORECASE):
                    self.fail(f"Possible secret assignment in script line: {line}")

    def test_script_no_production_hosts(self):
        forbidden_hosts = ["prod.", "grantlayer.io", "api.grantlayer"]
        lower = self.script_text.lower()
        for host in forbidden_hosts:
            self.assertNotIn(host, lower, f"Script must not reference production host: {host}")


class TestGl127DocumentationContract(unittest.TestCase):
    """Verify the backup/restore drill documentation exists and covers required topics."""

    @classmethod
    def setUpClass(cls):
        cls.docs_path = _REPO_ROOT / "docs" / "backup_restore_minimum_drill.md"
        cls.docs_text = cls.docs_path.read_text() if cls.docs_path.exists() else ""

    def test_docs_exist(self):
        self.assertTrue(
            self.docs_path.exists(),
            "docs/backup_restore_minimum_drill.md must exist",
        )

    def test_docs_list_critical_data_categories(self):
        lower = self.docs_text.lower()
        categories = [
            "grants",
            "grant requests",
            "grant executions",
            "evidence",
            "audit events",
            "provenance",
            "approvals",
            "compliance",
            "policy",
            "operators",
            "runtime configuration",
        ]
        for cat in categories:
            self.assertIn(cat, lower, f"Docs must mention critical data category: {cat}")

    def test_docs_document_sqlite_local_backup(self):
        lower = self.docs_text.lower()
        self.assertIn("sqlite", lower)
        self.assertIn("local", lower)
        self.assertIn("snapshot", lower)

    def test_docs_document_postgres_production_backup(self):
        lower = self.docs_text.lower()
        self.assertIn("pg_dump", lower)
        self.assertIn("managed database snapshot", lower)

    def test_docs_document_isolated_restore_environment(self):
        lower = self.docs_text.lower()
        self.assertIn("isolated environment", lower)

    def test_docs_document_schema_migration_compatibility(self):
        lower = self.docs_text.lower()
        self.assertIn("schema", lower)
        self.assertIn("migration", lower)
        self.assertIn("compatibility", lower)

    def test_docs_document_audit_immutability_expectations(self):
        lower = self.docs_text.lower()
        self.assertIn("immutability", lower)
        self.assertIn("update", lower)
        self.assertIn("delete", lower)

    def test_docs_document_hash_chain_row_hash_prev_hash(self):
        lower = self.docs_text.lower()
        self.assertIn("row_hash", lower)
        self.assertIn("prev_hash", lower)
        self.assertIn("hashchain", lower.lower().replace("-", ""))

    def test_docs_document_go_no_go_criteria(self):
        lower = self.docs_text.lower()
        self.assertIn("go/no-go", lower)
        self.assertIn("no-go", lower)

    def test_docs_reference_runtime_gate_command(self):
        lower = self.docs_text.lower()
        self.assertIn("run-production-runtime-gate", lower)

    def test_docs_reference_smoke_command(self):
        lower = self.docs_text.lower()
        self.assertIn("run-operational-smoke-tests", lower)

    def test_docs_reference_full_suite_command(self):
        lower = self.docs_text.lower()
        self.assertIn("run-full-backend-suite", lower)

    def test_docs_reference_drill_command(self):
        lower = self.docs_text.lower()
        self.assertIn("run-backup-restore-drill", lower)

    def test_docs_state_secrets_must_not_be_printed(self):
        lower = self.docs_text.lower()
        self.assertIn("never print", lower)
        self.assertIn("secret", lower)

    def test_docs_do_not_contain_raw_secret_examples(self):
        forbidden_patterns = [
            r"\bpassword\s*=\s*[^\s]",
            r"\bsecret\s*=\s*[^\s]",
            r"\bapi_key\s*=\s*[^\s]",
            r"\btoken\s*=\s*[^\s]",
            r"\bprivate_key\s*=\s*[^\s]",
            r"\bpassphrase\s*=\s*[^\s]",
        ]
        for pattern in forbidden_patterns:
            for line in self.docs_text.splitlines():
                if re.search(pattern, line, re.IGNORECASE):
                    self.fail(f"Docs must not contain raw secret example: {line}")


class TestGl127ScopeGuard(unittest.TestCase):
    """Verify no forbidden files were changed by GL-127."""

    def _changed_files(self):
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        return result.stdout.strip()

    def test_no_production_code_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("backend/src/"):
                self.fail(f"GL-127 changed production code: {line}")

    def test_no_openapi_changed(self):
        changed = self._changed_files()
        self.assertNotIn("openapi.yaml", changed)

    def test_no_migration_changed(self):
        changed = self._changed_files()
        self.assertNotIn("migrations/", changed)

    def test_no_frontend_or_website_changed(self):
        changed = self._changed_files()
        self.assertNotIn("frontend/", changed)
        self.assertNotIn("website/", changed)

    def test_no_dependency_file_changed(self):
        changed = self._changed_files()
        self.assertNotIn("pyproject.toml", changed)
        self.assertNotIn("requirements", changed)
        self.assertNotIn("package.json", changed)
        self.assertNotIn("package-lock.json", changed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
