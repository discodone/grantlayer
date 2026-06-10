# GrantLayer Production Readiness Cut

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Decision

| Milestone | Status |
|-----------|--------|
| Integration-Ready | **Yes** |
| Pilot-Ready | **Yes, with non-production constraints** |
| Production-Ready | **No** |

This decision (GL-063) is a readiness cut that separates Pilot-Ready status from Production-Ready requirements. It records what is already in place, what is still missing, and what must be done before production deployment can be considered.

## 2. Basis

The following prior blocks constitute the basis for this decision:

- **GL-052 Product Core E2E Flow Test**
- **GL-053 Minimum Viable Integration Guide**
- **GL-054 Integration Demo Pack**
- **GL-055 Integration Contract & Readiness Gate**
- **GL-056 Integration-Ready Release Candidate Review**
- **GL-057 Integrator Quickstart Examples**
- **GL-058 Minimal API Usage Walkthrough**
- **GL-059 Pilot-Ready Handoff Plan**
- **GL-060 Pilot-Ready Release Decision**
- **GL-061 Demo Runner / API Smoke Script**
- **GL-062 Pilot Partner Preparation Pack**

These artifacts prove the Product Core flow, provide integration guidance, and support first technical pilot discussions. They do not prove production readiness.

## 3. Production blockers

The following P0 blockers prevent any production deployment claim:

1. **Production auth is not implemented** — no OAuth, JWT, SSO, or HSM-backed key management.
2. **Production secrets are not managed** — demo Ed25519 keypair and synthetic data remain in the repository.
3. **Deployment hardening is not specified** — no containers, load balancing, TLS termination, or orchestration guidance.
4. **Observability is not implemented** — no metrics, logging pipelines, alerting, or tracing.
5. **Backup/restore is not defined** — no automated backup, point-in-time recovery, or disaster runbooks.
6. **PostgreSQL CI is not established** — SQLite is the default; PostgreSQL support exists but is not CI-gated.
7. **OpenAPI contract freeze process is not defined** — versioning and breaking-change policy are not documented.
8. **Data privacy and evidence-handling boundaries are not defined** — no data-classification matrix or retention policy.

## 4. Pilot-permitted scope

A pilot partner may do the following without implying production readiness:

- **Review docs** — read integration guide, demo scenario, walkthroughs, and checklists.
- **Run dry-run demo smoke script** — execute `python3 scripts/demo/gl061_api_smoke.py --dry-run` for local confidence.
- **Inspect examples** — examine static JSON examples in `docs/examples/gl057/` and `docs/examples/gl058/`.
- **Run backend tests** — execute the full backend suite with expected zero failures and zero errors.
- **Map partner workflow** — translate an internal grant or funding process into GrantLayer stages.
- **Identify production requirements** — produce a ranked list of what production operation would require.

A pilot partner must **not**:
- Process production or sensitive data through the current codebase.
- Deploy the current codebase to a production environment.
- Assume production auth, observability, backup, or compliance guarantees exist.

## 5. Production claim stop conditions

Do not claim or imply Production-Ready status if any of the following are true:

- The full backend suite is failing.
- Contract/readiness validation is failing.
- Production auth is missing.
- Production secrets are missing.
- Deployment hardening is missing.
- Backup/restore is missing.
- Observability is missing.
- The compliance/legal boundary is unclear.
- Production readiness is being claimed accidentally or implicitly.

If any of these conditions are present, pause and reference this readiness cut before proceeding.

## 6. Next recommended block

The default next block after GL-063 is one of the following, depending on whether the next priority is contract clarity or executable validation:

1. **API/OpenAPI Contract Hardening Review** — tighten the OpenAPI specification, define versioning, and resolve contract ambiguities.
2. **Local API Smoke v2** — extend the GL-061 demo runner to exercise more paths and produce a machine-readable confidence report.

Rationale:
- Both options build on the existing Pilot-Ready foundation without jumping to production infrastructure.
- Contract hardening reduces integration risk for the next pilot partner.
- Smoke v2 gives partners a more practical onboarding path than static JSON alone.

---

## See also

- [`docs/api_openapi_contract_hardening_review.md`](api_openapi_contract_hardening_review.md) — GL-064 API/OpenAPI contract hardening review
- [`docs/production_hardening_roadmap.md`](production_hardening_roadmap.md) — GL-063 production-hardening roadmap with prioritized workstreams
- [`docs/pilot_ready_release_decision.md`](pilot_ready_release_decision.md) — GL-060 pilot-ready release decision
- [`docs/pilot_partner_preparation_pack.md`](pilot_partner_preparation_pack.md) — GL-062 pilot partner preparation pack
- [`docs/pilot_ready_handoff_plan.md`](pilot_ready_handoff_plan.md) — GL-059 pilot-ready handoff plan
- [`docs/examples/gl063/production_hardening_backlog.json`](examples/gl063/production_hardening_backlog.json) — machine-readable production hardening backlog
- [`docs/examples/gl063/production_readiness_cut.json`](examples/gl063/production_readiness_cut.json) — machine-readable production readiness cut
- [`backend/tests/test_gl063_production_hardening_roadmap.py`](../backend/tests/test_gl063_production_hardening_roadmap.py) — validation test for this readiness cut and roadmap
