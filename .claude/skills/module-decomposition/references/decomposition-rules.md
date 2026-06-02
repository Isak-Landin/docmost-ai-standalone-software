# Decomposition Rules

These rules govern when and how to split code into files, packages, and directories.
They are written to work across common repository types rather than one framework only.

---

## Rule 1: Two-concern test

Before adding to an existing file or choosing where new code belongs, ask:

> "Would this code change for a different reason than the existing content?"

If the answer is yes, it belongs in a different file.

### Examples of one concern

- A Flask blueprint file that only defines HTTP handlers for one domain
- A FastAPI router module that only defines routes for one resource family
- A React component file that only renders and styles one reusable UI component
- A Dockerfile that defines one runtime image for one service

### Examples of two concerns

- A route file that also performs provider or database business logic
- A model file that also calls external APIs
- A React page file that contains both page layout and a reusable shared component
- A worker task file that also owns the scheduler boot logic

---

## When NOT to decompose

### 1. A helper used by exactly one function in the same file

A private helper that exists only for one parent function stays with that concern.

### 2. Constants and mappings that belong to the file's concern

Status maps, field lists, selector maps, or request timeouts remain with the module
that owns them.

### 3. A large file with only one reason to change

Line count is a signal to inspect, not the split rule by itself.

### 4. Thin entrypoints

Files such as `main.py`, `server.ts`, `manage.py`, `wsgi.py`, `asgi.py`, `cli.py`, or
worker bootstrap files are expected to stay thin.

### 5. Generated or tool-owned files

Migration revisions, generated clients, lockfiles, and vendor bundles follow the owning
tool's layout unless the repo deliberately wraps them in a higher-level domain folder.

---

## Growth-triggered migration

These cases begin small and stay flat until the second concern becomes real.

### When the trigger fires

A component is ready to migrate when it has:

- its own reason to change, and
- enough weight to justify a separate home, usually because it is large or reused

### Example 1: Flask view to service migration

A Flask route starts by validating input and doing a single ORM write. It later gains
payment checks, retry rules, and audit behavior.

**Trigger:** route behavior and domain workflow now change for different reasons.  
**Migration:** keep request parsing in the route and move the domain workflow to
`services/<domain>.py`.

### Example 2: FastAPI router to service/repository migration

A FastAPI router begins with inline SQLAlchemy queries. Later the same query logic is
needed by both the router and a background task.

**Trigger:** request handling and data access now have different reasons to change.  
**Migration:** move read/write logic to `repositories/` or `services/`, keep the router
focused on HTTP concerns.

### Example 3: Frontend page to component migration

A page starts with one inline widget. The widget later appears on multiple pages and
gains its own behavior, state handling, and styles.

**Trigger:** widget lifecycle diverges from the page lifecycle.  
**Migration:** move the widget into `components/` and keep page-specific composition in
the page file.

### Example 4: Shared asset migration

A few CSS rules or JS helpers begin inside one page-owned asset file. Later the same
UI element appears in multiple families or routes.

**Trigger:** the asset concern is now cross-page or cross-family.  
**Migration:** move the shared portion to `shared/` and keep page-only behavior in the
page or family asset file.

### Example 5: Worker task domain migration

A task queue module starts with one task. It later grows retries, serialization helpers,
event publishing, and task-specific state transitions.

**Trigger:** queue entrypoint, task logic, and support helpers now change independently.  
**Migration:** keep worker bootstrap in the entrypoint, move task families to
`tasks/` or `workers/<domain>/`.

### Example 6: Infra split

A single deployment directory starts with one Compose file. It later needs dev, staging,
and production variants plus Kubernetes or Terraform files.

**Trigger:** one deploy file now serves multiple environments with different change
drivers.  
**Migration:** split into `deploy/compose/`, `deploy/k8s/`, `deploy/terraform/`, or
another clear environment/tool grouping.

---

## Concrete thresholds

The two-concern test remains the actual rule, but these thresholds are useful prompts
that should make you stop and re-check whether decomposition is now justified.

- Route/controller handler above roughly 50 lines and containing business logic:
  check whether service extraction is due.
- Service file above roughly 200 lines:
  check whether it now owns multiple concerns.
- File importing from three or more unrelated layers:
  check whether it has become a coupling hotspot.
- Query logic duplicated in two or more transport/task files:
  check whether a repository/query module is due.
- Page/component file with multiple unrelated interactive regions:
  check whether feature/component extraction is due.
- Script file now supporting multiple commands or workflows:
  check whether a CLI or command package is due.
- Shared asset file accumulating unrelated page-specific logic:
  check whether page/family/shared separation is due.

Thresholds are prompts, not automatic mandates. The deciding rule is still:
"does this code now change for a different reason?"

See `decision-thresholds.md` for target-specific thresholds.

---

## Rule 2: Directory creation rule

Create a directory or package when **two or more files** share the same domain.

When the second file for a domain arrives:

1. Create the directory.
2. Move both files into it.
3. Add the boundary file if the language uses one.

This rule is recursive. It applies at every depth.

### Boundary file examples

- Python: `__init__.py`
- TypeScript / JavaScript: `index.ts`, `index.js`
- Frontend component libraries: `index.tsx` only when it is the public surface

Never create a directory speculatively for one file.

---

## Rule 3: Public boundary contract

The boundary file of a package or module group is the public API surface.

- Re-export only what outside callers should use
- Keep implementation logic out of the boundary file
- Internal callers import directly from sibling modules
- External callers import from the boundary file by convention

If the repo uses Python packages, this means `__init__.py`. If it uses TypeScript or
JavaScript packages, this usually means `index.ts` or `index.js`.

---

## Rule 4: Edit-triggered migration

When a task requires editing code that clearly lives in the wrong place:

1. Move it to its canonical location first.
2. Re-export or update callers as needed.
3. Land the move and the functional change together.

This is part of the task, not a separate refactor ticket.

---

## Rule 5: Migration-tool rule

Schema changes go through the repo's migration mechanism.

Examples:

- Alembic / Flask-Migrate
- Django migrations
- Prisma migrations
- Knex migrations
- Rails migrations

Do not hide schema evolution inside random startup code or route handlers unless the
repo explicitly uses a documented bootstrap-only pattern.

---

## Rule 6: Pre-creation rule

When new code belongs in a location that does not exist yet:

1. Create the target directory and file first.
2. Put the new code there.
3. Do not land it in a nearby file with a different concern.

---

## Naming: categorization over description

Names should say **what something is**, not every operation it performs.

### Prefer

- `billing/`
- `users/`
- `orders/`
- `schemas/`
- `repositories/`
- `tasks/`
- `components/`

### Avoid

- `billing-and-provider-handlers/`
- `get-user-data/`
- `db-helpers/`
- `shared-stuff/`
- `misc/`

If a name is difficult to derive, the concern is probably still unclear.
