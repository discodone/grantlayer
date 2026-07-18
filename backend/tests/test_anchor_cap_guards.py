"""Preprod proof matrix for the fail-closed cap guards (model-A capped hot key).

Every proof here is network-free: the BlockFrost chain context, the UTxO reads,
and the TransactionBuilder are all stubbed, and address derivation is OFFLINE
(key -> vkey -> hash -> address, no HTTP). None of these tests spend anything,
generate a key, or touch mainnet. They pin the three gates + two redaction layers:

  Gate A  wallet-balance ceiling (pre-build, fail-closed on query failure)
  Gate B  expected-address pin (startup boot-refuse AND pre-submit last defense)
  Gate C  per-tx fee ceiling (post-build, pre-submit)
  R1      build/sign span sanitized to AnchorSubmitError (no raw str(exc))
  R2      CardanoConfig.__repr__ masks signing_key + blockfrost_project_id

The one row this suite deliberately does NOT run is the live on-chain preprod
submit + `verify-anchor.py --network preprod` against a real tx: that needs a
funded preprod wallet + Blockfrost credentials (a credentialed environment), not
a unit-test seam. See the module docstring note at the bottom for the exact
command to run there.
"""

from __future__ import annotations

import os

# pycardano 0.19.2 refuses to import without this; set before the first import.
os.environ.setdefault("CBOR_C_EXTENSION", "1")

import asyncio
import tempfile
import types
import unittest
from contextlib import ExitStack
from unittest import mock

# Deterministic THROWAWAY test key (fixed 32-byte seed 00,01,...,1f). NOT funded,
# NOT real. Same key/address the address regression test pins, reused here so the
# expected-address proofs are anchored to a known-good value.
_SKEY_JSON = (
    '{"type": "PaymentSigningKeyShelley_ed25519", '
    '"description": "PaymentSigningKeyShelley_ed25519", '
    '"cborHex": "5820000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"}'
)
_PREPROD_ADDR = "addr_test1vqn78rgwr835xn3nl0gqr5l7qj6mwemrlz9v6cj7p4mskscud5urh"

_WS = "22222222-2222-2222-2222-222222222222"
_VALID_H = "a" * 64
_HEAD = {"final_hash": _VALID_H, "entry_count": 5}


def _cfg(**overrides):
    """Build a real CardanoConfig (preprod defaults) with per-test overrides."""
    from backend.src.anchoring.config import CardanoConfig

    base = dict(
        enabled=True,
        blockfrost_project_id="preprodPID",
        signing_key=_SKEY_JSON,
        workspace_id=_WS,
        network="preprod",
        max_wallet_lovelace=None,
        max_fee_lovelace=None,
        expected_address=None,
    )
    base.update(overrides)
    return CardanoConfig(**base)


def _payload():
    from backend.src.anchoring.models import AnchorPayload

    return AnchorPayload(h=_VALID_H, s=5, t="2026-07-16T02:00:00Z")


def _signed_with_fee(fee: int):
    """A stand-in signed tx exposing only transaction_body.fee (Gate C reads it)."""
    return types.SimpleNamespace(transaction_body=types.SimpleNamespace(fee=fee))


def _fee_builder(fee: int):
    """A stub TransactionBuilder whose build_and_sign yields a tx with `fee`."""

    class _Builder:
        def __init__(self, ctx):
            self.auxiliary_data = None

        def add_input_address(self, address):
            pass

        def build_and_sign(self, signing_keys, change_address=None):
            return _signed_with_fee(fee)

    return _Builder


def _utxo(coin: int):
    return types.SimpleNamespace(
        output=types.SimpleNamespace(amount=types.SimpleNamespace(coin=coin))
    )


def _make_db_maker():
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


