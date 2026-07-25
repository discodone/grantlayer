"""GL-400 — ``?order=anchor`` export mode (spec follow-up, SPECIFICATION.md §11.2).

Today an outsider cannot self-serve an anchor-verifiable export through the
public endpoint: GET /v1/audit/export feeds the fold a ``timestamp DESC,
seq DESC``, limit-capped list, so its head never equals any on-chain anchor.
The anchored head is the fold over the FULL workspace chain in ``seq ASC``
order (``_build_anchor_export`` / ``_load_workspace_entries``).

Contract pinned here (RED before implementation):

  1. ``GET /v1/audit/export?order=anchor`` returns the full chain in seq ASC
     (id ASC tiebreak), BYTE-IDENTICAL to ``_build_anchor_export`` — the
     anchor-ordered path must REUSE the one authoritative ordering, never
     reimplement it — and its recomputed fold head equals ``anchor_head``.
     RED reason: FastAPI ignores the unknown ``order`` query param, so the
     response comes back default-ordered and the head assertions fail.
  2. Anchor mode is the full-chain determinism contract: explicit window
     params (``limit`` / ``start_date`` / ``end_date``) are rejected with 400
     instead of silently producing a head that matches no anchor.
     RED reason: the params are currently accepted (200).
  3. The DEFAULT order stays byte-identical to today (Decision 2 — no silent
     break of saved exports). This test is the non-breaking guard: it passes
     before AND after the change.
  4. NULLS LAST hardening (Decision 3, §11.3): ``_load_workspace_entries``
     must order NULL-seq rows LAST explicitly. RED reason on SQLite: bare
     ``ORDER BY seq ASC`` sorts NULLs FIRST there; PostgreSQL already sorts
     them last, so this pins cross-backend agreement with the anchored order.

Isolation: every test uses a uuid4-fresh tenant + workspace (cross-workspace
"owner" JWT + X-Workspace-Id), so no other test's events can enter the chain
under fold.
"""

from __future__ import annotations

import datetime
import json
import os
import unittest
import uuid

_JWT_SECRET = "gl400-test-hs256-secret-32chars!"


def _make_client():
    from starlette.testclient import TestClient

    from backend.src.api.app import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


