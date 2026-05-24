"""GrantLayer MVP — Operator model (GL-021).

Minimal operator identity, role-based authorization, and bootstrap logic.
Not production IAM — still local-only demo-quality.
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
    ):
        self.operator_id = operator_id
        self.name = name
        self.role = role
        self.active = active
        self.created_at = created_at or datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat().replace("+00:00", "Z")

    def to_dict(self) -> dict:
        return {
            "operatorId": self.operator_id,
            "name": self.name,
            "role": self.role,
            "active": self.active,
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
                created_at        TEXT NOT NULL
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


def authenticate_operator(authorization_header: str | None) -> Operator | None:
    """Validate Bearer token and return operator (without token_hash).

    Returns None for missing/malformed header, unknown/inactive operator,
    or token hash mismatch.
    """
    if not authorization_header or not authorization_header.startswith("Bearer "):
        return None
    token = authorization_header.removeprefix("Bearer ").strip()
    if not token:
        return None

    # O(1) deterministic narrowing via SHA-256 lookup hash.
    # For legacy rows without token_lookup_hash, we fall back to
    # scanning only the legacy subset (ideally empty after migration).
    lookup = derive_token_lookup_hash(token)
    row = query_one(
        "SELECT id, token_hash FROM operators WHERE token_lookup_hash = ? AND active = 1",
        (lookup,),
    )
    if row is not None and verify_token(token, row["token_hash"]):
        return get_operator_by_id(row["id"])

    # Legacy fallback: rows created before GL-107 may lack token_lookup_hash.
    # This path is bounded by the number of legacy operators, not all operators.
    legacy_rows = query_all(
        "SELECT id, token_hash FROM operators WHERE active = 1 AND token_lookup_hash IS NULL"
    )
    for row in legacy_rows:
        if verify_token(token, row["token_hash"]):
            return get_operator_by_id(row["id"])

    return None


def check_role(operator: Operator, required_roles: list[str]) -> bool:
    """Return True if operator.role is in required_roles."""
    return operator.role in required_roles


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

        conn.execute(
            """
            INSERT INTO operators (id, name, role, token_hash, token_lookup_hash, active, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (
                config.GRANTLAYER_BOOTSTRAP_OPERATOR_ID,
                config.GRANTLAYER_BOOTSTRAP_OPERATOR_NAME,
                config.GRANTLAYER_BOOTSTRAP_OPERATOR_ROLE,
                hash_token(config.GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN),
                derive_token_lookup_hash(config.GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN),
                datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
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
