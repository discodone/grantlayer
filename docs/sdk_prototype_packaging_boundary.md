# GL-203C — SDK Prototype / Packaging Boundary

**Issue ID:** GL-203C
**Branch:** `gl-203c-sdk-prototype-packaging-boundary`
**Status:** Internal / Developer Preview

---

## Context

GL-200A, GL-200B, GL-200C, GL-201, GL-202, GL-203, and GL-203B are merged
internally. GL-203B cleaned the OpenAPI contract (`docs/openapi.yaml` version
`0.203b.0-developer-preview`) and concluded it was suitable as a basis for
SDK prototype work.

GL-203C is a prototype and packaging boundary decision issue. It creates a
minimal internal Python SDK prototype, defines the packaging boundary, and
documents what is and is not allowed for SDK work at this stage.

**GrantLayer remains:**
- Developer Preview / Controlled Preview with strict boundaries
- Not production SaaS
- Not ready for real customer data, private grant data, or institutional data
- Tenant/workspace isolation baseline implemented but not production-complete
- No official SDK/package is claimed or published

Security-sensitive reports route to GitHub Security Advisories. No exploit
details are included. No real secrets are included.

---

## Scope

GL-203C covers:
- SDK feasibility assessment against the GL-203B cleaned OpenAPI contract
- OpenAPI dependency assessment for SDK work
- Internal prototype boundary definition
- Packaging boundary definition (what is forbidden vs. allowed now)
- A minimal Python SDK prototype at `examples/sdk_prototype/python/` (internal only)
- Token/secret safety model documentation
- Tenant/workspace SDK boundary documentation
- Public claim boundary documentation
- Contract tests for the prototype and boundary decisions

## Non-Goals

GL-203C is not:
- An official SDK release
- Package publishing (no PyPI, npm, or any registry)
- Production SaaS readiness declaration
- Public publish, GitHub push, or visibility change
- Backend/src changes or API behavior changes
- Migration or DB/schema changes
- Dependency changes
- setup.py, pyproject.toml (for SDK), package.json, npm metadata, or release workflows
- Enterprise SDK or production-ready SDK
- Semantic versioned package commitment
- Complete tenant/workspace isolation (deferred)

---

## Input Sources Reviewed

| Source | Reviewed |
|--------|----------|
| docs/openapi_api_contract_cleanup.md | Yes |
| docs/examples/gl203b/openapi_api_contract_cleanup.json | Yes |
| docs/openapi.yaml | Yes |
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
| docs/production_readiness_gap_report_v2.md | Yes |
| docs/examples/gl199/production_readiness_gap_report_v2.json | Yes |
| docs/controlled_preview_boundary_pack.md | Yes |
| docs/examples/gl198/controlled_preview_boundary_pack.json | Yes |
| README.md | Yes |
| SECURITY.md | Yes |
| AGENTS.md | Yes |
| llms.txt | Yes |
| llms-full.txt | Yes |
| sdk/python/grantlayer_client.py | Yes (existing, for comparison) |
| sdk/python/README.md | Yes |
| backend/src/server.py | Yes (boundary review only) |
| backend/src/auth.py | Yes (token safety review only) |

---

## SDK Feasibility Assessment

### OpenAPI contract quality (post GL-203B)

| Dimension | Assessment |
|---|---|
| Endpoint coverage | 36 documented paths; all major operational endpoints present |
| Public/protected distinction | Clear: GET /health, GET /readiness, GET / have no security requirement |
| Auth model clarity | Two schemes (LegacyAdminToken, OperatorToken) are explicit and documented |
| Tenant context model | Server-derived from auth; documented in info description and security schemes |
| Error response shape | Consistent GL-030 additive shape `{error, errorCode, reason}` across all 4xx/5xx |
| Schema completeness | All referenced schemas now defined (ComplianceReadinessSummary added in GL-203B) |
| Backward compat fields | Grant dual snake_case/camelCase fields documented explicitly |
| workspace_id | Reserved/nullable/deferred — documented; SDK does not need to handle it |
| X-Correlation-ID | Documented; SDK may optionally send it |

**Verdict: FEASIBLE.** The cleaned OpenAPI is sufficient for a well-scoped SDK prototype.

### Existing SDK baseline

`sdk/python/grantlayer_client.py` (GL-147, 114 lines) is functional but:
- Uses urllib directly with no injectable transport (network always required for tests)
- Does not have `__repr__` token exclusion explicitly enforced
- Covers health, readiness, and generic `request_json()` only
- Has stale caveat: "Tenant isolation is not implemented" (should now say "baseline implemented, not production-complete")
- Does not cover the post-GL-200 endpoints (grant requests, executions, evidence)

