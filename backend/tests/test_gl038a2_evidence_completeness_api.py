"""GL-038-A2 — Evidence Completeness API Endpoint tests.

Covers endpoint routing, auth, response shape, 404 handling,
includeDetails flag, scoring logic, and secrets safety.
"""

import os
import sys
import unittest
import tempfile
import importlib
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestEvidenceCompletenessAPI(unittest.TestCase):
    """Tests for GET /evidence/executions/{executionId}/completeness endpoint."""

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
        from backend.src.core.models import GrantExecution, Grant
        from backend.src.grants.grants import create_grant
        from backend.src.evidence import evidence_persistence as evp
        from backend.src.evidence.evidence_bundle import build_evidence_bundle
        from backend.src.auth import operators as ops

        self.record_event = record_provenance_event
        self.create_execution = create_grant_execution
        self.GrantExecution = GrantExecution
        self.Grant = Grant
        self.create_grant = create_grant
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

    def _make_execution(self, execution_id: str, grant_id: str | None = None):
        ex = self.GrantExecution(
            id=execution_id,
            action="read",
            resource="doc-1",
            grant_id=grant_id,
            result="succeeded",
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
                   VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                   ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, role=EXCLUDED.role, token_hash=EXCLUDED.token_hash, active=EXCLUDED.active""",
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
            "/v1/evidence/executions/nonexistent-id/completeness",
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
            "/v1/evidence/executions/ex-api-1/completeness",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["reportType"], "evidence_completeness")
        self.assertEqual(body["executionId"], "ex-api-1")

    # ── Auth ────────────────────────────────────────────────────
    def test_endpoint_requires_admin_token_when_operator_disabled(self):
        self._make_execution("ex-auth-1")
        status, body = self._run_handler("/v1/evidence/executions/ex-auth-1/completeness")
        self.assertEqual(status, 401)
        status, body = self._run_handler(
            "/v1/evidence/executions/ex-auth-1/completeness",
            auth="Bearer wrong-token"
        )
        self.assertEqual(status, 403)

    def test_endpoint_accepts_operator_roles_when_operator_enabled(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("auditor-1", "Auditor One", "auditor", "auditor-token")

        self._make_execution("ex-auth-2")
        status, body = self._run_handler(
            "/v1/evidence/executions/ex-auth-2/completeness",
            auth="Bearer auditor-token"
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["reportType"], "evidence_completeness")

    def test_endpoint_rejects_demo_operator_role(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("demo-op-1", "Demo Op", "demo_operator", "demo-token")

        self._make_execution("ex-auth-3")
        status, body = self._run_handler(
            "/v1/evidence/executions/ex-auth-3/completeness",
            auth="Bearer demo-token"
        )
        self.assertEqual(status, 403)

    # ── Response shape ──────────────────────────────────────────
    def test_response_contains_minimum_fields(self):
        self._make_execution("ex-shape-1", grant_id="g-shape-1")
        grant = self.Grant(
            id="g-shape-1",
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
        self._archive_evidence("ex-shape-1")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-shape-1",
            grant_id="g-shape-1",
        )
        from backend.src.evidence import evidence_verification as ev_mod
        importlib.reload(ev_mod)
        ev_mod.verify_execution("ex-shape-1")

        status, body = self._run_handler(
            "/v1/evidence/executions/ex-shape-1/completeness",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        required_fields = {
            "reportType", "reportVersion", "executionId", "grantId",
            "generatedAt", "completenessScore", "completenessStatus",
            "checks", "missingEvidence", "complianceGaps",
            "warnings", "auditReadiness", "evidence", "verification", "provenance",
        }
        self.assertTrue(required_fields.issubset(body.keys()))
        self.assertEqual(body["reportType"], "evidence_completeness")
        self.assertEqual(body["reportVersion"], "gl-038-a1")

    def test_response_contains_checks_when_include_details_true(self):
        self._make_execution("ex-details-1")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-details-1",
        )
        status, body = self._run_handler(
            "/v1/evidence/executions/ex-details-1/completeness",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        self.assertIsNotNone(body["checks"])
        self.assertIn("auditorReportAvailable", body["checks"])

    def test_response_omits_checks_when_include_details_false(self):
        self._make_execution("ex-details-0")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-details-0",
        )
        status, body = self._run_handler(
            "/v1/evidence/executions/ex-details-0/completeness?includeDetails=false",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        self.assertIsNone(body["checks"])
        self.assertIsNone(body["provenance"]["events"])

    # ── Scoring logic via API ──────────────────────────────────
    def test_response_score_for_complete_data(self):
        self._make_execution("ex-complete", grant_id="g-complete")
        grant = self.Grant(
            id="g-complete",
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
        self._archive_evidence("ex-complete")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-complete",
            grant_id="g-complete",
        )
        from backend.src.evidence import evidence_verification as ev_mod
        importlib.reload(ev_mod)
        ev_mod.verify_execution("ex-complete")

        status, body = self._run_handler(
            "/v1/evidence/executions/ex-complete/completeness",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        self.assertGreaterEqual(body["completenessScore"], 90)
        self.assertEqual(body["completenessStatus"], "complete")
        self.assertEqual(body["auditReadiness"], "ready")
        self.assertEqual(body["complianceGaps"], [])

    def test_response_score_for_missing_evidence(self):
        self._make_execution("ex-missing")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-missing",
        )
        status, body = self._run_handler(
            "/v1/evidence/executions/ex-missing/completeness",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        self.assertIn("missing_evidence", body["complianceGaps"])
        self.assertLess(body["completenessScore"], 100)

    # ── Secrets safety ──────────────────────────────────────────
    def test_response_does_not_expose_secrets(self):
        self._make_execution("ex-sec-1", grant_id="g-sec-1")
        grant = self.Grant(
            id="g-sec-1",
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
        self._archive_evidence("ex-sec-1")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-sec-1",
            grant_id="g-sec-1",
        )
        status, body = self._run_handler(
            "/v1/evidence/executions/ex-sec-1/completeness",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        raw = json.dumps(body)
        for forbidden in ["GRANTLAYER_ADMIN_TOKEN", "password", "secret", "token", "private"]:
            self.assertNotIn(forbidden, raw.lower(), f"Secret leak detected: {forbidden}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
