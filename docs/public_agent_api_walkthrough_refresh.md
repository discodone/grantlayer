# GL-193 Public Agent/API Walkthrough Refresh

## Issue ID

GL-193

## Title

Public Agent/API Walkthrough Refresh

## Context

GrantLayer is publicly available on GitHub in Developer Preview / controlled
pilot posture. External developers and coding agents need one clear path that
shows:

1. what GrantLayer is,
2. what to run first,
3. what to run next,
4. how agent tasks should be handled,
5. how the no-install examples relate to the backend/API path,
6. what API walkthrough exists today, and
7. what is intentionally not production-ready.

This walkthrough ties together the public README, agent entry points, the first
output verify helper, the grant lifecycle evidence bundle, the backend
quickstart, and the public feedback infrastructure.

## Public Developer Entry Points

- [README.md](../README.md) - project overview, status, and the public path to try first.
- [docs/first_output_verify_helper.md](first_output_verify_helper.md) - verify the first no-install example.
- [docs/grant_lifecycle_evidence_bundle.md](grant_lifecycle_evidence_bundle.md) - the second no-install example.
- [docs/ten_minute_quickstart.md](ten_minute_quickstart.md) - backend quickstart after the deterministic examples.
- [docs/public_feedback_infrastructure_pack.md](public_feedback_infrastructure_pack.md) - public feedback intake and security routing.
- [SECURITY.md](../SECURITY.md) - security-sensitive reporting guidance.

## Coding Agent Entry Points

- [AGENTS.md](../AGENTS.md) - rules, safe/forbidden areas, and branch workflow.
- [llms.txt](../llms.txt) - concise agent entry map.
- [llms-full.txt](../llms-full.txt) - expanded repository map and caveats.
- [docs/agent_quickstart.md](agent_quickstart.md) - 60-second orientation.
- [docs/agent_task_contract.md](agent_task_contract.md) - issue contract and final report format.

## Recommended First Path

Start here first, from the repository root:

```bash
scripts/verify-first-output.sh
```

This verifies the first deterministic public output without starting the backend.
It is the fastest public confidence check and requires no network, no secrets,
and no customer data.

## Recommended Second Path

Run the second deterministic example next:

```bash
python3 examples/grant_lifecycle_evidence_bundle.py
```

Optional comparison against the committed reference:

```bash
python3 examples/grant_lifecycle_evidence_bundle.py --output /tmp/grantlayer_gl193_grant_lifecycle_check.json
diff -u examples/grant_lifecycle_evidence_bundle.json /tmp/grantlayer_gl193_grant_lifecycle_check.json
```

## API / Server Path Overview

Use the backend quickstart only after the two deterministic examples are clear.
The backend path is documented in [docs/ten_minute_quickstart.md](ten_minute_quickstart.md)
and summarized in [README.md](../README.md).

Prerequisites are kept intentionally separate from the no-install examples:

- Python 3.10+ (Python 3.13 recommended)
- Git and a local shell
- A local checkout of the repository
- A virtual environment and `pip install -r requirements.txt` for backend work

Do not invent additional setup steps here. Follow the existing quickstart docs
for the exact backend and health-check commands.

## Agent Workflow

- Read README.md, AGENTS.md, llms.txt, and llms-full.txt first.
- Use synthetic or demo data only.
- Do not request or paste secrets, real customer data, or private grants.
- Do not modify forbidden files unless the issue explicitly allows them.
- Run the relevant targeted tests before declaring the task complete.
- Report scope, changed files, safety confirmations, and caveats honestly.

## API Walkthrough State

GrantLayer today offers:

- a public first-output verify helper,
- a second runnable grant lifecycle evidence bundle,
- a local backend quickstart for validation and smoke checks,
- a minimal Python SDK README,
- and public feedback routing guidance.

What it does not claim:

- not production SaaS,
- tenant/workspace isolation not implemented,
- or maturity beyond the documented public examples and local backend smoke path.

This walkthrough is a documentation refresh, not runtime API work. It does not
change backend behavior or add new API surface.

## Feedback Path

For ordinary public feedback, use the guidance in
[docs/public_feedback_infrastructure_pack.md](public_feedback_infrastructure_pack.md).
For security-sensitive concerns, use GitHub Security Advisories via
[SECURITY.md](../SECURITY.md) and
https://github.com/Discodone/grantlayer/security/advisories.
Do not file exploit details publicly.

## Consistency Notes

- The public repository is already available at `https://github.com/Discodone/grantlayer.git`.
- The first path is no-install and offline.
- The second path is still no-install and offline.
- The backend path is separate and requires the documented prerequisites.
- Public feedback routing stays on synthetic/demo data and private security handling.

## Non-Goals

- No backend runtime behavior changes.
- No OpenAPI changes.
- No migrations, schema, dependency, SDK implementation, or frontend/design changes.
- No GitHub workflow changes.
- No publication or visibility changes.
- No GitHub API label or issue automation.
- No reviewer outreach.

## Safety Confirmations

- no real secrets
- no real customer data
- no private grants
- no exploit details
- no production SaaS claim
- tenant isolation is not implemented
- no GitHub push performed
- no visibility change performed

## Next Recommended Issue

GL-193 Combined Merge-and-Publish for Public Agent/API Walkthrough Refresh
