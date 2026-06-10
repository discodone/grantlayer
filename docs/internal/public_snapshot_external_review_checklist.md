# GL-212 Internal Public Snapshot / External Review Checklist

**Status:** Internal-only dry-run checklist. This checklist does not publish anything,
does not create a public export, does not push to public GitHub, and
does not change repository visibility.

## Future Export Candidate Requirements

- Start from an explicit internal issue and approved internal branch.
- Use tracked, reviewed files only.
- Use synthetic/demo data only.
- Preserve Developer Preview / Controlled Preview with strict boundaries.
- Keep Production SaaS, real customer/private grant/institutional data,
  official SDK/package, compliance certification, and production PostgreSQL
  readiness as no-go.

## Allowed Files

- Reviewed source files required for local Developer Preview evaluation.
- Reviewed docs, examples, tests, and static website baseline files.
- Claim-safe synthetic/demo examples.
- Internal-only gate artifacts that are approved for the candidate.

## Forbidden Files

- `.env*`, secrets, credentials, tokens, raw DSNs, private keys, passwords,
  authorization headers, logs, databases, dumps, backups, local caches, and
  virtual environments.
- Real customer data, private grant data, institutional data, personal data, and
  private attachments.
- Untracked website-design/import files and incomplete import reports unless a
  later issue explicitly approves them.
- Public export directories, public publish worktrees, public release branches,
  public release tags, release metadata, and package registry metadata.
- `setup.py`, SDK `pyproject.toml`, `package.json`, `package-lock.json`, package
  publishing config, analytics/tracking integrations, and data collection forms.

## Scanner Commands

Run these checks against the export candidate path and the branch diff before
any public action:

```bash
git status --short
git diff --check
git diff --name-only main...HEAD
git ls-files --others --exclude-standard
grep -RInE 'postgres(ql)?://|Bearer [A-Za-z0-9._~+/=-]{8,}|BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY|password|token|authorization:' <candidate>
grep -RInE 'Production SaaS ready|enterprise ready|compliance certified|GDPR ready|SOC2 ready|ISO ready|official SDK|public SDK package|production PostgreSQL ready|ready for real customer data|ready for private grant' <candidate>
find <candidate> -name setup.py -o -name pyproject.toml -o -name package.json -o -name package-lock.json
find <candidate> -path '*/.github/workflows/*' -o -iname '*publish*' -o -iname '*release*'
```

Use stronger secret scanners if available locally. Any positive must be
reviewed and either removed or explicitly classified before continuing.

## Claim Review

- Allowed: Developer Preview, Controlled Preview with strict boundaries,
  synthetic/demo data only, baselines implemented but not production-complete,
  internal SDK prototype only, and ephemeral live PostgreSQL validation passed.
- Prohibited: Production SaaS ready, enterprise ready, compliance certified,
  GDPR/SOC2/ISO ready, real-data ready, official SDK/package available,
  production PostgreSQL ready, complete tenant isolation, complete production
  IAM, complete DR/backup/restore, and complete incident response.

## Secret Review

- Block raw DSNs, credentials, tokens, passwords, authorization headers, private
  keys, webhook secrets, cookies, cloud credentials, and high-entropy values.
- Confirm examples use placeholders or synthetic values only.

## Real-Data Review

- Block real customer data, private grant data, institutional data, personal
  data, private attachments, production identifiers, and production exports.
- Confirm generated examples are deterministic synthetic/demo artifacts.

## Package Metadata Review

- Confirm no `setup.py`, SDK `pyproject.toml`, `package.json`,
  `package-lock.json`, package registry metadata, package publish workflow, or
  official SDK/package claim is present.

## Workflow / Snapshot Script Review

- Confirm no GitHub workflow changes.
- Confirm no snapshot publish script changes.
- Confirm no visibility-change, force-push, public release, public tag, or
  public publish behavior is present.

## Reviewer Handoff Rules

- Use internal-only or claim-safe reviewer instructions.
- Require synthetic/demo data only.
- Prohibit production credentials, real customer/private grant/institutional
  data, public exploit details, official SDK/package assumptions, public website
  publish assumptions, and Production SaaS implications.
- Do not include outreach text or public announcement text.

## Security Reporting Rules

- Security-sensitive reports route to GitHub Security Advisories.
- Public channels must not include exploit details, real secrets, raw DSNs,
  credentials, customer data, private grant data, or institutional data.
