"""Regression: submit_anchor must build the source/change Address with the
network as a KEYWORD argument.

The first real preprod submit failed-closed because ``submit_anchor`` built the
wallet address as ``Address(vk.hash(), network)`` — pycardano's second positional
parameter is ``staking_part``, not ``network``, so a Network enum was handed in as
the stake credential and pycardano raised ``InvalidAddressInputException`` before
any chain interaction. These tests pin the fix (``network=network``) and the exact
trap, fully network-free (the TransactionBuilder and chain context are mocked).
"""

from __future__ import annotations

import os

# pycardano 0.19.2 refuses to import without this; set before the first import.
os.environ.setdefault("CBOR_C_EXTENSION", "1")

import unittest
from unittest import mock

# Deterministic THROWAWAY test key from a fixed 32-byte seed (00,01,...,1f).
# Not a real or funded wallet — only used to pin the derived address form.
_SKEY_JSON = (
    '{"type": "PaymentSigningKeyShelley_ed25519", '
    '"description": "PaymentSigningKeyShelley_ed25519", '
    '"cborHex": "5820000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"}'
)
# The enterprise (no staking part) TESTNET address for that key. A mainnet build
# would start with "addr1"; a positional-network build never gets this far.
_EXPECTED_ADDR = "addr_test1vqn78rgwr835xn3nl0gqr5l7qj6mwemrlz9v6cj7p4mskscud5urh"


class _CapturingBuilder:
    """Stand-in TransactionBuilder that records the addresses submit_anchor uses."""

    last: dict = {}

    def __init__(self, ctx):
        self.auxiliary_data = None

    def add_input_address(self, address):
        _CapturingBuilder.last["input"] = address

    def build_and_sign(self, signing_keys, change_address=None):
        _CapturingBuilder.last["change"] = change_address
        return "signed-tx-object"


class TestSubmitAnchorAddress(unittest.TestCase):
    def _config(self):
        cfg = mock.MagicMock(name="CardanoConfig")
        cfg.signing_key = _SKEY_JSON
        cfg.network = "preprod"
        return cfg

    def test_submit_anchor_uses_expected_enterprise_testnet_address(self):
        """submit_anchor must build both the input and change address as the
        enterprise TESTNET address for the key — i.e. network went to the network
        parameter, not staking_part. On the pre-fix positional code this raised
        InvalidAddressInputException before the builder was ever reached."""
        from backend.src.anchoring import writer
        from backend.src.anchoring.models import AnchorPayload

        payload = AnchorPayload(h="a" * 64, s=5, t="2026-07-14T11:18:01.574059Z")
        ctx = mock.MagicMock(name="ChainContext")
        ctx.submit_tx.return_value = "tx-hash-123"

        _CapturingBuilder.last = {}
        with mock.patch("pycardano.TransactionBuilder", _CapturingBuilder):
            tx_id = writer.submit_anchor(ctx, self._config(), payload)

        self.assertEqual(tx_id, "tx-hash-123")
        self.assertEqual(str(_CapturingBuilder.last["input"]), _EXPECTED_ADDR)
        self.assertEqual(str(_CapturingBuilder.last["change"]), _EXPECTED_ADDR)
        # Preprod, never mainnet.
        self.assertTrue(str(_CapturingBuilder.last["input"]).startswith("addr_test1"))

    def test_address_built_is_enterprise_no_staking_part(self):
        """The derived address must have NO staking part. A leaked network-as-
        staking_part would either raise or produce a different address; a correct
        enterprise address proves the network is in the right slot."""
        from pycardano import (
            Address,
            Network,
            PaymentVerificationKey,
        )

        from backend.src.anchoring import writer

        sk = writer.load_signing_key(_SKEY_JSON)
        vk = PaymentVerificationKey.from_signing_key(sk)
        addr = Address(vk.hash(), network=Network.TESTNET)
        self.assertIsNone(addr.staking_part)
        self.assertEqual(str(addr), _EXPECTED_ADDR)

    def test_positional_network_is_the_trap(self):
        """Documents the exact defect: passing Network positionally lands it in
        staking_part and pycardano rejects it. Keyword form is required."""
        from pycardano import (
            Address,
            InvalidAddressInputException,
            Network,
            PaymentVerificationKey,
        )

        from backend.src.anchoring import writer

        sk = writer.load_signing_key(_SKEY_JSON)
        vk = PaymentVerificationKey.from_signing_key(sk)
        with self.assertRaises(InvalidAddressInputException):
            Address(vk.hash(), Network.TESTNET)  # positional == staking_part → rejected


if __name__ == "__main__":
    unittest.main(verbosity=2)
