# GL-214 — Production IAM & Operator Control Completion

**Issue ID:** GL-214
**Title:** Production IAM & Operator Control Completion
**Branch:** `gl-214-production-iam-operator-control-completion`
**Status:** Internal / Developer Preview

GL-214 is production IAM and operator-control hardening. It is not a
production SaaS readiness declaration.

GrantLayer remains Developer Preview / Controlled Preview with strict
boundaries. Controlled Preview remains synthetic/demo data only. Production
SaaS remains no-go unless a later production go/no-go gate changes that.
Real customer data, private grant data, and institutional data remain no-go.
Official SDK/package remains no-go. Compliance certification remains no-go.
GDPR, SOC2, ISO, and enterprise readiness are not claimed. Ephemeral live
PostgreSQL validation passed, but production PostgreSQL readiness remains
no-go.
Ephemeral live PostgreSQL validation passed, but production PostgreSQL readiness remains no-go.

Security-sensitive reports route to GitHub Security Advisories. No exploit
details are included. No real secrets are included. No real customer/private
data is used.
No real customer/private data is used.

Unrelated website-design/import files were excluded from GL-214. No
`website-design/` content or similarly named website-design import/report files
are included in this change.

---

## Context

GL-213 identified Production IAM Completion as the highest-priority P0 blocker.
GL-201 already added fail-closed production-like config checks and placeholder
token rejection. GL-206 added the admin/operator tenant control-plane baseline.
GL-208 added runtime abuse and incident hardening. GL-211 and GL-212 preserved
SDK, pilot, public, and external-review boundaries.

GL-214 reviews those controls and implements the minimum safe hardening needed
to materially reduce the IAM/operator-control blocker without adding OIDC, SAML,
SSO, browser login, MFA, a broad RBAC engine, or a new policy provider.

---

## Scope

GL-214 covers:
- Current admin token and operator token behavior
- Revoked/inactive operator handling
- Operator tenant assignment and role/scope boundaries
- Admin/operator route protection
- Fail-closed behavior for missing or invalid credentials/config
- Placeholder/default token rejection in production-like modes
- Bootstrap operator-token behavior
- Operator create/list/get/revoke permissions
- Durable audit coverage for operator create/revoke actions
- Token/secret leakage prevention
- Tenant/workspace preservation
- Remaining production IAM blockers

## Non-Goals

GL-214 does not:
- Claim Production SaaS readiness
- Claim real customer/private grant/institutional data readiness
- Add OIDC, SAML, SSO, MFA, password reset, browser login, or user accounts
- Implement a full enterprise IAM system or broad RBAC/policy rewrite
- Publish packages or create package metadata
- Create public snapshots, public export directories, public release branches,
  public release tags, or public GitHub pushes
- Change GitHub workflows, snapshot publish scripts, visibility, deployment
  config, external hostnames, analytics, tracking, or forms
- Weaken GL-201, GL-206, GL-208, GL-209, GL-212, or GL-213 boundaries

---

## Input Sources Reviewed

| Source | Reviewed |
|---|---|
| docs/production_readiness_gap_report_v4.md | Yes |
| docs/examples/gl213/production_readiness_gap_report_v4.json | Yes |
| docs/public_external_review_readiness_gate_pack.md | Yes |
| docs/examples/gl212/public_external_review_readiness_gate_pack.json | Yes |
| docs/sdk_pilot_production_gate.md | Yes |
| docs/examples/gl211/sdk_pilot_production_gate.json | Yes |
| docs/live_postgres_validation_execution_gl206b.md | Yes |
| docs/examples/gl206b/live_postgres_validation_execution_gl206b.json | Yes |
| docs/admin_operator_tenant_control_plane.md | Yes |
| docs/examples/gl206/admin_operator_tenant_control_plane.json | Yes |
| docs/production_auth_secrets_config_hardening.md | Yes |
| docs/examples/gl201/production_auth_secrets_config_hardening.json | Yes |
| docs/runtime_abuse_incident_hardening.md | Yes |
| docs/examples/gl208/runtime_abuse_incident_hardening.json | Yes |
| docs/data_governance_audit_operations.md | Yes |
| docs/examples/gl209/data_governance_audit_operations.json | Yes |
| docs/tenant_workspace_api_audit_regression_completion.md | Yes |
| docs/examples/gl200c/tenant_workspace_api_audit_regression_completion.json | Yes |
| docs/tenant_workspace_isolation_implementation_baseline.md | Yes |
| docs/examples/gl200b/tenant_workspace_isolation_implementation_baseline.json | Yes |
| docs/tenant_workspace_isolation_design_pack.md | Yes |
| docs/examples/gl200a/tenant_workspace_isolation_design_pack.json | Yes |
| docs/openapi.yaml | Yes |
| README.md | Yes |
| SECURITY.md | Yes |
| AGENTS.md | Yes |
| llms.txt | Yes |
| llms-full.txt | Yes |
| backend/src/auth.py | Yes |
| backend/src/config.py | Yes |
| backend/src/operators.py | Yes |
| backend/src/server.py | Yes |
| backend/src/audit_log.py | Yes |
| backend/src/db.py | Yes |
| backend/src/models.py | Yes |
| backend/src/grant_requests.py | Yes |
| backend/tests/ | Yes |
| scripts/ops/ | Yes |
| examples/grant_lifecycle_evidence_bundle.py | Yes |

