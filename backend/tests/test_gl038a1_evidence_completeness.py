"""GL-038-A1 — Evidence Completeness Scoring Builder tests.

Covers builder location, response minimum fields, scoring logic,
gap detection, include_details flag, secrets safety, and not-found handling.
"""

import os
import sys
import unittest
import tempfile
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestEvidenceCompletenessBuilder(unittest.TestCase):
    """Evidence completeness scoring builder tests."""

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

        from backend.src.evidence.evidence_completeness import build_evidence_completeness_for_execution
        from backend.src.grants.grant_executions import create_grant_execution
        from backend.src.core.models import GrantExecution
        from backend.src.evidence import evidence_persistence as evp
        from backend.src.evidence.evidence_bundle import build_evidence_bundle
        from backend.src.policy.provenance import record_provenance_event
        from backend.src.grants.grants import create_grant
        from backend.src.core.models import Grant

        self.build = build_evidence_completeness_for_execution
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

    def _create_grant(self, grant_id: str):
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
        )
        self.create_grant(grant)

    # ── Module location ─────────────────────────────────────
    def test_builder_lives_in_evidence_completeness_module(self):
        from backend.src.evidence import evidence_completeness as ec
        self.assertTrue(hasattr(ec, "build_evidence_completeness_for_execution"))

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
        result = self.build("ex-min")
        self.assertIsNotNone(result)
        required = {
            "reportType", "reportVersion", "executionId", "grantId",
            "generatedAt", "completenessScore", "completenessStatus",
            "checks", "missingEvidence", "complianceGaps",
            "warnings", "auditReadiness", "evidence", "verification", "provenance",
        }
        self.assertTrue(required.issubset(result.keys()))

    def test_report_type_and_version(self):
        self._make_execution("ex-type")
        result = self.build("ex-type")
        self.assertIsNotNone(result)
        self.assertEqual(result["reportType"], "evidence_completeness")
        self.assertEqual(result["reportVersion"], "gl-038-a1")

    # ── Scoring: high score for complete data ─────────────────
    def test_complete_report_produces_high_score(self):
        self._make_execution("ex-complete", grant_id="g-complete")
        self._create_grant("g-complete")
        self._archive_evidence("ex-complete")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-complete",
            grant_id="g-complete",
        )
        # Trigger verification so status becomes valid
        from backend.src.evidence import evidence_verification as ev_mod
        importlib.reload(ev_mod)
        ev_mod.verify_execution("ex-complete")

        result = self.build("ex-complete")
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result["completenessScore"], 90)
        self.assertEqual(result["completenessStatus"], "complete")
        self.assertEqual(result["auditReadiness"], "ready")
        self.assertEqual(result["complianceGaps"], [])
        self.assertEqual(result["missingEvidence"], [])

    # ── Scoring: missing evidence ────────────────────────────
    def test_missing_evidence_produces_gap(self):
        self._make_execution("ex-no-evidence")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-no-evidence",
        )
        result = self.build("ex-no-evidence")
        self.assertIsNotNone(result)
        self.assertIn("missing_evidence", result["complianceGaps"])
        self.assertIn("evidence_bundle", result["missingEvidence"])
        self.assertLess(result["completenessScore"], 100)

    # ── Scoring: unverified evidence ──────────────────────────
    def test_unverified_evidence_produces_gap(self):
        self._make_execution("ex-unverified", grant_id="g-unverified")
        self._create_grant("g-unverified")
        self._archive_evidence("ex-unverified")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-unverified",
            grant_id="g-unverified",
        )
        # Do NOT trigger verification → status stays None
        result = self.build("ex-unverified")
        self.assertIsNotNone(result)
        self.assertIn("unverified_evidence", result["complianceGaps"])
        self.assertLess(result["completenessScore"], 100)

    # ── Scoring: invalid evidence ──────────────────────────────
    def test_invalid_evidence_produces_gap(self):
        self._make_execution("ex-invalid", grant_id="g-invalid")
        self._create_grant("g-invalid")
        self._archive_evidence("ex-invalid")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-invalid",
            grant_id="g-invalid",
        )
        # Manually set verification status to invalid
        record = self.evp.get_bundle_by_execution("ex-invalid")
        self.assertIsNotNone(record)
        self.evp.update_verification_status(record.id, "invalid")

        result = self.build("ex-invalid")
        self.assertIsNotNone(result)
        self.assertIn("invalid_evidence", result["complianceGaps"])
        self.assertLess(result["completenessScore"], 100)
        self.assertEqual(result["completenessStatus"], "critical")
        self.assertEqual(result["auditReadiness"], "blocked")

    # ── Scoring: missing provenance events ────────────────────
    def test_missing_provenance_events_produces_gap(self):
        self._make_execution("ex-no-prov", grant_id="g-no-prov")
        self._create_grant("g-no-prov")
        self._archive_evidence("ex-no-prov")
        # No provenance events recorded
        result = self.build("ex-no-prov")
        self.assertIsNotNone(result)
        self.assertIn("missing_provenance_events", result["complianceGaps"])
        self.assertIn("provenance_events", result["missingEvidence"])
        self.assertLess(result["completenessScore"], 100)

    # ── include_details=False ──────────────────────────────────
    def test_include_details_false_omits_checks_and_events(self):
        self._make_execution("ex-lite", grant_id="g-lite")
        self._create_grant("g-lite")
        self._archive_evidence("ex-lite")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-lite",
            grant_id="g-lite",
        )
        result = self.build("ex-lite", include_details=False)
        self.assertIsNotNone(result)
        self.assertIn("completenessScore", result)
        self.assertIn("completenessStatus", result)
        self.assertIn("complianceGaps", result)
        self.assertIsNone(result["checks"])
        self.assertIsNone(result["provenance"]["events"])

    # ── Secrets safety ────────────────────────────────────────
    def test_response_does_not_expose_secrets(self):
        self._make_execution("ex-safe", grant_id="g-safe")
        self._create_grant("g-safe")
        self._archive_evidence("ex-safe")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-safe",
            grant_id="g-safe",
        )
        result = self.build("ex-safe")
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
        self.assertNotIn("evidenceBundle", result_str)

    def test_no_raw_metadata_json_from_provenance_events(self):
        self._make_execution("ex-nometa", grant_id="g-nometa")
        self._create_grant("g-nometa")
        self._archive_evidence("ex-nometa")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-nometa",
            grant_id="g-nometa",
        )
        result = self.build("ex-nometa")
        self.assertIsNotNone(result)
        result_str = str(result)
        self.assertNotIn("metadata_json", result_str)
        self.assertNotIn("metadataJson", result_str)

    # ── Grant decision logic unchanged ─────────────────────────
    def test_grant_decision_logic_unchanged(self):
        # Verify that existing grants module still works independently
        from backend.src.grants import grants as g_mod
        importlib.reload(g_mod)
        self._create_grant("g-unchanged")
        grant = g_mod.get_grant("g-unchanged")
        self.assertIsNotNone(grant)
        self.assertEqual(grant.id, "g-unchanged")

    # ── Checks detail structure ────────────────────────────────
    def test_checks_structure_when_include_details_true(self):
        self._make_execution("ex-checks", grant_id="g-checks")
        self._create_grant("g-checks")
        self._archive_evidence("ex-checks")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-checks",
            grant_id="g-checks",
        )
        result = self.build("ex-checks")
        self.assertIsNotNone(result)
        checks = result["checks"]
        self.assertIsNotNone(checks)
        expected_keys = {
            "auditorReportAvailable",
            "executionPresent",
            "evidencePresent",
            "evidenceVerified",
            "evidenceValid",
            "provenanceEventsPresent",
            "criticalGapsPresent",
        }
        self.assertTrue(expected_keys.issubset(checks.keys()))

    # ── Provenance event count ─────────────────────────────────
    def test_provenance_event_count_matches(self):
        self._make_execution("ex-count", grant_id="g-count")
        self._create_grant("g-count")
        self._archive_evidence("ex-count")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-count",
            grant_id="g-count",
        )
        self.record_event(
            event_type="grant_executed",
            actor_type="system",
            actor_id="engine-1",
            action="execute",
            occurred_at="2026-05-11T10:01:00Z",
            execution_id="ex-count",
            grant_id="g-count",
        )
        result = self.build("ex-count")
        self.assertIsNotNone(result)
        self.assertEqual(result["provenance"]["eventCount"], 2)
