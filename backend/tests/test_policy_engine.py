"""GrantLayer MVP — Policy Engine tests.

Tests:
  1. Valid grant allows protected action
  2. Expired grant blocks action
  3. Revoked grant blocks action
  4. Wrong role blocks action
  5. Wrong action blocks action
  6. No grant found blocks action
  7. Future grant (not yet valid) blocks action
  8. Wildcard action grant allows action
"""

import sys
import os
import datetime
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models import Grant, AccessRequest
from src.policy_engine import evaluate_access


def _make_grant(**kwargs) -> Grant:
    defaults = dict(
        subject_id="tech-01",
        role="technician",
        action="restart-service",
        resource="customer-env-a",
        valid_from="2026-01-01T00:00:00Z",
        valid_until="2099-12-31T23:59:59Z",
        created_by="admin",
        reason="Routine maintenance",
        revoked=False,
    )
    defaults.update(kwargs)
    return Grant(**defaults)


def _req(**kwargs) -> AccessRequest:
    defaults = dict(
        subject_id="tech-01",
        role="technician",
        action="restart-service",
        resource="customer-env-a",
    )
    defaults.update(kwargs)
    return AccessRequest(**defaults)


NOW = datetime.datetime(2026, 6, 1, 12, 0, 0)


class TestPolicyEngine(unittest.TestCase):

    # 1. Valid grant allows action
    def test_valid_grant_allows_action(self):
        grant = _make_grant()
        result = evaluate_access(_req(), [grant], NOW)
        self.assertTrue(result.approved)
        self.assertEqual(result.matched_grant_id, grant.id)

    # 2. Expired grant blocks action
    def test_expired_grant_blocks_action(self):
        grant = _make_grant(valid_until="2025-01-01T00:00:00Z")
        result = evaluate_access(_req(), [grant], NOW)
        self.assertFalse(result.approved)
        self.assertIn("expired", result.reason.lower())

    # 3. Revoked grant blocks action
    def test_revoked_grant_blocks_action(self):
        grant = _make_grant(revoked=True, revoked_by="admin", revoked_reason="Emergency")
        result = evaluate_access(_req(), [grant], NOW)
        self.assertFalse(result.approved)
        self.assertIn("revoked", result.reason.lower())

    # 4. Wrong role blocks action
    def test_wrong_role_blocks_action(self):
        grant = _make_grant(role="senior-engineer")
        result = evaluate_access(_req(role="technician"), [grant], NOW)
        self.assertFalse(result.approved)

    # 5. Wrong action blocks action
    def test_wrong_action_blocks_action(self):
        grant = _make_grant(action="read-logs")
        result = evaluate_access(_req(action="restart-service"), [grant], NOW)
        self.assertFalse(result.approved)

    # 6. No grant found blocks action
    def test_no_grant_blocks_action(self):
        result = evaluate_access(_req(), [], NOW)
        self.assertFalse(result.approved)
        self.assertIn("No grant found", result.reason)

    # 7. Future grant (not yet valid) blocks action
    def test_future_grant_blocks_action(self):
        grant = _make_grant(valid_from="2099-01-01T00:00:00Z")
        result = evaluate_access(_req(), [grant], NOW)
        self.assertFalse(result.approved)
        self.assertIn("not yet valid", result.reason)

    # 8. Wildcard action allows any action
    def test_wildcard_action_allows_action(self):
        grant = _make_grant(action="*")
        result = evaluate_access(_req(action="delete-snapshot"), [grant], NOW)
        self.assertTrue(result.approved)

    # 9. Wrong resource blocks action
    def test_wrong_resource_blocks_action(self):
        grant = _make_grant(resource="customer-env-b")
        result = evaluate_access(_req(resource="customer-env-a"), [grant], NOW)
        self.assertFalse(result.approved)

    # 10. Wildcard resource allows any resource
    def test_wildcard_resource_allows_resource(self):
        grant = _make_grant(resource="*")
        result = evaluate_access(_req(resource="customer-env-z"), [grant], NOW)
        self.assertTrue(result.approved)


