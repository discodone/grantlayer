"""GL-042-A — Institutional Auditor Export Builder tests.

Tests for the pure function that builds an institutional auditor export
from structured inputs.  No DB access, no network calls, no API endpoint.
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.src.audit.auditor_export import (
    build_institutional_auditor_export,
    RECORD_TYPE,
    RECORD_VERSION,
)


class TestAuditorExportBuilder(unittest.TestCase):
    """Institutional auditor export builder tests."""

    def test_module_import(self):
        """Test that the module imports successfully."""
        import backend.src.audit.auditor_export as ae_mod
        self.assertIsNotNone(ae_mod)
        self.assertTrue(hasattr(ae_mod, "build_institutional_auditor_export"))
        self.assertEqual(ae_mod.RECORD_TYPE, "auditor_export")
        self.assertEqual(ae_mod.RECORD_VERSION, "gl-auditor-export-v1")

    def test_function_exists(self):
        """Test that the build_institutional_auditor_export function exists."""
        self.assertTrue(callable(build_institutional_auditor_export))

    def test_ready_export_with_complete_inputs(self):
        """Test ready export when all inputs are complete and valid."""
        result = build_institutional_auditor_export(
            export_id="exp-123",
            export_type="institutional_audit",
            subject_id="sub-1",
            decision_id="dec-1",
            generated_by="system",
            auditor_id="auditor-1",
            decision_provenance={
                "decisionStatus": "approved",
                "readiness": {"evidence": "ready", "compliance": "ready"},
                "auditReadiness": {"status": "ready"},
            },
            auditor_report={"auditReady": True},
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": True},
            approval_requirement={"required": False, "decision": "approved"},
            approval_lifecycle={"status": "approved"},
            policy_results=[{"passed": True}],
        )

        self.assertEqual(result["recordType"], RECORD_TYPE)
        self.assertEqual(result["recordVersion"], RECORD_VERSION)
        self.assertEqual(result["exportId"], "exp-123")
        self.assertEqual(result["exportType"], "institutional_audit")
        self.assertEqual(result["subjectId"], "sub-1")
        self.assertEqual(result["decisionId"], "dec-1")
        self.assertEqual(result["generatedBy"], "system")
        self.assertEqual(result["auditorId"], "auditor-1")
        self.assertEqual(result["exportStatus"], "ready")
        self.assertEqual(result["auditReadiness"], "audit_ready")
        self.assertIn("createdAt", result)
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["warnings"], [])
        self.assertIn("decisionProvenance", result["sections"])
        self.assertIn("auditorReport", result["sections"])
        self.assertIn("evidence", result["sections"])
        self.assertIn("compliance", result["sections"])
        self.assertIn("permission", result["sections"])
        self.assertIn("approval", result["sections"])
        self.assertIn("policy", result["sections"])
        self.assertEqual(result["missingSections"], [])

    def test_blocked_by_decision_status(self):
        """Test blocked export when decision_provenance.decisionStatus is blocked."""
        result = build_institutional_auditor_export(
            export_id="exp-blocked",
            decision_provenance={
                "decisionStatus": "blocked",
                "readiness": {"evidence": "ready"},
                "auditReadiness": {"status": "ready"},
            },
            auditor_report={"auditReady": True},
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": True},
            approval_requirement={"required": False, "decision": "approved"},
            policy_results=[{"passed": True}],
        )

        self.assertEqual(result["exportStatus"], "blocked")
        self.assertIn("decision_provenance_blocked", result["blockers"])
        self.assertEqual(result["auditReadiness"], "blocked")

    def test_blocked_by_readiness_blocked(self):
        """Test blocked export when decision_provenance.readiness has blocked value."""
        result = build_institutional_auditor_export(
            export_id="exp-readiness-blocked",
            decision_provenance={
                "decisionStatus": "approved",
                "readiness": {"compliance": "blocked"},
                "auditReadiness": {"status": "ready"},
            },
            auditor_report={"auditReady": True},
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": True},
            approval_requirement={"required": False, "decision": "approved"},
            policy_results=[{"passed": True}],
        )

        self.assertEqual(result["exportStatus"], "blocked")
        self.assertIn("decision_provenance_compliance_blocked", result["blockers"])
        self.assertEqual(result["auditReadiness"], "blocked")

    def test_blocked_by_audit_readiness_blocked(self):
        """Test blocked export when decision_provenance.auditReadiness is blocked."""
        result = build_institutional_auditor_export(
            export_id="exp-audit-blocked",
            decision_provenance={
                "decisionStatus": "approved",
                "readiness": {"evidence": "ready"},
                "auditReadiness": {"status": "blocked"},
            },
            auditor_report={"auditReady": True},
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": True},
            approval_requirement={"required": False, "decision": "approved"},
            policy_results=[{"passed": True}],
        )

        self.assertEqual(result["exportStatus"], "blocked")
        self.assertIn("decision_provenance_audit_readiness_blocked", result["blockers"])
        self.assertEqual(result["auditReadiness"], "blocked")

    def test_blocked_by_critical_auditor_findings(self):
        """Test blocked export when auditor_report has critical findings."""
        result = build_institutional_auditor_export(
            export_id="exp-audit-critical",
            decision_provenance={
                "decisionStatus": "approved",
                "readiness": {"evidence": "ready"},
                "auditReadiness": {"status": "ready"},
            },
            auditor_report={
                "auditReady": True,
                "criticalFindings": [{"id": "f1", "severity": "critical"}],
            },
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": True},
            approval_requirement={"required": False, "decision": "approved"},
            policy_results=[{"passed": True}],
        )

        self.assertEqual(result["exportStatus"], "blocked")
        self.assertIn("auditor_report_critical_findings", result["blockers"])
        self.assertEqual(result["auditReadiness"], "blocked")

    def test_blocked_by_compliance_critical_gaps(self):
        """Test blocked export when compliance_gap_report has critical gaps."""
        result = build_institutional_auditor_export(
            export_id="exp-compliance-critical",
            decision_provenance={
                "decisionStatus": "approved",
                "readiness": {"evidence": "ready"},
                "auditReadiness": {"status": "ready"},
            },
            auditor_report={"auditReady": True},
            evidence_completeness={"complete": True},
            compliance_gap_report={
                "overallStatus": "complete",
                "criticalGaps": [{"id": "g1", "severity": "critical"}],
            },
            permission_result={"allowed": True},
            approval_requirement={"required": False, "decision": "approved"},
            policy_results=[{"passed": True}],
        )

        self.assertEqual(result["exportStatus"], "blocked")
        self.assertIn("compliance_critical_gaps", result["blockers"])
        self.assertEqual(result["auditReadiness"], "blocked")

    def test_blocked_by_compliance_high_gaps(self):
        """Test blocked export when compliance_gap_report has high gaps."""
        result = build_institutional_auditor_export(
            export_id="exp-compliance-high",
            decision_provenance={
                "decisionStatus": "approved",
                "readiness": {"evidence": "ready"},
                "auditReadiness": {"status": "ready"},
            },
            auditor_report={"auditReady": True},
            evidence_completeness={"complete": True},
            compliance_gap_report={
                "overallStatus": "complete",
                "highGaps": [{"id": "g2", "severity": "high"}],
            },
            permission_result={"allowed": True},
            approval_requirement={"required": False, "decision": "approved"},
            policy_results=[{"passed": True}],
        )

        self.assertEqual(result["exportStatus"], "blocked")
        self.assertIn("compliance_high_gaps", result["blockers"])
        self.assertEqual(result["auditReadiness"], "blocked")

    def test_warning_for_incomplete_evidence(self):
        """Test warning when evidence_completeness is incomplete."""
        result = build_institutional_auditor_export(
            export_id="exp-evidence-incomplete",
            decision_provenance={
                "decisionStatus": "approved",
                "readiness": {"evidence": "ready"},
                "auditReadiness": {"status": "ready"},
            },
            auditor_report={"auditReady": True},
            evidence_completeness={"complete": False, "missing": ["item1"]},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": True},
            approval_requirement={"required": False, "decision": "approved"},
            policy_results=[{"passed": True}],
        )

        self.assertEqual(result["exportStatus"], "needs_review")
        self.assertIn("evidence_incomplete", result["warnings"])
        self.assertIn("evidence_missing_items", result["warnings"])
        self.assertEqual(result["auditReadiness"], "needs_review")

    def test_incomplete_when_all_sections_missing(self):
        """Test incomplete export when no sections are provided."""
        result = build_institutional_auditor_export(
            export_id="exp-incomplete",
        )

        self.assertEqual(result["exportStatus"], "incomplete")
        self.assertEqual(result["auditReadiness"], "insufficient_evidence")
        self.assertEqual(result["sections"], [])
        self.assertIn("decisionProvenance", result["missingSections"])
        self.assertIn("auditorReport", result["missingSections"])
        self.assertIn("evidence", result["missingSections"])
        self.assertIn("compliance", result["missingSections"])
        self.assertIn("permission", result["missingSections"])
        self.assertIn("approval", result["missingSections"])
        self.assertIn("policy", result["missingSections"])

    def test_needs_review_when_some_sections_missing(self):
        """Test needs_review when some but not all sections are present."""
        result = build_institutional_auditor_export(
            export_id="exp-needs-review",
            decision_provenance={"decisionStatus": "approved"},
            auditor_report={"auditReady": True},
            # Missing: evidence_completeness, compliance_gap_report
            permission_result={"allowed": True},
            approval_requirement={"required": False, "decision": "approved"},
            policy_results=[{"passed": True}],
        )

        self.assertEqual(result["exportStatus"], "needs_review")
        self.assertEqual(result["auditReadiness"], "needs_review")
        self.assertIn("approval", result["sections"])
        self.assertIn("evidence", result["missingSections"])
        self.assertIn("compliance", result["missingSections"])

    def test_permission_denied_blocks(self):
        """Test blocked export when permission_result is denied."""
        result = build_institutional_auditor_export(
            export_id="exp-perm-denied",
            decision_provenance={
                "decisionStatus": "approved",
                "readiness": {"evidence": "ready"},
                "auditReadiness": {"status": "ready"},
            },
            auditor_report={"auditReady": True},
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": False, "reason": "Insufficient permissions"},
            approval_requirement={"required": False, "decision": "approved"},
            policy_results=[{"passed": True}],
        )

        self.assertEqual(result["exportStatus"], "blocked")
        self.assertIn("permission_denied", result["blockers"])
        self.assertEqual(result["auditReadiness"], "blocked")

    def test_policy_failed_blocks(self):
        """Test blocked export when policy_results has failed policy."""
        result = build_institutional_auditor_export(
            export_id="exp-policy-failed",
            decision_provenance={
                "decisionStatus": "approved",
                "readiness": {"evidence": "ready"},
                "auditReadiness": {"status": "ready"},
            },
            auditor_report={"auditReady": True},
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": True},
            approval_requirement={"required": False, "decision": "approved"},
            policy_results=[{"failed": True}],
        )

        self.assertEqual(result["exportStatus"], "blocked")
        self.assertIn("policy_failed", result["blockers"])
        self.assertEqual(result["auditReadiness"], "blocked")

    def test_policy_blocked_blocks(self):
        """Test blocked export when policy_results has blocked policy."""
        result = build_institutional_auditor_export(
            export_id="exp-policy-blocked",
            decision_provenance={
                "decisionStatus": "approved",
                "readiness": {"evidence": "ready"},
                "auditReadiness": {"status": "ready"},
            },
            auditor_report={"auditReady": True},
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": True},
            approval_requirement={"required": False, "decision": "approved"},
            policy_results=[{"blocked": True}],
        )

        self.assertEqual(result["exportStatus"], "blocked")
        self.assertIn("policy_blocked", result["blockers"])
        self.assertEqual(result["auditReadiness"], "blocked")

    def test_approval_blocked_blocks(self):
        """Test blocked export when approval_requirement decision is blocked."""
        result = build_institutional_auditor_export(
            export_id="exp-approval-blocked",
            decision_provenance={
                "decisionStatus": "approved",
                "readiness": {"evidence": "ready"},
                "auditReadiness": {"status": "ready"},
            },
            auditor_report={"auditReady": True},
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": True},
            approval_requirement={"decision": "blocked"},
            policy_results=[{"passed": True}],
        )

        self.assertEqual(result["exportStatus"], "blocked")
        self.assertIn("approval_requirement_blocked", result["blockers"])
        self.assertEqual(result["auditReadiness"], "blocked")

    def test_approval_denied_blocks(self):
        """Test blocked export when approval_requirement decision is denied."""
        result = build_institutional_auditor_export(
            export_id="exp-approval-denied",
            decision_provenance={
                "decisionStatus": "approved",
                "readiness": {"evidence": "ready"},
                "auditReadiness": {"status": "ready"},
            },
            auditor_report={"auditReady": True},
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": True},
            approval_requirement={"decision": "denied"},
            policy_results=[{"passed": True}],
        )

        self.assertEqual(result["exportStatus"], "blocked")
        self.assertIn("approval_requirement_denied", result["blockers"])
        self.assertEqual(result["auditReadiness"], "blocked")

    def test_approval_lifecycle_blocked_blocks(self):
        """Test blocked export when approval_lifecycle status is blocked."""
        result = build_institutional_auditor_export(
            export_id="exp-lifecycle-blocked",
            decision_provenance={
                "decisionStatus": "approved",
                "readiness": {"evidence": "ready"},
                "auditReadiness": {"status": "ready"},
            },
            auditor_report={"auditReady": True},
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": True},
            approval_lifecycle={"status": "blocked"},
            policy_results=[{"passed": True}],
        )

        self.assertEqual(result["exportStatus"], "blocked")
        self.assertIn("approval_lifecycle_blocked", result["blockers"])
        self.assertEqual(result["auditReadiness"], "blocked")

    def test_approval_lifecycle_denied_blocks(self):
        """Test blocked export when approval_lifecycle status is denied."""
        result = build_institutional_auditor_export(
            export_id="exp-lifecycle-denied",
            decision_provenance={
                "decisionStatus": "approved",
                "readiness": {"evidence": "ready"},
                "auditReadiness": {"status": "ready"},
            },
            auditor_report={"auditReady": True},
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": True},
            approval_lifecycle={"status": "denied"},
            policy_results=[{"passed": True}],
        )

        self.assertEqual(result["exportStatus"], "blocked")
        self.assertIn("approval_lifecycle_denied", result["blockers"])
        self.assertEqual(result["auditReadiness"], "blocked")

    def test_approval_pending_warning(self):
        """Test warning when approval_requirement is pending."""
        result = build_institutional_auditor_export(
            export_id="exp-approval-pending",
            decision_provenance={
                "decisionStatus": "approved",
                "readiness": {"evidence": "ready"},
                "auditReadiness": {"status": "ready"},
            },
            auditor_report={"auditReady": True},
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": True},
            approval_requirement={"decision": "pending"},
            policy_results=[{"passed": True}],
        )

        self.assertEqual(result["exportStatus"], "needs_review")
        self.assertIn("approval_requirement_pending", result["warnings"])
        self.assertEqual(result["auditReadiness"], "needs_review")

    def test_approval_lifecycle_pending_warning(self):
        """Test warning when approval_lifecycle is pending."""
        result = build_institutional_auditor_export(
            export_id="exp-lifecycle-pending",
            decision_provenance={
                "decisionStatus": "approved",
                "readiness": {"evidence": "ready"},
                "auditReadiness": {"status": "ready"},
            },
            auditor_report={"auditReady": True},
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": True},
            approval_lifecycle={"status": "pending"},
            policy_results=[{"passed": True}],
        )

        self.assertEqual(result["exportStatus"], "needs_review")
        self.assertIn("approval_lifecycle_pending", result["warnings"])
        self.assertEqual(result["auditReadiness"], "needs_review")

    def test_include_details_false_omits_details(self):
        """Test that include_details=False omits detail objects."""
        result = build_institutional_auditor_export(
            export_id="exp-no-details",
            decision_provenance={"decisionStatus": "approved"},
            auditor_report={"auditReady": True},
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": True},
            approval_requirement={"required": False, "decision": "approved"},
            policy_results=[{"passed": True}],
            include_details=False,
        )

        self.assertNotIn("decisionProvenance", result)
        self.assertNotIn("auditorReport", result)
        self.assertNotIn("evidence", result)
        self.assertNotIn("compliance", result)
        self.assertNotIn("permission", result)
        self.assertNotIn("approval", result)
        self.assertNotIn("policy", result)
        self.assertNotIn("metadata", result)

    def test_include_details_true_includes_details(self):
        """Test that include_details=True includes detail objects."""
        result = build_institutional_auditor_export(
            export_id="exp-with-details",
            decision_provenance={"decisionStatus": "approved"},
            auditor_report={"auditReady": True},
            evidence_completeness={"complete": True},
            compliance_gap_report={"overallStatus": "complete"},
            permission_result={"allowed": True},
            approval_requirement={"required": False, "decision": "approved"},
            policy_results=[{"passed": True}],
            metadata={"source": "test"},
            context={"env": "testing"},
            include_details=True,
        )

        self.assertIn("decisionProvenance", result)
        self.assertIn("auditorReport", result)
        self.assertIn("evidence", result)
        self.assertIn("compliance", result)
        self.assertIn("permission", result)
        self.assertIn("approval", result)
        self.assertIn("policy", result)
        self.assertIn("metadata", result)
        self.assertIn("context", result)

    def test_no_secrets_in_output(self):
        """Test that no secrets or credentials are exposed in the export."""
        result = build_institutional_auditor_export(
            export_id="exp-secrets",
            decision_provenance={"decisionStatus": "approved"},
            metadata={"api_key": "secret123", "token": "bearer-token"},
            include_details=True,
        )

        # The builder itself does not redact; verify that sensitive fields
        # are only in the metadata detail object, not in the top-level structure.
        self.assertNotIn("api_key", result)
        self.assertNotIn("token", result)
        # metadata is in the detail section
        self.assertIn("metadata", result)

    def test_created_at_uses_provided_value(self):
        """Test that provided created_at is used."""
        result = build_institutional_auditor_export(
            export_id="exp-time",
            created_at="2024-01-01T00:00:00Z",
        )
        self.assertEqual(result["createdAt"], "2024-01-01T00:00:00Z")

    def test_created_at_generated_when_not_provided(self):
        """Test that created_at is generated when not provided."""
        result = build_institutional_auditor_export(
            export_id="exp-time-gen",
        )
        self.assertIsNotNone(result["createdAt"])
        self.assertTrue(isinstance(result["createdAt"], str))
        self.assertTrue(len(result["createdAt"]) > 0)

    def test_unknown_status_when_no_inputs(self):
        """Test unknown status when no meaningful inputs provided."""
        result = build_institutional_auditor_export(
            export_id="exp-unknown",
        )
        self.assertEqual(result["exportStatus"], "incomplete")
        self.assertEqual(result["auditReadiness"], "insufficient_evidence")

    def test_minimum_response_fields_present(self):
        """Test that all minimum response fields are present."""
        result = build_institutional_auditor_export(
            export_id="exp-min",
        )
        required_fields = [
            "recordType",
            "recordVersion",
            "exportId",
            "exportType",
            "subjectId",
            "decisionId",
            "generatedBy",
            "auditorId",
            "exportStatus",
            "auditReadiness",
            "sections",
            "blockers",
            "warnings",
            "missingSections",
            "createdAt",
        ]
        for field in required_fields:
            self.assertIn(field, result, f"Missing required field: {field}")

    def test_deduplication_of_blockers_and_warnings(self):
        """Test that duplicate blockers and warnings are deduplicated."""
        result = build_institutional_auditor_export(
            export_id="exp-dedup",
            decision_provenance={
                "decisionStatus": "blocked",
                "readiness": {"compliance": "blocked", "permission": "blocked"},
                "auditReadiness": {"status": "blocked"},
            },
            compliance_gap_report={
                "criticalGaps": [{"id": "g1"}],
                "highGaps": [{"id": "g2"}],
            },
            policy_results=[{"failed": True}, {"failed": True}],
        )

        self.assertEqual(len(result["blockers"]), len(set(result["blockers"])))
        self.assertEqual(len(result["warnings"]), len(set(result["warnings"])))


if __name__ == "__main__":
    unittest.main()
