#!/usr/bin/env python3
"""Deterministic agent-trace extraction from a GrantLayer audit export.

STDLIB ONLY, no GrantLayer code — ships inside the agent evidence bundle so
a reviewer can re-derive the trace themselves and byte-compare it against
the bundled trace.json:

    python3 extract_agent_trace.py export.ndjson <subject> rederived.json
    diff trace.json rederived.json        # must be empty

The trace is a pure projection of the (independently verified) export:
for every data line whose subject_id matches, it keeps ONLY
{seq, timestamp, action, approved, reasonCode, matchedGrantId} — the tool
NAME is the witnessed action; tool ARGUMENTS are never witnessed anywhere
in the pipeline, so they cannot appear here. Entries keep export order
(the anchored seq-ASC total order). Serialization is pinned: sorted keys,
2-space indent, trailing newline — byte-deterministic for a given export.

Exit codes: 0 written, 2 usage/input error.
"""

from __future__ import annotations

import json
import sys


def extract(export_path: str, subject: str) -> dict:
    entries = []
    with open(export_path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            obj = json.loads(line)
            if not isinstance(obj, dict) or obj.get("_type") == "manifest":
                continue
            if obj.get("subject_id") != subject:
                continue
            entries.append({
                "seq": obj.get("seq"),
                "timestamp": obj.get("timestamp"),
                "action": obj.get("action"),
                "approved": obj.get("approved"),
                "reasonCode": obj.get("reason_code"),
                "matchedGrantId": obj.get("matched_grant_id"),
            })
    return {"subject": subject, "entryCount": len(entries), "entries": entries}


def write_trace(trace: dict, out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(trace, fh, sort_keys=True, indent=2, ensure_ascii=True)
        fh.write("\n")


def main(argv: list) -> int:
    if len(argv) != 3:
        print(
            "usage: extract_agent_trace.py <export.ndjson> <subject> <out.json>",
            file=sys.stderr,
        )
        return 2
    export_path, subject, out_path = argv
    try:
        trace = extract(export_path, subject)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    write_trace(trace, out_path)
    print(f"trace written: {out_path} ({trace['entryCount']} entries for "
          f"subject {subject})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