The GL-203C prototype improves on all these dimensions. It does not replace or deprecate `sdk/python/grantlayer_client.py` — both coexist as developer evaluation resources.

### SDK-readiness gaps remaining

| Gap | Impact | Action |
|---|---|---|
| workspace_id not enforced | SDK may need future workspace parameter | Document as reserved/deferred |
| Admin-plane isolation (GL-200D) deferred | Multi-tenant operator management unsafe | Do not expose tenant management in SDK |
| PostgreSQL not live-validated | Deployment constraint | SDK is storage-agnostic; gap is server-side |
| Stale "not implemented" claim in public docs | Documentation accuracy | Deferred per GL-203B (requires test coordination) |
| No semantic versioning commitment | SDK version stability | Explicitly deferred; no semver claim made |

---

## OpenAPI Dependency Assessment

The GL-203C prototype depends on the following from `docs/openapi.yaml`:
1. **Security schemes**: `LegacyAdminToken` and `OperatorToken` — both implemented as `Authorization: Bearer <token>` header
2. **Public endpoints**: `/health`, `/readiness` — no auth
3. **Protected endpoints**: All require bearer token; operator-only endpoints return 404 when operator model disabled
4. **Error contract**: `{error, errorCode, reason}` GL-030 shape — prototype parses `errorCode` and `error`
5. **Tenant context**: Server-derived; prototype sends NO tenant override header
6. **Request bodies**: JSON with `Content-Type: application/json`
7. **Response format**: JSON throughout

**Assessment**: The prototype correctly implements the OpenAPI contract. No OpenAPI changes are required for GL-203C. The prototype follows the documented auth, tenant, and error contract precisely.

---

## Prototype Boundary

### What the GL-203C prototype IS

- An experimental, internal-only Python source file at
  `examples/sdk_prototype/python/grantlayer_client.py`
- A feasibility demonstration against the cleaned OpenAPI contract
- 100% Python standard library (urllib.request, json)
- Has injectable/mockable transport (`FakeTransport`) for deterministic tests
  without any network dependency
- Covers 20 endpoint methods across grants, audit, challenges, operator,
  grant requests, executions, evidence, and agent permissions
- Token is never included in `__repr__`, error messages, or logged anywhere
- No tenant override header is supported or emitted
- No hardcoded production endpoints or tokens
- Auth header added only when token is explicitly supplied by the caller
- Developer Preview caveats in module docstring

### What the GL-203C prototype IS NOT

- Not an official SDK
- Not package-published (no pip install path)
- Not a version-committed release
- Not production-ready
- Not replacing `sdk/python/grantlayer_client.py`
- Not usable with real customer data
- Not usable with real secrets
- Not for shared/production deployment

---

## Packaging Boundary

### Explicitly FORBIDDEN for now

| Item | Reason |
|---|---|
| PyPI publication | No package metadata, no production-ready contract commitment |
| npm publication | Not a JavaScript SDK; no Node.js dependency |
| Official SDK claim | No semantic versioning, no support SLA, no production contract |
| setup.py | Not created; would imply installable package |
| pyproject.toml (SDK) | Not created; would imply build/publish pipeline |
| package.json | Not created; not a Node.js SDK |
| Release workflow (.github/workflows/publish*) | Not created; no public publish |
| Generated SDK (OpenAPI codegen) | Not explored; requires separate decision |
| Semantic version tag for SDK | Not made; no version commitment |
| Enterprise/production SDK claim | Not applicable at Developer Preview |
| Breaking-change-free guarantee | Not made; prototype only |

### Explicitly ALLOWED now

| Item | Status |
|---|---|
| Internal prototype source file | Created: `examples/sdk_prototype/python/grantlayer_client.py` |
| Prototype README with caveats | Created: `examples/sdk_prototype/python/README.md` |
| Deterministic tests (no network) | Created in test file via `FakeTransport` |
| Documentation of packaging boundary | This document |
| Future GL issue for SDK packaging | Recommended: GL-203D or GL-205 level |
| Claiming "internal prototype for evaluation" | Yes, with clear caveats |
| Claiming "examples-first approach" | Yes |
| Claiming "API-first Developer Preview" | Yes |

---

## Prototype Implementation Summary

**File**: `examples/sdk_prototype/python/grantlayer_client.py`
**Lines**: ~270
**Language**: Python 3.10+
**Dependencies**: stdlib only (urllib.request, json)

### Classes

