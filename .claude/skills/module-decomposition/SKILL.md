---
name: module-decomposition
description: >
  Governs how code is divided into files, modules, directories, and structural
  surfaces in a repository. Use when writing new code, deciding where an addition
  belongs, splitting an overgrown file, or setting the initial structure of a new
  repo. Covers common stacks such as Flask, FastAPI, Django, Node/TypeScript
  services, workers, frontends, and containerized deployments, with emphasis on
  repo structure, package boundaries, and directory ownership.
---

# Module Decomposition Skill

## When to use this skill

- Creating the initial structure of a new repository
- Adding any new function, class, module, route, worker, component, or package
- Editing existing code and verifying that it still lives in the correct location
- Deciding whether a growing file should split
- Deciding whether a second file justifies a new directory or package
- Deciding where framework-owned surfaces belong (Flask, FastAPI, Express, React, Docker, etc.)
- Mapping a repo's libraries and frameworks to a concrete target structure from the reference catalog

## When NOT to use this skill

- Choosing **what** external API or framework pattern to use
- Library-specific implementation details that do not affect structure
- Pure documentation wording work
- Style-only questions inside a file when the file already has the correct home
- In-file HTML semantics, CSS rules/selectors, or JavaScript coding patterns once the
  correct repo/module location is already established

## Core principle

One file = one concern. One directory = one domain.

A **concern** is a single reason to change: the external event that would cause an edit
to that file. A **domain** is a group of concerns that change together.

When a file has two distinct reasons to change, it must be split.

## Coverage principle

This skill intentionally covers more dependency and framework surfaces than any single
repo may use.

- If a stack is **unused**, its guidance can be ignored.
- If a stack is **used** but not covered, the skill becomes unreliable.
- A dependency does not dictate the whole structure, but it often introduces structural
  ownership that needs a home.

Examples:

- Flask / FastAPI / Express / Nest -> entrypoint, routes or routers, request handling
- SQLAlchemy / Prisma / ORM layers -> models, queries or repositories, migrations
- React / Vue / server-rendered templates -> pages, components, shared UI, assets
- Celery / RQ / BullMQ -> task modules, worker entrypoints, schedules
- Docker / Compose -> runtime and deploy configuration surfaces

This skill governs **where those surfaces live in the repo**. It does not govern the
fine-grained contents inside a template, stylesheet, or script file.

## How to use the catalog

1. Identify the repo's major targets:
   - backend API
   - backend-owned rendered UI
   - standalone frontend
   - worker/queue/consumer
   - CLI/automation
   - library/package
   - monorepo/workspace
   - data-heavy or migration-heavy service
2. Map libraries/frameworks to those targets with `dependency-surfaces.md`.
3. Apply the relevant detailed target file, not just the high-level rules.
4. Use `layer-interaction-patterns.md` to keep boundaries between routes, services,
   repositories, models, tasks, pages, components, and clients coherent.
5. Use `decision-thresholds.md` when deciding whether a split is warranted.

## The three structural rules

1. A file contains exactly one concern. Split when two appear.
2. A directory is created for a domain when at least two files share it - not before.
3. Package boundary files (`__init__.py`, `index.ts`, `index.js`, or equivalent) expose
   public API only. No implementation logic.

## DOs

- Create a new file when new code has a distinct concern
- Move edited code to its canonical location as part of the same change
- Create a directory as soon as a second file for the same domain arrives
- Keep entrypoints thin: bootstrap, wire, run
- Keep framework-specific surfaces separated from business logic
- Keep shared UI/assets shared only when reuse is real, not assumed
- Keep deploy/runtime files separate from application modules

## DON'Ts

- Do not add code to a nearby file just because it feels convenient
- Do not create speculative packages for a single file
- Do not create `utils`, `helpers`, or `common` catch-alls without a real domain meaning
- Do not put business logic in HTTP routes, controllers, or view functions
- Do not put database access in presentation layers
- Do not mix build/deploy concerns into app runtime modules
- Do not wait for a "future refactor" if code is already in the wrong place

## Reference files

- [Decomposition rules](references/decomposition-rules.md) - decision rules and migration examples
- [Decision thresholds](references/decision-thresholds.md) - concrete signals for when a split or new package is justified
- [Layer interaction patterns](references/layer-interaction-patterns.md) - structural contracts between routes, services, repositories, templates, assets, tasks, and clients
- [Target structure](references/target-structure.md) - repo-agnostic layouts for common stack families
- [Python targets](references/python-targets.md) - in-depth target structures for Python services, APIs, apps, libraries, and CLIs
- [Node/TypeScript targets](references/node-typescript-targets.md) - in-depth target structures for Node backends, services, packages, and CLIs
- [Frontend targets](references/frontend-targets.md) - in-depth target structures for SPA, SSR, static sites, and component libraries
- [Data and migrations targets](references/data-and-migrations-targets.md) - data access, migration, seed, and query-heavy service structures
- [Worker, CLI, and automation targets](references/worker-cli-and-automation-targets.md) - queue, scheduler, consumer, CLI, and script structures
- [Monorepo and workspace targets](references/monorepo-and-workspace-targets.md) - multi-app, multi-package, and shared package structures
- [Testing targets](references/testing-targets.md) - test ownership, fixtures, snapshots, and end-to-end structure
- [Dependency surfaces](references/dependency-surfaces.md) - what common libraries and frameworks imply structurally
- [Documented structure bases](references/documented-structure-bases.md) - official framework doc anchors used to generalize repo structures
