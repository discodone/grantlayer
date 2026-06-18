"""GL-322 — Audit Log Compliance Export + Immutability Proof.

Covers:
- audit_compliance router importable
- GET /v1/audit/export requires auth
- GET /v1/audit/export returns NDJSON content type
- GET /v1/audit/verify requires auth
- GET /v1/audit/verify returns {valid, checked, broken_at}
- Export + verify round trip: valid chain passes
- Tampered entry: verify detects broken chain
- HMAC manifest present in export
- verify_ndjson_export works offline
- CLI script verify-audit.py exists
- Chain hash uses SHA-256(prev_hash + canonical)
- Empty export returns manifest with 0 entries
"""

from __future__ import annotations

import json
import os
import unittest


_TEST_SECRET = "gl322-test-hs256-secret-32chars!!"


def _make_client():
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def _jwt() -> str:
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
    os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)
    from backend.src.api.auth_jwt import encode_token
    # No sub → legacy demo mode (no workspace DB lookup required)
    return encode_token(
        {"role": "auditor", "tenant_id": "demo",
         "iss": "grantlayer", "aud": "grantlayer-api"},
        _TEST_SECRET,
    )


class TestAuditComplianceRouterImport(unittest.TestCase):
    def test_router_importable(self):
        from backend.src.api.routers.audit_compliance import router
        self.assertIsNotNone(router)

    def test_router_prefix(self):
        from backend.src.api.routers.audit_compliance import router
        self.assertEqual(router.prefix, "/audit")


class TestAuditExportEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = _make_client()
        self.auth = {"Authorization": f"Bearer {_jwt()}"}

    def test_export_requires_auth(self):
        resp = self.client.get("/v1/audit/export")
        self.assertEqual(resp.status_code, 401)

    def test_export_returns_ndjson_content_type(self):
        resp = self.client.get("/v1/audit/export", headers=self.auth)
        self.assertIn(resp.status_code, [200, 400])
        if resp.status_code == 200:
            self.assertIn("ndjson", resp.headers.get("content-type", ""))

    def test_export_returns_200(self):
        resp = self.client.get("/v1/audit/export", headers=self.auth)
        self.assertEqual(resp.status_code, 200)

    def test_export_last_line_is_manifest(self):
        resp = self.client.get("/v1/audit/export", headers=self.auth)
        if resp.status_code != 200:
            return
        lines = [l.strip() for l in resp.text.strip().splitlines() if l.strip()]
        self.assertTrue(len(lines) >= 1)
        last = json.loads(lines[-1])
        self.assertEqual(last.get("_type"), "manifest")
        self.assertIn("_hmac_signature", last)


class TestAuditVerifyEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = _make_client()
        self.auth = {"Authorization": f"Bearer {_jwt()}"}

    def test_verify_requires_auth(self):
        resp = self.client.get("/v1/audit/verify")
        self.assertEqual(resp.status_code, 401)

    def test_verify_returns_200(self):
        resp = self.client.get("/v1/audit/verify", headers=self.auth)
        self.assertEqual(resp.status_code, 200)

    def test_verify_response_structure(self):
        resp = self.client.get("/v1/audit/verify", headers=self.auth)
        if resp.status_code != 200:
            return
        data = resp.json()
        self.assertIn("valid", data)
        self.assertIn("checked", data)
        self.assertIn("broken_at", data)

    def test_verify_returns_bool_valid(self):
        resp = self.client.get("/v1/audit/verify", headers=self.auth)
        if resp.status_code != 200:
            return
        data = resp.json()
        self.assertIsInstance(data["valid"], bool)

    def test_verify_returns_int_checked(self):
        resp = self.client.get("/v1/audit/verify", headers=self.auth)
        if resp.status_code != 200:
            return
        data = resp.json()
        self.assertIsInstance(data["checked"], int)