| Class | Purpose |
|---|---|
| `GrantLayerClientError` | Base exception |
| `GrantLayerHTTPError` | Non-2xx response; `.status` and `.error_code` |
| `GrantLayerJSONError` | Non-JSON response body |
| `GrantLayerConnectionError` | Network-level failure |
| `GrantLayerResponse` | Parsed response: `.status`, `.body`, `.headers`, `.correlation_id` |
| `FakeTransport` | Injectable fake for tests; `.add_response()`, `.calls` |
| `GrantLayerClient` | Main client; injectable `_transport` parameter |

### Endpoint methods (20 total)

| Method | HTTP | Path |
|---|---|---|
| `health()` | GET | /health (public) |
| `readiness()` | GET | /readiness (public) |
| `list_grants()` | GET | /grants |
| `get_grant(id)` | GET | /grants/{id} |
| `create_grant(...)` | POST | /grants |
| `revoke_grant(id, ...)` | POST | /grants/{id}/revoke |
| `list_audit_events(limit)` | GET | /audit-events |
| `list_challenges()` | GET | /challenges |
| `create_challenge(...)` | POST | /challenges |
| `get_operator_me()` | GET | /operators/me |
| `list_grant_requests(status)` | GET | /grant-requests |
| `get_grant_request(id)` | GET | /grant-requests/{id} |
| `create_grant_request(...)` | POST | /grant-requests |
| `approve_grant_request(id)` | POST | /grant-requests/{id}/approve |
| `deny_grant_request(id, reason)` | POST | /grant-requests/{id}/deny |
| `list_grant_executions(...)` | GET | /grant-executions |
| `get_grant_execution(id)` | GET | /grant-executions/{id} |
| `list_executions_for_grant(id)` | GET | /grants/{id}/executions |
| `get_evidence_bundle(id)` | GET | /evidence/executions/{id} |
| `verify_evidence_bundle(id)` | GET | /evidence/executions/{id}/verify |
| `list_agent_permission_profiles()` | GET | /agent-permissions/profiles |
| `get_agent_permission_profile(name)` | GET | /agent-permissions/profiles/{name} |
| `evaluate_agent_permission(...)` | POST | /agent-permissions/evaluate |
| `request(method, path, ...)` | Any | Generic escape hatch |

---

## Token/Secret Safety Model

| Property | Behavior |
|---|---|
| Token storage | Private attribute `_token`; never public |
| Token in `repr(client)` | `has_token=True/False` only — token value excluded |
| Token in error messages | Never — only HTTP status and `errorCode` from server |
| Token in logs | Never — client does not log; caller is responsible for not logging |
| Token transmission | Only in `Authorization: Bearer <token>` header, over the caller's network |
| Token on public endpoints | Not sent — auth header skipped when `_token is None` |
| Placeholder tokens in tests | Used — clearly marked as non-production synthetic identifiers |
| Real tokens in test files | None — all tests use `FakeTransport`, no network |
| Token in `GrantLayerHTTPError` | Not included — only `status`, `error_code`, `error_message` |

---

## Tenant/Workspace SDK Boundary

| Aspect | SDK Behavior |
|---|---|
| Tenant context | Server-derived from authentication — NOT a client-supplied parameter |
| Tenant override header | NOT supported — no X-Tenant-ID or similar is sent |
| workspace_id | Not exposed as a client parameter — reserved/deferred server-side |
| Cross-tenant isolation | Enforced server-side; SDK sees 404/empty list for cross-tenant access |
| Operator tenant context | Derived from operator record server-side; SDK only supplies the auth token |
| Admin-token tenant context | Bound to "demo" server-side; SDK is unaware of this binding |
| Multi-tenant SDK support | Not claimed — tenant isolation is not production-complete |

---

## Public Claim Boundary

### ALLOWED claims

1. **Developer Preview / Controlled Preview** — local evaluation and controlled pilot posture.
2. **API-first** — REST/HTTP API; no SDK required to integrate.
3. **Internal SDK prototype for evaluation** — GL-203C explores packaging feasibility.
4. **Examples-first approach** — examples and prototype source, no package installation.
5. **No official SDK yet** — prototype is not an official or published SDK.
6. **SDK packaging under evaluation** — future issue will decide experimental public SDK timeline.

### PROHIBITED claims

1. **Official SDK available** — not true; no published package.
2. **Installable production package** — not true; no pip/npm install.
3. **Production-ready SDK** — not true; prototype only.
4. **Real customer data readiness** — not true; synthetic identifiers only.
5. **Private grant/institutional data readiness** — not true.
6. **Production SaaS readiness** — not true.
7. **Complete tenant/workspace production guarantee** — not true; workspace not enforced.
8. **Enterprise SDK** — not true.
9. **Semantic versioned stable SDK** — not true; no version commitment.
10. **Breaking-change-free SDK API** — not true; prototype may change.

