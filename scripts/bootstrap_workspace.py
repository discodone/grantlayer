#!/usr/bin/env python3
"""Create ONE real workspace — a deliberate operator ceremony, not automation.

READ BEFORE RUNNING
    This writes a workspace row, an owner membership row, and TWO audit events
    into the configured database. The audit events are hash-chained and
    immutable (DB triggers forbid update/delete) — they become entries 1 and 2
    of the new workspace's audit chain, and if that chain is later anchored
    on-chain they are attested permanently. Run this against the database you
    mean, deliberately.

    The target database comes from the same environment the app uses:
    GRANTLAYER_DATABASE_URL (PostgreSQL) or GRANTLAYER_DB (SQLite path).

    Safety properties (enforced by the bootstrap itself, not this script):
      * refuses if the owner operator is missing, inactive, or wrong-tenant —
        create the operator first (POST /v1/admin/operators);
      * re-running with identical arguments is a no-op ("already exists");
      * an existing different workspace on the same (tenant, slug) is a hard
        error — this script never clobbers.

Usage:
    python3 scripts/bootstrap_workspace.py \\
        --tenant-id hofer --name hofercloud --slug hofercloud \\
        --owner-operator-id <operator-uuid>

Exit codes:
    0 — created, or identical workspace already exists (idempotent no-op)
    1 — refused (invalid owner, conflict, bad arguments, DB failure)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _describe_db_target() -> str:
    """Human-readable DB target WITHOUT credentials (PG URLs carry a password)."""
    from backend.src.core.db import DB_BACKEND, DB_PATH_OR_URL

    if DB_BACKEND == "postgres":
        parsed = urlparse(DB_PATH_OR_URL)
        host = parsed.hostname or "?"
        port = f":{parsed.port}" if parsed.port else ""
        db = parsed.path.lstrip("/") or "?"
        return f"postgres://{host}{port}/{db}"
    return f"sqlite:///{DB_PATH_OR_URL}"


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="bootstrap_workspace.py",
        description=(
            "Create one real workspace with one owner operator (idempotent, "
            "refuse-to-clobber). The owner operator must already exist."
        ),
    )
    parser.add_argument("--tenant-id", required=True, help="tenant the workspace belongs to")
    parser.add_argument("--name", required=True, help="human-readable workspace name")
    parser.add_argument("--slug", required=True, help="unique slug within the tenant")
    parser.add_argument(
        "--owner-operator-id",
        required=True,
        help="id of an EXISTING active operator in the same tenant",
    )
    parser.add_argument("--description", default=None, help="optional description")
    parser.add_argument(
        "--plan-tier",
        default="free",
        help="plan tier (free|pro|enterprise), default free",
    )
    args = parser.parse_args()

    from backend.src.core.db import get_session_maker
    from backend.src.workspaces.bootstrap import (
        WorkspaceBootstrapError,
        bootstrap_workspace,
    )

    print(f"target database : {_describe_db_target()}")
    print(f"tenant/slug     : {args.tenant_id} / {args.slug}")
    print(f"owner operator  : {args.owner_operator_id}")

    maker = get_session_maker()
    with maker() as session:
        try:
            result = bootstrap_workspace(
                session,
                tenant_id=args.tenant_id,
                name=args.name,
                slug=args.slug,
                owner_operator_id=args.owner_operator_id,
                description=args.description,
                plan_tier=args.plan_tier,
            )
        except WorkspaceBootstrapError as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 1

    if result["status"] == "already_exists":
        print("already exists — identical workspace present, nothing written")
        print(f"workspace_id    : {result['workspace_id']}")
        return 0

    print("created — workspace, owner membership, and 2 genesis audit events")
    print(f"workspace_id    : {result['workspace_id']}")
    print()
    print("NEXT: operators call the API with X-Workspace-Id set to this id.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
