# GL-191 Public Developer Experience Polish Pack

## Issue ID

GL-191

## Title

Public Developer Experience Polish Pack

## Context

After GL-188 (first output verify helper), GL-189 (grant lifecycle evidence
bundle), and GL-190 (demo endpoint safety guard) landed, the public README and
docs did not yet guide a first-time developer through the two no-install
runnable examples in order, explain what each example proves, or provide a
troubleshooting reference.

GL-191 polishes the public developer experience by:

- Adding "What to try first" and "What to try next" guidance to README.md.
- Cross-linking the verify helper and the grant lifecycle evidence bundle from
  README, and from each other.
- Adding a troubleshooting / FAQ section covering common first-run issues.
- Polishing the evidence bundle explanation doc.
- Updating the verify helper doc to point to the evidence bundle as the next step.

## Scope

Public docs/test/artifact only. No backend/src changes. No API, migration,
schema, or dependency changes. No frontend/website/design changes. No GitHub
workflow changes. No publication decisions.

## Public DX Improvements Made

### README changes

- Added "What to try first" section with the first verifiable output command
  and the verify-first-output.sh command.
- Added "What to try next" section with the grant lifecycle evidence bundle
  command and diff command.
- Updated "Developer entry path" table with steps 1–3 as no-install paths and
  step 4 (backend quickstart) clearly separated as requiring pip install.
- Updated "Choose your path" with Path A, Path A2, and Path B clearly separated.
- Added cross-links to docs/first_output_verify_helper.md,
  docs/grant_lifecycle_evidence_bundle.md, examples/first_verifiable_output.json,
  and examples/grant_lifecycle_evidence_bundle.json.
- Updated "Current status" table to include GL-188 through GL-191.
- Added cross-link to troubleshooting doc.

### Troubleshooting / FAQ additions

Added below in this file — see the "Troubleshooting / FAQ" section.

### Evidence bundle explanation polish

- Renamed heading from "GL-189 Grant Lifecycle Evidence Bundle" to
  "Grant Lifecycle Evidence Bundle" (removing the internal issue prefix).
- Improved the purpose paragraph.
- Added "Synthetic/Demo Data Only" section.
- Extended "What It Does Not Demonstrate" with real approval workflow and
  real grant decision clarifications.
- Updated the "Next Recommended Issue" pointer.

### Verify helper cross-links

- Added "What To Try Next" section in docs/first_output_verify_helper.md
  pointing to the grant lifecycle evidence bundle.
- Added cross-link to the troubleshooting doc.
- Updated "Next Recommended Issue" pointer.

## Caveats Preserved

- Developer Preview / technical preview posture preserved.
- Not production SaaS — not claimed.
- Tenant/workspace isolation not implemented — explicitly stated.
- Synthetic/demo data only — no real secrets, no customer data, no private grants.
- All public caveats from earlier README sections are preserved without change.

## Non-Goals

- No backend/src changes.
- No OpenAPI, migration, DB/schema, or dependency manifest changes.
- No SDK implementation changes.
- No examples runtime behavior changes.
- No frontend/website/design changes.
- No GitHub workflow changes.
- No snapshot publish script behavior changes.
- No public GitHub push.
- No visibility change.
- No production SaaS claim.
- No tenant isolation claim.
- No real customer/grant data requested.
- No secrets requested.
- No exploit details.

---

## Troubleshooting / FAQ

### "python3 not found"

Install Python 3.x using your OS package manager (e.g. `sudo apt install
python3` on Debian/Ubuntu). The no-install examples require only Python stdlib
— no virtualenv, no pip. Verify with:

```bash
python3 --version
```

### "Permission denied" or "script is not executable"

Make the script executable:

```bash
chmod +x scripts/verify-first-output.sh
```

Or run via bash explicitly:

```bash
bash scripts/verify-first-output.sh
```

### "verify-first-output mismatch"

The generated output does not match the committed reference artifact
(`examples/first_verifiable_output.json`). This usually means the example
script was edited locally or the reference artifact was modified. Steps:

1. Check `git diff examples/first_verifiable_output.py` and
   `git diff examples/first_verifiable_output.json`.
2. Restore both to the committed state with
   `git checkout examples/first_verifiable_output.py examples/first_verifiable_output.json`.
3. Rerun `scripts/verify-first-output.sh`.

### "grant lifecycle output mismatch"

The generated output does not match the committed reference artifact
(`examples/grant_lifecycle_evidence_bundle.json`). Steps:

1. Check `git diff examples/grant_lifecycle_evidence_bundle.py` and
   `git diff examples/grant_lifecycle_evidence_bundle.json`.
2. Restore both with `git checkout examples/grant_lifecycle_evidence_bundle.py
   examples/grant_lifecycle_evidence_bundle.json`.
3. Rerun the example and compare again.

### "I ran the backend quickstart but examples do not need backend"

The two local examples (`first_verifiable_output.py` and
`grant_lifecycle_evidence_bundle.py`) run entirely from Python stdlib. They do
not start or call the backend. You do not need to run the backend quickstart to
try them.

### "Do I need secrets?"

No. The local examples use only synthetic placeholders. No real tokens, API
keys, or credentials are needed or expected anywhere in the repository.

### "Do I need network access?"

No. The local examples run fully offline. No external service is called.

### "Can I use real customer data or real grant data?"

No. The examples are for local evaluation with synthetic/demo data only. Do not
use real customer identifiers, real institution data, or real grant records with
this repository.

### "Is this production SaaS?"

No. GrantLayer is in Developer Preview. It is intended for local evaluation and
controlled pilot discussion only — not for deployment to shared multi-tenant
infrastructure.

### "Is tenant isolation implemented?"

No. The backend does not currently enforce tenant/workspace boundaries. A single
namespace is used for all data.

### "Where do I report security-sensitive concerns?"

Report security-sensitive issues privately via GitHub Security Advisories on the
public repository at `https://github.com/Discodone/grantlayer`. See
[SECURITY.md](../SECURITY.md) for the full reporting guidance.

Do not include exploit details or proof-of-concept payloads in public GitHub
issues.

---

## Safety Confirmations

- no_github_push_performed: true
- no_visibility_change_performed: true
- internal_repo_not_pushed_directly_to_github: true
- no_backend_src_changes: true
- no_openapi_changes: true
- no_migration_db_dependency_changes: true
- no_frontend_website_design_changes: true
- no_github_workflow_changes: true
- no_snapshot_publish_script_behavior_changes: true
- no_production_saas_claim: true
- tenant_isolation_not_claimed: true
- no_real_customer_data_requested: true
- no_private_grant_data_requested: true
- no_secrets_requested: true
- no_exploit_details_included: true

## Next Recommended Issue

GL-191P Combined Merge-and-Publish for Public Developer Experience Polish Pack
