"""Tests for GL-039-A1 Agent Permission Scope Evaluator."""

import unittest

from backend.src.policy_engine import evaluate_access
from backend.src.models import AccessRequest, Grant
from backend.src.agent_permissions import (
    evaluate_agent_permission,
    normalize_scope,
    scope_matches,
    build_agent_permission_result,
    KNOWN_SCOPES,
)


class TestAgentPermissionScopeEvaluator(unittest.TestCase):
    def test_module_is_importable(self):
        self.assertTrue(callable(evaluate_agent_permission))
        self.assertTrue(callable(normalize_scope))
        self.assertTrue(callable(scope_matches))
        self.assertTrue(callable(build_agent_permission_result))

    def test_exact_scope_allows(self):
        result = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="evidence:read",
            assigned_scopes=["evidence:read"],
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["matchedScope"], "evidence:read")
        self.assertEqual(result["reason"], "scope_matched")

    def test_missing_scopes_denies(self):
        result = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="evidence:read",
            assigned_scopes=[],
        )
        self.assertFalse(result["allowed"])
        self.assertIsNone(result["matchedScope"])
        self.assertEqual(result["reason"], "scope_not_matched")

    def test_unknown_requested_scope_denies(self):
        result = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="evidence:frobnicate",
            assigned_scopes=["evidence:frobnicate"],
        )
        self.assertFalse(result["allowed"])
        self.assertIsNone(result["matchedScope"])
        self.assertEqual(result["reason"], "requested_scope_unknown")

    def test_malformed_assigned_scope_is_ignored(self):
        result = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="evidence:read",
            assigned_scopes=["evidence"],
        )
        self.assertFalse(result["allowed"])
        self.assertIsNone(result["matchedScope"])
        self.assertEqual(result["reason"], "scope_not_matched")
        self.assertEqual(len(result["warnings"]), 1)
        self.assertIn("malformed", result["warnings"][0])

    def test_malformed_requested_scope_denies(self):
        result = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="evidence",
            assigned_scopes=["evidence:read"],
        )
        self.assertFalse(result["allowed"])
        self.assertIsNone(result["matchedScope"])
        self.assertEqual(result["reason"], "requested_scope_malformed")

    def test_wildcard_read_allows_read(self):
        result = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="evidence:read",
            assigned_scopes=["*:read"],
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["matchedScope"], "*:read")

    def test_wildcard_read_does_not_allow_verify(self):
        result = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="evidence:verify",
            assigned_scopes=["*:read"],
        )
        self.assertFalse(result["allowed"])
        self.assertIsNone(result["matchedScope"])

    def test_wildcard_read_does_not_allow_admin(self):
        result = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="admin:*",
            assigned_scopes=["*:read"],
        )
        self.assertFalse(result["allowed"])
        self.assertIsNone(result["matchedScope"])

    def test_admin_star_allows_known_scopes(self):
        for known in KNOWN_SCOPES:
            with self.subTest(known=known):
                result = evaluate_agent_permission(
                    agent_id="agent-1",
                    requested_scope=known,
                    assigned_scopes=["admin:*"],
                )
                self.assertTrue(result["allowed"], f"Expected {known} allowed by admin:*")
                self.assertEqual(result["matchedScope"], "admin:*")

    def test_read_does_not_imply_write_or_admin(self):
        forbidden_scopes = ["evidence:write", "evidence:admin", "grant:write", "admin:*"]
        for forbidden in forbidden_scopes:
            with self.subTest(forbidden=forbidden):
                result = evaluate_agent_permission(
                    agent_id="agent-1",
                    requested_scope=forbidden,
                    assigned_scopes=["evidence:read"],
                )
                self.assertFalse(result["allowed"])

    def test_resource_type_and_resource_id_preserved(self):
        result = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="evidence:read",
            assigned_scopes=["evidence:read"],
            resource_type="bundle",
            resource_id="bundle-id-123",
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["resourceType"], "bundle")
        self.assertEqual(result["resourceId"], "bundle-id-123")

    def test_deny_by_default_empty_request(self):
        result = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="",
            assigned_scopes=["*:read"],
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "requested_scope_missing")

    def test_no_secrets_in_response(self):
        result = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="evidence:read",
            assigned_scopes=["evidence:read"],
        )
        for key in result:
            if isinstance(result[key], str):
                self.assertNotIn("token", result[key].lower())
                self.assertNotIn("secret", result[key].lower())
                self.assertNotIn("password", result[key].lower())
                self.assertNotIn("hash", result[key].lower())

    def test_grant_decision_logic_unchanged(self):
        """policy_engine.evaluate_access still works independently."""
        grant = Grant(
            subject_id="alice",
            role="user",
            action="read",
            resource="file-1",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2028-01-01T00:00:00Z",
            created_by="test",
            reason="test",
        )
        request = AccessRequest(
            subject_id="alice",
            role="user",
            action="read",
            resource="file-1",
        )
        import datetime
        result = evaluate_access(request, [grant], datetime.datetime.utcnow())
        self.assertTrue(result.approved)

    def test_case_insensitive_scope_matching(self):
        result = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="Evidence:READ",
            assigned_scopes=["EVIDENCE:read"],
        )
        self.assertTrue(result["allowed"])

    def test_context_optional_and_not_required(self):
        result_with = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="evidence:read",
            assigned_scopes=["evidence:read"],
            context={"ip": "127.0.0.1"},
        )
        result_without = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="evidence:read",
            assigned_scopes=["evidence:read"],
        )
        self.assertEqual(result_with["allowed"], result_without["allowed"])

    def test_empty_assigned_scopes_list_denies(self):
        result = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="evidence:read",
            assigned_scopes=[],
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "scope_not_matched")

    def test_unknown_requested_scope_even_with_admin_star(self):
        result = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="evidence:frobnicate",
            assigned_scopes=["admin:*"],
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "requested_scope_unknown")

    def test_only_well_formed_known_scopes_allowed_by_admin_star(self):
        result = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="not_valid_scope",
            assigned_scopes=["admin:*"],
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "requested_scope_malformed")

    def test_preserve_wildcard_assigned_scope_in_matched(self):
        result = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="evidence:read",
            assigned_scopes=["*:read"],
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["matchedScope"], "*:read")

    def test_multiple_assigned_scopes_finds_matching(self):
        result = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="provenance:read",
            assigned_scopes=["evidence:read", "*:read"],
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["matchedScope"], "*:read")

    def test_none_values_for_resource_passthrough(self):
        result = evaluate_agent_permission(
            agent_id="agent-1",
            requested_scope="evidence:read",
            assigned_scopes=["evidence:read"],
            resource_type=None,
            resource_id=None,
        )
        self.assertTrue(result["allowed"])
        self.assertIsNone(result["resourceType"])
        self.assertIsNone(result["resourceId"])