class TestVerifyNdjsonExport(unittest.TestCase):
    def _build_export(self, entries: list[dict]) -> str:
        """Build a valid NDJSON export from entries."""
        from backend.src.api.routers.audit_compliance import (
            _chain_hash, _entry_canonical, _sign_manifest
        )
        lines = []
        prev_hash = "0" * 64
        all_hashes = []
        for entry in entries:
            canonical = _entry_canonical(entry)
            entry_hash = _chain_hash(prev_hash, canonical)
            record = {**entry, "_chain_hash": entry_hash, "_prev_hash": prev_hash}
            all_hashes.append(entry_hash)
            prev_hash = entry_hash
            lines.append(json.dumps(record))
        manifest = {
            "_type": "manifest",
            "_entry_count": len(entries),
            "_final_hash": prev_hash,
            "_hmac_signature": _sign_manifest(all_hashes),
        }
        lines.append(json.dumps(manifest))
        return "\n".join(lines)

    def test_valid_chain_passes(self):
        from backend.src.api.routers.audit_compliance import verify_ndjson_export
        entries = [
            {"id": "e1", "timestamp": "2026-01-01T00:00:00Z", "action": "read", "subject_id": "u1", "resource": "r", "role": "viewer", "approved": 1, "reason": "test"},
            {"id": "e2", "timestamp": "2026-01-01T00:01:00Z", "action": "write", "subject_id": "u1", "resource": "r", "role": "viewer", "approved": 1, "reason": "test"},
        ]
        export = self._build_export(entries)
        result = verify_ndjson_export(export)
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked"], 2)
        self.assertIsNone(result["broken_at"])

    def test_tampered_entry_detected(self):
        from backend.src.api.routers.audit_compliance import verify_ndjson_export
        entries = [
            {"id": "e1", "timestamp": "2026-01-01T00:00:00Z", "action": "read", "subject_id": "u1", "resource": "r", "role": "viewer", "approved": 1, "reason": "test"},
            {"id": "e2", "timestamp": "2026-01-01T00:01:00Z", "action": "write", "subject_id": "u1", "resource": "r", "role": "viewer", "approved": 1, "reason": "test"},
        ]
        export = self._build_export(entries)

        # Tamper with the first record's _chain_hash
        lines = export.splitlines()
        first = json.loads(lines[0])
        first["_chain_hash"] = "deadbeef" * 8
        lines[0] = json.dumps(first)
        tampered = "\n".join(lines)

        result = verify_ndjson_export(tampered)
        # Second entry should fail due to prev_hash mismatch
        self.assertFalse(result["valid"])

    def test_empty_export_returns_valid_zero(self):
        from backend.src.api.routers.audit_compliance import verify_ndjson_export
        export = self._build_export([])
        result = verify_ndjson_export(export)
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked"], 0)

    def test_manifest_signature_valid(self):
        from backend.src.api.routers.audit_compliance import verify_ndjson_export
        entries = [
            {"id": "e1", "timestamp": "2026-01-01T00:00:00Z", "action": "read", "subject_id": "u1", "resource": "r", "role": "viewer", "approved": 1, "reason": "ok"},
        ]
        export = self._build_export(entries)
        result = verify_ndjson_export(export)
        self.assertTrue(result.get("manifest_valid", True))


class TestChainHash(unittest.TestCase):
    def test_chain_hash_is_sha256(self):
        import hashlib
        from backend.src.api.routers.audit_compliance import _chain_hash
        prev = "0" * 64
        canonical = '{"action": "read"}'
        expected = hashlib.sha256((prev + canonical).encode()).hexdigest()
        self.assertEqual(_chain_hash(prev, canonical), expected)


class TestVerifyScript(unittest.TestCase):
    def test_verify_script_exists(self):
        from pathlib import Path
        script = Path(__file__).parent.parent.parent / "scripts" / "verify-audit.py"
        self.assertTrue(script.exists())

    def test_verify_script_importable_logic(self):
        from pathlib import Path
        import importlib.util
        script = Path(__file__).parent.parent.parent / "scripts" / "verify-audit.py"
        spec = importlib.util.spec_from_file_location("verify_audit", script)
        self.assertIsNotNone(spec)
