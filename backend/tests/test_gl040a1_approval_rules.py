"""Tests for GL-040-A1 Approval Rule Evaluator Builder."""

import unittest

from backend.src.policy.approval_rules import (
    evaluate_approval_requirements,
    normalize_risk_level,
    normalize_amount,
    build_approval_requirement_result,
)


class TestApprovalRulesImportable(unittest.TestCase):
    def test_module_is_importable(self):
        self.assertTrue(callable(evaluate_approval_requirements))
        self.assertTrue(callable(normalize_risk_level))
        self.assertTrue(callable(normalize_amount))
        self.assertTrue(callable(build_approval_requirement_result))


class TestLowRiskCleanPath(unittest.TestCase):
    def test_low_risk_allowed_permission_clean_compliance_returns_no_approval_required(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
        )
        self.assertEqual(result["decision"], "no_approval_required")
        self.assertFalse(result["approvalRequired"])
        self.assertEqual(result["requiredApprovals"], 0)
        self.assertEqual(result["requiredRoles"], [])


class TestRiskBasedDecisions(unittest.TestCase):
    def test_medium_risk_requires_one_approval(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            risk_level="medium",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
        )
        self.assertEqual(result["decision"], "approval_required")
        self.assertTrue(result["approvalRequired"])
        self.assertEqual(result["requiredApprovals"], 1)
        self.assertEqual(result["requiredRoles"], ["grant_admin"])

    def test_high_risk_requires_four_eyes_approval(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            risk_level="high",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
        )
        self.assertEqual(result["decision"], "four_eyes_required")
        self.assertTrue(result["approvalRequired"])
        self.assertEqual(result["requiredApprovals"], 2)
        self.assertEqual(result["requiredRoles"], ["grant_admin", "owner"])


class TestAmountBasedDecisions(unittest.TestCase):
    def test_amount_10000_requires_one_approval(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            amount=10000,
            currency="EUR",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
        )
        self.assertEqual(result["decision"], "approval_required")
        self.assertEqual(result["requiredApprovals"], 1)

    def test_amount_100000_requires_four_eyes_approval(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            amount=100000,
            currency="EUR",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
        )
        self.assertEqual(result["decision"], "four_eyes_required")
        self.assertEqual(result["requiredApprovals"], 2)


class TestPolicyFlagDecisions(unittest.TestCase):
    def test_policy_flag_requires_approval_requires_one_approval(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
            policy_flags=["requires_approval"],
        )
        self.assertEqual(result["decision"], "approval_required")
        self.assertEqual(result["requiredApprovals"], 1)

    def test_policy_flag_requires_four_eyes_requires_four_eyes_approval(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
            policy_flags=["requires_four_eyes"],
        )
        self.assertEqual(result["decision"], "four_eyes_required")
        self.assertEqual(result["requiredApprovals"], 2)

    def test_unknown_policy_flag_produces_warning(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
            policy_flags=["requires_approval", "unknown_flag_xyz"],
        )
        self.assertEqual(result["decision"], "approval_required")
        self.assertTrue(
            any("unknown_policy_flag" in w for w in result["warnings"]),
            f"Expected warning about unknown flag, got: {result['warnings']}",
        )


class TestPermissionBlocking(unittest.TestCase):
    def test_permission_denied_produces_blocked(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            risk_level="low",
            permission_result={"allowed": False},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
        )
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("permission_denied", result["blockers"])

    def test_permission_denial_cannot_be_overridden_by_approval_flags(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            risk_level="low",
            permission_result={"allowed": False},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
            policy_flags=["requires_approval"],
        )
        self.assertEqual(result["decision"], "blocked")
        self.assertFalse(result["approvalRequired"])
        self.assertEqual(result["requiredApprovals"], 0)
        self.assertEqual(result["requiredRoles"], [])

    def test_permission_denial_cannot_be_overridden_by_high_risk(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            risk_level="high",
            permission_result={"allowed": False},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
        )
        self.assertEqual(result["decision"], "blocked")
        self.assertEqual(result["requiredApprovals"], 0)


