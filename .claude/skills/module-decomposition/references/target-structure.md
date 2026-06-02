# Target Structure

This document defines **where code belongs in the repo** by describing ownership
patterns rather than one repo's exact paths.

Use the smallest applicable subset. Do **not** pre-create every section in a new repo.

This is a **repo, package, and directory structure** document. It is not an in-file
HTML/CSS/JS implementation guide.

---

## Root-level guidance

Most repos benefit from a small, stable root:

```text
repo/
  README.md
  docs/                 # Project docs when the repo owns long-term documentation
  scripts/              # Operational or development scripts
  tests/                # Automated tests
  deploy/               # Docker, Compose, Kubernetes, Terraform, runtime manifests
  <code-root>/          # Usually app/, src/, package name, services/, frontend/, etc.
```

Choose one primary application root unless the repo is intentionally multi-service.

Common valid code roots:

- `app/`
- `src/`
- `<package_name>/`
- `services/`
- `frontend/`
- `backend/`

Avoid mixing multiple roots without a clear reason.

When a backend and frontend are owned separately, make that split visible at the root:

```text
repo/
  backend/
  frontend/
  deploy/
  tests/
```

---

## Python web backend pattern

Use this when the repo owns a Flask, FastAPI, Django, or similar backend surface.

```text
<code-root>/
  main.py or __init__.py    # entrypoint or app factory only
  config.py                 # configuration
  routes/ or routers/       # HTTP registration surface
    <domain>.py
  services/                 # business logic
    <domain>.py
  repositories/ or queries/ # data access when separated from services
    <domain>.py
  models/                   # ORM or persistence models
    <entity>.py
  schemas/                  # Pydantic, Marshmallow, serializers, DTOs
    <domain>.py
  dependencies/             # framework dependency injection or request-scoped helpers
  templates/                # if server-rendered
  static/                   # if server-rendered or asset-owned
```

### Ownership

- entrypoint/app factory: bootstrap and wiring only
- routes/routers: HTTP concerns only
- services: business workflows
- repositories/queries: data access concerns
- models: persistence shape
- schemas: request/response/data-transfer shape

### Framework notes

- Flask often uses `__init__.py`, blueprints, templates, and static assets
- FastAPI often uses `main.py`, `routers/`, `schemas/`, and dependency injection
- Django keeps stronger framework conventions, but the same concern boundaries still apply

---

## Backend-owned HTML/CSS/JS surfaces

Use these sections when the backend itself owns templates, views, and first-party
assets. These are generalized nested structures derived from common documented framework
patterns, not copied from any one repo.

### Flask-style server-rendered structure

Generalized from Flask's tutorial package layout and template/static organization.

```text
repo/
  <package_name>/
    __init__.py
    routes/ or blueprints/
      <domain>.py
    templates/
      <domain>/
      shared/
    static/
      css/
        <domain>/
        shared/
      js/
        <domain>/
        shared/
      img/
  tests/
```

Use this when the Flask backend renders HTML itself.

### Django app-owned structure

Generalized from Django's reusable-app documentation, where app-owned templates and
static files stay inside the app package.

```text
repo/
  manage.py
  <project_name>/
  <app_name>/
    migrations/
    templates/
      <app_name>/
    static/
      <app_name>/
        css/
        js/
        img/
    views.py or views/
    models.py or models/
    urls.py
  templates/              # project-level templates only when truly project-owned
```

Use app-local `templates/<app_name>/` and `static/<app_name>/` for backend-owned UI so
the app remains self-contained.

### FastAPI / Starlette with server-rendered surfaces

FastAPI's documented "bigger applications" structure is API-first. When the same app
also owns templates and static assets, keep those surfaces inside the application root
instead of inventing a second pseudo-frontend tree inside it.

```text
repo/
  app/
    main.py
    routers/
    dependencies/
    services/
    schemas/
    templates/
      <domain>/
      shared/
    static/
      css/
        <domain>/
        shared/
      js/
        <domain>/
        shared/
      img/
  tests/
```

If the FastAPI backend is API-only, prefer a separate `frontend/` workspace instead.

### Express / Fastify server-rendered structure

Generalized from Express's documented generator skeleton, which separates routes, views,
and public assets.

```text
repo/
  src/ or app/
    routes/
    controllers/
    services/
    views/
      <domain>/
      shared/
    public/
      stylesheets/
        <domain>/
        shared/
      javascripts/
        <domain>/
        shared/
      images/
  tests/
```

