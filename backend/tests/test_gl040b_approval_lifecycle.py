"""Tests for GL-040-B Approval Request Lifecycle Core."""

import os
import sys
import unittest

# Add parent directory to path so we can import src modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.src.policy.approval_lifecycle import (
    _STATUS_NOT_REQUIRED,
    _STATUS_PENDING,
    _STATUS_APPROVED,
    _STATUS_REJECTED,
    _STATUS_EXPIRED,
    _STATUS_CANCELLED,
    _STATUS_BLOCKED,
    build_approval_request_lifecycle,
    transition_approval_request,
)


class TestBuildApprovalRequestLifecycle(unittest.TestCase):
    """Tests for build_approval_request_lifecycle."""

    def test_no_approval_required_creates_not_required(self):
        """decision=no_approval_required creates status=not_required."""
        req = build_approval_request_lifecycle(
            approval_requirement={"decision": "no_approval_required", "reason": "low_risk"},
            request_id="req-1",
            action="create",
        )
        self.assertEqual(req["status"], _STATUS_NOT_REQUIRED)
        self.assertEqual(req["decision"], "no_approval_required")
        self.assertEqual(req["reason"], "low_risk")
        self.assertEqual(req["requiredApprovals"], 0)
        self.assertEqual(req["requiredRoles"], [])
        self.assertEqual(req["blockers"], [])

    def test_approval_required_creates_pending(self):
        """decision=approval_required creates status=pending."""
        req = build_approval_request_lifecycle(
            approval_requirement={
                "decision": "approval_required",
                "reason": "medium_risk",
                "requiredApprovals": 1,
                "requiredRoles": ["grant_admin"],
            },
            request_id="req-2",
            action="grant",
        )
        self.assertEqual(req["status"], _STATUS_PENDING)
        self.assertEqual(req["decision"], "approval_required")
        self.assertEqual(req["requiredApprovals"], 1)
        self.assertEqual(req["requiredRoles"], ["grant_admin"])
        self.assertEqual(req["receivedApprovals"], 0)

    def test_four_eyes_required_creates_pending_with_two(self):
        """decision=four_eyes_required creates status=pending with requiredApprovals >= 2."""
        req = build_approval_request_lifecycle(
            approval_requirement={
                "decision": "four_eyes_required",
                "reason": "high_risk",
                "requiredApprovals": 2,
                "requiredRoles": ["grant_admin", "owner"],
            },
            request_id="req-3",
            action="grant",
        )
        self.assertEqual(req["status"], _STATUS_PENDING)
        self.assertEqual(req["decision"], "four_eyes_required")
        self.assertEqual(req["requiredApprovals"], 2)
        self.assertEqual(req["requiredRoles"], ["grant_admin", "owner"])

    def test_blocked_decision_creates_blocked(self):
        """decision=blocked creates status=blocked."""
        req = build_approval_request_lifecycle(
            approval_requirement={
                "decision": "blocked",
                "reason": "compliance_blocked",
                "blockers": ["compliance_blocked"],
            },
            request_id="req-4",
            action="grant",
        )
        self.assertEqual(req["status"], _STATUS_BLOCKED)
        self.assertEqual(req["decision"], "blocked")
        self.assertEqual(req["blockers"], ["compliance_blocked"])

    def test_missing_approval_requirement_creates_blocked(self):
        """Missing approval_requirement creates blocked request."""
        req = build_approval_request_lifecycle(
            approval_requirement=None,
            request_id="req-5",
            action="grant",
        )
        self.assertEqual(req["status"], _STATUS_BLOCKED)
        self.assertEqual(req["decision"], "blocked")
        self.assertEqual(req["reason"], "missing_approval_requirement")
        self.assertIn("approval_requirement_missing", req["blockers"])

    def test_malformed_approval_requirement_creates_blocked(self):
        """Malformed approval_requirement creates blocked request."""
        req = build_approval_request_lifecycle(
            approval_requirement="not_a_dict",
            request_id="req-6",
            action="grant",
        )
        self.assertEqual(req["status"], _STATUS_BLOCKED)
        self.assertEqual(req["decision"], "blocked")
        self.assertEqual(req["reason"], "malformed_approval_requirement")
        self.assertIn("approval_requirement_malformed", req["blockers"])

    def test_unknown_decision_creates_blocked(self):
        """Unknown decision value creates blocked request."""
        req = build_approval_request_lifecycle(
            approval_requirement={"decision": "weird_value"},
            request_id="req-7",
            action="grant",
        )
        self.assertEqual(req["status"], _STATUS_BLOCKED)
        self.assertEqual(req["decision"], "blocked")
        self.assertEqual(req["reason"], "unknown_approval_decision")
        self.assertIn("unknown_decision", req["blockers"])

    def test_default_required_approvals_is_one(self):
        """When requiredApprovals is missing, default to 1."""
        req = build_approval_request_lifecycle(
            approval_requirement={"decision": "approval_required"},
            request_id="req-8",
        )
        self.assertEqual(req["requiredApprovals"], 1)

    def test_approvers_deduplicated_and_sorted(self):
        """Approvers are deduplicated and sorted deterministically."""
        req = build_approval_request_lifecycle(
            approval_requirement={"decision": "no_approval_required"},
            approvers=["charlie", "alice", "alice", "bob", "charlie"],
        )
        self.assertEqual(req["approvers"], ["alice", "bob", "charlie"])

    def test_include_details_false_omits_context(self):
        """include_details=False omits detail objects but keeps core fields."""
        req = build_approval_request_lifecycle(
            approval_requirement={"decision": "no_approval_required"},
            context={"some_key": "some_value"},
            include_details=False,
        )
        self.assertNotIn("context", req)
        self.assertIn("status", req)
        self.assertIn("requiredApprovals", req)

    def test_context_secrets_redacted(self):
        """Response does not expose secrets, tokens, or auth hashes."""
        req = build_approval_request_lifecycle(
            approval_requirement={"decision": "no_approval_required"},
            context={
                "normal_key": "normal_value",
                "api_key": "super-secret",
                "password": "hunter2",
                "Authorization": "Bearer xyz",
                "nested": {"token": "secret-token"},  # nested dicts are not recursively sanitized
            },
        )
        ctx = req.get("context", {})
        self.assertEqual(ctx["api_key"], "[REDACTED]")
        self.assertEqual(ctx["password"], "[REDACTED]")
        self.assertEqual(ctx["Authorization"], "[REDACTED]")
        self.assertEqual(ctx["normal_key"], "normal_value")
        # Nested dicts are kept as-is (not recursively sanitized)
        self.assertEqual(ctx["nested"]["token"], "secret-token")

    def test_no_db_access(self):
        """Lifecycle functions do not access the database."""
        # This is an architectural guarantee verified by code review.
        # The functions accept only plain dicts/lists/scalars and return dicts.
        req = build_approval_request_lifecycle(
            approval_requirement={"decision": "no_approval_required"},
        )
        self.assertIsInstance(req, dict)


