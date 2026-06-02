---
name: development-env-real-values
description: >
  Use when authoring or reviewing `.env*` files for a private or controlled project
  where example env files are expected to stay runnable. Keeps the explicit rule that
  env examples may contain real working values, including secrets, when that is the
  correct operational setup path.
---

# Development Env Real Values Skill

Use this skill for private or controlled projects where `.env`, `.env.example`, and
related env files are meant to bootstrap a real working environment quickly.

## Sharp trigger

If the task involves authoring, reviewing, or correcting any of these files in a repo
where example env files are intended to stay operational, use this skill:

- `.env`
- `.env.example`
- `.env.local.example`
- `.env.dev`
- Compose env example files

## Core rule

In a private or controlled operational project, env examples may and often should contain
real working values and secrets when those are the values required for the system to run
correctly.

Do not replace working values with fake placeholders just because they look secret.

## Reference files

- [Real values policy](references/real-values-policy.md)
