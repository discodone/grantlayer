# GrantLayer Production Auth and Operator Access Design

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose

This document defines the auth and operator access model for GrantLayer as a **reusable, adaptable API-first product core**.

It clarifies:
- which operator/admin access concepts belong to the Product Core boundary
- which authentication providers should remain replaceable adapters
- which roles and permissions need stable product semantics
- which local/test/demo auth shortcuts are acceptable outside production
- which production auth requirements must be explicit before production use
- which later implementation blocks should build auth runtime behavior

This is a **product-foundation security design document**. It does not implement authentication code.

## 2. Product auth principle

GrantLayer should keep **stable operator role semantics** in the Product Core while keeping **concrete auth providers replaceable**.

The Product Core owns the operator role definitions, capability boundaries, and audit expectations. The Product Core does not depend on one specific auth provider. OAuth, JWT, SSO, and mTLS should remain pluggable adapter boundaries.

Local, test, and demo auth shortcuts must **not accidentally become production behavior**. Any runtime mode that permits shortcut auth must explicitly declare that it is not production-ready.

## 3. Runtime-mode auth expectations

### 3.1 local-dev

- **Auth expectation**: developer convenience; simplified or bypassed authentication acceptable
- **Allowed shortcut**: deterministic local admin token, no external identity provider, no role enforcement
- **Audit expectation**: minimal; operator actions may be attributed to a generic local-dev identity
- **Production claim boundary**: **must not** be described as production-ready

### 3.2 test

- **Auth expectation**: deterministic automated verification; mock or bypassed authentication acceptable
- **Allowed shortcut**: fixture-based operator identities, synthetic role assignments, mock auth provider
- **Audit expectation**: none required; test identities are synthetic and isolated from production data
- **Production claim boundary**: **must not** be described as production-ready

### 3.3 demo

- **Auth expectation**: illustrative non-production walkthrough; simplified auth acceptable
- **Allowed shortcut**: demo operator identity, demo tokens, no external identity provider
- **Audit expectation**: minimal; demo actions must be clearly labeled as synthetic
- **Production claim boundary**: **must not** be described as production-ready; explicitly labeled as demonstration only

### 3.4 integration

- **Auth expectation**: controlled external technical integration; partner-agreed authentication
- **Allowed shortcut**: partner-agreed auth provider with documented constraints
- **Audit expectation**: partner-agreed; operator actions should be attributable where possible
- **Production claim boundary**: **must not** be described as production-ready without explicit partner agreement and documented constraints

### 3.5 staging

- **Auth expectation**: production-like validation; same auth target as production
- **Allowed shortcut**: same backend and auth as production target; realistic but synthetic data
- **Audit expectation**: full audit trail to validate production behavior
- **Production claim boundary**: **must not** be described as production-ready; explicitly labeled as pre-production validation

### 3.6 production

- **Auth expectation**: explicit hardened operation only
- **Allowed shortcut**: **none** — every required auth configuration must be explicit, validated, and fail-closed if missing
- **Audit expectation**: full; all operator-sensitive actions must produce auditable records
- **Production claim boundary**: may be described as production-ready **only** when all required auth configuration is explicit, validated, and monitored

## 4. Stable operator roles

The following operator roles are defined as stable Product Core semantics. Auth provider adapters must map their identity claims into these roles.

### 4.1 system_admin

- **Purpose**: ultimate system-level access for installation, bootstrap, and emergency recovery
- **Core responsibilities**: system configuration administration, operator bootstrap, role assignment, fail-closed override in documented emergencies

### 4.2 grant_admin

- **Purpose**: grant request and approval administration
- **Core responsibilities**: grant request administration, grant approval operations, grant creation and lifecycle operations

### 4.3 evidence_operator

- **Purpose**: evidence bundle and verification management
- **Core responsibilities**: evidence write operations, evidence verification operations

### 4.4 policy_admin

- **Purpose**: policy and rule pack administration
- **Core responsibilities**: policy/rule pack administration, permission profile administration

### 4.5 auditor

