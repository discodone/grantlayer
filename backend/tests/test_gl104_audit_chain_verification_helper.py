"""Tests for GL-104: Audit Chain Verification Helper.

Ensures:
1.  Clean audit hash chain verifies valid.
2.  Structured result includes valid/checked/failures.
3.  row_hash recomputation is deterministic.
4.  row_hash mismatch is detected.
5.  prev_hash mismatch is detected.
6.  Missing row_hash behavior is defined and tested.
7.  First event genesis prev_hash behavior is verified.
8.  Historical/pre-chain NULL hash rows behavior is defined and tested.
9.  Verification does not mutate audit_events.
10. Verification does not insert audit events.
11. GL-102 UPDATE immutability still blocks mutation.
12. GL-102 DELETE immutability still blocks deletion.
13. GL-103 audit insertion still creates row_hash and prev_hash.
14. No audit verification endpoint is added.
15. Health/readiness remain public.
16. Diff scope limited to allowed files.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))



class _BaseGl104(unittest.TestCase):
    """Shared helpers for GL-104 tests."""

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
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH_OR_URL = self.tmp_db.name
        db_mod.DB_PATH = self.tmp_db.name
        db_mod.init_db()

        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.grants.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.grants.grant_requests as requests_mod
        importlib.reload(requests_mod)
        self.requests_mod = requests_mod

        import backend.src.core.models as models_mod
        importlib.reload(models_mod)
        self.models_mod = models_mod

        import backend.src.audit.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        self.db_mod = db_mod

        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        self.client = TestClient(create_app(), raise_server_exceptions=False)

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
                   VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                   ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, role=EXCLUDED.role, token_hash=EXCLUDED.token_hash, active=EXCLUDED.active""",
                (op_id, name, role, self.ops_mod.hash_token(token)),
            )
            conn.commit()
        finally:
            conn.close()

    def _make_handler(self, path, method="GET", auth_header=None, body=b"", content_length=None):
        return (path, method, auth_header, body)

    def _run_handler(self, req):
        path, method, auth_header, body = req
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if method == "GET":
            resp = self.client.get(path, headers=headers)
        else:
            if isinstance(body, (bytes, bytearray)) and len(body) > 0:
                try:
                    body_dict = json.loads(body)
                    resp = self.client.post(path, json=body_dict, headers=headers)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    resp = self.client.post(path, content=body, headers=headers)
            else:
                resp = self.client.post(path, headers=headers)
        try:
            data = resp.json()
        except Exception:
            data = {}
        if isinstance(data, dict) and isinstance(data.get("detail"), dict):
            data = data["detail"]
        return resp.status_code, data

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
# 1. Clean chain verifies valid
# ═══════════════════════════════════════════════════════════════════════

class TestGl104CleanChainVerifiesValid(_BaseGl104):
    """A correctly formed hash chain must verify as valid."""

    def test_empty_chain_verifies_valid(self):
        result = self.audit_mod.verify_audit_hash_chain()
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked"], 0)
        self.assertEqual(result["failures"], [])

    def test_single_event_verifies_valid(self):
        self._append_audit_event("evt-clean-1")
        result = self.audit_mod.verify_audit_hash_chain()
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["failures"], [])

    def test_multiple_events_verifies_valid(self):
        self._append_audit_event("evt-clean-2")
        self._append_audit_event("evt-clean-3")
        self._append_audit_event("evt-clean-4")
        result = self.audit_mod.verify_audit_hash_chain()
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked"], 3)
        self.assertEqual(result["failures"], [])


# ═══════════════════════════════════════════════════════════════════════
# 2. Structured verification result
# ═══════════════════════════════════════════════════════════════════════

