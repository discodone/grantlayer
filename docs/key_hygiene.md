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

## Non-Goals

- No Git history rewrite.
- No force push.
- No new secret manager implementation.
- No auth behavior change.
- No production SaaS claim.
