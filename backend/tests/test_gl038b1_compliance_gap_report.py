"""GL-038-B1 — Compliance Gap Report Builder tests.

Covers builder location, not-found handling, report envelope fields,
gap structure, remediation flag, overall compliance logic, and secrets safety.
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

        import src.db as db_mod
        importlib.reload(db_mod)
        self.db = db_mod
        self.db.init_db()

        from src.compliance_gap_report import build_compliance_gap_report_for_execution
        from src.grant_executions import create_grant_execution
        from src.models import GrantExecution
        from src import evidence_persistence as evp
        from src.evidence_bundle import build_evidence_bundle
        from src.provenance import record_provenance_event
        from src.grants import create_grant
        from src.models import Grant

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
    def _make_execution(self, execution_id: str, grant_id: str | None = None):
        ex = self.GrantExecution(
            id=execution_id,
            action="read",
            resource="doc-1",
            grant_id=grant_id,
            result="succeeded",
            executed_at="2026-05-11T10:00:00Z",
        )
        self.create_execution(ex)
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
        self.create_grant(grant)

    # ── Module location ─────────────────────────────────────
    def test_builder_lives_in_compliance_gap_report_module(self):
        from src import compliance_gap_report as cgr
        self.assertTrue(hasattr(cgr, "build_compliance_gap_report_for_execution"))

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
        from src import evidence_verification as ev_mod
        importlib.reload(ev_mod)
        ev_mod.verify_execution("ex-min")

        result = self.build("ex-min")
        self.assertIsNotNone(result)
        required = {
            "reportType", "reportVersion", "executionId", "grantId",
            "generatedAt", "overallCompliance", "totalGaps", "criticalGaps",
            "gaps", "evidenceCompletenessScore", "evidenceCompletenessStatus",
        }
        self.assertTrue(required.issubset(result.keys()))

    def test_report_type_and_version(self):
        self._make_execution("ex-type")
        result = self.build("ex-type")
        self.assertIsNotNone(result)
        self.assertEqual(result["reportType"], "compliance_gap_report")
        self.assertEqual(result["reportVersion"], "gl-038-b1")

    # ── Overall compliance logic ──────────────────────────────
    def test_overall_compliance_compliant_when_no_gaps(self):
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
        from src import evidence_verification as ev_mod
        importlib.reload(ev_mod)
        ev_mod.verify_execution("ex-clean")

        result = self.build("ex-clean")
        self.assertIsNotNone(result)
        self.assertEqual(result["overallCompliance"], "compliant")
        self.assertEqual(result["totalGaps"], 0)
        self.assertEqual(result["criticalGaps"], 0)
        self.assertEqual(result["gaps"], [])

    def test_overall_compliance_partial_for_non_critical_gaps(self):
        self._make_execution("ex-partial", grant_id="g-partial")
        self._create_grant("g-partial")
        self._archive_evidence("ex-partial")
        # No provenance events → missing_provenance_events gap (medium severity)
        result = self.build("ex-partial")
        self.assertIsNotNone(result)
        self.assertEqual(result["overallCompliance"], "partial")
        self.assertIn("missing_provenance_events", [g["gapId"] for g in result["gaps"]])

    def test_overall_compliance_non_compliant_for_critical_gap(self):
        self._make_execution("ex-crit", grant_id="g-crit")
        self._create_grant("g-crit")
        # No evidence → missing_evidence gap (critical severity)
        result = self.build("ex-crit")
        self.assertIsNotNone(result)
        self.assertEqual(result["overallCompliance"], "non_compliant")
        self.assertEqual(result["criticalGaps"], 1)
        self.assertIn("missing_evidence", [g["gapId"] for g in result["gaps"]])

    # ── Gap structure ─────────────────────────────────────────
    def test_gap_contains_category_and_severity(self):
        self._make_execution("ex-gap", grant_id="g-gap")
        self._create_grant("g-gap")
        # No evidence, no events
        result = self.build("ex-gap")
        self.assertIsNotNone(result)
        self.assertTrue(len(result["gaps"]) > 0)
        for gap in result["gaps"]:
            self.assertIn("gapId", gap)
            self.assertIn("category", gap)
            self.assertIn("severity", gap)
            self.assertIn("description", gap)
            self.assertIn(gap["severity"], {"critical", "high", "medium", "low"})
            self.assertIn(gap["category"], {"evidence", "verification", "provenance", "execution", "grant_state", "request_state", "unknown"})

    # ── include_remediation flag ──────────────────────────────
    def test_include_remediation_true_includes_remediation(self):
        self._make_execution("ex-rem-on", grant_id="g-rem-on")
        self._create_grant("g-rem-on")
        result = self.build("ex-rem-on", include_remediation=True)
        self.assertIsNotNone(result)
        for gap in result["gaps"]:
            self.assertIn("remediation", gap)

    def test_include_remediation_false_omits_remediation(self):
        self._make_execution("ex-rem-off", grant_id="g-rem-off")
        self._create_grant("g-rem-off")
        result = self.build("ex-rem-off", include_remediation=False)
        self.assertIsNotNone(result)
        for gap in result["gaps"]:
            self.assertNotIn("remediation", gap)

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
    def test_grant_revoked_produces_critical_gap(self):
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
        self.create_grant(grant)
        from src.grants import revoke_grant
        revoke_grant("g-revoked-gap", "admin", "Emergency")
        self._make_execution("ex-revoked-gap", grant_id="g-revoked-gap")
        result = self.build("ex-revoked-gap")
        self.assertIsNotNone(result)
        gap_ids = [g["gapId"] for g in result["gaps"]]
        self.assertIn("grant_revoked", gap_ids)
        revoked_gap = next(g for g in result["gaps"] if g["gapId"] == "grant_revoked")
        self.assertEqual(revoked_gap["severity"], "critical")
        self.assertEqual(revoked_gap["category"], "grant_state")

    def test_grant_unsigned_produces_critical_gap(self):
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
        self.create_grant(grant)
        from src.db import execute
        execute(
            "UPDATE grants SET signature = NULL, signing_key_id = NULL, payload_hash = NULL WHERE id = ?",
            ("g-unsigned-gap",),
        )
        self._make_execution("ex-unsigned-gap", grant_id="g-unsigned-gap")
        result = self.build("ex-unsigned-gap")
        self.assertIsNotNone(result)
        gap_ids = [g["gapId"] for g in result["gaps"]]
        self.assertIn("grant_unsigned", gap_ids)
        unsigned_gap = next(g for g in result["gaps"] if g["gapId"] == "grant_unsigned")
        self.assertEqual(unsigned_gap["severity"], "critical")
        self.assertEqual(unsigned_gap["category"], "grant_state")

    # ── Execution denied gap ───────────────────────────────────
    def test_execution_denied_produces_critical_gap(self):
        ex = self.GrantExecution(
            id="ex-denied-gap",
            action="read",
            resource="doc-1",
            result="denied",
            error_code="no_grant",
            executed_at="2026-05-11T10:00:00Z",
        )
        self.create_execution(ex)
        result = self.build("ex-denied-gap")
        self.assertIsNotNone(result)
        gap_ids = [g["gapId"] for g in result["gaps"]]
        self.assertIn("execution_denied", gap_ids)
        denied_gap = next(g for g in result["gaps"] if g["gapId"] == "execution_denied")
        self.assertEqual(denied_gap["severity"], "critical")
        self.assertEqual(denied_gap["category"], "execution")


if __name__ == "__main__":
    unittest.main(verbosity=2)
