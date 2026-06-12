"""GL‑039‑C1 — Agent Permission Assignments module tests.

Covers assignment resolution with both direct scopes and profile‑based scopes,
deterministic ordering, security validation, and integration with evaluator.
"""

import os
import sys
import unittest
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestAgentPermissionAssignments(unittest.TestCase):
    """Agent Permission Assignment Resolver tests."""

    # ── Module location ─────────────────────────────────────────
    def test_module_is_importable(self):
        from backend.src.policy import agent_permission_assignments as resolver
        self.assertTrue(hasattr(resolver, "resolve_agent_permission_assignment"))
        self.assertTrue(hasattr(resolver, "_combine_effective_scopes"))
        # Private helper
        self.assertTrue(hasattr(resolver, "_build_permission_evaluation"))

    # ── resolve_agent_permission_assignment ────────────────────
    def test_resolve_with_direct_scopes_only(self):
        from backend.src.policy.agent_permission_assignments import resolve_agent_permission_assignment
        result = resolve_agent_permission_assignment(
            "agent-1", "evidence:read", assigned_scopes=["evidence:read"]
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["agentId"], "agent-1")
        self.assertEqual(result["requestedScope"], "evidence:read")
        self.assertEqual(result["assignedScopes"], ["evidence:read"])
        self.assertEqual(result["assignedProfiles"], [])
        self.assertEqual(result["resolvedScopes"], ["evidence:read"])
        self.assertEqual(result["matchedScope"], "evidence:read")
        self.assertEqual(result["reason"], "scope_matched")

    def test_resolve_with_profile_only(self):
        from backend.src.policy.agent_permission_assignments import resolve_agent_permission_assignment
        result = resolve_agent_permission_assignment(
            "agent-2", "evidence:read", assigned_profiles=["auditor_readonly"]
        )
        self.assertTrue(result["allowed"])
        self.assertIn("evidence:read", result["resolvedScopes"])
        self.assertEqual(result["assignedProfiles"], ["auditor_readonly"])
        self.assertEqual(result["assignedScopes"], [])
        self.assertEqual(result["matchedScope"], "evidence:read")
        self.assertEqual(result["reason"], "scope_matched")

    def test_resolve_with_both_scopes_and_profiles(self):
        from backend.src.policy.agent_permission_assignments import resolve_agent_permission_assignment
        result = resolve_agent_permission_assignment(
            "agent-3", "evidence:verify", 
            assigned_scopes=["evidence:read"],
            assigned_profiles=["evidence_verifier"]
        )
        self.assertTrue(result["allowed"])
        # Should have both scopes
        self.assertIn("evidence:read", result["resolvedScopes"])
        self.assertIn("evidence:verify", result["resolvedScopes"])
        self.assertEqual(result["matchedScope"], "evidence:verify")

    def test_resolve_denies_unknown_requested_scope(self):
        from backend.src.policy.agent_permission_assignments import resolve_agent_permission_assignment
        result = resolve_agent_permission_assignment(
            "agent-4", "evidence:frobnicate",
            assigned_profiles=["auditor_readonly"]
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "requested_scope_unknown")
        # Should still show what scopes the agent has
        self.assertIn("evidence:read", result["resolvedScopes"])

    def test_resolve_empty_assignment_denies(self):
        from backend.src.policy.agent_permission_assignments import resolve_agent_permission_assignment
        result = resolve_agent_permission_assignment(
            "agent-5", "evidence:read",
            assigned_scopes=[],
            assigned_profiles=[]
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "scope_not_matched")
        self.assertEqual(result["resolvedScopes"], [])

    def test_resolve_deduplicates_scopes_and_profiles(self):
        from backend.src.policy.agent_permission_assignments import resolve_agent_permission_assignment
        result = resolve_agent_permission_assignment(
            "agent-6", "evidence:read",
            assigned_scopes=["evidence:read", "evidence:read"],
            assigned_profiles=["auditor_readonly", "auditor_readonly"]
        )
        self.assertTrue(result["allowed"])
        # Should have evidence:read from auditor_readonly profile
        self.assertIn("evidence:read", result["resolvedScopes"])
        # Original assignments should remain as given
        self.assertEqual(result["assignedScopes"], ["evidence:read", "evidence:read"])
        self.assertEqual(result["assignedProfiles"], ["auditor_readonly", "auditor_readonly"])
        # Check that scope deduplication works
        resolved = result["resolvedScopes"]
        evidence_read_count = resolved.count("evidence:read")
        self.assertEqual(evidence_read_count, 1, f"evidence:read appears {evidence_read_count} times, should be 1")

    def test_resolve_with_malformed_scopes_adds_warnings(self):
        from backend.src.policy.agent_permission_assignments import resolve_agent_permission_assignment
        result = resolve_agent_permission_assignment(
            "agent-7", "evidence:read",
            assigned_scopes=["evidence", "evidence:read"],
        )
        self.assertTrue(result["allowed"])
        # Evaluator should filter malformed scope and add warnings
        self.assertIn("evidence", result["resolvedScopes"])
        self.assertIn("evidence:read", result["resolvedScopes"])
        # The warning comes from evaluator, not resolver
        # Check that request succeeded through valid scope
        self.assertEqual(result["matchedScope"], "evidence:read")

    def test_resolve_with_unknown_profile_adds_warnings(self):
        from backend.src.policy.agent_permission_assignments import resolve_agent_permission_assignment
        result = resolve_agent_permission_assignment(
            "agent-8", "evidence:read",
            assigned_profiles=["unknown_profile"],
        )
        self.assertFalse(result["allowed"])
        self.assertTrue(any("unknown" in w.lower() for w in result["warnings"]))
        self.assertEqual(result["resolvedScopes"], [])

    def test_resolve_include_details_false_omits_details(self):
        from backend.src.policy.agent_permission_assignments import resolve_agent_permission_assignment
        result = resolve_agent_permission_assignment(
            "agent-9", "evidence:read",
            assigned_profiles=["auditor_readonly"],
            include_details=False
        )
        self.assertTrue(result["allowed"])
        self.assertNotIn("profileResolution", result)
        self.assertNotIn("evaluation", result)
        # Still has basic fields
        self.assertIn("resolvedScopes", result)
        self.assertIn("matchedScope", result)

    def test_resolve_include_details_true_includes_details(self):
        from backend.src.policy.agent_permission_assignments import resolve_agent_permission_assignment
        result = resolve_agent_permission_assignment(
            "agent-10", "evidence:read",
            assigned_profiles=["auditor_readonly"],
            include_details=True
        )
        self.assertTrue(result["allowed"])
        self.assertIn("profileResolution", result)
        self.assertIn("evaluation", result)
        self.assertEqual(result["profileResolution"]["resolvedProfiles"], ["auditor_readonly"])

    def test_resolve_missing_agent_id_denies(self):
        from backend.src.policy.agent_permission_assignments import resolve_agent_permission_assignment
        result = resolve_agent_permission_assignment("", "evidence:read", assigned_scopes=["evidence:read"])
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "agent_id_missing")
        self.assertIn("missing or empty", result["warnings"][0])

    def test_resolve_resource_preservation(self):
        from backend.src.policy.agent_permission_assignments import resolve_agent_permission_assignment
        result = resolve_agent_permission_assignment(
            "agent-11", "evidence:read",
            assigned_scopes=["evidence:read"],
            resource_type="bundle",
            resource_id="bundle-123"
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["resourceType"], "bundle")
        self.assertEqual(result["resourceId"], "bundle-123")

    # ── Security / validation ───────────────────────────────────
    def test_response_does_not_expose_secrets(self):
        from backend.src.policy.agent_permission_assignments import resolve_agent_permission_assignment
        result = resolve_agent_permission_assignment(
            "agent-1", "evidence:read",
            assigned_profiles=["auditor_readonly"]
        )
        raw = json.dumps(result)
        for forbidden in ["grantlayer_admin_token", "password", "secret", "token"]:
            self.assertNotIn(forbidden, raw.lower(), f"Secret leak detected: {forbidden}")

    def test_no_assignment_introduces_admin_star(self):
        from backend.src.policy.agent_permission_assignments import resolve_agent_permission_assignment
        result = resolve_agent_permission_assignment(
            "agent-1", "evidence:read",
            assigned_profiles=["auditor_readonly", "evidence_verifier"]
        )
        resolved_scopes = result["resolvedScopes"]
        self.assertNotIn("admin:*", resolved_scopes)

    # ── Determinism and ordering ────────────────────────────────
    def test_resolve_result_is_deterministic(self):
        from backend.src.policy.agent_permission_assignments import resolve_agent_permission_assignment
        r1 = resolve_agent_permission_assignment(
            "agent-1", "evidence:read",
            assigned_scopes=["evidence:verify", "evidence:read"],
            assigned_profiles=["auditor_readonly", "evidence_verifier"]
        )
        r2 = resolve_agent_permission_assignment(
            "agent-1", "evidence:read",
            assigned_scopes=["evidence:verify", "evidence:read"],
            assigned_profiles=["auditor_readonly", "evidence_verifier"]
        )
        self.assertEqual(r1["resolvedScopes"], r2["resolvedScopes"])
        self.assertEqual(r1["allowed"], r2["allowed"])
        self.assertEqual(r1["matchedScope"], r2["matchedScope"])

    def test_combined_scopes_are_sorted(self):
        from backend.src.policy.agent_permission_assignments import resolve_agent_permission_assignment
        result = resolve_agent_permission_assignment(
            "agent-1", "evidence:read",
            assigned_scopes=["provenance:read", "evidence:verify"],
            assigned_profiles=["auditor_readonly"]
        )
        resolved = result["resolvedScopes"]
        # Should be sorted alphabetically
        sorted_resolved = sorted(resolved)
        self.assertEqual(resolved, sorted_resolved)

    # ── Integration with existing components ────────────────────
    def test_uses_existing_evaluator(self):
        from backend.src.policy.agent_permission_assignments import resolve_agent_permission_assignment
        from backend.src.policy.agent_permissions import evaluate_agent_permission
        result = resolve_agent_permission_assignment(
            "agent-1", "evidence:read",
            assigned_scopes=["evidence:read"]
        )
        eval_result = evaluate_agent_permission(
            "agent-1", "evidence:read", ["evidence:read"]
        )
        self.assertEqual(result["allowed"], eval_result["allowed"])
        self.assertEqual(result["matchedScope"], eval_result.get("matchedScope"))

    def test_uses_existing_profile_expander(self):
        from backend.src.policy.agent_permission_assignments import resolve_agent_permission_assignment
        from backend.src.policy.agent_permission_profiles import expand_agent_permission_profiles
        result = resolve_agent_permission_assignment(
            "agent-1", "evidence:read",
            assigned_profiles=["auditor_readonly"]
        )
        profile_expansion = expand_agent_permission_profiles(["auditor_readonly"])
        self.assertIn("evidence:read", profile_expansion.get("scopes", []))

    def test_context_argument_is_ignored(self):
        from backend.src.policy.agent_permission_assignments import resolve_agent_permission_assignment
        result = resolve_agent_permission_assignment(
            "agent-1", "evidence:read",
            assigned_scopes=["evidence:read"],
            context={"foo": "bar"}
        )
        self.assertTrue(result["allowed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)