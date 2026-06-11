"""Tests for GL-105: Audit Chain Verification Report Builder.

Ensures:
1.  Report builder returns stable structured object.
2.  Clean audit chain report is valid.
3.  Empty audit log behavior is defined.
4.  checked_events included.
5.  failure_count included.
6.  failures list included.
7.  summary/status included.
8.  row_hash mismatch appears in report.
9.  prev_hash mismatch appears in report.
10. missing hash appears in report.
11. historical/pre-chain NULL hash behavior appears in report.
12. recommendations are deterministic.
13. report builder is read-only.
14. report builder does not insert audit events.
15. no audit verification API endpoint is added.
16. no OpenAPI change is made.
17. GL-104 verification helper behavior preserved.
18. GL-103 audit insertion preserved.
19. GL-102 UPDATE/DELETE immutability preserved.
20. Diff scope limited to allowed files.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import importlib
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl105(unittest.TestCase):
    """Shared helpers for GL-105 tests."""

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

        import backend.src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import backend.src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.grant_requests as requests_mod
        importlib.reload(requests_mod)
        self.requests_mod = requests_mod

        import backend.src.models as models_mod
        importlib.reload(models_mod)
        self.models_mod = models_mod

        import backend.src.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

        import backend.src.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import backend.src.server as server_mod
        importlib.reload(server_mod)
        self.server_mod = server_mod

        self.db_mod = db_mod
        self.handler_class = server_mod.GrantLayerHandler

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

    def _insert_operator(self, op_id, name, role, token):
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators (id, name, role, token_hash, active, created_at)
                   VALUES (?, ?, ?, ?, 1, datetime('now'))""",
                (op_id, name, role, self.ops_mod.hash_token(token)),
            )
            conn.commit()
        finally:
            conn.close()

    def _make_handler(self, path, method="GET", auth_header=None, body=b"", content_length=None):
        handler = self.handler_class.__new__(self.handler_class)
        handler.rfile = BytesIO(body)
        handler.wfile = BytesIO()
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if body or content_length is not None:
            headers["Content-Length"] = str(content_length) if content_length is not None else str(len(body))
        handler.headers = headers
        handler.path = path
        handler.command = method
        handler.requestline = f"{method} {path} HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None
        return handler

    def _run_handler(self, handler):
        if handler.command == "GET":
            handler.do_GET()
        elif handler.command == "POST":
            handler.do_POST()
        handler.wfile.seek(0)
        response = handler.wfile.read()
        status_line = response.split(b"\r\n")[0]
        status = int(status_line.split(b" ")[1])
        parts = response.split(b"\r\n\r\n", 1)
        body = json.loads(parts[1]) if len(parts) > 1 else {}
        return status, body

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


# ═══════════════════════════════════════════════════════════════════════
# 1. Stable structured object
# ═══════════════════════════════════════════════════════════════════════

class TestGl105StableStructuredObject(_BaseGl105):
    """Report builder must return a stable structured object."""

    def test_report_has_required_fields(self):
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertIn("report_type", report)
        self.assertIn("valid", report)
        self.assertIn("checked_events", report)
        self.assertIn("failure_count", report)
        self.assertIn("failures", report)
        self.assertIn("summary", report)
        self.assertIn("status", report)
        self.assertIn("recommendations", report)

    def test_report_type_is_correct(self):
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertEqual(report["report_type"], "audit_chain_verification")

    def test_report_is_json_serializable(self):
        self._append_audit_event("evt-stable-1")
        report = self.audit_mod.build_audit_chain_verification_report()
        serialized = json.dumps(report)
        deserialized = json.loads(serialized)
        self.assertEqual(deserialized["report_type"], "audit_chain_verification")


# ═══════════════════════════════════════════════════════════════════════
# 2. Clean audit chain report is valid
# ═══════════════════════════════════════════════════════════════════════

class TestGl105CleanChainReportValid(_BaseGl105):
    """A correctly formed hash chain must produce a valid report."""

    def test_empty_log_report_valid(self):
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertTrue(report["valid"])
        self.assertEqual(report["checked_events"], 0)
        self.assertEqual(report["failure_count"], 0)
        self.assertEqual(report["failures"], [])

    def test_single_event_report_valid(self):
        self._append_audit_event("evt-clean-1")
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertTrue(report["valid"])
        self.assertEqual(report["checked_events"], 1)
        self.assertEqual(report["failure_count"], 0)
        self.assertEqual(report["failures"], [])

    def test_multiple_events_report_valid(self):
        self._append_audit_event("evt-clean-2")
        self._append_audit_event("evt-clean-3")
        self._append_audit_event("evt-clean-4")
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertTrue(report["valid"])
        self.assertEqual(report["checked_events"], 3)
        self.assertEqual(report["failure_count"], 0)
        self.assertEqual(report["failures"], [])


