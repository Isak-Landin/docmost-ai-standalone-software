# Python Targets

Use this file when the repo's primary implementation language is Python.

Pick the nearest target family and combine it with other target references as needed
(data, workers, testing, monorepo, etc.).

---

## 1. Python package/library target

```text
repo/
  pyproject.toml
  src/
    <package_name>/
      __init__.py
      <domain>.py
  tests/
```

### Rules

- prefer `src/` layout for installable packages
- `__init__.py` is the public package boundary
- create subpackages only when the second file for the domain arrives

---

## 2. Flask API target

```text
repo/
  pyproject.toml or requirements.txt
  app/
    __init__.py
    config.py
    extensions.py
    blueprints/ or routes/
      <domain>.py
    services/
      <domain>.py
    repositories/ or queries/
      <domain>.py
    models/
      <entity>.py
    schemas/
      <domain>.py
  migrations/
  tests/
```

### Rules

- keep templates/static absent if the repo is API-only
- keep blueprints thin
- move workflows to services
- move reusable queries out of routes

---

## 3. Flask server-rendered target

```text
repo/
  app/
    __init__.py
    blueprints/
      <domain>/
        __init__.py
        routes.py
        forms.py
    services/
    repositories/ or queries/
    models/
    templates/
      base.html
      <family>/
        base.html
        <view>.html
      shared/
        _<partial>.html
        components/
    static/
      css/
        <family>/
        shared/
      js/
        <family>/
        shared/
      img/
  migrations/
  tests/
```

### Rules

- template family mirrors route/blueprint family
- asset family mirrors template family
- page-owned CSS/JS stays local until reuse is real

---

## 4. FastAPI API target

```text
repo/
  app/
    __init__.py
    main.py
    routers/
      __init__.py
      <domain>.py
    dependencies.py or dependencies/
    services/
      <domain>.py
    repositories/
      <domain>.py
    models/
      <entity>.py
    schemas/
      <domain>.py
  tests/
```

### Rules

- routers own HTTP concerns only
- dependencies own framework injection helpers
- services own workflows
- repositories own data access when complexity justifies them

---

## 5. FastAPI server-rendered target

```text
repo/
  app/
    main.py
    routers/
    services/
    repositories/
    schemas/
    templates/
      <family>/
      shared/
    static/
      css/
        <family>/
        shared/
      js/
        <family>/
        shared/
      img/
  tests/
```

### Rules

- only use this target if the backend truly renders UI
- otherwise prefer a separate frontend workspace

---

## 6. Django project target

```text
repo/
  manage.py
  <project_name>/
    settings.py
    urls.py
    asgi.py
    wsgi.py
  <app_name>/
    migrations/
    models.py or models/
    views.py or views/
    forms.py or forms/
    urls.py
    templates/
      <app_name>/
    static/
      <app_name>/
        css/
        js/
        img/
  tests/
```

### Rules

- app-owned UI stays with the app
- use project-level templates only for truly project-wide concerns
- use project/app split visibly

---

## 7. Python CLI target

```text
repo/
  pyproject.toml
  src/
    <package_name>/
      __init__.py
      cli.py
      commands/
        <command>.py
      services/
        <domain>.py
  tests/
```

### Rules

- `cli.py` bootstraps only
- command modules own command-specific transport/parsing
- services own reusable logic

---

## 8. Python single-service daemon target

```text
repo/
  pyproject.toml
  src/
    <package_name>/
      main.py
      service.py
      clients/
      tasks/ or jobs/
  tests/
```

Use this for long-running consumers or daemonized services.

---

## 9. Installable internal utility target

```text
repo/
  pyproject.toml
  src/
    <package_name>/
      __init__.py
      <domain>.py
  tests/
  docs/
```

Do not invent app/service directories when the repo is just a library.
