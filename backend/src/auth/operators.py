"""GrantLayer MVP — Operator model (, ).

Minimal operator identity, role-based authorization, and bootstrap logic.
Not production IAM — still local-only demo-quality.

Admin/Operator Tenant Control Plane hardening:
- Explicit tenant_id required for create_operator (no silent global/None default)
- revoke_operator() added for admin-only operator revocation
- list_operators_for_admin() returns safe dict (no token/hash fields)
- get_operator_safe() returns safe dict (no token/hash fields)
- Audit events emitted for operator create/revoke (no raw token in events)
- Operator cannot self-escalate: tenant_id is server-assigned, not client-supplied
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import secrets
from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator, Optional

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# ──────────────────────────────────────────────────────────────
# PBKDF2 token hashing (stdlib only)
# ──────────────────────────────────────────────────────────────

TOKEN_HASH_ITERATIONS = 600_000
TOKEN_HASH_ALGORITHM = "sha256"
TOKEN_HASH_FORMAT = "pbkdf2_sha256"
DEFAULT_TOKEN_TTL_DAYS = 90


def hash_token(token: str) -> str:
    """Return PBKDF2-HMAC-SHA256 hash of token.

    Format: pbkdf2_sha256$<iterations>$<salt>$<hash>
    """
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        TOKEN_HASH_ALGORITHM,
        token.encode("utf-8"),
        salt.encode("utf-8"),
        TOKEN_HASH_ITERATIONS,
    ).hex()
    return f"{TOKEN_HASH_FORMAT}${TOKEN_HASH_ITERATIONS}${salt}${hashed}"


def verify_token(token: str, stored_hash: str) -> bool:
    """Verify a token against its stored PBKDF2 hash."""
    parts = stored_hash.split("$")
    if len(parts) != 4:
        return False
    algo, iterations_str, salt, _hash = parts
    if algo != TOKEN_HASH_FORMAT:
        return False
    try:
        iterations = int(iterations_str)
    except ValueError:
        return False
    expected = hashlib.pbkdf2_hmac(
        TOKEN_HASH_ALGORITHM,
        token.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return hmac.compare_digest(expected, _hash)


def derive_token_lookup_hash(token: str) -> str:
    """Return a fast, deterministic SHA-256 lookup hash for a token.

    This is NOT a secure password hash — it is used strictly for
    narrowing the candidate set before PBKDF2 verification."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now_utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _is_expired(expires_at: str | None) -> bool:
    """Return True if expires_at is in the past.

    Null/missing expires_at is treated as not expired for backward
    compatibility. Malformed timestamps are treated as expired (fail closed).
    """
    if not expires_at:
        return False
    try:
        expiry = datetime.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        return now >= expiry
    except Exception:
        return True


# ──────────────────────────────────────────────────────────────
# Data model
# ──────────────────────────────────────────────────────────────

class Operator:
    def __init__(
        self,
        operator_id: str,
        name: str,
        role: str,
        active: bool = True,
        created_at: Optional[str] = None,
        expires_at: Optional[str] = None,
        rotated_at: Optional[str] = None,
        tenant_id: str = "demo",
    ):
        self.operator_id = operator_id
        self.name = name
        self.role = role
        self.active = active
        self.created_at = created_at or _now_utc_iso()
        self.expires_at = expires_at
        self.rotated_at = rotated_at
        self.tenant_id = tenant_id

    def to_dict(self) -> dict:
        return {
            "operatorId": self.operator_id,
            "name": self.name,
            "role": self.role,
            "active": self.active,
            "tenantId": self.tenant_id,
        }


# ──────────────────────────────────────────────────────────────
# Session helpers
# ──────────────────────────────────────────────────────────────

@contextmanager
def _auto_session() -> Generator["Session", None, None]:
    from sqlalchemy.orm import Session as _Session

    from ..core.db import get_engine
    session = _Session(get_engine())
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _get_repo(session: "Optional[Session]" = None):
    from ..core.repositories_sqlalchemy import SqlAlchemyOperatorRepository
    if session is not None:
        return SqlAlchemyOperatorRepository(session), None
    # Return repo and a sentinel indicating auto-session is needed
    return None, True