class TestGl104StructuredResult(_BaseGl104):
    """Result must contain valid, checked, and failures."""

    def test_result_has_required_fields(self):
        self._append_audit_event("evt-struc-1")
        result = self.audit_mod.verify_audit_hash_chain()
        self.assertIn("valid", result)
        self.assertIn("checked", result)
        self.assertIn("failures", result)
        self.assertIsInstance(result["valid"], bool)
        self.assertIsInstance(result["checked"], int)
        self.assertIsInstance(result["failures"], list)

    def test_failures_contain_event_id_index_reason(self):
        # Insert a row with a bad row_hash directly via SQL
        # because UPDATE is blocked by immutability triggers
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO audit_events
                   (id, timestamp, subject_id, role, action, resource, approved,
                    reason, matched_grant_id, challenge_id, challenge_present,
                    challenge_result, grant_signature_result, row_hash, prev_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("evt-bad", "2026-01-01T00:00:00Z", "s", "r", "a", "res", 1,
                 "r", None, None, 0, "legacy_mode", "not_checked", "bad hash", None)
            )
            conn.commit()
        finally:
            conn.close()

        result = self.audit_mod.verify_audit_hash_chain()
        self.assertFalse(result["valid"])
        self.assertEqual(len(result["failures"]), 1)
        failure = result["failures"][0]
        self.assertIn("event_id", failure)
        self.assertIn("index", failure)
        self.assertIn("reason", failure)


# ═══════════════════════════════════════════════════════════════════════
# 3. Deterministic recomputation
# ═══════════════════════════════════════════════════════════════════════

class TestGl104DeterministicRecomputation(_BaseGl104):
    """Recomputing the same event multiple times must yield the same hash."""

    def test_recomputation_matches_stored_hash(self):
        event = self._append_audit_event("evt-det-1")
        # Recompute directly
        hash1 = self.audit_mod._compute_row_hash(event, event.prev_hash)
        hash2 = self.audit_mod._compute_row_hash(event, event.prev_hash)
        self.assertEqual(hash1, hash2)
        self.assertEqual(hash1, event.row_hash)


# ═══════════════════════════════════════════════════════════════════════
# 4. row_hash mismatch detection
# ═══════════════════════════════════════════════════════════════════════

class TestGl104RowHashMismatch(_BaseGl104):
    """Tampered row_hash must be detected as a mismatch."""

    def test_bad_row_hash_detected(self):
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

        result = self.audit_mod.verify_audit_hash_chain()
        self.assertFalse(result["valid"])
        reasons = [f["reason"] for f in result["failures"]]
        self.assertTrue(any("row_hash mismatch" in r for r in reasons))


# ═══════════════════════════════════════════════════════════════════════
# 5. prev_hash mismatch detection
# ═══════════════════════════════════════════════════════════════════════

class TestGl104PrevHashMismatch(_BaseGl104):
    """Tampered prev_hash must be detected as a mismatch."""

    def test_bad_prev_hash_detected(self):
        # Build a real first event so there is a prior row_hash
        self._append_audit_event("evt-prev-first")
        conn = self.db_mod.get_conn()
        try:
            # Insert second event with correct row_hash but wrong prev_hash
            # row_hash was computed over correct payload (with proper prev_hash),
            # so we'll manually compute it and store it with a wrong prev_hash value
            # Actually: to trigger prev_hash mismatch, store a row_hash that was
            # computed with the correct prev_hash but set prev_hash to something else.
            # The helper checks prev_hash equality first, then recomputes row_hash
            # using expected_prev_hash. So if prev_hash is wrong but row_hash was
            # computed with that wrong prev_hash, the row_hash check using expected
            # prev_hash will still fail.
            #
            # Simpler: insert first event, then insert second with correct row_hash
            # but store wrong prev_hash. The prev_hash mismatch is detected first;
            # then row_hash is recomputed with expected_prev_hash and will also mismatch.
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

        result = self.audit_mod.verify_audit_hash_chain()
        self.assertFalse(result["valid"])
        reasons = [f["reason"] for f in result["failures"]]
        self.assertTrue(any("prev_hash mismatch" in r for r in reasons))


# ═══════════════════════════════════════════════════════════════════════
# 6. Missing row_hash behavior
# ═══════════════════════════════════════════════════════════════════════

class TestGl104MissingRowHash(_BaseGl104):
    """Rows with NULL row_hash must be skipped in verification."""

    def test_null_row_hash_skipped(self):
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

        result = self.audit_mod.verify_audit_hash_chain()
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked"], 0)


# ═══════════════════════════════════════════════════════════════════════
# 7. Genesis prev_hash behavior
# ═══════════════════════════════════════════════════════════════════════