# =========================================================================== #
# Gate C — per-tx fee ceiling                                                 #
# =========================================================================== #
class TestGateCFeeCeiling(unittest.TestCase):
    def test_refuses_when_fee_exceeds_ceiling(self):
        """Artificially LOW ceiling => REFUSE before submit (nothing on chain)."""
        from backend.src.anchoring import writer

        ctx = mock.MagicMock(name="ChainContext")
        cfg = _cfg(max_fee_lovelace=100_000)  # below the 200_000 the tx will cost
        with mock.patch("pycardano.TransactionBuilder", _fee_builder(200_000)):
            with self.assertRaises(writer.AnchorFeeExceeded):
                writer.submit_anchor(ctx, cfg, _payload())
        ctx.submit_tx.assert_not_called()  # the irreversible line is never reached

    def test_allows_when_fee_within_ceiling(self):
        """Real-value ceiling (1.0 ADA) => normal anchor submits once."""
        from backend.src.anchoring import writer

        ctx = mock.MagicMock(name="ChainContext")
        ctx.submit_tx.return_value = "tx_ok_within_fee"
        cfg = _cfg(max_fee_lovelace=1_000_000)  # 1.0 ADA ceiling
        with mock.patch("pycardano.TransactionBuilder", _fee_builder(175_000)):
            tx = writer.submit_anchor(ctx, cfg, _payload())
        self.assertEqual(tx, "tx_ok_within_fee")
        ctx.submit_tx.assert_called_once()


# =========================================================================== #
# Gate A — wallet-balance ceiling + fail-closed balance query                 #
# =========================================================================== #
class TestGateAWalletCeiling(unittest.TestCase):
    def test_read_wallet_lovelace_sums_utxos_read_only(self):
        """Balance read sums UTxO coin and NEVER submits/signs (read-only)."""
        from backend.src.anchoring import writer

        ctx = mock.MagicMock(name="ChainContext")
        ctx.utxos.return_value = [_utxo(5_000_000), _utxo(20_000_000)]
        total = writer.read_wallet_lovelace(ctx, _cfg())
        self.assertEqual(total, 25_000_000)
        ctx.submit_tx.assert_not_called()  # no spend
        ctx.utxos.assert_called_once_with(_PREPROD_ADDR)  # queried the right wallet

    def test_read_wallet_lovelace_propagates_query_failure(self):
        """A broken UTxO endpoint must PROPAGATE (so the job can fail closed)."""
        from backend.src.anchoring import writer

        ctx = mock.MagicMock(name="ChainContext")
        ctx.utxos.side_effect = ConnectionError("koios/blockfrost unreachable")
        with self.assertRaises(ConnectionError):
            writer.read_wallet_lovelace(ctx, _cfg())

    def test_job_aborts_when_overfunded(self):
        """Balance above ceiling => ABORT, no submit, no row."""
        from backend.src.workers.jobs import anchor_audit_chain

        maker = _make_db_maker()
        submit = mock.MagicMock(name="submit_anchor")
        # cap 50 ADA, wallet holds 80 ADA => over-funded / wrong wallet
        cfg = _cfg(max_wallet_lovelace=50_000_000)
        with ExitStack() as es:
            es.enter_context(mock.patch(
                "backend.src.anchoring.config.CardanoConfig.from_env", return_value=cfg))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.build_chain_context",
                return_value=mock.MagicMock(name="chain")))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.probe_reachable", mock.MagicMock()))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.read_wallet_lovelace", return_value=80_000_000))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.submit_anchor", submit))
            es.enter_context(mock.patch(
                "backend.src.api.routers.audit_compliance.anchor_head",
                return_value=dict(_HEAD)))
            es.enter_context(mock.patch(
                "backend.src.core.db.get_session_maker", return_value=maker))
            result = asyncio.run(anchor_audit_chain({}))

        self.assertEqual(result["status"], "aborted_overfunded_or_wrong_wallet")
        submit.assert_not_called()
        self.assertEqual(_count_rows(maker), 0)  # no 'submitted' row written

    def test_job_aborts_when_balance_query_fails(self):
        """Fail-closed: balance query raises => ABORT ('balance_unavailable'),
        never proceed blind to submit."""
        from backend.src.workers.jobs import anchor_audit_chain

        maker = _make_db_maker()
        submit = mock.MagicMock(name="submit_anchor")
        cfg = _cfg(max_wallet_lovelace=50_000_000)
        with ExitStack() as es:
            es.enter_context(mock.patch(
                "backend.src.anchoring.config.CardanoConfig.from_env", return_value=cfg))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.build_chain_context",
                return_value=mock.MagicMock(name="chain")))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.probe_reachable", mock.MagicMock()))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.read_wallet_lovelace",
                side_effect=TimeoutError("balance endpoint timed out")))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.submit_anchor", submit))
            es.enter_context(mock.patch(
                "backend.src.api.routers.audit_compliance.anchor_head",
                return_value=dict(_HEAD)))
            es.enter_context(mock.patch(
                "backend.src.core.db.get_session_maker", return_value=maker))
            result = asyncio.run(anchor_audit_chain({}))

        self.assertEqual(result["status"], "aborted_balance_unavailable")
        submit.assert_not_called()
        self.assertEqual(_count_rows(maker), 0)