class TestAuditEvents(unittest.TestCase):
    """Verify that audit events are produced for approved and denied attempts."""

    def setUp(self):
        import tempfile
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name
        # Re-import after env var is set
        import importlib
        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()
        import src.grants as grants_mod
        importlib.reload(grants_mod)
        import src.audit_log as audit_mod
        importlib.reload(audit_mod)
        import src.demo_action as demo_mod
        importlib.reload(demo_mod)
        self.demo_mod = demo_mod
        self.grants_mod = grants_mod
        self.audit_mod = audit_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if "GRANTLAYER_DB" in os.environ:
            del os.environ["GRANTLAYER_DB"]

    def _add_valid_grant(self):
        g = _make_grant()
        self.grants_mod.create_grant(g)
        return g

    # 6. Audit event created for approved attempt
    def test_audit_event_created_for_approved(self):
        self._add_valid_grant()
        self.demo_mod.handle_demo_action("tech-01", "technician", "restart-service", "customer-env-a")
        events = self.audit_mod.list_events()
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0].approved)

    # 7. Audit event created for denied attempt
    def test_audit_event_created_for_denied(self):
        self.demo_mod.handle_demo_action("tech-01", "technician", "restart-service", "customer-env-a")
        events = self.audit_mod.list_events()
        self.assertEqual(len(events), 1)
        self.assertFalse(events[0].approved)


class TestChallengeFlow(unittest.TestCase):
    """Sprint 2A — Challenge/proof flow tests (8 new tests)."""

    def setUp(self):
        import tempfile
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name
        import importlib
        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()
        import src.grants as grants_mod
        importlib.reload(grants_mod)
        import src.audit_log as audit_mod
        importlib.reload(audit_mod)
        import src.challenges as ch_mod
        importlib.reload(ch_mod)
        import src.demo_action as demo_mod
        importlib.reload(demo_mod)
        self.db_mod = db_mod
        self.demo_mod = demo_mod
        self.grants_mod = grants_mod
        self.audit_mod = audit_mod
        self.ch_mod = ch_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if "GRANTLAYER_DB" in os.environ:
            del os.environ["GRANTLAYER_DB"]

    def _add_valid_grant(self):
        g = _make_grant()
        self.grants_mod.create_grant(g)
        return g

    def _make_challenge(self, action="restart-service", resource="customer-env-a"):
        return self.ch_mod.create_challenge("tech-01", action, resource)

    # 1. Challenge can be created
    def test_challenge_can_be_created(self):
        c = self._make_challenge()
        self.assertIsNotNone(c.id)
        self.assertEqual(c.subject_id, "tech-01")
        self.assertEqual(c.action, "restart-service")
        self.assertEqual(c.resource, "customer-env-a")
        self.assertEqual(c.status, "active")
        self.assertGreater(c.expires_at, c.created_at)

    # 2. Valid challenge allows demo action when grant exists
    def test_valid_challenge_allows_demo_action(self):
        self._add_valid_grant()
        c = self._make_challenge()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            challenge_id=c.id,
        )
        self.assertTrue(result["approved"])
        self.assertEqual(result.get("challengeId"), c.id)

    # 3. Reusing same challenge is blocked (replay protection)
    def test_replay_challenge_is_blocked(self):
        self._add_valid_grant()
        c = self._make_challenge()
        # First use: approved
        r1 = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            challenge_id=c.id,
        )
        self.assertTrue(r1["approved"])
        # Second use: blocked
        r2 = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            challenge_id=c.id,
        )
        self.assertFalse(r2["approved"])
        self.assertEqual(r2.get("challengeResult"), "already_used")

    # 4. Expired challenge is blocked
    def test_expired_challenge_is_blocked(self):
        self._add_valid_grant()
        c = self._make_challenge()
        # Manually expire the challenge
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                "UPDATE challenges SET expires_at = ? WHERE id = ?",
                ("2020-01-01T00:00:00Z", c.id),
            )
            conn.commit()
        finally:
            conn.close()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            challenge_id=c.id,
        )
        self.assertFalse(result["approved"])
        self.assertEqual(result.get("challengeResult"), "expired")

    # 5. Challenge with wrong action is blocked
    def test_challenge_wrong_action_is_blocked(self):
        self._add_valid_grant()
        c = self._make_challenge(action="read-logs")  # challenge for different action
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            challenge_id=c.id,
        )
        self.assertFalse(result["approved"])
        self.assertEqual(result.get("challengeResult"), "mismatch")

    # 6. Challenge with wrong resource is blocked
    def test_challenge_wrong_resource_is_blocked(self):
        self._add_valid_grant()
        c = self._make_challenge(resource="customer-env-b")  # challenge for different resource
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            challenge_id=c.id,
        )
        self.assertFalse(result["approved"])
        self.assertEqual(result.get("challengeResult"), "mismatch")

    # 7. Successful challenge attempt creates audit event with challenge info
    def test_challenge_creates_audit_event_with_challenge_info(self):
        self._add_valid_grant()
        c = self._make_challenge()
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
            challenge_id=c.id,
        )
        events = self.audit_mod.list_events()
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertTrue(ev.challenge_present)
        self.assertEqual(ev.challenge_id, c.id)
        self.assertEqual(ev.challenge_result, "valid")

    # 8. Legacy demo-action without challengeId marks challenge as legacy_mode
    def test_legacy_action_without_challenge_marks_legacy_mode(self):
        self._add_valid_grant()
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a",
        )
        events = self.audit_mod.list_events()
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertFalse(ev.challenge_present)
        self.assertIsNone(ev.challenge_id)
        self.assertEqual(ev.challenge_result, "legacy_mode")
        self.assertTrue(ev.approved)  # backward-compat: still approved without challenge


