"""GL-037-B1 — Decision Provenance Summary Builder tests.

Covers builder location, response shape, minimum fields, chronological
provenance events, flag behaviours (timeline/warnings/raw_evidence),
evidence/verification warnings, not-found handling, and secrets safety.
"""

import os
import sys
import unittest
import tempfile
import importlib
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestDecisionProvenanceSummary(unittest.TestCase):
    """Decision provenance summary builder tests."""

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

        from backend.src.policy.provenance_summary import build_decision_provenance_summary
        from backend.src.policy.provenance import record_provenance_event
        from backend.src.grants.grant_executions import create_grant_execution
        from backend.src.core.models import GrantExecution
        from backend.src.evidence import evidence_persistence as evp
        from backend.src.evidence.evidence_bundle import build_evidence_bundle

        self.build = build_decision_provenance_summary
        self.record_event = record_provenance_event
        self.create_execution = create_grant_execution
        self.GrantExecution = GrantExecution
        self.evp = evp
        self.build_evidence = build_evidence_bundle

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

    # ── Helper ──────────────────────────────────────────────────
    def _make_execution(self, execution_id: str, grant_id: str | None = None):
        ex = self.GrantExecution(
            id=execution_id,
            action="read",
            resource="doc-1",
            grant_id=grant_id,
            result="succeeded",
            executed_at="2026-05-11T10:00:00Z",
        )
        self.create_execution(ex, tenant_id="demo", workspace_id="default")
        return ex

    def _archive_evidence(self, execution_id: str, stored_by: str | None = None):
        bundle = self.build_evidence(execution_id)
        if bundle is None:
            raise RuntimeError("build_evidence_bundle returned None")
        self.evp.store_bundle(execution_id, bundle, stored_by=stored_by)

    # ── Module location ─────────────────────────────────────────
    def test_summary_builder_lives_in_provenance_summary_module(self):
        from backend.src.policy import provenance_summary as ps
        self.assertTrue(hasattr(ps, "build_decision_provenance_summary"))

    def test_provenance_module_keeps_low_level_functions(self):
        from backend.src.policy import provenance as prov
        self.assertTrue(hasattr(prov, "record_provenance_event"))
        self.assertTrue(hasattr(prov, "get_provenance_event"))
        self.assertTrue(hasattr(prov, "list_provenance_events"))
        self.assertFalse(hasattr(prov, "build_decision_provenance_summary"))

    # ── Not found ───────────────────────────────────────────────
    def test_returns_none_for_unknown_execution(self):
        result = self.build("nonexistent-exec-id")
        self.assertIsNone(result)

    # ── Minimum fields ──────────────────────────────────────────
    def test_summary_contains_minimum_fields(self):
        self._make_execution("ex-min", grant_id="g-min")
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
            "executionId", "grantId", "execution", "evidence",
            "verification", "provenanceEvents", "timeline",
            "warnings", "generatedAt",
        }
        self.assertTrue(required.issubset(result.keys()))

    # ── Execution field ─────────────────────────────────────────
    def test_execution_field_safe(self):
        self._make_execution("ex-exec", grant_id="g-exec")
        result = self.build("ex-exec")
        self.assertIsNotNone(result)
        ex = result["execution"]
        self.assertIsNotNone(ex)
        self.assertEqual(ex["id"], "ex-exec")
        self.assertEqual(ex["grantId"], "g-exec")
        self.assertEqual(ex["action"], "read")
        self.assertNotIn("metadataJson", ex)

    # ── Provenance events safe and chronological ──────────────
    def test_provenance_events_safe_and_chronological(self):
        self._make_execution("ex-chrono")
        self.record_event(
            event_type="grant_executed",
            actor_type="agent",
            actor_id="agent-1",
            action="execute",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-chrono",
        )
        self.record_event(
            event_type="evidence_created",
            actor_type="system",
            actor_id="engine-1",
            action="create",
            occurred_at="2026-05-11T11:00:00Z",
            execution_id="ex-chrono",
        )
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T12:00:00Z",
            execution_id="ex-chrono",
        )
        result = self.build("ex-chrono")
        self.assertIsNotNone(result)
        events = result["provenanceEvents"]
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["eventType"], "grant_executed")
        self.assertEqual(events[1]["eventType"], "evidence_created")
        self.assertEqual(events[2]["eventType"], "policy_evaluated")
        # Safe: no internal fields
        for ev in events:
            self.assertNotIn("id", ev)
            self.assertNotIn("createdAt", ev)
            self.assertNotIn("executionId", ev)
            self.assertNotIn("grantId", ev)
            self.assertNotIn("metadataJson", ev)

    # ── Empty provenance events ─────────────────────────────────
    def test_empty_provenance_events_no_exception(self):
        self._make_execution("ex-empty")
        result = self.build("ex-empty")
        self.assertIsNotNone(result)
        self.assertEqual(result["provenanceEvents"], [])
        self.assertEqual(result["timeline"], [])

    # ── include_timeline=False ──────────────────────────────────
    def test_include_timeline_false_returns_empty_timeline(self):
        self._make_execution("ex-notl")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-notl",
        )
        result = self.build("ex-notl", include_timeline=False)
        self.assertIsNotNone(result)
        self.assertEqual(result["timeline"], [])
        self.assertEqual(len(result["provenanceEvents"]), 1)

    # ── include_warnings=False ──────────────────────────────────
    def test_include_warnings_false_returns_empty_warnings(self):
        self._make_execution("ex-nowarn")
        result = self.build("ex-nowarn", include_warnings=False)
        self.assertIsNotNone(result)
        self.assertEqual(result["warnings"], [])

    # ── include_raw_evidence=False ──────────────────────────────
    def test_include_raw_evidence_false_leaks_no_bundle_json(self):
        self._make_execution("ex-noraw")
        self._archive_evidence("ex-noraw")
        result = self.build("ex-noraw", include_raw_evidence=False)
        self.assertIsNotNone(result)
        self.assertTrue(result["evidence"]["present"])
        self.assertNotIn("bundleJson", result["evidence"])

    def test_include_raw_evidence_true_includes_bundle_json(self):
        self._make_execution("ex-raw")
        self._archive_evidence("ex-raw")
        result = self.build("ex-raw", include_raw_evidence=True)
        self.assertIsNotNone(result)
        self.assertTrue(result["evidence"]["present"])
        self.assertIn("bundleJson", result["evidence"])
        self.assertIsInstance(result["evidence"]["bundleJson"], str)

    # ── Missing evidence warning ────────────────────────────────
    def test_missing_evidence_warning(self):
        self._make_execution("ex-missing-ev")
        result = self.build("ex-missing-ev")
        self.assertIsNotNone(result)
        self.assertFalse(result["evidence"]["present"])
        self.assertIn("missing_evidence", result["warnings"])

    def test_missing_evidence_warning_suppressed_when_flag_false(self):
        self._make_execution("ex-missing-ev2")
        result = self.build("ex-missing-ev2", include_warnings=False)
        self.assertIsNotNone(result)
        self.assertFalse(result["evidence"]["present"])
        self.assertNotIn("missing_evidence", result["warnings"])

    # ── Unverified evidence warning ─────────────────────────────
    def test_unverified_evidence_warning(self):
        self._make_execution("ex-unver")
        self._archive_evidence("ex-unver")
        result = self.build("ex-unver")
        self.assertIsNotNone(result)
        self.assertTrue(result["evidence"]["present"])
        self.assertIn("unverified_evidence", result["warnings"])

    def test_no_warning_when_evidence_valid(self):
        self._make_execution("ex-valid")
        self._archive_evidence("ex-valid")
        record = self.evp.get_bundle_by_execution("ex-valid")
        self.assertIsNotNone(record)
        self.evp.update_verification_status(record.id, "valid")
        result = self.build("ex-valid")
        self.assertIsNotNone(result)
        self.assertTrue(result["evidence"]["present"])
        self.assertNotIn("unverified_evidence", result["warnings"])
        self.assertNotIn("missing_evidence", result["warnings"])

    # ── Grant ID inference ──────────────────────────────────────
    def test_grant_id_from_execution(self):
        self._make_execution("ex-g1", grant_id="g-from-ex")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-g1",
        )
        result = self.build("ex-g1")
        self.assertEqual(result["grantId"], "g-from-ex")

    def test_grant_id_from_event_when_execution_missing(self):
        self.record_event(
            event_type="grant_executed",
            actor_type="agent",
            actor_id="agent-1",
            action="execute",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-g2",
            grant_id="g-from-ev",
        )
        result = self.build("ex-g2")
        self.assertIsNotNone(result)
        self.assertEqual(result["grantId"], "g-from-ev")

    # ── Verification section ────────────────────────────────────
    def test_verification_null_when_no_evidence(self):
        self._make_execution("ex-nover")
        result = self.build("ex-nover")
        self.assertIsNotNone(result)
        self.assertIsNone(result["verification"]["status"])
        self.assertIsNone(result["verification"]["verifiedAt"])

    def test_verification_reflects_archive_status(self):
        self._make_execution("ex-ver")
        self._archive_evidence("ex-ver")
        record = self.evp.get_bundle_by_execution("ex-ver")
        self.assertIsNotNone(record)
        self.evp.update_verification_status(record.id, "invalid")
        result = self.build("ex-ver")
        self.assertIsNotNone(result)
        self.assertEqual(result["verification"]["status"], "invalid")
        self.assertIsNotNone(result["verification"]["verifiedAt"])

    # ── Secrets safety ──────────────────────────────────────────
    def test_summary_does_not_expose_secrets(self):
        self._make_execution("ex-sec")
        self._archive_evidence("ex-sec")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-sec",
        )
        result = self.build("ex-sec", include_raw_evidence=True)
        self.assertIsNotNone(result)
        raw = json.dumps(result)
        # Ensure no secrets leak into the summary
        for forbidden in ["GRANTLAYER_ADMIN_TOKEN", "password", "secret", "token", "private"]:
            self.assertNotIn(forbidden, raw.lower())

    # ── generatedAt ─────────────────────────────────────────────
    def test_generated_at_present(self):
        self._make_execution("ex-gen")
        result = self.build("ex-gen")
        self.assertIsNotNone(result)
        self.assertIn("generatedAt", result)
        self.assertRegex(result["generatedAt"], r"^\d{4}-\d{2}-\d{2}T")

    # ── Evidence hash present when archived ─────────────────────
    def test_evidence_hash_present_when_archived(self):
        self._make_execution("ex-hash")
        self._archive_evidence("ex-hash")
        result = self.build("ex-hash")
        self.assertIsNotNone(result)
        self.assertTrue(result["evidence"]["present"])
        self.assertIsNotNone(result["evidence"]["hash"])
        self.assertEqual(len(result["evidence"]["hash"]), 64)

    def test_evidence_hash_none_when_not_archived(self):
        self._make_execution("ex-nohash")
        result = self.build("ex-nohash")
        self.assertIsNotNone(result)
        self.assertFalse(result["evidence"]["present"])
        self.assertIsNone(result["evidence"]["hash"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
