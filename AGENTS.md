# AGENTS.md

GrantLayer is a verification, audit, and compliance layer for agentic grant and
funding workflows. When AI agents prepare funding applications, evaluate eligibility,
or trigger approval decisions, GrantLayer makes every step traceable, tamper-evident,
and independently auditable.

This repository is in **Developer Preview** — designed for local evaluation and
controlled pilots. It is not a production SaaS.

---

## Getting Started

The fastest way to understand GrantLayer:

1. **[README.md](README.md)** — project overview, API reference, configuration
2. **[QUICKSTART.md](QUICKSTART.md)** — get the stack running in 5 minutes
3. **[docs/architecture.md](docs/architecture.md)** — system design and data model
4. **[docs/openapi.yaml](docs/openapi.yaml)** — full OpenAPI spec (also at `/api/docs` when running)

---

## Contributing

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for:

- Local setup and Docker quickstart
- Coding guidelines and test expectations
- How to open issues and pull requests
- Security and data-handling rules

All contributions are welcome. The safest starting points are documentation
improvements, test additions, and example updates.

---

## Reporting Bugs

1. Check [existing issues](https://github.com/discodone/grantlayer/issues) first.
2. Open a [new issue](https://github.com/discodone/grantlayer/issues/new) with:
   - What you ran (exact command)
   - What you expected
   - What happened instead
   - OS, Docker version, Python version

---

## Reporting Security Issues

Use [GitHub Security Advisories](https://github.com/discodone/grantlayer/security/advisories/new).
Do **not** open a public issue for vulnerabilities.

See [SECURITY.md](SECURITY.md) for the full security policy.

---

## Contact

Open an issue or a discussion on the [GitHub repository](https://github.com/discodone/grantlayer).

---

## Security and Data Rules

- **No real secrets** — never commit API keys, tokens, or passwords. All examples use placeholder values.
- **No real customer data** — never commit real names, addresses, or identifiers. All examples use synthetic data.
- **No overclaims** — do not claim production SaaS readiness or production-complete tenant isolation.
  Tenant/workspace isolation is not production-complete.
