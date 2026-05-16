"""GL-044-A — Compliance Readiness Summary Builder tests.

Tests for the pure function that builds a compliance readiness summary
from structured GrantLayer signals.

No DB access, no network calls, no API endpoint.
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.compliance_readiness import (
    build_compliance_readiness_summary,
    RECORD_TYPE,
    RECORD_VERSION,
)


class TestComplianceReadinessBuilder(unittest.TestCase):
    """Compliance readiness summary builder tests."""

    def test_module_import(self):
        """Test that the module imports successfully."""
        import src.compliance_readiness as cr_mod
        self.assertIsNotNone(cr_mod)
        self.assertTrue(hasattr(cr_mod, "build_compliance_readiness_summary"))
        self.assertEqual(cr_mod.RECORD_TYPE, "compliance_readiness_summary")
        self.assertEqual(cr_mod.RECORD_VERSION, "gl-compliance-readiness-v1")

    def test_function_exists(self):
        """Test that the build function exists and is callable."""
        self.assertTrue(callable(build_compliance_readiness_summary))

    def test_contract_fields_present(self):
        """Test that all required contract fields are present."""
        result = build_compliance_readiness_summary()
        required_keys = {
            "recordType", "recordVersion", "subjectId", "workflowId",
            "readinessStatus", "readinessScore",
            "evidenceStatus", "complianceStatus", "permissionStatus",
            "approvalStatus", "provenanceStatus", "auditorExportStatus", "policyStatus",
            "blockers", "warnings", "missingInputs", "recommendedActions",
            "createdAt",
        }
        self.assertTrue(required_keys.issubset(result.keys()))

    def test_all_ready_inputs_produces_ready(self):
        """Test that all ready inputs produce an overall ready status."""
        result = build_compliance_readiness_summary(
            execution_id="ex-123",
            grant_id="g-123",
            subject_id="sub-123",
            workflow_id="wf-123",
            evidence_completeness={"completenessStatus": "complete", "completenessScore": 95},
            compliance_gap_report={"overallStatus": "clear", "complianceGaps": []},
            permission_result={"allowed": True},
            approval_requirement={"required": False},
            provenance_summary={"events": [{"id": "evt-1"}]},
            auditor_report={"auditReady": True, "conclusion": "clean"},
            policy_results=[{"passed": True}],
        )

        self.assertEqual(result["recordType"], RECORD_TYPE)
        self.assertEqual(result["recordVersion"], RECORD_VERSION)
        self.assertEqual(result["executionId"], "ex-123")
        self.assertEqual(result["grantId"], "g-123")
        self.assertEqual(result["subjectId"], "sub-123")
        self.assertEqual(result["workflowId"], "wf-123")
        self.assertIn("createdAt", result)
        self.assertEqual(result["readinessStatus"], "ready")
        self.assertEqual(result["readinessScore"], 100)
        self.assertEqual(result["evidenceStatus"], "ready")
        self.assertEqual(result["complianceStatus"], "ready")
        self.assertEqual(result["permissionStatus"], "ready")
        self.assertEqual(result["approvalStatus"], "ready")
        self.assertEqual(result["provenanceStatus"], "ready")
        self.assertEqual(result["auditorExportStatus"], "ready")
        self.assertEqual(result["policyStatus"], "ready")
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["missingInputs"], [])
        self.assertIsInstance(result["recommendedActions"], list)
        self.assertEqual(result["recommendedActions"], [])

    def test_no_inputs_produces_not_assessed(self):
        """Test that no inputs produce not_assessed overall status."""
        result = build_compliance_readiness_summary()

        self.assertEqual(result["readinessStatus"], "not_assessed")
        self.assertEqual(result["evidenceStatus"], "not_assessed")
        self.assertEqual(result["complianceStatus"], "not_assessed")
        self.assertEqual(result["permissionStatus"], "not_assessed")
        self.assertEqual(result["approvalStatus"], "not_assessed")
        self.assertEqual(result["provenanceStatus"], "not_assessed")
        self.assertEqual(result["auditorExportStatus"], "not_assessed")
        self.assertEqual(result["policyStatus"], "not_assessed")
        self.assertEqual(result["readinessScore"], 0)
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["warnings"], [])
        self.assertTrue(len(result["missingInputs"]) > 0)

    def test_old_fields_removed(self):
        """Test that old contract fields are no longer present."""
        result = build_compliance_readiness_summary()
        self.assertNotIn("overallReadiness", result)
        self.assertNotIn("readinessByDimension", result)
        self.assertNotIn("scores", result)
        self.assertNotIn("generatedAt", result)

    def test_evidence_critical_blocked(self):
        """Test that critical evidence status blocks overall readiness."""
        result = build_compliance_readiness_summary(
            evidence_completeness={"completenessStatus": "critical"},
        )
        self.assertEqual(result["readinessStatus"], "blocked")
        self.assertEqual(result["evidenceStatus"], "blocked")
        self.assertIn("evidence_critical", result["blockers"])

    def test_compliance_blocked(self):
        """Test that blocked compliance gap report blocks overall readiness."""
        result = build_compliance_readiness_summary(
            compliance_gap_report={"overallStatus": "blocked", "complianceGaps": [{"gapId": "test"}]},
        )
        self.assertEqual(result["readinessStatus"], "blocked")
        self.assertEqual(result["complianceStatus"], "blocked")
        self.assertIn("compliance_blocked", result["blockers"])

    def test_permission_denied_blocked(self):
        """Test that denied permission blocks overall readiness."""
        result = build_compliance_readiness_summary(
            permission_result={"allowed": False},
        )
        self.assertEqual(result["readinessStatus"], "blocked")
        self.assertEqual(result["permissionStatus"], "blocked")
        self.assertIn("permission_denied", result["blockers"])

    def test_approval_requirement_blocked(self):
        """Test that blocked approval requirement blocks overall readiness."""
        result = build_compliance_readiness_summary(
            approval_requirement={"decision": "blocked"},
        )
        self.assertEqual(result["readinessStatus"], "blocked")
        self.assertEqual(result["approvalStatus"], "blocked")
        self.assertIn("approval_requirement_blocked", result["blockers"])

    def test_approval_lifecycle_denied_blocked(self):
        """Test that denied approval lifecycle blocks overall readiness."""
        result = build_compliance_readiness_summary(
            approval_lifecycle={"status": "denied"},
        )
        self.assertEqual(result["readinessStatus"], "blocked")
        self.assertEqual(result["approvalStatus"], "blocked")
        self.assertIn("approval_lifecycle_denied", result["blockers"])

    def test_auditor_not_ready_blocked(self):
        """Test that non-ready auditor report blocks overall readiness."""
        result = build_compliance_readiness_summary(
            auditor_report={"auditReady": False, "conclusion": "attention_required"},
        )
        self.assertEqual(result["readinessStatus"], "blocked")
        self.assertEqual(result["auditorExportStatus"], "blocked")
        self.assertIn("auditor_not_ready", result["blockers"])

    def test_policy_failed_blocked(self):
        """Test that failed policy results block overall readiness."""
        result = build_compliance_readiness_summary(
            policy_results=[{"failed": True}],
        )
        self.assertEqual(result["readinessStatus"], "blocked")
        self.assertEqual(result["policyStatus"], "blocked")
        self.assertIn("policy_failed", result["blockers"])

    def test_needs_review_from_incomplete_evidence(self):
        """Test that incomplete evidence produces needs_review, not blocked."""
        result = build_compliance_readiness_summary(
            evidence_completeness={"completenessStatus": "incomplete"},
        )
        self.assertEqual(result["readinessStatus"], "needs_review")
        self.assertEqual(result["evidenceStatus"], "needs_review")
        self.assertIn("evidence_incomplete", result["warnings"])

    def test_needs_review_from_gaps_detected(self):
        """Test that gaps detected in compliance produces needs_review."""
        result = build_compliance_readiness_summary(
            compliance_gap_report={"overallStatus": "gaps_detected", "complianceGaps": [{"gapId": "g1"}]},
        )
        self.assertEqual(result["readinessStatus"], "needs_review")
        self.assertEqual(result["complianceStatus"], "needs_review")
        self.assertIn("compliance_gaps_detected", result["warnings"])

    def test_needs_review_from_unknown_permission(self):
        """Test that unknown permission produces needs_review."""
        result = build_compliance_readiness_summary(
            permission_result={"allowed": None},
        )
        self.assertEqual(result["readinessStatus"], "needs_review")
        self.assertEqual(result["permissionStatus"], "needs_review")
        self.assertIn("permission_unknown", result["warnings"])

    def test_needs_review_from_pending_approval(self):
        """Test that pending approval produces needs_review."""
        result = build_compliance_readiness_summary(
            approval_requirement={"decision": "pending"},
        )
        self.assertEqual(result["readinessStatus"], "needs_review")
        self.assertEqual(result["approvalStatus"], "needs_review")
        self.assertIn("approval_requirement_pending", result["warnings"])

    def test_needs_review_from_limited_provenance(self):
        """Test that limited provenance produces needs_review."""
        result = build_compliance_readiness_summary(
            provenance_summary={"events": []},
        )
        self.assertEqual(result["readinessStatus"], "needs_review")
        self.assertEqual(result["provenanceStatus"], "needs_review")
        self.assertIn("provenance_limited", result["warnings"])

    def test_needs_review_from_partial_policy(self):
        """Test that partial policy results produce needs_review."""
        result = build_compliance_readiness_summary(
            policy_results=[{"passed": False, "failed": False}],
        )
        self.assertEqual(result["readinessStatus"], "needs_review")
        self.assertEqual(result["policyStatus"], "needs_review")
        self.assertIn("policy_partial", result["warnings"])

    def test_approval_ready_when_approved(self):
        """Test that approved approval requirement produces ready."""
        result = build_compliance_readiness_summary(
            approval_requirement={"decision": "approved"},
        )
        self.assertEqual(result["approvalStatus"], "ready")

    def test_approval_ready_when_not_required(self):
        """Test that not-required approval produces ready."""
        result = build_compliance_readiness_summary(
            approval_requirement={"required": False},
        )
        self.assertEqual(result["approvalStatus"], "ready")

    def test_approval_ready_when_lifecycle_approved(self):
        """Test that approved lifecycle produces ready even without requirement."""
        result = build_compliance_readiness_summary(
            approval_lifecycle={"status": "approved"},
        )
        self.assertEqual(result["approvalStatus"], "ready")

    def test_provenance_ready_with_events(self):
        """Test that provenance with events produces ready."""
        result = build_compliance_readiness_summary(
            provenance_summary={"events": [{"id": "e1"}]},
        )
        self.assertEqual(result["provenanceStatus"], "ready")

    def test_auditor_ready_with_clean_conclusion(self):
        """Test that auditor report with clean conclusion produces ready."""
        result = build_compliance_readiness_summary(
            auditor_report={"conclusion": "clean"},
        )
        self.assertEqual(result["auditorExportStatus"], "ready")

    def test_auditor_blocked_by_critical_findings(self):
        """Test that critical findings block auditor readiness."""
        result = build_compliance_readiness_summary(
            auditor_report={"auditReady": True, "criticalFindings": [{"id": "f1"}]},
        )
        self.assertEqual(result["auditorExportStatus"], "blocked")
        self.assertIn("auditor_critical_findings", result["blockers"])

    def test_readiness_score_with_no_inputs(self):
        """Test readiness score when no inputs are provided."""
        result = build_compliance_readiness_summary()
        self.assertEqual(result["readinessScore"], 0)

    def test_readiness_score_with_all_ready(self):
        """Test readiness score when all dimensions are ready."""
        result = build_compliance_readiness_summary(
            evidence_completeness={"completenessStatus": "complete"},
            compliance_gap_report={"overallStatus": "clear"},
            permission_result={"allowed": True},
            approval_requirement={"required": False},
            provenance_summary={"events": [{"id": "e1"}]},
            auditor_report={"auditReady": True},
            policy_results=[{"passed": True}],
        )
        self.assertEqual(result["readinessScore"], 100)

    def test_readiness_score_with_partial_ready(self):
        """Test readiness score with some ready dimensions."""
        result = build_compliance_readiness_summary(
            evidence_completeness={"completenessStatus": "complete"},
            compliance_gap_report={"overallStatus": "gaps_detected"},
            permission_result={"allowed": True},
            approval_requirement={"required": False},
            provenance_summary={"events": [{"id": "e1"}]},
            auditor_report={"auditReady": True},
            policy_results=[{"passed": True}],
        )
        self.assertEqual(result["readinessScore"], 85)

    def test_recommended_actions_populated(self):
        """Test that recommended actions are generated from blockers/warnings."""
        result = build_compliance_readiness_summary(
            evidence_completeness={"completenessStatus": "critical"},
        )
        self.assertTrue(len(result["recommendedActions"]) > 0)
        self.assertIn("Submit missing or incomplete evidence to unblock readiness.", result["recommendedActions"])

    def test_recommended_actions_empty_when_ready(self):
        """Test that recommended actions are empty when everything is ready."""
        result = build_compliance_readiness_summary(
            evidence_completeness={"completenessStatus": "complete"},
            compliance_gap_report={"overallStatus": "clear"},
            permission_result={"allowed": True},
            approval_requirement={"required": False},
            provenance_summary={"events": [{"id": "e1"}]},
            auditor_report={"auditReady": True},
            policy_results=[{"passed": True}],
        )
        self.assertEqual(result["recommendedActions"], [])

    def test_include_details_true_includes_nested_objects(self):
        """Test that include_details=True includes nested objects."""
        ec = {"completenessStatus": "complete"}
        cgr = {"overallStatus": "clear"}
        result = build_compliance_readiness_summary(
            evidence_completeness=ec,
            compliance_gap_report=cgr,
            include_details=True,
        )
        self.assertEqual(result["evidenceCompleteness"], ec)
        self.assertEqual(result["complianceGapReport"], cgr)

    def test_include_details_false_omits_nested_objects(self):
        """Test that include_details=False omits nested detail objects."""
        ec = {"completenessStatus": "complete"}
        cgr = {"overallStatus": "clear"}
        result = build_compliance_readiness_summary(
            evidence_completeness=ec,
            compliance_gap_report=cgr,
            include_details=False,
        )
        self.assertNotIn("evidenceCompleteness", result)
        self.assertNotIn("complianceGapReport", result)
        self.assertNotIn("permissionResult", result)
        self.assertNotIn("approval", result)
        self.assertNotIn("provenance", result)
        self.assertNotIn("auditorReport", result)
        self.assertNotIn("policy", result)
        self.assertNotIn("context", result)

    def test_context_included_when_include_details_true(self):
        """Test that context is included when include_details=True."""
        ctx = {"requestId": "req-1"}
        result = build_compliance_readiness_summary(
            context=ctx,
            include_details=True,
        )
        self.assertEqual(result["context"], ctx)

    def test_context_excluded_when_include_details_false(self):
        """Test that context is excluded when include_details=False."""
        ctx = {"requestId": "req-1"}
        result = build_compliance_readiness_summary(
            context=ctx,
            include_details=False,
        )
        self.assertNotIn("context", result)

    def test_blockers_deduplicated(self):
        """Test that duplicate blockers are deduplicated."""
        result = build_compliance_readiness_summary(
            compliance_gap_report={"overallStatus": "blocked", "complianceGaps": [{"gapId": "g1"}]},
            policy_results=[{"failed": True}],
        )
        self.assertEqual(len(result["blockers"]), len(set(result["blockers"])))

    def test_warnings_deduplicated(self):
        """Test that duplicate warnings are deduplicated."""
        result = build_compliance_readiness_summary(
            evidence_completeness={"completenessStatus": "incomplete"},
            compliance_gap_report={"overallStatus": "gaps_detected"},
        )
        self.assertEqual(len(result["warnings"]), len(set(result["warnings"])))

    def test_missing_inputs_deduplicated(self):
        """Test that duplicate missing inputs are deduplicated."""
        result = build_compliance_readiness_summary()
        self.assertEqual(len(result["missingInputs"]), len(set(result["missingInputs"])))

    def test_no_secrets_exposed_in_output(self):
        """Test that the response does not expose secrets."""
        result = build_compliance_readiness_summary(
            evidence_completeness={"completenessStatus": "complete"},
            compliance_gap_report={"overallStatus": "clear"},
            permission_result={"allowed": True},
            context={"note": "safe"},
            include_details=True,
        )
        result_str = str(result)
        self.assertNotIn("Bearer", result_str)
        self.assertNotIn("token", result_str.lower())
        self.assertNotIn("secret", result_str.lower())
        self.assertNotIn("password", result_str.lower())

    def test_created_at_override(self):
        """Test that created_at can be overridden."""
        custom_time = "2026-05-15T10:00:00Z"
        result = build_compliance_readiness_summary(
            created_at=custom_time,
        )
        self.assertEqual(result["createdAt"], custom_time)

    def test_execution_id_and_grant_id_optional(self):
        """Test that execution_id and grant_id are optional."""
        result = build_compliance_readiness_summary()
        self.assertIsNone(result["executionId"])
        self.assertIsNone(result["grantId"])

    def test_subject_id_and_workflow_id_optional(self):
        """Test that subject_id and workflow_id are optional."""
        result = build_compliance_readiness_summary()
        self.assertIsNone(result["subjectId"])
        self.assertIsNone(result["workflowId"])

    def test_mixed_ready_and_needs_review(self):
        """Test mixed readiness states with no blockers produce needs_review."""
        result = build_compliance_readiness_summary(
            evidence_completeness={"completenessStatus": "complete"},
            compliance_gap_report={"overallStatus": "gaps_detected", "complianceGaps": [{"gapId": "g1"}]},
            permission_result={"allowed": True},
            approval_requirement={"required": False},
            provenance_summary={"events": [{"id": "e1"}]},
            auditor_report={"auditReady": True},
            policy_results=[{"passed": True}],
        )
        self.assertEqual(result["readinessStatus"], "needs_review")
        self.assertEqual(result["evidenceStatus"], "ready")
        self.assertEqual(result["complianceStatus"], "needs_review")
        self.assertEqual(result["permissionStatus"], "ready")
        self.assertEqual(result["readinessScore"], 85)

    def test_mixed_ready_and_not_assessed(self):
        """Test that ready + not_assessed without blockers produces needs_review."""
        result = build_compliance_readiness_summary(
            evidence_completeness={"completenessStatus": "complete"},
            permission_result={"allowed": True},
        )
        self.assertEqual(result["readinessStatus"], "needs_review")
        self.assertEqual(result["evidenceStatus"], "ready")
        self.assertEqual(result["permissionStatus"], "ready")
        self.assertEqual(result["complianceStatus"], "not_assessed")

    def test_all_not_assessed(self):
        """Test that all not_assessed with no ready produces not_assessed."""
        result = build_compliance_readiness_summary()
        self.assertEqual(result["readinessStatus"], "not_assessed")

    def test_approval_priority_blocked_over_pending(self):
        """Test that blocked approval takes priority over pending."""
        result = build_compliance_readiness_summary(
            approval_requirement={"decision": "pending"},
            approval_lifecycle={"status": "blocked"},
        )
        self.assertEqual(result["approvalStatus"], "blocked")
        self.assertIn("approval_lifecycle_blocked", result["blockers"])
        self.assertIn("approval_requirement_pending", result["warnings"])

    def test_approval_priority_denied_over_pending(self):
        """Test that denied approval takes priority over pending."""
        result = build_compliance_readiness_summary(
            approval_requirement={"decision": "pending"},
            approval_lifecycle={"status": "denied"},
        )
        self.assertEqual(result["approvalStatus"], "blocked")
        self.assertIn("approval_lifecycle_denied", result["blockers"])

    def test_approval_priority_pending_over_approved(self):
        """Test that pending approval takes priority over approved lifecycle."""
        result = build_compliance_readiness_summary(
            approval_requirement={"decision": "pending"},
            approval_lifecycle={"status": "approved"},
        )
        self.assertEqual(result["approvalStatus"], "needs_review")
        self.assertIn("approval_requirement_pending", result["warnings"])

    def test_policy_results_with_non_dict_items(self):
        """Test that non-dict items in policy_results are skipped gracefully."""
        result = build_compliance_readiness_summary(
            policy_results=["not_a_dict", {"passed": True}],
        )
        self.assertEqual(result["policyStatus"], "ready")

    def test_compliance_gap_report_with_none_overall_status(self):
        """Test compliance gap report with None overallStatus."""
        result = build_compliance_readiness_summary(
            compliance_gap_report={"overallStatus": None},
        )
        self.assertEqual(result["complianceStatus"], "needs_review")
        self.assertIn("compliance_gaps_detected", result["warnings"])

    def test_evidence_completeness_with_only_status(self):
        """Test evidence completeness dict with only status key."""
        result = build_compliance_readiness_summary(
            evidence_completeness={"status": "complete"},
        )
        self.assertEqual(result["evidenceStatus"], "ready")

    def test_evidence_completeness_with_only_completeness_status(self):
        """Test evidence completeness dict with only completenessStatus key."""
        result = build_compliance_readiness_summary(
            evidence_completeness={"completenessStatus": "incomplete"},
        )
        self.assertEqual(result["evidenceStatus"], "needs_review")

    def test_permission_result_allowed_true(self):
        """Test permission result with allowed=True."""
        result = build_compliance_readiness_summary(
            permission_result={"allowed": True},
        )
        self.assertEqual(result["permissionStatus"], "ready")

    def test_permission_result_allowed_false(self):
        """Test permission result with allowed=False."""
        result = build_compliance_readiness_summary(
            permission_result={"allowed": False},
        )
        self.assertEqual(result["permissionStatus"], "blocked")

    def test_permission_result_no_allowed_key(self):
        """Test permission result without allowed key."""
        result = build_compliance_readiness_summary(
            permission_result={"reason": "unknown"},
        )
        self.assertEqual(result["permissionStatus"], "needs_review")

    def test_record_type_and_version_always_present(self):
        """Test that record type and version are always present."""
        result = build_compliance_readiness_summary()
        self.assertEqual(result["recordType"], RECORD_TYPE)
        self.assertEqual(result["recordVersion"], RECORD_VERSION)

    def test_no_bundle_json_in_response(self):
        """Test that raw bundle JSON is never exposed."""
        result = build_compliance_readiness_summary(
            evidence_completeness={"completenessStatus": "complete"},
            compliance_gap_report={"overallStatus": "clear"},
            include_details=True,
        )
        result_str = str(result)
        self.assertNotIn("bundle_json", result_str)
        self.assertNotIn("bundleJson", result_str)

    def test_no_metadata_json_in_response(self):
        """Test that raw metadata JSON is never exposed."""
        result = build_compliance_readiness_summary(
            provenance_summary={"events": [{"id": "e1"}]},
            include_details=True,
        )
        result_str = str(result)
        self.assertNotIn("metadata_json", result_str)
        self.assertNotIn("metadataJson", result_str)

    def test_approval_none_lifecycle_with_missing_requirement(self):
        """Test approval when lifecycle is None and requirement is missing."""
        result = build_compliance_readiness_summary(
            approval_lifecycle=None,
        )
        self.assertEqual(result["approvalStatus"], "not_assessed")

    def test_compliance_with_empty_gap_list(self):
        """Test compliance gap report with empty gap list but not clear status."""
        result = build_compliance_readiness_summary(
            compliance_gap_report={"overallStatus": "gaps_detected", "complianceGaps": []},
        )
        self.assertEqual(result["complianceStatus"], "needs_review")
        self.assertIn("compliance_gaps_detected", result["warnings"])

    def test_policy_results_empty_list(self):
        """Test empty policy results list."""
        result = build_compliance_readiness_summary(
            policy_results=[],
        )
        self.assertEqual(result["policyStatus"], "ready")
        self.assertEqual(result["readinessScore"], 14)

    def test_context_is_none_by_default(self):
        """Test that context is None when not provided even with include_details."""
        result = build_compliance_readiness_summary(
            include_details=True,
        )
        self.assertNotIn("context", result)

    def test_all_dimensions_blocked_produces_blocked(self):
        """Test that when all dimensions are blocked, overall is blocked."""
        result = build_compliance_readiness_summary(
            evidence_completeness={"completenessStatus": "critical"},
            compliance_gap_report={"overallStatus": "blocked"},
            permission_result={"allowed": False},
            approval_requirement={"decision": "blocked"},
            provenance_summary={"events": []},
            auditor_report={"auditReady": False},
            policy_results=[{"failed": True}],
        )
        self.assertEqual(result["readinessStatus"], "blocked")
        self.assertEqual(result["readinessScore"], 0)
        self.assertTrue(len(result["blockers"]) > 0)

    def test_some_ready_some_blocked(self):
        """Test mixed ready and blocked states."""
        result = build_compliance_readiness_summary(
            evidence_completeness={"completenessStatus": "complete"},
            compliance_gap_report={"overallStatus": "clear"},
            permission_result={"allowed": True},
            approval_requirement={"required": False},
            provenance_summary={"events": [{"id": "e1"}]},
            auditor_report={"auditReady": True},
            policy_results=[{"failed": True}],
        )
        self.assertEqual(result["readinessStatus"], "blocked")
        self.assertEqual(result["policyStatus"], "blocked")
        self.assertEqual(result["evidenceStatus"], "ready")
        self.assertEqual(result["readinessScore"], 85)

    def test_scores_with_only_policy_results(self):
        """Test scores computation with only policy results."""
        result = build_compliance_readiness_summary(
            policy_results=[{"passed": True}],
        )
        self.assertEqual(result["readinessScore"], 14)

    def test_multiple_policy_results_all_passed(self):
        """Test multiple policy results all passed."""
        result = build_compliance_readiness_summary(
            policy_results=[{"passed": True}, {"passed": True}],
        )
        self.assertEqual(result["policyStatus"], "ready")

    def test_multiple_policy_results_one_failed(self):
        """Test multiple policy results with one failed."""
        result = build_compliance_readiness_summary(
            policy_results=[{"passed": True}, {"failed": True}],
        )
        self.assertEqual(result["policyStatus"], "blocked")
        self.assertIn("policy_failed", result["blockers"])

    def test_compliance_clear_status_ready(self):
        """Test that compliance clear status produces ready."""
        result = build_compliance_readiness_summary(
            compliance_gap_report={"overallStatus": "clear"},
        )
        self.assertEqual(result["complianceStatus"], "ready")

    def test_evidence_status_none(self):
        """Test evidence completeness with status None."""
        result = build_compliance_readiness_summary(
            evidence_completeness={"completenessStatus": None},
        )
        self.assertEqual(result["evidenceStatus"], "needs_review")

    def test_approval_both_requirement_and_lifecycle_missing(self):
        """Test approval when both requirement and lifecycle are missing."""
        result = build_compliance_readiness_summary()
        self.assertEqual(result["approvalStatus"], "not_assessed")
        self.assertIn("approval_requirement", result["missingInputs"])

    def test_provenance_with_provenance_events_key(self):
        """Test provenance summary using provenanceEvents key."""
        result = build_compliance_readiness_summary(
            provenance_summary={"provenanceEvents": [{"id": "e1"}]},
        )
        self.assertEqual(result["provenanceStatus"], "ready")

    def test_approval_requirement_required_true(self):
        """Test approval requirement with required=True but no decision."""
        result = build_compliance_readiness_summary(
            approval_requirement={"required": True},
        )
        self.assertEqual(result["approvalStatus"], "needs_review")
        self.assertIn("approval_required", result["warnings"])

    def test_auditor_report_with_critical_findings_list(self):
        """Test auditor report with critical findings as empty list."""
        result = build_compliance_readiness_summary(
            auditor_report={"auditReady": True, "criticalFindings": []},
        )
        self.assertEqual(result["auditorExportStatus"], "ready")

    def test_compliance_gap_report_with_critical_gaps(self):
        """Test compliance gap report with critical gaps in gaps list."""
        result = build_compliance_readiness_summary(
            compliance_gap_report={
                "overallStatus": "blocked",
                "complianceGaps": [{"gapId": "g1", "severity": "critical"}],
            },
        )
        self.assertEqual(result["complianceStatus"], "blocked")

    def test_include_details_true_approval_none(self):
        """Test approval detail is None when no approval inputs and include_details=True."""
        result = build_compliance_readiness_summary(
            include_details=True,
        )
        if "approval" in result:
            self.assertIsNone(result["approval"])

    def test_created_at_is_iso_string(self):
        """Test that createdAt is an ISO datetime string."""
        result = build_compliance_readiness_summary()
        self.assertIsInstance(result["createdAt"], str)
        self.assertTrue(len(result["createdAt"]) > 0)

    def test_empty_dict_inputs_treated_as_present(self):
        """Test that empty dict inputs are treated as present inputs."""
        result = build_compliance_readiness_summary(
            evidence_completeness={},
            compliance_gap_report={},
            permission_result={},
            approval_requirement={},
            provenance_summary={},
            auditor_report={},
            policy_results=[],
        )
        self.assertEqual(result["evidenceStatus"], "needs_review")
        self.assertEqual(result["complianceStatus"], "needs_review")
        self.assertEqual(result["permissionStatus"], "needs_review")
        self.assertEqual(result["approvalStatus"], "ready")
        self.assertEqual(result["provenanceStatus"], "needs_review")
        self.assertEqual(result["auditorExportStatus"], "blocked")
        self.assertEqual(result["policyStatus"], "ready")
        self.assertEqual(result["missingInputs"], [])

    def test_subject_id_override_grant_id(self):
        """Test that subject_id and workflow_id can be set separately."""
        result = build_compliance_readiness_summary(
            grant_id="g-old",
            subject_id="sub-new",
            workflow_id="wf-test",
        )
        self.assertEqual(result["grantId"], "g-old")
        self.assertEqual(result["subjectId"], "sub-new")
        self.assertEqual(result["workflowId"], "wf-test")

    def test_recommended_actions_multiple_warnings(self):
        """Test recommended actions with multiple warnings."""
        result = build_compliance_readiness_summary(
            evidence_completeness={"completenessStatus": "incomplete"},
            compliance_gap_report={"overallStatus": "gaps_detected"},
        )
        actions = result["recommendedActions"]
        self.assertTrue(len(actions) >= 2)
        self.assertIn("Complete outstanding evidence submissions.", actions)
        self.assertIn("Review and remediate detected compliance gaps.", actions)

    def test_recommended_actions_with_blockers_and_warnings(self):
        """Test recommended actions include both blocker and warning actions."""
        result = build_compliance_readiness_summary(
            evidence_completeness={"completenessStatus": "critical"},
            permission_result={"allowed": None},
        )
        actions = result["recommendedActions"]
        self.assertIn("Submit missing or incomplete evidence to unblock readiness.", actions)
        self.assertIn("Clarify permission status for target scope.", actions)

    def test_recommended_actions_deduplicated(self):
        """Test that identical recommended actions are deduplicated."""
        # Only produce the same blocker twice via critical findings path
        result = build_compliance_readiness_summary(
            auditor_report={"auditReady": False, "criticalFindings": [{"id": "f1"}]},
        )
        # Should have deduplicated recommended actions
        actions = result["recommendedActions"]
        self.assertEqual(len(actions), len(set(actions)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
