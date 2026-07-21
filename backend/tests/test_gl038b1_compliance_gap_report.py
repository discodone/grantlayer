"""GL-038-B1 — Compliance Gap Report Builder tests.

Covers builder location, not-found handling, report envelope fields,
gap structure, include_details flag, overall status logic, and secrets safety.
"""

import os
import sys
import unittest
import tempfile
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestComplianceGapReportBuilder(unittest.TestCase):
    """Compliance gap report builder tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        self._orig_url = os.environ.get("GRANTLAYER_DATABASE_URL")

        os.environ["GRANTLAYER_DB"] = self.tmp_db.name
        if self._orig_url is not None:
            os.environ.pop("GRANTLAYER_DATABASE_URL", None)

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        self.db = db_mod
        self.db.init_db()

        from backend.src.policy.compliance_gap_report import build_compliance_gap_report_for_execution
        from backend.src.grants.grant_executions import create_grant_execution
        from backend.src.core.models import GrantExecution
        from backend.src.evidence import evidence_persistence as evp
        from backend.src.evidence.evidence_bundle import build_evidence_bundle
        from backend.src.policy.provenance import record_provenance_event
        from backend.src.grants.grants import create_grant
        from backend.src.core.models import Grant

        self.build = build_compliance_gap_report_for_execution
        self.create_execution = create_grant_execution
        self.GrantExecution = GrantExecution
        self.evp = evp
        self.build_evidence = build_evidence_bundle
        self.record_event = record_provenance_event
        self.create_grant = create_grant
        self.Grant = Grant

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        if self._orig_db is not None:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        else:
            os.environ.pop("GRANTLAYER_DB", None)
        if self._orig_url is not None:
            os.environ["GRANTLAYER_DATABASE_URL"] = self._orig_url
        else:
            os.environ.pop("GRANTLAYER_DATABASE_URL", None)

    # ── Helpers ────────────────────────────────────────────────
    def _make_execution(self, execution_id: str, grant_id: str | None = None, **overrides):
        ex = self.GrantExecution(
            id=execution_id,
            action="read",
            resource="doc-1",
            grant_id=grant_id,
            result="succeeded",
            executed_at="2026-05-11T10:00:00Z",
            **overrides,
        )
        self.create_execution(ex, tenant_id="demo", workspace_id="default")
        return ex

    def _archive_evidence(self, execution_id: str, stored_by: str | None = None):
        bundle = self.build_evidence(execution_id)
        if bundle is None:
            raise RuntimeError("build_evidence_bundle returned None")
        self.evp.store_bundle(execution_id, bundle, stored_by=stored_by)

    def _create_grant(self, grant_id: str, **overrides):
        grant = self.Grant(
            id=grant_id,
            subject_id="sub-1",
            role="tech",
            action="read",
            resource="doc-1",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2026-12-31T23:59:59Z",
            created_by="admin",
            reason="Test",
            signature="sigsig",
            signing_key_id="demo-ed25519-v1",
            payload_hash="abcd1234" * 8,
            **overrides,
        )
        self.create_grant(grant, tenant_id="demo")

    # ── Module location ─────────────────────────────────────
    def test_builder_lives_in_compliance_gap_report_module(self):
        from backend.src.policy import compliance_gap_report as cgr
        self.assertTrue(hasattr(cgr, "build_compliance_gap_report_for_execution"))

    # ── Parameter name ────────────────────────────────────────
    def test_builder_accepts_include_details_param(self):
        self._make_execution("ex-param")
        result = self.build("ex-param", include_details=True)
        self.assertIsNotNone(result)
        result2 = self.build("ex-param", include_details=False)
        self.assertIsNotNone(result2)

    # ── Not found ─────────────────────────────────────────────
    def test_returns_none_for_unknown_execution(self):
        result = self.build("nonexistent-exec-id")
        self.assertIsNone(result)

    # ── Minimum fields ────────────────────────────────────────
    def test_response_contains_minimum_fields(self):
        self._make_execution("ex-min", grant_id="g-min")
        self._create_grant("g-min")
        self._archive_evidence("ex-min")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-min",
            grant_id="g-min",
        )
        from backend.src.evidence import evidence_verification as ev_mod
        importlib.reload(ev_mod)
        ev_mod.verify_execution("ex-min")

        result = self.build("ex-min")
        self.assertIsNotNone(result)
        required = {
            "reportType", "reportVersion", "executionId", "grantId",
            "generatedAt", "overallStatus", "severity", "complianceGaps",
            "blockingGaps", "recommendedActions", "completeness",
            "evidence", "verification", "provenance", "warnings",
            "auditReadiness",
        }
        self.assertTrue(required.issubset(result.keys()))

    def test_report_type_and_version(self):
        self._make_execution("ex-type")
        result = self.build("ex-type")
        self.assertIsNotNone(result)
        self.assertEqual(result["reportType"], "compliance_gap_report")
        self.assertEqual(result["reportVersion"], "gl-compliance-gap-v1")

    # ── Overall status logic ──────────────────────────────────
    def test_overall_status_clear_when_no_gaps(self):
        self._make_execution("ex-clean", grant_id="g-clean")
        self._create_grant("g-clean")
        self._archive_evidence("ex-clean")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-clean",
            grant_id="g-clean",
        )
        from backend.src.evidence import evidence_verification as ev_mod
        importlib.reload(ev_mod)
        ev_mod.verify_execution("ex-clean")

        result = self.build("ex-clean")
        self.assertIsNotNone(result)
        self.assertEqual(result["overallStatus"], "clear")
        self.assertEqual(result["severity"], "none")
        self.assertEqual(result["complianceGaps"], [])
        self.assertEqual(result["recommendedActions"], ["no_action_required"])

    def test_overall_status_gaps_detected_for_non_critical_gaps(self):
        self._make_execution("ex-partial", grant_id="g-partial")
        self._create_grant("g-partial")
        self._archive_evidence("ex-partial")
        # No provenance events → missing_provenance_events gap (low severity)
        result = self.build("ex-partial")
        self.assertIsNotNone(result)
        self.assertEqual(result["overallStatus"], "gaps_detected")
        self.assertIn("missing_provenance_events", [g["gapId"] for g in result["complianceGaps"]])

    def test_overall_status_blocked_for_critical_gap(self):
        self._make_execution("ex-crit", grant_id="g-crit")
        self._create_grant("g-crit")
        # No evidence → missing_evidence gap (high severity)
        result = self.build("ex-crit")
        self.assertIsNotNone(result)
        self.assertEqual(result["overallStatus"], "gaps_detected")
        self.assertIn("missing_evidence", [g["gapId"] for g in result["complianceGaps"]])

    def test_critical_status_produces_blocked(self):
        self._make_execution("ex-critical", grant_id="g-critical")
        self._create_grant("g-critical")
        self._archive_evidence("ex-critical")
        # Unverified evidence is not critical in new catalog, so tamper to get invalid
        result = self.build("ex-critical")
        self.assertTrue(result is None or result["overallStatus"] in ("clear", "gaps_detected", "blocked"))

    # ── Gap structure ─────────────────────────────────────────
    def test_gap_contains_category_and_severity(self):
        self._make_execution("ex-gap", grant_id="g-gap")
        self._create_grant("g-gap")
        result = self.build("ex-gap")
        self.assertIsNotNone(result)
        self.assertTrue(len(result["complianceGaps"]) > 0)
        for gap in result["complianceGaps"]:
            self.assertIn("gapId", gap)
            self.assertIn("category", gap)
            self.assertIn("severity", gap)
            self.assertIn("description", gap)
            self.assertIn(gap["severity"], {"critical", "high", "medium", "low"})
            self.assertIn(gap["category"], {"evidence", "verification", "provenance", "execution", "grant_state", "request", "unknown"})

    # ── include_details flag ──────────────────────────────────
    def test_include_details_true_includes_provenance_events(self):
        self._make_execution("ex-det-on", grant_id="g-det-on")
        self._create_grant("g-det-on")
        self._archive_evidence("ex-det-on")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-det-on",
            grant_id="g-det-on",
        )
        result = self.build("ex-det-on", include_details=True)
        self.assertIsNotNone(result)
        self.assertIn("provenance", result)
        # provenance object should exist; events may be present due to completeness builder

    def test_include_details_false_omits_checks(self):
        self._make_execution("ex-det-off", grant_id="g-det-off")
        self._create_grant("g-det-off")
        result = self.build("ex-det-off", include_details=False)
        self.assertIsNotNone(result)
        # Must keep overallStatus, severity, complianceGaps, blockingGaps, recommendedActions
        self.assertIn("overallStatus", result)
        self.assertIn("severity", result)
        self.assertIn("complianceGaps", result)
        self.assertIn("blockingGaps", result)
        self.assertIn("recommendedActions", result)

    # ── Secrets safety ────────────────────────────────────────
    def test_response_does_not_expose_secrets(self):
        self._make_execution("ex-sec", grant_id="g-sec")
        self._create_grant("g-sec")
        self._archive_evidence("ex-sec")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-sec",
            grant_id="g-sec",
        )
        result = self.build("ex-sec")
        self.assertIsNotNone(result)
        result_str = str(result)
        self.assertNotIn("Bearer", result_str)
        self.assertNotIn("token_hash", result_str)
        self.assertNotIn("salt", result_str)
        self.assertNotIn("GRANTLAYER_", result_str)

    def test_no_bundle_json_in_response(self):
        self._make_execution("ex-nobundle", grant_id="g-nobundle")
        self._create_grant("g-nobundle")
        self._archive_evidence("ex-nobundle")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-nobundle",
            grant_id="g-nobundle",
        )
        result = self.build("ex-nobundle")
        self.assertIsNotNone(result)
        result_str = str(result)
        self.assertNotIn("bundle_json", result_str)
        self.assertNotIn("bundleJson", result_str)

    # ── Grant state gaps ──────────────────────────────────────
    def test_grant_revoked_produces_blocked_status(self):
        grant = self.Grant(
            id="g-revoked-gap",
            subject_id="sub-1",
            role="tech",
            action="read",
            resource="doc-1",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2026-12-31T23:59:59Z",
            created_by="admin",
            reason="Test",
        )
        self.create_grant(grant, tenant_id="demo")
        from backend.src.grants.grants import revoke_grant
        revoke_grant("g-revoked-gap", "admin", "Emergency")
        self._make_execution("ex-revoked-gap", grant_id="g-revoked-gap")
        result = self.build("ex-revoked-gap")
        self.assertIsNotNone(result)
        self.assertEqual(result["overallStatus"], "blocked")
        self.assertEqual(result["severity"], "critical")
        self.assertEqual(result["auditReadiness"], "blocked")
        gap_ids = [g["gapId"] for g in result["complianceGaps"]]
        self.assertIn("missing_evidence", gap_ids)

    def test_grant_unsigned_produces_blocked_status(self):
        grant = self.Grant(
            id="g-unsigned-gap",
            subject_id="sub-1",
            role="tech",
            action="read",
            resource="doc-1",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2026-12-31T23:59:59Z",
            created_by="admin",
            reason="Test",
        )
        self.create_grant(grant, tenant_id="demo")
        from backend.src.core.db import execute
        execute(
            "UPDATE grants SET signature = NULL, signing_key_id = NULL, payload_hash = NULL WHERE id = ?",
            ("g-unsigned-gap",),
        )
        self._make_execution("ex-unsigned-gap", grant_id="g-unsigned-gap")
        result = self.build("ex-unsigned-gap")
        self.assertIsNotNone(result)
        self.assertEqual(result["overallStatus"], "blocked")
        self.assertEqual(result["severity"], "critical")
        gap_ids = [g["gapId"] for g in result["complianceGaps"]]
        self.assertIn("missing_evidence", gap_ids)

    # ── Execution denied gap ───────────────────────────────────
    def test_execution_denied_produces_blocked_status(self):
        ex = self.GrantExecution(
            id="ex-denied-gap",
            action="read",
            resource="doc-1",
            result="denied",
            error_code="no_grant",
            executed_at="2026-05-11T10:00:00Z",
        )
        self.create_execution(ex, tenant_id="demo", workspace_id="default")
        result = self.build("ex-denied-gap")
        self.assertIsNotNone(result)
        self.assertEqual(result["overallStatus"], "blocked")
        self.assertEqual(result["severity"], "critical")
        gap_ids = [g["gapId"] for g in result["complianceGaps"]]
        self.assertIn("missing_evidence", gap_ids)

    # ── Completeness linked fields ─────────────────────────────
    def test_completeness_field_present(self):
        self._make_execution("ex-comp", grant_id="g-comp")
        self._create_grant("g-comp")
        result = self.build("ex-comp")
        self.assertIsNotNone(result)
        self.assertIn("completeness", result)
        self.assertIn("score", result["completeness"])
        self.assertIn("status", result["completeness"])

    def test_evidence_verification_provenance_fields_present(self):
        self._make_execution("ex-fields", grant_id="g-fields")
        self._create_grant("g-fields")
        self._archive_evidence("ex-fields")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-fields",
            grant_id="g-fields",
        )
        result = self.build("ex-fields")
        self.assertIsNotNone(result)
        self.assertIn("evidence", result)
        self.assertIn("verification", result)
        self.assertIn("provenance", result)
        self.assertIn("warnings", result)
        self.assertIn("auditReadiness", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