# ═══════════════════════════════════════════════════════════════════════
# 3. Empty audit log behavior
# ═══════════════════════════════════════════════════════════════════════

class TestGl105EmptyAuditLog(_BaseGl105):
    """Empty audit log must produce a defined report."""

    def test_empty_log_status_is_empty(self):
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertEqual(report["status"], "empty")
        self.assertIn("empty", report["summary"].lower())

    def test_empty_log_recommendation(self):
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertEqual(len(report["recommendations"]), 1)
        self.assertIn("no chain events present", report["recommendations"][0].lower())


# ═══════════════════════════════════════════════════════════════════════
# 4-7. Field inclusion
# ═══════════════════════════════════════════════════════════════════════

class TestGl105FieldsIncluded(_BaseGl105):
    """All required fields must be present and correct."""

    def test_checked_events_included(self):
        self._append_audit_event("evt-field-1")
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertEqual(report["checked_events"], 1)
        self.assertIsInstance(report["checked_events"], int)

    def test_failure_count_included(self):
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertEqual(report["failure_count"], 0)
        self.assertIsInstance(report["failure_count"], int)

    def test_failures_list_included(self):
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertIsInstance(report["failures"], list)

    def test_summary_and_status_included(self):
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertIsInstance(report["summary"], str)
        self.assertIsInstance(report["status"], str)
        self.assertTrue(len(report["summary"]) > 0)
        self.assertTrue(len(report["status"]) > 0)


# ═══════════════════════════════════════════════════════════════════════
# 8. row_hash mismatch appears in report
# ═══════════════════════════════════════════════════════════════════════

class TestGl105RowHashMismatchInReport(_BaseGl105):
    """Tampered row_hash must appear in the report."""

    def test_row_hash_mismatch_in_report(self):
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO audit_events
                   (id, timestamp, subject_id, role, action, resource, approved,
                    reason, matched_grant_id, challenge_id, challenge_present,
                    challenge_result, grant_signature_result, row_hash, prev_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("evt-row-bad", "2026-01-01T00:00:00Z", "s", "r", "a", "res", 1,
                 "r", None, None, 0, "legacy_mode", "not_checked",
                 "0000000000000000000000000000000000000000000000000000000000000000", None)
            )
            conn.commit()
        finally:
            conn.close()

        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertFalse(report["valid"])
        self.assertEqual(report["failure_count"], 1)
        reasons = [f["reason"] for f in report["failures"]]
        self.assertTrue(any("row_hash mismatch" in r for r in reasons))
        self.assertIn("invalid", report["status"])
        self.assertTrue(any("row_hash" in r.lower() for r in report["recommendations"]))


# ═══════════════════════════════════════════════════════════════════════
# 9. prev_hash mismatch appears in report
# ═══════════════════════════════════════════════════════════════════════

class TestGl105PrevHashMismatchInReport(_BaseGl105):
    """Tampered prev_hash must appear in the report."""

    def test_prev_hash_mismatch_in_report(self):
        self._append_audit_event("evt-prev-first")
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO audit_events
                   (id, timestamp, subject_id, role, action, resource, approved,
                    reason, matched_grant_id, challenge_id, challenge_present,
                    challenge_result, grant_signature_result, row_hash, prev_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("evt-prev-second", "2026-01-01T00:00:01Z", "s", "r", "a", "res", 1,
                 "r", None, None, 0, "legacy_mode", "not_checked",
                 "0000000000000000000000000000000000000000000000000000000000000000",
                 "bad_prev_hash")
            )
            conn.commit()
        finally:
            conn.close()

        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertFalse(report["valid"])
        reasons = [f["reason"] for f in report["failures"]]
        self.assertTrue(any("prev_hash mismatch" in r for r in reasons))
        self.assertTrue(any("prev_hash" in r.lower() for r in report["recommendations"]))


# ═══════════════════════════════════════════════════════════════════════
# 10. missing hash appears in report
# ═══════════════════════════════════════════════════════════════════════

class TestGl105MissingHashInReport(_BaseGl105):
    """Missing hash behavior must be represented in the report."""

    def test_missing_hash_skipped_in_report(self):
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO audit_events
                   (id, timestamp, subject_id, role, action, resource, approved,
                    reason, matched_grant_id, challenge_id, challenge_present,
                    challenge_result, grant_signature_result, row_hash, prev_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("evt-null-hash", "2026-01-01T00:00:00Z", "s", "r", "a", "res", 1,
                 "r", None, None, 0, "legacy_mode", "not_checked", None, None)
            )
            conn.commit()
        finally:
            conn.close()

        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertTrue(report["valid"])
        self.assertEqual(report["checked_events"], 0)
        # Missing hash row is represented in summary as skipped
        self.assertIn("historical", report["summary"].lower())


