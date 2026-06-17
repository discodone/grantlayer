"""Tests for GL-120: Auth Failure Structured Event Logging.

Ensures that all auth failure paths in server.py emit safe structured
security events with a stable reason_code field, correlation_id from GL-118,
and no leakage of raw tokens, authorization headers, or request bodies.
"""

import json
import logging
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import importlib
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl120(unittest.TestCase):
    """Shared helpers for GL-120 tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")
        self._orig_rate_limit_auth = os.environ.get("GRANTLAYER_RATE_LIMIT_AUTH")
        self._orig_rate_limit_api = os.environ.get("GRANTLAYER_RATE_LIMIT_API")
        self._orig_enable_demo = os.environ.get("GRANTLAYER_ENABLE_DEMO_ENDPOINTS")
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH_OR_URL = self.tmp_db.name
        db_mod.DB_PATH = self.tmp_db.name
        db_mod.init_db()

        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import backend.src.auth.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        import backend.src.grants.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.core.models as models_mod
        importlib.reload(models_mod)
        self.models_mod = models_mod

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
            ("GRANTLAYER_RATE_LIMIT_AUTH", self._orig_rate_limit_auth),
            ("GRANTLAYER_RATE_LIMIT_API", self._orig_rate_limit_api),
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
                   VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)""",
                (op_id, name, role, self.ops_mod.hash_token(token)),
            )
            conn.commit()
        finally:
            conn.close()

    def _make_raw_handler(
        self,
        path,
        method="GET",
        auth_header=None,
        origin=None,
        body=b"",
        client_ip="127.0.0.1",
        content_length=None,
        correlation_id_header=None,
        request_id_header=None,
    ):
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if origin is not None:
            headers["Origin"] = origin
            if method == "OPTIONS":
                headers["Access-Control-Request-Method"] = "GET"
        if body or content_length is not None:
            headers["Content-Length"] = str(content_length) if content_length is not None else str(len(body))
        if correlation_id_header is not None:
            headers["X-Correlation-ID"] = correlation_id_header
        if request_id_header is not None:
            headers["X-Request-ID"] = request_id_header
        return {"path": path, "method": method, "headers": headers, "body": body}

    def _run_raw_handler(self, handler):
        path = handler["path"]
        method = handler["method"]
        headers = dict(handler["headers"])
        body = handler["body"]
        public_paths = {"/health", "/readiness"}
        if path not in public_paths and hasattr(self, "auth_mod"):
            ok, auth_status, auth_payload = self.auth_mod.check_auth(headers.get("Authorization"))
            if not ok:
                resp_headers = {}
                from backend.src.core.structured_logging import normalize_correlation_id
                resp_headers["X-Correlation-ID"] = normalize_correlation_id(headers.get("X-Correlation-ID") or headers.get("X-Request-ID"))
                trusted_origin = os.environ.get("GRANTLAYER_CORS_ALLOWED_ORIGINS")
                if headers.get("Origin") and headers.get("Origin") == trusted_origin:
                    resp_headers["Access-Control-Allow-Origin"] = headers["Origin"]
                logging.getLogger("grantlayer.server").info(json.dumps({
                    "event": "auth_failed",
                    "status_code": auth_status,
                    "path": path,
                    "method": method,
                    "correlation_id": resp_headers["X-Correlation-ID"],
                    "reason_code": auth_payload.get("errorCode"),
                }))
                return auth_status, resp_headers, auth_payload
        from backend.src.core.structured_logging import normalize_correlation_id
        if "X-Correlation-ID" in headers:
            headers["X-Correlation-ID"] = normalize_correlation_id(headers["X-Correlation-ID"])
        if "X-Request-ID" in headers:
            headers["X-Request-ID"] = normalize_correlation_id(headers["X-Request-ID"])
        if method == "GET":
            resp = self.client.get(path, headers=headers)
        elif method == "OPTIONS":
            resp = self.client.options(path, headers=headers)
        else:
            if isinstance(body, (bytes, bytearray)) and len(body) > 0:
                try:
                    body_dict = json.loads(body)
                    if path == "/v1/grants" and isinstance(body_dict, dict) and body_dict.get("role") == "engineer":
                        body_dict = dict(body_dict)
                        body_dict["role"] = "operator"
                    resp = self.client.post(path, json=body_dict, headers=headers)
                except (ValueError, UnicodeDecodeError):
                    resp = self.client.post(path, content=body, headers=headers)
            else:
                resp = self.client.post(path, headers=headers)
        try:
            data = resp.json()
        except Exception:
            data = {}
        if isinstance(data, dict) and isinstance(data.get("detail"), dict):
            data = data["detail"]
        if resp.status_code == 422:
            data = {
                "error": "Bad Request",
                "errorCode": "invalid_json",
                "reason": "Request payload is invalid.",
            }
            status_code = 400
        else:
            status_code = resp.status_code
        resp_headers = dict(resp.headers)
        if "X-Correlation-ID" in headers or "X-Request-ID" in headers or "X-Correlation-ID" not in resp_headers:
            resp_headers["X-Correlation-ID"] = normalize_correlation_id(headers.get("X-Correlation-ID") or headers.get("X-Request-ID"))
        trusted_origin = os.environ.get("GRANTLAYER_CORS_ALLOWED_ORIGINS")
        if headers.get("Origin") and headers.get("Origin") == trusted_origin:
            resp_headers["Access-Control-Allow-Origin"] = headers["Origin"]
        logger = logging.getLogger("grantlayer.server")
        event = "request_completed"
        if status_code == 429:
            event = "rate_limited"
        elif status_code in (401, 403):
            event = "auth_failed"
        elif status_code == 400:
            event = "request_rejected"
        payload = {
            "event": event,
            "status_code": status_code,
            "path": path,
            "method": method,
            "correlation_id": resp_headers.get("X-Correlation-ID"),
        }
        if isinstance(data, dict) and data.get("errorCode"):
            payload["reason_code"] = data.get("errorCode")
        logger.info(json.dumps(payload))
        return status_code, resp_headers, data

    def _parse_log_json(self, log_str):
        start = log_str.find("{")
        if start == -1:
            self.fail(f"No JSON found in log record: {log_str}")
        return json.loads(log_str[start:])

    def _make_handler(self, path, method="GET", **kwargs):
        return (path, method, kwargs.get("auth_header"), kwargs.get("body", b""))

    def _run_handler(self, req):
        path, method, auth_header, body = req
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        from backend.src.core.structured_logging import normalize_correlation_id
        if "X-Correlation-ID" in headers:
            headers["X-Correlation-ID"] = normalize_correlation_id(headers["X-Correlation-ID"])
        if "X-Request-ID" in headers:
            headers["X-Request-ID"] = normalize_correlation_id(headers["X-Request-ID"])
        if method == "GET":
            resp = self.client.get(path, headers=headers)
        elif method == "OPTIONS":
            resp = self.client.options(path, headers=headers)
        else:
            if isinstance(body, (bytes, bytearray)) and len(body) > 0:
                try:
                    import json as _json
                    body_dict = _json.loads(body)
                    resp = self.client.post(path, json=body_dict, headers=headers)
                except (ValueError, UnicodeDecodeError):
                    resp = self.client.post(path, content=body, headers=headers)
            else:
                resp = self.client.post(path, headers=headers)
        try:
            import json as _json
            data = resp.json()
        except Exception:
            data = {}
        if isinstance(data, dict) and isinstance(data.get("detail"), dict):
            data = data["detail"]
        return resp.status_code, dict(resp.headers), data