---

## Tests Added

- `backend/tests/test_gl203c_sdk_prototype_packaging_boundary.py`
- Covers: doc existence, JSON artifact validity, safety confirmations, packaging boundary,
  prohibited claims, prototype import, prototype token safety, FakeTransport usage,
  no network in tests, auth header control, tenant override header absence, scope guard.

---

## Remaining Gaps

1. **Stale tenant isolation claim** in AGENTS.md, llms.txt, llms-full.txt, README.md,
   SECURITY.md — deferred per GL-203B (requires coordinated test changes).
2. **workspace_id enforcement** not implemented — SDK reflects deferred status.
3. **Admin-plane tenant isolation (GL-200D)** deferred — SDK does not expose tenant
   management endpoints.
4. **PostgreSQL live validation** blocked until GL-204.
5. **Package publishing pipeline** not established — not within GL-203C scope.
6. **Generated SDK (OpenAPI codegen)** not explored — separate decision required.
7. **Semantic versioning commitment** not made — deferred to official SDK decision.
8. **Existing sdk/python/ stale caveat** — `sdk/python/README.md` still says
   "Tenant isolation is not implemented" — updating requires coordinated test changes.

---

## Production Readiness Impact

GL-203C is a prototype and packaging boundary issue. It does not change
production readiness.

| Area | Status |
|---|---|
| API contract | GL-203B aligned; SDK prototype follows aligned contract |
| Auth/secrets/config | Hardened (GL-201); prototype inherits safe design |
| Persistence/migration | SQLite ready for Developer Preview; PostgreSQL not live-validated |
| Tenant/workspace isolation | Baseline implemented; not production-complete |
| SDK/package | Prototype created (internal); not published; not official |
| Public claims | Bounded by controlled preview; prototype clearly experimental |
| Follow-up needed | GL-204 (production ops), optional GL-203D (SDK packaging) |

GrantLayer **remains** Developer Preview / Controlled Preview with strict boundaries.

---

## Decision

**dispose: ready_for_merge**

**Decision: SDK prototype is feasible and safe. Internal prototype created.
Packaging boundary defined. Proceed to GL-204 (Production Ops / Go-No-Go v3)
as the next required issue. GL-203D (public SDK packaging) may follow
GL-204 if production ops gate passes.**

---

## Decision Rationale

1. The GL-203B cleaned OpenAPI contract provides sufficient documentation
   for an SDK prototype. All 36 endpoints are documented with auth requirements,
   error shapes, and schema definitions.
2. A minimal Python prototype with injectable transport is safe to create:
   stdlib only, no external deps, no hardcoded URLs/tokens, token never in repr/errors.
3. The prototype demonstrates that the auth model (two bearer token schemes),
   tenant context model (server-derived), and error contract are all
   representable with a clean client interface.
4. No package publishing metadata is created. No official SDK is claimed.
5. Remaining blockers (workspace enforcement, admin-plane isolation, PostgreSQL
   validation) are server-side concerns that do not block SDK prototype exploration.
6. GL-204 (production ops) is the critical next step before any external pilot.
7. An experimental public SDK (GL-203D equivalent) should only proceed after
   GL-204 validates the production path.

---

## Safety Confirmations

- No production SaaS readiness claim made.
- Tenant/workspace isolation not overclaimed as production-complete.
- No real customer/private grant data readiness claimed.
- Security-sensitive reports route to GitHub Security Advisories (per SECURITY.md).
- No exploit details included in this document, tests, or prototype.
- No real secrets included anywhere.
- No official SDK/package claimed or published.
- No package publishing metadata created (no setup.py, pyproject.toml, package.json).
- No backend/src changes.
- No API behavior changes.
- No migrations/DB/schema changes.
- No dependency changes.
- No frontend/website/design changes.
- No GitHub workflow changes.
- No public publish or visibility change.
- No force push.
- No Paperclip references or status updates.
- Unrelated pre-existing website untracked files (`docs/website_design_workspace_import_report.md`,
  `website-design/`) excluded from GL-203C.

---

## Recommended Next Issues

- **GL-203C Merge** — merge `gl-203c-sdk-prototype-packaging-boundary` to internal main after validation.
- **GL-204 — Production Ops / Go-No-Go v3** — live PostgreSQL validation, backup/restore minimum drill,
  observability baseline, go/no-go decision for first external controlled pilot. **Required before
  any external pilot or public SDK release.**
- **GL-203D — Experimental Public SDK / Packaging (conditional)** — only after GL-204 passes;
  design packaging pipeline, semantic versioning, and experimental public release. Do not proceed
  before GL-204.
