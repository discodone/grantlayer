#!/usr/bin/env python3
"""GL-219 identity/access gate.

Local-only dry-run/plan helper. It does not contact identity providers, fetch
JWKS documents, validate live tokens, read credentials, or certify production
readiness.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ISSUE_ID = "GL-219"
TITLE = "Production Identity & Access Hardening Pack"

REQUIRED_PATHS = [
    "docs/production_identity_access_hardening_pack.md",
    "docs/examples/gl219/production_identity_access_hardening_pack.json",
    "docs/production_go_no_go_v5.md",
    "docs/examples/gl217/production_go_no_go_v5.json",
    "docs/production_iam_operator_control_completion.md",
    "docs/examples/gl214/production_iam_operator_control_completion.json",
    "docs/production_auth_secrets_config_hardening.md",
    "docs/examples/gl201/production_auth_secrets_config_hardening.json",
    "docs/admin_operator_tenant_control_plane.md",
    "docs/examples/gl206/admin_operator_tenant_control_plane.json",
    "docs/production_operations_hardening_pack.md",
    "docs/examples/gl216/production_operations_hardening_pack.json",
    "docs/tenant_workspace_production_guarantee.md",
    "docs/examples/gl215/tenant_workspace_production_guarantee.json",
    "docs/public_external_review_export_safety_pack.md",
    "docs/examples/gl218/public_external_review_export_safety_pack.json",
    "docs/runtime_abuse_incident_hardening.md",
    "docs/examples/gl208/runtime_abuse_incident_hardening.json",
    "docs/data_governance_audit_operations.md",
    "docs/examples/gl209/data_governance_audit_operations.json",
    "docs/openapi.yaml",
    "README.md",
    "SECURITY.md",
    "AGENTS.md",
    "llms.txt",
    "llms-full.txt",
    "backend/src/auth.py",
    "backend/src/config.py",
    "backend/src/operators.py",
    "backend/src/audit_log.py",
    "backend/src/db.py",
    "backend/src/models.py",
    "scripts/ops/gl216_production_operations_gate.py",
    "scripts/ops/gl218_public_export_safety_scan.py",
    "scripts/verify-first-output.sh",
    "examples/grant_lifecycle_evidence_bundle.py",
]

PLAN_STEPS = [
    "step_01: Verify GL-219 identity/access docs and JSON artifact exist",
    "step_02: Verify required GL-201/206/208/209/214/215/216/217/218 inputs exist",
    "step_03: Check local environment for unsupported OAuth/OIDC/JWT enablement or provider config",
    "step_04: Report required issuer, audience, expiry, signature, and key-rotation controls",
    "step_05: Preserve Developer Preview / Controlled Preview boundaries without production certification",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_posture():
    root = _repo_root()
    sys.path.insert(0, str(root / "backend"))
    from src.identity_access import describe_identity_access_posture

    return describe_identity_access_posture()


def _path_status() -> list[dict[str, object]]:
    root = _repo_root()
    return [{"path": path, "exists": (root / path).exists()} for path in REQUIRED_PATHS]


def _result(mode: str) -> dict[str, object]:
    paths = _path_status()
    missing = [item["path"] for item in paths if not item["exists"]]
    posture = _load_posture()
    unsafe = posture["fail_closed_startup_errors"]
    return {
        "issue_id": ISSUE_ID,
        "title": TITLE,
        "mode": mode,
        "result": "blocked" if missing or unsafe else "dry_run_passed",
        "not_production_readiness_certification": True,
        "external_services_contacted": False,
        "network_required": False,
        "credentials_required": False,
        "tokens_read_or_logged": False,
        "destructive_operations": False,
        "public_artifacts_created": False,
        "missing_required_paths": missing,
        "identity_access_posture": posture,
        "remaining_blockers": [
            "production OAuth/OIDC/JWT validator is not implemented",
            "static admin token remains a production blocker",
            "SSO, MFA, dual-control, break-glass governance, and deprovisioning feeds remain absent",
            "workspace enforcement, RLS, and tenant lifecycle remain blockers",
            "real customer/private grant/institutional data remains no-go",
        ],
    }


def _print_plan() -> int:
    print("[GL-219] Production Identity & Access Gate - PLAN mode")
    for step in PLAN_STEPS:
        print(f"[GL-219]   {step}")
    print("[GL-219] No network calls are made.")
    print("[GL-219] No credentials or raw tokens are required.")
    print("[GL-219] This is not production readiness certification.")
    return 0


def _print_dry_run(as_json: bool) -> int:
    result = _result("dry_run")
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("[GL-219] Production Identity & Access Gate - DRY-RUN mode")
        print("[GL-219] No provider calls, credentials, raw tokens, or destructive commands.")
        print("[GL-219] This is not production readiness certification.")
        if result["missing_required_paths"]:
            print("[GL-219] Missing required paths:")
            for path in result["missing_required_paths"]:
                print(f"[GL-219]   {path}")
        else:
            print("[GL-219] Required paths are present.")
        posture = result["identity_access_posture"]
        if posture["fail_closed_startup_errors"]:
            print("[GL-219] Fail-closed identity findings:")
            for finding in posture["fail_closed_startup_errors"]:
                print(f"[GL-219]   {finding}")
        else:
            print("[GL-219] No unsupported external identity enablement detected.")
        print("[GL-219] Production identity remains blocked.")
    return 2 if result["missing_required_paths"] or result["identity_access_posture"]["fail_closed_startup_errors"] else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GL-219 dry-run identity/access gate")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="run local-only checklist checks")
    mode.add_argument("--plan", action="store_true", help="print safe plan steps")
    parser.add_argument("--json", action="store_true", help="emit JSON for --dry-run")
    args = parser.parse_args(argv)

    if args.json and not args.dry_run:
        parser.error("--json is only valid with --dry-run")

    if args.plan:
        return _print_plan()
    return _print_dry_run(args.json)


if __name__ == "__main__":
    raise SystemExit(main())
