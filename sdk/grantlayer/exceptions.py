"""GrantLayer SDK exceptions."""

from __future__ import annotations

from typing import Any


class GrantLayerError(Exception):
    """Base exception for all GrantLayer SDK errors."""


class GrantLayerHTTPError(GrantLayerError):
    """Raised when the server returns a non-2xx response."""

    def __init__(self, status_code: int, detail: Any = None) -> None:
        self.status_code = status_code
        self.detail = detail
        msg = f"HTTP {status_code}"
        if isinstance(detail, dict) and "error" in detail:
            msg = f"HTTP {status_code}: {detail['error']}"
        elif detail:
            msg = f"HTTP {status_code}: {detail}"
        super().__init__(msg)


class GrantLayerAuthError(GrantLayerHTTPError):
    """Raised on 401/403 responses."""


class GrantLayerNotFoundError(GrantLayerHTTPError):
    """Raised on 404 responses."""


class GrantLayerValidationError(GrantLayerHTTPError):
    """Raised on 400/422 responses."""


class GrantLayerRateLimitError(GrantLayerHTTPError):
    """Raised on 429 Too Many Requests."""

    def __init__(self, status_code: int, detail: Any = None, retry_after: int = 60) -> None:
        self.retry_after = retry_after
        super().__init__(status_code, detail)


class GrantLayerConnectionError(GrantLayerError):
    """Raised when the HTTP connection fails."""
