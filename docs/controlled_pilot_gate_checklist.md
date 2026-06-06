# Controlled Pilot Gate Checklist

**Status:** Internal-only checklist for GL-211 gate follow-up.

This checklist is not public outreach text, not a user invitation, not a
production readiness claim, and not a public publish requirement.

## Allowed

- Internal demo with synthetic/demo data only.
- Developer Preview review with synthetic/demo data only.
- Controlled external technical review only after the GL-211 boundaries are
  provided to reviewers.
- First external controlled pilot only if synthetic/demo data is used end to end.

## Required Before Any Controlled External Review

- Confirm every dataset is synthetic/demo data.
- Confirm no real customer data is used.
- Confirm no private grant data is used.
- Confirm no institutional data is used.
- Confirm no production-like import is requested or accepted.
- Confirm no real secrets, credentials, API keys, tokens, private keys, DSNs, or
  production hostnames are included.
- Confirm instructions do not claim Production SaaS readiness.
- Confirm instructions do not claim compliance certification, GDPR readiness,
  SOC2 readiness, ISO readiness, or enterprise readiness.
- Confirm instructions do not claim official SDK/package availability.
- Confirm instructions do not require public website publish, public GitHub
  push, package publishing, analytics, tracking, or data collection forms.
- Confirm security-sensitive reports route to GitHub Security Advisories.
- Confirm public channels must not include exploit details, real secrets, real
  customer data, private grant data, or institutional data.

## No-Go Conditions

- Any real customer data.
- Any private grant data.
- Any institutional data.
- Any production-like data import.
- Any real secret or credential.
- Any request to publish packages or add package metadata.
- Any request to claim Production SaaS, compliance certification, enterprise
  readiness, official SDK/package availability, live PostgreSQL production
  readiness, complete tenant isolation, complete production IAM, complete
  observability, or complete DR/backup/restore readiness.
- Any requirement to publish the website or update a public snapshot as part of
  the pilot.

## Reporting

Security-sensitive reports route to GitHub Security Advisories. Public reports
must not include exploit details, secrets, real customer data, private grant
data, or institutional data.
