# Locked and Shared Values

A locked contract is any value or behavior that must stay identical across two or more
independent locations.

Examples:

- a field name used by both producer and consumer
- a route or path used in both templates and handlers
- a port shared between runtime config and a reverse proxy
- an identifier stored in a database and later used in API requests

## Required workflow

Before changing a locked or shared value:

1. Find the canonical owner.
2. Find every mirrored or dependent location.
3. Check whether the repo has `CONTRACTS.md`, `ADDITIONAL_CONTRACTS.md`, or an equivalent registry.
4. If the task is only drift repair, keep the canonical value and update the drifted copies.
5. If the task is a true contract change, update every dependent location in the same change.
6. Update the relevant contract registry in the same change when the repo uses one.
7. Run the repo's relevant tests and any contract-validation script that exists.

Never defer contract-registry updates to a later task.

## When to create a new contract entry

Create a contract entry as soon as a value becomes cross-boundary and stable enough that
drift would break the system or create silent mismatches.
