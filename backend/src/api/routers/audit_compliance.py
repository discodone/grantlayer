"""Audit log compliance export + immutability proof."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from ...audit.audit_log import _row_to_audit_event, list_events
from ...core.orm import AuditEvent as _AuditEventORM
from ..deps import resolve_auth_and_workspace

router = APIRouter(prefix="/audit", tags=["audit-compliance"])

_HMAC_KEY_ENV = "GRANTLAYER_AUDIT_HMAC_KEY"
_DEFAULT_HMAC_KEY = "grantlayer-audit-hmac-default-key"


def _get_hmac_key() -> bytes:
    return os.environ.get(_HMAC_KEY_ENV, _DEFAULT_HMAC_KEY).encode()


def _entry_canonical(entry: dict[str, Any]) -> str:
    # Additive-and-forward-only fields are OMITTED from the canonical when their
    # value is None, so introducing such a column never alters the canonical of
    # any event written before it existed — every past on-chain anchor stays
    # recomputable. A field only enters the fold once an event actually carries
    # a value for it. `reason_code` (the machine decision code) is the first
    # such field; the same rule as the row_hash payload's dual-mode tenant_id.
    _forward_only_when_null = ("reason_code",)
    keys = [
        k for k in sorted(entry.keys())
        if not (k in _forward_only_when_null and entry.get(k) is None)
    ]
    return json.dumps(
        {k: entry.get(k) for k in keys},
        sort_keys=True,
        ensure_ascii=True,
    )


def _chain_hash(prev_hash: str, entry_canonical: str) -> str:
    return hashlib.sha256((prev_hash + entry_canonical).encode()).hexdigest()


# Genesis seed for the export chain.
_GENESIS = "0" * 64


def _iter_chain(records: list[dict[str, Any]]):
    """Left-fold the export chain from the genesis seed.

    Yields (record, prev_hash, entry_hash) per record. The per-entry hash is
    SHA-256 over (prev_hash + _entry_canonical(record without _-prefixed fields)),
    and the next prev_hash is the current entry_hash. This is the SINGLE
    definition of the genesis-seed + left-fold shared by the public export
    (_generate), the offline verifier (verify_ndjson_export), and
    recompute_head_from_records.
    """
    prev = _GENESIS
    for record in records:
        clean = {k: v for k, v in record.items() if not k.startswith("_")}
        entry_hash = _chain_hash(prev, _entry_canonical(clean))
        yield record, prev, entry_hash
        prev = entry_hash


def recompute_head_from_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Recompute the chain head from entry records.

    Records may be clean entry dicts or full exported lines (any _-prefixed
    chain fields are ignored). Genesis seed is "0"*64; per-record canonical +
    chain hash, no separator, left fold. Returns
    {"final_hash": str, "entry_count": int}.
    """
    final = _GENESIS
    count = 0
    for _record, _prev, entry_hash in _iter_chain(records):
        final = entry_hash
        count += 1
    return {"final_hash": final, "entry_count": count}


def _sign_manifest(all_hashes: list[str]) -> str:
    payload = "\n".join(all_hashes).encode()
    key = _get_hmac_key()
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


