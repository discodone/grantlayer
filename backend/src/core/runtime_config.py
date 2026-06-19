"""
GrantLayer runtime configuration helper.

Provides validated runtime mode detection and safe metadata inspection.
Dependency-free except Python standard library.
"""

import os
from typing import Mapping, Optional

SUPPORTED_MODES = frozenset([
    "local",
    "test",
    "demo",
    "staging",
    "production",
])

PRODUCTION_LIKE_MODES = frozenset([
    "staging",
    "production",
])

RUNTIME_MODE_ENV_VAR = "GRANTLAYER_RUNTIME_MODE"
DEFAULT_MODE = "production"


def get_runtime_mode(env: Optional[Mapping[str, str]] = None) -> str:
    """Resolve and validate the runtime mode from environment.

    Args:
        env: Optional mapping of environment variables. If None, reads os.environ.

    Returns:
        The normalized supported runtime mode.

    Raises:
        ValueError: If the runtime mode is unsupported.
    """
    source = env if env is not None else os.environ
    raw = source.get(RUNTIME_MODE_ENV_VAR, "")
    stripped = raw.strip()

    if not stripped:
        mode = DEFAULT_MODE
    else:
        mode = stripped.lower()

    if mode not in SUPPORTED_MODES:
        raise ValueError(
            "Unsupported runtime mode. "
            f"Supported modes are: {', '.join(sorted(SUPPORTED_MODES))}."
        )

    return mode


def is_production_like(
    mode: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
) -> bool:
    """Determine whether the runtime mode is production-like.

    Args:
        mode: Optional explicit mode to evaluate. If None, resolves from env.
        env: Optional environment mapping used when mode is None.

    Returns:
        True if the mode is staging or production, otherwise False.

    Raises:
        ValueError: If an explicit mode is provided and unsupported.
    """
    if mode is not None:
        normalized = mode.strip().lower()
        if normalized not in SUPPORTED_MODES:
            raise ValueError(
                "Unsupported runtime mode. "
                f"Supported modes are: {', '.join(sorted(SUPPORTED_MODES))}."
            )
        return normalized in PRODUCTION_LIKE_MODES

    resolved = get_runtime_mode(env)
    return resolved in PRODUCTION_LIKE_MODES


def describe_runtime_config(env: Optional[Mapping[str, str]] = None) -> dict:
    """Return safe metadata about the current runtime configuration.

    Does not expose raw environment values, secrets, tokens, private keys,
    database URLs, or operator tokens.

    Args:
        env: Optional environment mapping. If None, reads os.environ.

    Returns:
        A dictionary with safe runtime configuration metadata.
    """
    source = env if env is not None else os.environ
    raw = source.get(RUNTIME_MODE_ENV_VAR, "")
    stripped = raw.strip()

    if not stripped:
        mode = DEFAULT_MODE
        config_source = "default"
    else:
        mode = stripped.lower()
        config_source = "environment"

    # Validate to remain consistent with get_runtime_mode behavior
    if mode not in SUPPORTED_MODES:
        raise ValueError(
            "Unsupported runtime mode. "
            f"Supported modes are: {', '.join(sorted(SUPPORTED_MODES))}."
        )

    return {
        "runtimeMode": mode,
        "isProductionLike": mode in PRODUCTION_LIKE_MODES,
        "supportedModes": sorted(SUPPORTED_MODES),
        "configSource": config_source,
    }
