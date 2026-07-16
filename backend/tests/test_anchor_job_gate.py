"""GL-350b WRITER step 1 — RED tests: the daily anchor job's fail-closed gates.

Fully network-free: the BlockFrost chain context and every chain call are mocked.
These reference not-yet-existing code, so each test fails at import FIRST
(import is the first statement in every method):
  - backend.src.workers.jobs.anchor_audit_chain   (the ARQ daily cron job)
  - backend.src.core.orm.AnchorRecord              (persistence table)

Pinned job contract (order matters — the tests below enforce it):
  1. config = CardanoConfig.from_env()
  2. if not config.is_fully_configured(): abort — NO context built, NO row written
  3. chain = writer.build_chain_context(config)
  4. writer.probe_reachable(chain)        # raises on unreachable → abort, NO 'submitted' row
  5. same-(workspace, UTC-day) guard      # existing submitted/confirmed → abort, NO submit
  6. write 'submitted' AnchorRecord row   # BEFORE submit
  7. tx_id = writer.submit_anchor(chain, config, payload)
  8. update row → 'confirmed' + tx_id

Mockable seams (stable patch targets the GREEN code must expose):
  backend.src.anchoring.config.CardanoConfig.from_env
  backend.src.anchoring.writer.build_chain_context / probe_reachable / submit_anchor
  backend.src.api.routers.audit_compliance.anchor_head
  backend.src.core.db.get_session_maker
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import os
import tempfile
import unittest
from contextlib import ExitStack
from unittest import mock

_WS = "11111111-1111-1111-1111-111111111111"
_VALID_H = "a" * 64
_HEAD = {"final_hash": _VALID_H, "entry_count": 5}


def _make_db_maker():
    """Temp-file SQLite sessionmaker with all ORM tables created (incl AnchorRecord)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.src.core.orm import Base  # GREEN registers AnchorRecord on Base

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False), path


def _fake_config(*, configured: bool):
    cfg = mock.MagicMock(name="CardanoConfig")
    cfg.is_fully_configured.return_value = configured
    cfg.workspace_id = _WS
    cfg.network = "preprod"
    cfg.anchor_label = 923350
    cfg.blockfrost_project_id = "preprodPID" if configured else None
    cfg.signing_key = '{"type":"x","cborHex":"00"}' if configured else None
    # Cap guards inactive in these ordering tests (exercised in
    # test_anchor_cap_guards.py) so Gate A/B/C do not intercept the flow.
    cfg.max_wallet_lovelace = None
    cfg.max_fee_lovelace = None
    cfg.expected_address = None
    return cfg


def _count_rows(maker):
    from backend.src.core.orm import AnchorRecord

    with maker() as s:
        return s.query(AnchorRecord).count()


