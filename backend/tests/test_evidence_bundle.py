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
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")

        # Reset modules for clean state
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.grants.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.audit.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

        import backend.src.auth.challenges as ch_mod
        importlib.reload(ch_mod)
        self.ch_mod = ch_mod

        import backend.src.demo.demo_action as demo_mod
        importlib.reload(demo_mod)
        self.demo_mod = demo_mod

        import backend.src.core.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        crypto_mod.ensure_demo_keypair()

        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import backend.src.auth.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        import backend.src.grants.grant_requests as greps_mod
        importlib.reload(greps_mod)
        self.greps_mod = greps_mod

        import backend.src.grants.grant_executions as execs_mod
        importlib.reload(execs_mod)
        self.execs_mod = execs_mod

        import backend.src.evidence.evidence_bundle as eb_mod
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
        from backend.src.core.models import Grant
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

    def _make_client(self):
        """Create a FastAPI TestClient using the current module config state."""
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        import backend.src.core.db as bk_db
        bk_db.DB_PATH_OR_URL = self.tmp_db.name
        bk_db.DB_PATH = self.tmp_db.name
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        return TestClient(create_app(), raise_server_exceptions=False)

    def _run_handler(self, path, method="GET", auth=None):
        """Make a request via FastAPI TestClient and return (status, response_json)."""
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

    # ──────────────────────────────────────────────
    # 1. Missing execution returns 404
    # ──────────────────────────────────────────────
    def test_missing_execution_returns_404(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "admin"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        status, body = self._run_handler("/v1/evidence/executions/nonexistent-id", auth="Bearer admin")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "Execution not found")
        self.assertEqual(body["errorCode"], "execution_not_found")
        self.assertEqual(body["reason"], "The requested execution does not exist.")

    # ──────────────────────────────────────────────
    # 2. Builder returns None for missing execution
    # ──────────────────────────────────────────────
    def test_builder_returns_none_for_missing_execution(self):
        self.assertIsNone(self.eb_mod.build_evidence_bundle("no-such-id"))

    # ──────────────────────────────────────────────
    # 3. Execution without grant / request returns minimal bundle
    # ──────────────────────────────────────────────
    def test_minimal_bundle_for_orphan_execution(self):
        from backend.src.core.models import GrantExecution
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

        from backend.src.core.models import GrantRequest
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

        from backend.src.core.models import GrantRequest
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
        from backend.src.core.models import GrantExecution
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
        status, body = self._run_handler(f"/v1/evidence/executions/{ex_id}", auth="Bearer legacy-token")
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
        status, body = self._run_handler(f"/v1/evidence/executions/{ex_id}", auth=None)
        self.assertEqual(status, 401)
        # Invalid token
        status, body = self._run_handler(f"/v1/evidence/executions/{ex_id}", auth="Bearer wrong")
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
        status, body = self._run_handler(f"/v1/evidence/executions/{ex_id}", auth=f"Bearer {tok}")
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
        status, body = self._run_handler(f"/v1/evidence/executions/{ex_id}", auth=f"Bearer {tok}")
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
        status, body = self._run_handler(f"/v1/evidence/executions/{ex_id}", auth=f"Bearer {tok}")
        self.assertEqual(status, 403)
        self.assertEqual(body["error"], "operator_role_forbidden")
        self.assertEqual(body["errorCode"], "operator_role_forbidden")
        self.assertEqual(body["reason"], "Operator role is not authorized for this action.")

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
        status, body = self._run_handler(f"/v1/evidence/executions/{ex_id}", auth=None)
        self.assertEqual(status, 401)
        self.assertEqual(body["error"], "operator_auth_required")
        self.assertEqual(body["errorCode"], "operator_auth_required")
        self.assertEqual(body["reason"], "Operator authentication is required.")

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
        from backend.src.core.models import GrantExecution
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

        from backend.src.core.models import GrantRequest
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

        from backend.src.core.models import GrantExecution
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
        """Make an export request via FastAPI TestClient, return (status, headers_dict, body_bytes)."""
        headers = {}
        if auth:
            headers["Authorization"] = auth
        client = self._make_client()
        if method == "GET":
            resp = client.get(path, headers=headers)
        else:
            resp = client.post(path, headers=headers)
        return resp.status_code, dict(resp.headers), resp.content

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
        status, headers, body = self._run_export(f"/v1/evidence/executions/{ex_id}/export", auth="Bearer admin")
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
        status, headers, body = self._run_export(f"/v1/evidence/executions/{ex_id}/export", auth="Bearer admin")
        # HTTPX normalises header names to lowercase
        ct = headers.get("Content-Type") or headers.get("content-type", "")
        self.assertIn("application/json", ct)

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
        status, headers, body = self._run_export(f"/v1/evidence/executions/{ex_id}/export", auth="Bearer admin")
        cd = headers.get("Content-Disposition") or headers.get("content-disposition")
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
        status, headers, body = self._run_export(f"/v1/evidence/executions/{ex_id}/export", auth="Bearer admin")
        data = json.loads(body)
        xeh = headers.get("X-Evidence-Hash") or headers.get("x-evidence-hash")
        self.assertEqual(xeh, data["evidenceHash"])

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

        status_normal, body_normal = self._run_handler(f"/v1/evidence/executions/{ex_id}", auth="Bearer admin")
        self.assertEqual(status_normal, 200)

        status_export, headers, body_export = self._run_export(f"/v1/evidence/executions/{ex_id}/export", auth="Bearer admin")
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
        status, headers, body = self._run_export(f"/v1/evidence/executions/{ex_id}/export", auth="Bearer admin")
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
        status, headers, body = self._run_export(f"/v1/evidence/executions/{ex_id}/export", auth="Bearer admin")
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
        status, h, body = self._run_export(f"/v1/evidence/executions/{ex_id}/export", auth="Bearer admin")
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
        status, headers, body = self._run_export(f"/v1/evidence/executions/{ex_id}/export", auth=f"Bearer {tok}")
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
        status, headers, body = self._run_export(f"/v1/evidence/executions/{ex_id}/export", auth=f"Bearer {tok}")
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
        status, headers, body = self._run_export(f"/v1/evidence/executions/{ex_id}/export", auth=f"Bearer {tok}")
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
        status, headers, body = self._run_export(f"/v1/evidence/executions/{ex_id}/export", auth=f"Bearer {tok}")
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
        status, headers, body = self._run_export(f"/v1/evidence/executions/{ex_id}/export", auth="Bearer legacy-token")
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
        status, headers, body = self._run_export(f"/v1/evidence/executions/{ex_id}/export", auth=None)
        self.assertEqual(status, 401)
        # Wrong token
        status, headers, body = self._run_export(f"/v1/evidence/executions/{ex_id}/export", auth="Bearer wrong")
        self.assertEqual(status, 403)

    # ──────────────────────────────────────────────
    # 40. Export for missing execution returns 404
    # ──────────────────────────────────────────────
    def test_export_missing_execution_returns_404(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "admin"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.config_mod)
        importlib.reload(self.auth_mod)

        status, headers, body = self._run_export("/v1/evidence/executions/nonexistent-id/export", auth="Bearer admin")
        self.assertEqual(status, 404)


