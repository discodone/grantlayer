#!/usr/bin/env python3
"""GL-220 runtime/infrastructure gate.

Local-only dry-run/plan helper for GL-220. It checks documentation, branch
scope, obvious unsafe runtime environment patterns, and conservative claim
boundaries. It does not contact services, require credentials, run destructive
commands, create deployment artifacts, or certify production infrastructure.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


ISSUE_ID = "GL-220"
TITLE = "Production Runtime & Infrastructure Hardening Pack"

REQUIRED_PATHS = [
    "docs/production_runtime_infrastructure_hardening_pack.md",
    "docs/examples/gl220/production_runtime_infrastructure_hardening_pack.json",
    "docs/production_go_no_go_v5.md",
    "docs/examples/gl217/production_go_no_go_v5.json",
    "docs/production_identity_access_hardening_pack.md",
    "docs/examples/gl219/production_identity_access_hardening_pack.json",
    "docs/public_external_review_export_safety_pack.md",
    "docs/examples/gl218/public_external_review_export_safety_pack.json",
    "docs/production_operations_hardening_pack.md",
    "docs/examples/gl216/production_operations_hardening_pack.json",
    "docs/tenant_workspace_production_guarantee.md",
    "docs/examples/gl215/tenant_workspace_production_guarantee.json",
    "docs/production_iam_operator_control_completion.md",
    "docs/examples/gl214/production_iam_operator_control_completion.json",
    "docs/runtime_abuse_incident_hardening.md",
    "docs/examples/gl208/runtime_abuse_incident_hardening.json",
    "docs/live_postgres_backup_observability_baseline.md",
    "docs/examples/gl205/live_postgres_backup_observability_baseline.json",
    "docs/production_ops_go_no_go_v3.md",
    "docs/examples/gl204/production_ops_go_no_go_v3.json",
    "README.md",
    "SECURITY.md",
    "AGENTS.md",
    "llms.txt",
    "llms-full.txt",
    "docs/openapi.yaml",
    "backend/src/server.py",
    "backend/src/config.py",
    "backend/src/auth.py",
    "backend/src/identity_access.py",
    "backend/src/operators.py",
    "backend/src/audit_log.py",
    "backend/src/db.py",
    "backend/src/models.py",
    "scripts/ops/gl216_production_operations_gate.py",
    "scripts/ops/gl218_public_export_safety_scan.py",
    "scripts/ops/gl219_identity_access_gate.py",
    "scripts/ops/gl205_live_postgres_validation.py",
    "scripts/ops/gl205_backup_restore_drill.py",
    "scripts/ops/gl209_audit_export_check.py",
    "scripts/run-full-backend-suite.sh",
    "examples/grant_lifecycle_evidence_bundle.py",
]

ALLOWED_CHANGED_FILES = {
    "backend/tests/test_gl220_production_runtime_infrastructure_hardening_pack.py",
    "docs/production_runtime_infrastructure_hardening_pack.md",
    "docs/examples/gl220/production_runtime_infrastructure_hardening_pack.json",
    "scripts/ops/gl220_runtime_infrastructure_gate.py",
}

FORBIDDEN_EXACT = {
    "setup.py",
    "package.json",
    "package-lock.json",
    "pyproject.toml",
    "sdk/pyproject.toml",
    "examples/sdk_prototype/python/pyproject.toml",
}

FORBIDDEN_PREFIXES = (
    ".github/workflows/",
    "frontend/",
    "website/",
    "website-design/",
    "backend/src/migrations/",
    "public-export/",
    "public_snapshot/",
    "dist/",
    "release/",
    "deploy/",
    "deployment/",
    "terraform/",
    "kubernetes/",
    "helm/",
    "cloud/",
)

FORBIDDEN_SUFFIXES = (
    ".tf",
    ".tfvars",
    ".pem",
    ".key",
    ".crt",
    ".cer",
    ".p12",
    ".pfx",
)

FORBIDDEN_OVERCLAIMS = [
    "Production SaaS " + "is ready",
    "production-ready " + "SaaS",
    "ready for real " + "customer data",
    "ready for private " + "grant data",
    "ready for " + "institutional data",
    "official SDK " + "is available",
    "compliance " + "certified",
    "GDPR " + "ready",
    "SOC2 " + "ready",
    "ISO " + "ready",
    "live PostgreSQL production " + "ready",
    "production infrastructure " + "certified",
]

PLAN_STEPS = [
    "step_01: Verify GL-220 documentation, JSON artifact, and local gate script exist",
    "step_02: Verify prior runtime, identity, ops, tenant, audit, and go/no-go inputs exist",
    "step_03: Check branch scope for forbidden deployment, cloud, package, workflow, public export, migration, and TLS key paths",
    "step_04: Check GL-220 docs and script for conservative no-go claims and obvious secret-like values",
    "step_05: Inspect runtime environment names for production-like DSN, token, private-key, cloud, or credential patterns and redact values",
    "step_06: Report remaining runtime/infrastructure blockers without production infrastructure certification",
]

SECRET_ENV_NAME = re.compile(
    r"(TOKEN|PASSWORD|PASS|SECRET|PRIVATE[_-]?KEY|AUTH|CREDENTIAL|DSN|DATABASE_URL|POSTGRES|PGURL|AWS_|GCP_|AZURE_|CLOUD)",
    re.IGNORECASE,
)
PRODUCTION_LIKE_VALUE = re.compile(
    r"(prod|production|staging|customer|client|institution|private|grantdata|realdata|cloud|kubernetes|terraform|helm)",
    re.IGNORECASE,
)
DSN_LIKE_VALUE = re.compile(r"(postgres(ql)?://|mysql://|mariadb://|mongodb://|redis://)", re.IGNORECASE)
SECRET_LIKE_TEXT = [
    re.compile(r"Bearer\s+eyJ", re.IGNORECASE),
    re.compile(r"BEGIN\s+(RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY", re.IGNORECASE),
    re.compile(r"postgres(ql)?://[^/\s:]+:[^@\s]+@", re.IGNORECASE),
    re.compile(r"password\s*=\s*[^*\s]+", re.IGNORECASE),
]


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
    value = re.sub(r"(?i)(bearer\s+)[a-z0-9._~+/=-]+", r"\1***", value)
    value = re.sub(r"(?i)(password|token|secret|private[_-]?key)=([^&\s]+)", r"\1=***", value)
    if len(value) > 24:
        return value[:8] + "***" + value[-4:]
    return "***"


def _git_lines(args: list[str]) -> list[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=_repo_root(),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _changed_files() -> set[str]:
    changed = set(_git_lines(["diff", "--name-only", "main...HEAD"]))
    for line in _git_lines(["status", "--porcelain", "--untracked-files=all"]):
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        path = parts[1]
        if path.startswith("docs/website_design_") or path.startswith("docs/website-design-"):
            continue
        if path.startswith("website-design/"):
            continue
        changed.add(path)
    return changed


def _path_status() -> list[dict[str, object]]:
    root = _repo_root()
    return [{"path": path, "exists": (root / path).exists()} for path in REQUIRED_PATHS]


def _forbidden_path_findings(changed: set[str]) -> list[str]:
    findings: list[str] = []
    for path in sorted(changed):
        name = Path(path).name
        lower = path.lower()
        if path not in ALLOWED_CHANGED_FILES:
            findings.append(f"unexpected_changed_file:{path}")
        if path in FORBIDDEN_EXACT or name in FORBIDDEN_EXACT:
            findings.append(f"forbidden_exact_path:{path}")
        if path.startswith(FORBIDDEN_PREFIXES):
            findings.append(f"forbidden_prefix:{path}")
        if lower.endswith(FORBIDDEN_SUFFIXES):
            findings.append(f"forbidden_secret_or_deployment_suffix:{path}")
    return findings


def _claim_and_secret_findings() -> list[str]:
    root = _repo_root()
    paths = [
        root / "docs/production_runtime_infrastructure_hardening_pack.md",
        root / "docs/examples/gl220/production_runtime_infrastructure_hardening_pack.json",
        root / "scripts/ops/gl220_runtime_infrastructure_gate.py",
    ]
    findings: list[str] = []
    root = _repo_root()
    script_path = root / "scripts/ops/gl220_runtime_infrastructure_gate.py"
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if path != script_path:
            for phrase in FORBIDDEN_OVERCLAIMS:
                if phrase in text:
                    findings.append(f"overclaim:{path.relative_to(root)}:{phrase}")
        for pattern in SECRET_LIKE_TEXT:
            if pattern.search(text):
                findings.append(f"secret_like_text:{path.relative_to(root)}:{pattern.pattern}")
    return findings


def _unsafe_env_findings() -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for name, value in sorted(os.environ.items()):
        if not value or not SECRET_ENV_NAME.search(name):
            continue
        reason = ""
        if DSN_LIKE_VALUE.search(value):
            reason = "dsn-like value present"
        if PRODUCTION_LIKE_VALUE.search(name) or PRODUCTION_LIKE_VALUE.search(value):
            reason = reason or "production-like name or value"
        if reason:
            findings.append({"env": name, "reason": reason, "redacted_value": _redact(value)})
    return findings


def _result(mode: str) -> dict[str, object]:
    paths = _path_status()
    missing = [item["path"] for item in paths if not item["exists"]]
    changed = _changed_files()
    forbidden_paths = _forbidden_path_findings(changed)
    claim_secret_findings = _claim_and_secret_findings()
    unsafe_env = _unsafe_env_findings()
    blocked = bool(missing or forbidden_paths or claim_secret_findings or unsafe_env)
    return {
        "issue_id": ISSUE_ID,
        "title": TITLE,
        "mode": mode,
        "result": "blocked" if blocked else "dry_run_passed",
        "not_production_infrastructure_certification": True,
        "external_services_contacted": False,
        "network_required": False,
        "credentials_required": False,
        "destructive_operations": False,
        "deployment_artifacts_created": False,
        "cloud_resources_created": False,
        "tls_certificates_or_private_keys_written": False,
        "github_workflows_modified": False,
        "missing_required_paths": missing,
        "changed_files_considered": sorted(changed),
        "forbidden_path_findings": forbidden_paths,
        "claim_or_secret_findings": claim_secret_findings,
        "unsafe_environment_findings": unsafe_env,
        "remaining_blockers": [
            "No real TLS termination, certificate lifecycle, HSTS, or reverse proxy rollout is implemented.",
            "No production container runtime, non-root image policy, read-only filesystem, or orchestration baseline is implemented.",
            "No production process supervisor, restart policy, resource quotas, or graceful shutdown SLO is implemented.",
            "No external metrics, log aggregation, tracing, alerting, pager, or SIEM/SOC integration is implemented.",
            "No production backup automation, restore RTO/RPO evidence, failover, or DR integration is implemented.",
            "Production SaaS, real customer/private grant/institutional data, compliance certification, official SDK/package, and live PostgreSQL production readiness remain NO-GO.",
        ],
    }


def _print_plan() -> int:
    print("[GL-220] Runtime Infrastructure Gate - PLAN mode")
    for step in PLAN_STEPS:
        print(f"[GL-220]   {step}")
    print("[GL-220] No network calls are made.")
    print("[GL-220] No credentials are required.")
    print("[GL-220] No destructive commands are run.")
    print("[GL-220] No deployment artifacts, cloud resources, TLS certificates, or private keys are created.")
    print("[GL-220] This is not production infrastructure certification.")
    return 0


def _print_dry_run(as_json: bool) -> int:
    result = _result("dry_run")
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("[GL-220] Runtime Infrastructure Gate - DRY-RUN mode")
        print("[GL-220] No network calls, credentials, DB connections, deployment creation, or destructive commands.")
        print("[GL-220] This is not production infrastructure certification.")
        if result["missing_required_paths"]:
            print("[GL-220] Missing required paths:")
            for path in result["missing_required_paths"]:
                print(f"[GL-220]   {path}")
        else:
            print("[GL-220] Required paths are present.")
        for key, label in (
            ("forbidden_path_findings", "Forbidden path findings"),
            ("claim_or_secret_findings", "Claim or secret findings"),
            ("unsafe_environment_findings", "Unsafe environment findings"),
        ):
            if result[key]:
                print(f"[GL-220] {label}:")
                for finding in result[key]:
                    if isinstance(finding, dict):
                        print(f"[GL-220]   {finding['env']}: {finding['reason']} ({finding['redacted_value']})")
                    else:
                        print(f"[GL-220]   {finding}")
            else:
                print(f"[GL-220] No {label.lower()}.")
    return 2 if result["result"] == "blocked" else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GL-220 dry-run runtime/infrastructure gate")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="run local-only runtime/infrastructure checks")
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