# =========================================================================== #
# Gate B — expected-address pin (startup boot-refuse + pre-submit) + collision #
# =========================================================================== #
class TestGateBExpectedAddress(unittest.TestCase):
    def test_startup_error_on_wrong_expected_address(self):
        cfg = _cfg(expected_address="addr_test1_wrong_pin_value")
        errs = cfg.startup_errors()
        self.assertTrue(any("does not match" in e for e in errs))

    def test_startup_ok_on_correct_expected_address(self):
        cfg = _cfg(expected_address=_PREPROD_ADDR)
        # Fully configured + correct pin => no startup errors at all.
        self.assertEqual(cfg.startup_errors(), [])

    def test_startup_error_on_unloadable_key(self):
        cfg = _cfg(signing_key="not-a-valid-skey", expected_address=_PREPROD_ADDR)
        errs = cfg.startup_errors()
        self.assertTrue(any("cannot derive" in e for e in errs))
        # The message must never contain the (bogus) key material.
        self.assertFalse(any("not-a-valid-skey" in e for e in errs))

    def test_worker_refuses_to_boot_on_mismatch(self):
        from backend.src.workers import worker

        with mock.patch(
            "backend.src.workers.worker.CardanoConfig.from_env",
            return_value=_cfg(expected_address="addr_test1_wrong"),
        ):
            with self.assertRaises(RuntimeError):
                worker._validate_anchor_startup()

    def test_worker_boots_on_correct_pin(self):
        from backend.src.workers import worker

        with mock.patch(
            "backend.src.workers.worker.CardanoConfig.from_env",
            return_value=_cfg(expected_address=_PREPROD_ADDR),
        ):
            worker._validate_anchor_startup()  # must NOT raise

    def test_presubmit_gate_b_aborts_on_mismatch(self):
        """Even if startup were bypassed, submit_anchor re-checks the pin and
        refuses BEFORE submit."""
        from backend.src.anchoring import writer

        ctx = mock.MagicMock(name="ChainContext")
        cfg = _cfg(expected_address="addr_test1_wrong_pin")
        with mock.patch("pycardano.TransactionBuilder", _fee_builder(175_000)):
            with self.assertRaises(writer.AnchorAddressMismatch):
                writer.submit_anchor(ctx, cfg, _payload())
        ctx.submit_tx.assert_not_called()

    def test_collision_preprod_key_under_mainnet_tag_offline(self):
        """OFFLINE collision proof: the preprod key under a mainnet network tag
        derives an addr1... address, which cannot match a pinned addr_test...
        value — so the guard refuses. No network call whatsoever."""
        from backend.src.anchoring import writer

        mainnet_cfg = _cfg(network="mainnet")
        derived_mainnet = writer.derive_address(mainnet_cfg)
        # Mainnet tag yields the mainnet prefix...
        self.assertTrue(derived_mainnet.startswith("addr1"))
        # ...which can never equal the pinned preprod (addr_test) address.
        self.assertNotEqual(derived_mainnet, _PREPROD_ADDR)
        # And pinning the preprod address while running mainnet is a startup error
        # (this is exactly the preprod-key-under-mainnet-config collision).
        collide = _cfg(
            network="mainnet",
            expected_address=_PREPROD_ADDR,
            max_wallet_lovelace=50_000_000,
            max_fee_lovelace=1_000_000,
        )
        errs = collide.startup_errors()
        self.assertTrue(any("does not match" in e for e in errs))


