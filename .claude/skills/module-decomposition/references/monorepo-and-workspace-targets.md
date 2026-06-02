# Monorepo and Workspace Targets

Use this file when one repository owns multiple apps, packages, or services.

---

## 1. Basic monorepo target

```text
repo/
  apps/
    <app-one>/
    <app-two>/
  packages/ or libs/
    <shared-package>/
  deploy/
  scripts/
  tests/                   # only for truly cross-workspace tests
```

### Rules

- app-local code stays in the app by default
- shared packages require real multi-app ownership
- infra/tooling concerns stay at monorepo root or dedicated tooling packages

---

## 2. Backend + frontend workspace target

```text
repo/
  apps/
    backend/
    frontend/
  packages/
    shared-types/
    shared-ui/             # only if truly shared
  deploy/
  scripts/
```

### Rules

- do not force shared packages when only one app owns the code
- shared types/UI must not depend on app-local code

---

## 3. Multi-service backend target

```text
repo/
  services/
    api/
    worker/
    admin/
  packages/
    shared-domain/
    shared-clients/
  deploy/
```

### Rules

- a service owns its local transport/bootstrap/workflow code
- shared packages only own stable cross-service concerns

---

## 4. Workspace package thresholds

Create a shared package when:

- two or more apps/services actively depend on the same concern
- that concern has stable ownership separate from any one app

Do not create one when:

- reuse is speculative
- the code still changes primarily because one app changes
- the shared package would need app-specific imports

---

## 5. Tooling packages

If build tooling, lint config, or codegen logic becomes substantial, a dedicated tooling
package may be justified:

```text
repo/
  tooling/
    <tool-package>/
```

Use this only when root scripts/config are no longer enough.