# ──────────────────────────────────────────────────────────────
# Database helpers (legacy init — DDL now handled by Alembic)
# ──────────────────────────────────────────────────────────────

def _init_operators_table() -> None:
    pass


# ──────────────────────────────────────────────────────────────
# Query functions
# ──────────────────────────────────────────────────────────────

def get_operator_by_id(
    operator_id: str,
    session: "Optional[Session]" = None,
) -> Operator | None:
    from ..core.repositories_sqlalchemy import SqlAlchemyOperatorRepository
    if session is not None:
        return SqlAlchemyOperatorRepository(session).get(operator_id)
    with _auto_session() as sess:
        return SqlAlchemyOperatorRepository(sess).get(operator_id)


def list_operators(session: "Optional[Session]" = None) -> list[Operator]:
    from ..core.repositories_sqlalchemy import SqlAlchemyOperatorRepository
    if session is not None:
        return SqlAlchemyOperatorRepository(session).list()
    with _auto_session() as sess:
        return SqlAlchemyOperatorRepository(sess).list()


# ──────────────────────────────────────────────────────────────
# Admin control-plane safe-field helpers
# ──────────────────────────────────────────────────────────────

def _operator_to_safe_dict(op: Operator) -> dict:
    """Return safe operator dict for admin list/read responses.

    Excludes: token_hash, token_lookup_hash, lookup_hash, any raw token.
    Includes: operatorId, name, role, active, tenantId, createdAt, expiresAt.
    """
    return {
        "operatorId": op.operator_id,
        "name": op.name,
        "role": op.role,
        "active": op.active,
        "tenantId": op.tenant_id,
        "createdAt": op.created_at,
        "expiresAt": op.expires_at,
    }


def list_operators_for_admin(session: "Optional[Session]" = None) -> list[dict]:
    """List all operators with safe fields only (no token_hash/lookup_hash/raw token)."""
    operators = list_operators(session=session)
    return [_operator_to_safe_dict(op) for op in operators]


def get_operator_safe(
    operator_id: str,
    session: "Optional[Session]" = None,
) -> dict | None:
    """Get operator safe dict by ID (active or inactive)."""
    from ..core.repositories_sqlalchemy import SqlAlchemyOperatorRepository
    if session is not None:
        op = SqlAlchemyOperatorRepository(session).get_any(operator_id)
    else:
        with _auto_session() as sess:
            op = SqlAlchemyOperatorRepository(sess).get_any(operator_id)
    if op is None:
        return None
    return _operator_to_safe_dict(op)


def revoke_operator(
    operator_id: str,
    session: "Optional[Session]" = None,
) -> bool:
    """Deactivate an operator (set active=0)."""
    from ..core.repositories_sqlalchemy import SqlAlchemyOperatorRepository
    if session is not None:
        return SqlAlchemyOperatorRepository(session).revoke(operator_id)
    with _auto_session() as sess:
        return SqlAlchemyOperatorRepository(sess).revoke(operator_id)


def create_operator(
    name: str,
    role: str,
    token: str,
    tenant_id: str,
    ttl_days: int = DEFAULT_TOKEN_TTL_DAYS,
    session: "Optional[Session]" = None,
) -> tuple[Operator, str]:
    """Create a new operator and return (operator, raw_token).

    The raw_token is returned exactly once; store it securely.
    """
    from ..core.repositories_sqlalchemy import SqlAlchemyOperatorRepository
    if session is not None:
        return SqlAlchemyOperatorRepository(session).create(name, role, token, tenant_id, ttl_days)
    with _auto_session() as sess:
        return SqlAlchemyOperatorRepository(sess).create(name, role, token, tenant_id, ttl_days)


def is_operator_token_expired(
    operator_id: str,
    session: "Optional[Session]" = None,
) -> bool | None:
    """Check whether an operator's token is expired."""
    from ..core.repositories_sqlalchemy import SqlAlchemyOperatorRepository
    if session is not None:
        op = SqlAlchemyOperatorRepository(session).get(operator_id)
    else:
        with _auto_session() as sess:
            op = SqlAlchemyOperatorRepository(sess).get(operator_id)
    if op is None:
        return None
    return _is_expired(op.expires_at)


