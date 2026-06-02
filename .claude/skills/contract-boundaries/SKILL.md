---
name: contract-boundaries
description: >
  Use when changing a value, field, path, identifier, or behavior that crosses an
  ownership boundary or must stay in sync across multiple locations. Covers locked
  contracts, ownership-first reasoning, and restorative drift handling.
---

# Contract Boundaries Skill

Use this skill whenever a change might affect more than one owner or more than one copy
of the same canonical value.

## When to use this skill

- Changing a value that appears in multiple files, services, environments, or repos
- Changing a field or behavior that has a clear owner and downstream consumers
- Investigating code/runtime/doc/config disagreement
- Working in a repo that uses `CONTRACTS.md`, `ADDITIONAL_CONTRACTS.md`, or equivalent
- Deciding whether a request is a true contract change or only a drift repair

## Default posture

Contract work is restorative by default.

- If the user did not explicitly request a contract change, preserve the current canon.
- Weak or missing coverage is not permission to redefine the canon.
- If ownership is unclear, resolve that first instead of editing both sides speculatively.

## How to use this skill

1. Read the references that match the boundary in play.
2. Identify the current owner of the value or behavior.
3. Identify every downstream copy, mirror, or consumer that must stay in sync.
4. Repair drift toward the established owner unless the task explicitly changes the contract.
5. Update code, config, docs, and contract registries together when the canonical value changes.

## Reference files

- [Locked and shared values](references/locked-and-shared-values.md)
- [Ownership-first reasoning](references/ownership-first-reasoning.md)
- [Restorative drift posture](references/restorative-drift-posture.md)
