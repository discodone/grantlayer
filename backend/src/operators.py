"""GrantLayer MVP — Operator model (GL-021, GL-206).

Minimal operator identity, role-based authorization, and bootstrap logic.
Not production IAM — still local-only demo-quality.

GL-206: Admin/Operator Tenant Control Plane hardening:
- Explicit tenant_id required for create_operator (no silent global/None default)
- revoke_operator() added for admin-only operator revocation
- list_operators_for_admin() returns safe dict (no token/hash fields)
- get_operator_safe() returns safe dict (no token/hash fields)
- Audit events emitted for operator create/revoke (no raw token in events)
- Operator cannot self-escalate: tenant_id is server-assigned, not client-supplied
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
import datetime
from typing import Optional

from .db import get_conn, execute, query_one, query_all


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
# Database helpers
# ──────────────────────────────────────────────────────────────

def _init_operators_table() -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS operators (
                id                TEXT PRIMARY KEY,
                name              TEXT NOT NULL,
                role              TEXT NOT NULL,
                token_hash        TEXT NOT NULL,
                token_lookup_hash TEXT,
                active            INTEGER NOT NULL DEFAULT 1,
                created_at        TEXT NOT NULL,
                expires_at        TEXT,
                rotated_at        TEXT,
                tenant_id         TEXT NOT NULL DEFAULT 'demo',
                workspace_id      TEXT DEFAULT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_operator(row: dict | None) -> Operator | None:
    if row is None:
        return None
    return Operator(
        operator_id=row["id"],
        name=row["name"],
        role=row["role"],
        active=bool(row["active"]),
        created_at=row["created_at"],
        expires_at=row.get("expires_at"),
        rotated_at=row.get("rotated_at"),
        tenant_id=row.get("tenant_id") or "demo",
    )


def get_operator_by_id(operator_id: str) -> Operator | None:
    row = query_one(
        "SELECT * FROM operators WHERE id = ? AND active = 1", (operator_id,)
    )
    return _row_to_operator(row)


def _get_operator_row_by_token_hash(token_hash: str) -> dict | None:
    return query_one(
        "SELECT * FROM operators WHERE token_hash = ? AND active = 1", (token_hash,)
    )


def list_operators() -> list[Operator]:
    rows = query_all("SELECT * FROM operators ORDER BY created_at DESC")
    return [_row_to_operator(r) for r in rows if r is not None]


# ──────────────────────────────────────────────────────────────
# GL-206: Admin control-plane safe-field helpers
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


def list_operators_for_admin() -> list[dict]:
    """List all operators with safe fields only (no token_hash/lookup_hash/raw token).

    GL-206: Used by admin control-plane. Never returns internal hash fields.
    """
    operators = list_operators()
    return [_operator_to_safe_dict(op) for op in operators]


def get_operator_safe(operator_id: str) -> dict | None:
    """Get operator safe dict by ID (active or inactive).

    GL-206: Used by admin control-plane. Never returns internal hash fields.
    """
    row = query_one("SELECT * FROM operators WHERE id = ?", (operator_id,))
    if row is None:
        return None
    op = _row_to_operator(row)
    return _operator_to_safe_dict(op)


def revoke_operator(operator_id: str) -> bool:
    """Deactivate an operator (set active=0).

    GL-206: Admin-only revocation. Returns True if updated, False if not found.
    Revoked operators fail closed on authentication.
    """
    conn = get_conn()
    try:
        cursor = conn.execute(
            "UPDATE operators SET active = 0 WHERE id = ?",
            (operator_id,),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def create_operator(
    name: str,
    role: str,
    token: str,
    tenant_id: str,
    ttl_days: int = DEFAULT_TOKEN_TTL_DAYS,
) -> tuple[Operator, str]:
    """Create a new operator and return (operator, raw_token).

    The raw_token is returned exactly once; store it securely.

    GL-206: tenant_id is now a required positional argument — no silent global
    or None default in the public API. For demo/bootstrap usage, pass
    tenant_id='demo' explicitly.
    """
    op_id = str(uuid.uuid4())
    token_hash = hash_token(token)
    lookup = derive_token_lookup_hash(token)
    now = _now_utc_iso()
    expires = (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=ttl_days)
    ).isoformat().replace("+00:00", "Z")

    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO operators
                (id, name, role, token_hash, token_lookup_hash, active, created_at, expires_at, tenant_id)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (op_id, name, role, token_hash, lookup, now, expires, tenant_id),
        )
        conn.commit()
    finally:
        conn.close()

    op = Operator(
        operator_id=op_id,
        name=name,
        role=role,
        active=True,
        created_at=now,
        expires_at=expires,
        tenant_id=tenant_id,
    )
    return op, token


def is_operator_token_expired(operator_id: str) -> bool | None:
    """Check whether an operator's token is expired.

    Returns None if the operator is not found or inactive.
    """
    row = query_one(
        "SELECT expires_at FROM operators WHERE id = ? AND active = 1", (operator_id,)
    )
    if row is None:
        return None
    return _is_expired(row.get("expires_at"))


def authenticate_operator_with_reason(
    authorization_header: str | None,
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

    # O(1) deterministic narrowing via SHA-256 lookup hash.
    lookup = derive_token_lookup_hash(token)
    row = query_one(
        "SELECT id, token_hash, expires_at FROM operators WHERE token_lookup_hash = ? AND active = 1",
        (lookup,),
    )
    if row is not None and verify_token(token, row["token_hash"]):
        if _is_expired(row.get("expires_at")):
            return None, "operator_token_expired"
        return get_operator_by_id(row["id"]), None

    # Legacy fallback: rows created before GL-107 may lack token_lookup_hash.
    legacy_rows = query_all(
        "SELECT id, token_hash, expires_at FROM operators WHERE active = 1 AND token_lookup_hash IS NULL"
    )
    for row in legacy_rows:
        if verify_token(token, row["token_hash"]):
            if _is_expired(row.get("expires_at")):
                return None, "operator_token_expired"
            return get_operator_by_id(row["id"]), None

    return None, "operator_auth_required"


def authenticate_operator(authorization_header: str | None) -> Operator | None:
    """Validate Bearer token and return operator (without token_hash).

    Returns None for missing/malformed header, unknown/inactive operator,
    token hash mismatch, or expired token.
    """
    op, _reason = authenticate_operator_with_reason(authorization_header)
    return op


def check_role(operator: Operator, required_roles: list[str]) -> bool:
    """Return True if operator.role is in required_roles."""
    return operator.role in required_roles


def rotate_operator_token(operator_id: str, ttl_days: int = DEFAULT_TOKEN_TTL_DAYS) -> str | None:
    """Rotate an operator's token material.

    Generates a new raw token, hashes it with PBKDF2, computes a new
    token_lookup_hash, updates the operator row, and returns the new
    raw token exactly once.  Returns None if the operator is not found
    or inactive.
    """
    op = get_operator_by_id(operator_id)
    if op is None:
        return None

    new_token = secrets.token_urlsafe(32)
    new_hash = hash_token(new_token)
    new_lookup = derive_token_lookup_hash(new_token)
    now = _now_utc_iso()
    expires = (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=ttl_days)
    ).isoformat().replace("+00:00", "Z")

    conn = get_conn()
    try:
        conn.execute(
            """
            UPDATE operators
            SET token_hash = ?,
                token_lookup_hash = ?,
                rotated_at = ?,
                expires_at = ?
            WHERE id = ?
            """,
            (new_hash, new_lookup, now, expires, operator_id),
        )
        conn.commit()
    finally:
        conn.close()

    return new_token


# ──────────────────────────────────────────────────────────────
# Bootstrap
# ──────────────────────────────────────────────────────────────

def bootstrap_operator_if_needed() -> None:
    """Create bootstrap operator if operators table is empty and config is set."""
    from . import config

    if not config.ENABLE_OPERATOR_MODEL:
        return
    if not config.GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN:
        return

    conn = get_conn()
    try:
        count_row = conn.execute(
            "SELECT COUNT(*) FROM operators"
        ).fetchone()
        count = count_row[0] if count_row else 0
        if count > 0:
            return

        expires = (
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=DEFAULT_TOKEN_TTL_DAYS)
        ).isoformat().replace("+00:00", "Z")

        conn.execute(
            """
            INSERT INTO operators (id, name, role, token_hash, token_lookup_hash, active, created_at, expires_at, tenant_id)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                config.GRANTLAYER_BOOTSTRAP_OPERATOR_ID,
                config.GRANTLAYER_BOOTSTRAP_OPERATOR_NAME,
                config.GRANTLAYER_BOOTSTRAP_OPERATOR_ROLE,
                hash_token(config.GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN),
                derive_token_lookup_hash(config.GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN),
                _now_utc_iso(),
                expires,
                "demo",
            ),
        )
        conn.commit()
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# Integration hook (called from db.init_db)
# ──────────────────────────────────────────────────────────────

def ensure_operators_table() -> None:
    _init_operators_table()
    bootstrap_operator_if_needed()