class TestGrantSignatures(unittest.TestCase):
    """Sprint 2B — Ed25519 grant signature tests."""

    def setUp(self):
        import tempfile
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name
        import importlib
        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()
        import src.grants as grants_mod
        importlib.reload(grants_mod)
        import src.audit_log as audit_mod
        importlib.reload(audit_mod)
        import src.demo_action as demo_mod
        importlib.reload(demo_mod)
        import src.crypto_signing as crypto_mod
        importlib.reload(crypto_mod)
        crypto_mod.ensure_demo_keypair()
        self.db_mod = db_mod
        self.demo_mod = demo_mod
        self.grants_mod = grants_mod
        self.audit_mod = audit_mod
        self.crypto_mod = crypto_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if "GRANTLAYER_DB" in os.environ:
            del os.environ["GRANTLAYER_DB"]

    def _make_signed_grant(self, **kwargs):
        g = _make_grant(**kwargs)
        return self.grants_mod.create_grant(g)

    def _make_unsigned_grant(self, **kwargs):
        """Insert grant directly without signing (simulates legacy data)."""
        g = _make_grant(**kwargs)
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO grants
                   (id, subject_id, role, action, resource, valid_from, valid_until,
                    created_by, reason, revoked, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                (g.id, g.subject_id, g.role, g.action, g.resource,
                 g.valid_from, g.valid_until, g.created_by, g.reason, g.created_at),
            )
            conn.commit()
        finally:
            conn.close()
        return g

    # 1. New grant is signed on creation
    def test_new_grant_is_signed_on_creation(self):
        g = self._make_signed_grant()
        self.assertIsNotNone(g.signature)
        self.assertIsNotNone(g.signing_key_id)
        self.assertIsNotNone(g.payload_hash)
        self.assertEqual(g.signing_key_id, "demo-ed25519-v1")

    # 2. Valid signed grant allows action
    def test_valid_signed_grant_allows_action(self):
        self._make_signed_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        self.assertTrue(result["approved"])
        self.assertEqual(result.get("grantSignatureResult"), "valid")

    # 3. Unsigned legacy grant is blocked by default
    def test_unsigned_legacy_grant_is_blocked(self):
        self._make_unsigned_grant()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        self.assertFalse(result["approved"])
        self.assertEqual(result.get("grantSignatureResult"), "missing")
        self.assertEqual(result.get("reason"), "grant_signature_missing")

    # 4. Tampered role invalidates signature/hash
    def test_tampered_role_invalidates_signature(self):
        g = self._make_signed_grant()
        conn = self.db_mod.get_conn()
        try:
            conn.execute("UPDATE grants SET role = 'admin' WHERE id = ?", (g.id,))
            conn.commit()
        finally:
            conn.close()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "admin", "restart-service", "customer-env-a"
        )
        self.assertFalse(result["approved"])
        self.assertIn(result.get("grantSignatureResult"), ("invalid", "hash_mismatch"))

    # 5. Tampered action invalidates signature/hash
    def test_tampered_action_invalidates_signature(self):
        g = self._make_signed_grant()
        conn = self.db_mod.get_conn()
        try:
            conn.execute("UPDATE grants SET action = 'delete-all' WHERE id = ?", (g.id,))
            conn.commit()
        finally:
            conn.close()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "delete-all", "customer-env-a"
        )
        self.assertFalse(result["approved"])
        self.assertIn(result.get("grantSignatureResult"), ("invalid", "hash_mismatch"))

    # 6. Tampered resource invalidates signature/hash
    def test_tampered_resource_invalidates_signature(self):
        g = self._make_signed_grant()
        conn = self.db_mod.get_conn()
        try:
            conn.execute("UPDATE grants SET resource = 'customer-env-z' WHERE id = ?", (g.id,))
            conn.commit()
        finally:
            conn.close()
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-z"
        )
        self.assertFalse(result["approved"])
        self.assertIn(result.get("grantSignatureResult"), ("invalid", "hash_mismatch"))

    # 7. Revoked signed grant is still blocked (policy engine blocks)
    def test_revoked_signed_grant_is_blocked(self):
        g = self._make_signed_grant()
        self.grants_mod.revoke_grant(g.id, "admin", "Test revoke")
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        self.assertFalse(result["approved"])
        self.assertIn("revoked", result.get("reason", "").lower())

    # 8. Expired signed grant is still blocked (policy engine blocks)
    def test_expired_signed_grant_is_blocked(self):
        self._make_signed_grant(valid_until="2020-01-01T00:00:00Z")
        result = self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        self.assertFalse(result["approved"])
        self.assertIn("expired", result.get("reason", "").lower())

    # 9. Audit event records grantSignatureResult
    def test_audit_event_records_grant_signature_result(self):
        self._make_signed_grant()
        self.demo_mod.handle_demo_action(
            "tech-01", "technician", "restart-service", "customer-env-a"
        )
        events = self.audit_mod.list_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].grant_signature_result, "valid")

    # 10. Demo key files exist and are not tracked by git
    def test_demo_keys_exist_and_not_committed(self):
        import subprocess
        c = self.crypto_mod
        self.assertTrue(os.path.exists(c._PRIVATE_KEY_PATH))
        self.assertTrue(os.path.exists(c._PUBLIC_KEY_PATH))
        for path in (c._PRIVATE_KEY_PATH, c._PUBLIC_KEY_PATH):
            out = subprocess.run(
                ["git", "ls-files", "--error-unmatch", path],
                cwd=os.path.join(os.path.dirname(__file__), "../.."),
                capture_output=True,
            )
            self.assertNotEqual(out.returncode, 0,
                msg=f"{path} must NOT be tracked by git")


if __name__ == "__main__":
    unittest.main(verbosity=2)