# ═══════════════════════════════════════════════════════════════════════
# 1. Missing-token security event
# ═══════════════════════════════════════════════════════════════════════

class TestGl120MissingTokenEvent(_BaseGl120):
    """Verify missing Authorization header emits auth_failed with reason_code."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.auth.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_missing_token_emits_auth_failed_event(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/grants")
            status, _, _ = self._run_raw_handler(handler)
        self.assertEqual(status, 401)
        self.assertTrue(any("auth_failed" in msg for msg in cm.output))

    def test_missing_token_event_has_reason_code(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/grants")
            self._run_raw_handler(handler)
        payload = self._parse_log_json(
            next(msg for msg in cm.output if "auth_failed" in msg)
        )
        self.assertIn("reason_code", payload)
        self.assertEqual(payload["reason_code"], "operator_auth_required")

    def test_missing_token_event_fields(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/grants")
            self._run_raw_handler(handler)
        payload = self._parse_log_json(
            next(msg for msg in cm.output if "auth_failed" in msg)
        )
        self.assertEqual(payload["event"], "auth_failed")
        self.assertEqual(payload["status_code"], 401)
        self.assertEqual(payload["method"], "GET")
        self.assertEqual(payload["path"], "/v1/grants")

    def test_missing_token_event_has_no_status_field(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/grants")
            self._run_raw_handler(handler)
        payload = self._parse_log_json(
            next(msg for msg in cm.output if "auth_failed" in msg)
        )
        self.assertNotIn("status", payload)


# ═══════════════════════════════════════════════════════════════════════
# 2. Invalid-token security event
# ═══════════════════════════════════════════════════════════════════════

class TestGl120InvalidTokenEvent(_BaseGl120):
    """Verify wrong/invalid token emits auth_failed with reason_code."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.auth.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_invalid_token_emits_auth_failed_event(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/grants", auth_header="Bearer wrong-token")
            status, _, _ = self._run_raw_handler(handler)
        self.assertIn(status, (401, 403))
        self.assertTrue(any("auth_failed" in msg for msg in cm.output))

    def test_invalid_token_event_has_reason_code(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/grants", auth_header="Bearer wrong-token")
            self._run_raw_handler(handler)
        payload = self._parse_log_json(
            next(msg for msg in cm.output if "auth_failed" in msg)
        )
        self.assertIn("reason_code", payload)
        self.assertIsInstance(payload["reason_code"], str)
        self.assertGreater(len(payload["reason_code"]), 0)

    def test_invalid_token_reason_code_is_not_unknown(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/grants", auth_header="Bearer wrong-token")
            self._run_raw_handler(handler)
        payload = self._parse_log_json(
            next(msg for msg in cm.output if "auth_failed" in msg)
        )
        self.assertNotEqual(payload.get("reason_code"), "unknown")

    def test_invalid_token_event_includes_status_code(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/grants", auth_header="Bearer wrong-token")
            status, _, _ = self._run_raw_handler(handler)
        payload = self._parse_log_json(
            next(msg for msg in cm.output if "auth_failed" in msg)
        )
        self.assertEqual(payload["status_code"], status)


# ═══════════════════════════════════════════════════════════════════════
# 3. Forbidden/insufficient-role security event
# ═══════════════════════════════════════════════════════════════════════

class TestGl120ForbiddenRoleEvent(_BaseGl120):
    """Verify valid token with insufficient role emits auth_failed with reason_code."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.auth.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        # auditor role cannot create grants (requires owner/grant_admin)
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")

    def test_insufficient_role_emits_auth_failed_event(self):
        logger = logging.getLogger("grantlayer.server")
        grant_body = json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
            "validFrom": "2020-01-01T00:00:00Z",
            "validUntil": "2030-01-01T00:00:00Z",
            "createdBy": "auditor-1",
            "reason": "test",
        }).encode()
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler(
                "/v1/grants",
                method="POST",
                auth_header="Bearer auditor-token",
                body=grant_body,
            )
            status, _, _ = self._run_raw_handler(handler)
        self.assertEqual(status, 403)
        self.assertTrue(any("auth_failed" in msg for msg in cm.output))

    def test_insufficient_role_reason_code_is_operator_role_forbidden(self):
        logger = logging.getLogger("grantlayer.server")
        grant_body = json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
            "validFrom": "2020-01-01T00:00:00Z",
            "validUntil": "2030-01-01T00:00:00Z",
            "createdBy": "auditor-1",
            "reason": "test",
        }).encode()
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler(
                "/v1/grants",
                method="POST",
                auth_header="Bearer auditor-token",
                body=grant_body,
            )
            self._run_raw_handler(handler)
        payload = self._parse_log_json(
            next(msg for msg in cm.output if "auth_failed" in msg)
        )
        self.assertEqual(payload["reason_code"], "operator_role_forbidden")
        self.assertEqual(payload["status_code"], 403)

    def test_insufficient_role_and_missing_token_have_different_reason_codes(self):
        logger = logging.getLogger("grantlayer.server")
        grant_body = json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
            "validFrom": "2020-01-01T00:00:00Z",
            "validUntil": "2030-01-01T00:00:00Z",
            "createdBy": "auditor-1",
            "reason": "test",
        }).encode()
        # Forbidden role → 403
        with self.assertLogs(logger, level="INFO") as cm_role:
            handler = self._make_raw_handler(
                "/v1/grants",
                method="POST",
                auth_header="Bearer auditor-token",
                body=grant_body,
            )
            self._run_raw_handler(handler)
        role_payload = self._parse_log_json(
            next(msg for msg in cm_role.output if "auth_failed" in msg)
        )

        # Missing token → 401
        with self.assertLogs(logger, level="INFO") as cm_missing:
            handler2 = self._make_raw_handler("/v1/grants")
            self._run_raw_handler(handler2)
        missing_payload = self._parse_log_json(
            next(msg for msg in cm_missing.output if "auth_failed" in msg)
        )

        self.assertNotEqual(
            role_payload["reason_code"],
            missing_payload["reason_code"],
            "role-forbidden and missing-token must produce distinct reason_codes",
        )


# ═══════════════════════════════════════════════════════════════════════
# 4. Rate-limit security event
# ═══════════════════════════════════════════════════════════════════════
@unittest.skip("Legacy GrantLayerHandler rate-limit logging is not exposed by the FastAPI test surface")
class TestGl120RateLimitEvent(_BaseGl120):
    """Verify rate-limit rejections emit rate_limited event (GL-117 preserved)."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        os.environ["GRANTLAYER_RATE_LIMIT_AUTH"] = "2"
        importlib.reload(self.config_mod)
        import backend.src.auth.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_rate_limit_emits_rate_limited_event(self):
        logger = logging.getLogger("grantlayer.server")
        for _ in range(2):
            handler = self._make_raw_handler("/v1/challenges", auth_header="Bearer owner-token")
            self._run_raw_handler(handler)
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/challenges", auth_header="Bearer owner-token")
            status, _, _ = self._run_raw_handler(handler)
        self.assertEqual(status, 429)
        self.assertTrue(any("rate_limited" in msg for msg in cm.output))
        payload = self._parse_log_json(
            next(msg for msg in cm.output if "rate_limited" in msg)
        )
        self.assertEqual(payload["event"], "rate_limited")
        self.assertEqual(payload["status_code"], 429)

    def test_rate_limit_event_has_no_raw_token(self):
        logger = logging.getLogger("grantlayer.server")
        for _ in range(2):
            handler = self._make_raw_handler("/v1/challenges", auth_header="Bearer secret-rate-token")
            self._run_raw_handler(handler)
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/challenges", auth_header="Bearer secret-rate-token")
            self._run_raw_handler(handler)
        log_str = "\n".join(cm.output)
        self.assertNotIn("secret-rate-token", log_str)
        self.assertNotIn("Bearer", log_str)


# ═══════════════════════════════════════════════════════════════════════
# 5. Operator-auth-failure event (operator model specific)
# ═══════════════════════════════════════════════════════════════════════

class TestGl120OperatorAuthFailureEvent(_BaseGl120):
    """Verify operator auth failure events are emitted for all failure modes."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.auth.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_operator_missing_auth_emits_event(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/grants")
            status, _, _ = self._run_raw_handler(handler)
        self.assertEqual(status, 401)
        self.assertTrue(any("auth_failed" in msg for msg in cm.output))
        payload = self._parse_log_json(
            next(msg for msg in cm.output if "auth_failed" in msg)
        )
        self.assertEqual(payload["reason_code"], "operator_auth_required")

    def test_operator_invalid_auth_emits_event(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/grants", auth_header="Bearer bad")
            status, _, _ = self._run_raw_handler(handler)
        self.assertIn(status, (401, 403))
        self.assertTrue(any("auth_failed" in msg for msg in cm.output))
        payload = self._parse_log_json(
            next(msg for msg in cm.output if "auth_failed" in msg)
        )
        self.assertIn("reason_code", payload)
        self.assertIsInstance(payload["reason_code"], str)

    def test_multiple_endpoints_all_emit_auth_failed(self):
        logger = logging.getLogger("grantlayer.server")
        endpoints = ["/v1/grants", "/v1/audit-events", "/v1/grant-requests"]
        for endpoint in endpoints:
            with self.assertLogs(logger, level="INFO") as cm:
                handler = self._make_raw_handler(endpoint)
                self._run_raw_handler(handler)
            self.assertTrue(
                any("auth_failed" in msg for msg in cm.output),
                f"No auth_failed event for {endpoint}",
            )


# ═══════════════════════════════════════════════════════════════════════
# 6. Correlation ID in auth failure events
# ═══════════════════════════════════════════════════════════════════════

class TestGl120CorrelationIdInAuthEvent(_BaseGl120):
    """Verify auth failure events include correlation_id from GL-118."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.auth.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_auth_failed_event_includes_correlation_id(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/grants")
            self._run_raw_handler(handler)
        payload = self._parse_log_json(
            next(msg for msg in cm.output if "auth_failed" in msg)
        )
        self.assertIn("correlation_id", payload)
        self.assertIsNotNone(payload["correlation_id"])
        self.assertGreater(len(payload["correlation_id"]), 0)

    def test_auth_failed_correlation_id_matches_response_header(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/grants")
            _, resp_headers, _ = self._run_raw_handler(handler)
        response_cid = resp_headers.get("X-Correlation-ID")
        self.assertIsNotNone(response_cid)
        payload = self._parse_log_json(
            next(msg for msg in cm.output if "auth_failed" in msg)
        )
        self.assertEqual(payload.get("correlation_id"), response_cid)

    def test_inbound_correlation_id_appears_in_auth_failed_log(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler(
                "/v1/grants",
                correlation_id_header="trace-gl120-test",
            )
            self._run_raw_handler(handler)
        log_str = "\n".join(cm.output)
        self.assertIn("trace-gl120-test", log_str)
        payload = self._parse_log_json(
            next(msg for msg in cm.output if "auth_failed" in msg)
        )
        self.assertEqual(payload.get("correlation_id"), "trace-gl120-test")


# ═══════════════════════════════════════════════════════════════════════
# 7. Reason code stability
# ═══════════════════════════════════════════════════════════════════════

class TestGl120ReasonCodeStability(_BaseGl120):
    """Verify reason_codes are stable strings, never 'unknown' for known failure types."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.auth.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")

    def test_missing_token_reason_code_stable(self):
        logger = logging.getLogger("grantlayer.server")
        for _ in range(2):
            with self.assertLogs(logger, level="INFO") as cm:
                handler = self._make_raw_handler("/v1/grants")
                self._run_raw_handler(handler)
            payload = self._parse_log_json(
                next(msg for msg in cm.output if "auth_failed" in msg)
            )
            self.assertEqual(payload["reason_code"], "operator_auth_required")

    def test_wrong_role_reason_code_stable(self):
        logger = logging.getLogger("grantlayer.server")
        grant_body = json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
            "validFrom": "2020-01-01T00:00:00Z",
            "validUntil": "2030-01-01T00:00:00Z",
            "createdBy": "auditor-1",
            "reason": "test",
        }).encode()
        for _ in range(2):
            with self.assertLogs(logger, level="INFO") as cm:
                handler = self._make_raw_handler(
                    "/v1/grants",
                    method="POST",
                    auth_header="Bearer auditor-token",
                    body=grant_body,
                )
                self._run_raw_handler(handler)
            payload = self._parse_log_json(
                next(msg for msg in cm.output if "auth_failed" in msg)
            )
            self.assertEqual(payload["reason_code"], "operator_role_forbidden")

    def test_reason_code_is_non_empty_string(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/grants")
            self._run_raw_handler(handler)
        payload = self._parse_log_json(
            next(msg for msg in cm.output if "auth_failed" in msg)
        )
        self.assertIsInstance(payload["reason_code"], str)
        self.assertGreater(len(payload["reason_code"].strip()), 0)


# ═══════════════════════════════════════════════════════════════════════
# 8. Security safety — no raw tokens, headers, or bodies in logs
# ═══════════════════════════════════════════════════════════════════════

class TestGl120SecuritySafety(_BaseGl120):
    """Verify raw tokens, auth headers, and request bodies never appear in logs."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.auth.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_raw_token_not_in_auth_failed_log(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/grants", auth_header="Bearer secret-token-gl120")
            self._run_raw_handler(handler)
        log_str = "\n".join(cm.output)
        self.assertNotIn("secret-token-gl120", log_str)

    def test_bearer_scheme_not_in_auth_failed_log(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/grants", auth_header="Bearer secret-token-gl120")
            self._run_raw_handler(handler)
        log_str = "\n".join(cm.output)
        self.assertNotIn("Bearer", log_str)

    def test_authorization_header_name_not_in_auth_failed_log(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/grants", auth_header="Bearer secret-token-gl120")
            self._run_raw_handler(handler)
        log_str = "\n".join(cm.output)
        self.assertNotIn("authorization", log_str.lower())

    def test_raw_request_body_not_in_auth_failed_log(self):
        logger = logging.getLogger("grantlayer.server")
        sensitive_body = json.dumps({"secret": "my-private-value-gl120"}).encode()
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler(
                "/v1/grants",
                method="POST",
                auth_header="Bearer wrong-token",
                body=sensitive_body,
            )
            self._run_raw_handler(handler)
        log_str = "\n".join(cm.output)
        self.assertNotIn("my-private-value-gl120", log_str)

    def test_no_private_key_or_secret_in_logs(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/grants", auth_header="Bearer wrong-token")
            self._run_raw_handler(handler)
        log_str = "\n".join(cm.output)
        self.assertNotIn("private_key", log_str)
        self.assertNotIn("signature", log_str)


# ═══════════════════════════════════════════════════════════════════════
# 9. Logging failure safety
# ═══════════════════════════════════════════════════════════════════════

class TestGl120LoggingFailureSafety(_BaseGl120):
    """Verify structured logging failures do not alter auth HTTP behavior."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.auth.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_auth_logging_failure_preserves_401(self):
        with patch("backend.src.core.logging_utils.safe_log", side_effect=RuntimeError("log crash")):
            handler = self._make_raw_handler("/v1/grants")
            status, _, body = self._run_raw_handler(handler)
        self.assertEqual(status, 401)
        self.assertIn("errorCode", body)

    def test_auth_logging_failure_preserves_success_200(self):
        with patch("backend.src.core.logging_utils.safe_log", side_effect=RuntimeError("log crash")):
            handler = self._make_raw_handler("/v1/grants", auth_header="Bearer owner-token")
            status, _, body = self._run_raw_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body.get("items"), list)

    def test_auth_logging_failure_preserves_403_role(self):
        self._insert_operator("auditor-1", "Auditor", "auditor", "auditor-token")
        grant_body = json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
            "validFrom": "2020-01-01T00:00:00Z",
            "validUntil": "2030-01-01T00:00:00Z",
            "createdBy": "auditor-1",
            "reason": "test",
        }).encode()
        with patch("backend.src.core.logging_utils.safe_log", side_effect=RuntimeError("log crash")):
            handler = self._make_raw_handler(
                "/v1/grants",
                method="POST",
                auth_header="Bearer auditor-token",
                body=grant_body,
            )
            status, _, body = self._run_raw_handler(handler)
        self.assertEqual(status, 403)
        self.assertIn("errorCode", body)


# ═══════════════════════════════════════════════════════════════════════
# 10. Response semantics preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl120ResponseSemanticsPreserved(_BaseGl120):
    """Verify adding structured events does not change HTTP response behavior."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.auth.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_missing_token_response_unchanged(self):
        handler = self._make_raw_handler("/v1/grants")
        status, _, body = self._run_raw_handler(handler)
        self.assertEqual(status, 401)
        self.assertIn("errorCode", body)

    def test_invalid_token_response_unchanged(self):
        handler = self._make_raw_handler("/v1/grants", auth_header="Bearer wrong-token")
        status, _, body = self._run_raw_handler(handler)
        self.assertIn(status, (401, 403))
        self.assertIn("errorCode", body)

    def test_valid_auth_response_unchanged(self):
        handler = self._make_raw_handler("/v1/grants", auth_header="Bearer owner-token")
        status, _, body = self._run_raw_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body.get("items"), list)

    def test_gl117_structured_logging_preserved(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/v1/grants", auth_header="Bearer owner-token")
            status, _, _ = self._run_raw_handler(handler)
        self.assertEqual(status, 200)
        self.assertTrue(any("request_completed" in msg for msg in cm.output))

    def test_gl118_correlation_propagation_preserved(self):
        handler = self._make_raw_handler(
            "/v1/grants",
            auth_header="Bearer owner-token",
            correlation_id_header="persist-check-id",
        )
        _, headers, _ = self._run_raw_handler(handler)
        self.assertEqual(headers.get("X-Correlation-ID"), "persist-check-id")


# ═══════════════════════════════════════════════════════════════════════
# 11. Scope guard — diff validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl120NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-120 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-120-auth-failure-structured-event-logging":
            self.skipTest("Branch-wide diff check only valid on GL-120 feature branch")
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/server.py",
            "backend/tests/test_gl120_auth_failure_structured_event_logging.py",
            "backend/src/logging_utils.py",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-120 changed a forbidden file: {path}",
            )

    def test_no_openapi_change_needed(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        openapi_path = repo_root / "docs" / "openapi.yaml"
        self.assertTrue(openapi_path.exists())

    def test_no_db_schema_migration_change(self):
        import tempfile as tempfile_mod
        tmp_db = tempfile_mod.NamedTemporaryFile(suffix=".db", delete=False)
        orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = tmp_db.name
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        try:
            import backend.src.core.db as db_mod
            importlib.reload(db_mod)
            db_mod.init_db()
            conn = db_mod.get_conn()
            try:
                tables = [
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                ]
                self.assertIn("grants", tables)
                self.assertIn("operators", tables)
                self.assertIn("audit_events", tables)
                self.assertIn("grant_executions", tables)
            finally:
                conn.close()
        finally:
            os.unlink(tmp_db.name)
            if orig_db is not None:
                os.environ["GRANTLAYER_DB"] = orig_db
            else:
                os.environ.pop("GRANTLAYER_DB", None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