class TestGl104GenesisPrevHash(_BaseGl104):
    """First chain event must have prev_hash == None (genesis)."""

    def test_first_event_prev_hash_is_none(self):
        self._append_audit_event("evt-genesis-1")
        conn = self.db_mod.get_conn()
        try:
            row = conn.execute(
                "SELECT prev_hash FROM audit_events WHERE id = ?",
                ("evt-genesis-1",)
            ).fetchone()
            self.assertIsNone(row["prev_hash"])
        finally:
            conn.close()

    def test_genesis_included_in_result(self):
        self._append_audit_event("evt-genesis-2")
        result = self.audit_mod.verify_audit_hash_chain()
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked"], 1)


# ═══════════════════════════════════════════════════════════════════════
# 8. Historical/pre-chain NULL hash rows
# ═══════════════════════════════════════════════════════════════════════

class TestGl104HistoricalNullHashRows(_BaseGl104):
    """Historical rows with NULL row_hash should not break chain verification."""

    def test_null_rows_before_chain_are_skipped(self):
        # Insert legacy/historical rows without hashes
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

        # Then insert normal chained events
        self._append_audit_event("evt-after-legacy-1")
        self._append_audit_event("evt-after-legacy-2")

        result = self.audit_mod.verify_audit_hash_chain()
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked"], 2)


# ═══════════════════════════════════════════════════════════════════════
# 9. Read-only: no mutation
# ═══════════════════════════════════════════════════════════════════════

class TestGl104ReadOnly(_BaseGl104):
    """Verification must not mutate audit_events."""

    def test_verification_does_not_mutate(self):
        self._append_audit_event("evt-ro-1")
        self._append_audit_event("evt-ro-2")

        before = self.audit_mod.list_events(limit=10)
        before_hashes = {e.id: e.row_hash for e in before}

        self.audit_mod.verify_audit_hash_chain()

        after = self.audit_mod.list_events(limit=10)
        after_hashes = {e.id: e.row_hash for e in after}

        self.assertEqual(before_hashes, after_hashes)


# ═══════════════════════════════════════════════════════════════════════
# 10. Read-only: no insertion
# ═══════════════════════════════════════════════════════════════════════

class TestGl104NoInsertion(_BaseGl104):
    """Verification must not insert audit events."""

    def test_verification_does_not_insert(self):
        self._append_audit_event("evt-no-ins-1")
        before = len(self.audit_mod.list_events(limit=10))
        self.audit_mod.verify_audit_hash_chain()
        after = len(self.audit_mod.list_events(limit=10))
        self.assertEqual(before, after)


# ═══════════════════════════════════════════════════════════════════════
# 11-12. GL-102 immutability still intact
# ═══════════════════════════════════════════════════════════════════════

class TestGl104Gl102ImmutabilityPreserved(_BaseGl104):
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
# 13. GL-103 insertion still creates hashes
# ═══════════════════════════════════════════════════════════════════════

class TestGl104Gl103InsertionPreserved(_BaseGl104):
    """append_event must still create row_hash and prev_hash."""

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
# 14. No audit verification endpoint added
# ═══════════════════════════════════════════════════════════════════════

class TestGl104NoVerificationEndpoint(_BaseGl104):
    """Ensure no audit verification endpoint was added."""

    def test_no_verify_audit_route(self):
        req = self._make_handler("/audit/verify")
        status, data = self._run_handler(req)
        self.assertEqual(status, 404)

    def test_no_verify_hash_route(self):
        req = self._make_handler("/audit/verify-hash")
        status, data = self._run_handler(req)
        self.assertEqual(status, 404)


# ═══════════════════════════════════════════════════════════════════════
# 15. Server safety / boundary checks
# ═══════════════════════════════════════════════════════════════════════

class TestGl104ServerSafety(_BaseGl104):
    """Server-layer safety checks."""

    def test_health_public(self):
        req = self._make_handler("/health")
        status, data = self._run_handler(req)
        self.assertEqual(status, 200)
        self.assertEqual(data.get("status"), "ok")

    def test_readiness_public(self):
        req = self._make_handler("/readiness")
        status, data = self._run_handler(req)
        self.assertIn(status, (200, 503))

    def test_protected_endpoint_requires_auth(self):
        req = self._make_handler("/v1/grants")
        status, data = self._run_handler(req)
        self.assertIn(status, (401, 403))


# ═══════════════════════════════════════════════════════════════════════
# 16. Diff scope validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl104NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-104 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-104-audit-chain-verification-helper":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-104 feature branch"
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
            "backend/tests/test_gl104_audit_chain_verification_helper.py",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-104 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