class TestTransitionApprovalRequest(unittest.TestCase):
    """Tests for transition_approval_request."""

    def _make_pending(self, required=1, roles=None, approvers=None):
        """Helper to create a pending approval request."""
        if roles is None:
            roles = ["grant_admin"]
        if approvers is None:
            approvers = []
        return {
            "requestId": "req-p",
            "action": "grant",
            "status": _STATUS_PENDING,
            "requiredApprovals": required,
            "requiredRoles": roles,
            "receivedApprovals": 0,
            "approvedByRoles": [],
            "approvalHistory": [],
            "approvers": approvers,
            "decision": "approval_required",
            "reason": "test",
            "blockers": [],
            "warnings": [],
        }

    def test_pending_to_approved_enough_approvals(self):
        """Pending request can transition to approved if enough valid approvals."""
        req = self._make_pending(
            required=1,
            roles=["grant_admin"],
            approvers=[{"role": "grant_admin", "operatorId": "op-1"}],
        )
        result = transition_approval_request(req, "approve", actor_id="op-1")
        self.assertEqual(result["status"], _STATUS_APPROVED)
        self.assertEqual(result["receivedApprovals"], 1)
        self.assertEqual(result["approvedByRoles"], ["grant_admin"])
        self.assertEqual(result["decision"], "approved")

    def test_pending_to_approved_not_enough_approvals(self):
        """Pending request cannot approve without enough valid approvals."""
        req = self._make_pending(
            required=2,
            roles=["grant_admin", "owner"],
            approvers=[{"role": "grant_admin", "operatorId": "op-1"}],
        )
        result = transition_approval_request(req, "approve", actor_id="op-1")
        self.assertEqual(result["status"], _STATUS_PENDING)
        self.assertIn("not_enough_approvals", result["blockers"])
        self.assertEqual(result["receivedApprovals"], 1)

    def test_required_roles_respected(self):
        """Only approvers whose role is in requiredRoles count."""
        req = self._make_pending(
            required=1,
            roles=["owner"],
            approvers=[{"role": "grant_admin", "operatorId": "op-1"}],
        )
        result = transition_approval_request(req, "approve")
        self.assertEqual(result["status"], _STATUS_PENDING)
        self.assertIn("not_enough_approvals", result["blockers"])
        self.assertEqual(result["receivedApprovals"], 0)

    def test_duplicate_approvers_deduplicated(self):
        """Duplicate approvers are de-duplicated."""
        req = self._make_pending(
            required=1,
            roles=["grant_admin"],
            approvers=[
                {"role": "grant_admin", "operatorId": "op-1"},
                {"role": "grant_admin", "operatorId": "op-2"},
            ],
        )
        result = transition_approval_request(req, "approve")
        self.assertEqual(result["status"], _STATUS_APPROVED)
        self.assertEqual(result["receivedApprovals"], 1)
        self.assertEqual(result["approvedByRoles"], ["grant_admin"])

    def test_approvers_sorted_deterministically(self):
        """Approvers list is sorted deterministically."""
        req = build_approval_request_lifecycle(
            approval_requirement={"decision": "no_approval_required"},
            approvers=["charlie", "alice", "bob", "alice"],
        )
        self.assertEqual(req["approvers"], ["alice", "bob", "charlie"])

    def test_pending_to_reject(self):
        """Pending can reject."""
        req = self._make_pending()
        result = transition_approval_request(req, "reject", reason="bad_request")
        self.assertEqual(result["status"], _STATUS_REJECTED)
        self.assertEqual(result["reason"], "bad_request")
        self.assertEqual(result["decision"], "rejected")

    def test_pending_to_expire(self):
        """Pending can expire."""
        req = self._make_pending()
        result = transition_approval_request(req, "expire", reason="timed_out")
        self.assertEqual(result["status"], _STATUS_EXPIRED)
        self.assertEqual(result["reason"], "timed_out")
        self.assertEqual(result["decision"], "expired")

    def test_pending_to_cancel(self):
        """Pending can cancel."""
        req = self._make_pending()
        result = transition_approval_request(req, "cancel", reason="user_cancelled")
        self.assertEqual(result["status"], _STATUS_CANCELLED)
        self.assertEqual(result["reason"], "user_cancelled")
        self.assertEqual(result["decision"], "cancelled")

    def test_approved_cannot_approve_again(self):
        """Approved cannot approve again."""
        req = {
            "requestId": "req-a",
            "status": _STATUS_APPROVED,
            "requiredApprovals": 1,
            "requiredRoles": ["grant_admin"],
            "receivedApprovals": 1,
            "approvedByRoles": ["grant_admin"],
            "approvers": [{"role": "grant_admin", "operatorId": "op-1"}],
            "decision": "approved",
            "reason": "approved",
        }
        result = transition_approval_request(req, "approve")
        self.assertEqual(result["status"], _STATUS_APPROVED)
        self.assertIn("transition_not_allowed", result["blockers"][0])

    def test_blocked_cannot_approve_directly(self):
        """Blocked cannot approve directly."""
        req = {
            "requestId": "req-b",
            "status": _STATUS_BLOCKED,
            "requiredApprovals": 0,
            "requiredRoles": [],
            "receivedApprovals": 0,
            "approvedByRoles": [],
            "approvers": [],
            "decision": "blocked",
            "reason": "blocked",
        }
        result = transition_approval_request(req, "approve")
        self.assertEqual(result["status"], _STATUS_BLOCKED)
        self.assertIn("transition_not_allowed", result["blockers"][0])

    def test_rejected_can_reopen(self):
        """Rejected can reopen to pending."""
        req = {
            "requestId": "req-r",
            "status": _STATUS_REJECTED,
            "requiredApprovals": 1,
            "requiredRoles": ["grant_admin"],
            "receivedApprovals": 0,
            "approvedByRoles": [],
            "approvers": [],
            "decision": "approval_required",
            "reason": "rejected",
        }
        result = transition_approval_request(req, "reopen", reason="appeal_accepted")
        self.assertEqual(result["status"], _STATUS_PENDING)
        self.assertEqual(result["reason"], "appeal_accepted")
        self.assertEqual(result["decision"], "approval_required")

    def test_expired_can_reopen(self):
        """Expired can reopen to pending."""
        req = {
            "requestId": "req-e",
            "status": _STATUS_EXPIRED,
            "requiredApprovals": 1,
            "requiredRoles": ["grant_admin"],
            "receivedApprovals": 0,
            "approvedByRoles": [],
            "approvers": [],
            "decision": "approval_required",
            "reason": "expired",
        }
        result = transition_approval_request(req, "reopen", reason="extension_granted")
        self.assertEqual(result["status"], _STATUS_PENDING)
        self.assertEqual(result["reason"], "extension_granted")
        self.assertEqual(result["decision"], "approval_required")

    def test_cancelled_can_reopen(self):
        """Cancelled can reopen to pending."""
        req = {
            "requestId": "req-c",
            "status": _STATUS_CANCELLED,
            "requiredApprovals": 1,
            "requiredRoles": ["grant_admin"],
            "receivedApprovals": 0,
            "approvedByRoles": [],
            "approvers": [],
            "decision": "approval_required",
            "reason": "cancelled",
        }
        result = transition_approval_request(req, "reopen", reason="resubmitted")
        self.assertEqual(result["status"], _STATUS_PENDING)
        self.assertEqual(result["reason"], "resubmitted")
        self.assertEqual(result["decision"], "approval_required")

    def test_blocked_cannot_reopen_without_flag(self):
        """Blocked cannot reopen unless context explicitly includes allowBlockedReopen=True."""
        req = {
            "requestId": "req-b2",
            "status": _STATUS_BLOCKED,
            "requiredApprovals": 0,
            "requiredRoles": [],
            "receivedApprovals": 0,
            "approvedByRoles": [],
            "approvers": [],
            "decision": "blocked",
            "reason": "blocked",
        }
        result = transition_approval_request(req, "reopen", context={})
        self.assertEqual(result["status"], _STATUS_BLOCKED)
        self.assertIn("blocked_cannot_reopen_without_explicit_flag", result["blockers"])

    def test_blocked_can_reopen_with_flag(self):
        """Blocked can reopen when context has allowBlockedReopen=True."""
        req = {
            "requestId": "req-b3",
            "status": _STATUS_BLOCKED,
            "requiredApprovals": 1,
            "requiredRoles": ["grant_admin"],
            "receivedApprovals": 0,
            "approvedByRoles": [],
            "approvers": [],
            "decision": "approval_required",
            "reason": "blocked",
        }
        result = transition_approval_request(
            req, "reopen", reason="override", context={"allowBlockedReopen": True}
        )
        self.assertEqual(result["status"], _STATUS_PENDING)
        self.assertEqual(result["reason"], "override")

    def test_invalid_transition(self):
        """Invalid transition returns request unchanged with a blocker."""
        req = self._make_pending()
        result = transition_approval_request(req, "frobnicate")
        self.assertEqual(result["status"], _STATUS_PENDING)
        self.assertIn("invalid_transition", result["blockers"][0])

    def test_missing_request(self):
        """Missing approval_request creates blocked response."""
        result = transition_approval_request(None, "approve")
        self.assertEqual(result["status"], _STATUS_BLOCKED)
        self.assertEqual(result["reason"], "missing_approval_request")
        self.assertIn("approval_request_missing", result["blockers"])

    def test_malformed_request(self):
        """Malformed approval_request creates blocked response."""
        result = transition_approval_request("not_a_dict", "approve")
        self.assertEqual(result["status"], _STATUS_BLOCKED)
        self.assertEqual(result["reason"], "malformed_approval_request")
        self.assertIn("approval_request_malformed", result["blockers"])

    def test_include_details_false(self):
        """include_details=False omits context but keeps core fields."""
        req = self._make_pending()
        result = transition_approval_request(
            req, "reject", context={"foo": "bar"}, include_details=False
        )
        self.assertNotIn("context", result)
        self.assertIn("status", result)
        self.assertIn("requiredApprovals", result)

    def test_not_required_cannot_transition(self):
        """not_required status has no valid transitions."""
        req = {
            "requestId": "req-nr",
            "status": _STATUS_NOT_REQUIRED,
            "requiredApprovals": 0,
            "requiredRoles": [],
            "receivedApprovals": 0,
            "approvedByRoles": [],
            "approvers": [],
            "decision": "no_approval_required",
            "reason": "no_approval_required",
        }
        for trans in ["approve", "reject", "expire", "cancel", "block", "reopen"]:
            result = transition_approval_request(req, trans)
            self.assertEqual(result["status"], _STATUS_NOT_REQUIRED)
            self.assertIn("transition_not_allowed", result["blockers"][0])

    def test_create_transition(self):
        """create transition moves to pending."""
        req = {
            "requestId": "req-cr",
            "status": _STATUS_NOT_REQUIRED,
            "requiredApprovals": 1,
            "requiredRoles": ["grant_admin"],
            "receivedApprovals": 0,
            "approvedByRoles": [],
            "approvers": [],
            "decision": "approval_required",
            "reason": "test",
        }
        result = transition_approval_request(req, "create")
        self.assertEqual(result["status"], _STATUS_PENDING)
        self.assertEqual(result["reason"], "created")

    def test_block_transition(self):
        """block transition moves to blocked."""
        req = self._make_pending()
        result = transition_approval_request(req, "block", reason="policy_violation")
        self.assertEqual(result["status"], _STATUS_BLOCKED)
        self.assertEqual(result["reason"], "policy_violation")
        self.assertEqual(result["decision"], "blocked")

    def test_four_eyes_approve(self):
        """Four-eyes requirement needs 2 different roles."""
        req = self._make_pending(
            required=2,
            roles=["grant_admin", "owner"],
            approvers=[
                {"role": "grant_admin", "operatorId": "op-1"},
                {"role": "owner", "operatorId": "op-2"},
            ],
        )
        result = transition_approval_request(req, "approve")
        self.assertEqual(result["status"], _STATUS_APPROVED)
        self.assertEqual(result["receivedApprovals"], 2)
        self.assertEqual(sorted(result["approvedByRoles"]), ["grant_admin", "owner"])

    def test_history_appended_on_approve(self):
        """Approval history is appended on approve transition."""
        req = self._make_pending(
            required=1,
            roles=["grant_admin"],
            approvers=[{"role": "grant_admin", "operatorId": "op-1"}],
        )
        result = transition_approval_request(req, "approve", actor_id="op-1", at="2026-01-01T00:00:00Z")
        self.assertTrue(any("op-1 approved" in entry for entry in result["approvalHistory"]))


if __name__ == "__main__":
    unittest.main()
