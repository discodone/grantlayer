"""Tests for GL-043-A Policy Requirement / Grant Rule Pack Evaluator."""

import unittest

from backend.src.policy_requirements import (
    evaluate_policy_requirements,
    normalize_policy_pack,
    evaluate_required_evidence,
    evaluate_exclusions,
    evaluate_deadlines,
    evaluate_amount_limits,
    build_policy_requirement_result,
    RECORD_TYPE,
    RECORD_VERSION,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

def _make_policy_pack(**kwargs) -> dict:
    defaults = {
        "policyPackId": "grant-policy-2026",
        "policyPackVersion": "v1",
        "name": "Example Grant Policy",
        "requiredEvidence": [
            {"type": "budget_plan", "required": True},
            {"type": "eligibility_statement", "required": True},
        ],
        "exclusions": [
            {"code": "sanctioned_entity", "severity": "blocking"},
            {"code": "missing_tax_clearance", "severity": "warning"},
        ],
        "deadlines": [
            {"name": "submission_deadline", "dueAt": "2026-12-31T23:59:59Z", "required": True}
        ],
        "amountLimits": {
            "maxAmount": 50000,
            "currency": "EUR",
        },
        "requiredRoles": ["grant_admin"],
        "approvalPolicy": {
            "minimumApprovals": 1,
            "fourEyesAboveAmount": 50000,
        },
    }
    defaults.update(kwargs)
    return defaults


def _make_subject(**kwargs) -> dict:
    defaults = {
        "subjectId": "grant-request-123",
        "amount": 25000,
        "currency": "EUR",
        "evidenceTypes": ["budget_plan", "eligibility_statement"],
        "exclusionCodes": [],
        "submittedAt": "2026-01-10T10:00:00Z",
    }
    defaults.update(kwargs)
    return defaults


# ──────────────────────────────────────────────
# Import / Existence
# ──────────────────────────────────────────────

class TestModuleImportable(unittest.TestCase):
    def test_module_is_importable(self):
        self.assertEqual(RECORD_TYPE, "policy_requirement_evaluation")
        self.assertEqual(RECORD_VERSION, "gl-policy-requirements-v1")
        self.assertTrue(callable(evaluate_policy_requirements))
        self.assertTrue(callable(normalize_policy_pack))


# ──────────────────────────────────────────────
# Happy path
# ──────────────────────────────────────────────

class TestCompleteCleanPolicyPack(unittest.TestCase):
    def test_complete_clean_policy_pack_returns_passed(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
            approval_requirement={"decision": "no_approval_required"},
            approval_lifecycle={"status": "approved"},
            decision_provenance={"decisionStatus": "approved"},
            auditor_export={"exportStatus": "ready"},
        )
        self.assertEqual(result["evaluationStatus"], "passed")
        self.assertEqual(result["readiness"], "ready")
        self.assertEqual(result["missingEvidence"], [])
        self.assertEqual(result["exclusionViolations"], [])
        self.assertEqual(result["deadlineStatus"], "on_time")
        self.assertEqual(result["amountStatus"], "within_limit")


# ──────────────────────────────────────────────
# Missing / malformed policy pack
# ──────────────────────────────────────────────

class TestMissingPolicyPack(unittest.TestCase):
    def test_missing_policy_pack_returns_blocked(self):
        result = evaluate_policy_requirements(
            policy_pack=None,
            subject=_make_subject(),
        )
        self.assertEqual(result["evaluationStatus"], "blocked")
        self.assertEqual(result["readiness"], "blocked")
        self.assertIn("policy_pack_missing", result["blockers"])
        self.assertIn("policy_pack", result["missingInputs"])


class TestMalformedPolicyPack(unittest.TestCase):
    def test_malformed_policy_pack_returns_blocked(self):
        result = evaluate_policy_requirements(
            policy_pack="not-a-dict",
            subject=_make_subject(),
        )
        self.assertEqual(result["evaluationStatus"], "blocked")
        self.assertEqual(result["readiness"], "blocked")
        self.assertIn("policy_pack_malformed", result["blockers"])

    def test_policy_pack_missing_id_returns_blocked(self):
        result = evaluate_policy_requirements(
            policy_pack={"name": "no-id"},
            subject=_make_subject(),
        )
        self.assertEqual(result["evaluationStatus"], "blocked")
        self.assertIn("policy_pack_malformed", result["blockers"])


# ──────────────────────────────────────────────
# Required evidence
# ──────────────────────────────────────────────

class TestRequiredEvidence(unittest.TestCase):
    def test_missing_required_evidence_creates_blocker(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(evidenceTypes=["budget_plan"]),
            evidence_completeness={"complete": False},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
        )
        self.assertIn("eligibility_statement", result["missingEvidence"])
        self.assertTrue(
            any("missing_required_evidence:eligibility_statement" in b for b in result["blockers"]),
            f"Expected blocker for missing required evidence, got: {result['blockers']}"
        )
        self.assertEqual(result["evaluationStatus"], "blocked")

    def test_missing_optional_evidence_creates_warning(self):
        pack = _make_policy_pack(
            requiredEvidence=[
                {"type": "budget_plan", "required": True},
                {"type": "optional_statement", "required": False},
            ]
        )
        result = evaluate_policy_requirements(
            policy_pack=pack,
            subject=_make_subject(evidenceTypes=["budget_plan"]),
            evidence_completeness={"complete": False},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
        )
        self.assertTrue(
            any("missing_optional_evidence:optional_statement" in w for w in result["warnings"]),
            f"Expected warning for missing optional evidence, got: {result['warnings']}"
        )
        # Should not be blocked because required evidence is present
        self.assertNotEqual(result["evaluationStatus"], "blocked")


# ──────────────────────────────────────────────
# Exclusions
# ──────────────────────────────────────────────

class TestExclusions(unittest.TestCase):
    def test_blocking_exclusion_creates_blocker(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(exclusionCodes=["sanctioned_entity"]),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
        )
        self.assertIn("sanctioned_entity", result["exclusionViolations"])
        self.assertTrue(
            any("exclusion:sanctioned_entity" in b for b in result["blockers"]),
            f"Expected blocker for exclusion, got: {result['blockers']}"
        )
        self.assertEqual(result["evaluationStatus"], "blocked")

    def test_warning_exclusion_creates_warning(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(exclusionCodes=["missing_tax_clearance"]),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
        )
        self.assertIn("missing_tax_clearance", result["exclusionViolations"])
        self.assertTrue(
            any("exclusion:missing_tax_clearance" in w for w in result["warnings"]),
            f"Expected warning for exclusion, got: {result['warnings']}"
        )
        self.assertNotEqual(result["evaluationStatus"], "blocked")


# ──────────────────────────────────────────────
# Compliance gap report
# ──────────────────────────────────────────────

class TestComplianceGapBlocking(unittest.TestCase):
    def test_high_critical_compliance_gaps_block_result(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(),
            evidence_completeness={"complete": True},
            compliance_gap_report={
                "overallStatus": "blocked",
                "severity": "critical",
                "blockingGaps": [{"gapId": "g1", "severity": "critical"}],
            },
            permission_result={"allowed": True},
        )
        self.assertEqual(result["evaluationStatus"], "blocked")
        self.assertTrue(
            any("compliance" in b for b in result["blockers"]),
            f"Expected compliance blocker, got: {result['blockers']}"
        )


# ──────────────────────────────────────────────
# Permission result
# ──────────────────────────────────────────────

class TestPermissionBlocking(unittest.TestCase):
    def test_permission_denied_blocks_result(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": False},
        )
        self.assertEqual(result["evaluationStatus"], "blocked")
        self.assertIn("permission_denied", result["blockers"])


# ──────────────────────────────────────────────
# Approval requirement / lifecycle
# ──────────────────────────────────────────────

class TestApprovalBlocking(unittest.TestCase):
    def test_approval_requirement_blocked_blocks_result(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
            approval_requirement={"decision": "blocked"},
            approval_lifecycle={"status": "approved"},
        )
        self.assertEqual(result["evaluationStatus"], "blocked")
        self.assertIn("approval_requirement_blocked", result["blockers"])

    def test_approval_lifecycle_blocked_blocks_result(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
            approval_requirement={"decision": "approved"},
            approval_lifecycle={"status": "blocked"},
        )
        self.assertEqual(result["evaluationStatus"], "blocked")
        self.assertIn("approval_lifecycle_blocked", result["blockers"])


# ──────────────────────────────────────────────
# Decision provenance
# ──────────────────────────────────────────────

class TestDecisionProvenanceBlocking(unittest.TestCase):
    def test_decision_provenance_blocked_blocks_result(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
            approval_requirement={"decision": "approved"},
            approval_lifecycle={"status": "approved"},
            decision_provenance={"decisionStatus": "blocked"},
        )
        self.assertEqual(result["evaluationStatus"], "blocked")
        self.assertIn("decision_provenance_blocked", result["blockers"])


# ──────────────────────────────────────────────
# Auditor export
# ──────────────────────────────────────────────

class TestAuditorExportBlocking(unittest.TestCase):
    def test_auditor_export_blocked_blocks_result(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
            approval_requirement={"decision": "approved"},
            approval_lifecycle={"status": "approved"},
            decision_provenance={"decisionStatus": "approved"},
            auditor_export={"exportStatus": "blocked"},
        )
        self.assertEqual(result["evaluationStatus"], "blocked")
        self.assertIn("auditor_export_blocked", result["blockers"])


# ──────────────────────────────────────────────
# Amount limits
# ──────────────────────────────────────────────

class TestAmountLimits(unittest.TestCase):
    def test_amount_above_max_blocks_result(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(amount=75000),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
        )
        self.assertEqual(result["evaluationStatus"], "blocked")
        self.assertIn("amount_above_max", result["blockers"])
        self.assertEqual(result["amountStatus"], "above_limit")

    def test_currency_mismatch_handled_deterministically(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(amountLimits={"maxAmount": 50000, "currency": "EUR"}),
            subject=_make_subject(amount=25000, currency="USD"),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
        )
        self.assertNotEqual(result["evaluationStatus"], "blocked")
        self.assertEqual(result["amountStatus"], "currency_mismatch")
        self.assertTrue(
            any("currency_mismatch" in w for w in result["warnings"]),
            f"Expected currency mismatch warning, got: {result['warnings']}"
        )


# ──────────────────────────────────────────────
# Deadlines
# ──────────────────────────────────────────────

class TestDeadlines(unittest.TestCase):
    def test_expired_required_deadline_blocks_result(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(deadlines=[
                {"name": "submission_deadline", "dueAt": "2020-01-01T00:00:00Z", "required": True}
            ]),
            subject=_make_subject(),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
        )
        self.assertEqual(result["evaluationStatus"], "blocked")
        self.assertTrue(
            any("deadline_expired" in b for b in result["blockers"]),
            f"Expected deadline blocker, got: {result['blockers']}"
        )
        self.assertEqual(result["deadlineStatus"], "expired")

    def test_non_expired_deadline_passes(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(deadlines=[
                {"name": "submission_deadline", "dueAt": "2099-12-31T23:59:59Z", "required": True}
            ]),
            subject=_make_subject(),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
        )
        self.assertEqual(result["evaluationStatus"], "passed")
        self.assertEqual(result["deadlineStatus"], "on_time")


# ──────────────────────────────────────────────
# Missing inputs
# ──────────────────────────────────────────────

class TestMissingInputs(unittest.TestCase):
    def test_missing_subject_recorded(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=None,
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
        )
        self.assertIn("subject", result["missingInputs"])

    def test_missing_evidence_completeness_recorded(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(),
            evidence_completeness=None,
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
        )
        self.assertIn("evidence_completeness", result["missingInputs"])

    def test_missing_compliance_gap_report_recorded(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(),
            evidence_completeness={"complete": True},
            compliance_gap_report=None,
            permission_result={"allowed": True},
        )
        self.assertIn("compliance_gap_report", result["missingInputs"])

    def test_missing_permission_result_recorded(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result=None,
        )
        self.assertIn("permission_result", result["missingInputs"])

    def test_missing_approval_requirement_recorded(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
            approval_requirement=None,
            approval_lifecycle={"status": "approved"},
        )
        self.assertIn("approval_requirement", result["missingInputs"])

    def test_missing_decision_provenance_recorded(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
            approval_requirement={"decision": "approved"},
            approval_lifecycle={"status": "approved"},
            decision_provenance=None,
        )
        self.assertIn("decision_provenance", result["missingInputs"])


# ──────────────────────────────────────────────
# Determinism and deduplication
# ──────────────────────────────────────────────

class TestDeterminismAndDeduplication(unittest.TestCase):
    def test_blockers_are_deduplicated(self):
        # Create a situation where multiple paths could produce the same blocker
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(exclusionCodes=["sanctioned_entity", "sanctioned_entity"]),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
        )
        blocker_count = sum(1 for b in result["blockers"] if "exclusion:sanctioned_entity" in b)
        self.assertEqual(blocker_count, 1)

    def test_warnings_are_deduplicated(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(exclusionCodes=["missing_tax_clearance", "missing_tax_clearance"]),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
        )
        warning_count = sum(1 for w in result["warnings"] if "exclusion:missing_tax_clearance" in w)
        self.assertEqual(warning_count, 1)

    def test_missing_inputs_are_deduplicated(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=None,
            evidence_completeness=None,
            compliance_gap_report=None,
            permission_result=None,
            approval_requirement=None,
            approval_lifecycle=None,
            decision_provenance=None,
            auditor_export=None,
        )
        for item in ("subject", "evidence_completeness", "compliance_gap_report",
                     "permission_result", "approval_requirement", "approval_lifecycle",
                     "decision_provenance", "auditor_export"):
            self.assertEqual(result["missingInputs"].count(item), 1,
                             f"Expected single occurrence of {item} in missingInputs")

    def test_missing_evidence_and_satisfied_evidence_are_deterministic(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(evidenceTypes=["eligibility_statement", "budget_plan"]),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
        )
        self.assertEqual(sorted(result["satisfiedEvidence"]), ["budget_plan", "eligibility_statement"])
        self.assertEqual(result["missingEvidence"], [])


