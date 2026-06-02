---
name: external-provider-integration
description: >
  Use when integrating or debugging any external API or provider. Covers official-docs-
  first request and response contracts, idempotent ensure flows, environment-owner
  classification, and explicit handling of missing credentials.
---

# External Provider Integration Skill

Use this skill whenever the application talks to a third-party API, SDK, webhook source,
or managed service.

## Default rules

- Official provider documentation is the source of truth.
- Request and response contracts must be explicit.
- Provisioning or "ensure" paths must be idempotent.
- Failures must be classified by owner before code changes.
- Missing required credentials must fail explicitly.

## When to use this skill

- Creating or changing a provider client
- Debugging a failing API call or webhook flow
- Adding sandbox/test integrations
- Comparing live provider behavior with a mock or harness

## Reference files

- [Official contract first](references/official-contract-first.md)
- [Idempotent ensure flows](references/idempotent-ensure-flows.md)
- [Environment owner classification](references/environment-owner-classification.md)
- [Credential failure policy](references/credential-failure-policy.md)