class TestEvidenceBundleVerification(unittest.TestCase):
    """GL-028: Offline evidence bundle verification tests."""

    # ──────────────────────────────────────────────
    # 41. Valid GL-027 export verifies successfully
    # ──────────────────────────────────────────────
    def test_valid_export_verifies_successfully(self):
        bundle = {
            "evidenceId": "ex-001",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-001",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-001",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "evidenceHash": "",
            "canonicalVersion": "gl-evidence-v1",
            "hashAlgorithm": "sha256",
        }
        # Compute correct hash for this bundle
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle["evidenceHash"] = eb_mod.compute_evidence_hash(bundle)
        result = eb_mod.verify_evidence_export_artifact(bundle)
        self.assertTrue(result["ok"])
        self.assertEqual(result["evidenceId"], "ex-001")
        self.assertEqual(result["canonicalVersion"], "gl-evidence-v1")
        self.assertEqual(result["hashAlgorithm"], "sha256")

    # ──────────────────────────────────────────────
    # 42. Meaningful bundle content change fails
    # ──────────────────────────────────────────────
    def test_content_change_fails_verification(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "ex-002",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-002",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-002",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "evidenceHash": "",
            "canonicalVersion": "gl-evidence-v1",
            "hashAlgorithm": "sha256",
        }
        bundle["evidenceHash"] = eb_mod.compute_evidence_hash(bundle)
        # Tamper content
        bundle["execution"]["resource"] = "tampered-resource"
        result = eb_mod.verify_evidence_export_artifact(bundle)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "hash_mismatch")

    # ──────────────────────────────────────────────
    # 43. Changing generatedAt alone still verifies
    # ──────────────────────────────────────────────
    def test_generated_at_change_still_verifies(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "ex-003",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-003",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-003",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "evidenceHash": "",
            "canonicalVersion": "gl-evidence-v1",
            "hashAlgorithm": "sha256",
        }
        bundle["evidenceHash"] = eb_mod.compute_evidence_hash(bundle)
        # Change generatedAt (excluded from canonical hash)
        bundle["generatedAt"] = "2099-01-01T00:00:00Z"
        result = eb_mod.verify_evidence_export_artifact(bundle)
        self.assertTrue(result["ok"])

    # ──────────────────────────────────────────────
    # 44. Changing evidenceHash to wrong value fails
    # ──────────────────────────────────────────────
    def test_wrong_evidence_hash_fails(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "ex-004",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-004",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-004",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "evidenceHash": "0000000000000000000000000000000000000000000000000000000000000000",
            "canonicalVersion": "gl-evidence-v1",
            "hashAlgorithm": "sha256",
        }
        result = eb_mod.verify_evidence_export_artifact(bundle)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "hash_mismatch")

    # ──────────────────────────────────────────────
    # 45. Missing evidenceHash fails
    # ──────────────────────────────────────────────
    def test_missing_evidence_hash_fails(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "ex-005",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-005",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-005",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "canonicalVersion": "gl-evidence-v1",
            "hashAlgorithm": "sha256",
        }
        result = eb_mod.verify_evidence_export_artifact(bundle)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "invalid_artifact")

    # ──────────────────────────────────────────────
    # 46. Missing canonicalVersion fails
    # ──────────────────────────────────────────────
    def test_missing_canonical_version_fails(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "ex-006",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-006",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-006",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "evidenceHash": "a" * 64,
            "hashAlgorithm": "sha256",
        }
        result = eb_mod.verify_evidence_export_artifact(bundle)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "invalid_artifact")

    # ──────────────────────────────────────────────
    # 47. Unsupported canonicalVersion fails
    # ──────────────────────────────────────────────
    def test_unsupported_canonical_version_fails(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "ex-007",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-007",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-007",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "evidenceHash": "a" * 64,
            "canonicalVersion": "gl-evidence-v99",
            "hashAlgorithm": "sha256",
        }
        result = eb_mod.verify_evidence_export_artifact(bundle)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "unsupported_format")

    # ──────────────────────────────────────────────
    # 48. Missing hashAlgorithm fails
    # ──────────────────────────────────────────────
    def test_missing_hash_algorithm_fails(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "ex-008",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-008",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-008",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "evidenceHash": "a" * 64,
            "canonicalVersion": "gl-evidence-v1",
        }
        result = eb_mod.verify_evidence_export_artifact(bundle)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "invalid_artifact")

    # ──────────────────────────────────────────────
    # 49. Unsupported hashAlgorithm fails
    # ──────────────────────────────────────────────
    def test_unsupported_hash_algorithm_fails(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "ex-009",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-009",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-009",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "evidenceHash": "a" * 64,
            "canonicalVersion": "gl-evidence-v1",
            "hashAlgorithm": "md5",
        }
        result = eb_mod.verify_evidence_export_artifact(bundle)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "unsupported_format")

    # ──────────────────────────────────────────────
    # 50. Invalid hash format fails
    # ──────────────────────────────────────────────
    def test_invalid_hash_format_fails(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "ex-010",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-010",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-010",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "evidenceHash": "NOT_VALID_HEX",
            "canonicalVersion": "gl-evidence-v1",
            "hashAlgorithm": "sha256",
        }
        result = eb_mod.verify_evidence_export_artifact(bundle)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "invalid_artifact")

    # ──────────────────────────────────────────────
    # 51. Reordered JSON keys still verify
    # ──────────────────────────────────────────────
    def test_reordered_keys_still_verify(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "ex-011",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-011",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-011",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "evidenceHash": "",
            "canonicalVersion": "gl-evidence-v1",
            "hashAlgorithm": "sha256",
        }
        bundle["evidenceHash"] = eb_mod.compute_evidence_hash(bundle)
        # Reorder top-level keys
        reordered = {
            "hashAlgorithm": bundle["hashAlgorithm"],
            "evidenceHash": bundle["evidenceHash"],
            "canonicalVersion": bundle["canonicalVersion"],
            "auditTrail": bundle["auditTrail"],
            "usageLimits": bundle["usageLimits"],
            "execution": bundle["execution"],
            "grant": bundle["grant"],
            "approval": bundle["approval"],
            "request": bundle["request"],
            "grantRequestId": bundle["grantRequestId"],
            "grantId": bundle["grantId"],
            "executionId": bundle["executionId"],
            "generatedAt": bundle["generatedAt"],
            "evidenceId": bundle["evidenceId"],
        }
        result = eb_mod.verify_evidence_export_artifact(reordered)
        self.assertTrue(result["ok"])

    # ──────────────────────────────────────────────
    # 52. Build-then-verify round-trip using real bundle
    # ──────────────────────────────────────────────
    def test_build_then_verify_round_trip(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        # Minimal dict that mimics a real built bundle structure
        bundle = {
            "evidenceId": "ex-012",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-012",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-012",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "evidenceHash": "",
            "canonicalVersion": "gl-evidence-v1",
            "hashAlgorithm": "sha256",
        }
        bundle["evidenceHash"] = eb_mod.compute_evidence_hash(bundle)
        result = eb_mod.verify_evidence_export_artifact(bundle)
        self.assertTrue(result["ok"])

    # ──────────────────────────────────────────────
    # 53. Real-db built bundle verifies through helper
    # ──────────────────────────────────────────────
    def test_real_bundle_verifies(self):
        self._env_setup = {}
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()
        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        import backend.src.grants.grants as grants_mod
        importlib.reload(grants_mod)
        import backend.src.core.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        crypto_mod.ensure_demo_keypair()
        import backend.src.demo.demo_action as demo_mod
        importlib.reload(demo_mod)
        import backend.src.evidence.evidence_bundle as eb_mod
        importlib.reload(eb_mod)

        from backend.src.core.models import Grant
        g = Grant(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="admin",
            reason="Routine maintenance",
        )
        grants_mod.create_grant(g)
        result = demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle = eb_mod.build_evidence_bundle(result["executionId"])
        verify_result = eb_mod.verify_evidence_export_artifact(bundle)
        self.assertTrue(verify_result["ok"])

        os.unlink(self.tmp_db.name)
        del os.environ["GRANTLAYER_DB"]

    # ──────────────────────────────────────────────
    # 54. CLI: valid export exits 0
    # ──────────────────────────────────────────────
    def test_cli_valid_export_exits_0(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "ex-cli-001",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-cli-001",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-cli-001",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "evidenceHash": "",
            "canonicalVersion": "gl-evidence-v1",
            "hashAlgorithm": "sha256",
        }
        bundle["evidenceHash"] = eb_mod.compute_evidence_hash(bundle)
        import json, tempfile, os, subprocess, sys
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(bundle, f)
            path = f.name
        try:
            proc = subprocess.run(
                [sys.executable, "scripts/verify_evidence_bundle.py", path],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("OK evidence bundle verified", proc.stdout)
            self.assertNotIn("Bearer", proc.stdout)
            self.assertNotIn("token", proc.stdout.lower())
        finally:
            os.unlink(path)

    # ──────────────────────────────────────────────
    # 55. CLI: tampered export exits 2
    # ──────────────────────────────────────────────
    def test_cli_tampered_export_exits_2(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "ex-cli-002",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-cli-002",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-cli-002",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "evidenceHash": "0000000000000000000000000000000000000000000000000000000000000000",
            "canonicalVersion": "gl-evidence-v1",
            "hashAlgorithm": "sha256",
        }
        import json, tempfile, os, subprocess, sys
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(bundle, f)
            path = f.name
        try:
            proc = subprocess.run(
                [sys.executable, "scripts/verify_evidence_bundle.py", path],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("FAIL evidence hash mismatch", proc.stdout)
        finally:
            os.unlink(path)

    # ──────────────────────────────────────────────
    # 56. CLI: nonexistent file exits 5
    # ──────────────────────────────────────────────
    def test_cli_nonexistent_file_exits_5(self):
        import subprocess, sys
        proc = subprocess.run(
            [sys.executable, "scripts/verify_evidence_bundle.py", "/tmp/nonexistent-evidence-xyz.json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 5)
        self.assertIn("FAIL evidence bundle file read or parse error", proc.stdout)

    # ──────────────────────────────────────────────
    # 57. CLI: malformed JSON exits 5
    # ──────────────────────────────────────────────
    def test_cli_malformed_json_exits_5(self):
        import tempfile, os, subprocess, sys
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("this is not json")
            path = f.name
        try:
            proc = subprocess.run(
                [sys.executable, "scripts/verify_evidence_bundle.py", path],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 5)
            self.assertIn("FAIL evidence bundle file read or parse error", proc.stdout)
            self.assertNotIn("Traceback", proc.stderr)
        finally:
            os.unlink(path)

    # ──────────────────────────────────────────────
    # 58. CLI: missing evidenceHash exits 3
    # ──────────────────────────────────────────────
    def test_cli_missing_evidence_hash_exits_3(self):
        import json, tempfile, os, subprocess, sys
        bundle = {
            "evidenceId": "ex-cli-003",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-cli-003",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-cli-003",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "canonicalVersion": "gl-evidence-v1",
            "hashAlgorithm": "sha256",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(bundle, f)
            path = f.name
        try:
            proc = subprocess.run(
                [sys.executable, "scripts/verify_evidence_bundle.py", path],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 3)
            self.assertIn("FAIL invalid evidence bundle artifact", proc.stdout)
        finally:
            os.unlink(path)

    # ──────────────────────────────────────────────
    # 59. CLI: unsupported canonicalVersion exits 4
    # ──────────────────────────────────────────────
    def test_cli_unsupported_canonical_version_exits_4(self):
        import json, tempfile, os, subprocess, sys
        bundle = {
            "evidenceId": "ex-cli-004",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-cli-004",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-cli-004",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "evidenceHash": "a" * 64,
            "canonicalVersion": "gl-evidence-v99",
            "hashAlgorithm": "sha256",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(bundle, f)
            path = f.name
        try:
            proc = subprocess.run(
                [sys.executable, "scripts/verify_evidence_bundle.py", path],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 4)
            self.assertIn("FAIL unsupported evidence bundle format", proc.stdout)
        finally:
            os.unlink(path)


class TestEvidenceBundleVerificationReport(unittest.TestCase):
    """GL-029 A: Evidence Verification Report structure."""

    def _base_bundle(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "ex-029-a",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-029-a",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-029-a",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "evidenceHash": "",
            "canonicalVersion": "gl-evidence-v1",
            "hashAlgorithm": "sha256",
        }
        bundle["evidenceHash"] = eb_mod.compute_evidence_hash(bundle)
        return bundle

    def test_success_report_form(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        result = eb_mod.verify_evidence_export_artifact(bundle)
        self.assertTrue(result["ok"])
        self.assertEqual(result["evidenceId"], "ex-029-a")
        self.assertEqual(result["evidenceHash"], bundle["evidenceHash"])
        self.assertEqual(result["canonicalVersion"], "gl-evidence-v1")
        self.assertEqual(result["hashAlgorithm"], "sha256")
        self.assertIn("verifiedAt", result)
        self.assertTrue(result["verifiedAt"].startswith("20"))

    def test_error_report_includes_evidence_id(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["evidenceHash"] = "0" * 64
        result = eb_mod.verify_evidence_export_artifact(bundle)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "hash_mismatch")
        self.assertIn("reason", result)
        self.assertEqual(result["evidenceId"], "ex-029-a")

    def test_error_report_missing_fields(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        for missing_field, expected_error in [
            ("canonicalVersion", "invalid_artifact"),
            ("hashAlgorithm", "invalid_artifact"),
            ("evidenceHash", "invalid_artifact"),
        ]:
            bundle = self._base_bundle()
            del bundle[missing_field]
            result = eb_mod.verify_evidence_export_artifact(bundle)
            self.assertFalse(result["ok"], f"{missing_field} should cause failure")
            self.assertEqual(result["error"], expected_error)
            self.assertIn("evidenceId", result)

    def test_error_report_unsupported_version(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["canonicalVersion"] = "gl-evidence-v99"
        result = eb_mod.verify_evidence_export_artifact(bundle)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "unsupported_format")
        self.assertEqual(result["evidenceId"], "ex-029-a")

    def test_error_report_parse_error_code_added(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        self.assertIn("parse_error", eb_mod.VERIFY_ERROR_CODES)

    def test_verified_at_not_in_hash(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        result = eb_mod.verify_evidence_export_artifact(bundle)
        self.assertNotIn("verifiedAt", eb_mod.canonical_evidence_bundle(bundle))

    def test_success_report_no_secrets(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        result = eb_mod.verify_evidence_export_artifact(bundle)
        raw = json.dumps(result)
        self.assertNotIn("Bearer", raw)
        self.assertNotIn("token", raw.lower())
        self.assertNotIn("secret", raw.lower())

    def test_cli_exit_codes_unchanged(self):
        import json, tempfile, os, subprocess, sys, backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(bundle, f)
            path = f.name
        try:
            proc = subprocess.run(
                [sys.executable, "scripts/verify_evidence_bundle.py", path],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("OK evidence bundle verified", proc.stdout)
        finally:
            os.unlink(path)


class TestEvidenceCompleteness(unittest.TestCase):
    """GL-029 B: Evidence Completeness Checks."""

    def _base_bundle(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "ex-029-b",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-029-b",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-029-b",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [{
                "id": "ae-029-b",
                "timestamp": "2026-05-06T10:00:00Z",
                "subject_id": "tech-01",
                "role": "technician",
                "action": "restart-service",
                "resource": "customer-env-a",
                "approved": False,
                "reason": "no_grant",
                "matched_grant_id": None,
                "challenge_id": None,
                "challenge_present": False,
                "challenge_result": "legacy_mode",
                "grant_signature_result": "not_checked",
            }],
            "evidenceHash": "",
            "canonicalVersion": "gl-evidence-v1",
            "hashAlgorithm": "sha256",
        }
        bundle["evidenceHash"] = eb_mod.compute_evidence_hash(bundle)
        return bundle

    def test_completeness_all_checks_pass(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        result = eb_mod.check_evidence_completeness(bundle)
        self.assertTrue(result["complete"])
        self.assertTrue(result["checks"]["executionPresent"])
        self.assertTrue(result["checks"]["grantLinkage"])
        self.assertEqual(result["checks"]["grantRequestLinkage"], "missing_optional")
        self.assertTrue(result["checks"]["auditEventLinkage"])
        self.assertTrue(result["checks"]["auditTrailPresent"])
        self.assertTrue(result["checks"]["usageLimitsConsistent"])
        self.assertTrue(result["checks"]["outcomeConsistent"])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["errors"], [])

    def test_missing_execution_fails(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        del bundle["execution"]
        result = eb_mod.check_evidence_completeness(bundle)
        self.assertFalse(result["complete"])
        self.assertIn("missing execution section", result["errors"])

    def test_grant_linkage_mismatch(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["grantId"] = "g-001"
        result = eb_mod.check_evidence_completeness(bundle)
        self.assertFalse(result["complete"])
        self.assertIn("grantId set but grant section missing", result["errors"])
        self.assertFalse(result["checks"]["grantLinkage"])

    def test_grant_request_linkage_required_missing(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["grantRequestId"] = "gr-001"
        result = eb_mod.check_evidence_completeness(bundle)
        self.assertFalse(result["complete"])
        self.assertIn("grantRequestId set but request or approval section missing", result["errors"])
        self.assertEqual(result["checks"]["grantRequestLinkage"], "missing_required")

    def test_grant_request_linkage_present(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["grantRequestId"] = "gr-001"
        bundle["request"] = {"id": "gr-001"}
        bundle["approval"] = {"approvedBy": "owner-1"}
        result = eb_mod.check_evidence_completeness(bundle)
        self.assertTrue(result["complete"])
        self.assertEqual(result["checks"]["grantRequestLinkage"], "present")
        self.assertEqual(result["warnings"], [])

    def test_request_without_grant_request_id_warns(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["request"] = {"id": "gr-001"}
        result = eb_mod.check_evidence_completeness(bundle)
        self.assertTrue(result["complete"])
        self.assertEqual(result["checks"]["grantRequestLinkage"], "missing_optional")
        self.assertIn("request or approval present without grantRequestId", result["warnings"])

    def test_empty_audit_trail_warns(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["auditTrail"] = []
        result = eb_mod.check_evidence_completeness(bundle)
        self.assertTrue(result["complete"])  # empty trail is a warning, not an error
        self.assertIn("auditTrail is empty", result["warnings"])
        self.assertFalse(result["checks"]["auditTrailPresent"])

    def test_audit_trail_unsorted_warns(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["auditTrail"] = [
            {"id": "ae-002", "timestamp": "2026-05-06T11:00:00Z"},
            {"id": "ae-001", "timestamp": "2026-05-06T10:00:00Z"},
        ]
        result = eb_mod.check_evidence_completeness(bundle)
        self.assertTrue(result["complete"])
        self.assertIn("auditTrail is not chronologically sorted", result["warnings"])

    def test_audit_trail_duplicates_errors(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["auditTrail"] = [
            {"id": "ae-001", "timestamp": "2026-05-06T10:00:00Z"},
            {"id": "ae-001", "timestamp": "2026-05-06T10:00:00Z"},
        ]
        result = eb_mod.check_evidence_completeness(bundle)
        self.assertFalse(result["complete"])
        self.assertIn("auditTrail contains duplicate events", result["errors"])

    def test_usage_limits_inconsistent_exhausted_false(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["execution"]["errorCode"] = "grant_usage_exhausted"
        bundle["usageLimits"] = {"affectedOutcome": False}
        result = eb_mod.check_evidence_completeness(bundle)
        self.assertFalse(result["complete"])
        self.assertIn("errorCode is grant_usage_exhausted but usageLimits.affectedOutcome is false", result["errors"])
        self.assertFalse(result["checks"]["usageLimitsConsistent"])

    def test_usage_limits_inconsistent_affected_no_code(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["execution"]["errorCode"] = "no_grant"
        bundle["usageLimits"] = {"affectedOutcome": True}
        result = eb_mod.check_evidence_completeness(bundle)
        self.assertFalse(result["complete"])
        self.assertIn("usageLimits.affectedOutcome is true but errorCode is not grant_usage_exhausted", result["errors"])
        self.assertFalse(result["checks"]["usageLimitsConsistent"])

    def test_outcome_consistent_succeeded_with_error(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["execution"]["result"] = "succeeded"
        bundle["execution"]["errorCode"] = "no_grant"
        result = eb_mod.check_evidence_completeness(bundle)
        self.assertFalse(result["complete"])
        self.assertIn("result is succeeded but errorCode is not null", result["errors"])

    def test_outcome_consistent_denied_without_error(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["execution"]["result"] = "denied"
        bundle["execution"]["errorCode"] = None
        result = eb_mod.check_evidence_completeness(bundle)
        self.assertFalse(result["complete"])
        self.assertIn("result is denied but errorCode is null", result["errors"])

    def test_complete_true_when_no_errors(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["execution"]["result"] = "succeeded"
        bundle["execution"]["errorCode"] = None
        bundle["usageLimits"] = {"affectedOutcome": False}
        result = eb_mod.check_evidence_completeness(bundle)
        self.assertTrue(result["complete"])
        self.assertTrue(result["checks"]["outcomeConsistent"])
        self.assertEqual(result["errors"], [])


class TestDenialCodeConsistency(unittest.TestCase):
    """GL-029 C: Denial / Error-Code Consistency."""

    def _base_bundle(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "ex-029-c",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-029-c",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-029-c",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "evidenceHash": "a" * 64,
            "canonicalVersion": "gl-evidence-v1",
            "hashAlgorithm": "sha256",
        }
        return bundle

    def test_succeeded_requires_null_error_code(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["execution"]["result"] = "succeeded"
        bundle["execution"]["errorCode"] = None
        result = eb_mod.check_denial_code_consistency(bundle)
        self.assertTrue(result["consistent"])
        self.assertTrue(result["checks"]["resultMatchesErrorCode"])
        self.assertEqual(result["errors"], [])

    def test_denied_requires_error_code(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["execution"]["result"] = "denied"
        bundle["execution"]["errorCode"] = "no_grant"
        result = eb_mod.check_denial_code_consistency(bundle)
        self.assertTrue(result["consistent"])
        self.assertTrue(result["checks"]["resultMatchesErrorCode"])

    def test_denied_with_unknown_code_warns(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["execution"]["errorCode"] = "unknown_reason_xyz"
        result = eb_mod.check_denial_code_consistency(bundle)
        self.assertFalse(result["checks"]["errorCodeCatalogMembership"])
        self.assertIn("unknown error code: unknown_reason_xyz", result["warnings"])

    def test_succeeded_with_error_code_fails(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["execution"]["result"] = "succeeded"
        bundle["execution"]["errorCode"] = "no_grant"
        result = eb_mod.check_denial_code_consistency(bundle)
        self.assertFalse(result["consistent"])
        self.assertIn("result is succeeded but errorCode is present", result["errors"])
        self.assertFalse(result["checks"]["resultMatchesErrorCode"])

    def test_denied_missing_error_code_fails(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["execution"]["result"] = "denied"
        bundle["execution"]["errorCode"] = None
        result = eb_mod.check_denial_code_consistency(bundle)
        self.assertFalse(result["consistent"])
        self.assertIn("result is denied but errorCode is missing", result["errors"])

    def test_failed_warns(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["execution"]["result"] = "failed"
        bundle["execution"]["errorCode"] = "internal_error"
        result = eb_mod.check_denial_code_consistency(bundle)
        self.assertTrue(result["consistent"])
        self.assertIn("result is failed — manual review recommended", result["warnings"])

    def test_denial_reason_populated(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["execution"]["errorCode"] = "grant_usage_exhausted"
        result = eb_mod.check_denial_code_consistency(bundle)
        self.assertEqual(result["denialReason"], "grant usage limit reached")

    def test_outcome_matches_bundle_data_no_grant(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        result = eb_mod.check_denial_code_consistency(bundle)
        self.assertTrue(result["checks"]["outcomeMatchesBundleData"])

    def test_outcome_matches_bundle_data_grant_missing(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["execution"]["result"] = "succeeded"
        bundle["execution"]["errorCode"] = None
        bundle["grantId"] = "g-001"
        result = eb_mod.check_denial_code_consistency(bundle)
        self.assertFalse(result["checks"]["outcomeMatchesBundleData"])
        self.assertIn("result succeeded but grant missing despite grantId", result["errors"])

    def test_grant_request_denied_with_grant_fails(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["execution"]["errorCode"] = "grant_request_denied"
        bundle["grant"] = {"id": "g-001"}
        result = eb_mod.check_denial_code_consistency(bundle)
        self.assertFalse(result["checks"]["outcomeMatchesBundleData"])
        self.assertIn("result denied with grant_request_denied but grant section present", result["errors"])

    def test_no_grant_with_grant_present_fails(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["execution"]["errorCode"] = "no_grant"
        bundle["grant"] = {"id": "g-001"}
        result = eb_mod.check_denial_code_consistency(bundle)
        self.assertFalse(result["checks"]["outcomeMatchesBundleData"])
        self.assertIn("result denied with no_grant but grant section present", result["errors"])

    def test_usage_exhausted_without_flag_fails(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["execution"]["errorCode"] = "grant_usage_exhausted"
        bundle["usageLimits"] = {"affectedOutcome": False}
        result = eb_mod.check_denial_code_consistency(bundle)
        self.assertFalse(result["checks"]["outcomeMatchesBundleData"])
        self.assertIn("errorCode grant_usage_exhausted but usageLimits.affectedOutcome is false", result["errors"])

    def test_known_catalog_membership(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        for code in eb_mod.KNOWN_DENIAL_CODES:
            self.assertIsInstance(code, str)
            self.assertTrue(len(code) > 0)

    def test_unknown_result_value(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = self._base_bundle()
        bundle["execution"]["result"] = "weird"
        result = eb_mod.check_denial_code_consistency(bundle)
        self.assertFalse(result["consistent"])
        self.assertIn("unexpected result value: weird", result["errors"])


class TestEvidenceBundleSecurityBoundaries(unittest.TestCase):
    """GL-029 D: Security Boundary Regression Tests."""

    def test_completeness_no_secrets_leak(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "sec-001",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "sec-001",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-sec-001",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "evidenceHash": "a" * 64,
            "canonicalVersion": "gl-evidence-v1",
            "hashAlgorithm": "sha256",
        }
        result = eb_mod.check_evidence_completeness(bundle)
        raw = json.dumps(result)
        self.assertNotIn("Bearer", raw)
        self.assertNotIn("GRANTLAYER_", raw)
        self.assertNotIn("token", raw)
        self.assertNotIn("secret", raw)

    def test_denial_consistency_no_secrets_leak(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "sec-002",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "sec-002",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-sec-002",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "evidenceHash": "a" * 64,
            "canonicalVersion": "gl-evidence-v1",
            "hashAlgorithm": "sha256",
        }
        result = eb_mod.check_denial_code_consistency(bundle)
        raw = json.dumps(result)
        self.assertNotIn("Bearer", raw)
        self.assertNotIn("GRANTLAYER_", raw)
        self.assertNotIn("token", raw)
        self.assertNotIn("secret", raw)

    def test_completeness_helper_never_crashes_on_null(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        for bad_bundle in [
            {},
            {"execution": None},
            {"execution": {}, "usageLimits": None},
            {"execution": {"errorCode": "grant_usage_exhausted"}, "usageLimits": None},
        ]:
            try:
                result = eb_mod.check_evidence_completeness(bad_bundle)
                self.assertIsInstance(result, dict)
                self.assertIn("complete", result)
            except Exception as exc:
                self.fail(f"check_evidence_completeness crashed on {bad_bundle}: {exc}")

    def test_denial_consistency_never_crashes_on_null(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        for bad_bundle in [
            {},
            {"execution": None},
            {"execution": {}},
            {"execution": {"result": None, "errorCode": None}},
        ]:
            try:
                result = eb_mod.check_denial_code_consistency(bad_bundle)
                self.assertIsInstance(result, dict)
                self.assertIn("consistent", result)
            except Exception as exc:
                self.fail(f"check_denial_code_consistency crashed on {bad_bundle}: {exc}")

    def test_verify_helper_never_crashes_on_bare_dict(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        for bad_bundle in [
            {},
            {"evidenceHash": "a" * 64},
            {"canonicalVersion": "gl-evidence-v1"},
        ]:
            try:
                result = eb_mod.verify_evidence_export_artifact(bad_bundle)
                self.assertIsInstance(result, dict)
                self.assertIn("ok", result)
            except Exception as exc:
                self.fail(f"verify_evidence_export_artifact crashed on {bad_bundle}: {exc}")

    def test_completeness_legacy_null_grant_request_is_warning(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "sec-003",
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "result": "denied",
                "errorCode": "no_grant",
                "auditEventId": "ae-sec-003",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [{"id": "ae-sec-003", "timestamp": "2026-05-06T10:00:00Z"}],
            "grantRequestId": None,
            "request": None,
            "approval": None,
        }
        result = eb_mod.check_evidence_completeness(bundle)
        self.assertTrue(result["complete"])
        self.assertEqual(result["checks"]["grantRequestLinkage"], "missing_optional")
        self.assertEqual(result["warnings"], [])

    def test_completeness_does_not_mutate_bundle(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "sec-004",
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "result": "denied",
                "errorCode": "no_grant",
                "auditEventId": "ae-sec-004",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [{"id": "ae-sec-004", "timestamp": "2026-05-06T10:00:00Z"}],
        }
        original_keys = set(bundle.keys())
        eb_mod.check_evidence_completeness(bundle)
        eb_mod.check_denial_code_consistency(bundle)
        self.assertEqual(set(bundle.keys()), original_keys)


class TestEvidenceBundleCliJson(unittest.TestCase):
    """GL-029: CLI --json output tests."""

    def _base_bundle(self):
        import backend.src.evidence.evidence_bundle as eb_mod
        bundle = {
            "evidenceId": "ex-cli-json",
            "generatedAt": "2026-05-06T10:00:00Z",
            "executionId": "ex-cli-json",
            "grantId": None,
            "grantRequestId": None,
            "request": None,
            "approval": None,
            "grant": None,
            "execution": {
                "action": "restart-service",
                "resource": "customer-env-a",
                "operatorId": None,
                "challengeId": None,
                "challengeResult": "legacy_mode",
                "policyResult": "no_grant",
                "result": "denied",
                "errorCode": "no_grant",
                "executedAt": "2026-05-06T10:00:00Z",
                "auditEventId": "ae-cli-json",
            },
            "usageLimits": {"affectedOutcome": False},
            "auditTrail": [],
            "evidenceHash": "",
            "canonicalVersion": "gl-evidence-v1",
            "hashAlgorithm": "sha256",
        }
        bundle["evidenceHash"] = eb_mod.compute_evidence_hash(bundle)
        return bundle

    def test_cli_json_valid_artifact_returns_parseable_json(self):
        import json, tempfile, os, subprocess, sys
        bundle = self._base_bundle()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(bundle, f)
            path = f.name
        try:
            proc = subprocess.run(
                [sys.executable, "scripts/verify_evidence_bundle.py", path, "--json"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertTrue(data["ok"])
        finally:
            os.unlink(path)

    def test_cli_json_success_includes_expected_fields(self):
        import json, tempfile, os, subprocess, sys
        bundle = self._base_bundle()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(bundle, f)
            path = f.name
        try:
            proc = subprocess.run(
                [sys.executable, "scripts/verify_evidence_bundle.py", path, "--json"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0)
            data = json.loads(proc.stdout)
            self.assertTrue(data["ok"])
            self.assertEqual(data["evidenceId"], "ex-cli-json")
            self.assertIn("evidenceHash", data)
            self.assertEqual(len(data["evidenceHash"]), 64)
            self.assertEqual(data["canonicalVersion"], "gl-evidence-v1")
            self.assertEqual(data["hashAlgorithm"], "sha256")
            self.assertIn("verifiedAt", data)
            self.assertTrue(data["verifiedAt"].startswith("20"))
        finally:
            os.unlink(path)

    def test_cli_json_hash_mismatch_returns_ok_false(self):
        import json, tempfile, os, subprocess, sys
        bundle = self._base_bundle()
        bundle["evidenceHash"] = "0" * 64
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(bundle, f)
            path = f.name
        try:
            proc = subprocess.run(
                [sys.executable, "scripts/verify_evidence_bundle.py", path, "--json"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            data = json.loads(proc.stdout)
            self.assertFalse(data["ok"])
            self.assertEqual(data["error"], "hash_mismatch")
            self.assertIn("reason", data)
        finally:
            os.unlink(path)

    def test_cli_json_malformed_json_returns_safe_error(self):
        import json, tempfile, os, subprocess, sys
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json")
            path = f.name
        try:
            proc = subprocess.run(
                [sys.executable, "scripts/verify_evidence_bundle.py", path, "--json"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 5)
            data = json.loads(proc.stdout)
            self.assertFalse(data["ok"])
            self.assertEqual(data["error"], "parse_error")
            self.assertNotIn("Traceback", proc.stderr)
        finally:
            os.unlink(path)

    def test_cli_json_invalid_artifact_returns_safe_error(self):
        import json, tempfile, os, subprocess, sys
        bundle = self._base_bundle()
        del bundle["evidenceHash"]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(bundle, f)
            path = f.name
        try:
            proc = subprocess.run(
                [sys.executable, "scripts/verify_evidence_bundle.py", path, "--json"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 3)
            data = json.loads(proc.stdout)
            self.assertFalse(data["ok"])
            self.assertEqual(data["error"], "invalid_artifact")
        finally:
            os.unlink(path)

    def test_cli_json_output_contains_no_secrets(self):
        import json, tempfile, os, subprocess, sys
        bundle = self._base_bundle()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(bundle, f)
            path = f.name
        try:
            proc = subprocess.run(
                [sys.executable, "scripts/verify_evidence_bundle.py", path, "--json"],
                capture_output=True,
                text=True,
            )
            raw = json.dumps(proc.stdout.lower())
            self.assertNotIn("bearer", raw)
            self.assertNotIn("token", raw)
            self.assertNotIn("secret", raw)
            self.assertNotIn("salt", raw)
            self.assertNotIn("private key", raw)
            self.assertNotIn("credential", raw)
            self.assertNotIn("stack trace", proc.stdout.lower())
            self.assertNotIn("traceback", proc.stderr.lower())
        finally:
            os.unlink(path)

    def test_cli_json_compatible_with_human_readable(self):
        import json, tempfile, os, subprocess, sys
        bundle = self._base_bundle()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(bundle, f)
            path = f.name
        try:
            # Without --json
            proc_human = subprocess.run(
                [sys.executable, "scripts/verify_evidence_bundle.py", path],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc_human.returncode, 0)
            self.assertIn("OK evidence bundle verified", proc_human.stdout)
            # With --json
            proc_json = subprocess.run(
                [sys.executable, "scripts/verify_evidence_bundle.py", path, "--json"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc_json.returncode, 0)
            data = json.loads(proc_json.stdout)
            self.assertTrue(data["ok"])
        finally:
            os.unlink(path)

if __name__ == "__main__":
    unittest.main(verbosity=2)
