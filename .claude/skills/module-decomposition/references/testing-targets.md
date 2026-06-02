# Testing Targets

Use this file when deciding where tests, fixtures, snapshots, factories, and end-to-end
artifacts belong.

---

## 1. Flat test target

Valid for small repos:

```text
repo/
  tests/
    test_<domain>.py or .ts
```

Do not over-structure early.

---

## 2. Layered test target

Use when the repo has multiple testing concerns.

```text
repo/
  tests/
    unit/
    integration/
    contract/
    e2e/
```

### Rules

- only create the deeper split when the second concern really exists
- do not mix e2e/browser suites into unit test directories

---

## 3. Colocated frontend test target

Use when the frontend ecosystem favors colocated component tests.

```text
src/
  components/
    <component>/
      <component>.tsx
      <component>.test.tsx
```

This is acceptable when the repo's frontend tooling expects colocated tests.

---

## 4. Fixture and factory target

```text
repo/
  tests/
    fixtures/
    factories/
    data/
```

### Rules

- fixtures own static or reusable test inputs
- factories own generated object creation logic
- test data for integration/e2e can live under a deeper suite-local data directory if needed

---

## 5. Snapshot target

Keep snapshots close to the test system that owns them.

Examples:

- frontend snapshot directories beside component tests
- API contract snapshots under contract tests

Do not create one global snapshot dumping ground.

---

## 6. Cross-workspace tests

In monorepos, only use a repo-root test workspace when the test genuinely spans multiple
apps or packages. Otherwise keep tests near the owning app/package.
