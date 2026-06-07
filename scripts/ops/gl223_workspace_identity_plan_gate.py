#!/usr/bin/env python3
"""GL-223 Workspace Identity Plan Gate.

This script is a LOCAL-ONLY planning gate. It does NOT approve production
workspace enforcement implementation. It is dry-run / plan-only.

It verifies:
- GL-223 docs/artifacts exist
- No forbidden implementation/deployment/package/public-export paths introduced
- No production-readiness overclaims in GL-223 docs/artifacts
- Obvious secret-like text in GL-223 docs/artifacts (redacted in output)

This script:
- Does not contact external services
- Does not require credentials
- Does not run destructive commands
- Does not modify repository files
- Does not create migrations, DB schema, or public export directories
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_DOCS = [
    "docs/workspace_identity_membership_ownership_implementation_plan.md",
    "docs/examples/gl223/workspace_identity_membership_ownership_implementation_plan.json",
]

REQUIRED_JSON_KEYS = [
    "issue_id",
    "title",
    "result",
    "decision",
    "decision_rationale",
    "input_sources_reviewed",
    "current_tenant_workspace_state_summary",
    "current_workspace_trust_gaps",
    "workspace_identity_model",
    "membership_model",
    "ownership_model",
    "role_scope_model",
    "workspace_lifecycle_model",
    "admin_operator_ownership_boundary",
    "server_derived_workspace_context_model",
    "unsafe_workspace_override_prevention_model",
    "cross_workspace_lookup_denial_model",
    "cross_workspace_mutation_denial_model",
    "audit_evidence_provenance_compliance_propagation_model",
    "database_schema_plan",
    "migration_backfill_plan",
    "api_server_plan",
    "openapi_impact_plan",
    "testing_strategy",
    "rollout_strategy",
    "rollback_strategy",
    "demo_synthetic_compatibility",
    "production_readiness_impact",
    "controlled_preview_impact",
    "real_data_impact",
    "remaining_blockers",
    "proposed_implementation_issue_breakdown",
    "risk_register",
    "findings",
    "safety_confirmations",
    "recommended_next_issues",
]

# Paths that must not exist (newly created by GL-223 or any branch)
FORBIDDEN_NEW_PATHS = [
    "setup.py",
    "package.json",
    "package-lock.json",
    "public-snapshot",
    "public-export",
    "deploy",
    "k8s",
    "helm",
    "terraform",
]

# Patterns that must not appear in new/changed files on this branch
FORBIDDEN_DIFF_PATTERNS = [
    "backend/src/migrations/",
    ".github/workflows/",
    "scripts/publish",
    "scripts/snapshot",
]

FORBIDDEN_CLAIM_PATTERNS = [
    r"production[- ]saas[- ](ready|approved|enabled|go)",
    r"real[- ]customer[- ]data[- ](ready|approved|enabled|go)",
    r"compliance[- ](certified|ready|approved)",
    r"gdpr[- ](certified|compliant|ready)",
    r"soc2[- ](certified|compliant|ready)",
    r"iso[- ](certified|compliant|ready)",
    r"enterprise[- ](ready|approved)",
    r"live[- ]postgresql[- ]production[- ](ready|approved|go)",
    r"official[- ]sdk[- ](published|released|approved|ready)",
]

SECRET_LIKE_PATTERNS = [
    r"(password|passwd|secret|token|key|api_key|apikey|private_key)\s*[=:]\s*['\"]?\S{8,}['\"]?",
    r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"(aws_access_key_id|aws_secret_access_key)\s*[=:]\s*\S+",
    r"(AKIA|ASIA)[A-Z0-9]{16}",
    r"ghp_[A-Za-z0-9]{36}",
]

GL223_DOC_PATHS = [
    "docs/workspace_identity_membership_ownership_implementation_plan.md",
    "docs/examples/gl223/workspace_identity_membership_ownership_implementation_plan.json",
    "scripts/ops/gl223_workspace_identity_plan_gate.py",
    "backend/tests/test_gl223_workspace_identity_membership_ownership_implementation_plan.py",
]


def check_required_docs(verbose: bool) -> list[str]:
    errors = []
    for rel_path in REQUIRED_DOCS:
        full = REPO_ROOT / rel_path
        if not full.exists():
            errors.append(f"MISSING required doc: {rel_path}")
        elif verbose:
            print(f"  OK   {rel_path}")
    return errors


def check_forbidden_paths(verbose: bool) -> list[str]:
    errors = []
    # Check paths that must not exist at all
    for pattern in FORBIDDEN_NEW_PATHS:
        full = REPO_ROOT / pattern
        if full.exists():
            errors.append(f"FORBIDDEN path exists: {pattern}")
        elif verbose:
            print(f"  OK   (absent) {pattern}")
    # Check that branch diff doesn't introduce forbidden path types
    try:
        import subprocess as _sp
        result = _sp.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10,
        )
        changed = [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except Exception:
        changed = []
    for path in changed:
        for pattern in FORBIDDEN_DIFF_PATTERNS:
            if path.startswith(pattern) or pattern in path:
                errors.append(f"FORBIDDEN change introduced on branch: {path} (matches {pattern})")
    if not errors and verbose:
        print(f"  OK   no forbidden paths (checked {len(changed)} changed files)")
    return errors


def check_json_artifact() -> list[str]:
    errors = []
    json_path = REPO_ROOT / "docs/examples/gl223/workspace_identity_membership_ownership_implementation_plan.json"
    if not json_path.exists():
        errors.append("MISSING JSON artifact")
        return errors
    try:
        with open(json_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        errors.append(f"JSON artifact is invalid JSON: {exc}")
        return errors
    if data.get("issue_id") != "GL-223":
        errors.append(f"JSON artifact issue_id is not GL-223: {data.get('issue_id')!r}")
    for key in REQUIRED_JSON_KEYS:
        if key not in data:
            errors.append(f"JSON artifact missing key: {key}")
    safety = data.get("safety_confirmations", {})
    if not isinstance(safety, dict):
        errors.append("safety_confirmations is not a dict")
    else:
        required_safety = [
            "is_planning_only",
            "no_migrations_added",
            "no_real_data_enabled",
            "production_saas_no_go",
            "real_customer_data_no_go",
            "private_grant_institutional_data_no_go",
            "official_sdk_package_no_go",
            "compliance_certification_no_go",
            "live_postgresql_production_no_go",
            "no_exploit_details",
            "no_real_secrets",
            "no_real_customer_private_data",
            "website_design_import_files_excluded",
        ]
        for key in required_safety:
            if not safety.get(key):
                errors.append(f"safety_confirmation not set to true: {key}")
    return errors


def scan_for_overclaims(verbose: bool) -> list[str]:
    warnings = []
    for rel_path in GL223_DOC_PATHS:
        full = REPO_ROOT / rel_path
        if not full.exists():
            continue
        try:
            text = full.read_text(errors="replace").lower()
        except OSError:
            continue
        for pattern in FORBIDDEN_CLAIM_PATTERNS:
            if re.search(pattern, text):
                warnings.append(f"POTENTIAL OVERCLAIM in {rel_path}: pattern '{pattern}'")
    if verbose and not warnings:
        print("  OK   no overclaims detected")
    return warnings


def scan_for_secrets(verbose: bool) -> list[str]:
    findings = []
    for rel_path in GL223_DOC_PATHS:
        full = REPO_ROOT / rel_path
        if not full.exists():
            continue
        try:
            lines = full.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            for pattern in SECRET_LIKE_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    redacted = re.sub(r"([=:]\s*['\"]?)\S+(['\"]?)", r"\1[REDACTED]\2", line.strip())
                    findings.append(f"SECRET-LIKE in {rel_path}:{lineno}: {redacted}")
    if verbose and not findings:
        print("  OK   no secret-like values detected in GL-223 artifacts")
    return findings


def check_no_backend_src_changes() -> list[str]:
    errors = []
    try:
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10,
        )
        changed = [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except Exception:
        return []
    for path in changed:
        if path.startswith("backend/src/") and not path.startswith("backend/src/migrations/"):
            errors.append(f"FORBIDDEN backend/src change: {path}")
        if path.startswith("backend/src/migrations/"):
            errors.append(f"FORBIDDEN migration change: {path}")
        if path.endswith(".github/workflows/") or "/.github/workflows/" in path:
            errors.append(f"FORBIDDEN workflow change: {path}")
    return errors


def run_gate(verbose: bool, dry_run: bool, plan_only: bool) -> int:
    print()
    print("=" * 70)
    print("GL-223 Workspace Identity Plan Gate")
    print("=" * 70)
    print()
    print("IMPORTANT: This is a LOCAL-ONLY planning gate.")
    print("This gate DOES NOT approve production workspace enforcement.")
    print("This gate DOES NOT approve any change to the current production")
    print("readiness posture.")
    print()
    if dry_run or plan_only:
        print("[MODE] dry-run / plan-only — no files will be modified")
        print()

    all_errors: list[str] = []
    all_warnings: list[str] = []

    print("[1/6] Checking required GL-223 docs/artifacts...")
    errors = check_required_docs(verbose)
    all_errors.extend(errors)
    if errors:
        for e in errors:
            print(f"  FAIL {e}")
    else:
        print("  PASS")

    print()
    print("[2/6] Checking forbidden paths are absent...")
    errors = check_forbidden_paths(verbose)
    all_errors.extend(errors)
    if errors:
        for e in errors:
            print(f"  FAIL {e}")
    else:
        print("  PASS")

    print()
    print("[3/6] Validating JSON artifact structure...")
    errors = check_json_artifact()
    all_errors.extend(errors)
    if errors:
        for e in errors:
            print(f"  FAIL {e}")
    else:
        print("  PASS")

    print()
    print("[4/6] Scanning for production-readiness overclaims...")
    warnings = scan_for_overclaims(verbose)
    all_warnings.extend(warnings)
    if warnings:
        for w in warnings:
            print(f"  WARN {w}")
    else:
        print("  PASS")

    print()
    print("[5/6] Scanning GL-223 artifacts for secret-like values...")
    warnings = scan_for_secrets(verbose)
    all_warnings.extend(warnings)
    if warnings:
        for w in warnings:
            print(f"  WARN {w}")
    else:
        print("  PASS")

    print()
    print("[6/6] Checking no backend/src or migration changes on branch...")
    errors = check_no_backend_src_changes()
    all_errors.extend(errors)
    if errors:
        for e in errors:
            print(f"  FAIL {e}")
    else:
        print("  PASS")

    print()
    print("=" * 70)
    if all_errors:
        print(f"RESULT: FAIL — {len(all_errors)} error(s), {len(all_warnings)} warning(s)")
        print()
        print("Errors:")
        for e in all_errors:
            print(f"  - {e}")
        if all_warnings:
            print("Warnings:")
            for w in all_warnings:
                print(f"  - {w}")
        print()
        print("This gate has FAILED. GL-223 artifacts require correction.")
        print("This gate does NOT approve production workspace enforcement.")
        return 1
    else:
        if all_warnings:
            print(f"RESULT: PASS WITH WARNINGS — 0 errors, {len(all_warnings)} warning(s)")
            print()
            print("Warnings:")
            for w in all_warnings:
                print(f"  - {w}")
        else:
            print("RESULT: PASS — 0 errors, 0 warnings")
        print()
        print("GL-223 planning artifacts are present and internally consistent.")
        print()
        print("PLANNING POSTURE CONFIRMED:")
        print("  Developer Preview: GO / CONTINUE")
        print("  Controlled External Technical Review: GO with strict boundaries")
        print("  Synthetic/Demo Controlled Pilot: CONDITIONAL")
        print("  Real Customer Data: NO-GO")
        print("  Private Grant / Institutional Data: NO-GO")
        print("  Production SaaS: NO-GO")
        print("  Official SDK/Package: NO-GO")
        print("  Compliance Certification: NO-GO")
        print("  Live PostgreSQL Production Readiness: NO-GO")
        print()
        print("This gate DOES NOT approve production workspace enforcement.")
        print("Implementation requires GL-224 through GL-231 and a subsequent")
        print("production go/no-go gate (GL-231).")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="GL-223 Workspace Identity Plan Gate — local-only, dry-run/plan-only."
    )
    parser.add_argument("--dry-run", action="store_true", help="Dry-run mode (no files modified)")
    parser.add_argument("--plan", action="store_true", help="Plan-only mode (same as --dry-run)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()
    return run_gate(verbose=args.verbose, dry_run=args.dry_run, plan_only=args.plan)


if __name__ == "__main__":
    sys.exit(main())
