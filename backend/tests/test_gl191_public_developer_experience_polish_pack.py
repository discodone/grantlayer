"""GL-191 public developer experience polish pack tests.

Verifies that GL-191 README polish, troubleshooting/FAQ, evidence bundle
explanation, verify-helper cross-links, report doc, and JSON artifact are
all in place, consistent, and confined to the allowed file scope.
"""

import json
import subprocess
import sys
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[2]

README_PATH = REPO_ROOT / "README.md"
VERIFY_HELPER_DOC = REPO_ROOT / "docs" / "first_output_verify_helper.md"
EVIDENCE_BUNDLE_DOC = REPO_ROOT / "docs" / "grant_lifecycle_evidence_bundle.md"
POLISH_DOC = REPO_ROOT / "docs" / "public_developer_experience_polish_pack.md"
ARTIFACT_PATH = (
    REPO_ROOT
    / "docs"
    / "examples"
    / "gl191"
    / "public_developer_experience_polish_pack.json"
)

ALLOWED_CHANGED_FILES = {
    "README.md",
    "docs/first_output_verify_helper.md",
    "docs/grant_lifecycle_evidence_bundle.md",
    "docs/public_developer_experience_polish_pack.md",
    "docs/examples/gl191/public_developer_experience_polish_pack.json",
    "backend/tests/test_gl191_public_developer_experience_polish_pack.py",
}

FORBIDDEN_PREFIXES = (
    "backend/src/",
    "sdk/",
    "examples/first_verifiable_output.py",
    "examples/grant_lifecycle_evidence_bundle.py",
    "examples/langgraph_langchain/",
    "frontend/",
    "website/",
    "dashboard/",
    ".github/",
    "scripts/build-clean-public-snapshot.sh",
    "migrations/",
    "requirements.txt",
    "requirements-dev.txt",
    "docker-compose",
    "Dockerfile",
)

FORBIDDEN_FILENAMES = {
    "docs/openapi.yaml",
    "data/grantlayer.db",
}

