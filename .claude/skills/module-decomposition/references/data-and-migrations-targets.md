# Data and Migrations Targets

Use this file when data access, schema change, query complexity, or migration behavior
is a first-class concern in the repo.

---

## 1. ORM-backed application target

```text
repo/
  <code-root>/
    models/ or entities/
    repositories/ or queries/
    services/
  migrations/ or alembic/ or prisma/migrations/
  tests/
```

### Rules

- models/entities define persistence shape
- repositories/queries own reusable data access
- services own workflows using that data
- migrations own schema evolution

---

## 2. Query-heavy service target

Use this when dynamic query building, reporting, filtering, or analytics is substantial.

```text
repo/
  <code-root>/
    repositories/
      <domain>.py or .ts
    queries/
      reports/
      search/
      filters/
    models/
    services/
  migrations/
  tests/
```

### Rules

- separate query families when they change independently
- reporting/search/filter builders should not hide inside transport files

---

## 3. Migration-heavy target

Use this when schema change is frequent or governed by a migration tool.

```text
repo/
  migrations/ or alembic/ or prisma/migrations/
  seeds/ or fixtures/
  <code-root>/
    models/
    repositories/
```

### Rules

- schema migrations and seed/data bootstrap are different concerns
- do not mix seed logic into migration revisions unless the repo's toolchain explicitly requires it

---

## 4. Raw SQL or low-level DB target

Use this when the repo uses direct SQL heavily instead of a full ORM.

```text
repo/
  <code-root>/
    db/
      connection/
      queries/
      lifecycle/ or writes/
      schema/ or bootstrap/
    services/
  tests/
```

### Rules

- connection/bootstrap concerns do not own queries
- read queries and write/state-transition concerns separate when they evolve differently

---

## 5. Seed and fixture target

```text
repo/
  seeds/
  fixtures/
  tests/
```

Use separate homes when:

- the repo has reusable dev/test bootstrap data
- seed logic changes independently of schema revisions
