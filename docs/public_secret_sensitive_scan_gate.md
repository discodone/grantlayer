# Public Secret / Sensitive Data Scan Gate

## Purpose

`scripts/public-secret-sensitive-scan.sh` is a local heuristic pre-publication scan gate that checks tracked files for obvious secrets, sensitive data, internal hostnames/paths, and public-readiness overclaims.

It is designed to catch the most common accidental exposures before a public GitHub release. It does **not** perform a deep forensic audit of full git history — that is handled separately in GL-158 Git History Exposure Review / Public Snapshot Decision.

---

## How to Run

Default scan (tracked files, heuristic mode):

```bash
scripts/public-secret-sensitive-scan.sh
```

Strict mode (reserved for future stricter ruleset, currently same as default):

```bash
scripts/public-secret-sensitive-scan.sh --strict
```

Help:

```bash
scripts/public-secret-sensitive-scan.sh --help
```

Exit codes:
- `0` — No blockers found (heuristic scan)
- `1` — One or more blockers found

---

## Scanned Categories

| Category | What It Detects |
|---|---|
| `private_key` | `BEGIN RSA PRIVATE KEY`, `BEGIN OPENSSH PRIVATE KEY`, `BEGIN PRIVATE KEY` markers |
| `aws_access_key` | `AKIA[0-9A-Z]{16}` patterns |
| `github_token` | `ghp_` and `github_pat_` prefixes |
| `generic_secret_assign` | `api_key =`, `apiKey:`, `secret =`, `token =`, `password =`, `private_key =` assignments |
| `bearer_token` | `Bearer` followed by a 20+ character high-entropy-looking string |
| `internal_hostname` | Private internal hostnames (e.g. `internal-forge.example.com`) |
| `internal_path` | `/home/adminuser`, `/home/oai`, `/mnt/data` |
| `customer_data` | `customer email`, `customer name`, `customer id`, `real grant applicant` |
| `private_personal_data` | `passport`, `social security number`, `national id`, `bank account` |
| `overclaim` | `production SaaS ready`, `production-ready SaaS`, `tenant isolation implemented`, `public GitHub release completed` |

---

## Safe Placeholders

Lines containing any of the following terms are **skipped** (treated as safe references):

```
<token>
<api-key>
example
demo
fake
dummy
placeholder
legacy-admin-token
test-token
dev-token
local
no real secrets
no real customer data
not production SaaS
tenant isolation is not implemented
```

This means:
- Documentation that says `"no real secrets"`, `"no real customer data"`, `"not production SaaS"`, or `"tenant isolation is not implemented"` is **not** flagged — those are required caveats.
- Code samples using `token = test-token` or `api_key = placeholder` are **not** flagged.

---

## Blocker Examples

The following content in tracked files **would** be flagged:

```
# Blocker: private key marker (shown split to avoid triggering key-hygiene guards)
# Actual marker: "-----BEGIN" + " RSA PRIVATE KEY-----"

# Blocker: AWS access key (synthetic example — not a real key)
AKIAIOSFODNN7EXAMPLE123

# Blocker: internal hostname reference
Remote: internal-forge.example.com/org/repo.git

# Blocker: internal absolute path
config_path: /home/adminuser/config.json

# Blocker: overclaim phrase
GrantLayer is production SaaS ready for enterprise deployment.
```

---

## What to Do if Blockers Are Found

1. **Credentials / tokens / keys**: Replace the real value with a safe placeholder (`<token>`, `example`, `placeholder`). If a real credential was committed, **rotate it externally** — this script does not rotate secrets.

2. **Internal hostnames**: Replace with a generic example hostname (e.g. `git.example.com`) in docs, or remove the reference if it belongs only in local config.

3. **Internal paths**: Replace with a generic example path (e.g. `/path/to/config`) in docs.

4. **Customer or personal data**: Remove entirely. Do not include real grant applicant names, emails, IDs, or personal identifiers in tracked files.

5. **Overclaim phrases**: Revise the text to accurately reflect Developer Preview status (see Caveats below).

6. **Files that should never be tracked**: Use `git rm --cached <file>` to untrack them and add the path to `.gitignore`.

After resolving blockers, re-run the script to confirm exit 0.

---

## Limitations

- **Heuristic scan only** — this script uses pattern matching on tracked file content. It may miss obfuscated or encoded secrets.
- **Not a forensic audit** — it does not deeply scan full git history (commits, blobs, reflog). Past commits may contain content not present in the current working tree.
- **Does not deeply scan full git history** — historical exposure is handled in GL-158.
- **Does not rotate secrets** — rotation must be done externally through the relevant service.
- **Does not rewrite history** — history cleanup, squashing, or orphan-branch snapshots are out of scope and handled in GL-158.
- **Does not publish to GitHub** — publication decisions are handled in GL-159/GL-160.
- **False negatives possible** — novel patterns not in the scan categories will not be detected.
- **False positives possible** — context-free pattern matching may flag safe content not covered by the allowlist.

---

## Next Step

**GL-158 Git History Exposure Review / Public Snapshot Decision**

Before public GitHub release, GL-158 will audit git history for exposed secrets, decide on history strategy (full history vs. orphan public snapshot), and document the outcome.

---

## Caveats

**Developer Preview**: GrantLayer is a developer preview. It is **not production SaaS ready** for enterprise or multi-tenant deployment.

**Tenant isolation is not implemented**: No workspace or tenant isolation exists. All data sharing a GrantLayer instance shares the same database.

**No real secrets**: This repository does not contain real production credentials, API keys, or tokens.

**No real customer data**: This repository does not contain real grant applicants, customer records, or personal data.