---

## Current IAM/Operator State Summary

Admin authentication uses `GRANTLAYER_ADMIN_TOKEN` with Bearer-token validation
and constant-time comparison. Missing or invalid admin credentials fail closed
on admin-only endpoints when admin-token enforcement is enabled. Production-like
startup checks reject missing, placeholder, default, or short admin tokens.

Operator authentication uses the operator model by default. Operator tokens are
stored as PBKDF2-HMAC-SHA256 hashes with a deterministic lookup hash used only
to narrow candidates before PBKDF2 verification. Revoked/inactive rows are
excluded from authentication queries. Expired or malformed tokens fail closed
with safe reason codes.

Tenant context is server-derived. Operator tenant context comes from the stored
operator row; admin legacy mode is bound to the demo tenant. Caller-provided
tenant headers do not override the server-derived tenant. Workspace enforcement
remains a later production blocker.

Admin/operator control-plane routes exist for create, list, get, and revoke.
List/get responses expose safe fields only and do not expose token hashes,
lookup hashes, auth headers, or raw tokens. Create returns a one-time raw token.

---

## Production IAM Gap Assessment

| Area | Current State | Gap |
|---|---|---|
| Admin token validation | Present, constant-time, fail-closed when required | Single static admin token; no provider-backed identity |
| Operator token validation | PBKDF2 + lookup hash; active and expiry checked | No rotation policy automation or external secret store |
| Revoked/inactive handling | Revoked/inactive operators cannot authenticate | No automated deprovisioning feed |
| Tenant assignment | Required on operator creation and stored server-side | Workspace ID remains deferred |
| Role/scope boundaries | Route guards use `owner`, `grant_admin`, `auditor` | No full production RBAC/policy engine |
| Admin/operator route protection | Admin routes require admin token; operator tokens rejected | No multi-admin identity or dual-control approval |
| Fail closed | Startup and route auth fail closed where configured | Production deployment gate still no-go |
| Placeholder/default rejection | Production-like config rejects unsafe admin/bootstrap tokens | No HSM/KMS-backed secret lifecycle |
| Bootstrap token | Optional and rejected when unsafe in production-like modes | Bootstrap lifecycle still operationally manual |
| Audit coverage | Business actions are durable audit-chain events | Operator create/revoke needed durable audit-chain events |
| Rate/runtime safety | GL-208 in-process limiter and safe logging baseline | No external WAF/SIEM/SOC integration |
| Token leakage prevention | Safe responses and logs; no raw hashes returned | One-time create token remains an intentional bootstrap pattern |

---

## Implemented Hardening Summary

GL-214 implements two narrow changes:

1. Operator creation through `/admin/operators` now accepts only the existing
   route-guard roles: `owner`, `grant_admin`, and `auditor`.
2. Operator create and revoke actions now append durable audit-chain events
   with tenant-admin scope. The audit payload includes only safe identifiers and
   operational action names. It does not include raw tokens, token hashes,
   authorization headers, DSNs, private keys, credentials, or customer data.

No external identity provider, package metadata, public publish behavior,
GitHub workflow change, snapshot script change, migration, schema change, or
production deployment configuration was added.

---

## Admin Token Behavior

Admin-only operator management routes continue to require a valid
`GRANTLAYER_ADMIN_TOKEN` Bearer header. Missing credentials return a safe
`admin_token_required` response. Invalid credentials return a safe
`admin_token_invalid` response. Responses do not echo token values, header
values, or config details.

Production-like startup remains fail-closed when admin token enforcement is
disabled, the token is missing, or the token is a known placeholder/default or
too short.

## Operator Token Behavior

Operator tokens authenticate normal operator-protected routes based on role.
Operator tokens cannot create, list, get, or revoke operators through
admin-only routes. Operator list/get responses never include token hashes or
lookup hashes. Create returns a raw token once only.

## Revoked/Inactive Operator Behavior

Revoked operators are set inactive. Inactive operators are excluded by
authentication queries and cannot authenticate. Malformed expiry timestamps are
treated as expired and fail closed.

## Operator Tenant/Role/Scope Boundary

Operator tenant context is stored in the operator row and is server-derived at
request time. Request headers cannot override it. New operator roles are
constrained to `owner`, `grant_admin`, and `auditor`, matching the roles
recognized by the current route guards. This is not a full production RBAC
engine.

## Admin/Operator Route Protection

Admin/operator control-plane routes remain admin-token protected. Normal API
routes remain protected by operator role guards when the operator model is
enabled and by legacy admin-token mode when the operator model is disabled.
Health and readiness remain public.

