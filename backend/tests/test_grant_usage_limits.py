"""Tests for GL-024 Grant Usage Limits & Exhaustion Policy.

Covers:
1. Unlimited grant (max_uses=None) allows multiple uses
2. One-time grant (max_uses=1) allows exactly one successful execution
3. Limited grant (max_uses=N) allows exactly N successful executions
4. Exhausted grant fails closed with grant_usage_exhausted
5. Exhausted attempts create denied GrantExecution records
6. Exhausted attempts are audit logged with grant_usage_exhausted
7. Denied/failed attempts do not increment use_count
8. Atomic consumption helper prevents race-condition over-use
9. Policy engine pre-check catches already-exhausted grants
"""

import os
import unittest
import tempfile
import importlib


class TestGrantUsageLimits(unittest.TestCase):
    """Test grant usage limit enforcement."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.grants.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.audit.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

        import backend.src.demo.demo_action as demo_mod
        importlib.reload(demo_mod)
        self.demo_mod = demo_mod

        import backend.src.grants.grant_executions as exec_mod
        importlib.reload(exec_mod)
        self.exec_mod = exec_mod

        import backend.src.core.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        crypto_mod.ensure_demo_keypair()

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)

    def _make_grant(self, max_uses=None, **kwargs):
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
            max_uses=max_uses,
            **kwargs,
        )
        self.grants_mod.create_grant(g, tenant_id="demo")
        return g

    # ──────────────────────────────────────────────
    # 1. Unlimited grant allows multiple uses
    # ──────────────────────────────────────────────
    def test_unlimited_grant_allows_multiple_uses(self):
        g = self._make_grant(max_uses=None)
        for i in range(3):
            result = self.demo_mod.handle_demo_action(
                "tech-01", "technician", "restart-service", "customer-env-a",
                tenant_id="demo",
            )
            self.assertTrue(result["approved"], f"Use {i+1} should be approved")

        refreshed = self.grants_mod.get_grant(g.id)
        self.assertEqual(refreshed.use_count, 3)

    # ──────────────────────────────────────────────
    # 2. One-time grant allows exactly one use
    # ──────────────────────────────────────────────
    def test_one_time_grant_allows_exactly_one_use(self):
        g = self._make_grant(max_uses=1)
        r1 = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertTrue(r1["approved"])

        refreshed = self.grants_mod.get_grant(g.id)
        self.assertEqual(refreshed.use_count, 1)

        r2 = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertFalse(r2["approved"])
        self.assertEqual(r2["reason"], "grant_usage_exhausted")

    # ──────────────────────────────────────────────
    # 3. Limited grant allows exactly N uses
    # ──────────────────────────────────────────────
    def test_limited_grant_allows_exactly_n_uses(self):
        g = self._make_grant(max_uses=3)
        for i in range(3):
            result = self.demo_mod.handle_demo_action(
                "tech-01", "technician", "restart-service", "customer-env-a",
                tenant_id="demo",
            )
            self.assertTrue(result["approved"], f"Use {i+1} should be approved")

        refreshed = self.grants_mod.get_grant(g.id)
        self.assertEqual(refreshed.use_count, 3)

        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertFalse(result["approved"])
        self.assertEqual(result["reason"], "grant_usage_exhausted")

    # ──────────────────────────────────────────────
    # 4. Exhausted grant fails closed
    # ──────────────────────────────────────────────
    def test_exhausted_grant_fails_closed(self):
        self._make_grant(max_uses=0)
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertFalse(result["approved"])
        self.assertEqual(result["reason"], "grant_usage_exhausted")

    # ──────────────────────────────────────────────
    # 5. Exhausted attempt creates denied GrantExecution
    # ──────────────────────────────────────────────
    def test_exhausted_attempt_creates_denied_execution(self):
        self._make_grant(max_uses=1)
        r1 = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertTrue(r1["approved"])

        r2 = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertFalse(r2["approved"])

        execs = self.exec_mod.list_grant_executions()
        self.assertEqual(len(execs), 2)
        self.assertEqual(execs[0].result, "denied")
        self.assertEqual(execs[0].error_code, "grant_usage_exhausted")
        self.assertEqual(execs[1].result, "succeeded")

    # ──────────────────────────────────────────────
    # 6. Exhausted attempts are audit logged
    # ──────────────────────────────────────────────
    def test_exhausted_attempt_is_audit_logged(self):
        self._make_grant(max_uses=1)
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )

        events = self.audit_mod.list_events()
        self.assertEqual(len(events), 2)
        denied_event = events[0]
        self.assertFalse(denied_event.approved)
        self.assertEqual(denied_event.reason, "grant_usage_exhausted")

    # ──────────────────────────────────────────────
    # 7. Denied attempts do not increment use_count
    # ──────────────────────────────────────────────
    def test_denied_attempt_does_not_increment_use_count(self):
        g = self._make_grant(max_uses=3)
        # Wrong role → denied by policy engine, not usage
        result = self.demo_mod.handle_demo_action(
            "tech-01", "wrong-role", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertFalse(result["approved"])

        refreshed = self.grants_mod.get_grant(g.id)
        self.assertEqual(refreshed.use_count, 0)

    # ──────────────────────────────────────────────
    # 8. Failed attempts do not increment use_count
    # ──────────────────────────────────────────────
    def test_failed_attempt_does_not_increment_use_count(self):
        g = self._make_grant(max_uses=3)
        # Break list_grants to simulate internal error
        original = self.grants_mod.list_grants
        self.grants_mod.list_grants = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
        self.demo_mod.list_grants = self.grants_mod.list_grants
        try:
            result = self.demo_mod.handle_demo_action(
                "tech-01", "technician", "restart-service", "customer-env-a",
                tenant_id="demo",
            )
            self.assertFalse(result["approved"])
            self.assertEqual(result["reason"], "internal_handler_error")
        finally:
            self.grants_mod.list_grants = original
            self.demo_mod.list_grants = original

        refreshed = self.grants_mod.get_grant(g.id)
        self.assertEqual(refreshed.use_count, 0)

    # ──────────────────────────────────────────────
    # 9. No grant attempts do not increment anything
    # ──────────────────────────────────────────────
    def test_no_grant_attempt_does_not_increment(self):
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertFalse(result["approved"])
        execs = self.exec_mod.list_grant_executions()
        self.assertEqual(len(execs), 1)
        self.assertEqual(execs[0].result, "denied")

    # ──────────────────────────────────────────────
    # 10. Atomic consumption helper correctness
    # ──────────────────────────────────────────────
    def test_try_consume_grant_use_returns_false_when_exhausted(self):
        g = self._make_grant(max_uses=1)
        consumed1 = self.grants_mod.try_consume_grant_use(g.id)
        self.assertTrue(consumed1)

        consumed2 = self.grants_mod.try_consume_grant_use(g.id)
        self.assertFalse(consumed2)

        refreshed = self.grants_mod.get_grant(g.id)
        self.assertEqual(refreshed.use_count, 1)

    # ──────────────────────────────────────────────
    # 11. Atomic helper works for unlimited grants
    # ──────────────────────────────────────────────
    def test_try_consume_grant_use_works_for_unlimited(self):
        g = self._make_grant(max_uses=None)
        for i in range(3):
            consumed = self.grants_mod.try_consume_grant_use(g.id)
            self.assertTrue(consumed, f"Unlimited use {i+1} should consume")

        refreshed = self.grants_mod.get_grant(g.id)
        self.assertEqual(refreshed.use_count, 3)

    # ──────────────────────────────────────────────
    # 12. use_count starts at 0 on creation
    # ──────────────────────────────────────────────
    def test_use_count_starts_at_zero(self):
        g = self._make_grant(max_uses=5)
        self.assertEqual(g.use_count, 0)
        retrieved = self.grants_mod.get_grant(g.id)
        self.assertEqual(retrieved.use_count, 0)
        self.assertEqual(retrieved.max_uses, 5)

    # ──────────────────────────────────────────────
    # 13. Policy engine pre-check catches exhausted grant
    # ──────────────────────────────────────────────
    def test_policy_engine_pre_check_exhausted(self):
        from backend.src.core.models import AccessRequest, Grant
        from backend.src.policy.policy_engine import evaluate_access
        import datetime

        grant = Grant(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="admin",
            reason="test",
            max_uses=2,
            use_count=2,
        )
        req = AccessRequest(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
        )
        result = evaluate_access(req, [grant], datetime.datetime(2026, 6, 1, 12, 0, 0))
        self.assertFalse(result.approved)
        self.assertEqual(result.reason, "grant_usage_exhausted")
        self.assertEqual(result.matched_grant_id, grant.id)

    # ──────────────────────────────────────────────
    # 14. Policy engine allows non-exhausted grant
    # ──────────────────────────────────────────────
    def test_policy_engine_allows_non_exhausted(self):
        from backend.src.core.models import AccessRequest, Grant
        from backend.src.policy.policy_engine import evaluate_access
        import datetime

        grant = Grant(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="admin",
            reason="test",
            max_uses=2,
            use_count=1,
        )
        req = AccessRequest(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
        )
        result = evaluate_access(req, [grant], datetime.datetime(2026, 6, 1, 12, 0, 0))
        self.assertTrue(result.approved)
        self.assertEqual(result.matched_grant_id, grant.id)

    # ──────────────────────────────────────────────
    # 15. Expired grant does not consume usage
    # ──────────────────────────────────────────────
    def test_expired_grant_does_not_consume(self):
        from backend.src.core.models import Grant
        g = Grant(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2020-01-01T00:00:00Z",
            created_by="admin",
            reason="Routine maintenance",
            max_uses=3,
        )
        self.grants_mod.create_grant(g, tenant_id="demo")
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertFalse(result["approved"])
        self.assertIn("expired", result["reason"].lower())

        refreshed = self.grants_mod.get_grant(g.id)
        self.assertEqual(refreshed.use_count, 0)

    # ──────────────────────────────────────────────
    # 16. Revoked grant does not consume usage
    # ──────────────────────────────────────────────
    def test_revoked_grant_does_not_consume(self):
        g = self._make_grant(max_uses=3)
        self.grants_mod.revoke_grant(g.id, "admin", "test revoke")
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            tenant_id="demo",
        )
        self.assertFalse(result["approved"])
        self.assertIn("revoked", result["reason"].lower())

        refreshed = self.grants_mod.get_grant(g.id)
        self.assertEqual(refreshed.use_count, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
