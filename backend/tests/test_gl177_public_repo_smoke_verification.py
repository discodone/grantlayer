"""
GL-177: Public Repo Smoke Verification — validation tests.
"""
import json
import os
import subprocess
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MARKDOWN_PATH = os.path.join(REPO_ROOT, "docs", "public_repo_smoke_verification.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl177",
    "public_repo_smoke_verification.json",
)

VALID_SMOKE_DECISIONS = {
    "public_repo_smoke_passed",
    "public_repo_smoke_passed_with_cautions",
    "public_repo_smoke_blocked",
}

FORBIDDEN_PREFIXES = [
    "backend/src/",
    "openapi",
    "migrations/",
    "requirements",
    "package.json",
    "package-lock.json",
    "frontend/",
    "website/",
    ".github/workflows/",
]


class TestGL177ArtifactFilesExist(unittest.TestCase):
    def test_markdown_exists(self):
        self.assertTrue(
            os.path.isfile(MARKDOWN_PATH),
            f"GL-177 smoke report markdown not found: {MARKDOWN_PATH}",
        )

    def test_json_exists(self):
        self.assertTrue(
            os.path.isfile(JSON_PATH),
            f"GL-177 smoke report JSON not found: {JSON_PATH}",
        )


class TestGL177ArtifactJSON(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(JSON_PATH, encoding="utf-8") as f:
            cls.data = json.load(f)

    def test_valid_json(self):
        self.assertIsInstance(self.data, dict)

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-177")

    def test_public_repository_url(self):
        self.assertEqual(
            self.data.get("public_repository_url"),
            "https://github.com/Discodone/grantlayer.git",
        )

    def test_expected_public_commit(self):
        self.assertEqual(
            self.data.get("expected_public_commit"),
            "e4cd080df9d8da7d7cf4044e84eea4df8ac80cc6",
        )

    def test_previous_public_commit(self):
        self.assertEqual(
            self.data.get("previous_public_commit"),
            "8bf6c335af4f1229dd752e939ec5b0e5a6928bad",
        )

    def test_actual_public_clone_head_present(self):
        head = self.data.get("actual_public_clone_head", "")
        self.assertIsInstance(head, str)
        self.assertGreater(len(head), 0, "actual_public_clone_head must be non-empty")

    def test_smoke_decision_valid(self):
        decision = self.data.get("smoke_decision")
        self.assertIn(
            decision,
            VALID_SMOKE_DECISIONS,
            f"smoke_decision '{decision}' must be one of {VALID_SMOKE_DECISIONS}",
        )

    def test_public_correction_verification_exists(self):
        pcv = self.data.get("public_correction_verification")
        self.assertIsInstance(pcv, dict, "public_correction_verification must be a dict")

    def test_public_correction_includes_corrected_files(self):
        pcv = self.data.get("public_correction_verification", {})
        self.assertIn(
            "corrected_files_checked",
            pcv,
            "public_correction_verification must include corrected_files_checked",
        )
        self.assertIsInstance(pcv["corrected_files_checked"], list)
        self.assertGreater(len(pcv["corrected_files_checked"]), 0)

    def test_public_correction_old_internal_labels_absent_field(self):
        pcv = self.data.get("public_correction_verification", {})
        self.assertIn(
            "old_internal_labels_absent",
            pcv,
            "public_correction_verification must include old_internal_labels_absent",
        )

    def test_if_internal_labels_present_smoke_not_passed(self):
        pcv = self.data.get("public_correction_verification", {})
        labels_absent = pcv.get("old_internal_labels_absent", True)
        if not labels_absent:
            decision = self.data.get("smoke_decision", "")
            self.assertNotEqual(
                decision,
                "public_repo_smoke_passed",
                "if old internal labels are present, smoke_decision must not be public_repo_smoke_passed",
            )

    def test_first_verifiable_output_exists(self):
        fvo = self.data.get("first_verifiable_output")
        self.assertIsInstance(fvo, dict, "first_verifiable_output must be a dict")

    def test_first_verifiable_output_fields(self):
        fvo = self.data.get("first_verifiable_output", {})
        for field in ("command", "exit_code", "generated_output_path", "expected_output_path", "deterministic_match"):
            self.assertIn(
                field,
                fvo,
                f"first_verifiable_output must include field: {field}",
            )

    def test_if_deterministic_match_false_smoke_not_passed(self):
        fvo = self.data.get("first_verifiable_output", {})
        match = fvo.get("deterministic_match", True)
        if not match:
            decision = self.data.get("smoke_decision", "")
            self.assertNotEqual(
                decision,
                "public_repo_smoke_passed",
                "if first_verifiable_output.deterministic_match is false, smoke_decision must not be public_repo_smoke_passed",
            )

    def test_private_data_secret_smoke_exists(self):
        pdss = self.data.get("private_data_secret_smoke")
        self.assertIsInstance(pdss, dict, "private_data_secret_smoke must be a dict")

    def test_private_data_secret_smoke_scan_scope(self):
        pdss = self.data.get("private_data_secret_smoke", {})
        self.assertIn(
            "scan_scope",
            pdss,
            "private_data_secret_smoke must include scan_scope",
        )

    def test_private_data_secret_smoke_checks_performed(self):
        pdss = self.data.get("private_data_secret_smoke", {})
        self.assertIn(
            "checks_performed",
            pdss,
            "private_data_secret_smoke must include checks_performed",
        )

    def test_private_data_secret_smoke_private_data_found(self):
        pdss = self.data.get("private_data_secret_smoke", {})
        self.assertIn(
            "private_data_found",
            pdss,
            "private_data_secret_smoke must state whether private data was found",
        )

    def test_private_data_secret_smoke_secret_material_found(self):
        pdss = self.data.get("private_data_secret_smoke", {})
        self.assertIn(
            "secret_material_found",
            pdss,
            "private_data_secret_smoke must state whether secret material was found",
        )

    def test_private_data_secret_smoke_internal_infrastructure_found(self):
        pdss = self.data.get("private_data_secret_smoke", {})
        self.assertIn(
            "internal_infrastructure_found",
            pdss,
            "private_data_secret_smoke must state whether internal infrastructure was found",
        )

    def test_if_blockers_found_smoke_must_be_blocked(self):
        pdss = self.data.get("private_data_secret_smoke", {})
        blockers = pdss.get("blockers_found", False)
        if blockers:
            decision = self.data.get("smoke_decision", "")
            self.assertEqual(
                decision,
                "public_repo_smoke_blocked",
                "if private_data_secret_smoke.blockers_found is true, smoke_decision must be public_repo_smoke_blocked",
            )

    def test_findings_structure(self):
        findings = self.data.get("findings", [])
        self.assertIsInstance(findings, list)
        for finding in findings:
            for field in ("severity", "status", "recommendation", "blocking"):
                self.assertIn(
                    field,
                    finding,
                    f"each finding must include field '{field}', missing in: {finding.get('id', '?')}",
                )

    def test_finding_counts_match_findings(self):
        findings = self.data.get("findings", [])
        counts = self.data.get("finding_counts_by_severity", {})
        actual_counts = {}
        for finding in findings:
            sev = finding.get("severity", "unknown")
            actual_counts[sev] = actual_counts.get(sev, 0) + 1
        for sev, count in actual_counts.items():
            self.assertEqual(
                counts.get(sev, 0),
                count,
                f"finding_counts_by_severity['{sev}'] = {counts.get(sev, 0)} but found {count} findings with that severity",
            )

    def test_finding_counts_total(self):
        findings = self.data.get("findings", [])
        counts = self.data.get("finding_counts_by_severity", {})
        total = counts.get("total", -1)
        self.assertEqual(
            total,
            len(findings),
            f"finding_counts_by_severity.total = {total} but there are {len(findings)} findings",
        )

    def test_non_goals_present(self):
        non_goals = self.data.get("non_goals", [])
        self.assertIsInstance(non_goals, list)
        self.assertGreater(len(non_goals), 0)

    def test_non_goals_no_github_push(self):
        non_goals = self.data.get("non_goals", [])
        text = " ".join(non_goals).lower()
        self.assertIn(
            "no github push",
            text,
            "non_goals must confirm no GitHub push was performed",
        )

    def test_non_goals_no_visibility_change(self):
        non_goals = self.data.get("non_goals", [])
        text = " ".join(non_goals).lower()
        self.assertIn(
            "no visibility change",
            text,
            "non_goals must confirm no visibility change was performed",
        )

    def test_non_goals_internal_repo_not_pushed_directly(self):
        non_goals = self.data.get("non_goals", [])
        text = " ".join(non_goals).lower()
        self.assertIn(
            "internal repo was not pushed directly to github",
            text,
            "non_goals must confirm internal repo was not pushed directly to GitHub",
        )

    def test_no_backend_src_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertFalse(
                f.startswith("backend/src/"),
                f"changed_files must not include backend/src changes: {f}",
            )

    def test_no_openapi_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertFalse(
                "openapi" in f.lower(),
                f"changed_files must not include OpenAPI changes: {f}",
            )

    def test_no_migration_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertFalse(
                f.startswith("migrations/"),
                f"changed_files must not include migration changes: {f}",
            )

    def test_no_dependency_manifests_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            for prefix in ("requirements", "package.json", "package-lock.json"):
                self.assertFalse(
                    f.startswith(prefix),
                    f"changed_files must not include dependency manifest changes: {f}",
                )

    def test_no_sdk_implementation_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            if f.startswith("sdk/") and not f.startswith("sdk/python/README"):
                self.assertFalse(
                    f.endswith(".py") and "test" not in f.lower(),
                    f"changed_files must not include SDK implementation changes: {f}",
                )

    def test_no_github_workflow_changes_in_changed_files(self):
        changed = self.data.get("changed_files", [])
        for f in changed:
            self.assertFalse(
                f.startswith(".github/workflows/"),
                f"changed_files must not include GitHub workflow changes: {f}",
            )

    def test_no_forbidden_patterns_in_artifact(self):
        text = json.dumps(self.data)
        forbidden = [
            "forge.hofercloud.eu",
            "terminal.hofercloud.eu",
            "192.168.2.",
            "100.109.111.",
            "tapWjoj8",
        ]
        for pattern in forbidden:
            self.assertNotIn(
                pattern,
                text,
                f"forbidden pattern '{pattern}' found in GL-177 JSON artifact",
            )


class TestGL177MarkdownContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(MARKDOWN_PATH, encoding="utf-8") as f:
            cls.content = f.read()

    def test_must_reference_issue_id(self):
        self.assertIn("GL-177", self.content)

    def test_must_include_public_repository_url(self):
        self.assertIn("https://github.com/Discodone/grantlayer.git", self.content)

    def test_must_include_expected_public_commit(self):
        self.assertIn("e4cd080df9d8da7d7cf4044e84eea4df8ac80cc6", self.content)

    def test_must_include_previous_public_commit(self):
        self.assertIn("8bf6c335af4f1229dd752e939ec5b0e5a6928bad", self.content)

    def test_must_include_fresh_clone_path(self):
        self.assertIn("/tmp/grantlayer-public-smoke-gl177", self.content)

    def test_must_state_no_github_push(self):
        self.assertIn("No GitHub push performed", self.content)

    def test_must_state_no_visibility_change(self):
        self.assertIn("No visibility change performed", self.content)

    def test_must_state_internal_repo_not_pushed_directly(self):
        self.assertIn("Internal repo was not pushed directly to GitHub", self.content)

    def test_must_state_no_backend_src_changes(self):
        self.assertIn("backend/src", self.content)

    def test_must_state_no_openapi_changes(self):
        lower = self.content.lower()
        self.assertIn("openapi", lower)

    def test_must_include_smoke_decision(self):
        valid_decisions = [
            "public_repo_smoke_passed",
            "public_repo_smoke_passed_with_cautions",
            "public_repo_smoke_blocked",
        ]
        self.assertTrue(
            any(d in self.content for d in valid_decisions),
            "markdown must reference a valid smoke decision",
        )

    def test_must_include_private_data_result(self):
        self.assertIn("private", self.content.lower())
        self.assertIn("blocker", self.content.lower())

    def test_must_not_claim_tenant_isolation_implemented(self):
        self.assertNotIn("tenant isolation implemented", self.content.lower())
        self.assertNotIn("tenant isolation is implemented", self.content.lower())

    def test_must_not_claim_production_saas(self):
        self.assertNotIn("production saas ready", self.content.lower())
        self.assertNotIn("production-ready saas", self.content.lower())

    def test_no_forbidden_patterns_in_markdown(self):
        forbidden = [
            "forge.hofercloud.eu",
            "terminal.hofercloud.eu",
            "192.168.2.",
            "100.109.111.",
            "tapWjoj8",
        ]
        for pattern in forbidden:
            self.assertNotIn(
                pattern,
                self.content,
                f"forbidden pattern '{pattern}' found in GL-177 markdown",
            )

    def test_must_include_first_verifiable_output_result(self):
        self.assertIn("first_verifiable_output", self.content.lower().replace(" ", "_"))

    def test_must_include_findings_table(self):
        self.assertIn("F-001", self.content)
        self.assertIn("F-002", self.content)


class TestGL177ChangedFilesScope(unittest.TestCase):
    ALLOWED_FILES = {
        "docs/public_repo_smoke_verification.md",
        "docs/examples/gl177/public_repo_smoke_verification.json",
        "backend/tests/test_gl177_public_repo_smoke_verification.py",
    }

    def _get_changed_files(self):
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        if result.returncode != 0:
            return []
        return [f.strip() for f in result.stdout.splitlines() if f.strip()]

    def test_changed_files_within_allowed_scope(self):
        changed = self._get_changed_files()
        if not changed:
            self.skipTest("No branch diff (likely on main or single-commit branch)")
        for path in changed:
            self.assertIn(
                path,
                self.ALLOWED_FILES,
                f"Changed file '{path}' is outside allowed scope for GL-177",
            )

    def test_no_backend_src_changes(self):
        changed = self._get_changed_files()
        for path in changed:
            self.assertFalse(
                path.startswith("backend/src/"),
                f"GL-177 must not change backend/src: {path}",
            )

    def test_no_openapi_changes(self):
        changed = self._get_changed_files()
        for path in changed:
            self.assertFalse(
                "openapi" in path.lower(),
                f"GL-177 must not change OpenAPI files: {path}",
            )

    def test_no_migration_changes(self):
        changed = self._get_changed_files()
        for path in changed:
            self.assertFalse(
                path.startswith("migrations/"),
                f"GL-177 must not change migrations: {path}",
            )

    def test_no_dependency_changes(self):
        changed = self._get_changed_files()
        dep_files = ("requirements", "package.json", "package-lock.json", "pyproject.toml", "setup.py", "setup.cfg")
        for path in changed:
            for dep in dep_files:
                self.assertFalse(
                    path.startswith(dep) or os.path.basename(path) == dep,
                    f"GL-177 must not change dependency files: {path}",
                )

    def test_no_github_workflow_changes(self):
        changed = self._get_changed_files()
        for path in changed:
            self.assertFalse(
                path.startswith(".github/workflows/"),
                f"GL-177 must not change GitHub workflows: {path}",
            )

    def test_no_frontend_changes(self):
        changed = self._get_changed_files()
        for path in changed:
            self.assertFalse(
                path.startswith("frontend/") or path.startswith("website/"),
                f"GL-177 must not change frontend/website: {path}",
            )


if __name__ == "__main__":
    unittest.main()