## Audit Coverage for IAM/Operator Actions

GL-214 adds durable audit-chain events for:
- `operator_created`
- `operator_revoked`

Each event uses `subject_id="admin"`, `role="admin"`, a resource of
`operator/{operator_id}`, the operator tenant when available, and
`scope="tenant_admin"`. The event reason is generic and does not include token
material.

## Token/Secret Safety Model

Raw admin tokens, operator tokens, token hashes, lookup hashes, authorization
headers, DSNs, private keys, credentials, and config secret values are not
logged or written into audit-chain events. Auth failure responses use stable
reason codes and do not reveal token/config details.

## Fail-Closed Behavior

Missing admin credentials fail closed on admin/operator mutation routes.
Invalid admin credentials fail closed. Revoked, inactive, expired, malformed,
or unknown operator credentials fail closed. Production-like startup remains
blocked when GL-201 unsafe config checks fail.

---

## Production-Readiness Impact

GL-214 materially reduces the Production IAM / operator-control P0 blocker by
adding durable audit evidence for operator lifecycle actions and constraining
new operator roles to the current route-guard vocabulary.

Production SaaS remains no-go. Real customer/private grant/institutional data
remains no-go. Production IAM is still not complete because GrantLayer does not
yet have provider-backed identity, multi-admin governance, automated secret
lifecycle, production RBAC/policy administration, workspace enforcement, or an
external monitoring/incident response stack.

## Controlled-Preview Impact

Controlled Preview remains limited to synthetic/demo data and strict boundaries.
The GL-214 hardening improves internal operator accountability for controlled
preview use, but it does not expand the allowed data class or readiness tier.

---

## Remaining IAM Blockers

- Provider-backed identity is not implemented.
- Multi-admin governance and dual-control approval are not implemented.
- Production secret lifecycle, rotation, revocation, and storage automation are
  not complete.
- Workspace ID enforcement remains deferred.
- Tenant/workspace production guarantee remains incomplete.
- Full production RBAC/policy administration is not implemented.
- External SIEM/SOC/alerting integration is not implemented.
- Production incident runbooks and IAM break-glass procedures remain incomplete.
- Production PostgreSQL readiness remains no-go despite ephemeral validation.

---

## Risk Register

| Risk | Severity | Status | Mitigation |
|---|---:|---|---|
| Single static admin token remains | P0 | Open | Track with future production IAM work |
| Workspace enforcement deferred | P0 | Open | Track in tenant/workspace production guarantee |
| No external identity provider | P0 | Open | Defer provider integration to later explicit scope |
| No automated secret lifecycle | P0 | Open | Keep production SaaS no-go |
| Audit coverage for operator lifecycle was incomplete | P0 | Reduced | GL-214 adds durable audit-chain events |
| Arbitrary new operator roles could be created | P1 | Reduced | GL-214 constrains route-created roles |

---

## Decision

`ready_for_merge`

## Decision Rationale

GL-214 closes narrow, testable operator-control gaps without broad IAM scope.
The change preserves Developer Preview / Controlled Preview boundaries, avoids
production-readiness overclaims, keeps public publish and package behavior
untouched, and adds durable tenant-scoped audit evidence for IAM/operator
lifecycle actions.

## Findings

- Admin token behavior is fail-closed for protected admin routes and production
  config checks reject unsafe admin tokens.
- Operator authentication already rejects revoked, inactive, expired, malformed,
  and unknown tokens.
- Operator tenant context is server-derived and not caller-overridable.
- Operator lifecycle actions needed durable audit-chain events; GL-214 adds
  them safely.
- Operator creation needed alignment with the route-guard role vocabulary;
  GL-214 adds that constraint.
- Production IAM remains blocked on broader identity, secret lifecycle,
  RBAC/policy administration, and workspace guarantees.

## Safety Confirmations

- GL-214 is production IAM hardening, not a production SaaS readiness declaration.
- GrantLayer remains Developer Preview / Controlled Preview with strict boundaries.
- Controlled Preview expansion remains synthetic/demo data only.
- Production SaaS remains no-go.
- Real customer/private grant/institutional data remains no-go.
- Official SDK/package remains no-go.
- Compliance certification remains no-go.
- Ephemeral live PostgreSQL validation is not overclaimed as production PostgreSQL readiness.
- Security-sensitive reports route to GitHub Security Advisories.
- No exploit details are included.
- No real secrets are included.
- No real customer/private data is included.
- No public publish was performed.
- No public snapshot/export directory was created.
- No package publishing was performed.
- No package metadata was added.
- No GitHub workflow changes were made.
- No snapshot publish script changes were made.
- No public GitHub push, public publish, or visibility change was performed.

## Recommended Next Issues

1. GL-214 Merge if ready
2. GL-215 Tenant / Workspace Production Guarantee
3. GL-216 Production Operations Hardening Pack
