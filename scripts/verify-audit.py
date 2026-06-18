#!/usr/bin/env python3
"""Offline audit log integrity verifier.

Usage:
    python3 scripts/verify-audit.py audit-export.ndjson

Reads a GrantLayer audit export (NDJSON format with _chain_hash fields)
and verifies the hash chain integrity without network access.

Exit codes:
    0 — chain valid
    1 — chain broken or error
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: verify-audit.py <export.ndjson>", file=sys.stderr)
        return 1

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    content = path.read_text()

    # Import verify function from the GrantLayer package if available,
    # otherwise use inline logic.
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from backend.src.api.routers.audit_compliance import verify_ndjson_export
        result = verify_ndjson_export(content)
    except ImportError:
        result = _verify_inline(content)

    print(json.dumps(result, indent=2))

    if result.get("valid"):
        print(f"\n✓ Chain valid — {result['checked']} entries verified")
        return 0
    else:
        broken = result.get("broken_at")
        print(f"\n✗ Chain broken at entry: {broken}")
        return 1


def _verify_inline(content: str) -> dict:
    """Fallback inline verifier (no package imports required)."""
    import hashlib

    lines = [l.strip() for l in content.strip().splitlines() if l.strip()]
    if not lines:
        return {"valid": False, "checked": 0, "broken_at": None, "error": "empty"}

    records = [json.loads(l) for l in lines]
    if records and records[-1].get("_type") == "manifest":
        records.pop()

    prev_hash = "0" * 64
    broken_at = None

    for record in records:
        stored_prev = record.get("_prev_hash")
        stored_chain = record.get("_chain_hash")

        if stored_prev != prev_hash:
            broken_at = record.get("id", "unknown")
            break

        clean = {k: v for k, v in record.items() if not k.startswith("_")}
        canonical = json.dumps(
            {k: clean.get(k) for k in sorted(clean.keys())},
            sort_keys=True, ensure_ascii=True,
        )
        expected = hashlib.sha256((prev_hash + canonical).encode()).hexdigest()

        if stored_chain and stored_chain != expected:
            broken_at = record.get("id", "unknown")
            break

        prev_hash = stored_chain or expected

    return {
        "valid": broken_at is None,
        "checked": len(records),
        "broken_at": broken_at,
    }


if __name__ == "__main__":
    sys.exit(main())
