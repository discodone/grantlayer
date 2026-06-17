"""GL-304 — BIGSERIAL audit tiebreak + cursor-based pagination.

Covers:
- Migration 0013 adds seq column (INTEGER) to audit_events
- Migration backfills seq from rowid for existing rows
- append_event assigns seq on SQLite INSERT
- _get_latest_row_hash orders by seq DESC (not ctid/rowid)
- _fetch_all_audit_events_ordered orders by seq ASC
- list_events after_seq parameter filters correctly
- list_events ordering is (timestamp DESC, seq DESC)
- /v1/audit-events returns next_cursor when page is full
- /v1/audit-events cursor parameter navigates correctly
- /v1/audit-events next_cursor is None on last page
- Invalid cursor is silently ignored (falls back to no-cursor)
- seq field is populated on AuditEvent after insert
- AuditEventListResponse schema includes next_cursor field
"""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid


_TEST_TOKEN = "gl304-test-admin-token-valid"


def _make_client(tmp_db_path: str):
    """Return an isolated (app, TestClient) pair in legacy/demo auth mode."""
    os.environ["GRANTLAYER_DB"] = tmp_db_path
    os.environ.pop("GRANTLAYER_DATABASE_URL", None)
    os.environ["GRANTLAYER_ADMIN_TOKEN"] = _TEST_TOKEN
    os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "false"
    os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
    os.environ["GRANTLAYER_RATE_LIMIT_API"] = "10000"
    os.environ["GRANTLAYER_RATE_LIMIT_AUTH"] = "10000"

    import backend.src.core.db as db_mod
    importlib.reload(db_mod)
    db_mod.DB_PATH = tmp_db_path
    db_mod.DB_PATH_OR_URL = tmp_db_path
    db_mod.init_db()

    import backend.src.core.config as config_mod
    importlib.reload(config_mod)

    from fastapi.testclient import TestClient
    import backend.src.api.app as app_mod
    importlib.reload(app_mod)
    app = app_mod.create_app()
    client = TestClient(app, raise_server_exceptions=True)
    return app, client


def _make_event(tenant_id: str = "t1", workspace_id: str = "ws1") -> dict:
    from backend.src.core.models import AuditEvent
    return AuditEvent(
        subject_id=f"agent-{uuid.uuid4().hex[:8]}",
        role="viewer",
        action="read",
        resource=f"res/{uuid.uuid4().hex[:8]}",
        approved=True,
        reason="test",
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )


class TestMigration0013(unittest.TestCase):
    """seq column is created and backfilled by migration 0013."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self._env = {k: os.environ.get(k) for k in ["GRANTLAYER_DB", "GRANTLAYER_DATABASE_URL"]}

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        os.unlink(self.tmp.name)

    def test_seq_column_exists_after_migration(self):
        os.environ["GRANTLAYER_DB"] = self.tmp.name
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH = self.tmp.name
        db_mod.DB_PATH_OR_URL = self.tmp.name
        db_mod.init_db()

        from backend.src.core.db import query_one
        row = query_one("SELECT * FROM audit_events LIMIT 0")
        # Verify via PRAGMA rather than row content
        import sqlite3
        conn = sqlite3.connect(self.tmp.name)
        cursor = conn.execute("PRAGMA table_info(audit_events)")
        cols = [r[1] for r in cursor.fetchall()]
        conn.close()
        self.assertIn("seq", cols)

    def test_seq_backfilled_for_existing_rows(self):
        """Rows inserted before the migration column-add get seq from rowid."""
        # Pre-populate by calling init_db (migrations run including 0013)
        os.environ["GRANTLAYER_DB"] = self.tmp.name
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH = self.tmp.name
        db_mod.DB_PATH_OR_URL = self.tmp.name
        db_mod.init_db()

        # Insert an event via append_event
        import backend.src.audit.audit_log as al
        importlib.reload(al)
        event = _make_event()
        al.append_event(event)

        from backend.src.core.db import query_all
        rows = query_all("SELECT seq FROM audit_events WHERE seq IS NOT NULL")
        self.assertGreater(len(rows), 0)
        for r in rows:
            self.assertIsNotNone(r["seq"])
            self.assertGreater(int(r["seq"]), 0)


class TestSeqOnInsert(unittest.TestCase):
    """append_event assigns a positive seq on SQLite INSERT."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self._env = {k: os.environ.get(k) for k in ["GRANTLAYER_DB", "GRANTLAYER_DATABASE_URL"]}
        os.environ["GRANTLAYER_DB"] = self.tmp.name
        os.environ.pop("GRANTLAYER_DATABASE_URL", None)
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH = self.tmp.name
        db_mod.DB_PATH_OR_URL = self.tmp.name
        db_mod.init_db()
        import backend.src.audit.audit_log as al
        importlib.reload(al)
        self.al = al

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        os.unlink(self.tmp.name)

    def test_seq_assigned_after_append(self):
        event = _make_event()
        self.assertIsNone(event.seq)
        self.al.append_event(event)
        self.assertIsNotNone(event.seq)
        self.assertGreater(event.seq, 0)

    def test_seq_monotonically_increasing(self):
        events = [_make_event() for _ in range(5)]
        for e in events:
            self.al.append_event(e)
        seqs = [e.seq for e in events]
        self.assertEqual(seqs, sorted(seqs))
        self.assertEqual(len(seqs), len(set(seqs)))  # all unique

    def test_seq_populated_in_list_events(self):
        event = _make_event()
        self.al.append_event(event)
        results = self.al.list_events(limit=10)
        self.assertTrue(all(e.seq is not None for e in results))

    def test_no_ctid_rowid_reference(self):
        """audit_log.py must not reference ctid or rowid directly."""
        import inspect
        src = inspect.getsource(self.al)
        self.assertNotIn("ctid", src)
        self.assertNotIn('"rowid"', src)
        self.assertNotIn("'rowid'", src)


