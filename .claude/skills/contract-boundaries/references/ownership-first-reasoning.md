# Ownership-First Reasoning

Do not change a boundary until you know who owns it.

## Core rule

Every stable surface should have one canonical owner:

- one writer for a stored field
- one owner for a public route or integration path
- one owner for a user-visible label or naming rule
- one owner for a runtime exposure decision

Consumers may mirror, display, transform, or validate the value, but they do not become
co-owners just because they reference it.

## Workflow

1. Identify the surface being changed.
2. Ask which module, service, config layer, or upstream system is authoritative.
3. Separate owner logic from consumer logic.
4. Change the owner first, then align downstream consumers.

## Warning signs

Stop and re-check ownership if you notice any of these:

- multiple modules writing the same field
- a UI or transport layer inventing provider-owned values
- runtime config overriding source-of-truth values without an explicit contract
- a downstream consumer becoming the accidental place where canonical names are decided

Avoid duplicate responsibilities. If two places seem to own the same surface, the task is
usually to restore the boundary, not to keep both owners.
