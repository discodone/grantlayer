"""OIDC integration endpoints for GrantLayer.

GET /v1/auth/oidc/config  — returns OIDC configuration metadata (no secrets).
GET /v1/auth/oidc/status  — returns OIDC integration status and posture.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ...auth.identity_access import describe_identity_access_posture
from ...auth.oidc import OIDCConfig

router = APIRouter(prefix="/auth/oidc", tags=["oidc"])


@router.get("/config")
async def get_oidc_config() -> Any:
    """Return OIDC configuration metadata.

    Returns only non-secret configuration values (no keys, no tokens).
    Callers can use this to discover the OIDC provider and redirect URI.
    """
    cfg = OIDCConfig.from_env()
    return JSONResponse({
        "oidc_enabled": cfg.enabled,
        "oidc_configured": cfg.is_fully_configured(),
        "issuer": cfg.issuer if cfg.enabled else "",
        "audience": cfg.audience if cfg.enabled else "",
        "algorithms": cfg.algorithms,
        "tenant_claim": cfg.tenant_claim,
        "role_claim": cfg.role_claim,
        "clock_skew_seconds": cfg.clock_skew_seconds,
    })


@router.get("/status")
async def get_oidc_status() -> Any:
    """Return OIDC integration status and identity/access posture."""
    posture = describe_identity_access_posture()
    cfg = OIDCConfig.from_env()
    startup_errs = cfg.startup_errors()
    return JSONResponse({
        "oidc_implemented": True,
        "oidc_enabled": cfg.enabled,
        "oidc_fully_configured": cfg.is_fully_configured(),
        "oidc_startup_errors": startup_errs,
        "saml_implemented": False,
        "identity_posture": posture,
    })