- **Purpose**: institutional audit and compliance review
- **Core responsibilities**: auditor report/export access, compliance readiness review

### 4.6 readonly_integrator

- **Purpose**: read-only integration access for external systems
- **Core responsibilities**: readonly integration access, safe read-only queries without mutation rights

### 4.7 external_workflow_agent

- **Purpose**: service-to-service workflow execution by external agents
- **Core responsibilities**: service-to-service workflow execution, attributable action records linked to a stable operator or service identity

### 4.8 service_operator

- **Purpose**: internal service-to-service operations and maintenance
- **Core responsibilities**: service-to-service workflow execution, system health and maintenance operations

## 5. Capability boundaries

The following capability groups define what actions each role may perform. Auth provider adapters must map provider-specific claims into these stable capability groups.

### 5.1 Grant request administration

- Review, approve, reject, and manage grant requests
- Link requests to subjects, scopes, and time bounds

### 5.2 Grant approval operations

- Execute approval decisions with required signatures
- Enforce multi-step and quorum approval policies

### 5.3 Grant creation and lifecycle operations

- Create, update, revoke, and expire grants
- Manage grant execution records

### 5.4 Evidence write operations

- Create, append, and finalize evidence bundles
- Link evidence to grants, requests, and executions

### 5.5 Evidence verification operations

- Recompute and compare evidence hashes
- Flag tampering, corruption, or completeness gaps

### 5.6 Policy/rule pack administration

- Load, validate, and activate policy rule packs
- Manage exclusions, deadlines, amount limits, and required roles

### 5.7 Permission profile administration

- Define and assign permission profiles
- Manage scope templates and role hierarchies

### 5.8 Auditor report/export access

- Export structured auditor records
- Review compliance readiness summaries and gap reports

### 5.9 Compliance readiness review

- Access compliance readiness outputs
- Review but not mutate readiness dimensions

### 5.10 System configuration administration

- Configure runtime settings, feature flags, and extension toggles
- Manage system-level parameters with documented override procedures

### 5.11 Readonly integration access

- Query grants, requests, evidence, and audit records
- No mutation rights; no approval or revocation access

### 5.12 Service-to-service workflow execution

- Execute workflow steps between services
- Produce attributable action records with stable service identity

## 6. Auth provider adapter boundary

The Product Core should **not** depend on one specific auth provider. The following boundary rules apply:

- **Product Core should not depend on one specific auth provider** — the core owns roles and capabilities, not provider-specific fields
- **OAuth/JWT/SSO can be future provider adapters** — any of these may be implemented as adapter layers that map into stable GrantLayer roles
- **Local/demo tokens are non-production shortcuts only** — they are acceptable in local-dev, test, and demo modes but must not persist into production
- **Production must use explicit provider configuration** — the active auth provider must be declared, validated, and fail-closed if missing
- **Provider claims should map into stable GrantLayer roles/capabilities** — adapters translate provider-specific group memberships, scopes, or roles into the stable operator roles defined in this document
- **Provider-specific fields should not leak into Product Core records** — audit records and evidence bundles should reference stable operator IDs and roles, not raw provider tokens, JWTs, or OAuth fields

## 7. Production fail-closed rules

Production mode must enforce the following fail-closed behavior:

- **Production mode must not start with demo/default admin token** — if the only configured auth is a demo token, startup must fail
- **Production mode must not silently allow unauthenticated access** — every protected endpoint must require valid authentication
- **Production mode must require explicit auth provider configuration** — the auth mechanism, endpoints, and validation rules must be declared
- **Production mode must require explicit operator/admin bootstrap configuration** — at least one valid operator must be bootstrapped with explicit role assignment
- **Production mode must fail closed if required auth config is missing** — the system must refuse to start rather than assume a safe default
- **Denied access should be auditable where appropriate** — failed authentication and authorization attempts should produce audit records when feasible

## 8. Audit and provenance expectations

Operator-sensitive actions should produce auditable records. The following events must be traceable:

