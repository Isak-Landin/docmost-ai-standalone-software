# Idempotent Ensure Flows

Whenever code ensures that an external resource exists or matches a desired state, make
the flow safe to run repeatedly.

## Standard pattern

1. Read current state from the provider.
2. Compare that state to the desired state.
3. Return existing state when it already matches.
4. Create or update only when required.
5. Re-read when needed to confirm the final provider state.

## Why this matters

Idempotent flows are safer for:

- deploy-time bootstrap
- repeated background jobs
- recovery from partial failure
- remote retries after timeouts

Do not create duplicate resources just because the previous call's result was not cached locally.
