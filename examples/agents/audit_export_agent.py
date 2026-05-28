"""Audit Export Agent — dry-run example for GrantLayer.

This module demonstrates a conceptual audit-export workflow using
only Python's standard library. It uses fake/demo audit events only and
performs no network calls.

Caveats:
- Developer Preview — local evaluation only
- Not a production SaaS
- Tenant isolation is not implemented
- No real secrets
- No real customer data
"""

import json
from dataclasses import dataclass, field
from typing import List


@dataclass
class AuditEvent:
    event_id: str
    event_type: str
    timestamp: str
    subject: str
    details: str


def build_demo_audit_events() -> List[AuditEvent]:
    """Return a list of demo audit events with synthetic identifiers."""
    return [
        AuditEvent(
            event_id="gl155-demo-event-001",
            event_type="grant_created",
            timestamp="2026-05-01T09:00:00Z",
            subject="gl155-demo-admin-001",
            details="Synthetic grant created for demo purposes.",
        ),
        AuditEvent(
            event_id="gl155-demo-event-002",
            event_type="evidence_submitted",
            timestamp="2026-05-01T09:15:00Z",
            subject="gl155-demo-subject-001",
            details="Synthetic evidence bundle submitted.",
        ),
        AuditEvent(
            event_id="gl155-demo-event-003",
            event_type="approval_given",
            timestamp="2026-05-01T09:30:00Z",
            subject="gl155-demo-admin-001",
            details="Synthetic approval recorded.",
        ),
        AuditEvent(
            event_id="gl155-demo-event-004",
            event_type="execution_logged",
            timestamp="2026-05-01T09:45:00Z",
            subject="gl155-demo-subject-001",
            details="Synthetic execution event logged.",
        ),
    ]


def export_audit_events(events: List[AuditEvent]) -> dict:
    """Export demo audit events as a deterministic summary."""
    event_counts: dict[str, int] = {}
    for ev in events:
        event_counts[ev.event_type] = event_counts.get(ev.event_type, 0) + 1

    return {
        "agent_name": "audit_export_agent",
        "mode": "dry_run",
        "developer_preview": True,
        "production_saas_ready": False,
        "tenant_isolation_implemented": False,
        "uses_real_customer_data": False,
        "uses_real_secrets": False,
        "grantlayer_concept": "audit_export",
        "exported_event_count": len(events),
        "audit_summary": {
            "event_counts": event_counts,
            "time_range": {
                "from": events[0].timestamp if events else None,
                "to": events[-1].timestamp if events else None,
            },
        },
    }


def main() -> None:
    events = build_demo_audit_events()
    result = export_audit_events(events)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