class TestNormalizeScope(unittest.TestCase):
    def test_lowercase(self):
        self.assertEqual(normalize_scope("Evidence:READ"), "evidence:read")

    def test_strips_whitespace(self):
        self.assertEqual(normalize_scope("  evidence:read  "), "evidence:read")

    def test_non_string_returns_empty(self):
        self.assertEqual(normalize_scope(None), "")
        self.assertEqual(normalize_scope(123), "")


class TestScopeMatches(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(scope_matches("evidence:read", "evidence:read"))

    def test_no_match_different_resource(self):
        self.assertFalse(scope_matches("evidence:read", "grant:read"))

    def test_no_match_different_action(self):
        self.assertFalse(scope_matches("evidence:read", "evidence:verify"))

    def test_wildcard_read_match(self):
        self.assertTrue(scope_matches("*:read", "grant:read"))

    def test_wildcard_read_no_match_for_verify(self):
        self.assertFalse(scope_matches("*:read", "grant:verify"))

    def test_admin_star_matches_known(self):
        self.assertTrue(scope_matches("admin:*", "auditor_report:read"))

    def test_admin_star_denies_unknown_action(self):
        self.assertFalse(scope_matches("admin:*", "evidence:frobnicate"))

    def test_malformed_assigned(self):
        self.assertFalse(scope_matches("evidence", "evidence:read"))

    def test_malformed_requested(self):
        self.assertFalse(scope_matches("evidence:read", "evidence"))


class TestBuildAgentPermissionResult(unittest.TestCase):
    def test_returns_expected_keys(self):
        result = build_agent_permission_result(
            allowed=True,
            agent_id="agent-1",
            requested_scope="evidence:read",
            matched_scope="evidence:read",
            resource_type="bundle",
            resource_id="123",
            reason="scope_matched",
            warnings=[],
        )
        expected_keys = {
            "allowed",
            "agentId",
            "requestedScope",
            "matchedScope",
            "resourceType",
            "resourceId",
            "reason",
            "warnings",
        }
        self.assertEqual(set(result.keys()), expected_keys)


if __name__ == "__main__":
    unittest.main()
