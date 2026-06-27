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


@dataclass(frozen=True)
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

        return cls(
            enabled=_env_bool("GRANTLAYER_ENABLE_CARDANO_ANCHORING"),
            blockfrost_project_id=_secret("GRANTLAYER_BLOCKFROST_PROJECT_ID") or None,
            signing_key=_secret("GRANTLAYER_CARDANO_SIGNING_KEY") or None,
            workspace_id=_env_str("GRANTLAYER_CARDANO_ANCHOR_WORKSPACE_ID") or None,
            network=_env_str("GRANTLAYER_CARDANO_NETWORK", "preprod"),
            anchor_label=_env_int("GRANTLAYER_CARDANO_ANCHOR_LABEL", ANCHOR_LABEL),
            cron_hour=_env_int("GRANTLAYER_CARDANO_ANCHOR_CRON_HOUR", 2),
            cron_minute=_env_int("GRANTLAYER_CARDANO_ANCHOR_CRON_MINUTE", 0),
        )

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
        return errors
