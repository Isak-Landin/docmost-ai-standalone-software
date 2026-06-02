# Dependency Surfaces

This document maps common libraries, frameworks, and tooling families to the structural
surfaces they usually introduce.

The purpose is **coverage**, not obligation:

- if a repo does not use a dependency family, ignore that section
- if a repo does use a dependency family, make sure its structural surface has a home

---

## HTTP frameworks

### Flask

Typical surfaces:

- app factory or bootstrap
- blueprints or route modules
- forms, templates, static assets
- services for non-HTTP business logic

When Flask renders HTML itself, the repo usually needs a backend-owned `templates/`
and `static/` surface under the application package.

### FastAPI / Starlette

Typical surfaces:

- ASGI entrypoint
- routers
- dependencies
- Pydantic schemas
- services and repositories

FastAPI is commonly API-first. Add backend-owned `templates/` and `static/` only when
the backend truly serves HTML and first-party assets.

### Django

Typical surfaces:

- app modules
- models
- views
- forms/serializers
- migrations
- templates/static

Django commonly wants template and static ownership visible at the app level, not only
at project root.

### Express / Fastify / Nest

Typical surfaces:

- server bootstrap
- routes/controllers
- middleware/guards
- services
- repositories/entities/dto depending on stack style

Express commonly uses server-rendered `views/` and public asset directories when the
backend owns the rendered UI. Nest is more commonly API-first; backend-owned frontend
surfaces should be explicit exceptions, not assumed defaults.

---

## Data and migration stacks

### SQLAlchemy / SQLModel / Django ORM

Typical surfaces:

- models
- repositories/queries
- DB session or connection management
- migrations

### Alembic / Flask-Migrate / Django migrations / Prisma / Knex

Typical surfaces:

- migration config
- migration revision files
- schema evolution ownership separate from request handlers

---

## Validation and schema libraries

### Pydantic / Marshmallow / Zod / Joi

Typical surfaces:

- request schemas
- response schemas
- DTOs / validation models

These usually deserve a schema-focused home rather than living in route/controller files.

---

## Async, background, and queue stacks

### Celery / RQ / Huey / BullMQ / Sidekiq-like patterns

Typical surfaces:

- worker bootstrap
- task modules
- retry / schedule modules
- queue integration helpers

Task definition, scheduling, and service/business logic should not all collapse into one file.

---

## Frontend stacks

### React / Vue / Svelte

Typical surfaces:

- pages/routes
- shared components
- hooks/composables
- state containers
- client-side API services
- shared styles/tokens

### Vanilla JS / CSS / server-rendered templates

Typical surfaces:

- template families
- page-owned scripts and styles
- shared component assets
- shared partials/macros

These are directory-ownership concerns for this skill, not in-file styling or scripting
guidance.

---

## Outbound clients and SDKs

### Payment SDKs / cloud provider SDKs / internal service clients / requests / fetch wrappers

Typical surfaces:

- client/bootstrap helpers
- service-domain callers
- mapping/adapter code between provider payloads and internal models

These belong with service/client concerns, not inside routes, controllers, or templates.

---

## CLI and automation stacks

### Click / Typer / argparse / Commander

Typical surfaces:

- CLI entrypoint
- commands/
- reusable service logic called by commands

Keep command parsing separate from reusable application logic.

---

## Observability stacks

### OpenTelemetry / Prometheus / Sentry / logging wrappers

Typical surfaces:

- instrumentation setup
- shared telemetry helpers
- middleware/hooks if framework-owned

Instrumentation should not sprawl across business files when a shared concern file will do.

---

## Containerization and deployment

### Docker / Compose / Kubernetes / Terraform / Helm

Typical surfaces:

- Dockerfiles
- runtime manifests
- environment-specific deployment config
- infra modules

These should live in a deployment surface, not be mixed into application package trees.