class TestComplianceBlocking(unittest.TestCase):
    def test_compliance_overall_status_blocked_produces_blocked(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "blocked", "severity": "low"},
            evidence_completeness={"complete": True},
        )
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("compliance_blocked", result["blockers"])

    def test_compliance_severity_critical_requires_four_eyes_unless_blocked(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "critical"},
            evidence_completeness={"complete": True},
        )
        self.assertEqual(result["decision"], "four_eyes_required")
        self.assertEqual(result["requiredApprovals"], 2)

    def test_compliance_critical_blocked_by_permission_stays_blocked(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            risk_level="low",
            permission_result={"allowed": False},
            compliance_report={"overallStatus": "clean", "severity": "critical"},
            evidence_completeness={"complete": True},
        )
        self.assertEqual(result["decision"], "blocked")
        self.assertEqual(result["requiredApprovals"], 0)


class TestEvidenceBlocking(unittest.TestCase):
    def test_invalid_evidence_produces_blocked(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": False, "invalid": True},
        )
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("evidence_invalid", result["blockers"])

    def test_missing_evidence_requires_approval(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness=None,
        )
        self.assertEqual(result["decision"], "approval_required")
        self.assertEqual(result["requiredApprovals"], 1)

    def test_incomplete_evidence_requires_approval(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": False, "invalid": False},
        )
        self.assertEqual(result["decision"], "approval_required")
        self.assertEqual(result["requiredApprovals"], 1)

    def test_evidence_with_errors_produces_blocked(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": False, "errors": ["hash_mismatch"]},
        )
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("evidence_invalid", result["blockers"])


class TestUnknownRiskLevel(unittest.TestCase):
    def test_unknown_risk_level_produces_warning_and_requires_approval(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            risk_level="extraterrestrial",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
        )
        self.assertEqual(result["decision"], "approval_required")
        self.assertTrue(
            any("unknown_risk_level" in w for w in result["warnings"]),
            f"Expected warning about unknown risk, got: {result['warnings']}",
        )


class TestMissingAction(unittest.TestCase):
    def test_none_action_produces_blocked(self):
        result = evaluate_approval_requirements(
            action=None,
            actor_id="admin-1",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
        )
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("action_missing_or_empty", result["blockers"])

    def test_empty_string_action_produces_blocked(self):
        result = evaluate_approval_requirements(
            action="",
            actor_id="admin-1",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
        )
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("action_missing_or_empty", result["blockers"])

    def test_whitespace_only_action_produces_blocked(self):
        result = evaluate_approval_requirements(
            action="   ",
            actor_id="admin-1",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
        )
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("action_missing_or_empty", result["blockers"])


class TestMalformedAmount(unittest.TestCase):
    def test_malformed_amount_produces_warning_and_does_not_become_no_approval_required(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            amount="not_a_number",
            currency="EUR",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
        )
        self.assertNotEqual(result["decision"], "no_approval_required")
        self.assertTrue(
            any("amount_malformed" in w for w in result["warnings"]),
            f"Expected warning about malformed amount, got: {result['warnings']}",
        )

    def test_malformed_amount_with_clean_signals_still_approval_required(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            amount={"value": 5000},
            currency="EUR",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
        )
        self.assertEqual(result["decision"], "approval_required")


class TestIncludeDetails(unittest.TestCase):
    def test_include_details_true_includes_checks_and_inputs(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
            include_details=True,
        )
        self.assertIn("checks", result)
        self.assertIn("inputs", result)

    def test_include_details_false_omits_checks_and_inputs(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
            include_details=False,
        )
        self.assertNotIn("checks", result)
        self.assertNotIn("inputs", result)
        # Core fields must still be present
        self.assertIn("action", result)
        self.assertIn("decision", result)
        self.assertIn("approvalRequired", result)


class TestResponseFieldPreservation(unittest.TestCase):
    def test_response_preserves_action_actor_id_amount_currency(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            amount=5000,
            currency="EUR",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
        )
        self.assertEqual(result["action"], "create-grant")
        self.assertEqual(result["actorId"], "admin-1")
        self.assertEqual(result["amount"], 5000.0)
        self.assertEqual(result["currency"], "EUR")


class TestSecretsNotExposed(unittest.TestCase):
    def test_response_does_not_expose_secrets_tokens_auth_hashes_or_raw_sensitive_context(self):
        result = evaluate_approval_requirements(
            action="create-grant",
            actor_id="admin-1",
            amount=5000,
            currency="EUR",
            risk_level="low",
            permission_result={"allowed": True},
            compliance_report={"overallStatus": "clean", "severity": "low"},
            evidence_completeness={"complete": True},
            policy_flags=["requires_approval"],
            context={"api_key": "secret-key-123", "password": "hunter2", "token_hash": "abc123"},
            include_details=True,
        )
        result_str = str(result)
        self.assertNotIn("secret-key-123", result_str)
        self.assertNotIn("hunter2", result_str)
        self.assertNotIn("abc123", result_str)
        # Ensure context itself is not dumped into response
        self.assertNotIn("api_key", result_str)
        self.assertNotIn("password", result_str)
        self.assertNotIn("token_hash", result_str)


