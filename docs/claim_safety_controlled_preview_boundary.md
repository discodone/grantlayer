# GL-207 — Claim Safety & Controlled Preview Boundary

**Issue ID:** GL-207
**Branch:** `gl-207-claim-safety-controlled-preview-boundary`
**Status:** Internal / Developer Preview

---

## Title

Claim Safety & Controlled Preview Boundary

---

## Context

GL-200A through GL-206 are merged internally. The GL-200 tenant/workspace
isolation block, GL-201 production auth/secrets/config hardening, GL-202
persistence/PostgreSQL/migration readiness, GL-203 API contract/SDK packaging
decision, GL-203B OpenAPI contract cleanup, GL-203C SDK prototype/packaging
boundary, GL-204 Production Ops / Go-No-Go v3, GL-205 Live PostgreSQL /
Backup-Restore / Observability Baseline, and GL-206 Admin/Operator Tenant
Control Plane are all represented by clean doc, JSON, and test artifacts.

GL-207 is the Claim Safety & Controlled Preview Boundary pack. It audits
public-facing docs, metadata files, and accumulated decision artifacts for
stale, overbroad, misleading, or prohibited claims. It corrects stale claims
in allowed docs and produces a canonical controlled-preview boundary artifact
after GL-200 through GL-206.

**GrantLayer remains:**
- Developer Preview / Controlled Preview with strict boundaries
- Not production SaaS
- Not ready for real customer data, private grant data, or institutional data
- Tenant/workspace isolation baseline implemented but not production-complete
- Admin/operator control-plane baseline implemented, not a production tenant-management UI
- No official SDK/package is claimed or published
- No live PostgreSQL production claim

Security-sensitive reports route to GitHub Security Advisories. No exploit
details are included. No real secrets are included. No real customer/private
grant/institutional data is used.

---

## Scope

GL-207 covers:
- Reading and reviewing all input sources listed below
- Building a repository claim inventory
- Classifying claims as allowed, allowed-with-caveat, stale, misleading, prohibited, or requires-follow-up
- Defining the current controlled preview boundary after GL-200 through GL-206
- Correcting stale or unsafe wording in README.md, SECURITY.md, AGENTS.md, llms.txt, llms-full.txt
- Documenting allowed and prohibited claims
- Aligning GL-206 admin/operator control-plane claims
- Aligning GL-205 live PostgreSQL / backup-restore / observability claims
- Aligning GL-203C SDK prototype claims
- Producing this doc, the JSON artifact, and claim-safety tests
- Adding tests that prevent future claim drift

## Non-Goals

GL-207 is not:
- Implementation of product features
- Backend/src changes
- API behavior changes
- OpenAPI behavioral changes
- Migration, DB, schema, or dependency changes
- SDK/package implementation or publication
- Public publish, GitHub push, or visibility change
- Marketing website creation
- Frontend or design changes
- GitHub workflow changes
- Production SaaS readiness declaration
- Real customer data or private grant/institutional data readiness claim

---

## Input Sources Reviewed

