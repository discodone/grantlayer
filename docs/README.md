# GrantLayer Docs

This directory contains documentation for GrantLayer.

---

## For External Developers

Start here if you're evaluating, integrating, or contributing to GrantLayer.

| File | What it covers |
|------|----------------|
| [architecture.md](architecture.md) | System design, data model, audit chain |
| [openapi.yaml](openapi.yaml) | Full OpenAPI specification (also at `/api/docs` when running) |
| [integration_guide.md](integration_guide.md) | How to integrate GrantLayer into a workflow |
| [integrator_quickstart.md](integrator_quickstart.md) | Quickstart for integrators |
| [ten_minute_quickstart.md](ten_minute_quickstart.md) | Clone → install → backend → smoke test (no Docker) |
| [minimal_api_usage_walkthrough.md](minimal_api_usage_walkthrough.md) | Minimal API usage walkthrough |
| [key_hygiene.md](key_hygiene.md) | Key and secret hygiene guidelines |
| [security_boundaries.md](security_boundaries.md) | Security boundary reference |
| [dependency_manifest.md](dependency_manifest.md) | Runtime and dev dependency manifest |
| [mvp_scope.md](mvp_scope.md) | MVP feature scope and limitations |

### Examples and Walkthroughs

| File | What it covers |
|------|----------------|
| [langgraph_langchain_integration_example.md](langgraph_langchain_integration_example.md) | LangGraph/LangChain integration example |
| [public_agent_api_walkthrough_refresh.md](public_agent_api_walkthrough_refresh.md) | Public agent/API walkthrough, no-install examples |
| [first_output_verify_helper.md](first_output_verify_helper.md) | Helper for verifying your first output |
| [grant_lifecycle_evidence_bundle.md](grant_lifecycle_evidence_bundle.md) | Grant lifecycle evidence bundle example |
| [demo_scenario.md](demo_scenario.md) | Demo scenario description |
| [demo_script.md](demo_script.md) | Demo script |

### Feedback and Support

| File | What it covers |
|------|----------------|
| [public_feedback_infrastructure_pack.md](public_feedback_infrastructure_pack.md) | How to give feedback, severity routing, Security Advisory guidance |

### For AI Coding Agents

| File | What it covers |
|------|----------------|
| [agent_quickstart.md](agent_quickstart.md) | 60-second orientation for first contributions |
| [agent_task_contract.md](agent_task_contract.md) | Issue/task contract and final-report format |
| [agent_integration_manifest.json](agent_integration_manifest.json) | Machine-readable project metadata |

---

## Internal Governance Documents

The `docs/internal/` subdirectory contains internal governance records — gate
reports, go/no-go decisions, review artifacts, and hardening checklists from the
development process. These documents are kept for historical completeness but are
**not intended for external developers**.

The remaining `.md` files at the root of `docs/` that are not listed in the
external index above are also internal governance documents (kept here for
test-suite compatibility). They include production-readiness reviews, tenant
isolation design records, and internal security audits.

---

## API Reference

Full OpenAPI spec: [openapi.yaml](openapi.yaml)

Interactive Swagger UI: available at `/api/docs` when the stack is running.
