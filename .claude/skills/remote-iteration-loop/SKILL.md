---
name: remote-iteration-loop
description: >
  Governs local-authoring and remote validation loops for systems deployed to a remote
  runtime. Use when debugging deployed behavior, shipping a fix through git, or
  iterating via logs across local code and remote services.
---

# Remote Iteration Loop Skill

Use this skill when the source of truth is local code but the failing behavior appears in
a remote runtime.

## When to use this skill

- Fixing a bug that reproduces only in a deployed environment
- Deploying a code change through the repo's normal delivery path
- Reading remote logs before deciding on a fix
- Iterating through change -> deploy -> observe -> repeat

## Core principle

Author locally. Observe remotely. Deliver through the repo's normal source path.

The remote environment is for:

- logs
- runtime state
- verification
- one-off inspection commands

It is not the final authoring location for source changes.

## Git remote

For these repos the git remote used for push and pull is `forgejo`, replacing the previous
`origin`. This cannot be derived from the repo state, so always name it explicitly:
`git push forgejo <branch>` and `git pull forgejo <branch>`.

## Loop summary

1. Reproduce or observe the failure.
2. Read logs and runtime state before editing.
3. Implement the fix locally.
4. Run the repo's existing validation steps.
5. Commit and push through the repo's normal source path using the `forgejo` remote (`git push forgejo <branch>`, not `origin`).
6. Pull/deploy on the remote using the repo's documented procedure - pull from `forgejo` (`git pull forgejo <branch>`).
7. Restart or recreate the affected runtime with the correct level of change.
8. Re-check logs and verify the symptom is gone.
9. Repeat from logs if the result is still wrong.

## Reference files

- [Local authoring and delivery](references/local-authoring-and-delivery.md)
- [Iteration loop](references/iteration-loop.md)
