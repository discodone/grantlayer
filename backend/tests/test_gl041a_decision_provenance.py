"""GL-041-A — Decision Provenance v2 Builder tests.

Tests for the pure function that determines decision provenance from structured inputs.
No DB access, no network calls, no API endpoint.
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.decision_provenance import (
    build_decision_provenance_v2,
    RECORD_TYPE,
    RECORD_VERSION,
)


class TestDecisionProvenanceV2(unittest.TestCase):
    """Decision provenance v2 builder tests."""

    def test_module_import(self):
        """Test that the module imports successfully."""
        import src.decision_provenance as dp_mod
        self.assertIsNotNone(dp_mod)
        self.assertTrue(hasattr(dp_mod, "build_decision_provenance_v2"))
        self.assertEqual(dp_mod.RECORD_TYPE, "decision_provenance")
        self.assertEqual(dp_mod.RECORD_VERSION, "gl-decision-provenance-v2")

    def test_function_exists(self):
        """Test that the build_decision_provenance_v2 function exists."""
        self.assertTrue(callable(build_decision_provenance_v2))

    def test_approved_decision_without_blockers(self):
        """Test approved decision without any blockers."""
        result = build_decision_provenance_v2(
            decision_id="dec-123",
            decision_type="grant_request",
            subject_id="sub-1",
            actor_id="agent-1",
            action="read",
            decision="approved",
            reason="All checks passed",
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": True},
            approval_requirement={"required": False},
            approval_lifecycle={"status": "approved"},
            provenance_summary={"events": [{"id": "evt-1"}]},
            auditor_report={"auditReady": True},
            policy_results=[{"passed": True}],
        )

        self.assertEqual(result["recordType"], RECORD_TYPE)
        self.assertEqual(result["recordVersion"], RECORD_VERSION)
        self.assertEqual(result["decisionId"], "dec-123")
        self.assertEqual(result["decisionType"], "grant_request")
        self.assertEqual(result["subjectId"], "sub-1")
        self.assertEqual(result["actorId"], "agent-1")
        self.assertEqual(result["action"], "read")
        self.assertEqual(result["decision"], "approved")
        self.assertEqual(result["decisionStatus"], "approved")
        self.assertEqual(result["reason"], "All checks passed")
        self.assertIn("createdAt", result)
        self.assertEqual(result["signals"]["evidence"], "complete")
        self.assertEqual(result["signals"]["compliance"], "complete")
        self.assertEqual(result["signals"]["permission"], "allowed")
        self.assertEqual(result["signals"]["approval"], "approved")
        self.assertEqual(result["signals"]["provenance"], "present")
        self.assertEqual(result["signals"]["auditor"], "ready")
        self.assertEqual(result["signals"]["policy"], "passed")
        self.assertEqual(result["readiness"]["evidence"], "ready")
        self.assertEqual(result["readiness"]["compliance"], "ready")
        self.assertEqual(result["readiness"]["permission"], "ready")
        self.assertEqual(result["readiness"]["approval"], "ready")
        self.assertEqual(result["readiness"]["provenance"], "ready")
        self.assertEqual(result["readiness"]["policy"], "ready")
        self.assertEqual(result["auditReadiness"]["status"], "ready")
        self.assertEqual(result["auditReadiness"]["auditReady"], True)
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["missingInputs"], [])

    def test_rejected_decision(self):
        """Test explicitly rejected decision."""
        result = build_decision_provenance_v2(
            decision_id="dec-456",
            decision_type="access_request",
            subject_id="sub-2",
            actor_id="user-1",
            action="write",
            decision="denied",
            reason="Permission denied",
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": False, "reason": "Insufficient permissions"},
            approval_requirement={"required": False},
        )

        self.assertEqual(result["decision"], "denied")
        self.assertEqual(result["decisionStatus"], "denied")
        self.assertEqual(result["signals"]["permission"], "denied")
        self.assertEqual(result["blockers"], ["permission_denied"])
        self.assertEqual(result["readiness"]["permission"], "blocked")

    def test_missing_decision(self):
        """Test missing decision input."""
        result = build_decision_provenance_v2(
            decision_id="dec-789",
            decision_type="unknown",
            subject_id="sub-3",
            evidence_completeness={"complete": True},
        )

        self.assertIsNone(result["decision"])
        self.assertEqual(result["decisionStatus"], "incomplete")
        self.assertIn("decision", result["missingInputs"])

    def test_permission_denial_blocks(self):
        """Test that permission denial blocks decision."""
        result = build_decision_provenance_v2(
            decision_id="dec-perm-block",
            decision="approved",
            permission_result={"allowed": False},
        )

        self.assertEqual(result["decisionStatus"], "blocked")
        self.assertEqual(result["blockers"], ["permission_denied"])
        self.assertEqual(result["signals"]["permission"], "denied")

    def test_blocked_approval_requirement_blocks(self):
        """Test blocked approval requirement blocks decision."""
        result = build_decision_provenance_v2(
            decision_id="dec-approval-block",
            decision="approved",
            approval_requirement={"decision": "blocked"},
        )

        self.assertEqual(result["blockers"], ["approval_requirement_blocked"])
        self.assertEqual(result["signals"]["approval"], "blocked")
        self.assertEqual(result["readiness"]["approval"], "blocked")

    def test_blocked_approval_lifecycle_blocks(self):
        """Test blocked approval lifecycle blocks decision."""
        result = build_decision_provenance_v2(
            decision_id="dec-lifecycle-block",
            decision="approved",
            approval_lifecycle={"status": "blocked"},
        )

        self.assertEqual(result["blockers"], ["approval_lifecycle_blocked"])
        self.assertEqual(result["signals"]["approval"], "blocked")
        self.assertEqual(result["readiness"]["approval"], "blocked")

    def test_high_compliance_gaps_block(self):
        """Test high compliance gaps block decision."""
        result = build_decision_provenance_v2(
            decision_id="dec-compliance-block",
            decision="approved",
            compliance_gap_report={
                "overallStatus": "incomplete",
                "highGaps": [{"id": "gap-1", "description": "High gap"}],
            },
        )

        self.assertIn("high_compliance_gaps", result["blockers"])
        self.assertEqual(result["signals"]["compliance"], "blocked")
        self.assertEqual(result["readiness"]["compliance"], "blocked")

    def test_critical_compliance_gaps_block(self):
        """Test critical compliance gaps block decision."""
        result = build_decision_provenance_v2(
            decision_id="dec-critical",
            decision="approved",
            compliance_gap_report={
                "overallStatus": "incomplete",
                "criticalGaps": [{"id": "gap-crit", "description": "Critical gap"}],
            },
        )

        self.assertIn("critical_compliance_gaps", result["blockers"])
        self.assertEqual(result["signals"]["compliance"], "blocked")
        self.assertEqual(result["readiness"]["compliance"], "blocked")

    def test_compliance_overall_status_blocked(self):
        """Test overall status blocked."""
        result = build_decision_provenance_v2(
            decision="approved",
            compliance_gap_report={"overallStatus": "blocked"},
        )

        self.assertIn("compliance_blocked", result["blockers"])
        self.assertEqual(result["signals"]["compliance"], "blocked")

    def test_missing_inputs_recorded(self):
        """Test missing inputs are recorded in missingInputs."""
        result = build_decision_provenance_v2(decision="approved")

        expected_missing = [
            "evidence_completeness",
            "compliance_gap_report",
            "permission_result",
            "approval_requirement",
            "provenance_summary",
            "auditor_report",
            "policy_results",
        ]
        for missing in expected_missing:
            self.assertIn(missing, result["missingInputs"])

    def test_provenance_warning_when_no_events(self):
        """Test provenance warning when no events are present."""
        result = build_decision_provenance_v2(
            decision="approved",
            provenance_summary={"warnings": ["No provenance events found"]},
        )

        self.assertEqual(result["signals"]["provenance"], "warning")
        self.assertIn("No provenance events found", result["warnings"])

    def test_auditor_critical_findings_block(self):
        """Test auditor critical findings block decision."""
        result = build_decision_provenance_v2(
            decision="approved",
            auditor_report={
                "auditReady": False,
                "criticalFindings": [{"id": "find-1", "severity": "critical"}],
            },
        )

        self.assertIn("auditor_critical_findings", result["blockers"])
        self.assertEqual(result["signals"]["auditor"], "blocked")
        self.assertEqual(result["auditReadiness"]["status"], "blocked")
        self.assertEqual(result["auditReadiness"]["auditReady"], False)

    def test_approval_does_not_override_permission_denial(self):
        """Test approval status does not override permission denial."""
        result = build_decision_provenance_v2(
            decision="approved",
            permission_result={"allowed": False},
            approval_requirement={"decision": "approved"},
        )

        self.assertIn("permission_denied", result["blockers"])
        self.assertEqual(result["signals"]["permission"], "denied")
        self.assertEqual(result["decisionStatus"], "blocked")

    def test_compliance_blockers_not_hidden_by_approval(self):
        """Test compliance blockers not hidden by approval status."""
        result = build_decision_provenance_v2(
            decision="approved",
            compliance_gap_report={
                "overallStatus": "blocked",
            },
            approval_requirement={"decision": "approved"},
        )

        self.assertIn("compliance_blocked", result["blockers"])
        self.assertEqual(result["signals"]["compliance"], "blocked")

    def test_deterministic_output(self):
        """Test deterministic output across identical inputs."""
        inputs = {
            "decision_id": "test-det",
            "decision": "approved",
            "evidence_completeness": {"complete": True},
            "compliance_gap_report": {"overallStatus": "complete"},
            "permission_result": {"allowed": True},
            "approval_requirement": {"required": False},
            "auditor_report": {"auditReady": True},
            "policy_results": [{"passed": True}],
            "include_details": False,
        }

        result1 = build_decision_provenance_v2(**inputs)
        result2 = build_decision_provenance_v2(**inputs)

        self.assertEqual(result1["blockers"], result2["blockers"])
        self.assertEqual(result1["warnings"], result2["warnings"])
        self.assertEqual(result1["missingInputs"], result2["missingInputs"])
        self.assertEqual(result1["signals"], result2["signals"])
        self.assertEqual(result1["readiness"], result2["readiness"])

    def test_deduplication(self):
        """Test that blockers, warnings, and missingInputs are deduplicated."""
        result = build_decision_provenance_v2(
            decision="approved",
            compliance_gap_report={
                "overallStatus": "blocked",
                "criticalGaps": [{"id": "gap1"}],
            },
            permission_result={"allowed": False},
        )

        self.assertEqual(len(result["blockers"]), len(set(result["blockers"])))
        self.assertEqual(len(result["warnings"]), len(set(result["warnings"])))
        self.assertEqual(len(result["missingInputs"]), len(set(result["missingInputs"])))

    def test_include_details_false_omits_details(self):
        """Test include_details=False omits detail objects."""
        result = build_decision_provenance_v2(
            decision_id="test-details",
            decision="approved",
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": True},
            approval_requirement={"required": False},
            approval_lifecycle={"status": "approved"},
            provenance_summary={"events": [{"id": "evt-1"}]},
            auditor_report={"auditReady": True},
            policy_results=[{"passed": True}],
            inputs={"param1": "value1"},
            context={"env": "test"},
            include_details=False,
        )

        # Core fields and signals should be present
        self.assertEqual(result["decision"], "approved")
        self.assertEqual(result["recordType"], RECORD_TYPE)
        self.assertEqual(result["recordVersion"], RECORD_VERSION)
        self.assertIn("signals", result)
        self.assertIn("readiness", result)
        self.assertIn("blockers", result)
        self.assertIn("warnings", result)
        self.assertIn("missingInputs", result)

        # Detail objects should be omitted
        self.assertIsNone(result.get("evidence"))
        self.assertIsNone(result.get("compliance"))
        self.assertIsNone(result.get("permission"))
        self.assertIsNone(result.get("approval"))
        self.assertIsNone(result.get("provenance"))
        self.assertIsNone(result.get("auditor"))
        self.assertIsNone(result.get("policy"))
        self.assertIsNone(result.get("inputs"))

    def test_include_details_true_includes_details(self):
        """Test include_details=True includes detail objects."""
        result = build_decision_provenance_v2(
            decision_id="test-details-true",
            decision="approved",
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": True},
            approval_requirement={"required": False},
            provenance_summary={"events": [{"id": "evt-1"}]},
            auditor_report={"auditReady": True},
            policy_results=[{"passed": True}],
            include_details=True,
        )

        self.assertIsNotNone(result.get("evidence"))
        self.assertIsNotNone(result.get("compliance"))
        self.assertIsNotNone(result.get("permission"))
        self.assertIsNotNone(result.get("provenance"))
        self.assertIsNotNone(result.get("auditor"))
        self.assertIsNotNone(result.get("policy"))

    def test_no_secrets_exposed(self):
        """Test that secrets are redacted from inputs."""
        sensitive_inputs = {
            "token": "secret-token-123",
            "password": "mypassword",
            "api_key": "key-456",
            "safe_param": "normal_value",
        }

        sensitive_context = {
            "auth_header": "Bearer secret-token",
            "normal_data": "safe_value",
        }

        result = build_decision_provenance_v2(
            decision="approved",
            inputs=sensitive_inputs,
            context=sensitive_context,
            include_details=True,
        )

        inputs_out = result["inputs"]
        self.assertIsNotNone(inputs_out)
        self.assertEqual(inputs_out["token"], "[REDACTED]")
        self.assertEqual(inputs_out["password"], "[REDACTED]")
        self.assertEqual(inputs_out["api_key"], "[REDACTED]")
        self.assertEqual(inputs_out["auth_header"], "[REDACTED]")
        self.assertEqual(inputs_out["safe_param"], "normal_value")
        self.assertEqual(inputs_out["normal_data"], "safe_value")

    def test_created_at_custom(self):
        """Test custom created_at timestamp."""
        custom_time = "2026-01-01T00:00:00Z"
        result = build_decision_provenance_v2(
            decision="approved",
            created_at=custom_time,
        )

        self.assertEqual(result["createdAt"], custom_time)

    def test_decision_id_mismatch_warning(self):
        """Test warning when provenance decisionId mismatches."""
        result = build_decision_provenance_v2(
            decision_id="dec-A",
            provenance_summary={"decisionId": "dec-B"},
        )

        self.assertIn("provenance_decision_id_mismatch", result["warnings"])

    def test_approval_pending_blocks(self):
        """Test pending approval requirement blocks."""
        result = build_decision_provenance_v2(
            decision="approved",
            approval_requirement={"decision": "pending"},
        )

        self.assertIn("approval_requirement_pending", result["blockers"])
        self.assertEqual(result["signals"]["approval"], "pending")

    def test_approval_required_blocks(self):
        """Test required approval blocks."""
        result = build_decision_provenance_v2(
            decision="approved",
            approval_requirement={"required": True},
        )

        self.assertIn("approval_required", result["blockers"])
        self.assertEqual(result["signals"]["approval"], "required")

    def test_no_db_access_required(self):
        """Test that function doesn't require DB access (pure function)."""
        test_cases = [
            {},
            {"decision": "approved"},
            {"decision": "denied", "reason": "test"},
            {
                "decision": "approved",
                "evidence_completeness": {"complete": True},
                "permission_result": {"allowed": True},
            },
        ]

        for inputs in test_cases:
            try:
                result = build_decision_provenance_v2(**inputs)
                self.assertIsNotNone(result)
                self.assertIn("recordType", result)
                self.assertIn("recordVersion", result)
                self.assertIn("signals", result)
                self.assertIn("blockers", result)
                self.assertIn("warnings", result)
                self.assertIn("missingInputs", result)
            except Exception as e:
                self.fail(f"Function failed with inputs {inputs}: {e}")

    def test_policy_failed_blocks(self):
        """Test failed policy blocks decision."""
        result = build_decision_provenance_v2(
            decision="approved",
            policy_results=[{"failed": True}],
        )

        self.assertIn("policy_failed", result["blockers"])
        self.assertEqual(result["signals"]["policy"], "failed")

    def test_policy_partial_warning(self):
        """Test partial policy gives warning."""
        result = build_decision_provenance_v2(
            decision="approved",
            policy_results=[{"passed": False}, {"passed": True}],
        )

        self.assertEqual(result["signals"]["policy"], "partial")
        self.assertIn("policy_partial", result["warnings"])

    def test_auditor_not_ready_blocks(self):
        """Test auditor not ready blocks decision."""
        result = build_decision_provenance_v2(
            decision="approved",
            auditor_report={"auditReady": False},
        )

        self.assertIn("audit_not_ready", result["blockers"])
        self.assertEqual(result["signals"]["auditor"], "blocked")

    def test_auditor_warnings(self):
        """Test auditor warnings."""
        result = build_decision_provenance_v2(
            decision="approved",
            auditor_report={
                "auditReady": True,
                "warnings": [{"id": "warn-1"}],
            },
        )

        self.assertEqual(result["signals"]["auditor"], "warning")
        self.assertIn("auditor_warnings", result["warnings"])

    def test_approval_priority_blocked_over_denied(self):
        """Test approval blocked takes priority over denied."""
        result = build_decision_provenance_v2(
            decision="approved",
            approval_requirement={"decision": "blocked"},
            approval_lifecycle={"status": "denied"},
        )

        self.assertEqual(result["signals"]["approval"], "blocked")

    def test_compliance_and_permission_both_block(self):
        """Test multiple blockers coexist."""
        result = build_decision_provenance_v2(
            decision="approved",
            compliance_gap_report={
                "overallStatus": "blocked",
            },
            permission_result={"allowed": False},
        )

        self.assertIn("compliance_blocked", result["blockers"])
        self.assertIn("permission_denied", result["blockers"])
        self.assertEqual(result["decisionStatus"], "blocked")

    def test_empty_inputs_no_error(self):
        """Test function handles empty inputs without error."""
        result = build_decision_provenance_v2()

        self.assertEqual(result["recordType"], RECORD_TYPE)
        self.assertEqual(result["recordVersion"], RECORD_VERSION)
        self.assertIsNone(result["decision"])
        self.assertEqual(result["decisionStatus"], "incomplete")
        self.assertEqual(result["signals"]["evidence"], "missing")
        self.assertEqual(result["signals"]["compliance"], "missing")
        self.assertEqual(result["signals"]["permission"], "missing")
        self.assertEqual(result["signals"]["approval"], "missing")
        self.assertEqual(result["signals"]["provenance"], "missing")
        self.assertEqual(result["signals"]["auditor"], "missing")
        self.assertEqual(result["signals"]["policy"], "missing")


if __name__ == "__main__":
    unittest.main(verbosity=2)
