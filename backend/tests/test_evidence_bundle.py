"""Tests for GL-025 Evidence Bundle & Audit Trace Export.

Covers:
1. Missing execution returns 404
2. Execution without grant / request returns minimal bundle
3. Execution with grant-only returns grant block
4. Execution with grant request (approved) returns request + approval blocks
5. Execution with denied grant request returns deniedBy block
6. Usage-limit exhaustion sets affectedOutcome=True
7. Legacy admin-token mode allows access
8. Legacy admin-token mode fails closed when missing/invalid
9. Operator model: owner/auditor/grant_admin may read
10. Operator model: demo_operator is denied
11. Operator model: missing token fails closed
12. Response does not expose secrets (no tokens, salts, signatures as raw bytes)
13. Response contains evidenceId, generatedAt, execution, grant, request, approval, usageLimits, auditTrail
14. grant block contains grantSignatureResult (NOT signatureValid)
15. Related audit events are included in auditTrail (excluding duplicates)
"""

import os
import sys
import json
import unittest
import tempfile
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestEvidenceBundle(unittest.TestCase):
    """Test evidence bundle endpoint and builder."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        # Save env vars we will mutate
        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")

        # Reset modules for clean state
        import backend.src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

        import backend.src.challenges as ch_mod
        importlib.reload(ch_mod)
        self.ch_mod = ch_mod

        import backend.src.demo_action as demo_mod
        importlib.reload(demo_mod)
        self.demo_mod = demo_mod

        import backend.src.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        crypto_mod.ensure_demo_keypair()

        import backend.src.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import backend.src.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        import backend.src.grant_requests as greps_mod
        importlib.reload(greps_mod)
        self.greps_mod = greps_mod

        import backend.src.grant_executions as execs_mod
        importlib.reload(execs_mod)
        self.execs_mod = execs_mod

        import backend.src.evidence_bundle as eb_mod
        importlib.reload(eb_mod)
        self.eb_mod = eb_mod

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if "GRANTLAYER_DB" in os.environ:
            del os.environ["GRANTLAYER_DB"]

        for key, orig in [
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", self._orig_bootstrap_token),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────
    def _make_grant(self, **kwargs):
        from backend.src.models import Grant
        defaults = dict(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="admin",
            reason="Routine maintenance",
        )
        defaults.update(kwargs)
        g = Grant(**defaults)
        self.grants_mod.create_grant(g)
        return g

    def _setup_operator(self, op_id, name, role, token=None):
        """Enable operator model and insert an operator."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)
        tok = token or f"{op_id}-token"
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                "INSERT INTO operators (id, name, role, token_hash, active, created_at) VALUES (?, ?, ?, ?, 1, datetime('now'))",
                (op_id, name, role, self.ops_mod.hash_token(tok)),
            )
            conn.commit()
        finally:
            conn.close()
        importlib.reload(self.ops_mod)
        return tok

    def _run_handler(self, path, method="GET", auth=None):
        """Simulate a server request and return (status, response_json)."""
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)
        from backend.src.server import GrantLayerHandler
        from io import BytesIO
        import http.client

        class DummyRequest:
            def __init__(self):
                self.headers = {}
                if auth:
                    self.headers["Authorization"] = auth
                self.rfile = BytesIO(b"")
                self.wfile = BytesIO()
                self._status = None
                self._headers = {}

            def send_response(self, code):
                self._status = code

            def send_header(self, key, value):
                self._headers[key] = value

            def end_headers(self):
                pass

        class TestHandler(GrantLayerHandler):
            def __init__(inner_self, request):
                # Minimal init for testing path routing
                inner_self.command = method
                inner_self.path = path
                inner_self.request_version = "HTTP/1.1"
                inner_self.headers = request.headers
                inner_self.rfile = request.rfile
                inner_self.wfile = request.wfile
                inner_self._status = None
                inner_self._headers = {}

            def send_response(inner_self, code):
                inner_self._status = code

            def send_header(inner_self, key, value):
                inner_self._headers[key] = value

            def end_headers(inner_self):
                pass

            def _send_json(inner_self, status, data):
                inner_self.send_response(status)
                inner_self._json = data
                inner_self._status = status

            def _send_html(inner_self, body):
                inner_self.send_response(200)
                inner_self._status = 200

        req = DummyRequest()
        handler = TestHandler(req)
        if method == "GET":
            handler.do_GET()
        else:
            handler.do_POST()
        return handler._status, getattr(handler, "_json", None)

    # ──────────────────────────────────────────────
    # 1. Missing execution returns 404
    # ──────────────────────────────────────────────
    def test_missing_execution_returns_404(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "admin"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        status, body = self._run_handler("/evidence/executions/nonexistent-id", auth="Bearer admin")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "Execution not found")

    # ──────────────────────────────────────────────
    # 2. Builder returns None for missing execution
    # ──────────────────────────────────────────────
    def test_builder_returns_none_for_missing_execution(self):
        self.assertIsNone(self.eb_mod.build_evidence_bundle("no-such-id"))

    # ──────────────────────────────────────────────
    # 3. Execution without grant / request returns minimal bundle
    # ──────────────────────────────────────────────
    def test_minimal_bundle_for_orphan_execution(self):
        from backend.src.models import GrantExecution
        ex = GrantExecution(
            action="restart-service",
            resource="customer-env-a",
            result="denied",
            policy_result="no_grant",
            error_code="no_grant",
        )
        self.execs_mod.create_grant_execution(ex)
        bundle = self.eb_mod.build_evidence_bundle(ex.id)
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle["evidenceId"], ex.id)
        self.assertEqual(bundle["executionId"], ex.id)
        self.assertEqual(bundle["grantId"], None)
        self.assertEqual(bundle["grantRequestId"], None)
        self.assertIsNone(bundle["request"])
        self.assertIsNone(bundle["approval"])
        self.assertIsNone(bundle["grant"])
        self.assertEqual(bundle["usageLimits"]["affectedOutcome"], False)
        self.assertIn("auditTrail", bundle)
        self.assertIn("generatedAt", bundle)
        # generatedAt should be an ISO string
        self.assertTrue(isinstance(bundle["generatedAt"], str))
        self.assertTrue(bundle["generatedAt"][0:4].isdigit())

    # ──────────────────────────────────────────────
    # 4. Execution with grant-only returns grant block
    # ──────────────────────────────────────────────
    def test_bundle_with_grant(self):
        g = self._make_grant()
        # Run a demo action to create an execution linked to the grant
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]
        bundle = self.eb_mod.build_evidence_bundle(ex_id)
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle["grantId"], g.id)
        grant_block = bundle["grant"]
        self.assertIsNotNone(grant_block)
        self.assertEqual(grant_block["id"], g.id)
        self.assertEqual(grant_block["subjectId"], "tech-01")
        self.assertEqual(grant_block["role"], "technician")
        self.assertEqual(grant_block["action"], "restart-service")
        self.assertEqual(grant_block["resource"], "customer-env-a")
        self.assertIn("createdBy", grant_block)
        self.assertIn("createdAt", grant_block)
        self.assertIn("payloadHash", grant_block)
        self.assertIn("grantSignatureResult", grant_block)

    # ──────────────────────────────────────────────
    # 5. Execution with approved grant request returns request + approval blocks
    # ──────────────────────────────────────────────
    def test_bundle_with_approved_grant_request(self):
        # Bootstrap operator for approval
        self._setup_operator("owner-1", "Owner", "owner")
        self._setup_operator("req-1", "Requester", "grant_admin")

        from backend.src.models import GrantRequest
        req = GrantRequest(
            subject_id="tech-02",
            role="senior-engineer",
            action="restart-service",
            resource="customer-env-b",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="req-1",
            reason="Emergency",
        )
        self.greps_mod.create_grant_request(req)
        approved_req, grant = self.greps_mod.approve_grant_request(req.id, "owner-1")

        # Execute action with the newly created grant
        result = self.demo_mod.handle_demo_action(
            "tech-02", "senior-engineer", "restart-service", "customer-env-b"
        )
        ex_id = result["executionId"]
        bundle = self.eb_mod.build_evidence_bundle(ex_id)
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle["grantId"], grant.id)
        self.assertEqual(bundle["grantRequestId"], req.id)

        req_block = bundle["request"]
        self.assertIsNotNone(req_block)
        self.assertEqual(req_block["id"], req.id)
        self.assertEqual(req_block["requestedBy"], "req-1")
        self.assertEqual(req_block["reason"], "Emergency")

        appr_block = bundle["approval"]
        self.assertIsNotNone(appr_block)
        self.assertEqual(appr_block["approvedBy"], "owner-1")
        self.assertIn("approvedAt", appr_block)

    # ──────────────────────────────────────────────
    # 6. Execution with denied grant request returns deniedBy block
    # ──────────────────────────────────────────────
    def test_bundle_with_denied_grant_request(self):
        self._setup_operator("owner-1", "Owner", "owner")
        self._setup_operator("req-1", "Requester", "grant_admin")

        from backend.src.models import GrantRequest
        req = GrantRequest(
            subject_id="tech-03",
            role="technician",
            action="restart-service",
            resource="customer-env-c",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="req-1",
            reason="Testing denial",
        )
        self.greps_mod.create_grant_request(req)
        denied_req = self.greps_mod.deny_grant_request(req.id, "owner-1", "Not needed")

        # Manually create an execution linked to the denied request (no grant)
        from backend.src.models import GrantExecution
        ex = GrantExecution(
            action="restart-service",
            resource="customer-env-c",
            grant_request_id=denied_req.id,
            result="denied",
            policy_result="grant_request_denied",
            error_code="grant_request_denied",
        )
        self.execs_mod.create_grant_execution(ex)

        bundle = self.eb_mod.build_evidence_bundle(ex.id)
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle["grantRequestId"], denied_req.id)
        self.assertIsNone(bundle["grant"])

        req_block = bundle["request"]
        self.assertIsNotNone(req_block)

        appr_block = bundle["approval"]
        self.assertIsNotNone(appr_block)
        self.assertEqual(appr_block["deniedBy"], "owner-1")
        self.assertEqual(appr_block["denialReason"], "Not needed")

    # ──────────────────────────────────────────────
    # 7. Usage-limit exhaustion sets affectedOutcome=True
    # ──────────────────────────────────────────────
    def test_usage_limit_exhaustion_sets_affected_outcome(self):
        g = self._make_grant(max_uses=1)
        # First use consumes the single use
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        # Second use should be denied due to exhaustion
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        self.assertEqual(result["reason"], "grant_usage_exhausted")
        ex_id = result["executionId"]
        bundle = self.eb_mod.build_evidence_bundle(ex_id)
        self.assertTrue(bundle["usageLimits"]["affectedOutcome"])
        self.assertEqual(bundle["usageLimits"]["reason"], "grant_usage_exhausted")
        self.assertEqual(bundle["usageLimits"]["maxUses"], 1)

    # ──────────────────────────────────────────────
    # 8. Response does not expose secrets
    # ──────────────────────────────────────────────
    def test_bundle_does_not_expose_secrets(self):
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle = self.eb_mod.build_evidence_bundle(result["executionId"])
        raw = json.dumps(bundle)
        self.assertNotIn("Bearer", raw)               # auth tokens
        self.assertNotIn("super-secret", raw)         # example secret
        self.assertNotIn("token_hash", raw)
        self.assertNotIn("salt", raw)
        # The raw ED25519 signature hex should NOT appear in the bundle,
        # although the safe field grantSignatureResult is allowed.
        # The real signature is a 128-char hex string; it will contain digits
        # and a-f, and be far longer than any dictionary key.
        # Find any long hex-looking string that isn't a known hash field.
        # We assert that g.signature (raw hex) is absent.
        if g.signature:
            self.assertNotIn(g.signature, raw)
        # Also ensure no env value leakage
        self.assertNotIn("GRANTLAYER_", raw)

    # ──────────────────────────────────────────────
    # 9. Legacy admin-token mode allows access
    # ──────────────────────────────────────────────
    def test_legacy_admin_token_allows_evidence(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "legacy-token"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]
        status, body = self._run_handler(f"/evidence/executions/{ex_id}", auth="Bearer legacy-token")
        self.assertEqual(status, 200)
        self.assertEqual(body["evidenceId"], ex_id)

    # ──────────────────────────────────────────────
    # 10. Legacy admin-token mode fails closed when missing/invalid
    # ──────────────────────────────────────────────
    def test_legacy_admin_token_missing_fails(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "legacy-token"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]
        # Missing token
        status, body = self._run_handler(f"/evidence/executions/{ex_id}", auth=None)
        self.assertEqual(status, 401)
        # Invalid token
        status, body = self._run_handler(f"/evidence/executions/{ex_id}", auth="Bearer wrong")
        self.assertEqual(status, 403)

    # ──────────────────────────────────────────────
    # 11. Operator model: owner may read evidence
    # ──────────────────────────────────────────────
    def test_operator_owner_can_read_evidence(self):
        tok = self._setup_operator("owner-1", "Owner One", "owner")
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]
        status, body = self._run_handler(f"/evidence/executions/{ex_id}", auth=f"Bearer {tok}")
        self.assertEqual(status, 200)
        self.assertEqual(body["evidenceId"], ex_id)

    # ──────────────────────────────────────────────
    # 12. Operator model: auditor may read evidence
    # ──────────────────────────────────────────────
    def test_operator_auditor_can_read_evidence(self):
        tok = self._setup_operator("auditor-1", "Auditor One", "auditor")
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]
        status, body = self._run_handler(f"/evidence/executions/{ex_id}", auth=f"Bearer {tok}")
        self.assertEqual(status, 200)
        self.assertEqual(body["evidenceId"], ex_id)

    # ──────────────────────────────────────────────
    # 13. Operator model: demo_operator is denied
    # ──────────────────────────────────────────────
    def test_operator_demo_is_denied_evidence(self):
        tok = self._setup_operator("demo-1", "Demo One", "demo_operator")
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]
        status, body = self._run_handler(f"/evidence/executions/{ex_id}", auth=f"Bearer {tok}")
        self.assertEqual(status, 403)
        self.assertEqual(body["error"], "operator_role_forbidden")

    # ──────────────────────────────────────────────
    # 14. Operator model: missing token fails closed
    # ──────────────────────────────────────────────
    def test_operator_missing_token_fails(self):
        self._setup_operator("owner-1", "Owner", "owner")  # just enable model
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]
        status, body = self._run_handler(f"/evidence/executions/{ex_id}", auth=None)
        self.assertEqual(status, 401)
        self.assertEqual(body["error"], "operator_auth_required")

    # ──────────────────────────────────────────────
    # 15. Response shape matches expectation
    # ──────────────────────────────────────────────
    def test_bundle_shape(self):
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle = self.eb_mod.build_evidence_bundle(result["executionId"])
        self.assertIn("evidenceId", bundle)
        self.assertIn("generatedAt", bundle)
        self.assertIn("executionId", bundle)
        self.assertIn("grantId", bundle)
        self.assertIn("grantRequestId", bundle)
        self.assertIn("request", bundle)
        self.assertIn("approval", bundle)
        self.assertIn("grant", bundle)
        self.assertIn("execution", bundle)
        self.assertIn("usageLimits", bundle)
        self.assertIn("auditTrail", bundle)
        # execution block shape
        ex_block = bundle["execution"]
        self.assertIn("action", ex_block)
        self.assertIn("resource", ex_block)
        self.assertIn("operatorId", ex_block)
        self.assertIn("challengeId", ex_block)
        self.assertIn("challengeResult", ex_block)
        self.assertIn("policyResult", ex_block)
        self.assertIn("result", ex_block)
        self.assertIn("errorCode", ex_block)
        self.assertIn("executedAt", ex_block)
        self.assertIn("auditEventId", ex_block)
        # grant block must contain grantSignatureResult, NOT signatureValid
        grant_block = bundle["grant"]
        self.assertIn("grantSignatureResult", grant_block)
        self.assertNotIn("signatureValid", grant_block)

    # ──────────────────────────────────────────────
    # 16. Audit trail includes primary event and excludes duplicates
    # ──────────────────────────────────────────────
    def test_audit_trail_deduplicates_primary_event(self):
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle = self.eb_mod.build_evidence_bundle(result["executionId"])
        audit_trail = bundle["auditTrail"]
        primary_ids = [ev["id"] for ev in audit_trail]
        seen = set()
        for ev_id in primary_ids:
            self.assertNotIn(ev_id, seen, "Duplicate audit event in trail")
            seen.add(ev_id)


    # ──────────────────────────────────────────────
    # 17. GL-026: Bundle contains evidenceHash, canonicalVersion, hashAlgorithm
    # ──────────────────────────────────────────────
    def test_bundle_has_evidence_hash_fields(self):
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle = self.eb_mod.build_evidence_bundle(result["executionId"])
        self.assertIn("evidenceHash", bundle)
        self.assertIn("canonicalVersion", bundle)
        self.assertIn("hashAlgorithm", bundle)
        eh = bundle["evidenceHash"]
        self.assertEqual(len(eh), 64)
        self.assertTrue(eh == eh.lower())
        self.assertEqual(bundle["canonicalVersion"], "gl-evidence-v1")
        self.assertEqual(bundle["hashAlgorithm"], "sha256")

    # ──────────────────────────────────────────────
    # 18. GL-026: Rebuild yields same evidenceHash
    # ──────────────────────────────────────────────
    def test_bundle_evidence_hash_is_deterministic(self):
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle1 = self.eb_mod.build_evidence_bundle(result["executionId"])
        bundle2 = self.eb_mod.build_evidence_bundle(result["executionId"])
        self.assertEqual(bundle1["evidenceHash"], bundle2["evidenceHash"])

    # ──────────────────────────────────────────────
    # 19. GL-026: evidenceHash changes when data changes
    # ──────────────────────────────────────────────
    def test_bundle_evidence_hash_changes_with_data_change(self):
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle = self.eb_mod.build_evidence_bundle(result["executionId"])
        original_hash = bundle["evidenceHash"]
        # Modify bundle data and recompute
        bundle["execution"]["resource"] = "tampered-resource"
        new_hash = self.eb_mod.compute_evidence_hash(bundle)
        self.assertNotEqual(original_hash, new_hash)

    # ──────────────────────────────────────────────
    # 20. GL-026: canonical form excludes generatedAt, evidenceHash, canonicalVersion, hashAlgorithm
    # ──────────────────────────────────────────────
    def test_canonical_form_excludes_generated_and_hash_meta(self):
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle = self.eb_mod.build_evidence_bundle(result["executionId"])
        canonical = self.eb_mod.canonical_evidence_bundle(bundle)
        self.assertNotIn("generatedAt", canonical)
        self.assertNotIn("evidenceHash", canonical)
        self.assertNotIn("canonicalVersion", canonical)
        self.assertNotIn("hashAlgorithm", canonical)
        # Deterministic on repeated calls
        self.assertEqual(canonical, self.eb_mod.canonical_evidence_bundle(bundle))

    # ──────────────────────────────────────────────
    # 21. GL-026: audit trail is sorted by timestamp then id
    # ──────────────────────────────────────────────
    def test_audit_trail_is_sorted(self):
        g = self._make_grant()
        # Multiple executions create multiple audit events
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        result2 = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle = self.eb_mod.build_evidence_bundle(result2["executionId"])
        audit_trail = bundle["auditTrail"]
        self.assertGreaterEqual(len(audit_trail), 1)
        keys = [(ev.get("timestamp") or "", ev.get("id") or "") for ev in audit_trail]
        self.assertEqual(keys, sorted(keys))

    # ──────────────────────────────────────────────
    # 22. GL-026: export readiness invariants
    # ──────────────────────────────────────────────
    def test_bundle_is_export_ready(self):
        g = self._make_grant(max_uses=5)
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle = self.eb_mod.build_evidence_bundle(result["executionId"])

        required_keys = {
            "evidenceId", "generatedAt", "executionId", "grantId",
            "grantRequestId", "request", "approval", "grant",
            "execution", "usageLimits", "auditTrail",
            "evidenceHash", "canonicalVersion", "hashAlgorithm",
        }
        self.assertTrue(required_keys.issubset(set(bundle.keys())))

        # Self-contained scalars
        self.assertIsNotNone(bundle["evidenceId"])
        self.assertIsNotNone(bundle["generatedAt"])
        self.assertIsNotNone(bundle["evidenceHash"])
        self.assertIsNotNone(bundle["canonicalVersion"])
        self.assertIsNotNone(bundle["hashAlgorithm"])

        # Secret-free
        raw = json.dumps(bundle)
        self.assertNotIn("Bearer", raw)
        self.assertNotIn("token_hash", raw)
        self.assertNotIn("salt", raw)
        if g.signature:
            self.assertNotIn(g.signature, raw)
        self.assertNotIn("GRANTLAYER_", raw)

        # Traceable
        self.assertEqual(bundle["evidenceId"], bundle["executionId"])


    # ──────────────────────────────────────────────
    # 23. GL-026: null grantRequest produces deterministic hash
    # ──────────────────────────────────────────────
    def test_null_grant_request_produces_deterministic_hash(self):
        # Orphan execution with no grant/request
        from backend.src.models import GrantExecution
        ex = GrantExecution(
            action="restart-service",
            resource="customer-env-a",
            result="denied",
            policy_result="no_grant",
            error_code="no_grant",
        )
        self.execs_mod.create_grant_execution(ex)
        bundle1 = self.eb_mod.build_evidence_bundle(ex.id)
        bundle2 = self.eb_mod.build_evidence_bundle(ex.id)
        self.assertEqual(bundle1["evidenceHash"], bundle2["evidenceHash"])
        self.assertIsNone(bundle1["grant"])
        self.assertIsNone(bundle1["request"])
        self.assertIsNone(bundle1["approval"])

    # ──────────────────────────────────────────────
    # 24. GL-026: denied execution produces deterministic hash
    # ──────────────────────────────────────────────
    def test_denied_execution_produces_deterministic_hash(self):
        self._setup_operator("owner-1", "Owner", "owner")
        self._setup_operator("req-1", "Requester", "grant_admin")

        from backend.src.models import GrantRequest
        req = GrantRequest(
            subject_id="tech-03",
            role="technician",
            action="restart-service",
            resource="customer-env-c",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="req-1",
            reason="Testing denial",
        )
        self.greps_mod.create_grant_request(req)
        denied_req = self.greps_mod.deny_grant_request(req.id, "owner-1", "Not needed")

        from backend.src.models import GrantExecution
        ex = GrantExecution(
            action="restart-service",
            resource="customer-env-c",
            grant_request_id=denied_req.id,
            result="denied",
            policy_result="grant_request_denied",
            error_code="grant_request_denied",
        )
        self.execs_mod.create_grant_execution(ex)

        bundle1 = self.eb_mod.build_evidence_bundle(ex.id)
        bundle2 = self.eb_mod.build_evidence_bundle(ex.id)
        self.assertEqual(bundle1["evidenceHash"], bundle2["evidenceHash"])
        self.assertEqual(bundle1["approval"]["deniedBy"], "owner-1")
        self.assertEqual(bundle1["grant"], None)

    # ──────────────────────────────────────────────
    # 25. GL-026: usageLimits affects hash when present
    # ──────────────────────────────────────────────
    def test_usage_limits_affects_hash_when_present(self):
        g = self._make_grant(max_uses=1)
        # First use allows
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        # Second use denied due to exhaustion
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        self.assertEqual(result["reason"], "grant_usage_exhausted")
        ex_id = result["executionId"]

        # Build bundle with usageLimits present
        bundle_with_limits = self.eb_mod.build_evidence_bundle(ex_id)
        self.assertTrue(bundle_with_limits["usageLimits"]["affectedOutcome"])
        hash_with_limits = bundle_with_limits["evidenceHash"]

        # Build a modified version with altered usage limits
        altered = dict(bundle_with_limits)
        altered["usageLimits"] = {"affectedOutcome": False}
        # Must exclude metadata before recomputing
        altered_hash = self.eb_mod.compute_evidence_hash(altered)
        self.assertNotEqual(hash_with_limits, altered_hash)

    # ──────────────────────────────────────────────
    # Export helper
    # ──────────────────────────────────────────────
    def _run_export(self, path, method="GET", auth=None):
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)
        from backend.src.server import GrantLayerHandler
        from io import BytesIO
        import http.client

        class DummyRequest:
            def __init__(self):
                self.headers = {}
                if auth:
                    self.headers["Authorization"] = auth
                self.rfile = BytesIO(b"")
                self.wfile = BytesIO()
                self._status = None
                self._headers = {}

            def send_response(self, code):
                self._status = code

            def send_header(self, key, value):
                self._headers[key] = value

            def end_headers(self):
                pass

        class TestHandler(GrantLayerHandler):
            def __init__(inner_self, request):
                inner_self.command = method
                inner_self.path = path
                inner_self.request_version = "HTTP/1.1"
                inner_self.headers = request.headers
                inner_self.rfile = request.rfile
                inner_self.wfile = request.wfile
                inner_self._status = None
                inner_self._headers = {}

            def send_response(inner_self, code):
                inner_self._status = code

            def send_header(inner_self, key, value):
                inner_self._headers[key] = value

            def end_headers(inner_self):
                pass

            def _send_json(inner_self, status, data):
                inner_self.send_response(status)
                inner_self._json = data
                inner_self._status = status

            def _send_html(inner_self, body):
                inner_self.send_response(200)
                inner_self._status = 200

        req = DummyRequest()
        handler = TestHandler(req)
        if method == "GET":
            handler.do_GET()
        else:
            handler.do_POST()
        status = handler._status
        headers = handler._headers
        body = req.wfile.getvalue()
        return status, headers, body

    # ──────────────────────────────────────────────
    # 26. Export returns 200 for valid execution
    # ──────────────────────────────────────────────
    def test_export_returns_200(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "admin"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]
        status, headers, body = self._run_export(f"/evidence/executions/{ex_id}/export", auth="Bearer admin")
        self.assertEqual(status, 200)

    # ──────────────────────────────────────────────
    # 27. Export Content-Type is application/json; charset=utf-8
    # ──────────────────────────────────────────────
    def test_export_content_type(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "admin"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]
        status, headers, body = self._run_export(f"/evidence/executions/{ex_id}/export", auth="Bearer admin")
        self.assertEqual(headers.get("Content-Type"), "application/json; charset=utf-8")

    # ──────────────────────────────────────────────
    # 28. Export Content-Disposition includes executionId and short hash
    # ──────────────────────────────────────────────
    def test_export_content_disposition(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "admin"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]
        status, headers, body = self._run_export(f"/evidence/executions/{ex_id}/export", auth="Bearer admin")
        cd = headers.get("Content-Disposition")
        self.assertTrue(cd.startswith("attachment"))
        self.assertIn(f"evidence-{ex_id}", cd)
        bundle = self.eb_mod.build_evidence_bundle(ex_id)
        short_hash = bundle["evidenceHash"][:8]
        self.assertIn(short_hash, cd)
        self.assertTrue(cd.endswith('.json"'))

    # ──────────────────────────────────────────────
    # 29. Export X-Evidence-Hash header equals body evidenceHash
    # ──────────────────────────────────────────────
    def test_export_x_evidence_hash_header(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "admin"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]
        status, headers, body = self._run_export(f"/evidence/executions/{ex_id}/export", auth="Bearer admin")
        data = json.loads(body)
        self.assertEqual(headers.get("X-Evidence-Hash"), data["evidenceHash"])

    # ──────────────────────────────────────────────
    # 30. Export body evidenceHash equals normal endpoint evidenceHash
    # ──────────────────────────────────────────────
    def test_export_evidence_hash_matches_normal_endpoint(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "admin"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]

        status_normal, body_normal = self._run_handler(f"/evidence/executions/{ex_id}", auth="Bearer admin")
        self.assertEqual(status_normal, 200)

        status_export, headers, body_export = self._run_export(f"/evidence/executions/{ex_id}/export", auth="Bearer admin")
        self.assertEqual(status_export, 200)

        data_export = json.loads(body_export)
        self.assertEqual(data_export["evidenceHash"], body_normal["evidenceHash"])

    # ──────────────────────────────────────────────
    # 31. Export body contains canonicalVersion and hashAlgorithm
    # ──────────────────────────────────────────────
    def test_export_contains_version_and_algorithm(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "admin"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]
        status, headers, body = self._run_export(f"/evidence/executions/{ex_id}/export", auth="Bearer admin")
        data = json.loads(body)
        self.assertEqual(data["canonicalVersion"], "gl-evidence-v1")
        self.assertEqual(data["hashAlgorithm"], "sha256")

    # ──────────────────────────────────────────────
    # 32. Export JSON is parseable and safe
    # ──────────────────────────────────────────────
    def test_export_json_is_safe(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "admin"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]
        status, headers, body = self._run_export(f"/evidence/executions/{ex_id}/export", auth="Bearer admin")
        data = json.loads(body)
        raw = json.dumps(data)
        self.assertNotIn("Bearer", raw)
        self.assertNotIn("token_hash", raw)
        self.assertNotIn("salt", raw)
        self.assertNotIn("GRANTLAYER_", raw)

    # ──────────────────────────────────────────────
    # 33. Export pretty JSON is deterministic (sorted keys)
    # ──────────────────────────────────────────────
    def test_export_pretty_json_deterministic(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "admin"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]

        # Determinism must hold for the same bundle dict
        bundle = self.eb_mod.build_evidence_bundle(ex_id)
        export1 = self.eb_mod.export_bundle_json(bundle)
        export2 = self.eb_mod.export_bundle_json(bundle)
        self.assertEqual(export1, export2)

        # The HTTP response should also be pretty-printed
        status, h, body = self._run_export(f"/evidence/executions/{ex_id}/export", auth="Bearer admin")
        self.assertEqual(status, 200)
        text = body.decode("utf-8")
        self.assertIn("\n  ", text)  # 2-space indent

    # ──────────────────────────────────────────────
    # 34. Owner can export
    # ──────────────────────────────────────────────
    def test_export_owner_can_export(self):
        tok = self._setup_operator("owner-1", "Owner One", "owner")
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]
        status, headers, body = self._run_export(f"/evidence/executions/{ex_id}/export", auth=f"Bearer {tok}")
        self.assertEqual(status, 200)

    # ──────────────────────────────────────────────
    # 35. grant_admin can export
    # ──────────────────────────────────────────────
    def test_export_grant_admin_can_export(self):
        tok = self._setup_operator("admin-1", "Admin One", "grant_admin")
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]
        status, headers, body = self._run_export(f"/evidence/executions/{ex_id}/export", auth=f"Bearer {tok}")
        self.assertEqual(status, 200)

    # ──────────────────────────────────────────────
    # 36. auditor can export
    # ──────────────────────────────────────────────
    def test_export_auditor_can_export(self):
        tok = self._setup_operator("auditor-1", "Auditor One", "auditor")
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]
        status, headers, body = self._run_export(f"/evidence/executions/{ex_id}/export", auth=f"Bearer {tok}")
        self.assertEqual(status, 200)

    # ──────────────────────────────────────────────
    # 37. demo_operator cannot export
    # ──────────────────────────────────────────────
    def test_export_demo_operator_denied(self):
        tok = self._setup_operator("demo-1", "Demo One", "demo_operator")
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]
        status, headers, body = self._run_export(f"/evidence/executions/{ex_id}/export", auth=f"Bearer {tok}")
        self.assertEqual(status, 403)

    # ──────────────────────────────────────────────
    # 38. Legacy admin-token mode can export
    # ──────────────────────────────────────────────
    def test_export_legacy_admin_token(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "legacy-token"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]
        status, headers, body = self._run_export(f"/evidence/executions/{ex_id}/export", auth="Bearer legacy-token")
        self.assertEqual(status, 200)

    # ──────────────────────────────────────────────
    # 39. Invalid token fails closed in export
    # ──────────────────────────────────────────────
    def test_export_invalid_token_fails(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "legacy-token"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        ex_id = result["executionId"]
        # Missing auth
        status, headers, body = self._run_export(f"/evidence/executions/{ex_id}/export", auth=None)
        self.assertEqual(status, 401)
        # Wrong token
        status, headers, body = self._run_export(f"/evidence/executions/{ex_id}/export", auth="Bearer wrong")
        self.assertEqual(status, 403)

    # ──────────────────────────────────────────────
    # 40. Export for missing execution returns 404
    # ──────────────────────────────────────────────
    def test_export_missing_execution_returns_404(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "admin"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        status, headers, body = self._run_export("/evidence/executions/nonexistent-id/export", auth="Bearer admin")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
