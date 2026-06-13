"""identity/access posture helpers.

This module does not implement OAuth, OIDC, SAML, SSO, MFA, or JWT auth.
It records the validation posture required before those token types may be
accepted and provides fail-closed checks for production-like misconfiguration.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from ..core.runtime_config import PRODUCTION_LIKE_MODES, get_runtime_mode

EXTERNAL_IDENTITY_ENABLE_FLAGS: tuple[str, ...] = (
    "GRANTLAYER_ENABLE_OAUTH",
    "GRANTLAYER_ENABLE_OIDC",
    "GRANTLAYER_ENABLE_JWT_AUTH",
    "GRANTLAYER_ACCEPT_EXTERNAL_JWT",
)

EXTERNAL_IDENTITY_CONFIG_VARS: tuple[str, ...] = (
    "GRANTLAYER_OIDC_ISSUER",
    "GRANTLAYER_OIDC_AUDIENCE",
    "GRANTLAYER_OIDC_JWKS_URL",
    "GRANTLAYER_JWT_ISSUER",
    "GRANTLAYER_JWT_AUDIENCE",
    "GRANTLAYER_JWT_JWKS_URL",
    "GRANTLAYER_JWT_ALGORITHMS",
)

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


def external_identity_startup_errors(
    env: Mapping[str, str] | None = None,
    runtime_mode: str | None = None,
) -> list[str]:
    """Return safe startup errors for unsupported external identity config.

    Production-like modes fail closed when an operator tries to enable OAuth,
    OIDC, or JWT acceptance before a real validator exists. Error messages
    include variable names only, never configured values.
    """
    effective_env = env if env is not None else os.environ
    mode = runtime_mode or get_runtime_mode()
    if mode not in PRODUCTION_LIKE_MODES:
        return []

    enabled_flags = [name for name in EXTERNAL_IDENTITY_ENABLE_FLAGS if _env_true(effective_env, name)]
    configured_vars = _present(effective_env, EXTERNAL_IDENTITY_CONFIG_VARS)
    errors: list[str] = []

    if enabled_flags:
        errors.append(
            "ERROR: external_identity_provider_not_implemented. "
            "OAuth/OIDC/JWT bearer-token acceptance is not implemented; "
            "unset external identity enablement flags before starting in "
            "production-like modes."
        )

    if configured_vars:
        errors.append(
            "ERROR: external_identity_config_present_without_validator. "
            "Issuer, audience, JWKS, or JWT algorithm configuration is present, "
            "but GrantLayer does not yet include a production OAuth/OIDC/JWT "
            "validator. Remove these settings or implement a later approved "
            "identity-provider gate."
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
    return {
        "runtime_mode": mode,
        "is_production_like": mode in PRODUCTION_LIKE_MODES,
        "current_admin_model": "static_admin_bearer_token",
        "current_operator_model": "hashed_operator_bearer_tokens",
        "external_identity_provider_implemented": False,
        "oauth_oidc_jwt_bearer_acceptance": "not_implemented",
        "external_identity_enable_flags_present": enabled_flags,
        "external_identity_config_vars_present": configured_vars,
        "jwt_validation_requirements": list(JWT_VALIDATION_REQUIREMENTS),
        "fail_closed_startup_errors": startup_errors,
        "production_identity_ready": False,
        "real_customer_private_data_ready": False,
    }
