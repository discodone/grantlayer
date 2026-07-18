"""Empty-chain anchor guard — the writer must refuse a below-minimum chain.

Fully network-free: chain context, probe, balance and submit are mocked; the
head read is stubbed. The guard under proof:

  * The daily anchor job refuses, fail-closed, to anchor a chain whose event
    count is below the configured minimum — BEFORE the chain context is even
    built (i.e. before the reachability probe and Gates A/B/C), and before any
    'submitted' row is written. Refusal is an explicit, distinct error
    (writer.AnchorChainTooShort → job status "refused_chain_below_minimum"),
    never a silent skip.
  * anchor_head() query failure aborts the job (same fail-closed posture as
    the balance guard) — never proceed blind, never build, never submit.
  * CardanoConfig grows min_anchor_events (GRANTLAYER_CARDANO_MIN_ANCHOR_EVENTS);
    on mainnet it is REQUIRED and must be >= 3 (three genesis events exist by
    construction — anything below is definitionally an empty/wrong chain).
    Non-mainnet defaults to an effective minimum of 1.

Self-provisions SQLite (listed in _sqlite_only_modules.py).
"""

from __future__ import annotations

import os

# pycardano 0.19.2 refuses to import without this; set before the first import.
os.environ.setdefault("CBOR_C_EXTENSION", "1")

import asyncio
import tempfile
import unittest
from contextlib import ExitStack
from unittest import mock

_WS = "33333333-3333-3333-3333-333333333333"
_VALID_H = "b" * 64
_EMPTY_H = "0" * 64


def _cfg(**overrides):
    """Build a real CardanoConfig (preprod defaults) with per-test overrides."""
    from backend.src.anchoring.config import CardanoConfig

    base = dict(
        enabled=True,
        blockfrost_project_id="preprodPID",
        signing_key='{"type":"x","cborHex":"00"}',
        workspace_id=_WS,
        network="preprod",
        max_wallet_lovelace=None,
        max_fee_lovelace=None,
        expected_address=None,
    )
    base.update(overrides)
    return CardanoConfig(**base)


