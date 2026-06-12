"""GL-168 first verifiable output example validation tests."""

import hashlib
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "examples" / "first_verifiable_output.py"
JSON_PATH = REPO_ROOT / "examples" / "first_verifiable_output.json"
DOC_PATH = REPO_ROOT / "docs" / "first_verifiable_output.md"
TMP_OUTPUT = Path("/tmp/grantlayer_first_output.json")

EXPECTED_FILES = {
    "examples/first_verifiable_output.py",
    "examples/first_verifiable_output.json",
    "docs/first_verifiable_output.md",
    "backend/tests/test_gl168_first_verifiable_output.py",
}


def _read(path):
    return path.read_text(encoding="utf-8")


def _load_json(path=JSON_PATH):
    return json.loads(_read(path))


def _canonical_json(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_json(data):
    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


def _load_script_module():
    spec = importlib.util.spec_from_file_location("first_verifiable_output", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestGL168FilesExist(unittest.TestCase):
    def test_expected_files_exist(self):
        for path in [SCRIPT_PATH, JSON_PATH, DOC_PATH, Path(__file__)]:
            self.assertTrue(path.is_file(), f"Missing {path}")


class TestGL168ScriptBehavior(unittest.TestCase):
    def test_script_reproduces_committed_json_exactly(self):
        if TMP_OUTPUT.exists():
            TMP_OUTPUT.unlink()
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--output",
                str(TMP_OUTPUT),
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(_read(JSON_PATH), _read(TMP_OUTPUT))

    def test_build_record_matches_committed_json(self):
        module = _load_script_module()
        self.assertEqual(module.build_record(), _load_json())

    def test_script_uses_standard_library_only(self):
        source = _read(SCRIPT_PATH)
        for forbidden in [
            "requests",
            "urllib",
            "http.client",
            "socket",
            "subprocess",
            "httpx",
            "aiohttp",
        ]:
            self.assertNotIn(forbidden, source)

    def test_script_requires_output_argument(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--output", result.stderr)


class TestGL168JsonContent(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()

    def test_required_top_level_sections(self):
        for key in [
            "grant_request",
            "decision",
            "evidence_items",
            "evidence_bundle",
            "audit_trail",
            "compliance_readiness_summary",
        ]:
            self.assertIn(key, self.data)

    def test_identity_and_fixed_timestamps(self):
        self.assertEqual(self.data["example_id"], "gl168-first-verifiable-output")
        self.assertEqual(
            self.data["record_type"],
            "grantlayer_first_verifiable_output_example",
        )
        self.assertEqual(self.data["generated_at"], "2026-01-15T12:00:00Z")
        self.assertEqual(
            self.data["grant_request"]["id"],
            "gl168-grant-request-001",
        )

    def test_evidence_hashes_are_valid_sha256(self):
        for item in self.data["evidence_items"]:
            digest = item["content_sha256"]
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
            self.assertEqual(digest, _sha256_json(item["content"]))

    def test_bundle_hash_matches_content(self):
        bundle = self.data["evidence_bundle"]
        self.assertRegex(bundle["bundle_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(bundle["bundle_sha256"], _sha256_json(bundle["content"]))
        self.assertEqual(
            bundle["content"]["evidence_item_hashes"],
            [item["content_sha256"] for item in self.data["evidence_items"]],
        )

    def test_audit_trail_is_chained_and_hashed(self):
        previous_hash = None
        for event in self.data["audit_trail"]:
            self.assertEqual(event["previous_event_hash"], previous_hash)
            event_without_hash = dict(event)
            event_hash = event_without_hash.pop("event_hash")
            self.assertRegex(event_hash, r"^[0-9a-f]{64}$")
            self.assertEqual(event_hash, _sha256_json(event_without_hash))
            previous_hash = event_hash

    def test_compliance_readiness_preserves_caveats(self):
        summary = self.data["compliance_readiness_summary"]
        self.assertEqual(summary["status"], "ready_for_local_review")
        self.assertEqual(summary["checks"]["production_saas_readiness"], "not_claimed")
        self.assertEqual(summary["checks"]["tenant_isolation"], "not_implemented")
        caveats = " ".join(self.data["caveats"]).lower()
        self.assertIn("synthetic local example data", caveats)
        self.assertIn("not production saas readiness", caveats)
        self.assertIn("tenant isolation is not implemented", caveats)


class TestGL168Docs(unittest.TestCase):
    def setUp(self):
        self.content = _read(DOC_PATH)
        self.lower = self.content.lower()
        self.normalized = " ".join(self.lower.split())

    def test_docs_include_required_topics(self):
        for phrase in [
            "what it demonstrates",
            "what it does not claim",
            "python3 examples/first_verifiable_output.py --output /tmp/grantlayer_first_output.json",
            "/tmp/grantlayer_first_output.json",
            "evidence hashes",
            "audit trail",
            "synthetic local example data",
            "not claim production saas readiness",
            "tenant isolation is not implemented",
        ]:
            self.assertIn(phrase, self.normalized)

    def test_docs_state_no_external_requirements(self):
        for phrase in [
            "no network calls",
            "uses no secrets",
            "requires no backend service startup",
            "requires no github auth",
            "uses no real customer data",
        ]:
            self.assertIn(phrase, self.normalized)


class TestGL168SafetyAndScope(unittest.TestCase):
    def test_no_forbidden_content(self):
        combined = "\n".join(_read(path) for path in [SCRIPT_PATH, JSON_PATH, DOC_PATH])
        lowered = combined.lower()
        forbidden = [
            "paper" + "clip",
            "forge." + "hofercloud.eu",
            "/home/" + "adminuser",
            "/home/" + "oai",
            "/mnt/" + "data",
            "begin rsa private key",
            "begin openssh private key",
            "github " + "push",
            "change github " + "visibility",
            "force " + "push",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, lowered)

    def test_no_forbidden_paths_changed_in_branch_diff(self):
        try:
            subprocess.run(['git', 'rev-parse', 'main'], check=True,
                          capture_output=True)
        except subprocess.CalledProcessError:
            self.skipTest("main branch not available in this environment")
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        changed = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        if changed and changed.issubset(EXPECTED_FILES):
            self.assertEqual(changed, EXPECTED_FILES)
        for path in changed:
            self.assertFalse(path.startswith("backend/src/"), path)
            self.assertFalse(path.startswith("backend/src/migrations/"), path)
            self.assertNotEqual(path, "docs/openapi.yaml")
            self.assertNotIn(path, {"requirements.txt", "requirements-dev.txt"})
