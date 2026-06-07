#!/usr/bin/env python3
"""GL-222 Controlled External Review Handoff Gate — local-only, dry-run/plan only.

This script is NOT approval to publish. It is NOT a full security audit.
It is a local-only pre-handoff readiness check only.
"""
import argparse
import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REQUIRED_DOCS = [
    "docs/controlled_external_review_handoff_pack.md",
    "docs/examples/gl222/controlled_external_review_handoff_pack.json",
]

REQUIRED_JSON_KEYS = [
    "issue_id", "title", "result", "decision", "decision_rationale",
    "input_sources_reviewed", "current_controlled_external_review_posture",
    "handoff_package_purpose", "reviewer_scope", "excluded_scope",
    "eligible_review_materials", "prohibited_materials",
    "allowed_claims", "prohibited_claims",
    "data_boundary_synthetic_demo_only",
    "real_customer_private_grant_institutional_data_boundary",
    "production_saas_boundary", "public_snapshot_export_publish_boundary",
    "official_sdk_package_boundary", "compliance_certification_boundary",
    "live_postgres_production_readiness_boundary",
    "identity_access_status_after_gl219",
    "runtime_infrastructure_status_after_gl220",
    "workspace_status_after_gl221",
    "public_export_safety_status_after_gl218",
    "known_limitations", "known_full_suite_false_positive_classes",
    "reviewer_safe_verification_commands",
    "security_sensitive_reporting_instructions",
    "optional_handoff_gate_script_summary",
    "production_readiness_impact", "controlled_preview_impact",
    "remaining_blockers", "risk_register", "findings",
    "safety_confirmations", "recommended_next_issues",
]

FORBIDDEN_PATH_PATTERNS = [
    r"public[_-]?(snapshot|export)[_-]?worktree",
    r"public[_-]?export[_-]?dir",
    r"setup\.py$",
    r"sdk[_-]?pyproject\.toml$",
    r"(?<![_-])package\.json$",
    r"package-lock\.json$",
    r"kubernetes[/\\]",
    r"terraform[/\\]",
    r"helm[/\\]",
    r"\.github[/\\]workflows[/\\].*gl-?222",
]

SECRET_PATTERNS = [
    (r"(?i)(password|passwd|pwd)\s*=\s*['\"][^'\"]{4,}['\"]", "password-like assignment"),
    (r"(?i)secret\s*=\s*['\"][^'\"]{8,}['\"]", "secret-like assignment"),
    (r"-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----", "PEM private key"),
    (r"(?i)Bearer\s+[A-Za-z0-9\-._~+/]{20,}", "Bearer token"),
    (r"(?i)(api[_-]?key|apikey)\s*=\s*['\"][^'\"]{8,}['\"]", "API key assignment"),
    (r"postgres(?:ql)?://[^@\s]+:[^@\s]+@[^\s]+", "PostgreSQL DSN with credentials"),
    (r"(?i)aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{16,}", "AWS secret"),
]

GL222_DOCS = [
    "docs/controlled_external_review_handoff_pack.md",
    "docs/examples/gl222/controlled_external_review_handoff_pack.json",
    "scripts/ops/gl222_controlled_review_handoff_gate.py",
]


def redact(value: str) -> str:
    return value[:4] + "***REDACTED***" if len(value) > 4 else "***REDACTED***"


def check_required_docs(findings: list, warnings: list) -> None:
    for rel_path in REQUIRED_DOCS:
        full_path = os.path.join(REPO_ROOT, rel_path)
        if os.path.isfile(full_path):
            findings.append(f"  [PASS] Required doc exists: {rel_path}")
        else:
            findings.append(f"  [FAIL] Required doc missing: {rel_path}")
            warnings.append(f"Missing required doc: {rel_path}")


