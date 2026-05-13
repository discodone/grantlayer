"""GL-037-C1 — Minimal Auditor Report Builder tests.

Covers builder location, not-found handling, report envelope fields,
grant and grant-request linkage, findings derivation, conclusion logic,
chronological provenance events preservation, and secrets safety.
"""

import os
import sys
import unittest
import tempfile
import importlib
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestAuditorReportBuilder(unittest.TestCase):
    """Minimal auditor report builder tests."""

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

        from src.auditor_report import build_auditor_report_for_execution
        from src.provenance_summary import build_decision_provenance_summary
        from src.provenance import record_provenance_event
        from src.grant_executions import create_grant_execution
        from src.models import GrantExecution, Grant, GrantRequest
        from src.grants import create_grant
        from src.grant_requests import create_grant_request
        from src import evidence_persistence as evp
        from src.evidence_bundle import build_evidence_bundle

        self.build = build_auditor_report_for_execution
        self.build_summary = build_decision_provenance_summary
        self.record_event = record_provenance_event
        self.create_execution = create_grant_execution
        self.GrantExecution = GrantExecution
        self.Grant = Grant
        self.GrantRequest = GrantRequest
        self.create_grant = create_grant
        self.create_grant_request = create_grant_request
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

    # ── Module location ─────────────────────────────────────
    def test_auditor_report_builder_lives_in_auditor_report_module(self):
        from src import auditor_report as ar
        self.assertTrue(hasattr(ar, "build_auditor_report_for_execution"))

    def test_compat_wrapper_build_auditor_report_still_exists(self):
        from src import auditor_report as ar
        self.assertTrue(hasattr(ar, "build_auditor_report"))

    def test_provenance_summary_module_unchanged(self):
        from src import provenance_summary as ps
        self.assertTrue(hasattr(ps, "build_decision_provenance_summary"))
        self.assertFalse(hasattr(ps, "build_auditor_report"))

    # ── Not found ─────────────────────────────────────────────
    def test_returns_none_for_unknown_execution(self):
        result = self.build("nonexistent-exec-id")
        self.assertIsNone(result)

    # ── Report envelope ──────────────────────────────────────
    def test_report_contains_minimum_fields(self):
        self._make_execution("ex-env", grant_id="g-env")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-env",
            grant_id="g-env",
        )
        result = self.build("ex-env")
        self.assertIsNotNone(result)
        required = {
            "reportId", "reportType", "scope", "generatedAt",
            "findings", "conclusion", "provenanceSummary",
            "grant", "grantRequest",
        }
        self.assertTrue(required.issubset(result.keys()))

    def test_report_type_is_auditor_report(self):
        self._make_execution("ex-type")
        result = self.build("ex-type")
        self.assertIsNotNone(result)
        self.assertEqual(result["reportType"], "auditor_report")

    def test_scope_contains_execution_and_grant_id(self):
        self._make_execution("ex-scope", grant_id="g-scope")
        result = self.build("ex-scope")
        self.assertIsNotNone(result)
        self.assertEqual(result["scope"]["executionId"], "ex-scope")
        self.assertEqual(result["scope"]["grantId"], "g-scope")

    def test_generated_at_present(self):
        self._make_execution("ex-gen")
        result = self.build("ex-gen")
        self.assertIsNotNone(result)
        self.assertIn("generatedAt", result)
        self.assertRegex(result["generatedAt"], r"^\d{4}-\d{2}-\d{2}T")

    # ── Grant linkage ────────────────────────────────────────
    def test_grant_section_present_when_grant_exists(self):
        grant = self.Grant(
            id="g-link",
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
        self._make_execution("ex-grant", grant_id="g-link")
        result = self.build("ex-grant")
        self.assertIsNotNone(result)
        self.assertIsNotNone(result["grant"])
        self.assertEqual(result["grant"]["id"], "g-link")
        self.assertEqual(result["grant"]["subjectId"], "sub-1")
        self.assertTrue(result["grant"]["signaturePresent"])
        # Secrets safety: signature raw bytes should not leak
        self.assertNotIn("signature", result["grant"])

    def test_grant_section_none_when_grant_missing(self):
        self._make_execution("ex-nogrant", grant_id="g-missing")
        result = self.build("ex-nogrant")
        self.assertIsNotNone(result)
        self.assertIsNone(result["grant"])

    # ── GrantRequest linkage ─────────────────────────────────
    def test_grant_request_section_present_when_request_exists(self):
        grant = self.Grant(
            id="g-req",
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
        req = self.GrantRequest(
            id="req-1",
            subject_id="sub-1",
            role="tech",
            action="read",
            resource="doc-1",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2026-12-31T23:59:59Z",
            requested_by="requester",
            reason="Need access",
            status="approved",
            approved_by="approver",
            approved_at="2026-01-01T10:00:00Z",
            grant_id="g-req",
        )
        self.create_grant_request(req)
        from src.db import execute
        execute(
            "UPDATE grant_requests SET grant_id = ? WHERE id = ?",
            ("g-req", "req-1"),
        )
        self._make_execution("ex-req", grant_id="g-req")
        result = self.build("ex-req")
        self.assertIsNotNone(result)
        self.assertIsNotNone(result["grantRequest"])
        self.assertEqual(result["grantRequest"]["id"], "req-1")
        self.assertEqual(result["grantRequest"]["status"], "approved")

    def test_grant_request_section_none_when_request_missing(self):
        grant = self.Grant(
            id="g-noreq",
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
        self._make_execution("ex-noreq", grant_id="g-noreq")
        result = self.build("ex-noreq")
        self.assertIsNotNone(result)
        self.assertIsNone(result["grantRequest"])

    # ── Findings ─────────────────────────────────────────────
    def test_finding_missing_evidence(self):
        self._make_execution("ex-find-missing")
        result = self.build("ex-find-missing")
        self.assertIsNotNone(result)
        self.assertIn("missing_evidence", " ".join(result["findings"]))
        self.assertEqual(result["conclusion"], "attention_required")

    def test_finding_unverified_evidence(self):
        self._make_execution("ex-find-unver")
        self._archive_evidence("ex-find-unver")
        result = self.build("ex-find-unver")
        self.assertIsNotNone(result)
        self.assertIn("unverified_evidence", " ".join(result["findings"]))
        self.assertEqual(result["conclusion"], "attention_required")

    def test_no_finding_when_evidence_valid(self):
        self._make_execution("ex-find-valid")
        self._archive_evidence("ex-find-valid")
        record = self.evp.get_bundle_by_execution("ex-find-valid")
        self.assertIsNotNone(record)
        self.evp.update_verification_status(record.id, "valid")
        result = self.build("ex-find-valid")
        self.assertIsNotNone(result)
        self.assertNotIn("unverified_evidence", " ".join(result["findings"]))
        self.assertNotIn("missing_evidence", " ".join(result["findings"]))
        # If there are other findings (e.g. grant missing) conclusion may differ,
        # but for a bare execution with no grant the grant is None so no extra findings.
        self.assertEqual(result["conclusion"], "clean")

    def test_finding_execution_denied(self):
        ex = self.GrantExecution(
            id="ex-denied",
            action="read",
            resource="doc-1",
            result="denied",
            error_code="no_grant",
            executed_at="2026-05-11T10:00:00Z",
        )
        self.create_execution(ex)
        result = self.build("ex-denied")
        self.assertIsNotNone(result)
        self.assertIn("execution_denied", " ".join(result["findings"]))
        self.assertIn("no_grant", " ".join(result["findings"]))
        self.assertEqual(result["conclusion"], "attention_required")

    def test_finding_grant_revoked(self):
        grant = self.Grant(
            id="g-revoked",
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
        revoke_grant("g-revoked", "admin", "Emergency")
        self._make_execution("ex-revoked", grant_id="g-revoked")
        result = self.build("ex-revoked")
        self.assertIsNotNone(result)
        self.assertIn("grant_revoked", " ".join(result["findings"]))
        self.assertEqual(result["conclusion"], "attention_required")

    def test_finding_grant_unsigned(self):
        grant = self.Grant(
            id="g-unsigned",
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
            ("g-unsigned",),
        )
        self._make_execution("ex-unsigned", grant_id="g-unsigned")
        result = self.build("ex-unsigned")
        self.assertIsNotNone(result)
        self.assertIn("grant_unsigned", " ".join(result["findings"]))
        self.assertEqual(result["conclusion"], "attention_required")

    def test_finding_request_denied(self):
        grant = self.Grant(
            id="g-reqdeny",
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
        req = self.GrantRequest(
            id="req-deny",
            subject_id="sub-1",
            role="tech",
            action="read",
            resource="doc-1",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2026-12-31T23:59:59Z",
            requested_by="requester",
            reason="Need access",
            status="denied",
            denied_by="denier",
            denied_at="2026-01-01T10:00:00Z",
            denial_reason="Not approved",
            grant_id="g-reqdeny",
        )
        self.create_grant_request(req)
        from src.db import execute
        execute(
            "UPDATE grant_requests SET grant_id = ? WHERE id = ?",
            ("g-reqdeny", "req-deny"),
        )
        self._make_execution("ex-reqdeny", grant_id="g-reqdeny")
        result = self.build("ex-reqdeny")
        self.assertIsNotNone(result)
        self.assertIn("grant_request_denied", " ".join(result["findings"]))
        self.assertEqual(result["conclusion"], "attention_required")

    # ── Provenance summary preserved ──────────────────────────
    def test_provenance_summary_embedded(self):
        self._make_execution("ex-embed")
        self.record_event(
            event_type="policy_evaluated",
            actor_type="system",
            actor_id="engine-1",
            action="evaluate",
            occurred_at="2026-05-11T10:00:00Z",
            execution_id="ex-embed",
        )
        result = self.build("ex-embed")
        self.assertIsNotNone(result)
        summary = result["provenanceSummary"]
        self.assertIsNotNone(summary)
        self.assertEqual(summary["executionId"], "ex-embed")
        self.assertEqual(len(summary["provenanceEvents"]), 1)
        self.assertEqual(summary["provenanceEvents"][0]["eventType"], "policy_evaluated")

    # ── Secrets safety ────────────────────────────────────────
    def test_report_does_not_expose_secrets(self):
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
        result = self.build("ex-sec")
        self.assertIsNotNone(result)
        raw = json.dumps(result)
        for forbidden in ["GRANTLAYER_ADMIN_TOKEN", "password", "secret", "token", "private"]:
            self.assertNotIn(forbidden, raw.lower(), f"Secret leak detected: {forbidden}")

    # ── Raw evidence flag ─────────────────────────────────────
    def test_include_raw_evidence_false_omits_bundle(self):
        self._make_execution("ex-raw-off")
        self._archive_evidence("ex-raw-off")
        result = self.build("ex-raw-off", include_raw_evidence=False)
        self.assertIsNotNone(result)
        self.assertNotIn("evidenceBundle", result)

    def test_include_raw_evidence_true_includes_bundle(self):
        self._make_execution("ex-raw-on")
        self._archive_evidence("ex-raw-on")
        result = self.build("ex-raw-on", include_raw_evidence=True)
        self.assertIsNotNone(result)
        self.assertIn("evidenceBundle", result)
        self.assertIsNotNone(result["evidenceBundle"])
        self.assertEqual(result["evidenceBundle"]["executionId"], "ex-raw-on")

    def test_include_raw_evidence_true_none_when_no_archive(self):
        self._make_execution("ex-raw-none")
        result = self.build("ex-raw-none", include_raw_evidence=True)
        self.assertIsNotNone(result)
        self.assertIn("evidenceBundle", result)
        self.assertIsNone(result["evidenceBundle"])

    # ── Consistency: no crash on null/legacy data ─────────────
    def test_no_crash_when_grant_missing(self):
        self._make_execution("ex-legacy", grant_id="nonexistent-grant")
        result = self.build("ex-legacy")
        self.assertIsNotNone(result)
        self.assertIsNone(result["grant"])
        self.assertIsNone(result["grantRequest"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
