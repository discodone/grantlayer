"""Audit log compliance export + immutability proof."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header, Query
from fastapi.responses import StreamingResponse

from ...audit.audit_log import list_events
from ..deps import resolve_auth_and_workspace

router = APIRouter(prefix="/audit", tags=["audit-compliance"])

_HMAC_KEY_ENV = "GRANTLAYER_AUDIT_HMAC_KEY"
_DEFAULT_HMAC_KEY = "grantlayer-audit-hmac-default-key"


def _get_hmac_key() -> bytes:
    return os.environ.get(_HMAC_KEY_ENV, _DEFAULT_HMAC_KEY).encode()


def _entry_canonical(entry: dict[str, Any]) -> str:
    return json.dumps(
        {k: entry.get(k) for k in sorted(entry.keys())},
        sort_keys=True,
        ensure_ascii=True,
    )


def _chain_hash(prev_hash: str, entry_canonical: str) -> str:
    return hashlib.sha256((prev_hash + entry_canonical).encode()).hexdigest()


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
        prev_hash = "0" * 64
        all_hashes = []

        for event in events:
            canonical = _entry_canonical(event)
            entry_hash = _chain_hash(prev_hash, canonical)
            record = {**event, "_chain_hash": entry_hash, "_prev_hash": prev_hash}
            all_hashes.append(entry_hash)
            prev_hash = entry_hash
            yield json.dumps(record, ensure_ascii=True) + "\n"

        # HMAC-signed manifest as final NDJSON record
        manifest = {
            "_type": "manifest",
            "_entry_count": len(all_hashes),
            "_final_hash": prev_hash,
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

    prev_hash = "0" * 64
    all_hashes = []
    broken_at = None

    for record in records:
        stored_chain = record.get("_chain_hash")
        stored_prev = record.get("_prev_hash")

        if stored_prev != prev_hash:
            broken_at = record.get("id")
            break

        # Recompute hash from the original entry (without chain fields)
        clean = {k: v for k, v in record.items() if not k.startswith("_")}
        canonical = _entry_canonical(clean)
        expected_hash = _chain_hash(prev_hash, canonical)

        if stored_chain and stored_chain != expected_hash:
            broken_at = record.get("id")
            break

        all_hashes.append(stored_chain or expected_hash)
        prev_hash = stored_chain or expected_hash

    result: dict[str, Any] = {
        "valid": broken_at is None,
        "checked": len(records),
        "broken_at": broken_at,
    }

    if manifest and broken_at is None:
        expected_sig = _sign_manifest(all_hashes)
        result["manifest_valid"] = manifest.get("_hmac_signature") == expected_sig

    return result