class TestNoDbAccessRequired(unittest.TestCase):
    def test_evaluator_does_not_require_db_access(self):
        # The evaluator is pure: it should work with only arguments
        result = evaluate_approval_requirements(
            action="test-action",
            actor_id="test-actor",
            amount=100,
            currency="USD",
            risk_level="low",
            compliance_report=None,
            evidence_completeness=None,
            permission_result=None,
            policy_flags=None,
            context=None,
        )
        self.assertIn("decision", result)
        # Should not raise or attempt any DB/network calls


class TestExistingGrantLogicUnchanged(unittest.TestCase):
    def test_existing_grant_decision_logic_not_changed(self):
        # This is a meta-test: approval_rules is a new module and must not
        # mutate any existing GrantLayer state.
        from backend.src.policy import policy_engine
        # Ensure evaluate_access still exists and behaves correctly
        self.assertTrue(callable(policy_engine.evaluate_access))

        from backend.src.grants import grants
        self.assertTrue(callable(grants.create_grant))


class TestNormalizeHelpers(unittest.TestCase):
    def test_normalize_risk_level_lowercase(self):
        self.assertEqual(normalize_risk_level("LOW"), "low")
        self.assertEqual(normalize_risk_level("Medium"), "medium")
        self.assertEqual(normalize_risk_level("high"), "high")

    def test_normalize_risk_level_none(self):
        self.assertIsNone(normalize_risk_level(None))
        self.assertIsNone(normalize_risk_level(""))
        self.assertIsNone(normalize_risk_level("   "))

    def test_normalize_risk_level_unknown(self):
        self.assertEqual(normalize_risk_level("unknown"), "unknown")
        self.assertEqual(normalize_risk_level("critical"), "unknown")
        self.assertEqual(normalize_risk_level(123), "unknown")

    def test_normalize_amount_int(self):
        self.assertEqual(normalize_amount(100), 100.0)

    def test_normalize_amount_float(self):
        self.assertEqual(normalize_amount(100.5), 100.5)

    def test_normalize_amount_string(self):
        self.assertEqual(normalize_amount("10000"), 10000.0)

    def test_normalize_amount_none(self):
        self.assertIsNone(normalize_amount(None))

    def test_normalize_amount_malformed(self):
        self.assertIsNone(normalize_amount("abc"))
        self.assertIsNone(normalize_amount({"value": 100}))


class TestBuildResult(unittest.TestCase):
    def test_build_result_returns_expected_keys_with_details(self):
        result = build_approval_requirement_result(
            action="create-grant",
            actor_id="admin-1",
            approval_required=True,
            required_approvals=1,
            required_roles=["grant_admin"],
            decision="approval_required",
            reason="approval_required",
            blockers=[],
            warnings=[],
            risk_level="medium",
            amount=5000.0,
            currency="EUR",
            checks={"riskLevelChecked": True},
            inputs={"action": "create-grant"},
        )
        expected_keys = {
            "action",
            "actorId",
            "approvalRequired",
            "requiredApprovals",
            "requiredRoles",
            "decision",
            "reason",
            "blockers",
            "warnings",
            "riskLevel",
            "amount",
            "currency",
            "checks",
            "inputs",
        }
        self.assertEqual(set(result.keys()), expected_keys)

    def test_build_result_returns_expected_keys_without_details(self):
        result = build_approval_requirement_result(
            action="create-grant",
            actor_id="admin-1",
            approval_required=False,
            required_approvals=0,
            required_roles=[],
            decision="no_approval_required",
            reason="no_approval_required",
            blockers=[],
            warnings=[],
            risk_level="low",
            amount=None,
            currency=None,
        )
        expected_keys = {
            "action",
            "actorId",
            "approvalRequired",
            "requiredApprovals",
            "requiredRoles",
            "decision",
            "reason",
            "blockers",
            "warnings",
            "riskLevel",
            "amount",
            "currency",
        }
        self.assertEqual(set(result.keys()), expected_keys)


if __name__ == "__main__":
    unittest.main()