class TestAnchorJobGate(unittest.TestCase):

    # 3 ──────────────────────────────────────────────────────────────────
    def test_job_aborts_when_not_fully_configured(self):
        from backend.src.workers.jobs import anchor_audit_chain  # RED: not implemented yet

        maker, _ = _make_db_maker()
        build_ctx = mock.MagicMock(name="build_chain_context")
        submit = mock.MagicMock(name="submit_anchor")
        with ExitStack() as es:
            es.enter_context(mock.patch(
                "backend.src.anchoring.config.CardanoConfig.from_env",
                return_value=_fake_config(configured=False)))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.build_chain_context", build_ctx))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.submit_anchor", submit))
            es.enter_context(mock.patch(
                "backend.src.core.db.get_session_maker", return_value=maker))

            asyncio.run(anchor_audit_chain({}))

        build_ctx.assert_not_called()   # the chain context is never even built
        submit.assert_not_called()      # nothing submitted
        assert _count_rows(maker) == 0  # no row written

    # 4 ──────────────────────────────────────────────────────────────────
    def test_job_aborts_on_chain_unreachable(self):
        from backend.src.workers.jobs import anchor_audit_chain  # RED

        maker, _ = _make_db_maker()
        submit = mock.MagicMock(name="submit_anchor")
        probe = mock.MagicMock(side_effect=ConnectionError("blockfrost unreachable"))
        with ExitStack() as es:
            es.enter_context(mock.patch(
                "backend.src.anchoring.config.CardanoConfig.from_env",
                return_value=_fake_config(configured=True)))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.build_chain_context",
                return_value=mock.MagicMock(name="chain")))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.probe_reachable", probe))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.submit_anchor", submit))
            es.enter_context(mock.patch(
                "backend.src.api.routers.audit_compliance.anchor_head",
                return_value=dict(_HEAD)))
            es.enter_context(mock.patch(
                "backend.src.core.db.get_session_maker", return_value=maker))

            # Must fail closed — abort, never raise a partial anchor up the stack.
            asyncio.run(anchor_audit_chain({}))

        probe.assert_called_once()
        submit.assert_not_called()       # never submitted
        assert _count_rows(maker) == 0   # NO 'submitted' row left stuck

    # 5 ──────────────────────────────────────────────────────────────────
    def test_idempotent_same_day_guard(self):
        from backend.src.core.orm import AnchorRecord
        from backend.src.workers.jobs import anchor_audit_chain  # RED

        maker, _ = _make_db_maker()
        # Pre-existing 'submitted' row for (workspace, today UTC).
        now = _dt.datetime.now(_dt.timezone.utc)
        with maker() as s:
            s.add(AnchorRecord(
                id="pre-existing",
                workspace_id=_WS,
                final_hash=_VALID_H,
                entry_count=5,
                anchored_at=now.isoformat(),
                tx_id=None,
                network="preprod",
                anchor_label=923350,
                status="submitted",
            ))
            s.commit()

        submit = mock.MagicMock(name="submit_anchor")
        with ExitStack() as es:
            es.enter_context(mock.patch(
                "backend.src.anchoring.config.CardanoConfig.from_env",
                return_value=_fake_config(configured=True)))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.build_chain_context",
                return_value=mock.MagicMock(name="chain")))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.probe_reachable", mock.MagicMock()))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.submit_anchor", submit))
            es.enter_context(mock.patch(
                "backend.src.api.routers.audit_compliance.anchor_head",
                return_value=dict(_HEAD)))
            es.enter_context(mock.patch(
                "backend.src.core.db.get_session_maker", return_value=maker))

            asyncio.run(anchor_audit_chain({}))

        submit.assert_not_called()       # guard short-circuits before submit
        assert _count_rows(maker) == 1   # no duplicate row created

    # 6 ──────────────────────────────────────────────────────────────────
    def test_submitted_row_written_before_submit(self):
        from backend.src.core.orm import AnchorRecord
        from backend.src.workers.jobs import anchor_audit_chain  # RED

        maker, _ = _make_db_maker()
        seen = {}

        def _submit(chain, config, payload):
            # At submit time a 'submitted' row must already exist (ordering pin).
            with maker() as s:
                rows = s.query(AnchorRecord).filter_by(status="submitted").all()
                seen["submitted_at_submit_time"] = len(rows)
            return "tx_deadbeef"

        with ExitStack() as es:
            es.enter_context(mock.patch(
                "backend.src.anchoring.config.CardanoConfig.from_env",
                return_value=_fake_config(configured=True)))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.build_chain_context",
                return_value=mock.MagicMock(name="chain")))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.probe_reachable", mock.MagicMock()))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.submit_anchor",
                mock.MagicMock(side_effect=_submit)))
            es.enter_context(mock.patch(
                "backend.src.api.routers.audit_compliance.anchor_head",
                return_value=dict(_HEAD)))
            es.enter_context(mock.patch(
                "backend.src.core.db.get_session_maker", return_value=maker))

            asyncio.run(anchor_audit_chain({}))

        assert seen.get("submitted_at_submit_time") == 1  # row written BEFORE submit
        with maker() as s:
            row = s.query(AnchorRecord).one()
        assert row.status == "confirmed"     # updated AFTER ack
        assert row.tx_id == "tx_deadbeef"    # with the returned tx id


if __name__ == "__main__":
    unittest.main()