def authenticate_operator_with_reason(
    authorization_header: str | None,
    session: "Optional[Session]" = None,
) -> tuple[Operator | None, str | None]:
    """Validate Bearer token and return operator with a reason code on failure.

    Returns (operator, reason_code).  On success reason_code is None.
    On failure operator is None and reason_code is a stable string:
      - "operator_auth_required"  — missing, malformed, or invalid token
      - "operator_token_expired"  — token hash verified but expired
    """
    if not authorization_header or not authorization_header.startswith("Bearer "):
        return None, "operator_auth_required"
    token = authorization_header.removeprefix("Bearer ").strip()
    if not token:
        return None, "operator_auth_required"

    lookup = derive_token_lookup_hash(token)

    def _check(repo) -> tuple[Operator | None, str | None]:
        from ..core.repositories_sqlalchemy import SqlAlchemyOperatorRepository
        assert isinstance(repo, SqlAlchemyOperatorRepository)
        orm_row = repo.find_by_lookup_hash(lookup)
        if orm_row is not None and verify_token(token, str(orm_row.token_hash)):
            expires = str(orm_row.expires_at) if orm_row.expires_at is not None else None
            if _is_expired(expires):
                return None, "operator_token_expired"
            from ..core.repositories_sqlalchemy import _orm_to_operator
            return _orm_to_operator(orm_row), None

        # Legacy fallback: rows created before token_lookup_hash was added.
        for orm_op in repo.find_all_without_lookup_hash():
            if verify_token(token, str(orm_op.token_hash)):
                expires = str(orm_op.expires_at) if orm_op.expires_at is not None else None
                if _is_expired(expires):
                    return None, "operator_token_expired"
                from ..core.repositories_sqlalchemy import _orm_to_operator
                return _orm_to_operator(orm_op), None

        return None, "operator_auth_required"

    from ..core.repositories_sqlalchemy import SqlAlchemyOperatorRepository
    if session is not None:
        return _check(SqlAlchemyOperatorRepository(session))
    with _auto_session() as sess:
        return _check(SqlAlchemyOperatorRepository(sess))


def authenticate_operator(authorization_header: str | None) -> Operator | None:
    """Validate Bearer token and return operator (without token_hash)."""
    op, _reason = authenticate_operator_with_reason(authorization_header)
    return op


def check_role(operator: Operator, required_roles: list[str]) -> bool:
    """Return True if operator.role is in required_roles."""
    return operator.role in required_roles


def rotate_operator_token(
    operator_id: str,
    ttl_days: int = DEFAULT_TOKEN_TTL_DAYS,
    session: "Optional[Session]" = None,
) -> str | None:
    """Rotate an operator's token material."""
    from ..core.repositories_sqlalchemy import SqlAlchemyOperatorRepository
    if session is not None:
        return SqlAlchemyOperatorRepository(session).rotate_token(operator_id, ttl_days)
    with _auto_session() as sess:
        return SqlAlchemyOperatorRepository(sess).rotate_token(operator_id, ttl_days)


# ──────────────────────────────────────────────────────────────
# Bootstrap
# ──────────────────────────────────────────────────────────────

def bootstrap_operator_if_needed(session: "Optional[Session]" = None) -> None:
    """Create bootstrap operator if operators table is empty and config is set."""
    from ..core.repositories_sqlalchemy import SqlAlchemyOperatorRepository
    if session is not None:
        SqlAlchemyOperatorRepository(session).bootstrap_if_needed()
        return
    with _auto_session() as sess:
        SqlAlchemyOperatorRepository(sess).bootstrap_if_needed()


# ──────────────────────────────────────────────────────────────
# Integration hook (called from db.init_db)
# ──────────────────────────────────────────────────────────────

def ensure_operators_table() -> None:
    _init_operators_table()
    bootstrap_operator_if_needed()
