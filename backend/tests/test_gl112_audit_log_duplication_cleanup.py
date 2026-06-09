"""Tests for GL-112: Audit Log Duplication Cleanup.

Verifies that the five new internal helpers introduced in GL-112 behave
correctly, and that the public functions verify_audit_hash_chain() and
build_audit_chain_verification_report() produce identical results after
the refactor.

Scope guard: no migration, no endpoint, no OpenAPI change.
"""

import json
import os
import pathlib
import sys
import tempfile
import unittest
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl112(unittest.TestCase):
    """Shared setUp/tearDown for GL-112 tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"

        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")
        self._orig_enable_demo = os.environ.get("GRANTLAYER_ENABLE_DEMO_ENDPOINTS")

        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import src.models as models_mod
        importlib.reload(models_mod)
        self.models_mod = models_mod

        import src.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, orig in [
            ("GRANTLAYER_DB", self._orig_db),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", self._orig_bootstrap_token),
            ("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", self._orig_enable_demo),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    def _append_audit_event(self, event_id, action="test_action", approved=True, reason="test reason"):
        event = self.models_mod.AuditEvent(
            id=event_id,
            timestamp="2026-01-01T00:00:00Z",
            subject_id="test-subject",
            role="tester",
            action=action,
            resource="test-resource",
            approved=approved,
            reason=reason,
            matched_grant_id=None,
            challenge_id=None,
            challenge_present=False,
            challenge_result="legacy_mode",
            grant_signature_result="not_checked",
        )
        self.audit_mod.append_event(event)
        return event

    def _insert_raw_row(self, event_id, row_hash, prev_hash=None):
        """Insert a raw row with arbitrary hash values, bypassing append_event."""
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO audit_events
                   (id, timestamp, subject_id, role, action, resource, approved,
                    reason, matched_grant_id, challenge_id, challenge_present,
                    challenge_result, grant_signature_result, row_hash, prev_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event_id, "2026-01-01T00:00:00Z", "s", "r", "a", "res", 1,
                 "r", None, None, 0, "legacy_mode", "not_checked", row_hash, prev_hash),
            )
            conn.commit()
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════
# 1. _fetch_all_audit_events_ordered
# ═══════════════════════════════════════════════════════════════════════

class TestGl112FetchAllAuditEventsOrdered(_BaseGl112):
    """_fetch_all_audit_events_ordered returns rows in deterministic ASC order."""

    def test_empty_db_returns_empty_list(self):
        rows = self.audit_mod._fetch_all_audit_events_ordered()
        self.assertEqual(rows, [])

    def test_returns_all_inserted_rows(self):
        self._append_audit_event("evt-f1")
        self._append_audit_event("evt-f2")
        self._append_audit_event("evt-f3")
        rows = self.audit_mod._fetch_all_audit_events_ordered()
        self.assertEqual(len(rows), 3)

    def test_rows_are_dicts_with_required_keys(self):
        self._append_audit_event("evt-f4")
        rows = self.audit_mod._fetch_all_audit_events_ordered()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        for key in ("id", "timestamp", "row_hash", "prev_hash"):
            self.assertIn(key, row)

    def test_order_is_oldest_first(self):
        # Events inserted in sequence; oldest must appear first
        self._append_audit_event("evt-order-1")
        self._append_audit_event("evt-order-2")
        rows = self.audit_mod._fetch_all_audit_events_ordered()
        self.assertEqual(rows[0]["id"], "evt-order-1")
        self.assertEqual(rows[1]["id"], "evt-order-2")


# ═══════════════════════════════════════════════════════════════════════
# 2. _filter_chain_rows
# ═══════════════════════════════════════════════════════════════════════

class TestGl112FilterChainRows(_BaseGl112):
    """_filter_chain_rows keeps only rows where row_hash is not None."""

    def test_empty_list_returns_empty(self):
        result = self.audit_mod._filter_chain_rows([])
        self.assertEqual(result, [])

    def test_all_non_null_rows_pass_through(self):
        rows = [
            {"id": "a", "row_hash": "abc"},
            {"id": "b", "row_hash": "def"},
        ]
        result = self.audit_mod._filter_chain_rows(rows)
        self.assertEqual(len(result), 2)

    def test_null_row_hash_rows_filtered_out(self):
        rows = [
            {"id": "a", "row_hash": None},
            {"id": "b", "row_hash": "abc"},
            {"id": "c", "row_hash": None},
        ]
        result = self.audit_mod._filter_chain_rows(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "b")

    def test_all_null_returns_empty(self):
        rows = [{"id": "a", "row_hash": None}, {"id": "b", "row_hash": None}]
        result = self.audit_mod._filter_chain_rows(rows)
        self.assertEqual(result, [])

    def test_integration_with_fetch(self):
        # Insert one normal event and one raw NULL-hash historical row
        self._append_audit_event("evt-filt-chain")
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO audit_events
                   (id, timestamp, subject_id, role, action, resource, approved,
                    reason, matched_grant_id, challenge_id, challenge_present,
                    challenge_result, grant_signature_result, row_hash, prev_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("evt-historical", "2025-01-01T00:00:00Z", "s", "r", "a", "res", 1,
                 "r", None, None, 0, "legacy_mode", "not_checked", None, None),
            )
            conn.commit()
        finally:
            conn.close()

        rows = self.audit_mod._fetch_all_audit_events_ordered()
        chain_rows = self.audit_mod._filter_chain_rows(rows)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(chain_rows), 1)
        self.assertEqual(chain_rows[0]["id"], "evt-filt-chain")


# ═══════════════════════════════════════════════════════════════════════
# 3. _verify_single_event
# ═══════════════════════════════════════════════════════════════════════

class TestGl112VerifySingleEvent(_BaseGl112):
    """_verify_single_event returns empty list when valid, failure dicts when not."""

    def _build_event_from_row(self, row_dict):
        return self.audit_mod._row_to_audit_event(row_dict)

    def test_valid_genesis_event_returns_no_failures(self):
        # Insert genesis event via append_event so hashes are correct
        self._append_audit_event("evt-gen-ok")
        rows = self.audit_mod._fetch_all_audit_events_ordered()
        event = self.audit_mod._row_to_audit_event(rows[0])
        # Genesis: expected_prev_hash is None
        failures = self.audit_mod._verify_single_event(event, None, 0)
        self.assertEqual(failures, [])

    def test_valid_chained_event_returns_no_failures(self):
        self._append_audit_event("evt-chain-a")
        self._append_audit_event("evt-chain-b")
        rows = self.audit_mod._fetch_all_audit_events_ordered()
        event_b = self.audit_mod._row_to_audit_event(rows[1])
        expected_prev_hash = rows[0]["row_hash"]
        failures = self.audit_mod._verify_single_event(event_b, expected_prev_hash, 1)
        self.assertEqual(failures, [])

    def test_bad_row_hash_produces_row_hash_mismatch_failure(self):
        self._append_audit_event("evt-bad-rh")
        rows = self.audit_mod._fetch_all_audit_events_ordered()
        event = self.audit_mod._row_to_audit_event(rows[0])
        # Corrupt the stored row_hash
        event.row_hash = "badhash"
        failures = self.audit_mod._verify_single_event(event, None, 0)
        self.assertEqual(len(failures), 1)
        self.assertIn("row_hash mismatch", failures[0]["reason"])

    def test_bad_prev_hash_produces_prev_hash_mismatch_failure(self):
        self._append_audit_event("evt-bad-ph-a")
        self._append_audit_event("evt-bad-ph-b")
        rows = self.audit_mod._fetch_all_audit_events_ordered()
        event_b = self.audit_mod._row_to_audit_event(rows[1])
        # Pass wrong expected_prev_hash
        failures = self.audit_mod._verify_single_event(event_b, "wrongprevhash", 1)
        reasons = [f["reason"] for f in failures]
        self.assertTrue(any("prev_hash mismatch" in r for r in reasons))

    def test_both_bad_produces_two_failures(self):
        self._append_audit_event("evt-both-bad")
        rows = self.audit_mod._fetch_all_audit_events_ordered()
        event = self.audit_mod._row_to_audit_event(rows[0])
        event.row_hash = "badhash"
        # Pass wrong prev_hash (should be None for genesis)
        failures = self.audit_mod._verify_single_event(event, "wrongprev", 0)
        self.assertEqual(len(failures), 2)

    def test_failure_dict_contains_event_id_index_reason(self):
        self._append_audit_event("evt-fields")
        rows = self.audit_mod._fetch_all_audit_events_ordered()
        event = self.audit_mod._row_to_audit_event(rows[0])
        event.row_hash = "badhash"
        failures = self.audit_mod._verify_single_event(event, None, 7)
        self.assertTrue(len(failures) > 0)
        for f in failures:
            self.assertIn("event_id", f)
            self.assertIn("index", f)
            self.assertIn("reason", f)
            self.assertEqual(f["index"], 7)
            self.assertEqual(f["event_id"], "evt-fields")


# ═══════════════════════════════════════════════════════════════════════
# 4. _build_report_summary
# ═══════════════════════════════════════════════════════════════════════

class TestGl112BuildReportSummary(_BaseGl112):
    """_build_report_summary produces correct summary string and status."""

    def _summary(self, valid, checked, skipped, failure_count):
        return self.audit_mod._build_report_summary(valid, checked, skipped, failure_count)

    def test_empty_log_gives_empty_status(self):
        summary, status = self._summary(True, 0, 0, 0)
        self.assertEqual(status, "empty")
        self.assertIn("empty", summary.lower())

    def test_historical_only_gives_historical_only_status(self):
        summary, status = self._summary(True, 0, 2, 0)
        self.assertEqual(status, "historical_only")
        self.assertIn("2", summary)

    def test_valid_chain_gives_valid_status(self):
        summary, status = self._summary(True, 3, 0, 0)
        self.assertEqual(status, "valid")
        self.assertIn("3", summary)

    def test_valid_chain_with_skipped_gives_valid_status_with_counts(self):
        summary, status = self._summary(True, 3, 1, 0)
        self.assertEqual(status, "valid")
        self.assertIn("3", summary)
        self.assertIn("1", summary)

    def test_invalid_chain_gives_invalid_status_with_failure_count(self):
        summary, status = self._summary(False, 2, 0, 1)
        self.assertEqual(status, "invalid")
        self.assertIn("1", summary)
        self.assertIn("2", summary)

    def test_returns_two_element_tuple(self):
        result = self._summary(True, 1, 0, 0)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], str)
        self.assertIsInstance(result[1], str)


# ═══════════════════════════════════════════════════════════════════════
# 5. _build_report_recommendations
# ═══════════════════════════════════════════════════════════════════════

class TestGl112BuildReportRecommendations(_BaseGl112):
    """_build_report_recommendations returns deterministic list of strings."""

    def _recs(self, valid, checked, failures):
        return self.audit_mod._build_report_recommendations(valid, checked, failures)

    def test_valid_chain_recommends_no_action(self):
        recs = self._recs(True, 3, [])
        self.assertEqual(len(recs), 1)
        self.assertIn("No action required", recs[0])

    def test_empty_valid_chain_recommends_no_action(self):
        recs = self._recs(True, 0, [])
        self.assertEqual(len(recs), 1)
        self.assertIn("No action required", recs[0])

    def test_row_hash_mismatch_recommends_investigation(self):
        failures = [{"event_id": "e1", "index": 0, "reason": "row_hash mismatch: stored=x expected=y"}]
        recs = self._recs(False, 1, failures)
        self.assertTrue(any("row_hash mismatches" in r for r in recs))

    def test_prev_hash_mismatch_recommends_investigation(self):
        failures = [{"event_id": "e1", "index": 0, "reason": "prev_hash mismatch: stored=x expected=y"}]
        recs = self._recs(False, 1, failures)
        self.assertTrue(any("prev_hash mismatches" in r for r in recs))

    def test_both_mismatches_produce_two_recommendations(self):
        failures = [
            {"event_id": "e1", "index": 0, "reason": "row_hash mismatch: stored=x expected=y"},
            {"event_id": "e1", "index": 0, "reason": "prev_hash mismatch: stored=a expected=b"},
        ]
        recs = self._recs(False, 1, failures)
        self.assertEqual(len(recs), 2)

    def test_fallback_generic_recommendation(self):
        # Failure with neither "row_hash mismatch" nor "prev_hash mismatch" in reason
        failures = [{"event_id": "e1", "index": 0, "reason": "some other problem"}]
        recs = self._recs(False, 1, failures)
        self.assertEqual(len(recs), 1)
        self.assertIn("anomalies", recs[0])

    def test_returns_list_of_strings(self):
        recs = self._recs(True, 1, [])
        self.assertIsInstance(recs, list)
        for r in recs:
            self.assertIsInstance(r, str)


# ═══════════════════════════════════════════════════════════════════════
# 6. verify_audit_hash_chain equivalence (regression guard)
# ═══════════════════════════════════════════════════════════════════════

class TestGl112VerifyHashChainEquivalence(_BaseGl112):
    """Refactored verify_audit_hash_chain() is functionally identical to pre-refactor."""

    def test_clean_chain_verifies_valid(self):
        self._append_audit_event("evt-eq-1")
        self._append_audit_event("evt-eq-2")
        self._append_audit_event("evt-eq-3")
        result = self.audit_mod.verify_audit_hash_chain()
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked"], 3)
        self.assertEqual(result["failures"], [])

    def test_bad_row_hash_produces_invalid_result(self):
        self._insert_raw_row("evt-eq-bad", row_hash="badhash", prev_hash=None)
        result = self.audit_mod.verify_audit_hash_chain()
        self.assertFalse(result["valid"])
        self.assertEqual(len(result["failures"]), 1)
        self.assertIn("row_hash mismatch", result["failures"][0]["reason"])

    def test_result_shape_is_unchanged(self):
        result = self.audit_mod.verify_audit_hash_chain()
        self.assertIn("valid", result)
        self.assertIn("checked", result)
        self.assertIn("failures", result)
        self.assertIsInstance(result["valid"], bool)
        self.assertIsInstance(result["checked"], int)
        self.assertIsInstance(result["failures"], list)

    def test_historical_null_rows_skipped(self):
        # Insert a pre-chain NULL row then a valid chain event
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO audit_events
                   (id, timestamp, subject_id, role, action, resource, approved,
                    reason, matched_grant_id, challenge_id, challenge_present,
                    challenge_result, grant_signature_result, row_hash, prev_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("evt-hist-null", "2025-01-01T00:00:00Z", "s", "r", "a", "res", 1,
                 "r", None, None, 0, "legacy_mode", "not_checked", None, None),
            )
            conn.commit()
        finally:
            conn.close()
        self._append_audit_event("evt-after-hist")
        result = self.audit_mod.verify_audit_hash_chain()
        self.assertTrue(result["valid"])
        # Only the chain row (not the NULL historical row) is checked
        self.assertEqual(result["checked"], 1)

    def test_missing_row_hash_row_does_not_count_in_checked(self):
        # A row with row_hash=None is excluded from chain verification
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO audit_events
                   (id, timestamp, subject_id, role, action, resource, approved,
                    reason, matched_grant_id, challenge_id, challenge_present,
                    challenge_result, grant_signature_result, row_hash, prev_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("evt-no-hash", "2026-06-01T00:00:00Z", "s", "r", "a", "res", 1,
                 "r", None, None, 0, "legacy_mode", "not_checked", None, None),
            )
            conn.commit()
        finally:
            conn.close()
        result = self.audit_mod.verify_audit_hash_chain()
        self.assertEqual(result["checked"], 0)
        self.assertTrue(result["valid"])


# ═══════════════════════════════════════════════════════════════════════
# 7. build_audit_chain_verification_report equivalence (regression guard)
# ═══════════════════════════════════════════════════════════════════════

class TestGl112BuildReportEquivalence(_BaseGl112):
    """Refactored build_audit_chain_verification_report() preserves all fields."""

    def test_report_has_all_required_keys(self):
        self._append_audit_event("evt-rep-1")
        report = self.audit_mod.build_audit_chain_verification_report()
        for key in ("report_type", "valid", "checked_events", "failure_count",
                    "failures", "summary", "status", "recommendations"):
            self.assertIn(key, report)

    def test_report_type_is_audit_chain_verification(self):
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertEqual(report["report_type"], "audit_chain_verification")

    def test_valid_agrees_with_verify_helper(self):
        self._append_audit_event("evt-agree-1")
        verify_result = self.audit_mod.verify_audit_hash_chain()
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertEqual(report["valid"], verify_result["valid"])

    def test_checked_events_agrees_with_verify_helper(self):
        self._append_audit_event("evt-agree-2")
        self._append_audit_event("evt-agree-3")
        verify_result = self.audit_mod.verify_audit_hash_chain()
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertEqual(report["checked_events"], verify_result["checked"])

    def test_failure_count_matches_failures_list(self):
        self._append_audit_event("evt-fc-1")
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertEqual(report["failure_count"], len(report["failures"]))

    def test_historical_only_status_when_all_null(self):
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO audit_events
                   (id, timestamp, subject_id, role, action, resource, approved,
                    reason, matched_grant_id, challenge_id, challenge_present,
                    challenge_result, grant_signature_result, row_hash, prev_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("evt-hist-only", "2025-01-01T00:00:00Z", "s", "r", "a", "res", 1,
                 "r", None, None, 0, "legacy_mode", "not_checked", None, None),
            )
            conn.commit()
        finally:
            conn.close()
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertEqual(report["status"], "historical_only")
        self.assertEqual(report["checked_events"], 0)

    def test_valid_status_with_clean_chain(self):
        self._append_audit_event("evt-valid-rep")
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertEqual(report["status"], "valid")
        self.assertTrue(report["valid"])

    def test_empty_log_status(self):
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertEqual(report["status"], "empty")
        self.assertTrue(report["valid"])

    def test_recommendations_is_list_of_strings(self):
        self._append_audit_event("evt-recs")
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertIsInstance(report["recommendations"], list)
        for r in report["recommendations"]:
            self.assertIsInstance(r, str)

    def test_clean_chain_with_historical_row_shows_valid_summary(self):
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO audit_events
                   (id, timestamp, subject_id, role, action, resource, approved,
                    reason, matched_grant_id, challenge_id, challenge_present,
                    challenge_result, grant_signature_result, row_hash, prev_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("evt-hist-mixed", "2025-01-01T00:00:00Z", "s", "r", "a", "res", 1,
                 "r", None, None, 0, "legacy_mode", "not_checked", None, None),
            )
            conn.commit()
        finally:
            conn.close()
        self._append_audit_event("evt-chain-after-hist")
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertEqual(report["status"], "valid")
        # Historical/pre-chain row should be reflected in summary
        self.assertIn("skipped", report["summary"].lower())


# ═══════════════════════════════════════════════════════════════════════
# 8. Audit INSERT / SELECT preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl112AuditInsertSelectPreserved(_BaseGl112):
    """append_event and list_events are unaffected by the refactor."""

    def test_append_event_assigns_row_hash(self):
        event = self._append_audit_event("evt-ins-1")
        self.assertIsNotNone(event.row_hash)
        self.assertEqual(len(event.row_hash), 64)

    def test_append_event_genesis_prev_hash_is_none(self):
        event = self._append_audit_event("evt-ins-gen")
        self.assertIsNone(event.prev_hash)

    def test_append_event_chaining_sets_prev_hash(self):
        ev1 = self._append_audit_event("evt-ch-1")
        ev2 = self._append_audit_event("evt-ch-2")
        self.assertEqual(ev2.prev_hash, ev1.row_hash)

    def test_list_events_returns_inserted_events(self):
        self._append_audit_event("evt-list-1")
        self._append_audit_event("evt-list-2")
        events = self.audit_mod.list_events()
        ids = [e.id for e in events]
        self.assertIn("evt-list-1", ids)
        self.assertIn("evt-list-2", ids)

    def test_get_event_returns_correct_event(self):
        self._append_audit_event("evt-get-1")
        fetched = self.audit_mod.get_event("evt-get-1")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, "evt-get-1")

    def test_no_historical_rows_rewritten(self):
        # Insert a NULL-hash historical row; verify it is still NULL after chain ops
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO audit_events
                   (id, timestamp, subject_id, role, action, resource, approved,
                    reason, matched_grant_id, challenge_id, challenge_present,
                    challenge_result, grant_signature_result, row_hash, prev_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("evt-preserve-hist", "2020-01-01T00:00:00Z", "s", "r", "a", "res", 1,
                 "r", None, None, 0, "legacy_mode", "not_checked", None, None),
            )
            conn.commit()
        finally:
            conn.close()
        # Run verification — it must not rewrite historical row
        self.audit_mod.verify_audit_hash_chain()
        self.audit_mod.build_audit_chain_verification_report()
        row = self.audit_mod.get_event("evt-preserve-hist")
        self.assertIsNone(row.row_hash)


# ═══════════════════════════════════════════════════════════════════════
# 9. Scope guard
# ═══════════════════════════════════════════════════════════════════════

@unittest.skipIf(os.environ.get('CI') == 'true', "Scope-guard test skipped in CI environment")
class TestGl112ScopeGuard(unittest.TestCase):
    """No migration, no new endpoint, no OpenAPI change."""

    def test_migration_count_unchanged(self):
        migrations_dir = pathlib.Path(__file__).parent.parent / "src" / "migrations"
        scripts = sorted(migrations_dir.glob("0*.py"))
        self.assertEqual(len(scripts), 11, f"Expected 11 migration scripts, got {len(scripts)}: {scripts}")

    def test_no_audit_chain_endpoint_in_openapi(self):
        openapi_path = pathlib.Path(__file__).parent.parent.parent / "docs" / "openapi.yaml"
        content = openapi_path.read_text()
        # GL-112 must not add any new audit-chain verification paths
        self.assertNotIn("/audit/verify", content)
        self.assertNotIn("/audit/chain", content)
        self.assertNotIn("/audit-chain", content)


if __name__ == "__main__":
    unittest.main()
