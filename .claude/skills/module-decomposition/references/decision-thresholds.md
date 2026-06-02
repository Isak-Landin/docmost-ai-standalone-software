# Decision Thresholds

This file provides concrete prompts for when a file, module, or directory should be
re-evaluated for decomposition.

Thresholds are not automatic split mandates. They are "stop and check" signals.

---

## Transport layer thresholds

### Routes / controllers / views

Check for service extraction when one or more of these appear:

- handler above roughly 50 lines
- multiple database queries inline
- outbound HTTP/API calls in the transport file
- retry, payment, audit, or workflow logic in the transport file
- the same domain logic repeated in multiple handlers

### Middleware

Create a dedicated middleware domain when:

- two or more middleware files share a cross-cutting concern
- auth/session/telemetry/logging behavior grows beyond one file

---

## Service layer thresholds

Check for service domain splits when:

- a service file grows beyond roughly 200 lines
- unrelated external systems are handled in one service file
- the file contains both orchestration and low-level provider client code
- it owns both read/query helpers and write/state-transition logic

Create a subpackage when:

- two or more files inside a domain clearly share a narrower sub-domain
- examples: `billing/webhooks/`, `users/permissions/`, `orders/fulfillment/`

---

## Data layer thresholds

Check for repository/query extraction when:

- queries are repeated in 2 or more routes/tasks
- query building is complex enough to deserve reuse or testing
- transaction/session handling appears in multiple places
- raw SQL and ORM logic are mixed in unrelated files

Check for separate migration/seed structure when:

- the repo has both schema migrations and data seeding concerns
- bootstrap SQL and runtime queries are mixed

---

## Frontend thresholds

### Pages

Check for feature/component extraction when:

- a page owns 2 or more clearly independent interactive regions
- a page accumulates reusable UI also needed elsewhere
- page-specific assets begin carrying shared logic used by multiple pages

### Components

Check for component package/domain extraction when:

- a reusable component family has 2 or more sibling files
- example: component, test, stories, styles, variants, hooks

### Shared assets

Check for shared vs page-owned split when:

- the same selector/behavior is used by 2 or more route families
- "shared" files begin accumulating unrelated page-specific logic

---

## Worker / job thresholds

Check for decomposition when:

- worker bootstrap file contains actual task logic
- scheduling rules and task execution logic evolve independently
- multiple task families share queue utilities or serialization helpers
- one task file owns unrelated queue domains

---

## CLI and script thresholds

Check for a command package when:

- one script now supports multiple commands or modes
- argument parsing and business logic are intertwined
- multiple scripts repeat the same bootstrap logic

Keep one-off scripts flat only while they remain one-off and single-concern.

---

## Monorepo thresholds

Create a shared package when:

- two or more apps genuinely reuse the same domain logic or component set
- that concern has stable ownership separate from any one app

Do **not** create a shared package when:

- the only reason is "might be reused later"
- the code is still owned by one app/workspace
- the shared package would need app-specific imports

---

## Boundary warning signs

If a file imports across many unrelated layers, stop and inspect.

Common warning signs:

- route imports repository, provider client, and template helper directly
- service imports route/controller code
- model/entity imports HTTP clients
- template/view layer contains data access or external API calls
- task imports controller/router code

Those are strong signals that structure and ownership are drifting.