ALLOWED_RESULT_VALUES = {
    "public_developer_experience_polish_complete",
    "blocked_unexpected_scope",
    "blocked_public_claim_safety",
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


class TestGL191FilesExist(unittest.TestCase):
    def test_readme_exists(self):
        self.assertTrue(README_PATH.is_file(), "README.md must exist")

    def test_verify_helper_doc_exists(self):
        self.assertTrue(VERIFY_HELPER_DOC.is_file(), "docs/first_output_verify_helper.md must exist")

    def test_evidence_bundle_doc_exists(self):
        self.assertTrue(EVIDENCE_BUNDLE_DOC.is_file(), "docs/grant_lifecycle_evidence_bundle.md must exist")

    def test_polish_doc_exists(self):
        self.assertTrue(POLISH_DOC.is_file(), "docs/public_developer_experience_polish_pack.md must exist")

    def test_artifact_exists(self):
        self.assertTrue(ARTIFACT_PATH.is_file(), "docs/examples/gl191/public_developer_experience_polish_pack.json must exist")


class TestGL191Artifact(unittest.TestCase):
    def setUp(self):
        self.artifact = _read_json(ARTIFACT_PATH)

    def test_artifact_valid_json(self):
        self.assertIsInstance(self.artifact, dict)

    def test_issue_id(self):
        self.assertEqual(self.artifact["issue_id"], "GL-191")

    def test_result_is_allowed(self):
        self.assertIn(self.artifact["result"], ALLOWED_RESULT_VALUES)

    def test_safety_confirmations_exist(self):
        sc = self.artifact.get("safety_confirmations", {})
        self.assertIsInstance(sc, dict)

    def test_no_github_push_confirmation(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_github_push_performed"), "no_github_push_performed must be true")

    def test_no_visibility_change_confirmation(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_visibility_change_performed"))

    def test_internal_repo_not_pushed_directly(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("internal_repo_not_pushed_directly_to_github"))

    def test_no_backend_src_changes(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_backend_src_changes"))

    def test_no_openapi_changes(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_openapi_changes"))

    def test_no_migration_db_dependency_changes(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_migration_db_dependency_changes"))

    def test_no_frontend_website_design_changes(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_frontend_website_design_changes"))

    def test_no_github_workflow_changes(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_github_workflow_changes"))

    def test_no_snapshot_publish_script_behavior_changes(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_snapshot_publish_script_behavior_changes"))

    def test_no_production_saas_claim(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_production_saas_claim"))

    def test_tenant_isolation_not_claimed(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("tenant_isolation_not_claimed"))

    def test_no_real_customer_data_requested(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_real_customer_data_requested"))

    def test_no_private_grant_data_requested(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_private_grant_data_requested"))

    def test_no_secrets_requested(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_secrets_requested"))

    def test_no_exploit_details_included(self):
        sc = self.artifact["safety_confirmations"]
        self.assertTrue(sc.get("no_exploit_details_included"))

    def test_changed_files_within_scope(self):
        changed = set(self.artifact.get("changed_files", []))
        extra = changed - ALLOWED_CHANGED_FILES
        self.assertEqual(extra, set(), f"Unexpected files in artifact changed_files: {extra}")


class TestGL191ReadmeContent(unittest.TestCase):
    def setUp(self):
        self.readme = _read_text(README_PATH)

    def test_references_verify_first_output_script(self):
        self.assertIn("scripts/verify-first-output.sh", self.readme)

    def test_references_grant_lifecycle_example(self):
        self.assertIn("examples/grant_lifecycle_evidence_bundle.py", self.readme)

    def test_references_first_output_verify_helper_doc(self):
        self.assertIn("docs/first_output_verify_helper.md", self.readme)

    def test_references_grant_lifecycle_evidence_bundle_doc(self):
        self.assertIn("docs/grant_lifecycle_evidence_bundle.md", self.readme)

    def test_separates_first_verifiable_output_from_lifecycle_bundle(self):
        self.assertIn("first_verifiable_output", self.readme)
        self.assertIn("grant_lifecycle_evidence_bundle", self.readme)
        first_pos = self.readme.find("first_verifiable_output")
        bundle_pos = self.readme.find("grant_lifecycle_evidence_bundle")
        self.assertNotEqual(first_pos, bundle_pos, "Both examples should be referenced distinctly")

    def test_separates_no_install_examples_from_backend_quickstart(self):
        self.assertIn("no install", self.readme.lower())
        self.assertIn("pip install", self.readme)

    def test_preserves_developer_preview_caveat(self):
        lower = self.readme.lower()
        self.assertTrue(
            "developer preview" in lower or "developer-preview" in lower,
            "README must mention Developer Preview"
        )

    def test_preserves_not_production_saas_caveat(self):
        lower = self.readme.lower()
        self.assertTrue(
            "not production saas" in lower
            or "not claimed" in lower
            or "not production-ready" in lower,
            "README must preserve not-production-SaaS caveat"
        )

    def test_preserves_tenant_isolation_not_implemented_caveat(self):
        lower = self.readme.lower()
        self.assertTrue(
            "tenant" in lower and ("not implemented" in lower or "isolation" in lower),
            "README must mention tenant isolation not implemented"
        )

    def test_preserves_no_real_secrets_customer_data_caveat(self):
        lower = self.readme.lower()
        self.assertTrue(
            ("no real secrets" in lower or "do not use real secrets" in lower)
            or ("no real customer" in lower or "do not use real customer" in lower),
            "README must preserve no-real-secrets/customer-data caveat"
        )


class TestGL191TroubleshootingFAQ(unittest.TestCase):
    def setUp(self):
        self.polish_doc = _read_text(POLISH_DOC)

    def test_troubleshooting_section_exists(self):
        self.assertIn("Troubleshooting", self.polish_doc)

    def test_covers_verify_first_output_mismatch(self):
        self.assertIn("verify-first-output mismatch", self.polish_doc)

    def test_covers_grant_lifecycle_output_mismatch(self):
        self.assertIn("grant lifecycle output mismatch", self.polish_doc)

    def test_covers_python3_or_script_executable_issues(self):
        lower = self.polish_doc.lower()
        self.assertTrue(
            "python3 not found" in lower or "executable" in lower or "permission denied" in lower,
            "Troubleshooting must cover python3/executable issues"
        )

    def test_covers_no_network_required(self):
        lower = self.polish_doc.lower()
        self.assertIn("network", lower)

    def test_covers_no_backend_required(self):
        lower = self.polish_doc.lower()
        self.assertIn("backend", lower)

    def test_covers_no_secrets_required(self):
        lower = self.polish_doc.lower()
        self.assertIn("secret", lower)

    def test_points_security_to_github_security_advisories(self):
        lower = self.polish_doc.lower()
        self.assertIn("security advisories", lower)


class TestGL191EvidenceBundleDoc(unittest.TestCase):
    def setUp(self):
        self.doc = _read_text(EVIDENCE_BUNDLE_DOC)

    def test_explains_audit_chain(self):
        lower = self.doc.lower()
        self.assertIn("audit chain", lower)

    def test_explains_bundle_hash(self):
        lower = self.doc.lower()
        self.assertIn("bundle_sha256", lower)

    def test_states_synthetic_demo_data_only(self):
        lower = self.doc.lower()
        self.assertTrue(
            "synthetic" in lower or "demo data only" in lower,
            "Evidence bundle doc must state synthetic/demo data only"
        )

    def test_states_no_backend_required(self):
        lower = self.doc.lower()
        self.assertIn("no backend required", lower)

    def test_states_no_network_required(self):
        lower = self.doc.lower()
        self.assertIn("no network required", lower)

    def test_states_no_secrets_required(self):
        lower = self.doc.lower()
        self.assertIn("no secrets required", lower)

    def test_states_no_customer_data_required(self):
        lower = self.doc.lower()
        self.assertIn("no customer data required", lower)


class TestGL191VerifyHelperDoc(unittest.TestCase):
    def setUp(self):
        self.doc = _read_text(VERIFY_HELPER_DOC)

    def test_points_to_grant_lifecycle_evidence_bundle(self):
        lower = self.doc.lower()
        self.assertTrue(
            "grant_lifecycle_evidence_bundle" in lower or "grant lifecycle evidence bundle" in lower,
            "Verify helper doc must point to grant lifecycle evidence bundle as next example"
        )

    def test_explains_verify_helper_scope(self):
        lower = self.doc.lower()
        self.assertIn("first deterministic output", lower)


class TestGL191ScopeGuard(unittest.TestCase):
    def test_changed_files_within_allowed_scope(self):
        changed = _changed_files()
        violations = []
        for f in changed:
            if f in ALLOWED_CHANGED_FILES:
                continue
            for prefix in FORBIDDEN_PREFIXES:
                if f.startswith(prefix):
                    violations.append(f)
                    break
            if f in FORBIDDEN_FILENAMES:
                violations.append(f)
        self.assertEqual(
            violations,
            [],
            f"Forbidden files changed: {violations}"
        )

    def test_no_backend_src_changes(self):
        changed = _changed_files()
        violations = [f for f in changed if f.startswith("backend/src/")]
        self.assertEqual(violations, [], f"backend/src/ files changed: {violations}")

    def test_no_openapi_changes(self):
        changed = _changed_files()
        violations = [f for f in changed if "openapi" in f.lower()]
        self.assertEqual(violations, [], f"OpenAPI files changed: {violations}")

    def test_no_migration_changes(self):
        changed = _changed_files()
        violations = [f for f in changed if "migration" in f.lower()]
        self.assertEqual(violations, [], f"Migration files changed: {violations}")

    def test_no_db_schema_changes(self):
        changed = _changed_files()
        violations = [f for f in changed if "schema" in f.lower() or f.endswith(".sql")]
        self.assertEqual(violations, [], f"DB/schema files changed: {violations}")

    def test_no_dependency_manifest_changes(self):
        changed = _changed_files()
        violations = [
            f for f in changed
            if f in ("requirements.txt", "requirements-dev.txt", "pyproject.toml", "setup.py", "setup.cfg")
        ]
        self.assertEqual(violations, [], f"Dependency manifests changed: {violations}")

    def test_no_sdk_implementation_changes(self):
        changed = _changed_files()
        violations = [f for f in changed if f.startswith("sdk/")]
        self.assertEqual(violations, [], f"SDK files changed: {violations}")

    def test_no_examples_runtime_implementation_changes(self):
        changed = _changed_files()
        violations = [
            f for f in changed
            if f.startswith("examples/") and f.endswith(".py")
        ]
        self.assertEqual(violations, [], f"Example runtime .py files changed: {violations}")

    def test_no_frontend_website_design_changes(self):
        changed = _changed_files()
        violations = [
            f for f in changed
            if f.startswith("frontend/") or f.startswith("website/") or f.startswith("dashboard/")
        ]
        self.assertEqual(violations, [], f"Frontend/website/design files changed: {violations}")

    def test_no_github_workflow_changes(self):
        changed = _changed_files()
        violations = [f for f in changed if f.startswith(".github/")]
        self.assertEqual(violations, [], f"GitHub workflow files changed: {violations}")

    def test_no_snapshot_publish_script_behavior_changes(self):
        changed = _changed_files()
        violations = [
            f for f in changed
            if "build-clean-public-snapshot" in f or "github-private-mirror" in f
        ]
        self.assertEqual(violations, [], f"Snapshot publish script changed: {violations}")


if __name__ == "__main__":
    unittest.main()
