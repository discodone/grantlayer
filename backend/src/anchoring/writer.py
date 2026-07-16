"""Cardano anchor writer.

Thin, mockable seams around the minimal PyCardano call sequence that builds,
signs, and submits the metadata-only anchoring transaction. The actual
``pycardano`` / ``blockfrost`` imports are LAZY (inside the functions) so that:
  * importing this module never drags in the heavy Cardano stack, and
  * the daily worker job can be unit-tested fully network-free by patching
    ``build_chain_context`` / ``probe_reachable`` / ``submit_anchor``.

PyCardano 0.19.2 import prerequisite (see requirements.txt): the process MUST run
with ``CBOR_C_EXTENSION=1`` and ``cbor2==5.6.5`` or pycardano crashes at import.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .config import CardanoConfig
from .models import AnchorPayload


class AnchorSubmitError(Exception):
    """Sanitized failure of the key-touching build/sign span.

    Carries ONLY a curated, key-free summary (``type(exc).__name__``) so a raw
    pycardano exception — whose repr is not proven key-safe — can never be
    stringified into a log or traceback that reaches the caller.
    """


class AnchorAddressMismatch(Exception):
    """Gate B: the derived wallet address does not match the pinned address."""


class AnchorFeeExceeded(Exception):
    """Gate C: the built transaction's fee exceeds the configured ceiling."""


def head_to_payload(head: dict[str, Any], now: datetime) -> AnchorPayload:
    """Map an ``anchor_head`` result + a timestamp into a validated AnchorPayload.

    Reuses AnchorPayload's construction validation (64-hex, no ``0x`` prefix,
    non-negative count) — a malformed head can never reach the chain.
    """
    t = now.isoformat().replace("+00:00", "Z")
    return AnchorPayload(h=head["final_hash"], s=head["entry_count"], t=t)


def build_chain_context(config: CardanoConfig) -> Any:
    """Construct a BlockFrostChainContext for the configured network.

    base_url is set EXPLICITLY (pycardano #353: otherwise it can resolve mainnet).
    """
    from blockfrost import ApiUrls
    from pycardano import BlockFrostChainContext

    base_url = (
        ApiUrls.mainnet.value if config.network == "mainnet" else ApiUrls.preprod.value
    )
    return BlockFrostChainContext(config.blockfrost_project_id, base_url=base_url)


def probe_reachable(ctx: Any) -> None:
    """Fail-closed reachability probe — raise if the chain backend is unreachable.

    Performs one cheap read against the backend; any failure propagates so the
    caller aborts BEFORE writing a 'submitted' row (never leave a partial anchor).
    """
    # epoch_latest() is a minimal authenticated read against Blockfrost.
    ctx.api.epoch_latest()


def derive_address(config: CardanoConfig) -> str:
    """Derive the bech32 wallet address from the loaded signing key. OFFLINE.

    No network call — key → verification key → key hash → address. Used by the
    startup binding check (Gate B) and the balance guard (Gate A). The network tag
    comes from ``config.network`` so a preprod key yields ``addr_test…`` and a
    mainnet key yields ``addr…`` — the prefix alone catches a network/key mismatch.
    """
    from pycardano import Address, Network, PaymentVerificationKey

    sk = load_signing_key(config.signing_key or "")
    vk = PaymentVerificationKey.from_signing_key(sk)
    network = Network.MAINNET if config.network == "mainnet" else Network.TESTNET
    return str(Address(vk.hash(), network=network))


def read_wallet_lovelace(ctx: Any, config: CardanoConfig) -> int:
    """Sum lovelace across the wallet's UTxOs. READ-ONLY (no spend, no signing).

    One ``GET addresses/{addr}/utxos`` via the chain context. Any failure
    propagates so the caller can fail closed: no balance confirmation ⇒ no submit.
    """
    address = derive_address(config)
    total = 0
    for utxo in ctx.utxos(address):
        total += int(utxo.output.amount.coin)
    return total


def submit_anchor(ctx: Any, config: CardanoConfig, payload: AnchorPayload) -> str:
    """Build, sign and submit the metadata-only anchoring tx. Returns the tx id.

    Metadata-only: no outputs; the sender funds the fee and receives the change.
    The signing key is loaded in-memory from ``config.signing_key`` here (never on
    disk) so the whole key-touching path lives behind this one mockable seam.
    """
    from pycardano import (
        Address,
        AlonzoMetadata,
        AuxiliaryData,
        Metadata,
        Network,
        PaymentVerificationKey,
        TransactionBuilder,
    )

    from .models import ANCHOR_LABEL

    # Key-touching span — REDACTED. Any raw failure here is re-raised as a
    # sanitized AnchorSubmitError carrying only the exception type name, and
    # ``from None`` drops the original (possibly key-bearing) exception from the
    # chain so it can never be stringified downstream. Our own gate exceptions
    # (AnchorAddressMismatch) are pass-through — they carry no key material.
    try:
        sk = load_signing_key(config.signing_key or "")
        network = Network.MAINNET if config.network == "mainnet" else Network.TESTNET
        vk = PaymentVerificationKey.from_signing_key(sk)
        # Address(payment_part, staking_part, network): network MUST be keyword — a
        # positional 2nd arg lands in staking_part and pycardano rejects it.
        address = Address(vk.hash(), network=network)

        # Gate B (pre-submit): expected-address pin — the last line of defense
        # before the irreversible submit. Refuse if the derived wallet is not the
        # pinned one (wrong key / preprod-key-under-mainnet-config collision).
        if config.expected_address and str(address) != config.expected_address:
            raise AnchorAddressMismatch(
                "derived wallet address does not match the configured "
                "GRANTLAYER_CARDANO_EXPECTED_ADDRESS — refusing to submit"
            )

        builder = TransactionBuilder(ctx)
        builder.add_input_address(address)  # required: builder selects UTXOs to pay the fee
        builder.auxiliary_data = AuxiliaryData(
            AlonzoMetadata(metadata=Metadata({ANCHOR_LABEL: payload.to_dict()}))
        )
        signed = builder.build_and_sign([sk], change_address=address)
    except AnchorAddressMismatch:
        raise
    except Exception as exc:  # noqa: BLE001 — deliberate: sanitize before it escapes
        raise AnchorSubmitError(
            f"anchor build/sign failed: {type(exc).__name__}"
        ) from None

    # Gate C (post-build, pre-submit): per-tx fee ceiling. The signed tx carries a
    # signature, never the private key, so inspecting it here is key-safe.
    if config.max_fee_lovelace is not None:
        fee = int(signed.transaction_body.fee)
        if fee > config.max_fee_lovelace:
            raise AnchorFeeExceeded(
                f"tx fee {fee} lovelace exceeds ceiling "
                f"{config.max_fee_lovelace} lovelace — refusing to submit"
            )

    # The single irreversible line. Every gate above aborts before reaching it.
    return str(ctx.submit_tx(signed))


def load_signing_key(material: str) -> Any:
    """Load a PaymentSigningKey from an in-memory .skey envelope (never via disk)."""
    from pycardano import PaymentSigningKey

    return PaymentSigningKey.from_json(material)