# ──────────────────────────────────────────────
# Include details
# ──────────────────────────────────────────────

class TestIncludeDetails(unittest.TestCase):
    def test_include_details_true_includes_detail_objects(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
            include_details=True,
        )
        self.assertIn("policyPack", result)
        self.assertIn("subject", result)
        self.assertIn("evidenceCompleteness", result)
        self.assertIn("complianceGapReport", result)
        self.assertIn("permissionResult", result)

    def test_include_details_false_omits_detail_objects(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
            include_details=False,
        )
        self.assertNotIn("policyPack", result)
        self.assertNotIn("subject", result)
        self.assertNotIn("evidenceCompleteness", result)
        self.assertNotIn("complianceGapReport", result)
        self.assertNotIn("permissionResult", result)
        self.assertNotIn("approvalRequirement", result)
        self.assertNotIn("approvalLifecycle", result)
        self.assertNotIn("decisionProvenance", result)
        self.assertNotIn("auditorExport", result)
        self.assertNotIn("context", result)
        # Core fields must still be present
        self.assertIn("recordType", result)
        self.assertIn("evaluationStatus", result)
        self.assertIn("blockers", result)
        self.assertIn("warnings", result)


# ──────────────────────────────────────────────
# Field preservation
# ──────────────────────────────────────────────

