"""GL-037-B2 — Decision Provenance Summary API Endpoint tests.

Covers endpoint routing, auth, response shape, 404 handling,
provenance events integration, and secrets safety.
"""

import os
import sys
import unittest
import tempfile
import importlib
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestProvenanceSummaryAPI(unittest.TestCase):
    """Tests for GET /provenance/executions/{executionId}/summary endpoint."""

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
        # Set a known admin token for legacy-auth tests
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "test-admin-token"
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"

        import backend.src.db as db_mod
        importlib.reload(db_mod)
        self.db = db_mod
        self.db.init_db()

        from backend.src.provenance import record_provenance_event
        from backend.src.grant_executions import create_grant_execution
        from backend.src.models import GrantExecution
        from backend.src import evidence_persistence as evp
        from backend.src.evidence_bundle import build_evidence_bundle
        from backend.src import operators as ops

        self.record_event = record_provenance_event
        self.create_execution = create_grant_execution
        self.GrantExecution = GrantExecution
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
        self.create_execution(ex)
        return ex

    def _archive_evidence(self, execution_id: str, stored_by: str | None = None):
        bundle = self.build_evidence(execution_id)
        if bundle is None:
            raise RuntimeError("build_evidence_bundle returned None")
        self.evp.store_bundle(execution_id, bundle, stored_by=stored_by)

    def _insert_operator(self, op_id, name, role, token):
        import backend.src.db as db_mod
        conn = db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators (id, name, role, token_hash, active, created_at)
                   VALUES (?, ?, ?, ?, 1, datetime('now'))""",
                (op_id, name, role, self.ops.hash_token(token)),
            )
            conn.commit()
        finally:
            conn.close()

    def _make_client(self):
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        import backend.src.db as bk_db
        import backend.src.config as config_mod
        import backend.src.auth as auth_mod
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
            "/provenance/executions/nonexistent-id/summary",
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
            "/provenance/executions/ex-api-1/summary",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["executionId"], "ex-api-1")
        self.assertEqual(body["grantId"], "g-api-1")
        required_fields = {
            "executionId", "grantId", "execution", "evidence",
            "verification", "provenanceEvents", "timeline",
            "warnings", "generatedAt",
        }
        self.assertTrue(required_fields.issubset(body.keys()))

    def test_endpoint_returns_summary_without_execution(self):
        """If no execution but events exist, endpoint still returns 200."""
        self.record_event(
            event_type="grant_executed",
            actor_type="agent",
            actor_id="agent-1",
            action="execute",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-api-2",
            grant_id="g-api-2",
        )
        status, body = self._run_handler(
            "/provenance/executions/ex-api-2/summary",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["executionId"], "ex-api-2")
        self.assertEqual(body["grantId"], "g-api-2")
        self.assertIsNone(body["execution"])
        self.assertEqual(len(body["provenanceEvents"]), 1)

    # ── Auth ────────────────────────────────────────────────────
    def test_endpoint_requires_admin_token_when_operator_disabled(self):
        self._make_execution("ex-auth-1")
        # No auth header when token is configured -> 401
        status, body = self._run_handler("/provenance/executions/ex-auth-1/summary")
        self.assertEqual(status, 401)
        # Invalid token -> 403
        status, body = self._run_handler(
            "/provenance/executions/ex-auth-1/summary",
            auth="Bearer wrong-token"
        )
        self.assertEqual(status, 403)

    def test_endpoint_accepts_operator_roles_when_operator_enabled(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("auditor-1", "Auditor One", "auditor", "auditor-token")

        self._make_execution("ex-auth-2")
        status, body = self._run_handler(
            "/provenance/executions/ex-auth-2/summary",
            auth="Bearer auditor-token"
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["executionId"], "ex-auth-2")

    def test_endpoint_rejects_demo_operator_role(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"

        self._insert_operator("demo-op-1", "Demo Op", "demo_operator", "demo-token")

        self._make_execution("ex-auth-3")
        status, body = self._run_handler(
            "/provenance/executions/ex-auth-3/summary",
            auth="Bearer demo-token"
        )
        self.assertEqual(status, 403)

    # ── Response shape ──────────────────────────────────────────
    def test_response_contains_provenance_events_chronologically(self):
        self._make_execution("ex-shape-1")
        self.record_event(
            event_type="grant_executed",
            actor_type="agent",
            actor_id="agent-1",
            action="execute",
            occurred_at="2026-05-11T09:00:00Z",
            execution_id="ex-shape-1",
        )
        self.record_event(
            event_type="evidence_created",
            actor_type="system",
            actor_id="engine-1",
            action="create",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-shape-1",
        )
        status, body = self._run_handler(
            "/provenance/executions/ex-shape-1/summary",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        events = body["provenanceEvents"]
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["eventType"], "grant_executed")
        self.assertEqual(events[1]["eventType"], "evidence_created")

    def test_response_includes_evidence_when_archived(self):
        self._make_execution("ex-ev-1")
        self._archive_evidence("ex-ev-1")
        status, body = self._run_handler(
            "/provenance/executions/ex-ev-1/summary",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["evidence"]["present"])
        self.assertIsNotNone(body["evidence"]["hash"])
        self.assertEqual(len(body["evidence"]["hash"]), 64)

    def test_response_warnings_for_missing_evidence(self):
        self._make_execution("ex-warn-1")
        status, body = self._run_handler(
            "/provenance/executions/ex-warn-1/summary",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        self.assertIn("missing_evidence", body["warnings"])

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
            "/provenance/executions/ex-sec-1/summary",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        raw = json.dumps(body)
        for forbidden in ["GRANTLAYER_ADMIN_TOKEN", "password", "secret", "token", "private"]:
            self.assertNotIn(forbidden, raw.lower(), f"Secret leak detected: {forbidden}")

    # ── Timeline and flags integration ──────────────────────────
    def test_timeline_matches_provenance_events(self):
        self._make_execution("ex-tl-1")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-tl-1",
        )
        status, body = self._run_handler(
            "/provenance/executions/ex-tl-1/summary",
            auth="Bearer test-admin-token"
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["timeline"], body["provenanceEvents"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
