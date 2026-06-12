"""GL-039-B1 — Agent Permission Scope Profiles Builder tests.

Covers module importability, profile retrieval, listing, expansion,
validation, deterministic ordering, secrets safety, and integration
with the existing agent permission evaluator.
"""

import os
import sys
import unittest
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestAgentPermissionScopeProfiles(unittest.TestCase):
    """Agent Permission Scope Profiles Builder tests."""

    # ── Module location ─────────────────────────────────────────
    def test_module_is_importable(self):
        from backend.src.policy import agent_permission_profiles as app
        self.assertTrue(hasattr(app, "get_agent_permission_profile"))
        self.assertTrue(hasattr(app, "list_agent_permission_profiles"))
        self.assertTrue(hasattr(app, "expand_agent_permission_profiles"))
        self.assertTrue(hasattr(app, "build_agent_permission_profile_result"))

    # ── get_agent_permission_profile ────────────────────────────
    def test_known_profile_auditor_readonly(self):
        from backend.src.policy.agent_permission_profiles import get_agent_permission_profile
        profile = get_agent_permission_profile("auditor_readonly")
        self.assertIsNotNone(profile)
        self.assertEqual(profile["profileName"], "auditor_readonly")
        expected = [
            "evidence:read",
            "provenance:read",
            "auditor_report:read",
            "compliance_gap:read",
            "grant_execution:read",
        ]
        self.assertEqual(profile["scopes"], expected)

    def test_known_profile_evidence_verifier(self):
        from backend.src.policy.agent_permission_profiles import get_agent_permission_profile
        profile = get_agent_permission_profile("evidence_verifier")
        self.assertIsNotNone(profile)
        self.assertIn("evidence:verify", profile["scopes"])
        self.assertNotIn("admin:*", profile["scopes"])

    def test_known_profile_grant_operator_readonly(self):
        from backend.src.policy.agent_permission_profiles import get_agent_permission_profile
        profile = get_agent_permission_profile("grant_operator_readonly")
        self.assertIsNotNone(profile)
        self.assertIn("grant:read", profile["scopes"])
        self.assertIn("evidence:read", profile["scopes"])

    def test_known_profile_compliance_reviewer(self):
        from backend.src.policy.agent_permission_profiles import get_agent_permission_profile
        profile = get_agent_permission_profile("compliance_reviewer")
        self.assertIsNotNone(profile)
        self.assertIn("compliance_gap:read", profile["scopes"])
        self.assertIn("grant:read", profile["scopes"])

    def test_unknown_profile_returns_none(self):
        from backend.src.policy.agent_permission_profiles import get_agent_permission_profile
        self.assertIsNone(get_agent_permission_profile("nonexistent_profile"))
        self.assertIsNone(get_agent_permission_profile(""))
        self.assertIsNone(get_agent_permission_profile("   "))

    def test_profile_name_is_case_insensitive(self):
        from backend.src.policy.agent_permission_profiles import get_agent_permission_profile
        lower = get_agent_permission_profile("auditor_readonly")
        upper = get_agent_permission_profile("AUDITOR_READONLY")
        mixed = get_agent_permission_profile("Auditor_Readonly")
        self.assertIsNotNone(lower)
        self.assertIsNotNone(upper)
        self.assertIsNotNone(mixed)
        self.assertEqual(lower["scopes"], upper["scopes"])
        self.assertEqual(lower["scopes"], mixed["scopes"])

    # ── list_agent_permission_profiles ──────────────────────────
    def test_list_profiles_returns_deterministic_order(self):
        from backend.src.policy.agent_permission_profiles import list_agent_permission_profiles
        profiles = list_agent_permission_profiles()
        names = [p["profileName"] for p in profiles]
        self.assertEqual(names, sorted(names))
        self.assertTrue(len(profiles) >= 4)

    def test_list_profiles_contains_all_built_ins(self):
        from backend.src.policy.agent_permission_profiles import list_agent_permission_profiles
        profiles = list_agent_permission_profiles()
        names = {p["profileName"] for p in profiles}
        self.assertIn("auditor_readonly", names)
        self.assertIn("evidence_verifier", names)
        self.assertIn("grant_operator_readonly", names)
        self.assertIn("compliance_reviewer", names)

    # ── expand_agent_permission_profiles ────────────────────────
    def test_expand_multiple_profiles_returns_deduplicated_sorted_scopes(self):
        from backend.src.policy.agent_permission_profiles import expand_agent_permission_profiles
        result = expand_agent_permission_profiles(["auditor_readonly", "evidence_verifier"])
        scopes = result["scopes"]
        self.assertEqual(scopes, sorted(set(scopes)))
        self.assertIn("evidence:read", scopes)
        self.assertIn("evidence:verify", scopes)
        self.assertIn("auditor_report:read", scopes)

    def test_expand_duplicate_profile_names_do_not_duplicate_scopes(self):
        from backend.src.policy.agent_permission_profiles import expand_agent_permission_profiles
        result = expand_agent_permission_profiles(
            ["auditor_readonly", "auditor_readonly"]
        )
        scopes = result["scopes"]
        self.assertEqual(len(scopes), len(set(scopes)))

    def test_expand_unknown_profile_adds_warning(self):
        from backend.src.policy.agent_permission_profiles import expand_agent_permission_profiles
        result = expand_agent_permission_profiles(["auditor_readonly", "unknown_xyz"])
        self.assertIn("evidence:read", result["scopes"])
        self.assertTrue(
            any("unknown_xyz" in w for w in result["warnings"]),
            f"Expected warning about unknown profile, got {result['warnings']}"
        )

    def test_expand_empty_list_returns_empty(self):
        from backend.src.policy.agent_permission_profiles import expand_agent_permission_profiles
        result = expand_agent_permission_profiles([])
        self.assertEqual(result["scopes"], [])
        self.assertEqual(result["scopeCount"], 0)
        self.assertEqual(result["warnings"], [])

    # ── Security / validation ───────────────────────────────────
    def test_no_builtin_profile_contains_admin_star(self):
        from backend.src.policy.agent_permission_profiles import (
            list_agent_permission_profiles,
            expand_agent_permission_profiles,
        )
        profiles = list_agent_permission_profiles()
        for profile in profiles:
            self.assertNotIn("admin:*", profile["scopes"], f"{profile['profileName']} contains admin:*")

        expanded = expand_agent_permission_profiles([p["profileName"] for p in profiles])
        self.assertNotIn("admin:*", expanded["scopes"])

    def test_no_builtin_profile_contains_malformed_scopes(self):
        from backend.src.policy.agent_permission_profiles import list_agent_permission_profiles
        from backend.src.policy.agent_permissions import _is_valid_format
        profiles = list_agent_permission_profiles()
        for profile in profiles:
            for scope in profile["scopes"]:
                self.assertTrue(
                    _is_valid_format(scope),
                    f"{profile['profileName']} has malformed scope: {scope}"
                )

    def test_profile_scopes_work_with_evaluate_agent_permission(self):
        from backend.src.policy.agent_permission_profiles import get_agent_permission_profile
        from backend.src.policy.agent_permissions import evaluate_agent_permission
        profile = get_agent_permission_profile("auditor_readonly")
        for scope in profile["scopes"]:
            result = evaluate_agent_permission(
                agent_id="agent-1",
                requested_scope=scope,
                assigned_scopes=profile["scopes"],
            )
            self.assertTrue(result["allowed"], f"Expected {scope} to be allowed")
            self.assertEqual(result["reason"], "scope_matched")

    # ── Response shape ──────────────────────────────────────────
    def test_profile_result_has_minimum_fields(self):
        from backend.src.policy.agent_permission_profiles import get_agent_permission_profile
        profile = get_agent_permission_profile("auditor_readonly")
        self.assertIn("profileName", profile)
        self.assertIn("description", profile)
        self.assertIn("scopes", profile)
        self.assertIn("scopeCount", profile)
        self.assertIn("warnings", profile)
        self.assertIsInstance(profile["scopes"], list)
        self.assertIsInstance(profile["scopeCount"], int)
        self.assertIsInstance(profile["warnings"], list)

    def test_expand_result_has_minimum_fields(self):
        from backend.src.policy.agent_permission_profiles import expand_agent_permission_profiles
        result = expand_agent_permission_profiles(["auditor_readonly"])
        self.assertIn("scopes", result)
        self.assertIn("scopeCount", result)
        self.assertIn("warnings", result)
        self.assertIn("resolvedProfiles", result)

    # ── Secrets safety ──────────────────────────────────────────
    def test_profile_response_does_not_expose_secrets(self):
        from backend.src.policy.agent_permission_profiles import (
            get_agent_permission_profile,
            list_agent_permission_profiles,
            expand_agent_permission_profiles,
        )
        raw = json.dumps(get_agent_permission_profile("auditor_readonly"))
        raw += json.dumps(list_agent_permission_profiles())
        raw += json.dumps(expand_agent_permission_profiles(["auditor_readonly"]))
        for forbidden in ["token", "secret", "password", "hash", "private"]:
            self.assertNotIn(forbidden, raw.lower(), f"Secret leak detected: {forbidden}")

    # ── build_agent_permission_profile_result ───────────────────
    def test_build_result_validates_unknown_scopes(self):
        from backend.src.policy.agent_permission_profiles import build_agent_permission_profile_result
        result = build_agent_permission_profile_result(
            profile_name="test",
            scopes=["evidence:read", "unknown:action", "badscope"],
        )
        self.assertIn("evidence:read", result["scopes"])
        self.assertNotIn("unknown:action", result["scopes"])
        self.assertNotIn("badscope", result["scopes"])
        self.assertTrue(len(result["warnings"]) >= 1)

    def test_build_result_deduplicates_scopes(self):
        from backend.src.policy.agent_permission_profiles import build_agent_permission_profile_result
        result = build_agent_permission_profile_result(
            profile_name="test",
            scopes=["evidence:read", "evidence:read"],
        )
        self.assertEqual(result["scopes"], ["evidence:read"])
        self.assertEqual(result["scopeCount"], 1)

    def test_build_result_with_description(self):
        from backend.src.policy.agent_permission_profiles import build_agent_permission_profile_result
        result = build_agent_permission_profile_result(
            profile_name="test",
            scopes=["evidence:read"],
            description="A test profile.",
        )
        self.assertEqual(result["description"], "A test profile.")

    def test_build_result_without_description_defaults_to_empty(self):
        from backend.src.policy.agent_permission_profiles import build_agent_permission_profile_result
        result = build_agent_permission_profile_result(
            profile_name="test",
            scopes=["evidence:read"],
        )
        self.assertEqual(result["description"], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
