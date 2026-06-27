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

    sk = load_signing_key(config.signing_key or "")
    network = Network.MAINNET if config.network == "mainnet" else Network.TESTNET
    vk = PaymentVerificationKey.from_signing_key(sk)
    address = Address(vk.hash(), network)

    builder = TransactionBuilder(ctx)
    builder.add_input_address(address)  # required: builder selects UTXOs to pay the fee
    builder.auxiliary_data = AuxiliaryData(
        AlonzoMetadata(metadata=Metadata({ANCHOR_LABEL: payload.to_dict()}))
    )
    signed = builder.build_and_sign([sk], change_address=address)
    return str(ctx.submit_tx(signed))


def load_signing_key(material: str) -> Any:
    """Load a PaymentSigningKey from an in-memory .skey envelope (never via disk)."""
    from pycardano import PaymentSigningKey

    return PaymentSigningKey.from_json(material)