Use this when the Node backend renders templates directly.

### Nest default structure

Nest is usually documented and used as an API/backend application first. The default
generalized structure is:

```text
repo/
  src/
    modules/
    common/
  test/
```

If HTML/CSS/JS are owned by the same overall repo, prefer a visible split:

```text
repo/
  src/                    # Nest backend
  frontend/               # separate web app or SSR app
```

Only add backend-owned `views/` or `public/` surfaces when the Nest app is explicitly
responsible for server-rendered output.

### Rule for all backend-owned frontend surfaces

- HTML templates/views belong with the backend that renders them
- CSS/JS asset trees belong next to that backend's template/view surface
- Shared assets are justified by real reuse, not convenience
- Avoid umbrella asset containers such as `families/` or root `app.css` / `app.js`
- If the backend is API-only, do not fake a backend-owned template/static tree
- If the frontend is its own application, give it its own top-level workspace

---

## Node / TypeScript backend pattern

Use this when the repo owns Express, Fastify, Nest, or similar services.

```text
src/
  server.ts or main.ts      # bootstrap only
  routes/ or controllers/   # transport surface
  services/                 # business logic
  repositories/             # data access
  models/ or entities/      # persistence/domain entities
  schemas/ or dto/          # validation and transport shapes
  middleware/               # transport middleware
  clients/                  # outbound API clients
```

Keep controllers/routes thin. Keep data access out of controllers.

---

## Server-rendered web pattern

Use this when a backend owns templates/views and first-party assets, regardless of
language or framework.

```text
templates/
  base.html
  <family>/
    base.html
    <view>.html
  shared/
    _<partial>.html
    components/
      _<component>.html

static/
  css/
    <family>/
      <view>.css
    shared/
      <concern>.css
  js/
    <family>/
      <view>.js
    shared/
      <concern>.js
  vendor/
```

### Rules

- family names mirror the real route or template family
- page-owned assets stay page-owned until reuse is real
- shared assets are for verified reuse, not convenience dumping
- avoid umbrella containers such as `families/`, `pages/`, or root `app.css` / `app.js`
- keep this as repo/directory structure guidance, not as a template/CSS/JS coding guide

---

## Frontend SPA pattern

Use this when the repo owns a React, Vue, Svelte, or similar frontend app.

```text
src/
  app/ or router/          # app shell and route registration
  pages/                   # route-owned pages
  components/              # shared reusable UI
  features/                # feature-local modules when multiple files share a domain
  hooks/ or composables/   # shared view logic
  services/ or api/        # client-side API access
  state/                   # shared state containers if present
  styles/                  # shared design system or tokens
  assets/                  # static assets
```

### Rules

- page files own composition for one route
- shared components move to `components/` only after real reuse
- feature folders are justified when two or more files share a product/domain concern

---

## Worker / job pattern

Use this when the repo owns background jobs, schedulers, queues, or consumers.

```text
<code-root>/
  worker.py or main.py     # worker bootstrap only
  tasks/ or jobs/
    <domain>.py
  schedules/               # recurring-job definitions when separate
  clients/                 # outbound clients
  services/                # reusable domain logic
```

Keep scheduling concerns separate from task implementation when they evolve independently.

---

## Shared library pattern

Use this when the repo owns reusable internal packages.

```text
<code-root>/
  <library_name>/
    __init__.py or index.ts
    <domain>.py or <domain>.ts
```

Only create nested directories when the second file for that sub-domain appears.

---

## Database and migrations

Common migration homes:

```text
migrations/
alembic/
prisma/migrations/
db/migrations/
```

Choose the tool-native structure and keep schema evolution there.

Data access concerns usually belong in one of:

- `repositories/`
- `queries/`
- `models/` for ORM definitions only
- `db/` for connection/bootstrap concerns

---

## Infrastructure and deployment

Use a separate deploy/runtime surface rather than mixing these files into app modules.

```text
deploy/
  docker/
  compose/
  k8s/
  terraform/

Dockerfile
docker-compose.yml
compose.yaml
```

### Rules

- One Dockerfile per runtime surface unless the repo intentionally uses a multi-stage shared image
- Environment-specific variants live under a deploy grouping when more than one becomes necessary
- Infra code is not application business logic

---

## Tests

Tests may start flat, but when multiple concerns exist a common structure is:

```text
tests/
  unit/
  integration/
  contract/
  e2e/
```

Only introduce the deeper split when the repo actually needs it.