# =========================================================================== #
# Redaction layers                                                            #
# =========================================================================== #
class TestRedaction(unittest.TestCase):
    _MARKER = "SUPER_SECRET_KEY_MATERIAL_abc123"

    def test_build_sign_failure_is_sanitized(self):
        """A raw exception in build_and_sign (carrying a key marker) must surface
        ONLY as AnchorSubmitError with the type name — never the marker."""
        from backend.src.anchoring import writer

        marker = self._MARKER

        class _Boom:
            def __init__(self, ctx):
                self.auxiliary_data = None

            def add_input_address(self, address):
                pass

            def build_and_sign(self, signing_keys, change_address=None):
                raise ValueError(marker)

        ctx = mock.MagicMock(name="ChainContext")
        with mock.patch("pycardano.TransactionBuilder", _Boom):
            with self.assertRaises(writer.AnchorSubmitError) as cm:
                writer.submit_anchor(ctx, _cfg(), _payload())
        msg = str(cm.exception)
        self.assertIn("ValueError", msg)          # curated type name present
        self.assertNotIn(self._MARKER, msg)        # marker NOT leaked
        # The original (marker-bearing) exception must be dropped from the chain.
        self.assertIsNone(cm.exception.__cause__)
        self.assertTrue(cm.exception.__suppress_context__)
        ctx.submit_tx.assert_not_called()

    def test_load_signing_key_failure_is_sanitized(self):
        from backend.src.anchoring import writer

        ctx = mock.MagicMock(name="ChainContext")
        with mock.patch(
            "backend.src.anchoring.writer.load_signing_key",
            side_effect=RuntimeError(self._MARKER),
        ):
            with self.assertRaises(writer.AnchorSubmitError) as cm:
                writer.submit_anchor(ctx, _cfg(), _payload())
        self.assertNotIn(self._MARKER, str(cm.exception))
        ctx.submit_tx.assert_not_called()

    def test_config_repr_redacts_secrets(self):
        cfg = _cfg(
            signing_key="SECRET_SKEY_" + self._MARKER,
            blockfrost_project_id="SECRET_PID_" + self._MARKER,
        )
        r = repr(cfg)
        self.assertNotIn("SECRET_SKEY", r)
        self.assertNotIn("SECRET_PID", r)
        self.assertNotIn(self._MARKER, r)
        self.assertIn("<redacted>", r)
        # Non-secret fields still visible for diagnostics.
        self.assertIn("network=", r)

    def test_job_submit_failure_returns_type_name_not_raw(self):
        """The job's returned error field must be a type name, never a raw
        (possibly key-bearing) exception string."""
        from backend.src.workers.jobs import anchor_audit_chain

        maker = _make_db_maker()
        with ExitStack() as es:
            es.enter_context(mock.patch(
                "backend.src.anchoring.config.CardanoConfig.from_env", return_value=_cfg()))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.build_chain_context",
                return_value=mock.MagicMock(name="chain")))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.probe_reachable", mock.MagicMock()))
            es.enter_context(mock.patch(
                "backend.src.anchoring.writer.submit_anchor",
                side_effect=Exception(self._MARKER)))
            es.enter_context(mock.patch(
                "backend.src.api.routers.audit_compliance.anchor_head",
                return_value=dict(_HEAD)))
            es.enter_context(mock.patch(
                "backend.src.core.db.get_session_maker", return_value=maker))
            result = asyncio.run(anchor_audit_chain({}))

        self.assertEqual(result["status"], "submit_failed")
        self.assertEqual(result["error"], "Exception")
        self.assertNotIn(self._MARKER, str(result))


