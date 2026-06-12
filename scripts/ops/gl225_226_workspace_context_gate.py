#!/usr/bin/env python3
"""GL-225/226 Workspace Context Resolver + Authorization Enforcement Gate.

LOCAL-ONLY planning and validation gate. It does NOT apply migrations,
call any external services, or modify any repository files.

Checks:
- auth.py contains resolve_workspace_context and check_workspace_resource_access
- Test file exists and compiles
- Docs and JSON artifact exist with required keys
- No forbidden files (package.json, setup.py, k8s, helm, terraform, etc.)
- No obvious secret-like text in GL-225/226 docs/artifacts
- No GL-225/226 migration files (this GL does not introduce a migration)
- No network calls, no credentials, no destructive operations

Usage:
    python3 scripts/ops/gl225_226_workspace_context_gate.py --dry-run
    python3 scripts/ops/gl225_226_workspace_context_gate.py --plan
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_DOCS = [
    "docs/workspace_context_resolver_authorization.md",
    "docs/examples/gl225_226/workspace_context_resolver_authorization.json",
]

REQUIRED_JSON_KEYS = [
    "issue_id",
    "title",
    "result",
    "workspace_context_resolver",
    "authorization_enforcement",
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

AUTH_FILE = REPO_ROOT / "backend" / "src" / "auth" / "auth.py"
TEST_FILE = REPO_ROOT / "backend" / "tests" / "test_gl225_226_workspace_context_resolver_authorization.py"

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
    r"(?i)password\s*=\s*['\"][^'\"]{8,}",
]

REQUIRED_FUNCTIONS = [
    "resolve_workspace_context",
    "check_workspace_resource_access",
]


def _check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def check_auth_functions(errors: list[str]) -> None:
    """Verify required functions exist in auth.py."""
    if not AUTH_FILE.exists():
        errors.append(f"MISSING: {AUTH_FILE}")
        return
    content = AUTH_FILE.read_text()
    for fn in REQUIRED_FUNCTIONS:
        _check(
            f"def {fn}" in content,
            f"MISSING FUNCTION: {fn} not found in auth.py",
            errors,
        )


def check_test_file(errors: list[str]) -> None:
    """Verify test file exists and compiles."""
    if not TEST_FILE.exists():
        errors.append(f"MISSING: {TEST_FILE}")
        return
    import py_compile
    try:
        py_compile.compile(str(TEST_FILE), doraise=True)
    except Exception as e:
        errors.append(f"SYNTAX ERROR in test file: {e}")


def check_docs(errors: list[str]) -> None:
    """Verify documentation files exist with required keys."""
    for rel in REQUIRED_DOCS:
        path = REPO_ROOT / rel
        _check(path.exists(), f"MISSING DOC: {rel}", errors)

    json_path = REPO_ROOT / "docs" / "examples" / "gl225_226" / "workspace_context_resolver_authorization.json"
    if not json_path.exists():
        return
    try:
        with open(json_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"INVALID JSON: {e}")
        return

    for key in REQUIRED_JSON_KEYS:
        _check(key in data, f"JSON MISSING KEY: {key}", errors)

    sc = data.get("safety_confirmations", {})
    for flag in REQUIRED_SAFETY_FLAGS:
        _check(
            sc.get(flag) is True,
            f"SAFETY FLAG NOT SET: safety_confirmations.{flag} must be true",
            errors,
        )

    _check(
        "GL-225" in data.get("issue_id", ""),
        "JSON: issue_id must reference GL-225",
        errors,
    )


def check_forbidden_files(errors: list[str]) -> None:
    for path in FORBIDDEN_FILES:
        _check(not path.exists(), f"FORBIDDEN FILE PRESENT: {path}", errors)


def check_no_secrets(errors: list[str]) -> None:
    """Scan GL-225/226 docs/artifacts for secret-like patterns."""
    scan_targets = [
        REPO_ROOT / "docs" / "workspace_context_resolver_authorization.md",
        REPO_ROOT / "docs" / "examples" / "gl225_226" / "workspace_context_resolver_authorization.json",
    ]
    for path in scan_targets:
        if not path.exists():
            continue
        content = path.read_text()
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, content):
                errors.append(f"SECRET PATTERN FOUND in {path.name}: pattern={pattern[:40]}...")


def check_no_gl225_migration(errors: list[str]) -> None:
    """Ensure no GL-225/226 migration file was added (not required for this GL)."""
    migrations_dir = REPO_ROOT / "backend" / "src" / "migrations"
    if not migrations_dir.exists():
        return
    for f in migrations_dir.iterdir():
        name = f.name.lower()
        if "gl225" in name or "gl226" in name:
            errors.append(f"UNEXPECTED MIGRATION FILE: {f.name} (GL-225/226 does not require a migration)")


def run_checks() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    infos: list[str] = []

    check_auth_functions(errors)
    infos.append(f"auth.py: {AUTH_FILE}")

    check_test_file(errors)
    infos.append(f"test file: {TEST_FILE}")

    check_docs(errors)
    infos.append("docs and JSON artifact checked")

    check_forbidden_files(errors)
    infos.append("forbidden files checked")

    check_no_secrets(errors)
    infos.append("secret pattern scan done")

    check_no_gl225_migration(errors)
    infos.append("migration file check done")

    return errors, infos


def main() -> int:
    parser = argparse.ArgumentParser(description="GL-225/226 workspace context gate")
    parser.add_argument("--dry-run", action="store_true", help="Run checks without side effects")
    parser.add_argument("--plan", action="store_true", help="Alias for --dry-run")
    args = parser.parse_args()

    is_plan = args.dry_run or args.plan
    mode = "DRY-RUN" if is_plan else "CHECK"

    print(f"=== GL-225/226 Workspace Context Gate [{mode}] ===")
    print("LOCAL ONLY — no network, no credentials, no destructive operations.")
    print()

    errors, infos = run_checks()

    for info in infos:
        print(f"  [OK] {info}")

    print()

    if errors:
        print(f"GATE FAILED: {len(errors)} error(s):")
        for err in errors:
            print(f"  [FAIL] {err}")
        print()
        print("Fix the above before marking GL-225/226 ready_for_merge.")
        return 1

    print("All checks passed.")
    print()
    print("GL-225/226 gate: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
