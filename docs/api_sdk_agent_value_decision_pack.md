# GL-197 API/SDK/Agent Value Decision Pack

GrantLayer is an API-first Developer Preview. It is not production SaaS, and
production SaaS readiness is not claimed. Tenant isolation is not implemented.
All examples use synthetic data, placeholder token values, no real secrets, no
real customer data, and no private grants. Security-sensitive reports route to
GitHub Security Advisories.

## Decision

Decision: api_first_agent_examples_now_sdk_later.

The current public value is the local API quickstart, deterministic local
examples, and agent-readable documentation. The API is useful for Developer
Preview exploration, while SDK packaging should wait for API stability,
versioning policy, packaging infrastructure, and external reviewer demand.

## API Value

The HTTP API can be evaluated locally through the README, ten-minute quickstart,
OpenAPI file, and curl examples. It is sufficient for controlled preview
feedback. It is not a hosted production API and does not carry service-level or
production readiness claims.

Recommended follow-up: add a compact request collection or clearer API smoke
path for health, grants, demo action, audit events, and evidence verification.

## SDK Value

The repository includes a minimal local Python client wrapper under `sdk/python`
for showing API call shape. It is local only. No official SDK package is
published, no package publishing changes were made, and no official SDK package
is claimed unless verified.

Examples are examples, not a published SDK. The deterministic local examples are
standalone scripts and should remain documentation/evidence assets until the API
contract is stable.

## Agent Workflow Value

AI coding agents can use AGENTS.md, llms.txt, llms-full.txt, the first output
helper, scripts/verify-first-output.sh, and the grant lifecycle evidence bundle.
The agent path is valuable today because it produces repeatable evidence without
requiring hosted infrastructure or real data.

Future value: an agent-to-API example can show health, grant creation, demo
action, audit lookup, and structured report generation using placeholder values.

## Packaging Boundaries

Current examples remain examples and docs. The local Python client remains a
local wrapper. No PyPI package, official SDK release, backend runtime package,
frontend surface, workflow, OpenAPI contract change, migration, dependency
manifest change, or backend/src implementation change is part of GL-197.

## Findings

- API docs need a compact request collection for common paths.
- README wording should avoid implying a published SDK package.
- llms.txt needs a current next-steps refresh.
- A future agent-to-API integration example would strengthen the story.
- A hosted API viewer is not required for Developer Preview, but would reduce
  first-time friction later.

## Recommended Next Issues

- GL-198: Controlled Preview Boundary Pack.
- GL-199: Production Readiness Gap Report v2.

## Safety Confirmations

- no_github_push_performed: confirmed
- no_visibility_change_performed: confirmed
- internal_repo_not_pushed_directly_to_github: confirmed
- no_backend_src_changes: confirmed
- no_openapi_changes: confirmed
- no_sdk_implementation_changes: confirmed
- no_package_publishing_changes: confirmed
- no_production_saas_claim: confirmed
- tenant_isolation_not_claimed: confirmed
