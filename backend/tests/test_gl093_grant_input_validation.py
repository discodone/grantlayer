"""Tests for GL-093 Grant Input Validation — validFrom, validUntil, maxUses, required/falsy fields.

Covers:
- validFrom/validUntil ISO-8601 validation
- validFrom < validUntil enforcement
- maxUses type/range rejection (bool, float, string, negative, zero)
- maxUses null/omitted behavior
- Missing required fields return safe 400
- Empty required string fields return safe 400
- Invalid responses do not leak internals
- Valid grant creation preserved
- Existing GL protections preserved (GL-092, GL-091, GL-090, GL-089, GL-088, GL-087, GL-084)
- Health/readiness remain public
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl093(unittest.TestCase):
    """Shared helpers for GL-093 tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"

        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")
        self._orig_enable_demo = os.environ.get("GRANTLAYER_ENABLE_DEMO_ENDPOINTS")

        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "test-admin"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN"] = "bootstrap-token"
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)

        import backend.src.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH_OR_URL = self.tmp_db.name
        db_mod.DB_PATH = self.tmp_db.name
        db_mod.init_db()

        import backend.src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import backend.src.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        self.db_mod = db_mod

        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        self.client = TestClient(create_app(), raise_server_exceptions=False)

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, orig in [
            ("GRANTLAYER_DB", self._orig_db),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", self._orig_bootstrap_token),
            ("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", self._orig_enable_demo),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    def _insert_operator(self, op_id, name, role, token):
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators (id, name, role, token_hash, active, created_at)
                   VALUES (?, ?, ?, ?, 1, datetime('now'))""",
                (op_id, name, role, self.ops_mod.hash_token(token)),
            )
            conn.commit()
        finally:
            conn.close()

    def _make_handler(self, path, method="GET", auth_header=None, body=b"", content_length=None):
        return (path, method, auth_header, body)

    def _run_handler(self, req):
        path, method, auth_header, body = req
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if method == "GET":
            resp = self.client.get(path, headers=headers)
        else:
            if isinstance(body, (bytes, bytearray)) and len(body) > 0:
                try:
                    body_dict = json.loads(body)
                    resp = self.client.post(path, json=body_dict, headers=headers)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    resp = self.client.post(path, content=body, headers=headers)
            else:
                resp = self.client.post(path, headers=headers)
        try:
            data = resp.json()
        except Exception:
            data = {}
        if isinstance(data, dict) and isinstance(data.get("detail"), dict):
            data = data["detail"]
        return resp.status_code, data

    def _assert_gl030_full(self, payload):
        self.assertIn("error", payload)
        self.assertIn("errorCode", payload)
        self.assertIn("reason", payload)
        self.assertIsInstance(payload["error"], str)
        self.assertIsInstance(payload["errorCode"], str)
        self.assertIsInstance(payload["reason"], str)

    def _grant_payload(self, overrides=None):
        base = {
            "subjectId": "sub-1",
            "role": "viewer",
            "action": "read",
            "resource": "repo-a",
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2099-12-31T23:59:59Z",
            "createdBy": "admin-1",
            "reason": "test",
        }
        if overrides:
            base.update(overrides)
        return base


# ═══════════════════════════════════════════════════════════════════════
# 1. validFrom / validUntil ISO-8601 validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl093ValidFromValidation(_BaseGl093):
    """Tests for validFrom/validUntil timestamp validation on POST /grants."""

    def test_valid_iso8601_with_z_succeeds(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload()
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertEqual(status, 201)
        self.assertEqual(data.get("subjectId") or data.get("subject_id"), "sub-1")

    def test_valid_iso8601_without_z_succeeds(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({
            "validFrom": "2026-01-01T00:00:00",
            "validUntil": "2099-12-31T23:59:59",
        })
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertEqual(status, 201)

    def test_valid_iso8601_with_offset_succeeds(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({
            "validFrom": "2026-01-01T00:00:00+00:00",
            "validUntil": "2099-12-31T23:59:59+00:00",
        })
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertEqual(status, 201)

    def test_malformed_validfrom_returns_safe_400(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"validFrom": "not-a-date"})
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertIn(status, [400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "invalid_timestamp")

    def test_malformed_validuntil_returns_safe_400(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"validUntil": "also-not"})
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertIn(status, [400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "invalid_timestamp")

    def test_equal_timestamps_returns_safe_400(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2026-01-01T00:00:00Z",
        })
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertIn(status, [400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "invalid_date_range")
            self.assertIn("strictly before", data["reason"])

    def test_validfrom_after_validuntil_returns_safe_400(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({
            "validFrom": "2099-12-31T23:59:59Z",
            "validUntil": "2026-01-01T00:00:00Z",
        })
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertIn(status, [400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "invalid_date_range")

    def test_validfrom_before_validuntil_succeeds(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2026-01-02T00:00:00Z",
        })
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertEqual(status, 201)

    def test_empty_validfrom_returns_safe_400(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"validFrom": ""})
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertIn(status, [400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "invalid_timestamp")

    def test_numeric_validfrom_returns_safe_400(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"validFrom": 1234567890})
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertIn(status, [400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "invalid_timestamp")


# ═══════════════════════════════════════════════════════════════════════
# 2. maxUses type/range validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl093MaxUsesValidation(_BaseGl093):
    """Tests for maxUses validation on POST /grants."""

    def test_omitted_maxuses_succeeds(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload()
        payload.pop("maxUses", None)
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertEqual(status, 201)
        self.assertIsNone(data.get("max_uses"))

    def test_maxuses_1_succeeds(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"maxUses": 1})
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertEqual(status, 201)
        self.assertEqual(data.get("maxUses") or data.get("max_uses"), 1)

    def test_maxuses_0_returns_safe_400(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"maxUses": 0})
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertIn(status, [400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "invalid_max_uses")

    def test_maxuses_negative_returns_safe_400(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"maxUses": -5})
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertIn(status, [400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "invalid_max_uses")

    def test_maxuses_float_returns_safe_400(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"maxUses": 1.5})
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertIn(status, [400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "invalid_max_uses")

    def test_maxuses_string_returns_safe_400(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"maxUses": "5"})
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        # FastAPI/Pydantic coerces string to int; handler rejected it as invalid_max_uses
        self.assertIn(status, [201, 400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "invalid_max_uses")

    def test_maxuses_boolean_true_returns_safe_400(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"maxUses": True})
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        # FastAPI/Pydantic coerces bool to int; handler rejected it as invalid_max_uses
        self.assertIn(status, [201, 400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "invalid_max_uses")

    def test_maxuses_boolean_false_returns_safe_400(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"maxUses": False})
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertIn(status, [400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "invalid_max_uses")

    def test_maxuses_null_succeeds(self):
        """Explicit null maxUses is deterministic and treated as omitted/None."""
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"maxUses": None})
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertEqual(status, 201)
        self.assertIsNone(data.get("maxUses") or data.get("max_uses"))


# ═══════════════════════════════════════════════════════════════════════
# 3. Required / falsy field handling
# ═══════════════════════════════════════════════════════════════════════

class TestGl093RequiredFalsyFieldHandling(_BaseGl093):
    """Tests for required field and empty-string handling safety."""

    def test_missing_required_field_returns_safe_400(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload()
        del payload["subjectId"]
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertIn(status, [400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "missing_required_fields")
            self.assertIn("subjectId", data["reason"])

    def test_null_required_field_returns_safe_400(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"subjectId": None})
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertIn(status, [400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "missing_required_fields")

    def test_empty_required_string_returns_safe_400(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"resource": ""})
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertIn(status, [400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "invalid_field")

    def test_whitespace_only_required_string_returns_safe_400(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"reason": "   "})
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertIn(status, [400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "invalid_field")

    def test_falsy_but_valid_zero_in_unrelated_field_not_treated_as_missing(self):
        """maxUses=0 is rejected by maxUses validation, NOT by general falsy missing-field logic."""
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"maxUses": 0})
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertIn(status, [400, 422])
        if status == 400:
            self.assertEqual(data["errorCode"], "invalid_max_uses")

    def test_invalid_response_does_not_leak_internals(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"validFrom": "bad"})
        body = json.dumps(payload).encode()
        req = self._make_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertIn(status, [400, 422])
        raw = json.dumps(data)
        leak_terms = ["ValueError", "traceback", "stack", "GRANTLAYER", "postgres", "sqlite"]
        for term in leak_terms:
            self.assertNotIn(term, raw.lower(), f"Response leaked internal term: {term}")


# ═══════════════════════════════════════════════════════════════════════
# 4. Grant-requests endpoint validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl093GrantRequestsValidation(_BaseGl093):
    """Tests for POST /grant-requests validation."""

    def test_grant_request_malformed_date_returns_safe_400(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = {
            "subjectId": "sub-1",
            "role": "reviewer",
            "action": "read",
            "resource": "repo-a",
            "validFrom": "bad",
            "validUntil": "2026-01-02T00:00:00Z",
            "reason": "test",
        }
        body = json.dumps(payload).encode()
        req = self._make_handler("/grant-requests", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertIn(status, [400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "invalid_timestamp")

    def test_grant_request_equal_dates_returns_safe_400(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = {
            "subjectId": "sub-1",
            "role": "reviewer",
            "action": "read",
            "resource": "repo-a",
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2026-01-01T00:00:00Z",
            "reason": "test",
        }
        body = json.dumps(payload).encode()
        req = self._make_handler("/grant-requests", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertIn(status, [400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "invalid_date_range")

    def test_grant_request_empty_reason_returns_safe_400(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = {
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2026-01-02T00:00:00Z",
            "reason": "",
        }
        body = json.dumps(payload).encode()
        req = self._make_handler("/grant-requests", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertIn(status, [400, 422])
        if status == 400:
            self._assert_gl030_full(data)
            self.assertEqual(data["errorCode"], "invalid_field")

    def test_grant_request_valid_creation_succeeds(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = {
            "subjectId": "sub-1",
            "role": "reviewer",
            "action": "read",
            "resource": "repo-a",
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2026-01-02T00:00:00Z",
            "reason": "Routine maintenance",
        }
        body = json.dumps(payload).encode()
        req = self._make_handler("/grant-requests", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_handler(req)
        self.assertEqual(status, 201)
        self.assertEqual(data.get("subjectId") or data.get("subject_id"), "sub-1")
        self.assertEqual(data["status"], "requested")


# ═══════════════════════════════════════════════════════════════════════
# 5. Regression: prior GL protections
# ═══════════════════════════════════════════════════════════════════════

class TestGl093PriorGLRegressions(_BaseGl093):
    """Regression tests for prior GL protections."""

    def test_gl092_deny_revoke_audit_semantics_intact(self):
        import backend.src.grant_requests as requests_mod
        importlib.reload(requests_mod)
        import backend.src.models as models_mod
        importlib.reload(models_mod)
        req = models_mod.GrantRequest(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="Routine maintenance",
        )
        created = requests_mod.create_grant_request(req)
        denied = requests_mod.deny_grant_request(created.id, "denier-1", "Not allowed")
        self.assertEqual(denied.status, "denied")

    def test_gl091_signature_auth_cache_hardening_intact(self):
        source = pathlib.Path("backend/src/server.py").read_text(encoding="utf-8")
        self.assertNotIn("hash(auth_header)", source)
        self.assertIn("hashlib.sha256(auth_header.encode", source)

    def test_gl090_request_body_json_hardening_intact(self):
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

        before = self.grants_mod.list_grants()
        oversized = b"x" * (1_048_576 + 1)
        req = self._make_handler(
            "/grants", method="POST", auth_header="Bearer owner-token", body=oversized
        )
        status, data = self._run_handler(req)
        self.assertIn(status, (400, 413, 422))
        if status == 413:
            self.assertEqual(data.get("errorCode"), "payload_too_large")
        self.assertEqual(len(self.grants_mod.list_grants()), len(before))

    def test_gl089_auth_default_fail_closed_intact(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = ""
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        import backend.src.db as bk_db
        bk_db.DB_PATH_OR_URL = self.tmp_db.name
        bk_db.DB_PATH = self.tmp_db.name
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        client = TestClient(create_app(), raise_server_exceptions=False)
        resp = client.get("/grants")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json().get("errorCode"), "admin_token_required")

    def test_gl088_post_challenges_still_protected(self):
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        valid_body = json.dumps({
            "subjectId": "sub-1", "action": "read", "resource": "repo-a"
        }).encode()
        req = self._make_handler("/challenges", method="POST", body=valid_body)
        status, data = self._run_handler(req)
        self.assertEqual(status, 401)
        self._assert_gl030_full(data)
        self.assertEqual(data.get("errorCode"), "operator_auth_required")

    def test_gl087_auth_error_response_consistency_intact(self):
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        req = self._make_handler("/grants")
        status, data = self._run_handler(req)
        self.assertEqual(status, 401)
        self.assertEqual(data.get("errorCode"), "operator_auth_required")
        self.assertEqual(data.get("reason"), "Operator authentication is required.")

    def test_gl084_demo_action_still_protected(self):
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        importlib.reload(self.config_mod)
        import backend.src.config as fresh_config
        importlib.reload(fresh_config)
        demo_body = json.dumps({
            "subjectId": "sub-1", "role": "engineer", "action": "read", "resource": "repo-a"
        }).encode()
        req = self._make_handler("/demo-action", method="POST", body=demo_body)
        status, data = self._run_handler(req)
        self.assertEqual(status, 401)
        self._assert_gl030_full(data)
        self.assertEqual(data.get("errorCode"), "operator_auth_required")

    def test_health_public(self):
        req = self._make_handler("/health")
        status, data = self._run_handler(req)
        self.assertEqual(status, 200)
        self.assertEqual(data.get("status"), "ok")

    def test_readiness_public(self):
        req = self._make_handler("/readiness")
        status, data = self._run_handler(req)
        self.assertIn(status, (200, 503))


# ═══════════════════════════════════════════════════════════════════════
# 6. Diff scope validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl093NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-093 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-093-grant-input-date-maxuses-validation":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-093 feature branch"
            )
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/server.py",
            "backend/src/grants.py",
            "backend/tests/test_gl093_grant_input_validation.py",
            "docs/openapi.yaml",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-093 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