class TestFieldPreservation(unittest.TestCase):
    def test_response_preserves_policy_pack_id_version_and_subject_id(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(policyPackId="pp-123", policyPackVersion="v2"),
            subject=_make_subject(subjectId="sub-456"),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
        )
        self.assertEqual(result["policyPackId"], "pp-123")
        self.assertEqual(result["policyPackVersion"], "v2")
        self.assertEqual(result["subjectId"], "sub-456")


# ──────────────────────────────────────────────
# Secrets safety
# ──────────────────────────────────────────────

class TestSecretsSafety(unittest.TestCase):
    def test_response_does_not_expose_secrets(self):
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(),
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "clear", "severity": "low"},
            permission_result={"allowed": True},
            context={"api_key": "secret-key-123", "password": "hunter2", "token_hash": "abc123"},
            include_details=True,
        )
        result_str = str(result)
        self.assertNotIn("secret-key-123", result_str)
        self.assertNotIn("hunter2", result_str)
        self.assertNotIn("abc123", result_str)
        # Context key names may appear, but values should be redacted
        self.assertIn("[REDACTED]", result_str)


# ──────────────────────────────────────────────
# No DB access
# ──────────────────────────────────────────────

class TestNoDbAccess(unittest.TestCase):
    def test_evaluator_does_not_require_db_access(self):
        # Pure evaluator should work with only arguments
        result = evaluate_policy_requirements(
            policy_pack=_make_policy_pack(),
            subject=_make_subject(),
        )
        self.assertIn("evaluationStatus", result)
        # Should not raise or attempt any DB/network calls


# ──────────────────────────────────────────────
# Existing module tests still pass (meta)
# ──────────────────────────────────────────────

class TestExistingModulesUnchanged(unittest.TestCase):
    def test_existing_modules_still_importable(self):
        from backend.src import policy_engine, grants, audit_log, challenges, demo_action
        self.assertTrue(callable(policy_engine.evaluate_access))
        self.assertTrue(callable(grants.create_grant))
        self.assertTrue(callable(audit_log.list_events))
        self.assertTrue(callable(challenges.create_challenge))
        self.assertTrue(callable(demo_action.handle_demo_action))


if __name__ == "__main__":
    unittest.main(verbosity=2)
