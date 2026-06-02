# Layer Interaction Patterns

This document defines how common repo layers interact structurally.

The problem it solves is not "which directory name is correct?" but "which layers are
allowed to know about which other layers, and in what direction?"

---

## Backend web pattern

### Preferred direction

```text
route/controller -> service -> repository/query -> model/entity
route/controller -> schema/serializer
service -> provider client
service -> model/entity
repository/query -> model/entity
```

### Avoid

```text
route/controller -> provider client
route/controller -> raw data layer everywhere
model/entity -> provider client
repository/query -> route/controller
```

### Ownership

- routes/controllers own transport only
- services own workflows/orchestration
- repositories/queries own data access
- models/entities own persistence shape
- schemas/serializers own external or transport shape

---

## Server-rendered pattern

### Preferred direction

```text
route/view function -> service -> repository/query
route/view function -> template
template -> shared partial/component
template family -> page asset
page asset -> shared asset
```

### Avoid

```text
template -> database
template -> provider client
shared asset -> unrelated page-specific logic
```

### Ownership

- template directories follow route/view family
- page assets stay page-owned until reuse is real
- shared assets own cross-page or cross-family concerns only

---

## API-only backend pattern

If the backend is API-only:

- keep templates/static absent
- do not invent a fake server-rendered tree
- prefer a separate frontend workspace when one exists

---

## Frontend SPA pattern

### Preferred direction

```text
page -> feature module -> shared component
page/feature -> client-side service/api module
feature -> state container or hook/composable
shared component -> shared style/token/module
```

### Avoid

```text
shared component -> page module
component library -> app-specific service
page -> raw fetch scattered everywhere without service/client ownership
```

### Ownership

- pages own route composition
- features own domain-local behavior when multiple files share a concern
- components own reusable presentation
- services/api own outbound API access
- hooks/composables own reusable UI logic

---

## Worker pattern

### Preferred direction

```text
worker bootstrap -> task/job module -> service -> repository/query
scheduler -> task/job module
task/job module -> provider client
```

### Avoid

```text
worker bootstrap -> business logic
task/job module -> controller/router
scheduler -> domain logic
```

### Ownership

- bootstrap starts the worker
- tasks/jobs own message handling and task-level flow
- services own reusable domain logic
- schedules own recurrence definitions only

---

## CLI pattern

### Preferred direction

```text
cli entrypoint -> command module -> service -> repository/query or provider client
```

### Avoid

```text
command parser -> all business logic inline
service -> command module
```

### Ownership

- CLI entrypoint owns parser/bootstrap
- command modules own command dispatch
- services own reusable logic

---

## Data-heavy pattern

### Preferred direction

```text
transport/task/service -> repository/query layer -> model/entity -> database
migration tool -> migration files
seed/bootstrap -> seed files or dedicated bootstrap modules
```

### Avoid

```text
random transport modules -> ad hoc raw SQL everywhere
migration logic -> route/controller
schema bootstrap -> mixed into unrelated runtime files
```

### Ownership

- migrations own schema evolution
- seed files own data bootstrap
- repository/query modules own reusable reads/writes
- model/entity layer owns persistence shapes

---

## Monorepo pattern

### Preferred direction

```text
app -> local modules
app -> shared package only when ownership is truly shared
shared package -> no app-specific imports
```

### Avoid

```text
shared package -> app-local code
every app -> giant dumping-ground shared package
```

### Ownership

- app-local logic stays local by default
- shared packages require clear cross-app ownership and reuse
- workspace tooling stays at monorepo root or dedicated tooling package
