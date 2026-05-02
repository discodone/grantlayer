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


if __name__ == "__main__":
    unittest.main(verbosity=2)
