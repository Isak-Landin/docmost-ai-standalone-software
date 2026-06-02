# Iteration Loop

Use the repo's documented commands, but keep this order stable:

```text
observe failure
  ->
read logs and inspect runtime state
  ->
implement fix locally
  ->
run repo validation
  ->
commit
  ->
push (git push forgejo <branch>)
  ->
pull (git pull forgejo <branch>) or deploy on remote
  ->
restart or recreate affected runtime
  ->
read fresh logs
  ->
verify behavior
  ->
repeat if still broken
```

## Restart selection

- Use a light restart only when the repo's documented runtime model says it is enough.
- Use recreate when environment, command, volume, or service definition changed.
- Use rebuild when image contents, dependencies, or build inputs changed.

Do not guess. If the repo already documents a canonical deploy path, follow it.

## Verification rule

Do not stop at "deploy completed". Confirm:

- the service started cleanly
- the original error is gone from fresh logs
- the user-visible behavior now matches the intended contract