| Source | Reviewed |
|--------|----------|
| docs/admin_operator_tenant_control_plane.md | Yes |
| docs/examples/gl206/admin_operator_tenant_control_plane.json | Yes |
| docs/live_postgres_backup_observability_baseline.md | Yes |
| docs/examples/gl205/live_postgres_backup_observability_baseline.json | Yes |
| docs/production_ops_go_no_go_v3.md | Yes |
| docs/examples/gl204/production_ops_go_no_go_v3.json | Yes |
| docs/sdk_prototype_packaging_boundary.md | Yes |
| docs/examples/gl203c/sdk_prototype_packaging_boundary.json | Yes |
| docs/openapi_api_contract_cleanup.md | Yes |
| docs/examples/gl203b/openapi_api_contract_cleanup.json | Yes |
| docs/api_contract_sdk_packaging_decision.md | Yes |
| docs/examples/gl203/api_contract_sdk_packaging_decision.json | Yes |
| docs/persistence_postgres_migration_readiness.md | Yes |
| docs/examples/gl202/persistence_postgres_migration_readiness.json | Yes |
| docs/production_auth_secrets_config_hardening.md | Yes |
| docs/examples/gl201/production_auth_secrets_config_hardening.json | Yes |
| docs/tenant_workspace_api_audit_regression_completion.md | Yes |
| docs/examples/gl200c/tenant_workspace_api_audit_regression_completion.json | Yes |
| docs/tenant_workspace_isolation_implementation_baseline.md | Yes |
| docs/examples/gl200b/tenant_workspace_isolation_implementation_baseline.json | Yes |
| docs/tenant_workspace_isolation_design_pack.md | Yes |
| docs/examples/gl200a/tenant_workspace_isolation_design_pack.json | Yes |
| docs/controlled_preview_boundary_pack.md | Yes |
| docs/examples/gl198/controlled_preview_boundary_pack.json | Yes |
| docs/production_readiness_gap_report_v2.md | Yes |
| docs/examples/gl199/production_readiness_gap_report_v2.json | Yes |
| README.md | Yes |
| SECURITY.md | Yes |
| AGENTS.md | Yes |
| llms.txt | Yes |
| llms-full.txt | Yes |
| docs/openapi.yaml | Yes |
| backend/src/server.py | Yes (read-only, claim accuracy only) |
| backend/src/auth.py | Yes (read-only, claim accuracy only) |
| backend/src/operators.py | Yes (read-only, claim accuracy only) |
| backend/src/config.py | Yes (read-only, claim accuracy only) |
| backend/src/db.py | Yes (read-only, claim accuracy only) |
| backend/src/audit_log.py | Yes (read-only, claim accuracy only) |
| backend/src/migrations/* | Yes (read-only, count/state only) |
| examples/sdk_prototype/python/grantlayer_client.py | Yes (read-only, claim accuracy only) |
| scripts/ops/gl205_live_postgres_validation.py | Yes (read-only, claim accuracy only) |
| scripts/ops/gl205_backup_restore_drill.py | Yes (read-only, claim accuracy only) |

---

## Claim Inventory Summary

### README.md

| Claim | Classification | Notes |
|-------|---------------|-------|
| Release label: GL-0.1 / Developer Preview | Allowed | Accurate |
| Maturity: local evaluation and controlled pilot only | Allowed | Accurate |
| Production SaaS readiness: Not claimed | Allowed | Accurate |
| Tenant/workspace isolation: **Not implemented** | Stale | GL-200–GL-206 implemented baseline; corrected to "Baseline implemented, not production-complete" |
| Real customer data in examples: No | Allowed | Accurate |
| Real secrets in examples: No | Allowed | Accurate |
| Public GitHub release: Available | Allowed | Accurate |
| "not production SaaS" in body text | Allowed | Accurate |
| "Tenant isolation is not implemented — data shares a single namespace." | Stale | Corrected to baseline implemented, not production-complete |
| "Tenant isolation is not implemented" in limitations | Stale | Corrected |
| Current status/next steps table ends at GL-192 | Stale | Updated to reflect GL-193–GL-207 |
| No admin routes in API Quick Reference | Allowed with caveat | Admin routes are internal/admin-only; not required in public API reference |

### SECURITY.md

| Claim | Classification | Notes |
|-------|---------------|-------|
| Maturity: Developer Preview | Allowed | Accurate |
| Production SaaS support guarantee: Not provided | Allowed | Accurate |
| Tenant/workspace isolation: **Not implemented** | Stale | Corrected to "Baseline implemented, not production-complete" |
| Security advisory reporting channel | Allowed | Accurate |
| "Tenant isolation not implemented" in caveats | Stale | Corrected |

### AGENTS.md

| Claim | Classification | Notes |
|-------|---------------|-------|
| Maturity: Developer Preview | Allowed | Accurate |
| Production SaaS readiness: Not claimed | Allowed | Accurate |
| Tenant/workspace isolation: **Not implemented** | Stale | Corrected to "Baseline implemented, not production-complete" |
| "Tenant isolation is not implemented." in body | Stale | Corrected |
| Forbidden: "Claim tenant isolation is implemented" | Misleading | After GL-200–GL-206 the baseline IS implemented; rule corrected to prohibit overclaiming production-complete isolation |
| Safety phrase: "tenant isolation is not implemented" | Stale | Updated to "tenant/workspace isolation is not production-complete" |

### llms.txt

| Claim | Classification | Notes |
|-------|---------------|-------|
| Status: Developer Preview | Allowed | Accurate |
| "Tenant isolation is not implemented." | Stale | Corrected |
| "Do not claim tenant isolation is implemented." | Misleading | Corrected to prohibit production-complete claim |
| Safety phrase: "tenant isolation is not implemented" | Stale | Updated |

### llms-full.txt

| Claim | Classification | Notes |
|-------|---------------|-------|
| Maturity: Developer Preview | Allowed | Accurate |
| Production SaaS readiness: Not claimed | Allowed | Accurate |
| Tenant/workspace isolation: Not implemented | Stale | Corrected |
| "Tenant isolation is not implemented" in body | Stale | Corrected |
| "Do not claim tenant isolation is implemented." | Misleading | Corrected |
| Next Issues section outdated (references GL-187/188) | Stale | Updated |

### docs/openapi.yaml

| Claim | Classification | Notes |
|-------|---------------|-------|
| Status: Developer Preview / Controlled Preview with strict boundaries | Allowed | Accurate |
| "not a production SaaS" | Allowed | Accurate |
| "No official SDK/package is claimed or published" | Allowed | Accurate |
| Tenant context server-derived | Allowed | Accurate |
| workspace_id deferred | Allowed | Accurate |
| Version "0.203b.0-developer-preview" | Allowed with caveat | Public API contract unchanged since GL-203B; GL-204–GL-206 admin routes are internal-only and intentionally excluded from public OpenAPI |
| Security advisories routing note | Allowed | Accurate |

### examples/sdk_prototype/python/grantlayer_client.py

| Claim | Classification | Notes |
|-------|---------------|-------|
| "NOT an official SDK" | Allowed | Accurate |
| "No package is published" | Allowed | Accurate |
| "Tenant/workspace isolation is baseline-implemented but not production-complete" | Allowed | Already correct — no change needed |

### sdk/python/README.md (not in GL-207 scope)

| Claim | Classification | Notes |
|-------|---------------|-------|
| "Tenant isolation is **not implemented**" | Stale | Out of GL-207 scope; recommend correction in GL-208 or follow-up |

### Prior Decision Docs (docs/controlled_preview_boundary_pack.md, docs/production_readiness_gap_report_v2.md, etc.)

All prior decision docs are historical records accurate at the time of their issue. They are not updated by GL-207. The stale tenant isolation phrasing within historical docs (e.g., GL-198, GL-199) is acceptable context for those points in time.

---

## Controlled Preview Boundary

After GL-200 through GL-206, the controlled preview boundary is:

### Allowed

| Tier | Status |
|------|--------|
| Developer Preview (local evaluation) | ALLOWED |
| Controlled Preview (strict boundaries) | ALLOWED |
| Controlled Preview expansion | CONDITIONAL — synthetic/demo data only |
| First external controlled pilot | CONDITIONAL — synthetic/demo data only, no real customer/private grant data |
| Internal development and testing | ALLOWED |
| Synthetic/demo data in all paths | ALLOWED |

### Not Allowed / No-Go

| Tier | Status |
|------|--------|
| Production SaaS | NO-GO |
| Real customer data | NO-GO |
| Private grant/institutional data | NO-GO |
| Official SDK/package | NO-GO |
| Live PostgreSQL production deployment | NO-GO |
| Public website/marketing expansion | DEFERRED until website claim gate |
| Production multi-tenant deployment | NO-GO |

---

## Allowed Claims

The following claims are accurate and allowed:

| Allowed Claim | Basis |
|---------------|-------|
| Developer Preview posture | GL-198 boundary, GL-204 decision |
| Controlled Preview with strict boundaries | GL-198 boundary, GL-204 decision |
| API-first grant-layer prototype | GL-197, GL-198 |
| Tenant/workspace isolation baseline implemented, not production-complete | GL-200A–GL-206 |
| Auth/secrets/config hardening improved (fail-closed, PBKDF2, structured logging) | GL-201 |
| Migration/PostgreSQL readiness improved; live validation incomplete | GL-202, GL-205 |
| OpenAPI contract cleaned and stable as of GL-203B | GL-203B |
| Internal SDK prototype exists; not an official SDK | GL-203C |
| Backup/restore baseline exists for synthetic/demo SQLite drill | GL-205 |
| Observability baseline documented | GL-205 |
| Admin/operator tenant control-plane baseline exists; not a production tenant-management UI | GL-206 |
| Controlled preview expansion conditional on synthetic/demo data | GL-198, GL-204 |
| No real secrets or customer data in examples | All |
| Security-sensitive reports route to GitHub Security Advisories | GL-153, GL-192 |

---

## Prohibited Claims

The following claims are prohibited:

| Prohibited Claim | Reason |
|-----------------|--------|
| Production SaaS ready | NO-GO per GL-204 |
| Enterprise ready | NO-GO — multiple P0 gaps remain |
| Compliance ready | NO-GO — no compliance certification |
| Ready for real customer data | NO-GO — no production multi-tenant isolation |
| Ready for private grant/institutional data | NO-GO — no production data handling |
| Official SDK/package available | NO-GO — internal prototype only |
| Production-ready SDK | NO-GO |
| Public SDK package available | NO-GO |
| Live PostgreSQL production ready | NO-GO — live validation not executed |
| Complete tenant/workspace production guarantee | NO-GO — baseline only |
| Complete admin/operator tenant-management plane | NO-GO — baseline only |
| Production DR ready | NO-GO — no production backup/restore automation |
| Production observability stack complete | NO-GO — baseline only |
| Security/compliance certified | NO-GO — no external certification |
| First external pilot has started | NO-GO — pilot remains conditional/deferred |

---

## Stale Claim Corrections

The following stale claims were found and corrected in this issue:

### README.md

1. **Status table — Tenant/workspace isolation**
   - Old: `Tenant/workspace isolation | **Not implemented**`
   - New: `Tenant/workspace isolation | **Baseline implemented — not production-complete** (GL-200–GL-206)`
   - Reason: GL-200A–GL-206 implemented tenant_id server-derivation, cross-tenant data isolation, operator model with tenant assignment, and admin control-plane. Full multi-tenant isolation and workspace enforcement remain deferred.

2. **Agent caveats section**
   - Old: "**Tenant isolation is not implemented** — data shares a single namespace."
   - New: "**Tenant/workspace isolation baseline is implemented** (GL-200–GL-206) but not production-complete. Full multi-tenant RBAC, workspace enforcement, and production IAM remain deferred."

3. **Safety and limitations section**
   - Old: "Tenant isolation is not implemented — the backend does not enforce tenant/workspace boundaries at the data, authorization, or audit layers."
   - New: "Tenant/workspace isolation baseline is implemented (GL-200–GL-206) — the backend derives tenant context server-side and enforces cross-tenant data boundaries at the data and authorization layers. Full multi-tenant production isolation, workspace enforcement, and production IAM remain deferred."

4. **Current status and next steps table**
   - Added GL-193 through GL-207 entries.

### SECURITY.md

1. **Supported Status table — Tenant/workspace isolation**
   - Old: `Tenant/workspace isolation | **Not implemented**`
   - New: `Tenant/workspace isolation | **Baseline implemented, not production-complete** (GL-200–GL-206)`

2. **Section 6 Current Caveats**
   - Old: "Tenant isolation not implemented — the backend does not enforce tenant/workspace boundaries at the data, authorization, or audit layers."
   - New: "Tenant/workspace isolation baseline is implemented (GL-200–GL-206) but not production-complete. The backend enforces tenant context server-side. Full multi-tenant production isolation, workspace enforcement, and production IAM remain deferred."

### AGENTS.md

1. **Status table — Tenant/workspace isolation**
   - Old: `Tenant/workspace isolation | **Not implemented**`
   - New: `Tenant/workspace isolation | **Baseline implemented, not production-complete** (GL-200–GL-206)`

2. **Body text**
   - Old: "Tenant isolation is not implemented."
   - New: "Tenant/workspace isolation baseline is implemented (GL-200–GL-206) but not production-complete."

3. **Forbidden by Default rule**
   - Old: "Claim tenant isolation is implemented"
   - New: "Claim production-complete or production-grade tenant isolation"

4. **Safety phrase**
   - Old: "tenant isolation is not implemented"
   - New: "tenant/workspace isolation is not production-complete"

### llms.txt

1. **Caveats section**
   - Old: "Tenant isolation is not implemented."
   - New: "Tenant/workspace isolation baseline is implemented (GL-200–GL-206) but not production-complete."

2. **Safety rules**
   - Old: "Do not claim tenant isolation is implemented."
   - New: "Do not claim production-complete or production-grade tenant isolation."

3. **Exact Safety Phrases**
   - Old: "tenant isolation is not implemented"
   - New: "tenant/workspace isolation is not production-complete"

### llms-full.txt

1. **Status table**
   - Old: `Tenant/workspace isolation | Not implemented`
   - New: `Tenant/workspace isolation | Baseline implemented, not production-complete (GL-200–GL-206)`

2. **Body text**
   - Old: "**Tenant isolation is not implemented** — data shares a single namespace."
   - New: "**Tenant/workspace isolation baseline is implemented** (GL-200–GL-206) but not production-complete. Full multi-tenant RBAC, workspace enforcement, and production IAM remain deferred."

3. **No-Overclaim Rules**
   - Old: "Do not claim tenant isolation is implemented."
   - New: "Do not claim production-complete or production-grade tenant isolation."

---

## Public Docs Impact

| Doc | Impact | Action |
|-----|--------|--------|
| README.md | Stale tenant isolation claim corrected; status table updated | Updated |
| SECURITY.md | Stale tenant isolation claim corrected | Updated |
| AGENTS.md | Stale tenant isolation claim corrected; forbidden rule updated | Updated |
| llms.txt | Stale tenant isolation claim corrected; safety phrases updated | Updated |
| llms-full.txt | Stale tenant isolation claim corrected; no-overclaim rules updated | Updated |
| docs/openapi.yaml | No update required — existing claims are accurate | No change |
| Prior decision docs | Historical records — no change | No change |
| sdk/python/README.md | Out of GL-207 scope (stale claim noted for follow-up) | Deferred |

---

## OpenAPI Claim Impact

The public OpenAPI contract (`docs/openapi.yaml`, version `0.203b.0-developer-preview`) was reviewed
and found accurate:

- Status line "Developer Preview / Controlled Preview with strict boundaries" — accurate.
- "not a production SaaS" — accurate.
- "No official SDK/package is claimed or published" — accurate.
- Tenant context is server-derived — accurate.
- workspace_id reserved/deferred — accurate.
- Security advisory routing note — accurate.

The version string `0.203b.0-developer-preview` reflects the last contract change in GL-203B.
GL-204, GL-205, and GL-206 did not change the public API contract. GL-206 admin routes
(`/admin/operators`, `/admin/operators/{id}`, `/admin/operators/{id}/revoke`) are internal/admin-only
and are intentionally excluded from the public OpenAPI spec. This is accurate and no change required.

---

## SDK Claim Boundary

| Claim | Status |
|-------|--------|
| Internal prototype exists at examples/sdk_prototype/python/ | Allowed |
| GL-203C prototype demonstrates GL-203B contract is SDK-compatible | Allowed |
| "NOT an official SDK" | Required and present |
| "No package is published" | Required and present |
| GL-203D (official SDK) remains deferred | Confirmed |
| examples/sdk_prototype/python/grantlayer_client.py already has correct claim language | No change needed |
| sdk/python/README.md has stale "Tenant isolation is not implemented" | Out of scope (GL-207); recommend follow-up |

---

## Tenant/Workspace Claim Boundary

After GL-200 through GL-206:

| Claim | Status |
|-------|--------|
| Tenant/workspace isolation baseline is implemented | Allowed |
| tenant_id enforced server-side, not client-supplied | Allowed |
| Cross-tenant data boundaries enforced | Allowed |
| workspace_id field present but not enforced | Allowed |
| workspace-level isolation deferred | Allowed |
| Full production multi-tenant isolation | NOT allowed — not implemented |
| Production RBAC / IAM | NOT allowed — not implemented |
| Complete workspace enforcement | NOT allowed — deferred |

---

## Admin/Operator Claim Boundary

After GL-206:

| Claim | Status |
|-------|--------|
| Admin/operator tenant control-plane baseline exists | Allowed |
| Admin-only control-plane HTTP routes exist (POST /admin/operators, GET /admin/operators, etc.) | Allowed |
| Admin routes are internal/admin-only (not public API) | Accurate |
| Operator tenant_id is server-assigned, not client-overridable | Allowed |
| Structured audit events for operator_created/revoked | Allowed |
| Complete production admin plane | NOT allowed — baseline only |
| Production tenant-management UI | NOT allowed — does not exist |
| Full production RBAC | NOT allowed — not implemented |
| Production IAM (OAuth/JWT/SSO) | NOT allowed — not implemented |

---

## Live PostgreSQL Claim Boundary

After GL-205:

| Claim | Status |
|-------|--------|
| PostgreSQL live validation script exists (dry-run/plan mode) | Allowed |
| Dry-run/plan passed | Allowed |
| SQLite synthetic backup/restore drill passed | Allowed |
| Observability baseline documented | Allowed |
| Live PostgreSQL validation executed against real database | NOT allowed — not executed |
| Live PostgreSQL production ready | NOT allowed — not claimed |
| Production backup/restore automation | NOT allowed — not implemented |

---

## Backup/Restore/DR Claim Boundary

| Claim | Status |
|-------|--------|
| Backup/restore drill baseline exists for SQLite synthetic data | Allowed |
| PostgreSQL manual backup checklist documented | Allowed |
| Dry-run/plan mode validated | Allowed |
| Production DR ready | NOT allowed — not implemented |
| Production backup/restore automation | NOT allowed — not implemented |
| Production RTO/RPO guarantees | NOT allowed — not documented |

---

## Observability Claim Boundary

| Claim | Status |
|-------|--------|
| Observability baseline documented (GL-205) | Allowed |
| Structured log events with correlation IDs | Allowed |
| Signal categories documented | Allowed |
| Secret-safety rules in logging documented | Allowed |
| Production observability stack complete | NOT allowed — not implemented |
| External metrics/alerting/tracing | NOT allowed — not implemented |
| Production SLO/SLA observability | NOT allowed — not claimed |

---

## First External Controlled Pilot Boundary

| Condition | Status |
|-----------|--------|
| First external controlled pilot is conditional | Confirmed |
| Synthetic/demo data only | Required |
| No real customer data | Required |
| No private grant/institutional data | Required |
| Controlled reviewer pool | Required |
| Boundary doc (GL-198) shared with pilot participants | Required |
| First pilot has started | NOT claimed |

---

## Website/Marketing Deferral

| Item | Status |
|------|--------|
| Public marketing website | Deferred |
| Marketing landing page | Deferred |
| Website claim gate | Pending |
| External marketing copy | Deferred until claim boundary is clean |
| Unrelated website design files (website-design/, docs/website_design*) | Excluded from GL-207 |

---

## Production Readiness Impact

After GL-207 claim corrections:

| Category | Status |
|----------|--------|
| Developer Preview posture | CONFIRMED |
| Controlled Preview with strict boundaries | CONFIRMED |
| Production SaaS | NO-GO |
| Real customer data | NO-GO |
| Private grant/institutional data | NO-GO |
| Official SDK/package | NO-GO |
| Live PostgreSQL production | NO-GO |
| Full multi-tenant production isolation | NO-GO |
| Production observability stack | NO-GO |
| Production DR | NO-GO |

---

## Remaining Gaps

| Gap | Category | Priority |
|-----|----------|----------|
| Production IAM (OAuth/JWT/SSO) not implemented | P0 production blocker | P0 |
| Live PostgreSQL validation not executed | P0 ops blocker | P0 |
| workspace_id enforcement deferred | P1 isolation gap | P1 |
| Full multi-tenant RBAC not implemented | P0 production blocker | P0 |
| Production observability stack (external metrics, alerting, tracing) | P0 production blocker | P0 |
| Production backup/restore automation | P0 production blocker | P0 |
| Key management (demo Ed25519 keypair in repo) | P0 production blocker | P0 |
| CORS origin hardening for production | P1 | P1 |
| sdk/python/README.md stale "tenant isolation is not implemented" | Low claim drift | Low |
| Public marketing website deferred | Deferred | Deferred |

---

## Risk Register

| ID | Description | Category | Severity | Mitigation |
|----|-------------|----------|----------|-----------|
| RR-207-01 | Old tests checking for "tenant isolation is not implemented" exact phrase in AGENTS.md, llms.txt, README.md, etc. will fail on GL-207 branch | scope-guard false positive | Low | Classified as branch-only scope-guard false positives; GL-207 tests check new correct phrase |
| RR-207-02 | sdk/python/README.md retains stale "Tenant isolation is not implemented" | claim drift | Low | Out of GL-207 scope; document for follow-up |
| RR-207-03 | Prior historical decision docs (GL-198, GL-199) retain old phrasing | expected | Low | Historical docs are accurate for their time; not updated |
| RR-207-04 | First external controlled pilot expansion could trigger data safety risk if boundary not enforced | data safety | High | Boundary documented; synthetic/demo data only; pilot remains conditional |
| RR-207-05 | Production SaaS claim drift if future contributors miss claim boundary | claim drift | Medium | GL-207 tests added; AGENTS.md/llms.txt rules updated |

---

## Decision

**claim_safety_corrections_approved_controlled_preview_confirmed**

---

## Decision Rationale

1. The claim "Tenant/workspace isolation: Not implemented" in README, SECURITY, AGENTS, llms.txt,
   and llms-full.txt is stale after GL-200 through GL-206 implemented the isolation baseline.
   The accurate claim is "Baseline implemented, not production-complete."

2. The controlled preview boundary after GL-200 through GL-206 is well-defined:
   Developer Preview and Controlled Preview continue with strict boundaries; Production SaaS
   remains NO-GO; real customer/private grant data remains NO-GO.

3. The admin/operator control-plane baseline (GL-206) does not constitute a production
   tenant-management UI and must not be overclaimed as such.

4. The OpenAPI contract (docs/openapi.yaml, version 0.203b.0-developer-preview) is accurate —
   the public contract did not change from GL-204 through GL-206.

5. The SDK prototype (GL-203C) is correctly labeled "NOT an official SDK" and requires no
   claim corrections.

6. All claim corrections are conservative and accurate — no production claims are added,
   and the "not production-complete" caveat is explicit and prominent.

---

## Safety Confirmations

| Confirmation | Status |
|-------------|--------|
| No exploit details included | Confirmed |
| No real secrets included | Confirmed |
| No real customer data included | Confirmed |
| No private grant/institutional data included | Confirmed |
| Security-sensitive reports route to GitHub Security Advisories | Confirmed |
| Production SaaS is not claimed | Confirmed |
| Real customer data is not claimed ready | Confirmed |
| Private grant/institutional data is not claimed ready | Confirmed |
| Official SDK/package is not claimed | Confirmed |
| Live PostgreSQL production is not claimed | Confirmed |
| Tenant isolation is not overclaimed as production-complete | Confirmed |
| Admin/operator plane is not overclaimed as production-complete | Confirmed |
| No backend/src changes | Confirmed |
| No API behavior changes | Confirmed |
| No migrations/DB/schema/dependency changes | Confirmed |
| No SDK/package implementation changes | Confirmed |
| No package publishing metadata | Confirmed |
| No frontend/website/design changes | Confirmed |
| No GitHub workflow changes | Confirmed |
| No public GitHub push | Confirmed |
| No visibility change | Confirmed |
| Unrelated website files (website-design/, docs/website_design*) excluded | Confirmed |

---

## Recommended Next Issues

| Issue | Title | Purpose |
|-------|-------|---------|
| GL-208 | Production IAM Baseline | OAuth/JWT/SSO baseline — P0 production blocker |
| GL-209 | Live PostgreSQL Validation Execution | Execute GL-205 validation against real database |
| GL-210 | workspace_id Enforcement Baseline | Implement workspace-level isolation |
| GL-211 | SDK README Claim Correction | Update sdk/python/README.md stale tenant isolation claim |

---

> This document was created in **GL-207 Claim Safety & Controlled Preview Boundary**.
> It does not change production code, API behavior, migrations, DB/schema, dependencies,
> SDK implementations, package publishing metadata, frontend/website/design, GitHub workflows,
> git remotes, or make any public publish or visibility change.
> All examples use synthetic identifiers and placeholder tokens only.