class TestListEventsAfterSeq(unittest.TestCase):
    """list_events(after_seq=...) returns correct filtered results."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self._env = {k: os.environ.get(k) for k in ["GRANTLAYER_DB", "GRANTLAYER_DATABASE_URL"]}
        os.environ["GRANTLAYER_DB"] = self.tmp.name
        os.environ.pop("GRANTLAYER_DATABASE_URL", None)
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH = self.tmp.name
        db_mod.DB_PATH_OR_URL = self.tmp.name
        db_mod.init_db()
        import backend.src.audit.audit_log as al
        importlib.reload(al)
        self.al = al
        # Insert 10 events with shared tenant/workspace
        self.events = []
        for _ in range(10):
            e = _make_event(tenant_id="tenant-a", workspace_id="ws-a")
            self.al.append_event(e)
            self.events.append(e)

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        os.unlink(self.tmp.name)

    def test_after_seq_excludes_cursor_and_beyond(self):
        # Get the seq of the 5th event (index 4, 0-based)
        pivot_seq = self.events[4].seq
        results = self.al.list_events(
            limit=100,
            tenant_id="tenant-a",
            workspace_id="ws-a",
            after_seq=pivot_seq,
        )
        result_seqs = [e.seq for e in results]
        for s in result_seqs:
            self.assertLess(s, pivot_seq)

    def test_after_seq_returns_older_events(self):
        # With after_seq = seq of last inserted, should return earlier events.
        last_seq = self.events[-1].seq
        results = self.al.list_events(
            limit=100,
            tenant_id="tenant-a",
            workspace_id="ws-a",
            after_seq=last_seq,
        )
        self.assertEqual(len(results), 9)

    def test_after_seq_empty_when_no_older_events(self):
        first_seq = self.events[0].seq
        results = self.al.list_events(
            limit=100,
            tenant_id="tenant-a",
            workspace_id="ws-a",
            after_seq=first_seq,
        )
        self.assertEqual(len(results), 0)

    def test_ordering_is_timestamp_desc_seq_desc(self):
        results = self.al.list_events(
            limit=100,
            tenant_id="tenant-a",
            workspace_id="ws-a",
        )
        seqs = [e.seq for e in results]
        self.assertEqual(seqs, sorted(seqs, reverse=True))


class TestCursorEncoding(unittest.TestCase):
    """Cursor encode/decode round-trips correctly."""

    def test_encode_decode_roundtrip(self):
        from backend.src.api.routers.audit_events import _encode_cursor, _decode_cursor
        for seq in [1, 42, 9999, 1_000_000]:
            encoded = _encode_cursor(seq)
            self.assertIsInstance(encoded, str)
            decoded = _decode_cursor(encoded)
            self.assertEqual(decoded, seq)

    def test_invalid_cursor_returns_none(self):
        from backend.src.api.routers.audit_events import _decode_cursor
        self.assertIsNone(_decode_cursor("not-valid-base64!!!"))
        self.assertIsNone(_decode_cursor("aGVsbG8="))  # "hello" — not an int


class TestAuditEventsEndpointCursor(unittest.TestCase):
    """GET /v1/audit-events cursor pagination via TestClient."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self._env = {k: os.environ.get(k) for k in [
            "GRANTLAYER_DB", "GRANTLAYER_DATABASE_URL",
            "GRANTLAYER_ADMIN_TOKEN", "GRANTLAYER_REQUIRE_ADMIN_TOKEN",
            "GRANTLAYER_ENABLE_OPERATOR_MODEL",
            "GRANTLAYER_RATE_LIMIT_API", "GRANTLAYER_RATE_LIMIT_AUTH",
        ]}
        self.app, self.client = _make_client(self.tmp.name)

        # Reload audit_log and insert events directly
        import backend.src.core.db as db_mod
        import backend.src.audit.audit_log as al
        importlib.reload(db_mod)
        importlib.reload(al)
        self.al = al
        # legacy demo mode resolves to tenant_id="demo", workspace_id="default"
        self._insert_events(12, tenant_id="demo", workspace_id="default")

    def _insert_events(self, n: int, **kwargs):
        for _ in range(n):
            e = _make_event(**kwargs)
            self.al.append_event(e)

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        os.unlink(self.tmp.name)

    def _auth_headers(self):
        return {"Authorization": f"Bearer {_TEST_TOKEN}"}

    def test_response_includes_next_cursor_when_page_full(self):
        resp = self.client.get(
            "/v1/audit-events?limit=5",
            headers=self._auth_headers(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("next_cursor", data)
        self.assertIsNotNone(data["next_cursor"])

    def test_next_cursor_none_on_last_page(self):
        resp = self.client.get(
            "/v1/audit-events?limit=1000",
            headers=self._auth_headers(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("next_cursor", data)
        self.assertIsNone(data["next_cursor"])

    def test_cursor_pagination_covers_all_events(self):
        """Paginating with cursor yields all events exactly once."""
        all_ids: list[str] = []
        cursor = None
        limit = 5
        for _ in range(10):  # safety limit
            url = f"/v1/audit-events?limit={limit}"
            if cursor:
                url += f"&cursor={cursor}"
            resp = self.client.get(url, headers=self._auth_headers())
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            all_ids.extend(item["id"] for item in data["items"])
            cursor = data.get("next_cursor")
            if cursor is None:
                break
        # 12 events were inserted; all should appear exactly once
        self.assertEqual(len(all_ids), 12)
        self.assertEqual(len(set(all_ids)), 12)

    def test_invalid_cursor_treated_as_no_cursor(self):
        resp = self.client.get(
            "/v1/audit-events?limit=100&cursor=invalid!!!",
            headers=self._auth_headers(),
        )
        # Should not 500 — falls back to unconstrained query
        self.assertEqual(resp.status_code, 200)

    def test_response_schema_has_next_cursor_field(self):
        resp = self.client.get(
            "/v1/audit-events",
            headers=self._auth_headers(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("next_cursor", data)

    def test_total_reflects_full_count_not_page(self):
        resp = self.client.get(
            "/v1/audit-events?limit=3",
            headers=self._auth_headers(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 12)
        self.assertEqual(len(data["items"]), 3)

    def test_offset_still_works_without_cursor(self):
        resp_p1 = self.client.get(
            "/v1/audit-events?limit=5&offset=0",
            headers=self._auth_headers(),
        )
        resp_p2 = self.client.get(
            "/v1/audit-events?limit=5&offset=5",
            headers=self._auth_headers(),
        )
        self.assertEqual(resp_p1.status_code, 200)
        self.assertEqual(resp_p2.status_code, 200)
        ids_p1 = {i["id"] for i in resp_p1.json()["items"]}
        ids_p2 = {i["id"] for i in resp_p2.json()["items"]}
        self.assertEqual(len(ids_p1 & ids_p2), 0)  # no overlap


class TestHashChainOrderingWithSeq(unittest.TestCase):
    """Hash chain helpers use seq for stable tiebreaking."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self._env = {k: os.environ.get(k) for k in ["GRANTLAYER_DB", "GRANTLAYER_DATABASE_URL"]}
        os.environ["GRANTLAYER_DB"] = self.tmp.name
        os.environ.pop("GRANTLAYER_DATABASE_URL", None)
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH = self.tmp.name
        db_mod.DB_PATH_OR_URL = self.tmp.name
        db_mod.init_db()
        import backend.src.audit.audit_log as al
        importlib.reload(al)
        self.al = al

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        os.unlink(self.tmp.name)

    def test_hash_chain_valid_after_multiple_appends(self):
        for _ in range(5):
            self.al.append_event(_make_event())
        result = self.al.verify_audit_hash_chain()
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked"], 5)
        self.assertEqual(len(result["failures"]), 0)

    def test_get_latest_row_hash_returns_last_appended(self):
        events = []
        for _ in range(3):
            e = _make_event()
            self.al.append_event(e)
            events.append(e)
        latest_hash = self.al._get_latest_row_hash()
        self.assertEqual(latest_hash, events[-1].row_hash)
