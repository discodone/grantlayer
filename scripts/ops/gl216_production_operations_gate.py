#!/usr/bin/env python3
"""GL-216 production operations gate.

Dry-run/plan-only checklist helper for the GL-216 hardening pack. It does not
connect to services, read real credentials, mutate databases, or certify
production readiness.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


ISSUE_ID = "GL-216"
TITLE = "Production Operations Hardening Pack"

REQUIRED_PATHS = [
    "docs/production_operations_hardening_pack.md",
    "docs/examples/gl216/production_operations_hardening_pack.json",
    "docs/production_readiness_gap_report_v4.md",
    "docs/examples/gl213/production_readiness_gap_report_v4.json",
    "docs/tenant_workspace_production_guarantee.md",
    "docs/examples/gl215/tenant_workspace_production_guarantee.json",
    "docs/production_iam_operator_control_completion.md",
    "docs/examples/gl214/production_iam_operator_control_completion.json",
    "docs/live_postgres_validation_execution_gl206b.md",
    "docs/examples/gl206b/live_postgres_validation_execution_gl206b.json",
    "docs/live_postgres_backup_observability_baseline.md",
    "docs/examples/gl205/live_postgres_backup_observability_baseline.json",
    "docs/data_governance_audit_operations.md",
    "docs/examples/gl209/data_governance_audit_operations.json",
    "docs/runtime_abuse_incident_hardening.md",
    "docs/examples/gl208/runtime_abuse_incident_hardening.json",
    "docs/admin_operator_tenant_control_plane.md",
    "docs/examples/gl206/admin_operator_tenant_control_plane.json",
    "docs/production_ops_go_no_go_v3.md",
    "docs/examples/gl204/production_ops_go_no_go_v3.json",
    "docs/persistence_postgres_migration_readiness.md",
    "docs/examples/gl202/persistence_postgres_migration_readiness.json",
    "docs/production_auth_secrets_config_hardening.md",
    "docs/examples/gl201/production_auth_secrets_config_hardening.json",
    "docs/public_external_review_readiness_gate_pack.md",
    "docs/examples/gl212/public_external_review_readiness_gate_pack.json",
    "docs/sdk_pilot_production_gate.md",
    "docs/examples/gl211/sdk_pilot_production_gate.json",
    "README.md",
    "SECURITY.md",
    "AGENTS.md",
    "llms.txt",
    "llms-full.txt",
    "docs/openapi.yaml",
    "backend/src/server.py",
    "backend/src/core/config.py",
    "backend/src/auth/auth.py",
    "backend/src/auth/operators.py",
    "backend/src/audit_log.py",
    "backend/src/core/db.py",
    "backend/src/core/models.py",
    "backend/src/grants.py",
    "backend/src/grant_requests.py",
    "scripts/ops/gl205_live_postgres_validation.py",
    "scripts/ops/gl205_backup_restore_drill.py",
    "scripts/ops/gl209_audit_export_check.py",
    "scripts/run-full-backend-suite.sh",
    "examples/grant_lifecycle_evidence_bundle.py",
]

PLAN_STEPS = [
    "step_01: Verify GL-216 documentation and JSON artifact exist",
    "step_02: Verify prior operational, IAM, tenant/workspace, audit, and readiness inputs exist",
    "step_03: Check for unsafe production-like DB, credential, token, or cloud environment variables",
    "step_04: Print safe follow-up commands only; do not connect to services",
    "step_05: Report remaining production operations blockers without certification language",
]

SENSITIVE_ENV_NAME = re.compile(
    r"(TOKEN|PASSWORD|PASS|SECRET|PRIVATE[_-]?KEY|AUTH|CREDENTIAL|DSN|DATABASE_URL|POSTGRES|PGURL)",
    re.IGNORECASE,
)
PRODUCTION_LIKE_VALUE = re.compile(
    r"(prod|production|staging|customer|client|institution|private|grantdata|realdata)",
    re.IGNORECASE,
)
DSN_LIKE_VALUE = re.compile(r"(postgres(ql)?://|mysql://|mariadb://|mongodb://|redis://)", re.IGNORECASE)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _redact(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = urlparse(value)
        if parsed.scheme and parsed.netloc:
            host = parsed.hostname or "unknown"
            port = f":{parsed.port}" if parsed.port else ""
            user = parsed.username or "user"
            db = (parsed.path or "").lstrip("/") or "db"
            return f"{parsed.scheme}://{user}:***@{host}{port}/{db}"
    except Exception:
        pass
    redacted = re.sub(r"(?i)(bearer\s+)[a-z0-9._~+/=-]+", r"\1***", value)
    redacted = re.sub(r"(?i)(password|token|secret|private[_-]?key)=([^&\s]+)", r"\1=***", redacted)
    if len(redacted) > 24:
        return redacted[:8] + "***" + redacted[-4:]
    return "***"


def _unsafe_env_findings() -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for name, value in sorted(os.environ.items()):
        if not SENSITIVE_ENV_NAME.search(name):
            continue
        if not value:
            continue
        unsafe = False
        reason = ""
        if DSN_LIKE_VALUE.search(value):
            unsafe = True
            reason = "dsn-like value present"
        if PRODUCTION_LIKE_VALUE.search(name) or PRODUCTION_LIKE_VALUE.search(value):
            unsafe = True
            reason = reason or "production-like name or value"
        if unsafe:
            findings.append(
                {
                    "env": name,
                    "reason": reason,
                    "redacted_value": _redact(value),
                }
            )
    return findings


def _path_status() -> list[dict[str, object]]:
    root = _repo_root()
    return [
        {"path": path, "exists": (root / path).exists()}
        for path in REQUIRED_PATHS
    ]


def _result(mode: str) -> dict[str, object]:
    paths = _path_status()
    unsafe_env = _unsafe_env_findings()
    missing = [item["path"] for item in paths if not item["exists"]]
    return {
        "issue_id": ISSUE_ID,
        "title": TITLE,
        "mode": mode,
        "result": "blocked" if missing or unsafe_env else "dry_run_passed",
        "not_production_readiness_certification": True,
        "external_services_contacted": False,
        "network_required": False,
        "credentials_required": False,
        "destructive_operations": False,
        "public_artifacts_created": False,
        "missing_required_paths": missing,
        "unsafe_environment_findings": unsafe_env,
        "remaining_blockers": [
            "production PostgreSQL operations remain no-go",
            "automated backup scheduling, restore RTO/RPO, and DR failover remain blockers",
            "external monitoring, alerting, tracing, and pager integration remain blockers",
            "secret/key rotation automation and KMS/HSM lifecycle remain blockers",
            "real customer/private grant/institutional data remains no-go",
        ],
    }


def _print_plan() -> int:
    print("[GL-216] Production Operations Gate - PLAN mode")
    for step in PLAN_STEPS:
        print(f"[GL-216]   {step}")
    print("[GL-216] No network calls are made.")
    print("[GL-216] No credentials are required.")
    print("[GL-216] No destructive commands are run.")
    print("[GL-216] This is not production readiness certification.")
    return 0


def _print_dry_run(as_json: bool) -> int:
    result = _result("dry_run")
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("[GL-216] Production Operations Gate - DRY-RUN mode")
        print("[GL-216] No network calls, credentials, DB connections, or destructive commands.")
        print("[GL-216] This is not production readiness certification.")
        if result["missing_required_paths"]:
            print("[GL-216] Missing required paths:")
            for path in result["missing_required_paths"]:
                print(f"[GL-216]   {path}")
        else:
            print("[GL-216] Required paths are present.")
        if result["unsafe_environment_findings"]:
            print("[GL-216] Unsafe environment findings:")
            for finding in result["unsafe_environment_findings"]:
                print(
                    "[GL-216]   "
                    f"{finding['env']}: {finding['reason']} ({finding['redacted_value']})"
                )
        else:
            print("[GL-216] No production-like credential or DSN environment variables detected.")
    return 2 if result["missing_required_paths"] or result["unsafe_environment_findings"] else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GL-216 dry-run production operations gate")
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
