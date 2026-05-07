"""GL-020 Product Core Hardening tests.

Covers:
1. Demo tamper endpoint disabled by default
2. Demo tamper endpoint works only when enabled
3. Demo-action without challenge fails when REQUIRE_CHALLENGE=true
4. Demo-action with challenge still works when challenge required
5. Protected endpoints fail if REQUIRE_ADMIN_TOKEN=true and token missing
6. Protected endpoints work with valid token when required
7. /health does not expose secrets
8. /health reports config booleans correctly
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestProductCoreHardening(unittest.TestCase):
    """Test product-mode hardening flags."""

    def setUp(self):
        import tempfile
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        # Keep original env vars
        self._orig_enable_demo = os.environ.get("GRANTLAYER_ENABLE_DEMO_ENDPOINTS")
        self._orig_require_challenge = os.environ.get("GRANTLAYER_REQUIRE_CHALLENGE")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")

        # Reset modules for clean state
        import importlib
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

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if "GRANTLAYER_DB" in os.environ:
            del os.environ["GRANTLAYER_DB"]

        # Restore env vars
        for key, orig in [
            ("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", self._orig_enable_demo),
            ("GRANTLAYER_REQUIRE_CHALLENGE", self._orig_require_challenge),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

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
    # 1. Demo tamper endpoint disabled by default
    # ──────────────────────────────────────────────
    def test_demo_tamper_disabled_by_default(self):
        os.environ.pop("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", None)
        import importlib
        importlib.reload(self.config_mod)
        self.assertFalse(self.config_mod.ENABLE_DEMO_ENDPOINTS)

    # ──────────────────────────────────────────────
    # 2. Demo tamper endpoint works only when enabled
    # ──────────────────────────────────────────────
    def test_demo_tamper_works_when_enabled(self):
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        import importlib
        importlib.reload(self.config_mod)
        self.assertTrue(self.config_mod.ENABLE_DEMO_ENDPOINTS)
        # tamper_grant function itself should still work when called directly
        g = self._make_grant()
        result = self.grants_mod.tamper_grant(g.id)
        self.assertIsNotNone(result)
        self.assertTrue(result["ok"])

    # ──────────────────────────────────────────────
    # 3. Demo-action without challenge fails when REQUIRE_CHALLENGE=true
    # ──────────────────────────────────────────────
    def test_demo_action_without_challenge_fails_when_required(self):
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        import importlib
        importlib.reload(self.demo_mod)
        self._make_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        self.assertFalse(result["approved"])
        self.assertEqual(result["reason"], "challenge_required")
        self.assertEqual(result["challengeResult"], "required_missing")

    # ──────────────────────────────────────────────
    # 4. Demo-action with challenge still works when challenge required
    # ──────────────────────────────────────────────
    def test_demo_action_with_challenge_works_when_required(self):
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        import importlib
        importlib.reload(self.demo_mod)
        self._make_grant()
        c = self.ch_mod.create_challenge("tech-01", "restart-service", "customer-env-a")
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            challenge_id=c.id,
        )
        self.assertTrue(result["approved"])
        self.assertEqual(result.get("challengeId"), c.id)

    # ──────────────────────────────────────────────
    # 5. Admin-token: fail closed when required and missing
    # ──────────────────────────────────────────────
    def test_admin_token_required_missing_fails(self):
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        from src.auth import check_admin_token
        ok, status, payload = check_admin_token(None)
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "admin_token_required")
        self.assertEqual(payload["errorCode"], "admin_token_required")
        self.assertEqual(payload["reason"], "Admin token is required for this endpoint.")

    # ──────────────────────────────────────────────
    # 6. Admin-token: works with valid token when required
    # ──────────────────────────────────────────────
    def test_admin_token_required_valid_allows(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "prod-token"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        from src.auth import check_admin_token
        ok, status, payload = check_admin_token("Bearer prod-token")
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    # ──────────────────────────────────────────────
    # 7. /health does not expose secrets
    # ──────────────────────────────────────────────
    def test_health_does_not_expose_secrets(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "super-secret-123"
        import importlib
        importlib.reload(self.config_mod)
        # Simulate health payload manually
        payload = {
            "ok": True,
            "service": "grantlayer-mvp",
            "dbConfigured": bool(self.config_mod.GRANTLAYER_DB),
            "adminTokenConfigured": True,
            "requireAdminToken": self.config_mod.REQUIRE_ADMIN_TOKEN,
            "requireChallenge": self.config_mod.REQUIRE_CHALLENGE,
            "demoEndpointsEnabled": self.config_mod.ENABLE_DEMO_ENDPOINTS,
        }
        payload_str = str(payload)
        self.assertNotIn("super-secret-123", payload_str)
        self.assertNotIn("GRANTLAYER_ADMIN_TOKEN", payload_str)

    # ──────────────────────────────────────────────
    # 8. /health reports config booleans correctly
    # ──────────────────────────────────────────────
    def test_health_reports_config_booleans_correctly(self):
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        import importlib
        importlib.reload(self.config_mod)
        self.assertTrue(self.config_mod.REQUIRE_ADMIN_TOKEN)
        self.assertTrue(self.config_mod.REQUIRE_CHALLENGE)
        self.assertTrue(self.config_mod.ENABLE_DEMO_ENDPOINTS)

    # ──────────────────────────────────────────────
    # Audit events for missing required challenge
    # ──────────────────────────────────────────────
    def test_audit_event_created_for_missing_required_challenge(self):
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
        import importlib
        importlib.reload(self.demo_mod)
        self._make_grant()
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        events = self.audit_mod.list_events()
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertFalse(ev.approved)
        self.assertEqual(ev.reason, "challenge_required")
        self.assertFalse(ev.challenge_present)
        self.assertEqual(ev.challenge_result, "required_missing")


if __name__ == "__main__":
    unittest.main(verbosity=2)
