# Key Hygiene

## Scope

This document defines the key hygiene rules for the GrantLayer MVP repository.
It applies to all developers, contributors, and automated processes that interact
with the codebase.

## GL-136 Purpose

- Remove tracked demo/private key material from the active tree.
- Add a guard against future key commits.

## Rules

1. **No private keys in Git.** Private key PEM blocks, certificates, and real
   secret material must never be committed to the repository.
2. **No real secrets in docs, tests, screenshots, logs, or examples.** All
   examples must use clearly fake placeholder values.
3. **Local/generated keys must stay outside Git.** Keys generated for local
   development or testing must be placed in ignored directories or outside the
   repository.
4. **`.env.example` may contain placeholders only.** Example environment files
   must use values like `change-me-in-production`, never real credentials.
5. **Example docs must use placeholder values, not valid secrets.** Any
   documentation showing secret handling must use obviously fake data.

## Ignored Patterns

The following patterns are ignored by `.gitignore` to prevent accidental commits
of sensitive material:

- `*.pem`
- `*.key`
- `*.p8`
- `*.p12`
- `*.crt`
- `*.cert`
- `*.csr`
- `.env`
- `.env.*`
- `!.env.example`
- `secrets/`
- `private/`
- `keys/`
- `certs/`

## Developer Workflow

1. **Generate local keys outside the repo** or under an ignored path (e.g.
   `~/.grantlayer/keys/` or `./secrets/` which is ignored).
2. **Never commit generated keys.** Before committing, review `git status` and
   `git diff --cached` to ensure no key material is staged.
3. **Use environment variables or a local secret store** for secret material at
   runtime. Do not hard-code secrets in source files.

## CI/Test Gate

The test module `backend.tests.test_gl136_key_hygiene` enforces key hygiene:

- Scans tracked files for obvious private-key PEM markers.
- Validates `.gitignore` coverage.
- Validates documentation and JSON artifact presence and correctness.

Run the gate with:

```bash
python3 -m unittest backend.tests.test_gl136_key_hygiene -v
```

## Explicit Limitation

**GL-136 does not rewrite Git history.** Historical commits may still contain
key material. History cleanup requires a separate explicit decision and a
coordinated process (e.g. `git filter-repo`, BFG, or force-push) which is
outside the scope of this issue.

**GL-136 does not use force push.**

## Public GitHub Readiness

Public release remains blocked if the GL-136 gate fails. Before public release:

1. Run the GL-136 gate.
2. Run the full backend test suite.
3. Confirm no tracked files contain private key PEM markers.

## Test Credential Placeholders

Certain values that resemble credentials are intentionally present in the
repository as **non-secret test placeholders** for CI or local test
infrastructure. These are not real secrets and have never been used as
production credentials.

### grantlayer_test_password

**Location:** `.github/workflows/postgres-ci.yml`

**Decision:** Non-secret test placeholder. This value is the ephemeral
PostgreSQL password used by the CI Docker service container during automated
testing. The workflow file contains the explicit comment:
*"Ephemeral CI-only test database credential; not a production secret."*

**Rules that apply to all test credential placeholders:**

1. **No real secrets in public examples or CI fixtures.** Test credentials
   must be obviously fake (e.g. `grantlayer_test_password`, `change-me`,
   `test-token`). They must never be real passwords, API keys, or tokens
   that grant access to any live system.
2. **Do not reuse test placeholders as real credentials.** A value used as a
   CI placeholder must never be configured as a real credential in any
   environment.
3. **Users must not use real secrets or customer data in Developer Preview.**
   The Developer Preview posture does not provide the isolation guarantees
   required for real credentials or real customer data.
4. **Future tokens, passwords, and keys in examples must use obvious
   placeholders only.** Acceptable patterns: `change-me-in-production`,
   `<your-token-here>`, `example-token`, `test-token`.
5. **Real secrets require rotation and must never be committed.** If a real
   credential is accidentally committed, rotate it immediately — removing it
   from tracked files is not sufficient because it remains in git history.

**History rewrite decision:** Because `grantlayer_test_password` is a
non-secret placeholder and not a real credential, no history rewrite or
secret rotation is required. The value is documented here to confirm this
decision explicitly.

## Non-Goals

- No Git history rewrite.
- No force push.
- No new secret manager implementation.
- No auth behavior change.
- No production SaaS claim.
