"""GL-037-C2 — Auditor Report API Endpoint tests.

Covers endpoint routing, auth, response shape, 404 handling,
grant/grant-request linkage, findings/conclusion, provenance summary
embedding, includeRawEvidence flag, and secrets safety.
"""

import os
import sys
import unittest
import tempfile
import importlib
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestAuditorReportAPI(unittest.TestCase):
    """Tests for GET /auditor/reports/executions/{executionId} endpoint."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        self._orig_url = os.environ.get("GRANTLAYER_DATABASE_URL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")

        os.environ["GRANTLAYER_DB"] = self.tmp_db.name
        if self._orig_url is not None:
            os.environ.pop("GRANTLAYER_DATABASE_URL", None)
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "test-admin-token"
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        self.db = db_mod
        self.db.init_db()

        from backend.src.policy.provenance import record_provenance_event
        from backend.src.grants.grant_executions import create_grant_execution
        from backend.src.core.models import GrantExecution, Grant, GrantRequest
        from backend.src.grants.grants import create_grant
        from backend.src.grants.grant_requests import create_grant_request
        from backend.src.evidence import evidence_persistence as evp
        from backend.src.evidence.evidence_bundle import build_evidence_bundle
        from backend.src.auth import operators as ops

        self.record_event = record_provenance_event
        self.create_execution = create_grant_execution
        self.GrantExecution = GrantExecution
        self.Grant = Grant
        self.GrantRequest = GrantRequest
        self.create_grant = create_grant
        self.create_grant_request = create_grant_request
        self.evp = evp
        self.build_evidence = build_evidence_bundle
        self.ops = ops

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)
        if self._orig_url is not None:
            os.environ["GRANTLAYER_DATABASE_URL"] = self._orig_url
        else:
            os.environ.pop("GRANTLAYER_DATABASE_URL", None)
        if self._orig_admin_token is not None:
            os.environ["GRANTLAYER_ADMIN_TOKEN"] = self._orig_admin_token
        else:
            os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        if self._orig_enable_operator is not None:
            os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = self._orig_enable_operator
        else:
            os.environ.pop("GRANTLAYER_ENABLE_OPERATOR_MODEL", None)
        if self._orig_require_admin is not None:
            os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = self._orig_require_admin
        else:
            os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)

    def _make_execution(self, execution_id: str, grant_id: str | None = None, result: str = "succeeded", error_code: str | None = None):
        ex = self.GrantExecution(
            id=execution_id,
            action="read",
            resource="doc-1",
            grant_id=grant_id,
            result=result,
            error_code=error_code,
            executed_at="2026-05-11T10:00:00Z",
        )
        self.create_execution(ex, tenant_id="demo")
        return ex

    def _archive_evidence(self, execution_id: str, stored_by: str | None = None):
        bundle = self.build_evidence(execution_id)
        if bundle is None:
            raise RuntimeError("build_evidence_bundle returned None")
        self.evp.store_bundle(execution_id, bundle, stored_by=stored_by)

    def _insert_operator(self, op_id, name, role, token):
        import backend.src.core.db as db_mod
        conn = db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators (id, name, role, token_hash, active, created_at)
                   VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)""",
                (op_id, name, role, self.ops.hash_token(token)),
            )
            conn.commit()
        finally:
            conn.close()

    def _make_client(self):
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        import backend.src.core.db as bk_db
        import backend.src.core.config as config_mod
        import backend.src.auth.auth as auth_mod
        bk_db.DB_PATH_OR_URL = self.tmp_db.name
        bk_db.DB_PATH = self.tmp_db.name
        importlib.reload(config_mod)
        importlib.reload(auth_mod)
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        return TestClient(create_app(), raise_server_exceptions=False)

    def _run_handler(self, path, method="GET", auth=None):
        headers = {}
        if auth:
            headers["Authorization"] = auth
        client = self._make_client()
        if method == "GET":
            resp = client.get(path, headers=headers)
        else:
            resp = client.post(path, headers=headers)
        try:
            return resp.status_code, resp.json()
        except Exception:
            return resp.status_code, None

    # ── Endpoint routing ────────────────────────────────────────
    def test_endpoint_exists_and_returns_404_for_unknown_execution(self):
        status, body = self._run_handler(
            "/v1/auditor/reports/executions/nonexistent-id",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 404)
        self.assertIn("errorCode", body)
        self.assertEqual(body["errorCode"], "execution_not_found")

    def test_endpoint_returns_200_for_existing_execution(self):
        self._make_execution("ex-api-1", grant_id="g-api-1")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-api-1",
            grant_id="g-api-1",
        )
        status, body = self._run_handler(
            "/v1/auditor/reports/executions/ex-api-1",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["reportType"], "auditor_report")
        required_fields = {
            "reportId", "reportType", "scope", "generatedAt",
            "findings", "conclusion", "provenanceSummary",
            "grant", "grantRequest",
        }
        self.assertTrue(required_fields.issubset(body.keys()))
        self.assertEqual(body["scope"]["executionId"], "ex-api-1")
        self.assertEqual(body["scope"]["grantId"], "g-api-1")

    # ── Auth ────────────────────────────────────────────────────
    def test_endpoint_requires_admin_token_when_operator_disabled(self):
        self._make_execution("ex-auth-1")
        status, body = self._run_handler("/v1/auditor/reports/executions/ex-auth-1")
        self.assertEqual(status, 401)
        status, body = self._run_handler(
            "/v1/auditor/reports/executions/ex-auth-1",
            auth="Bearer wrong-token"
        )
        self.assertEqual(status, 403)

    def test_endpoint_accepts_operator_roles_when_operator_enabled(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("auditor-1", "Auditor One", "auditor", "auditor-token")

        self._make_execution("ex-auth-2")
        status, body = self._run_handler(
            "/v1/auditor/reports/executions/ex-auth-2",
            auth="Bearer auditor-token"
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["reportType"], "auditor_report")

    def test_endpoint_rejects_demo_operator_role(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("demo-op-1", "Demo Op", "demo_operator", "demo-token")

        self._make_execution("ex-auth-3")
        status, body = self._run_handler(
            "/v1/auditor/reports/executions/ex-auth-3",
            auth="Bearer demo-token"
        )
        self.assertEqual(status, 403)

    # ── Response shape ──────────────────────────────────────────
    def test_response_contains_provenance_summary_embedded(self):
        self._make_execution("ex-shape-1")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-shape-1",
        )
        status, body = self._run_handler(
            "/v1/auditor/reports/executions/ex-shape-1",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        summary = body["provenanceSummary"]
        self.assertIsNotNone(summary)
        self.assertEqual(summary["executionId"], "ex-shape-1")
        self.assertEqual(len(summary["provenanceEvents"]), 1)
        self.assertEqual(summary["provenanceEvents"][0]["eventType"], "policy_evaluated")

    def test_response_contains_grant_when_grant_exists(self):
        grant = self.Grant(
            id="g-link",
            subject_id="sub-1",
            role="tech",
            action="read",
            resource="doc-1",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2026-12-31T23:59:59Z",
            created_by="admin",
            reason="Test",
            signature="sigsig",
            signing_key_id="demo-ed25519-v1",
            payload_hash="abcd1234" * 8,
        )
        self.create_grant(grant, tenant_id="demo")
        self._make_execution("ex-grant", grant_id="g-link")
        status, body = self._run_handler(
            "/v1/auditor/reports/executions/ex-grant",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        self.assertIsNotNone(body["grant"])
        self.assertEqual(body["grant"]["id"], "g-link")
        self.assertTrue(body["grant"]["signaturePresent"])
        self.assertNotIn("signature", body["grant"])

    def test_response_contains_grant_request_when_request_exists(self):
        grant = self.Grant(
            id="g-req",
            subject_id="sub-1",
            role="tech",
            action="read",
            resource="doc-1",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2026-12-31T23:59:59Z",
            created_by="admin",
            reason="Test",
        )
        self.create_grant(grant, tenant_id="demo")
        req = self.GrantRequest(
            id="req-1",
            subject_id="sub-1",
            role="tech",
            action="read",
            resource="doc-1",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2026-12-31T23:59:59Z",
            requested_by="requester",
            reason="Need access",
            status="approved",
            approved_by="approver",
            approved_at="2026-01-01T10:00:00Z",
            grant_id="g-req",
        )
        self.create_grant_request(req, tenant_id="demo")
        from backend.src.core.db import execute
        execute(
            "UPDATE grant_requests SET grant_id = ? WHERE id = ?",
            ("g-req", "req-1"),
        )
        self._make_execution("ex-req", grant_id="g-req")
        status, body = self._run_handler(
            "/v1/auditor/reports/executions/ex-req",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        self.assertIsNotNone(body["grantRequest"])
        self.assertEqual(body["grantRequest"]["id"], "req-1")
        self.assertEqual(body["grantRequest"]["status"], "approved")

    def test_response_findings_and_conclusion_attention_required(self):
        self._make_execution("ex-find-attn")
        status, body = self._run_handler(
            "/v1/auditor/reports/executions/ex-find-attn",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        self.assertIn("missing_evidence", " ".join(body["findings"]))
        self.assertEqual(body["conclusion"], "attention_required")

    def test_response_findings_and_conclusion_clean(self):
        self._make_execution("ex-find-clean")
        self._archive_evidence("ex-find-clean")
        record = self.evp.get_bundle_by_execution("ex-find-clean")
        self.evp.update_verification_status(record.id, "valid")
        status, body = self._run_handler(
            "/v1/auditor/reports/executions/ex-find-clean",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["conclusion"], "clean")
        self.assertNotIn("unverified_evidence", " ".join(body["findings"]))
        self.assertNotIn("missing_evidence", " ".join(body["findings"]))

    # ── Secrets safety ──────────────────────────────────────────
    def test_response_does_not_expose_secrets(self):
        self._make_execution("ex-sec-1")
        self._archive_evidence("ex-sec-1")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-sec-1",
        )
        status, body = self._run_handler(
            "/v1/auditor/reports/executions/ex-sec-1",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        raw = json.dumps(body)
        for forbidden in ["GRANTLAYER_ADMIN_TOKEN", "password", "secret", "token", "private"]:
            self.assertNotIn(forbidden, raw.lower(), f"Secret leak detected: {forbidden}")

    # ── includeRawEvidence flag ─────────────────────────────────
    def test_include_raw_evidence_false_omits_bundle(self):
        self._make_execution("ex-raw-off")
        self._archive_evidence("ex-raw-off")
        status, body = self._run_handler(
            "/v1/auditor/reports/executions/ex-raw-off?includeRawEvidence=false",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        self.assertNotIn("evidenceBundle", body)

    def test_include_raw_evidence_true_includes_bundle(self):
        self._make_execution("ex-raw-on")
        self._archive_evidence("ex-raw-on")
        status, body = self._run_handler(
            "/v1/auditor/reports/executions/ex-raw-on?includeRawEvidence=true",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        self.assertIn("evidenceBundle", body)
        self.assertIsNotNone(body["evidenceBundle"])
        self.assertEqual(body["evidenceBundle"]["executionId"], "ex-raw-on")

    def test_include_raw_evidence_true_none_when_no_archive(self):
        self._make_execution("ex-raw-none")
        status, body = self._run_handler(
            "/v1/auditor/reports/executions/ex-raw-none?includeRawEvidence=true",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        self.assertIn("evidenceBundle", body)
        self.assertIsNone(body["evidenceBundle"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
