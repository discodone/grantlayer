# GL-177 Public Repo Smoke Verification

Public repository: https://github.com/Discodone/grantlayer.git

Expected public commit: e4cd080df9d8da7d7cf4044e84eea4df8ac80cc6

Previous public commit: 8bf6c335af4f1229dd752e939ec5b0e5a6928bad

Fresh clone path: `/tmp/grantlayer-public-smoke-gl177`

## Smoke Decision

`public_repo_smoke_passed_with_cautions`

## First Verifiable Output

`first_verifiable_output` was run from the fresh public clone and matched the
committed deterministic reference output.

## Private Data Smoke

Private data and secret smoke checks found no blockers. The scan covered
credential-like material, private keys, raw tokens, private contact data,
customer data, internal infrastructure references, and direct-publish
instructions.

## Findings

| ID | Severity | Status | Summary |
|----|----------|--------|---------|
| F-001 | medium | open | Public status wording needs post-public cleanup. |
| F-002 | high | open | Security reporting channel needs public-ready wording. |

## Explicit Confirmations

No GitHub push performed.

No visibility change performed.

Internal repo was not pushed directly to GitHub.

No backend/src, OpenAPI, migration, dependency, SDK implementation, GitHub
workflow, frontend, website, or design changes.

The smoke report does not claim production SaaS readiness.
