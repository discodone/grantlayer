"""Identity/access posture helpers.

Reports the current state of external identity provider support and
enforces fail-closed startup checks for misconfigured deployments.

OIDC: Implemented — validates externally-issued JWTs via JWKS when fully configured.
  Requires GRANTLAYER_ENABLE_OIDC=true + GRANTLAYER_OIDC_ISSUER + GRANTLAYER_OIDC_AUDIENCE
  + GRANTLAYER_OIDC_JWKS_URL.  Partial configuration fails-closed in production-like modes.
SAML 2.0: Not yet implemented — placeholder for future library integration.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from ..core.runtime_config import PRODUCTION_LIKE_MODES, get_runtime_mode

# Flags that enable external identity providers.
EXTERNAL_IDENTITY_ENABLE_FLAGS: tuple[str, ...] = (
    "GRANTLAYER_ENABLE_OAUTH",
    "GRANTLAYER_ENABLE_OIDC",
    "GRANTLAYER_ENABLE_JWT_AUTH",
    "GRANTLAYER_ACCEPT_EXTERNAL_JWT",
    "GRANTLAYER_ENABLE_SAML",
)

# Env vars that configure external identity providers.
EXTERNAL_IDENTITY_CONFIG_VARS: tuple[str, ...] = (
    "GRANTLAYER_OIDC_ISSUER",
    "GRANTLAYER_OIDC_AUDIENCE",
    "GRANTLAYER_OIDC_JWKS_URL",
    "GRANTLAYER_JWT_JWKS_URL",
    "GRANTLAYER_JWT_ALGORITHMS",
    "GRANTLAYER_SAML_METADATA_URL",
    "GRANTLAYER_SAML_ENTITY_ID",
)

# Non-OIDC flags that remain unimplemented.
_UNIMPLEMENTED_FLAGS: frozenset[str] = frozenset({
    "GRANTLAYER_ENABLE_OAUTH",
    "GRANTLAYER_ENABLE_JWT_AUTH",
    "GRANTLAYER_ACCEPT_EXTERNAL_JWT",
    "GRANTLAYER_ENABLE_SAML",
})

# Config vars belonging to the OIDC implementation.
_OIDC_VARS: frozenset[str] = frozenset({
    "GRANTLAYER_OIDC_ISSUER",
    "GRANTLAYER_OIDC_AUDIENCE",
    "GRANTLAYER_OIDC_JWKS_URL",
})

# Non-OIDC config vars that remain unimplemented.
_UNIMPLEMENTED_VARS: frozenset[str] = frozenset({
    "GRANTLAYER_JWT_JWKS_URL",
    "GRANTLAYER_JWT_ALGORITHMS",
    "GRANTLAYER_SAML_METADATA_URL",
    "GRANTLAYER_SAML_ENTITY_ID",
})

JWT_VALIDATION_REQUIREMENTS: tuple[str, ...] = (
    "signature validation before claim trust",
    "explicit issuer allowlist with exact issuer match",
    "explicit audience allowlist with exact audience match",
    "expiration, not-before, and issued-at validation with bounded clock skew",
    "algorithm allowlist that rejects none and unexpected algorithms",
    "JWKS or key material selection by key id with unknown-key denial",
    "key rotation and retired-key handling with a documented overlap window",
    "tenant/workspace mapping from trusted claims only",
    "revocation/deprovisioning lifecycle for operators and admin access",
    "safe logging that omits raw tokens, token hashes, auth headers, and keys",
    "provider outage and metadata-fetch failures deny protected access",
)


def _env_true(env: Mapping[str, str], name: str) -> bool:
    value = env.get(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _present(env: Mapping[str, str], names: tuple[str, ...]) -> list[str]:
    return [name for name in names if env.get(name, "").strip()]


def _oidc_fully_configured(env: Mapping[str, str]) -> bool:
    """True when OIDC is enabled AND all three required vars are present."""
    return (
        _env_true(env, "GRANTLAYER_ENABLE_OIDC")
        and bool(env.get("GRANTLAYER_OIDC_ISSUER", "").strip())
        and bool(env.get("GRANTLAYER_OIDC_AUDIENCE", "").strip())
        and bool(env.get("GRANTLAYER_OIDC_JWKS_URL", "").strip())
    )


def external_identity_startup_errors(
    env: Mapping[str, str] | None = None,
    runtime_mode: str | None = None,
) -> list[str]:
    """Return safe startup errors for unsupported or misconfigured external identity config.

    Fail-closed in production-like modes:
    - OIDC fully configured (flag + issuer + audience + jwks_url): no errors.
    - OIDC partially configured (flag set but any required var missing,
      or config vars present without the flag): fails-closed with 2 errors.
    - Non-OIDC external identity flags (OAuth, SAML, etc.): fails-closed.
    - Non-OIDC config vars (SAML, raw JWT): fails-closed.

    Returns [] in local/test mode regardless of configuration.
    """
    effective_env = env if env is not None else os.environ
    mode = runtime_mode or get_runtime_mode()
    if mode not in PRODUCTION_LIKE_MODES:
        return []

    oidc_fully_ok = _oidc_fully_configured(effective_env)
    oidc_enabled = _env_true(effective_env, "GRANTLAYER_ENABLE_OIDC")

    # OIDC flags that should produce errors: either not enabled, or enabled but incomplete.
    # A fully configured OIDC passes without error.
    oidc_flag_has_error = oidc_enabled and not oidc_fully_ok

    # Non-OIDC flags always fail in production-like modes.
    unimplemented_flags = [
        name for name in _UNIMPLEMENTED_FLAGS if _env_true(effective_env, name)
    ]

    # OIDC config vars without a complete OIDC setup → fail-closed.
    oidc_vars_present = [v for v in _OIDC_VARS if effective_env.get(v, "").strip()]
    oidc_vars_without_full_config = oidc_vars_present and not oidc_fully_ok

    # Non-OIDC config vars → always fail.
    unimplemented_var_present = any(effective_env.get(v, "").strip() for v in _UNIMPLEMENTED_VARS)

    errors: list[str] = []

    if oidc_flag_has_error or unimplemented_flags:
        errors.append(
            "ERROR: external_identity_provider_not_implemented. "
            "OAuth/OIDC/SAML bearer-token acceptance requires complete configuration; "
            "partial or unsupported external identity flags detected. "
            "OIDC requires GRANTLAYER_ENABLE_OIDC=true plus GRANTLAYER_OIDC_ISSUER, "
            "GRANTLAYER_OIDC_AUDIENCE, and GRANTLAYER_OIDC_JWKS_URL. "
            "GRANTLAYER_ENABLE_OAUTH and GRANTLAYER_ENABLE_SAML are not implemented."
        )

    if oidc_vars_without_full_config or unimplemented_var_present:
        errors.append(
            "ERROR: external_identity_config_present_without_validator. "
            "External identity configuration is present but OIDC is not fully configured "
            "or unsupported config vars are set. Ensure all three OIDC vars are set "
            "(GRANTLAYER_OIDC_ISSUER, GRANTLAYER_OIDC_AUDIENCE, GRANTLAYER_OIDC_JWKS_URL) "
            "or remove the configuration."
        )

    return errors


def describe_identity_access_posture(
    env: Mapping[str, str] | None = None,
    runtime_mode: str | None = None,
) -> dict[str, Any]:
    """Return a safe machine-readable identity/access posture summary."""
    effective_env = env if env is not None else os.environ
    mode = runtime_mode or get_runtime_mode()
    enabled_flags = [name for name in EXTERNAL_IDENTITY_ENABLE_FLAGS if _env_true(effective_env, name)]
    configured_vars = _present(effective_env, EXTERNAL_IDENTITY_CONFIG_VARS)
    startup_errors = external_identity_startup_errors(effective_env, mode)

    oidc_enabled = _env_true(effective_env, "GRANTLAYER_ENABLE_OIDC")
    oidc_fully_ok = _oidc_fully_configured(effective_env)

    # An external identity provider is "implemented" when OIDC is fully connected.
    external_idp_implemented = oidc_fully_ok

    return {
        "runtime_mode": mode,
        "is_production_like": mode in PRODUCTION_LIKE_MODES,
        "current_admin_model": "static_admin_bearer_token",
        "current_operator_model": "hashed_operator_bearer_tokens",
        "oidc_implemented": True,
        "oidc_enabled": oidc_enabled,
        "oidc_fully_configured": oidc_fully_ok,
        "saml_implemented": False,
        "saml_note": "SAML 2.0 requires python-saml or pysaml2; planned for a future release.",
        "external_identity_provider_implemented": external_idp_implemented,
        "oauth_oidc_jwt_bearer_acceptance": (
            "oidc_implemented" if oidc_fully_ok else "not_implemented"
        ),
        "external_identity_enable_flags_present": enabled_flags,
        "external_identity_config_vars_present": configured_vars,
        "jwt_validation_requirements": list(JWT_VALIDATION_REQUIREMENTS),
        "fail_closed_startup_errors": startup_errors,
        "production_identity_ready": oidc_fully_ok and not startup_errors,
        "real_customer_private_data_ready": False,
    }