def check_json_artifact(findings: list, warnings: list) -> None:
    rel_path = "docs/examples/gl222/controlled_external_review_handoff_pack.json"
    full_path = os.path.join(REPO_ROOT, rel_path)
    if not os.path.isfile(full_path):
        findings.append(f"  [SKIP] JSON artifact missing; skipping key checks")
        return
    try:
        with open(full_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        findings.append(f"  [FAIL] JSON artifact is invalid: {e}")
        warnings.append(f"Invalid JSON: {rel_path}")
        return
    findings.append(f"  [PASS] JSON artifact is valid JSON")

    issue_id = data.get("issue_id", "")
    if issue_id == "GL-222":
        findings.append(f"  [PASS] issue_id is GL-222")
    else:
        findings.append(f"  [FAIL] issue_id is {issue_id!r}, expected 'GL-222'")
        warnings.append(f"issue_id mismatch")

    missing_keys = [k for k in REQUIRED_JSON_KEYS if k not in data]
    if missing_keys:
        for k in missing_keys:
            findings.append(f"  [FAIL] Missing JSON key: {k}")
            warnings.append(f"Missing JSON key: {k}")
    else:
        findings.append(f"  [PASS] All {len(REQUIRED_JSON_KEYS)} required JSON keys present")

    safety = data.get("safety_confirmations", {})
    for key, label in [
        ("production_saas_no_go", "production SaaS NO-GO"),
        ("real_customer_private_grant_institutional_data_no_go", "real-data NO-GO"),
        ("official_sdk_package_no_go", "official SDK/package NO-GO"),
        ("compliance_certification_no_go", "compliance certification NO-GO"),
        ("live_postgresql_production_readiness_no_go", "live PostgreSQL NO-GO"),
        ("gl222_does_not_create_public_export", "no public export"),
        ("gl222_is_internal_handoff_pack_not_reviewer_outreach", "not reviewer outreach"),
        ("no_exploit_details", "no exploit details"),
        ("no_real_secrets", "no real secrets"),
        ("no_real_customer_private_data", "no real customer/private data"),
    ]:
        val = safety.get(key)
        if val is True:
            findings.append(f"  [PASS] safety_confirmations.{key} = true ({label})")
        else:
            findings.append(f"  [FAIL] safety_confirmations.{key} = {val!r} (expected true for {label})")
            warnings.append(f"safety_confirmations.{key} must be true")


def check_forbidden_paths(findings: list, warnings: list) -> None:
    compiled = [re.compile(p) for p in FORBIDDEN_PATH_PATTERNS]
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__", "venv", ".venv", "node_modules"}]
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, REPO_ROOT)
            for pattern in compiled:
                if pattern.search(rel):
                    findings.append(f"  [FAIL] Forbidden path pattern matched: {rel}")
                    warnings.append(f"Forbidden path: {rel}")
                    break


def check_secret_scan(findings: list, warnings: list) -> None:
    compiled = [(re.compile(p), label) for p, label in SECRET_PATTERNS]
    hit_count = 0
    for rel_path in GL222_DOCS:
        full_path = os.path.join(REPO_ROOT, rel_path)
        if not os.path.isfile(full_path):
            continue
        try:
            with open(full_path, errors="replace") as f:
                content = f.read()
        except OSError:
            continue
        for line_no, line in enumerate(content.splitlines(), 1):
            for pattern, label in compiled:
                m = pattern.search(line)
                if m:
                    hit_count += 1
                    snippet = redact(m.group(0))
                    findings.append(
                        f"  [WARN] Possible {label} in {rel_path}:{line_no}: {snippet}"
                    )
                    warnings.append(f"Secret-like pattern in {rel_path}:{line_no}: {label}")
    if hit_count == 0:
        findings.append(f"  [PASS] No obvious secret-like patterns found in GL-222 docs/artifacts")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="GL-222 Controlled External Review Handoff Gate (local-only, dry-run/plan only)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Run in dry-run mode (no changes)")
    parser.add_argument("--plan", action="store_true", help="Run in plan mode (no changes)")
    args = parser.parse_args()

    print("=" * 72)
    print("GL-222 Controlled External Review Handoff Gate")
    print("LOCAL-ONLY — DRY-RUN / PLAN MODE")
    print()
    print("NOTICE: This script is NOT approval to publish.")
    print("NOTICE: This script is NOT a full security audit.")
    print("NOTICE: It is a local-only pre-handoff readiness check only.")
    print("=" * 72)
    print()

    if args.dry_run:
        print("[MODE] dry-run: checks will run, no files will be modified")
    if args.plan:
        print("[MODE] plan: checks will run, no files will be modified")
    print()

    findings: list = []
    warnings: list = []

    print("--- 1. Required Documents ---")
    check_required_docs(findings, warnings)
    for f in findings:
        print(f)
    findings.clear()
    print()

    print("--- 2. JSON Artifact Validation ---")
    check_json_artifact(findings, warnings)
    for f in findings:
        print(f)
    findings.clear()
    print()

    print("--- 3. Forbidden Path Check ---")
    check_forbidden_paths(findings, warnings)
    if not any("[FAIL]" in f for f in findings):
        findings.append("  [PASS] No forbidden path patterns found in repository")
    for f in findings:
        print(f)
    findings.clear()
    print()

    print("--- 4. Secret Scan (GL-222 docs/artifacts only) ---")
    check_secret_scan(findings, warnings)
    for f in findings:
        print(f)
    findings.clear()
    print()

    print("=" * 72)
    if warnings:
        print(f"RESULT: {len(warnings)} issue(s) found")
        for w in warnings:
            print(f"  - {w}")
        print()
        print("NOTICE: This script is NOT approval to publish.")
        print("NOTICE: This script is NOT a full security audit.")
        print("NOTICE: Resolve the above issues before initiating any handoff.")
        return 1
    else:
        print("RESULT: All checks passed")
        print()
        print("NOTICE: This script is NOT approval to publish.")
        print("NOTICE: This script is NOT a full security audit.")
        print("NOTICE: A separate explicit gate issue is required before any")
        print("        public export, publish, or reviewer outreach.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
