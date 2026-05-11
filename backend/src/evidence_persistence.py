"""GrantLayer MVP — GL-036 Evidence Bundle Persistence Layer.

Provides durable, immutable storage for evidence bundles with hash-based
verification, lookup, and integrity checking.

No mutation after storage. No deletion. No secrets in stored bundles.
"""

from typing import Optional, Any
import datetime
import json

from . import db
from .models import EvidenceBundle


STORE_ERROR_CODES = {"already_stored", "execution_not_found", "hash_mismatch", "invalid_bundle"}


def _iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


# ──────────────────────────────────────────────────────────────
# Core storage operations
# ──────────────────────────────────────────────────────────────

def store_bundle(
    execution_id: str,
    bundle: dict[str, Any],
    stored_by: Optional[str] = None,
) -> dict[str, Any]:
    """Persist an evidence bundle to the archive store.

    Validates:
      - Bundle hash matches recomputed hash
      - Execution is not already archived (UNIQUE constraint)

    Returns a result dict with ok=True and archive metadata, or ok=False
    with an error code and reason.
    """
    # Validate required fields
    evidence_hash = bundle.get("evidenceHash")
    if not evidence_hash or not isinstance(evidence_hash, str) or len(evidence_hash) != 64:
        return {
            "ok": False,
            "error": "invalid_bundle",
            "reason": "Bundle is missing a valid evidenceHash.",
            "executionId": execution_id,
        }

    canonical_version = bundle.get("canonicalVersion", "")
    hash_algorithm = bundle.get("hashAlgorithm", "")
    grant_id = bundle.get("grantId")
    grant_request_id = bundle.get("grantRequestId")
    bundle_json = json.dumps(bundle, separators=(",", ":"), ensure_ascii=False, default=str)
    now = _iso_now()

    # Check for existing archive by execution_id
    existing = db.query_one(
        "SELECT id, evidence_hash FROM evidence_archives WHERE execution_id = ?",
        (execution_id,),
    )
    if existing is not None:
        return {
            "ok": False,
            "error": "already_stored",
            "reason": "This execution has already been archived.",
            "archiveId": existing["id"],
            "executionId": execution_id,
        }

    # Insert archive record
    db.execute(
        """
        INSERT INTO evidence_archives (
            id, evidence_hash, canonical_version, hash_algorithm,
            bundle_json, execution_id, grant_id, grant_request_id,
            created_at, stored_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            execution_id,
            evidence_hash,
            canonical_version,
            hash_algorithm,
            bundle_json,
            execution_id,
            grant_id,
            grant_request_id,
            now,
            stored_by,
        ),
    )

    # Insert hash index record
    db.execute(
        "INSERT INTO evidence_hashes (evidence_hash, archive_id, created_at) VALUES (?, ?, ?)",
        (evidence_hash, execution_id, now),
    )

    return {
        "ok": True,
        "archiveId": execution_id,
        "evidenceHash": evidence_hash,
        "storedAt": now,
        "executionId": execution_id,
    }


def get_stored_bundle(archive_id: str) -> Optional[EvidenceBundle]:
    """Load a persisted bundle record by archive ID.

    Returns an EvidenceBundle dataclass or None.
    """
    row = db.query_one("SELECT * FROM evidence_archives WHERE id = ?", (archive_id,))
    if row is None:
        return None
    return EvidenceBundle(
        id=row["id"],
        evidence_hash=row["evidence_hash"],
        canonical_version=row["canonical_version"],
        hash_algorithm=row["hash_algorithm"],
        bundle_json=row["bundle_json"],
        execution_id=row["execution_id"],
        grant_id=row["grant_id"] if row["grant_id"] is not None else None,
        grant_request_id=row["grant_request_id"] if row["grant_request_id"] is not None else None,
        created_at=row["created_at"],
        stored_by=row["stored_by"] if row["stored_by"] is not None else None,
        last_verified_at=row.get("last_verified_at"),
        last_verification_status=row.get("last_verification_status"),
    )


def get_bundle_by_execution(execution_id: str) -> Optional[EvidenceBundle]:
    """Load a persisted bundle record by execution ID (1:1 mapping)."""
    row = db.query_one(
        "SELECT * FROM evidence_archives WHERE execution_id = ?",
        (execution_id,),
    )
    if row is None:
        return None
    return EvidenceBundle(
        id=row["id"],
        evidence_hash=row["evidence_hash"],
        canonical_version=row["canonical_version"],
        hash_algorithm=row["hash_algorithm"],
        bundle_json=row["bundle_json"],
        execution_id=row["execution_id"],
        grant_id=row["grant_id"] if row["grant_id"] is not None else None,
        grant_request_id=row["grant_request_id"] if row["grant_request_id"] is not None else None,
        created_at=row["created_at"],
        stored_by=row["stored_by"] if row["stored_by"] is not None else None,
        last_verified_at=row.get("last_verified_at"),
        last_verification_status=row.get("last_verification_status"),
    )


def get_bundle_by_hash(evidence_hash: str) -> Optional[EvidenceBundle]:
    """Load a persisted bundle record by its SHA-256 evidence hash."""
    hash_row = db.query_one(
        "SELECT archive_id FROM evidence_hashes WHERE evidence_hash = ?",
        (evidence_hash,),
    )
    if hash_row is None:
        return None
    return get_stored_bundle(hash_row["archive_id"])


# ──────────────────────────────────────────────────────────────
# Listing
# ──────────────────────────────────────────────────────────────

def list_stored_bundles(
    grant_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    """Return a paginated list of archived evidence bundle summaries.

    Returns:
        {
            "items": [ { archive metadata }, ... ],
            "total": int,
            "limit": int,
            "offset": int,
        }
    """
    conditions: list[str] = []
    params: list = []

    if grant_id is not None:
        conditions.append("grant_id = ?")
        params.append(grant_id)
    if execution_id is not None:
        conditions.append("execution_id = ?")
        params.append(execution_id)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # Count total
    count_sql = f"SELECT COUNT(*) as count FROM evidence_archives {where_clause}"
    count_row = db.query_one(count_sql, tuple(params))
    total = count_row["count"] if count_row else 0

    # Fetch items
    items_sql = f"""
        SELECT id, evidence_hash, execution_id, grant_id, grant_request_id,
               created_at, stored_by, last_verified_at, last_verification_status
        FROM evidence_archives
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """
    rows = db.query_all(items_sql, tuple(params + [limit, offset]))

    items = [
        {
            "archiveId": r["id"],
            "evidenceHash": r["evidence_hash"],
            "executionId": r["execution_id"],
            "grantId": r["grant_id"],
            "grantRequestId": r["grant_request_id"],
            "storedAt": r["created_at"],
            "storedBy": r["stored_by"],
            "lastVerifiedAt": r.get("last_verified_at"),
            "lastVerificationStatus": r.get("last_verification_status"),
        }
        for r in rows
    ]

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ──────────────────────────────────────────────────────────────
# Convenience: archive on demand
# ──────────────────────────────────────────────────────────────

def archive_execution(
    execution_id: str,
    bundle: dict[str, Any],
    stored_by: Optional[str] = None,
) -> dict[str, Any]:
    """Persist an evidence bundle for an execution.

    Thin wrapper around store_bundle for explicit bundle input.
    Returns store result dict, or error if bundle invalid.
    """
    return store_bundle(execution_id, bundle, stored_by=stored_by)


def update_verification_status(archive_id: str, status: str) -> int:
    """Update last_verified_at and last_verification_status for an archive.

    Returns the number of rows updated (0 or 1).
    """
    now = _iso_now()
    return db.execute(
        """
        UPDATE evidence_archives
        SET last_verified_at = ?, last_verification_status = ?
        WHERE id = ?
        """,
        (now, status, archive_id),
    )
