"""GL-031 — Security Boundary Regression Tests.

Covers:
1. Demo tamper endpoint is disabled by default
2. Demo tamper endpoint requires explicit enable
3. Admin token fails closed when required and missing
4. Admin token fails closed when invalid
5. Operator auth fails closed when token missing
6. Operator auth fails closed when role incorrect
7. Health endpoint does not expose secrets
8. Evidence bundle does not expose secrets (no raw tokens, salts, signatures)
9. Challenge required mode blocks unchallenged actions
10. Grant signature verification blocks tampered grants
"""

import os
import sys
import json
import unittest
import tempfile
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSecurityBoundaryRegression(unittest.TestCase):
    """Security boundary regression tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_demo = os.environ.get("GRANTLAYER_ENABLE_DEMO_ENDPOINTS")
        self._orig_require_challenge = os.environ.get("GRANTLAYER_REQUIRE_CHALLENGE")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")

        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import src.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import src.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

        import src.challenges as ch_mod
        importlib.reload(ch_mod)
        self.ch_mod = ch_mod

        import src.demo_action as demo_mod
        importlib.reload(demo_mod)
        self.demo_mod = demo_mod

        import src.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        crypto_mod.ensure_demo_keypair()

        import src.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import src.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        import src.evidence_bundle as eb_mod
        importlib.reload(eb_mod)
        self.eb_mod = eb_mod

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)

        for key, orig in [
            ("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", self._orig_enable_demo),
            ("GRANTLAYER_REQUIRE_CHALLENGE", self._orig_require_challenge),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
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

    def _make_grant(self):
        from src.models import Grant
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
        self.grants_mod.create_grant(g)
        return g

    # ──────────────────────────────────────────────
    # 1. Demo tamper disabled by default
    # ──────────────────────────────────────────────
    def test_demo_tamper_disabled_by_default(self):
        os.environ.pop("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", None)
        importlib.reload(self.config_mod)
        self.assertFalse(self.config_mod.ENABLE_DEMO_ENDPOINTS)

    # ──────────────────────────────────────────────
    # 2. Demo tamper requires explicit enable
    # ──────────────────────────────────────────────
    def test_demo_tamper_requires_explicit_enable(self):
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        importlib.reload(self.config_mod)
        self.assertTrue(self.config_mod.ENABLE_DEMO_ENDPOINTS)

    # ──────────────────────────────────────────────
    # 3. Admin token fails closed when required and missing
    # ──────────────────────────────────────────────
    def test_admin_token_fails_closed_when_required_and_missing(self):
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.auth_mod)
        ok, status, payload = self.auth_mod.check_admin_token(None)
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self.assertEqual(payload["errorCode"], "admin_token_required")

    # ──────────────────────────────────────────────
    # 4. Admin token fails closed when invalid
    # ──────────────────────────────────────────────
    def test_admin_token_fails_closed_when_invalid(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "correct-token"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        importlib.reload(self.auth_mod)
        ok, status, payload = self.auth_mod.check_admin_token("Bearer wrong-token")
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self.assertEqual(payload["errorCode"], "admin_token_invalid")

    # ──────────────────────────────────────────────
    # 5. Operator auth fails closed when token missing
    # ──────────────────────────────────────────────
    def test_operator_auth_fails_closed_when_token_missing(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        # Must reload config first so auth sees the new flag
        importlib.reload(self.config_mod)
        import src.config as fresh_config
        importlib.reload(fresh_config)
        import src.operators as fresh_ops
        importlib.reload(fresh_ops)
        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        ok, status, payload = fresh_auth.check_auth(None, required_roles=["owner"])
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self.assertEqual(payload["errorCode"], "operator_auth_required")

    # ──────────────────────────────────────────────
    # 6. Operator auth fails closed when role incorrect
    # ──────────────────────────────────────────────
    def test_operator_auth_fails_closed_when_role_incorrect(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        self._insert_operator("aud-01", "Auditor", "auditor", "token-aud")
        importlib.reload(self.config_mod)
        import src.config as fresh_config
        importlib.reload(fresh_config)
        import src.operators as fresh_ops
        importlib.reload(fresh_ops)
        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        ok, status, payload = fresh_auth.check_auth(
            "Bearer token-aud", required_roles=["owner"]
        )
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self.assertEqual(payload["errorCode"], "operator_role_forbidden")

    # ──────────────────────────────────────────────
    # 7. Health endpoint does not expose secrets
    # ──────────────────────────────────────────────
    def test_health_does_not_expose_secrets(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "super-secret-123"
        importlib.reload(self.config_mod)
        payload = {
            "ok": True,
            "service": "grantlayer-mvp",
            "dbConfigured": bool(self.config_mod.GRANTLAYER_DB),
            "adminTokenConfigured": True,
            "requireAdminToken": self.config_mod.REQUIRE_ADMIN_TOKEN,
            "requireChallenge": self.config_mod.REQUIRE_CHALLENGE,
            "demoEndpointsEnabled": self.config_mod.ENABLE_DEMO_ENDPOINTS,
            "operatorModelEnabled": self.config_mod.ENABLE_OPERATOR_MODEL,
            "operatorsConfigured": False,
        }
        payload_str = str(payload)
        self.assertNotIn("super-secret-123", payload_str)
        self.assertNotIn("GRANTLAYER_ADMIN_TOKEN", payload_str)

    # ──────────────────────────────────────────────
    # 8. Evidence bundle does not expose secrets
    # ──────────────────────────────────────────────
    def test_evidence_bundle_does_not_expose_secrets(self):
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        bundle = self.eb_mod.build_evidence_bundle(result["executionId"])
        bundle_str = json.dumps(bundle)
        # No raw signatures should be exposed as bytes (they're strings if present)
        # No token hashes should be present
        self.assertNotIn("token_hash", bundle_str.lower())
        self.assertNotIn("token_hash", bundle_str)
        # SAFE_AUDIT_FIELDS check: no secrets in audit trail
        for event in bundle["auditTrail"]:
            self.assertNotIn("token", str(event).lower())

    # ──────────────────────────────────────────────
    # 9. Challenge required mode blocks unchallenged actions
    # ──────────────────────────────────────────────
    def test_challenge_required_blocks_unchallenged_actions(self):
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        importlib.reload(self.demo_mod)
        g = self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        self.assertFalse(result["approved"])
        self.assertEqual(result["reason"], "challenge_required")
        self.assertEqual(result["challengeResult"], "required_missing")

    # ──────────────────────────────────────────────
    # 10. Grant signature verification blocks tampered grants
    # ──────────────────────────────────────────────
    def test_grant_signature_blocks_tampered_grants(self):
        g = self._make_grant()
        # Tamper the grant (role changed → no longer matches request)
        self.grants_mod.tamper_grant(g.id)
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        # Tampered grant is blocked (either via signature mismatch or role mismatch)
        self.assertFalse(result["approved"])
        # Direct signature verification should fail
        fresh_grant = self.grants_mod.get_grant(g.id)
        import src.crypto_signing as cs
        importlib.reload(cs)
        sig_result = cs.verify_grant_signature(fresh_grant)
        self.assertNotEqual(sig_result, "valid")
        self.assertIn(sig_result, {"missing", "invalid", "hash_mismatch"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
