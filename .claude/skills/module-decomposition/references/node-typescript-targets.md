# Node and TypeScript Targets

Use this file when the repo's primary implementation language is JavaScript or TypeScript.

---

## 1. Node package/library target

```text
repo/
  package.json
  src/
    index.ts or index.js
    <domain>.ts or <domain>.js
  test/ or tests/
```

### Rules

- `index.ts`/`index.js` is the package boundary
- keep implementation out of the boundary file

---

## 2. Express or Fastify API target

```text
repo/
  package.json
  src/
    server.ts or server.js
    routes/
      <domain>.ts
    controllers/
      <domain>.ts
    services/
      <domain>.ts
    repositories/
      <domain>.ts
    schemas/ or dto/
      <domain>.ts
    middleware/
    clients/
  tests/
```

### Rules

- route registration stays thin
- controllers own transport details
- services own workflows
- repositories own data access

If the repo is small, routes and controllers may begin together, but should split when
transport and business concerns diverge.

---

## 3. Express server-rendered target

```text
repo/
  package.json
  src/ or app/
    server.ts or app.ts
    routes/
    controllers/
    services/
    views/
      <family>/
      shared/
    public/
      stylesheets/
        <family>/
        shared/
      javascripts/
        <family>/
        shared/
      images/
  tests/
```

Use this when the backend directly renders views/templates.

---

## 4. Nest application target

```text
repo/
  package.json
  src/
    main.ts
    app.module.ts
    modules/
      <domain>/
        <domain>.module.ts
        <domain>.controller.ts
        <domain>.service.ts
        dto/
        entities/
    common/
      guards/
      interceptors/
      decorators/
  test/
```

### Rules

- module folder is the primary domain boundary
- keep controller/service/entity/dto concerns explicit
- use `common/` for true cross-module framework helpers only

If the repo also owns a frontend, prefer a top-level `frontend/` workspace unless the
Nest app explicitly renders the UI.

---

## 5. Node CLI target

```text
repo/
  package.json
  src/
    cli.ts
    commands/
      <command>.ts
    services/
      <domain>.ts
  tests/
```

`cli.ts` bootstraps. Commands own transport/parsing. Services own reusable logic.

---

## 6. Worker or consumer target

```text
repo/
  package.json
  src/
    worker.ts
    jobs/ or tasks/
      <domain>.ts
    schedules/
    services/
    clients/
  tests/
```

Keep worker bootstrap, task logic, and schedules separate once they diverge.

---

## 7. Published shared package target

```text
repo/
  package.json
  src/
    index.ts
    <domain>/
      index.ts
      <concern>.ts
  tests/
```

Use nested domain folders only when the second file for that domain exists.