# ═══════════════════════════════════════════════════════════════════════
# 11. Historical/pre-chain NULL hash rows
# ═══════════════════════════════════════════════════════════════════════

class TestGl105HistoricalNullHashRows(_BaseGl105):
    """Historical rows with NULL row_hash should be represented in report."""

    def test_null_rows_before_chain_in_report(self):
        conn = self.db_mod.get_conn()
        try:
            for i in range(3):
                conn.execute(
                    """INSERT INTO audit_events
                       (id, timestamp, subject_id, role, action, resource, approved,
                        reason, matched_grant_id, challenge_id, challenge_present,
                        challenge_result, grant_signature_result, row_hash, prev_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (f"evt-legacy-{i}", f"2025-12-0{i+1}T00:00:00Z", "s", "r", "a", "res", 1,
                     "r", None, None, 0, "legacy_mode", "not_checked", None, None)
                )
            conn.commit()
        finally:
            conn.close()

        self._append_audit_event("evt-after-legacy-1")
        self._append_audit_event("evt-after-legacy-2")

        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertTrue(report["valid"])
        self.assertEqual(report["checked_events"], 2)
        self.assertIn("historical", report["summary"].lower())
        self.assertIn("skipped", report["summary"].lower())


# ═══════════════════════════════════════════════════════════════════════
# 12. Recommendations are deterministic
# ═══════════════════════════════════════════════════════════════════════

class TestGl105RecommendationsDeterministic(_BaseGl105):
    """Recommendations must be deterministic for the same input state."""

    def test_same_state_same_recommendations(self):
        self._append_audit_event("evt-det-1")
        report1 = self.audit_mod.build_audit_chain_verification_report()
        report2 = self.audit_mod.build_audit_chain_verification_report()
        self.assertEqual(report1["recommendations"], report2["recommendations"])

    def test_clean_chain_recommendation(self):
        self._append_audit_event("evt-det-2")
        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertEqual(len(report["recommendations"]), 1)
        self.assertIn("no action required", report["recommendations"][0].lower())

    def test_row_hash_mismatch_recommendation_deterministic(self):
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO audit_events
                   (id, timestamp, subject_id, role, action, resource, approved,
                    reason, matched_grant_id, challenge_id, challenge_present,
                    challenge_result, grant_signature_result, row_hash, prev_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("evt-rec-bad", "2026-01-01T00:00:00Z", "s", "r", "a", "res", 1,
                 "r", None, None, 0, "legacy_mode", "not_checked",
                 "0000000000000000000000000000000000000000000000000000000000000000", None)
            )
            conn.commit()
        finally:
            conn.close()

        report1 = self.audit_mod.build_audit_chain_verification_report()
        report2 = self.audit_mod.build_audit_chain_verification_report()
        self.assertEqual(report1["recommendations"], report2["recommendations"])
        self.assertTrue(any("row_hash" in r.lower() for r in report1["recommendations"]))


# ═══════════════════════════════════════════════════════════════════════
# 13. Read-only: no mutation
# ═══════════════════════════════════════════════════════════════════════

class TestGl105ReadOnly(_BaseGl105):
    """Report builder must not mutate audit_events."""

    def test_report_builder_does_not_mutate(self):
        self._append_audit_event("evt-ro-1")
        self._append_audit_event("evt-ro-2")

        before = self.audit_mod.list_events(limit=10)
        before_hashes = {e.id: e.row_hash for e in before}

        self.audit_mod.build_audit_chain_verification_report()

        after = self.audit_mod.list_events(limit=10)
        after_hashes = {e.id: e.row_hash for e in after}

        self.assertEqual(before_hashes, after_hashes)


# ═══════════════════════════════════════════════════════════════════════
# 14. Read-only: no insertion
# ═══════════════════════════════════════════════════════════════════════

class TestGl105NoInsertion(_BaseGl105):
    """Report builder must not insert audit events."""

    def test_report_builder_does_not_insert(self):
        self._append_audit_event("evt-no-ins-1")
        before = len(self.audit_mod.list_events(limit=10))
        self.audit_mod.build_audit_chain_verification_report()
        after = len(self.audit_mod.list_events(limit=10))
        self.assertEqual(before, after)


# ═══════════════════════════════════════════════════════════════════════
# 15. No audit verification endpoint added
# ═══════════════════════════════════════════════════════════════════════

class TestGl105NoVerificationEndpoint(_BaseGl105):
    """Ensure no audit verification endpoint was added."""

    def test_no_verify_audit_route(self):
        handler = self._make_handler("/audit/verify")
        status, data = self._run_handler(handler)
        self.assertEqual(status, 404)

    def test_no_verify_hash_route(self):
        handler = self._make_handler("/audit/verify-hash")
        status, data = self._run_handler(handler)
        self.assertEqual(status, 404)


# ═══════════════════════════════════════════════════════════════════════
# 16. No OpenAPI change
# ═══════════════════════════════════════════════════════════════════════

class TestGl105NoOpenApiChange(unittest.TestCase):
    """Ensure no OpenAPI changes were made."""

    def test_no_openapi_file_changed(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        openapi_files = [p for p in changed if "openapi" in p.lower()]
        self.assertEqual(
            openapi_files,
            [],
            f"OpenAPI files changed unexpectedly: {openapi_files}",
        )


# ═══════════════════════════════════════════════════════════════════════
# 17. GL-104 verification helper preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl105Gl104Preserved(_BaseGl105):
    """GL-104 verification helper must remain intact."""

    def test_verify_audit_hash_chain_still_works(self):
        self._append_audit_event("evt-gl104-1")
        result = self.audit_mod.verify_audit_hash_chain()
        self.assertTrue(result["valid"])
        self.assertIn("checked", result)
        self.assertIn("failures", result)

    def test_gl104_detects_row_hash_mismatch(self):
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO audit_events
                   (id, timestamp, subject_id, role, action, resource, approved,
                    reason, matched_grant_id, challenge_id, challenge_present,
                    challenge_result, grant_signature_result, row_hash, prev_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("evt-gl104-bad", "2026-01-01T00:00:00Z", "s", "r", "a", "res", 1,
                 "r", None, None, 0, "legacy_mode", "not_checked",
                 "0000000000000000000000000000000000000000000000000000000000000000", None)
            )
            conn.commit()
        finally:
            conn.close()

        result = self.audit_mod.verify_audit_hash_chain()
        self.assertFalse(result["valid"])
        reasons = [f["reason"] for f in result["failures"]]
        self.assertTrue(any("row_hash mismatch" in r for r in reasons))


# ═══════════════════════════════════════════════════════════════════════
# 18. GL-103 audit insertion preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl105Gl103Preserved(_BaseGl105):
    """GL-103 audit insertion must remain intact."""

    def test_insert_creates_row_hash(self):
        event = self._append_audit_event("evt-hash-1")
        self.assertIsNotNone(event.row_hash)
        self.assertEqual(len(event.row_hash), 64)

    def test_insert_chains_prev_hash(self):
        first = self._append_audit_event("evt-hash-2")
        second = self._append_audit_event("evt-hash-3")
        self.assertIsNone(first.prev_hash)
        self.assertEqual(second.prev_hash, first.row_hash)


# ═══════════════════════════════════════════════════════════════════════
# 19. GL-102 immutability preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl105Gl102ImmutabilityPreserved(_BaseGl105):
    """UPDATE and DELETE on audit_events must still be blocked."""

    def test_update_still_blocked(self):
        self._append_audit_event("evt-upd-1")
        conn = self.db_mod.get_conn()
        try:
            with self.assertRaises(Exception) as ctx:
                conn.execute(
                    "UPDATE audit_events SET reason = 'tampered' WHERE id = ?",
                    ("evt-upd-1",),
                )
            msg = str(ctx.exception).lower()
            self.assertIn("immutable", msg)
            self.assertIn("update", msg)
        finally:
            conn.close()

    def test_delete_still_blocked(self):
        self._append_audit_event("evt-del-1")
        conn = self.db_mod.get_conn()
        try:
            with self.assertRaises(Exception) as ctx:
                conn.execute(
                    "DELETE FROM audit_events WHERE id = ?",
                    ("evt-del-1",),
                )
            msg = str(ctx.exception).lower()
            self.assertIn("immutable", msg)
            self.assertIn("delete", msg)
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════
# 20. Server safety / boundary checks
# ═══════════════════════════════════════════════════════════════════════

class TestGl105ServerSafety(_BaseGl105):
    """Server-layer safety checks."""

    def test_health_public(self):
        handler = self._make_handler("/health")
        status, data = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(data.get("status"), "ok")

    def test_readiness_public(self):
        handler = self._make_handler("/readiness")
        status, data = self._run_handler(handler)
        self.assertIn(status, (200, 503))

    def test_protected_endpoint_requires_auth(self):
        handler = self._make_handler("/grants")
        status, data = self._run_handler(handler)
        self.assertIn(status, (401, 403))


# ═══════════════════════════════════════════════════════════════════════
# 21. Diff scope validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl105NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-105 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-105-audit-chain-verification-report-builder":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-105 feature branch"
            )
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/audit_log.py",
            "backend/tests/test_gl105_audit_chain_verification_report.py",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-105 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
