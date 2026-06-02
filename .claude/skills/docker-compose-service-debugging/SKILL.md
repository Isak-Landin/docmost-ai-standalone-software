---
name: docker-compose-service-debugging
description: >
  Use when debugging services managed by Docker Compose. Covers logs, exec, rebuild vs
  recreate vs restart semantics, and how to reason about config drift versus runtime
  drift in a Compose-managed stack.
---

# Docker Compose Service Debugging Skill

Use this skill when the runtime is managed by Docker Compose and the question is whether
the problem lives in code, image contents, service definition, environment, mounts, or
live container state.

## Standard flow

1. Inspect service state with `docker compose ps`.
2. Read logs before changing anything.
3. Inspect the running container or service config when logs are insufficient.
4. Decide whether the fix needs restart, recreate, or rebuild.
5. Re-check logs after the action.

## Core rule

`restart` only restarts the current container process.

It does not:

- rebuild images
- recreate containers
- apply changed `env_file` values
- apply changed service definitions, mounts, commands, or networks

Use the smallest correct action, but not a smaller one.

## Reference files

- [Compose debugging flow](references/compose-debugging-flow.md)
- [Config vs runtime drift](references/config-vs-runtime-drift.md)
