"""Defense-in-depth: the writer fee guard still fires below the constraint layer.

The signed max_fee_lovelace grant constraint is enforced at exercise time
against a DECLARED attempt. It is a layer ABOVE the deployment-level anchor
writer guard (Gate C, anchoring/writer.py), which inspects the ACTUAL fee of
the built transaction and refuses to submit over the env-configured ceiling.
This test simulates the constraint layer being bypassed entirely — the writer
path is called directly with an over-limit fee — and pins that the backstop
still denies. The writer guard is deliberately UNTOUCHED by the grant-policy
slice: the signed constraint replaces nothing.

Network-free (same seams as test_anchor_cap_guards): stubbed chain context and
TransactionBuilder, offline key derivation, nothing is spent.
"""

from __future__ import annotations

import os

# pycardano 0.19.2 refuses to import without this; set before the first import.
os.environ.setdefault("CBOR_C_EXTENSION", "1")

import types
import unittest
from unittest import mock

# Deterministic THROWAWAY test key (fixed 32-byte seed). NOT funded, NOT real.
_SKEY_JSON = (
    '{"type": "PaymentSigningKeyShelley_ed25519", '
    '"description": "PaymentSigningKeyShelley_ed25519", '
    '"cborHex": "5820000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"}'
)
_WS = "22222222-2222-2222-2222-222222222222"
_VALID_H = "a" * 64


def _cfg(**overrides):
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


def _fee_builder(fee: int):
    class _Builder:
        def __init__(self, ctx):
            self.auxiliary_data = None

        def add_input_address(self, address):
            pass

        def build_and_sign(self, signing_keys, change_address=None):
            return types.SimpleNamespace(
                transaction_body=types.SimpleNamespace(fee=fee)
            )

    return _Builder


class TestWriterFeeGuardIsStillTheBackstop(unittest.TestCase):
    def test_over_limit_fee_refused_even_without_constraint_layer(self):
        """Constraint layer bypassed (writer called directly) => Gate C denies."""
        from backend.src.anchoring import writer

        ctx = mock.MagicMock(name="ChainContext")
        cfg = _cfg(max_fee_lovelace=200_000)
        with mock.patch("pycardano.TransactionBuilder", _fee_builder(200_001)):
            with self.assertRaises(writer.AnchorFeeExceeded):
                writer.submit_anchor(ctx, cfg, _payload())
        ctx.submit_tx.assert_not_called()

    def test_within_limit_fee_still_submits(self):
        from backend.src.anchoring import writer

        ctx = mock.MagicMock(name="ChainContext")
        ctx.submit_tx.return_value = "tx_ok"
        cfg = _cfg(max_fee_lovelace=200_000)
        with mock.patch("pycardano.TransactionBuilder", _fee_builder(199_999)):
            tx = writer.submit_anchor(ctx, cfg, _payload())
        self.assertEqual(tx, "tx_ok")
        ctx.submit_tx.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