# =========================================================================== #
# Startup requirements — no enabled-but-uncapped mainnet                      #
# =========================================================================== #
class TestMainnetStartupRequirements(unittest.TestCase):
    def test_mainnet_requires_all_three_caps(self):
        cfg = _cfg(network="mainnet", expected_address=None,
                   max_wallet_lovelace=None, max_fee_lovelace=None)
        errs = cfg.startup_errors()
        self.assertTrue(any("MAX_WALLET_LOVELACE" in e for e in errs))
        self.assertTrue(any("MAX_FEE_LOVELACE" in e for e in errs))
        self.assertTrue(any("EXPECTED_ADDRESS" in e for e in errs))

    def test_mainnet_fully_capped_and_pinned_has_no_errors(self):
        cfg = _cfg(
            network="mainnet",
            expected_address=None,  # filled below with the real mainnet address
            max_wallet_lovelace=50_000_000,
            max_fee_lovelace=1_000_000,
        )
        from backend.src.anchoring import writer

        mainnet_addr = writer.derive_address(cfg)
        cfg = _cfg(
            network="mainnet",
            expected_address=mainnet_addr,
            max_wallet_lovelace=50_000_000,
            max_fee_lovelace=1_000_000,
            min_anchor_events=3,
        )
        self.assertEqual(cfg.startup_errors(), [])

    def test_preprod_allows_uncapped(self):
        """Preprod is free to run uncapped (mistakes are free) — no requirement."""
        cfg = _cfg(network="preprod")
        self.assertEqual(cfg.startup_errors(), [])


# =========================================================================== #
# Happy path — guards active but non-blocking                                 #
# =========================================================================== #
class TestHappyPath(unittest.TestCase):
    def test_writer_happy_path_all_gates_pass(self):
        """All three gates active and satisfied => submit happens exactly once."""
        from backend.src.anchoring import writer

        ctx = mock.MagicMock(name="ChainContext")
        ctx.submit_tx.return_value = "tx_happy"
        cfg = _cfg(expected_address=_PREPROD_ADDR, max_fee_lovelace=1_000_000)
        with mock.patch("pycardano.TransactionBuilder", _fee_builder(175_000)):
            tx = writer.submit_anchor(ctx, cfg, _payload())
        self.assertEqual(tx, "tx_happy")
        ctx.submit_tx.assert_called_once()

    def test_job_happy_path_then_idempotent_skip(self):
        """Full daily job with Gate A active: first run confirms, second run
        same UTC day is an idempotency skip (guards don't break normal op)."""
        from backend.src.core.orm import AnchorRecord
        from backend.src.workers.jobs import anchor_audit_chain

        maker = _make_db_maker()
        cfg = _cfg(max_wallet_lovelace=50_000_000, max_fee_lovelace=1_000_000,
                   expected_address=_PREPROD_ADDR)

        def _patches(stack):
            stack.enter_context(mock.patch(
                "backend.src.anchoring.config.CardanoConfig.from_env", return_value=cfg))
            stack.enter_context(mock.patch(
                "backend.src.anchoring.writer.build_chain_context",
                return_value=mock.MagicMock(name="chain")))
            stack.enter_context(mock.patch(
                "backend.src.anchoring.writer.probe_reachable", mock.MagicMock()))
            stack.enter_context(mock.patch(
                "backend.src.anchoring.writer.read_wallet_lovelace", return_value=25_000_000))
            stack.enter_context(mock.patch(
                "backend.src.anchoring.writer.submit_anchor", return_value="tx_daily"))
            stack.enter_context(mock.patch(
                "backend.src.api.routers.audit_compliance.anchor_head",
                return_value=dict(_HEAD)))
            stack.enter_context(mock.patch(
                "backend.src.core.db.get_session_maker", return_value=maker))

        with ExitStack() as es:
            _patches(es)
            first = asyncio.run(anchor_audit_chain({}))
        self.assertEqual(first["status"], "confirmed")
        self.assertEqual(first["tx_id"], "tx_daily")

        with ExitStack() as es:
            _patches(es)
            second = asyncio.run(anchor_audit_chain({}))
        self.assertEqual(second["status"], "skipped_already_anchored_today")

        with maker() as s:
            self.assertEqual(s.query(AnchorRecord).count(), 1)  # exactly one anchor


if __name__ == "__main__":
    unittest.main(verbosity=2)
