"""GrantLayer MVP — GL-028 Offline Evidence Bundle Verifier CLI.

Usage:
    python3 scripts/verify_evidence_bundle.py path/to/evidence.json

Exit codes:
    0  OK evidence bundle verified
    2  FAIL evidence hash mismatch
    3  FAIL invalid evidence bundle artifact
    4  FAIL unsupported evidence bundle format
    5  FAIL evidence bundle file read or parse error

Constraints:
- Python stdlib only
- No network calls
- No database access
- No secrets printed
"""

import json
import sys
from pathlib import Path

# Allow running from repo root without installing the backend package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from src.evidence_bundle import verify_evidence_export_artifact  # noqa: E402


def main(argv: list[str]) -> int:
    json_output = "--json" in argv
    args = [a for a in argv if a != "--json"]

    if len(args) < 2:
        msg = "missing file path"
        if json_output:
            print(json.dumps({"ok": False, "error": "parse_error", "reason": msg}), file=sys.stdout)
        else:
            print("FAIL evidence bundle file read or parse error", file=sys.stdout)
        return 5

    path = Path(args[1]).resolve()
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, PermissionError) as exc:
        if json_output:
            print(json.dumps({"ok": False, "error": "parse_error", "reason": "file read error"}), file=sys.stdout)
        else:
            print("FAIL evidence bundle file read or parse error", file=sys.stdout)
        return 5

    try:
        bundle = json.loads(raw)
    except json.JSONDecodeError as exc:
        if json_output:
            print(json.dumps({"ok": False, "error": "parse_error", "reason": "json decode error"}), file=sys.stdout)
        else:
            print("FAIL evidence bundle file read or parse error", file=sys.stdout)
        return 5

    result = verify_evidence_export_artifact(bundle)

    if json_output:
        print(json.dumps(result, sort_keys=True, indent=2), file=sys.stdout)
        if result["ok"]:
            return 0
        error = result.get("error", "invalid_artifact")
        if error == "hash_mismatch":
            return 2
        if error == "unsupported_format":
            return 4
        return 3

    if result["ok"]:
        print("OK evidence bundle verified", file=sys.stdout)
        return 0

    error = result.get("error", "invalid_artifact")
    if error == "hash_mismatch":
        print("FAIL evidence hash mismatch", file=sys.stdout)
        return 2
    if error == "unsupported_format":
        print("FAIL unsupported evidence bundle format", file=sys.stdout)
        return 4
    # invalid_artifact (and any unexpected fallback)
    print("FAIL invalid evidence bundle artifact", file=sys.stdout)
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))