def _make_db_maker():
    """Temp-file SQLite sessionmaker with all ORM tables created."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.src.core.orm import Base

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _count_rows(maker):
    from backend.src.core.orm import AnchorRecord

    with maker() as s:
        return s.query(AnchorRecord).count()


def _run_job(cfg, head, maker):
    """Run anchor_audit_chain with every network seam spied; return (result, spies)."""
    from backend.src.workers.jobs import anchor_audit_chain

    build_ctx = mock.MagicMock(name="build_chain_context",
                               return_value=mock.MagicMock(name="chain"))
    probe = mock.MagicMock(name="probe_reachable")
    submit = mock.MagicMock(name="submit_anchor", return_value="tx_min_chain")
    with ExitStack() as es:
        es.enter_context(mock.patch(
            "backend.src.anchoring.config.CardanoConfig.from_env", return_value=cfg))
        es.enter_context(mock.patch(
            "backend.src.anchoring.writer.build_chain_context", build_ctx))
        es.enter_context(mock.patch(
            "backend.src.anchoring.writer.probe_reachable", probe))
        es.enter_context(mock.patch(
            "backend.src.anchoring.writer.submit_anchor", submit))
        if isinstance(head, Exception):
            es.enter_context(mock.patch(
                "backend.src.api.routers.audit_compliance.anchor_head",
                side_effect=head))
        else:
            es.enter_context(mock.patch(
                "backend.src.api.routers.audit_compliance.anchor_head",
                return_value=dict(head)))
        es.enter_context(mock.patch(
            "backend.src.core.db.get_session_maker", return_value=maker))
        result = asyncio.run(anchor_audit_chain({}))
    return result, {"build_ctx": build_ctx, "probe": probe, "submit": submit}


# =========================================================================== #
# Job refusal — the choke point sits BEFORE the chain context / Gates A/B/C   #
# =========================================================================== #
class TestJobRefusesShortChain(unittest.TestCase):
    def test_empty_chain_refused_nothing_built_or_submitted(self):
        """0 events => refused with the distinct status; the chain context is
        never built (no probe, no Gate A/B/C), nothing submitted, no row."""
        maker = _make_db_maker()
        result, spies = _run_job(
            _cfg(), {"final_hash": _EMPTY_H, "entry_count": 0}, maker)

        self.assertEqual(result["status"], "refused_chain_below_minimum")
        self.assertIn("error", result)  # operator-visible reason, not a silent skip
        spies["build_ctx"].assert_not_called()  # refused BEFORE any tx machinery
        spies["probe"].assert_not_called()
        spies["submit"].assert_not_called()
        self.assertEqual(_count_rows(maker), 0)

    def test_below_configured_minimum_refused(self):
        """count < min_anchor_events => refused (2 < 3)."""
        maker = _make_db_maker()
        result, spies = _run_job(
            _cfg(min_anchor_events=3),
            {"final_hash": _VALID_H, "entry_count": 2}, maker)

        self.assertEqual(result["status"], "refused_chain_below_minimum")
        spies["build_ctx"].assert_not_called()
        spies["submit"].assert_not_called()
        self.assertEqual(_count_rows(maker), 0)

    def test_at_minimum_proceeds_past_guard(self):
        """count == min_anchor_events => the guard lets the job continue and the
        (stubbed) submit path completes."""
        maker = _make_db_maker()
        result, spies = _run_job(
            _cfg(min_anchor_events=3),
            {"final_hash": _VALID_H, "entry_count": 3}, maker)

        self.assertEqual(result["status"], "confirmed")
        spies["submit"].assert_called_once()

    def test_head_query_failure_aborts_fail_closed(self):
        """anchor_head() raising => abort (same posture as the balance guard):
        no chain context, no submit, no row."""
        maker = _make_db_maker()
        result, spies = _run_job(
            _cfg(), RuntimeError("audit query failed"), maker)

        self.assertEqual(result["status"], "aborted_head_unavailable")
        spies["build_ctx"].assert_not_called()
        spies["submit"].assert_not_called()
        self.assertEqual(_count_rows(maker), 0)


# =========================================================================== #
# Writer guard — explicit, distinct exception                                 #
# =========================================================================== #
class TestWriterGuard(unittest.TestCase):
    def test_short_chain_raises_distinct_exception(self):
        from backend.src.anchoring import writer

        with self.assertRaises(writer.AnchorChainTooShort) as caught:
            writer.assert_chain_anchorable(
                {"final_hash": _EMPTY_H, "entry_count": 0}, _cfg(min_anchor_events=3))
        msg = str(caught.exception)
        self.assertIn("0", msg)  # the operator sees the actual count...
        self.assertIn("3", msg)  # ...and the minimum it fell below

    def test_distinct_type_not_a_submit_error(self):
        """Its own exception type — distinguishable from the build/sign span."""
        from backend.src.anchoring import writer

        self.assertFalse(issubclass(writer.AnchorChainTooShort, writer.AnchorSubmitError))

    def test_at_minimum_passes(self):
        from backend.src.anchoring import writer

        writer.assert_chain_anchorable(
            {"final_hash": _VALID_H, "entry_count": 3}, _cfg(min_anchor_events=3))


# =========================================================================== #
# Config — GRANTLAYER_CARDANO_MIN_ANCHOR_EVENTS + mainnet startup requirement #
# =========================================================================== #
class TestMinAnchorEventsConfig(unittest.TestCase):
    def test_mainnet_unset_is_a_startup_error(self):
        cfg = _cfg(network="mainnet", min_anchor_events=None)
        errs = cfg.startup_errors()
        self.assertTrue(any("MIN_ANCHOR_EVENTS" in e for e in errs))

    def test_mainnet_below_three_is_a_startup_error(self):
        cfg = _cfg(network="mainnet", min_anchor_events=2)
        errs = cfg.startup_errors()
        self.assertTrue(any("MIN_ANCHOR_EVENTS" in e for e in errs))

    def test_mainnet_three_is_accepted(self):
        cfg = _cfg(network="mainnet", min_anchor_events=3)
        errs = cfg.startup_errors()
        self.assertFalse(any("MIN_ANCHOR_EVENTS" in e for e in errs))

    def test_non_mainnet_defaults_to_effective_minimum_one(self):
        """Preprod without the knob: effective minimum 1 (dev ergonomics) — an
        empty chain is still refused, a 1-event chain anchors."""
        cfg = _cfg(network="preprod", min_anchor_events=None)
        self.assertEqual(cfg.effective_min_anchor_events, 1)
        self.assertEqual(cfg.startup_errors(), [])  # not required off-mainnet

    def test_from_env_parses_min_anchor_events(self):
        from backend.src.anchoring.config import CardanoConfig

        with mock.patch.dict(os.environ, {
            "GRANTLAYER_ENABLE_CARDANO_ANCHORING": "true",
            "GRANTLAYER_CARDANO_MIN_ANCHOR_EVENTS": "7",
        }):
            cfg = CardanoConfig.from_env()
        self.assertEqual(cfg.min_anchor_events, 7)
        self.assertEqual(cfg.effective_min_anchor_events, 7)

    def test_from_env_unset_is_none(self):
        from backend.src.anchoring.config import CardanoConfig

        env = {k: v for k, v in os.environ.items()
               if k != "GRANTLAYER_CARDANO_MIN_ANCHOR_EVENTS"}
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = CardanoConfig.from_env()
        self.assertIsNone(cfg.min_anchor_events)


if __name__ == "__main__":
    unittest.main()
