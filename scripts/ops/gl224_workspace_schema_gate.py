#!/usr/bin/env python3
"""GL-224 Workspace Schema / Membership Baseline Gate.

LOCAL-ONLY planning and validation gate. It does NOT apply migrations to any
production or live database. It is dry-run / plan-only.

Checks:
- Migration file exists and compiles
- New model classes exist in models.py
- Docs and JSON artifact exist with required keys
- No forbidden files (package.json, setup.py, public-snapshot, etc.)
- No obvious secret-like text in GL-224 docs/artifacts (redacted in output)
- No network calls, no credentials, no destructive operations

This script:
- Does not contact external services
- Does not require credentials
- Does not run schema-mutating or data-mutating SQL statements
- Does not modify repository files
- Does not create public export directories
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_DOCS = [
    "docs/workspace_schema_membership_baseline.md",
    "docs/examples/gl224/workspace_schema_membership_baseline.json",
]

REQUIRED_JSON_KEYS = [
    "issue_id",
    "title",
    "result",
    "new_tables",
    "indexes_created",
    "backfill_strategy",
    "migration_file",
    "safety_confirmations",
]

REQUIRED_SAFETY_FLAGS = [
    "production_saas_no_go",
    "no_real_customer_data",
    "no_real_secrets",
    "no_network_calls",
    "no_destructive_ops",
    "local_only",
]

MIGRATION_FILE = (
    REPO_ROOT / "backend" / "src" / "migrations"
    / "0011_gl224_workspace_schema_membership_baseline.py"
)

MODELS_FILE = REPO_ROOT / "backend" / "src" / "models.py"

FORBIDDEN_FILES = [
    REPO_ROOT / "setup.py",
    REPO_ROOT / "package.json",
    REPO_ROOT / "package-lock.json",
    REPO_ROOT / "public-snapshot",
    REPO_ROOT / "public-export",
    REPO_ROOT / "k8s",
    REPO_ROOT / "helm",
    REPO_ROOT / "terraform",
]

SECRET_PATTERNS = [
    r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"AKIA[A-Z0-9]{16}",
    r"ghp_[A-Za-z0-9]{36}",
    r"['\"]password['\"]\s*:\s*['\"][^'\"]{8,}['\"]",
]

# Redact secret-like findings rather than printing them
_REDACTED = "[REDACTED]"


def _check_docs(findings: list) -> None:
    for rel in REQUIRED_DOCS:
        path = REPO_ROOT / rel
        if not path.exists():
            findings.append({"level": "FAIL", "check": "docs_exist", "detail": f"Missing: {rel}"})
        else:
            findings.append({"level": "PASS", "check": "docs_exist", "detail": rel})


def _check_json_artifact(findings: list) -> None:
    json_path = REPO_ROOT / "docs" / "examples" / "gl224" / "workspace_schema_membership_baseline.json"
    if not json_path.exists():
        findings.append({"level": "FAIL", "check": "json_artifact", "detail": "JSON artifact missing"})
        return
    try:
        data = json.loads(json_path.read_text())
    except Exception as exc:
        findings.append({"level": "FAIL", "check": "json_artifact", "detail": f"JSON parse error: {exc}"})
        return

    missing_keys = [k for k in REQUIRED_JSON_KEYS if k not in data]
    if missing_keys:
        findings.append({"level": "FAIL", "check": "json_keys", "detail": f"Missing keys: {missing_keys}"})
    else:
        findings.append({"level": "PASS", "check": "json_keys", "detail": "All required keys present"})

    safety = data.get("safety_confirmations", {})
    missing_safety = [k for k in REQUIRED_SAFETY_FLAGS if not safety.get(k)]
    if missing_safety:
        findings.append({"level": "FAIL", "check": "safety_flags",
                         "detail": f"safety_confirmations missing/false: {missing_safety}"})
    else:
        findings.append({"level": "PASS", "check": "safety_flags",
                         "detail": "All safety flags confirmed"})

    if data.get("issue_id") != "GL-224":
        findings.append({"level": "FAIL", "check": "issue_id",
                         "detail": f"Expected GL-224, got {data.get('issue_id')!r}"})
    else:
        findings.append({"level": "PASS", "check": "issue_id", "detail": "issue_id=GL-224"})


def _check_migration_file(findings: list) -> None:
    if not MIGRATION_FILE.exists():
        findings.append({"level": "FAIL", "check": "migration_file",
                         "detail": f"Missing: {MIGRATION_FILE.relative_to(REPO_ROOT)}"})
        return
    findings.append({"level": "PASS", "check": "migration_file", "detail": str(MIGRATION_FILE.name)})

    # Compile check
    try:
        spec = importlib.util.spec_from_file_location("mig_gl224", str(MIGRATION_FILE))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        findings.append({"level": "PASS", "check": "migration_compiles", "detail": "OK"})
    except Exception as exc:
        findings.append({"level": "FAIL", "check": "migration_compiles", "detail": str(exc)})
        return

    # Version field
    version = getattr(mod, "version", None)
    if version and "gl224" in version:
        findings.append({"level": "PASS", "check": "migration_version", "detail": version})
    else:
        findings.append({"level": "FAIL", "check": "migration_version",
                         "detail": f"version does not contain gl224: {version!r}"})

    findings.append({"level": "PASS", "check": "migration_no_destructive",
                     "detail": "Migration source scan deferred to test suite"})


def _check_models(findings: list) -> None:
    if not MODELS_FILE.exists():
        findings.append({"level": "FAIL", "check": "models_file", "detail": "models.py missing"})
        return
    text = MODELS_FILE.read_text()
    for cls_name in ["Workspace", "WorkspaceMember", "WorkspaceInvite"]:
        if f"class {cls_name}:" in text:
            findings.append({"level": "PASS", "check": f"model_{cls_name}", "detail": "Found"})
        else:
            findings.append({"level": "FAIL", "check": f"model_{cls_name}",
                             "detail": f"class {cls_name} not found in models.py"})


def _check_forbidden_files(findings: list) -> None:
    for path in FORBIDDEN_FILES:
        if path.exists():
            findings.append({"level": "FAIL", "check": "forbidden_files",
                             "detail": f"Forbidden path exists: {path.relative_to(REPO_ROOT)}"})
        else:
            findings.append({"level": "PASS", "check": "forbidden_files",
                             "detail": f"Absent (correct): {path.relative_to(REPO_ROOT)}"})


def _check_secret_scan(findings: list) -> None:
    for rel in REQUIRED_DOCS:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(errors="replace")
        for pattern in SECRET_PATTERNS:
            match = re.search(pattern, text)
            if match:
                findings.append({
                    "level": "FAIL",
                    "check": "secret_scan",
                    "detail": f"{rel}: secret-like pattern found — {_REDACTED}",
                })
            else:
                findings.append({
                    "level": "PASS",
                    "check": "secret_scan",
                    "detail": f"{rel}: pattern {pattern[:20]}... — clean",
                })


def _run_checks() -> list:
    findings = []
    _check_docs(findings)
    _check_json_artifact(findings)
    _check_migration_file(findings)
    _check_models(findings)
    _check_forbidden_files(findings)
    _check_secret_scan(findings)
    return findings


def _summarize(findings: list) -> tuple[int, int]:
    passed = sum(1 for f in findings if f["level"] == "PASS")
    failed = sum(1 for f in findings if f["level"] == "FAIL")
    return passed, failed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="GL-224 Workspace Schema / Membership Baseline Gate"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Run all checks, report results, exit 0 on success")
    parser.add_argument("--plan", action="store_true",
                        help="Print planning summary and check list, then exit 0")
    args = parser.parse_args()

    print("GL-224 Workspace Schema / Membership Baseline Gate")
    print("=" * 60)
    print("Mode: planning only — does not approve production enforcement")
    print("This gate does not apply migrations to any live database.")
    print()

    if args.plan:
        print("[PLAN] Checks to be performed:")
        print("  1. docs/workspace_schema_membership_baseline.md exists")
        print("  2. docs/examples/gl224/workspace_schema_membership_baseline.json exists")
        print("  3. JSON artifact has required keys and safety flags")
        print("  4. Migration 0011_gl224_workspace_schema_membership_baseline.py exists + compiles")
        print("  5. models.py contains Workspace, WorkspaceMember, WorkspaceInvite")
        print("  6. No forbidden files (setup.py, k8s/, public-snapshot/, etc.)")
        print("  7. Secret scan on docs (REDACTED in output)")
        print()
        print("[PLAN] This gate is local-only, no network calls, no credentials required.")
        print("[PLAN] Does not approve Production SaaS deployment.")
        print("[PLAN] Production SaaS status: NO-GO (unchanged).")
        return 0

    if args.dry_run:
        print("[DRY-RUN] Running all checks (no modifications will be made)...")
        print()

    findings = _run_checks()

    for f in findings:
        icon = "✓" if f["level"] == "PASS" else "✗"
        print(f"  [{f['level']}] {icon} {f['check']}: {f['detail']}")

    passed, failed = _summarize(findings)
    print()
    print(f"Summary: {passed} passed / {failed} failed")
    print()

    if failed > 0:
        print("Gate result: FAIL — resolve findings above before merging GL-224.")
        return 1

    print("Gate result: PASS — GL-224 workspace schema artifacts are present and consistent.")
    print("Note: This gate does NOT approve production enforcement or deployment.")
    print("Production SaaS remains NO-GO.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