- **Grant approval** — who approved, when, under what policy, and with what evidence
- **Evidence mutation** — who wrote, modified, or finalized evidence bundles
- **Policy changes** — who loaded, activated, or modified rule packs
- **Permission changes** — who assigned, revoked, or modified permission profiles and role assignments
- **Auditor export access** — who exported audit records and when

Audit records must **not contain secrets** — no plaintext tokens, JWTs, passwords, or private keys should appear in audit logs or provenance summaries.

External workflow agent actions should be attributable to a **stable operator/service identity** — not anonymous or untraceable.

## 9. Local/test/demo shortcuts

The following auth shortcuts are acceptable **only outside production**:

- **Deterministic test identity** — synthetic operator IDs used in automated tests
- **Local admin token for developer convenience** — a simple shared token for local-dev environments
- **Demo operator identity** — a preconfigured operator for walkthroughs and stakeholder demos
- **Fixture-based service identity** — synthetic service accounts loaded from test fixtures
- **Readonly demo access** — a preconfigured readonly account for demo integration queries

These shortcuts are **not valid production behavior**. Production must replace all shortcuts with explicit auth provider configuration, role mapping, and operator bootstrap.

## 10. Future implementation expectations

The following implementation blocks should be built after this planning document is accepted:

1. **Auth configuration schema** — a validated schema that declares the active auth provider, role mapping, and capability assignments
2. **Runtime-mode auth validation** — startup checks that enforce the auth expectations defined for each runtime mode
3. **Production fail-closed startup checks** — explicit checks that refuse to start in production mode if required auth configuration is missing
4. **Role/capability mapping helper** — a utility that translates provider claims into stable GrantLayer roles and capabilities
5. **Auth provider adapter interface** — a defined boundary that auth provider adapters must implement to integrate with the Product Core
6. **Operator bootstrap mechanism** — a secure process for creating the first operator/admin in a fresh production deployment
7. **Service-to-service access model** — how internal and external services authenticate and authorize workflow steps
8. **Auth audit event integration** — how authentication and authorization events feed into the audit event stream
9. **OpenAPI security contract update** — how auth requirements are documented in the OpenAPI contract (security schemes, scopes, and protected paths)
10. **Integration tests for auth gates** — tests that verify protected endpoints reject unauthenticated and unauthorized requests in production-like modes

## 11. What not to implement yet

This block does **not** implement:

- OAuth
- JWT validation
- SSO
- Session management
- Password login
- User management UI
- Production secret store
- Multi-tenant identity
- Dashboard access control
- Provider-specific integration

These remain valid future workstreams but must be scoped in separate issues.

## 12. Decision boundary

GrantLayer should **not** claim production auth readiness until auth provider configuration, operator bootstrap, role/capability mapping, fail-closed startup checks, and audit expectations are implemented and verified.

Any statement to external partners, documentation, or marketing materials must include the non-production constraint. If a partner asks about production timelines, reference this document, the GL-066 runtime configuration environment model, the GL-065 product architecture and extension boundaries, the GL-063 production-hardening roadmap, and the GL-064 API/OpenAPI contract hardening review.

---

## See also

- [`docs/runtime_configuration_environment_model.md`](runtime_configuration_environment_model.md) — GL-066 runtime configuration and environment model
- [`docs/product_architecture_extension_boundaries.md`](product_architecture_extension_boundaries.md) — GL-065 product architecture and extension boundaries
- [`docs/production_hardening_roadmap.md`](production_hardening_roadmap.md) — GL-063 production-hardening roadmap
- [`docs/api_openapi_contract_hardening_review.md`](api_openapi_contract_hardening_review.md) — GL-064 API/OpenAPI contract hardening review
- [`docs/examples/gl067/auth_operator_role_matrix.json`](examples/gl067/auth_operator_role_matrix.json) — machine-readable auth operator role matrix
- [`docs/examples/gl067/operator_access_boundary_catalog.json`](examples/gl067/operator_access_boundary_catalog.json) — machine-readable operator access boundary catalog
- [`backend/tests/test_gl067_production_auth_operator_access_design.py`](../backend/tests/test_gl067_production_auth_operator_access_design.py) — validation test for this auth and operator access design
