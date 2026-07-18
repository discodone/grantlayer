"""Cardano anchoring configuration.

Opt-in, fail-closed subsystem config mirroring backend/src/auth/oidc.py
OIDCConfig: a frozen dataclass with from_env() / is_fully_configured() /
startup_errors(). Anchoring is off unless GRANTLAYER_ENABLE_CARDANO_ANCHORING is
set, and enabled-but-misconfigured is a hard startup error (never fail open).

Secrets (Blockfrost project id + Cardano signing key) are resolved through the
existing _secret() chain (Vault > /run/secrets file > env); non-secret knobs come
from GRANTLAYER_CARDANO_* env vars.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from ..core.config import _secret
from .models import ANCHOR_LABEL


@dataclass(frozen=True, repr=False)
class CardanoConfig:
    enabled: bool
    blockfrost_project_id: Optional[str]
    signing_key: Optional[str]
    workspace_id: Optional[str]
    network: str = "preprod"
    anchor_label: int = ANCHOR_LABEL
    # Daily cron schedule (NOT a polling interval). Default 02:00 UTC.
    cron_hour: int = 2
    cron_minute: int = 0
    # Fail-closed spend guards (model-A capped hot key). All in lovelace; None
    # means the guard is inactive (allowed on preprod, REQUIRED on mainnet — see
    # startup_errors()). max_wallet_lovelace: refuse to submit if the wallet holds
    # more than this (over-fund / wrong-wallet). max_fee_lovelace: refuse to submit
    # if the built tx fee exceeds this. expected_address: the bech32 address the
    # loaded key MUST derive to (wrong-wallet + preprod/mainnet collision guard).
    max_wallet_lovelace: Optional[int] = None
    max_fee_lovelace: Optional[int] = None
    expected_address: Optional[str] = None
    # Minimum audit-chain event count required to anchor at all. None means
    # unset: allowed off-mainnet (effective minimum 1 — an empty chain is still
    # refused), a HARD startup error on mainnet, where it must be >= 3 (the
    # three genesis events exist by construction; anything below is
    # definitionally an empty/wrong chain and must never be witnessed on-chain).
    min_anchor_events: Optional[int] = None

    @classmethod
    def from_env(cls) -> "CardanoConfig":
        def _env_bool(name: str, default: bool = False) -> bool:
            v = os.environ.get(name, "").strip().lower()
            return v in {"1", "true", "yes", "on"} if v else default

        def _env_str(name: str, default: str = "") -> str:
            return os.environ.get(name, default).strip()

        def _env_int(name: str, default: int) -> int:
            try:
                return int(os.environ.get(name, str(default)))
            except (ValueError, TypeError):
                return default

        def _env_int_opt(name: str) -> Optional[int]:
            raw = os.environ.get(name, "").strip()
            if not raw:
                return None
            try:
                return int(raw)
            except (ValueError, TypeError):
                # Invalid → treated as unset (fail-closed: on mainnet this then
                # trips the "required" startup error rather than silently guarding).
                return None

        return cls(
            enabled=_env_bool("GRANTLAYER_ENABLE_CARDANO_ANCHORING"),
            blockfrost_project_id=_secret("GRANTLAYER_BLOCKFROST_PROJECT_ID") or None,
            signing_key=_secret("GRANTLAYER_CARDANO_SIGNING_KEY") or None,
            workspace_id=_env_str("GRANTLAYER_CARDANO_ANCHOR_WORKSPACE_ID") or None,
            network=_env_str("GRANTLAYER_CARDANO_NETWORK", "preprod"),
            anchor_label=_env_int("GRANTLAYER_CARDANO_ANCHOR_LABEL", ANCHOR_LABEL),
            cron_hour=_env_int("GRANTLAYER_CARDANO_ANCHOR_CRON_HOUR", 2),
            cron_minute=_env_int("GRANTLAYER_CARDANO_ANCHOR_CRON_MINUTE", 0),
            max_wallet_lovelace=_env_int_opt("GRANTLAYER_CARDANO_MAX_WALLET_LOVELACE"),
            max_fee_lovelace=_env_int_opt("GRANTLAYER_CARDANO_MAX_FEE_LOVELACE"),
            expected_address=_env_str("GRANTLAYER_CARDANO_EXPECTED_ADDRESS") or None,
            min_anchor_events=_env_int_opt("GRANTLAYER_CARDANO_MIN_ANCHOR_EVENTS"),
        )

    def __repr__(self) -> str:
        """Redacted repr — NEVER expose signing_key or blockfrost_project_id.

        The two secret fields are masked so an accidental ``logger.info(config)``
        or a frame dump that captures this object can never leak key material.
        ``expected_address`` is a public on-chain address and is shown verbatim.
        """
        def _mask(v: Optional[str]) -> Optional[str]:
            return "<redacted>" if v else None

        return (
            "CardanoConfig("
            f"enabled={self.enabled!r}, "
            f"blockfrost_project_id={_mask(self.blockfrost_project_id)!r}, "
            f"signing_key={_mask(self.signing_key)!r}, "
            f"workspace_id={self.workspace_id!r}, "
            f"network={self.network!r}, "
            f"anchor_label={self.anchor_label!r}, "
            f"cron_hour={self.cron_hour!r}, "
            f"cron_minute={self.cron_minute!r}, "
            f"max_wallet_lovelace={self.max_wallet_lovelace!r}, "
            f"max_fee_lovelace={self.max_fee_lovelace!r}, "
            f"expected_address={self.expected_address!r}, "
            f"min_anchor_events={self.min_anchor_events!r})"
        )

    @property
    def effective_min_anchor_events(self) -> int:
        """The enforced chain-length minimum. Unset defaults to 1 (dev
        ergonomics off-mainnet — an empty chain is still refused); on mainnet
        startup_errors() guarantees an explicit value >= 3 before any run."""
        return self.min_anchor_events if self.min_anchor_events is not None else 1

    def is_fully_configured(self) -> bool:
        """True when anchoring is enabled and all required fields are present."""
        return bool(
            self.enabled
            and self.blockfrost_project_id
            and self.signing_key
            and self.workspace_id
        )

    def startup_errors(self) -> list[str]:
        """Return configuration errors that block anchoring from starting safely."""
        if not self.enabled:
            return []
        errors: list[str] = []
        if not self.blockfrost_project_id:
            errors.append(
                "ERROR: GRANTLAYER_BLOCKFROST_PROJECT_ID is required when "
                "GRANTLAYER_ENABLE_CARDANO_ANCHORING=true."
            )
        if not self.signing_key:
            errors.append(
                "ERROR: GRANTLAYER_CARDANO_SIGNING_KEY is required when "
                "GRANTLAYER_ENABLE_CARDANO_ANCHORING=true."
            )
        if not self.workspace_id:
            errors.append(
                "ERROR: GRANTLAYER_CARDANO_ANCHOR_WORKSPACE_ID is required when "
                "GRANTLAYER_ENABLE_CARDANO_ANCHORING=true."
            )
        # Mainnet is irreversible real-value territory: the spend guards are
        # MANDATORY. No enabled-but-uncapped mainnet state is allowed.
        if self.network == "mainnet":
            if self.max_wallet_lovelace is None:
                errors.append(
                    "ERROR: GRANTLAYER_CARDANO_MAX_WALLET_LOVELACE is required when "
                    "GRANTLAYER_CARDANO_NETWORK=mainnet (fail-closed spend cap)."
                )
            if self.max_fee_lovelace is None:
                errors.append(
                    "ERROR: GRANTLAYER_CARDANO_MAX_FEE_LOVELACE is required when "
                    "GRANTLAYER_CARDANO_NETWORK=mainnet (fail-closed per-tx fee ceiling)."
                )
            if not self.expected_address:
                errors.append(
                    "ERROR: GRANTLAYER_CARDANO_EXPECTED_ADDRESS is required when "
                    "GRANTLAYER_CARDANO_NETWORK=mainnet (wrong-wallet / collision guard)."
                )
            if self.min_anchor_events is None or self.min_anchor_events < 3:
                errors.append(
                    "ERROR: GRANTLAYER_CARDANO_MIN_ANCHOR_EVENTS is required and must "
                    "be >= 3 when GRANTLAYER_CARDANO_NETWORK=mainnet (three genesis "
                    "events exist by construction — anything below is an empty/wrong "
                    "chain and must never be anchored)."
                )
        # Gate B (startup): bind the loaded key to the pinned address. Whenever we
        # have both a key and an expected address, the derived address MUST match —
        # this is what makes the worker/app refuse to boot on a wrong key or a
        # preprod-key-under-mainnet-config collision. Derivation is offline.
        if self.signing_key and self.expected_address:
            errors.extend(self._address_binding_errors())
        return errors

    def _address_binding_errors(self) -> list[str]:
        """Derive the wallet address from the loaded key and compare to the pin.

        Fully offline (no network). Any derivation failure is itself fail-closed:
        a key we cannot load must not be allowed to start. The signing key is
        never included in the returned message.
        """
        try:
            from .writer import derive_address

            derived = derive_address(self)
        except Exception as exc:  # never leak key material into the message
            return [
                "ERROR: cannot derive a Cardano wallet address from "
                f"GRANTLAYER_CARDANO_SIGNING_KEY ({type(exc).__name__}) — "
                "the key is unloadable or malformed."
            ]
        if derived != self.expected_address:
            return [
                "ERROR: derived Cardano wallet address does not match "
                "GRANTLAYER_CARDANO_EXPECTED_ADDRESS — wrong key or wrong network "
                f"(derived {derived}, expected {self.expected_address})."
            ]
        return []