@router.get("/export")
async def export_audit_log(
    start_date: Optional[str] = Query(default=None, description="ISO date filter start"),
    end_date: Optional[str] = Query(default=None, description="ISO date filter end"),
    limit: int = Query(default=10000, ge=1, le=100000),
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
) -> StreamingResponse:
    """Stream NDJSON audit export with chain hashes + HMAC manifest footer."""
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    workspace_id = ws_ctx["workspace_id"]

    raw_events = list_events(
        limit=limit,
        offset=0,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )
    events = [e.to_dict() for e in raw_events]

    # Filter by date if provided
    if start_date:
        events = [e for e in events if (e.get("timestamp") or "") >= start_date]
    if end_date:
        events = [e for e in events if (e.get("timestamp") or "") <= end_date]

    def _generate():
        all_hashes: list[str] = []
        final_hash = _GENESIS

        # _iter_chain is the single shared genesis-seed + left-fold primitive.
        for event, prev_hash, entry_hash in _iter_chain(events):
            record = {**event, "_chain_hash": entry_hash, "_prev_hash": prev_hash}
            all_hashes.append(entry_hash)
            final_hash = entry_hash
            yield json.dumps(record, ensure_ascii=True) + "\n"

        # HMAC-signed manifest as final NDJSON record
        manifest = {
            "_type": "manifest",
            "_entry_count": len(all_hashes),
            "_final_hash": final_hash,
            "_hmac_signature": _sign_manifest(all_hashes),
        }
        yield json.dumps(manifest, ensure_ascii=True) + "\n"

    return StreamingResponse(
        _generate(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="audit-export.ndjson"'},
    )


@router.get("/verify", response_model=dict[str, Any])
async def verify_audit_chain(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    limit: int = Query(default=10000, ge=1, le=100000),
    authorization: Annotated[Optional[str], Header()] = None,
    x_workspace_id: Annotated[Optional[str], Header(alias="X-Workspace-Id")] = None,
) -> Any:
    """Verify audit chain integrity. Returns {valid, checked, broken_at}."""
    _, ws_ctx = resolve_auth_and_workspace(
        authorization,
        required_roles=["owner", "grant_admin", "auditor"],
        workspace_id=x_workspace_id,
    )
    tenant_id = ws_ctx["tenant_id"]
    workspace_id = ws_ctx["workspace_id"]

    raw_events_verify = list_events(
        limit=limit,
        offset=0,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )
    events_verify = [e.to_dict() for e in raw_events_verify]

    if start_date:
        events_verify = [e for e in events_verify if (e.get("timestamp") or "") >= start_date]
    if end_date:
        events_verify = [e for e in events_verify if (e.get("timestamp") or "") <= end_date]

    prev_hash = "0" * 64
    broken_at = None

    for event in events_verify:
        canonical = _entry_canonical(event)
        expected_hash = _chain_hash(prev_hash, canonical)
        stored_hash = event.get("row_hash")

        if stored_hash and stored_hash != expected_hash:
            broken_at = event.get("id")
            break

        prev_hash = stored_hash or expected_hash

    return {
        "valid": broken_at is None,
        "checked": len(events_verify),
        "broken_at": broken_at,
    }


def verify_ndjson_export(ndjson_content: str) -> dict[str, Any]:
    """Verify an exported NDJSON file offline. Used by CLI verify script."""
    lines = [line.strip() for line in ndjson_content.strip().splitlines() if line.strip()]
    if not lines:
        return {"valid": False, "checked": 0, "broken_at": None, "error": "empty_export"}

    records = [json.loads(line) for line in lines]
    manifest = None
    if records and records[-1].get("_type") == "manifest":
        manifest = records.pop()

    all_hashes = []
    broken_at = None

    # Same genesis-seed + left-fold as the export (via _iter_chain), with
    # per-line linkage + tamper localization layered on top.
    for record, prev_hash, expected_hash in _iter_chain(records):
        stored_chain = record.get("_chain_hash")
        stored_prev = record.get("_prev_hash")

        if stored_prev != prev_hash:
            broken_at = record.get("id")
            break

        if stored_chain and stored_chain != expected_hash:
            broken_at = record.get("id")
            break

        all_hashes.append(stored_chain or expected_hash)

    result: dict[str, Any] = {
        "valid": broken_at is None,
        "checked": len(records),
        "broken_at": broken_at,
    }

    if manifest and broken_at is None:
        expected_sig = _sign_manifest(all_hashes)
        result["manifest_valid"] = manifest.get("_hmac_signature") == expected_sig

    return result


# ──────────────────────────────────────────────────────────────────────────
# Anchor export — single-workspace, full chain, stable seq-ASC order.
# ──────────────────────────────────────────────────────────────────────────

def _load_workspace_entries(session: Any, workspace_id: str) -> list[dict]:
    """Load a workspace's full audit chain as public-export entry dicts.

    FULL chain — NO date filter, NO limit — ordered by the stable ``seq`` ASC
    total order (the public endpoint's ``timestamp DESC, seq DESC`` is NOT used;
    seq ASC is the determinism guarantee). Rows are normalized through the SAME
    ``_row_to_audit_event``/``to_dict`` path as the public export, so the
    per-entry canonicalization is byte-for-byte identical.
    """
    rows = (
        session.execute(
            select(_AuditEventORM)
            .where(_AuditEventORM.workspace_id == workspace_id)
            .order_by(_AuditEventORM.seq.asc(), _AuditEventORM.id.asc())
        )
        .scalars()
        .all()
    )
    entries: list[dict] = []
    for orm in rows:
        row = {
            "id": orm.id,
            "timestamp": orm.timestamp,
            "subject_id": orm.subject_id,
            "role": orm.role,
            "action": orm.action,
            "resource": orm.resource,
            "approved": orm.approved,
            "reason": orm.reason,
            "matched_grant_id": orm.matched_grant_id,
            "challenge_id": orm.challenge_id,
            "challenge_present": orm.challenge_present,
            "challenge_result": orm.challenge_result,
            "grant_signature_result": orm.grant_signature_result,
            "row_hash": orm.row_hash,
            "prev_hash": orm.prev_hash,
            "tenant_id": orm.tenant_id,
            "workspace_id": orm.workspace_id,
            "scope": orm.scope,
            "seq": orm.seq,
            "reason_code": orm.reason_code,
        }
        entries.append(_row_to_audit_event(row).to_dict())
    return entries


def _build_anchor_export(session: Any, workspace_id: str) -> str:
    """Build the canonical NDJSON anchor export for ONE workspace's full chain.

    Determinism contract: FULL chain, no date filter, NO limit, ordered by
    ``seq`` ASC (stable total order). Each data line is the entry dict plus
    ``_chain_hash``/``_prev_hash`` (same per-entry canonicalization as the public
    export); the final manifest line carries ``_final_hash`` + ``_entry_count``
    computed via ``recompute_head_from_records``.
    """
    entries = _load_workspace_entries(session, workspace_id)
    lines: list[str] = []
    all_hashes: list[str] = []
    for entry, prev_hash, entry_hash in _iter_chain(entries):
        lines.append(
            json.dumps(
                {**entry, "_chain_hash": entry_hash, "_prev_hash": prev_hash},
                ensure_ascii=True,
            )
        )
        all_hashes.append(entry_hash)
    head = recompute_head_from_records(entries)
    manifest = {
        "_type": "manifest",
        "_entry_count": head["entry_count"],
        "_final_hash": head["final_hash"],
        "_hmac_signature": _sign_manifest(all_hashes),
    }
    lines.append(json.dumps(manifest, ensure_ascii=True))
    return "\n".join(lines) + "\n"


def anchor_head(session: Any, workspace_id: str) -> dict[str, Any]:
    """Return {"final_hash", "entry_count"} for a workspace's full audit chain."""
    return recompute_head_from_records(_load_workspace_entries(session, workspace_id))
