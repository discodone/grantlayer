#!/usr/bin/env python3
"""GL-221 workspace and final Go/No-Go gate.

Local-only dry-run/plan helper. It checks required artifacts, branch scope, and
conservative claim boundaries. It does not contact services, require
credentials, create public exports, publish packages, deploy infrastructure, or
certify production readiness.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path


ISSUE_ID = "GL-221"
TITLE = "Workspace Enforcement & Final Go/No-Go v6"

REQUIRED_PATHS = [
    "docs/workspace_enforcement_final_go_no_go_v6.md",
    "docs/examples/gl221/workspace_enforcement_final_go_no_go_v6.json",
    "docs/production_go_no_go_v5.md",
    "docs/examples/gl217/production_go_no_go_v5.json",
    "docs/production_runtime_infrastructure_hardening_pack.md",
    "docs/examples/gl220/production_runtime_infrastructure_hardening_pack.json",
    "docs/production_identity_access_hardening_pack.md",
    "docs/examples/gl219/production_identity_access_hardening_pack.json",
    "docs/public_external_review_export_safety_pack.md",
    "docs/examples/gl218/public_external_review_export_safety_pack.json",
    "docs/tenant_workspace_production_guarantee.md",
    "docs/examples/gl215/tenant_workspace_production_guarantee.json",
    "backend/src/server.py",
    "backend/src/grants.py",
    "backend/src/grant_requests.py",
    "backend/src/audit_log.py",
    "scripts/ops/gl220_runtime_infrastructure_gate.py",
]

ALLOWED_CHANGED_FILES = {
    "backend/tests/test_gl221_workspace_enforcement_final_go_no_go_v6.py",
    "docs/workspace_enforcement_final_go_no_go_v6.md",
    "docs/examples/gl221/workspace_enforcement_final_go_no_go_v6.json",
    "scripts/ops/gl221_workspace_go_no_go_gate.py",
}

FORBIDDEN_PREFIXES = (
    ".github/workflows/",
    "website/",
    "frontend/",
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
FORBIDDEN_EXACT = {
    "setup.py",
    "package.json",
    "package-lock.json",
    "pyproject.toml",
    "sdk/pyproject.toml",
}
FORBIDDEN_SUFFIXES = (".tf", ".tfvars", ".pem", ".key", ".crt", ".cer", ".p12", ".pfx")

FORBIDDEN_TEXT = [
    "Production SaaS " + "is ready",
    "production-ready " + "SaaS",
    "ready for real " + "customer data",
    "ready for private " + "grant data",
    "ready for " + "institutional data",
    "official SDK " + "is available",
    "compliance " + "certified",
    "GD" + "PR ready",
    "SO" + "C2 ready",
    "IS" + "O ready",
    "live PostgreSQL production " + "ready",
    "BEGIN " + "PRIVATE KEY",
    "Bearer " + "eyJ",
]

SECRET_PATTERN = re.compile(
    r"(postgres(?:ql)?://[^/\s:]+:[^@\s]+@|BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY|Bearer\s+eyJ|password\s*=)",
    re.IGNORECASE,
)

PLAN_STEPS = [
    "step_01: Verify GL-221 docs, JSON artifact, test, and local gate exist",
    "step_02: Verify prior GL-214 through GL-220 evidence inputs exist",
    "step_03: Check branch scope for forbidden public, package, workflow, deployment, migration, TLS, and website-design changes",
    "step_04: Check conservative workspace and final Go/No-Go claims",
    "step_05: Report remaining blockers without production readiness certification",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


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


def _path_findings(changed: set[str]) -> list[str]:
    findings: list[str] = []
    for path in sorted(changed):
        if path not in ALLOWED_CHANGED_FILES:
            findings.append(f"unexpected_changed_file:{path}")
        if path in FORBIDDEN_EXACT or Path(path).name in FORBIDDEN_EXACT:
            findings.append(f"forbidden_file:{path}")
        if any(path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            findings.append(f"forbidden_path:{path}")
        if path.lower().endswith(FORBIDDEN_SUFFIXES):
            findings.append(f"forbidden_sensitive_or_deployment_suffix:{path}")
    return findings


def _claim_findings() -> list[str]:
    root = _repo_root()
    content = ""
    for rel in (
        "docs/workspace_enforcement_final_go_no_go_v6.md",
        "docs/examples/gl221/workspace_enforcement_final_go_no_go_v6.json",
    ):
        path = root / rel
        if path.exists():
            content += path.read_text(encoding="utf-8") + "\n"
    findings = [f"forbidden_claim:{phrase}" for phrase in FORBIDDEN_TEXT if phrase in content]
    if SECRET_PATTERN.search(content):
        findings.append("secret_like_content_detected")
    return findings


def _result(mode: str) -> dict[str, object]:
    root = _repo_root()
    paths = [{"path": path, "exists": (root / path).exists()} for path in REQUIRED_PATHS]
    missing = [item["path"] for item in paths if not item["exists"]]
    changed = _changed_files()
    forbidden = _path_findings(changed)
    claims = _claim_findings()
    blocked = bool(missing or forbidden or claims)
    return {
        "issue_id": ISSUE_ID,
        "title": TITLE,
        "mode": mode,
        "result": "blocked" if blocked else "dry_run_passed",
        "not_production_readiness_certification": True,
        "external_services_contacted": False,
        "network_required": False,
        "credentials_required": False,
        "destructive_operations": False,
        "public_artifacts_created": False,
        "packages_published": False,
        "deployment_artifacts_created": False,
        "missing_required_paths": missing,
        "changed_files": sorted(changed),
        "forbidden_path_findings": forbidden,
        "claim_findings": claims,
        "remaining_blockers": [
            "workspace enforcement remains not production-complete",
            "real customer/private grant/institutional data remains NO-GO",
            "Production SaaS remains NO-GO",
            "official SDK/package remains NO-GO",
            "live PostgreSQL production readiness remains NO-GO",
        ],
    }


def _print_plan() -> int:
    print("[GL-221] Workspace Go/No-Go Gate - PLAN mode")
    for step in PLAN_STEPS:
        print(f"[GL-221]   {step}")
    print("[GL-221] No network calls are made.")
    print("[GL-221] No credentials, public exports, package publishes, or deployment actions are performed.")
    print("[GL-221] This is not production readiness certification.")
    return 0


def _print_dry_run(as_json: bool) -> int:
    result = _result("dry_run")
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("[GL-221] Workspace Go/No-Go Gate - DRY-RUN mode")
        print("[GL-221] Local-only checks complete.")
        print("[GL-221] This is not production readiness certification.")
        for key in ("missing_required_paths", "forbidden_path_findings", "claim_findings"):
            values = result[key]
            if values:
                print(f"[GL-221] {key}:")
                for value in values:
                    print(f"[GL-221]   {value}")
    return 2 if result["result"] == "blocked" else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GL-221 dry-run workspace/final go-no-go gate")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="run local-only checks")
    mode.add_argument("--plan", action="store_true", help="print plan steps")
    parser.add_argument("--json", action="store_true", help="emit JSON for --dry-run")
    args = parser.parse_args(argv)

    if args.json and not args.dry_run:
        parser.error("--json is only valid with --dry-run")
    if args.plan:
        return _print_plan()
    return _print_dry_run(args.json)


if __name__ == "__main__":
    raise SystemExit(main())