class TestOrderAnchorExportMode(unittest.TestCase):
    def setUp(self):
        self._orig_jwt_secret = os.environ.get("GRANTLAYER_JWT_SECRET")
        os.environ["GRANTLAYER_JWT_SECRET"] = _JWT_SECRET
        from backend.src.core.db import get_session, init_db

        init_db()

        self.tenant_id = f"t-gl400-{uuid.uuid4()}"
        self.workspace_id = f"ws-gl400-{uuid.uuid4()}"
        self.operator_id = f"op-gl400-{uuid.uuid4()}"

        from backend.src.core.orm import Workspace

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        session = get_session()
        try:
            session.add(
                Workspace(
                    id=self.workspace_id,
                    tenant_id=self.tenant_id,
                    name="gl400",
                    slug=f"gl400-{uuid.uuid4()}",
                    owner_id=self.operator_id,
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()
        finally:
            session.close()

        from backend.src.api.auth_jwt import encode_token

        token = encode_token(
            {
                "sub": self.operator_id,
                "role": "owner",
                "tenant_id": self.tenant_id,
                "iss": "grantlayer",
                "aud": "grantlayer-api",
            },
            _JWT_SECRET,
        )
        self.headers = {
            "Authorization": f"Bearer {token}",
            "X-Workspace-Id": self.workspace_id,
        }
        self.client = _make_client()

    def tearDown(self):
        if self._orig_jwt_secret is None:
            os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        else:
            os.environ["GRANTLAYER_JWT_SECRET"] = self._orig_jwt_secret

    # ── helpers ────────────────────────────────────────────────────────────

    def _seed(self, n: int):
        """Append n events with ASCENDING timestamps, so the default export
        order (timestamp DESC) is the REVERSE of the anchored order (seq ASC)
        and the two cannot coincide by accident."""
        from backend.src.audit.audit_log import append_event
        from backend.src.core.models import AuditEvent

        for i in range(n):
            append_event(
                AuditEvent(
                    subject_id=f"subj-{i}",
                    role="agent",
                    action=f"act-{i}",
                    resource=f"res/{i}",
                    approved=(i % 2 == 0),
                    reason=f"reason-{i}",
                    timestamp=f"2026-01-01T00:{i // 60:02d}:{i % 60:02d}Z",
                    tenant_id=self.tenant_id,
                    workspace_id=self.workspace_id,
                    scope="tenant",
                )
            )

    @staticmethod
    def _parse(ndjson_text: str):
        records = [json.loads(line) for line in ndjson_text.splitlines() if line.strip()]
        manifest = None
        if records and records[-1].get("_type") == "manifest":
            manifest = records.pop()
        return records, manifest

    def _session(self):
        from backend.src.core.db import get_session

        return get_session()

    # ── 1. anchor mode: full chain, seq ASC, head == anchored head ─────────

    def test_anchor_mode_matches_build_anchor_export_and_anchored_head(self):
        from backend.src.api.routers.audit_compliance import (
            _build_anchor_export,
            anchor_head,
            recompute_head_from_records,
        )

        n = 7
        self._seed(n)

        resp = self.client.get("/v1/audit/export?order=anchor", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("ndjson", resp.headers.get("content-type", ""))

        data, manifest = self._parse(resp.text)
        self.assertIsNotNone(manifest)
        self.assertEqual(
            len(data), n, "anchor mode did not return the full workspace chain"
        )

        seqs = [r["seq"] for r in data]
        self.assertEqual(
            seqs,
            sorted(seqs),
            "anchor mode is not seq ASC — its fold head can never match an anchor",
        )

        session = self._session()
        try:
            expected_ndjson = _build_anchor_export(session, self.workspace_id)
            expected_head = anchor_head(session, self.workspace_id)
        finally:
            session.close()

        # Byte-identity with the anchor builder — the endpoint must REUSE the
        # single authoritative ordering + fold, not reimplement it.
        self.assertEqual(
            resp.text,
            expected_ndjson,
            "anchor-mode response is not byte-identical to _build_anchor_export",
        )

        self.assertEqual(manifest["_entry_count"], expected_head["entry_count"])
        self.assertEqual(
            manifest["_final_hash"],
            expected_head["final_hash"],
            "anchor-mode manifest head != anchored head",
        )

        # Independent recompute from the response's own data lines.
        clean = [
            {k: v for k, v in rec.items() if not k.startswith("_")} for rec in data
        ]
        recomputed = recompute_head_from_records(clean)
        self.assertEqual(recomputed["final_hash"], expected_head["final_hash"])
        self.assertEqual(recomputed["entry_count"], expected_head["entry_count"])

    # ── 2. anchor mode rejects window params (full-chain contract) ─────────

    def test_anchor_mode_rejects_window_params(self):
        self._seed(3)
        for query in (
            "order=anchor&limit=5",
            "order=anchor&start_date=2026-01-01",
            "order=anchor&end_date=2026-12-31",
        ):
            resp = self.client.get(f"/v1/audit/export?{query}", headers=self.headers)
            self.assertEqual(
                resp.status_code,
                400,
                f"?{query} must be rejected: anchor mode is the FULL-chain "
                "contract — a windowed 'anchor' export would verify against "
                "no anchor",
            )

    # ── 3. default order stays byte-identical (Decision 2 guard) ───────────

    def test_default_order_unchanged_byte_identical(self):
        """Non-breaking guard: passes before AND after GL-400. The expected
        bytes replicate the CURRENT default path (list_events limit=10000,
        timestamp DESC + date filter + fold) using the REAL primitives."""
        from backend.src.api.routers.audit_compliance import _iter_chain, _sign_manifest
        from backend.src.audit.audit_log import list_events

        self._seed(5)

        raw = list_events(
            limit=10000,
            offset=0,
            tenant_id=self.tenant_id,
            workspace_id=self.workspace_id,
        )
        events = [e.to_dict() for e in raw]

        expected_lines: list[str] = []
        all_hashes: list[str] = []
        final_hash = "0" * 64
        for event, prev_hash, entry_hash in _iter_chain(events):
            record = {**event, "_chain_hash": entry_hash, "_prev_hash": prev_hash}
            all_hashes.append(entry_hash)
            final_hash = entry_hash
            expected_lines.append(json.dumps(record, ensure_ascii=True) + "\n")
        expected_lines.append(
            json.dumps(
                {
                    "_type": "manifest",
                    "_entry_count": len(all_hashes),
                    "_final_hash": final_hash,
                    "_hmac_signature": _sign_manifest(all_hashes),
                },
                ensure_ascii=True,
            )
            + "\n"
        )
        expected = "".join(expected_lines)

        resp_implicit = self.client.get("/v1/audit/export", headers=self.headers)
        self.assertEqual(resp_implicit.status_code, 200)
        self.assertEqual(
            resp_implicit.text,
            expected,
            "default export changed — Decision 2 forbids breaking saved exports",
        )

        resp_explicit = self.client.get(
            "/v1/audit/export?order=default", headers=self.headers
        )
        self.assertEqual(resp_explicit.status_code, 200)
        self.assertEqual(resp_explicit.text, expected)

        # Default order is still timestamp DESC — NOT the anchored order.
        data, _ = self._parse(resp_implicit.text)
        timestamps = [r["timestamp"] for r in data]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    # ── 4. NULLS LAST hardening (Decision 3, §11.3) ────────────────────────

    def test_null_seq_rows_ordered_last(self):
        """A pre-migration NULL-seq row must fold LAST, on every backend.
        PostgreSQL sorts NULL last in ASC by default; SQLite sorts it FIRST —
        without an explicit NULLS LAST the two backends would fold different
        chains for the same data. RED on SQLite until the query says it."""
        from backend.src.api.routers.audit_compliance import _load_workspace_entries
        from backend.src.core.orm import AuditEvent as OrmAuditEvent

        self._seed(3)

        null_seq_id = f"ev-gl400-nullseq-{uuid.uuid4()}"
        session = self._session()
        try:
            session.add(
                OrmAuditEvent(
                    id=null_seq_id,
                    timestamp="2025-01-01T00:00:00Z",
                    subject_id="subj-legacy",
                    role="agent",
                    action="legacy-pre-seq",
                    resource="res/legacy",
                    approved=1,
                    reason="pre-migration row without seq",
                    tenant_id=self.tenant_id,
                    workspace_id=self.workspace_id,
                    scope="tenant",
                    seq=None,
                )
            )
            session.commit()
        finally:
            session.close()

        session = self._session()
        try:
            entries = _load_workspace_entries(session, self.workspace_id)
        finally:
            session.close()

        self.assertEqual(len(entries), 4)
        self.assertEqual(
            entries[-1]["id"],
            null_seq_id,
            "NULL-seq row is not ordered LAST — SQLite and PostgreSQL would "
            "fold different chains for the same data (Decision 3: explicit "
            "NULLS LAST)",
        )
        non_null_seqs = [e["seq"] for e in entries[:-1]]
        self.assertEqual(non_null_seqs, sorted(non_null_seqs))


if __name__ == "__main__":
    unittest.main()
