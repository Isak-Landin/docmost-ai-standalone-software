# Worker, CLI, and Automation Targets

Use this file when the repo owns workers, consumers, scheduled jobs, CLI tools, or
operational automation.

---

## 1. Queue worker target

```text
repo/
  <code-root>/
    worker.py or worker.ts
    tasks/ or jobs/
      <domain>.py or .ts
    services/
    repositories/ or queries/
    clients/
  tests/
```

### Rules

- worker bootstrap owns startup only
- task modules own queue/job handling
- reusable business logic stays in services

---

## 2. Scheduler target

```text
repo/
  <code-root>/
    scheduler.py or scheduler.ts
    schedules/
      <domain>.py or .ts
    tasks/ or jobs/
    services/
```

### Rules

- schedule definitions do not own task logic
- task logic does not belong in scheduler bootstrap

---

## 3. Event consumer target

```text
repo/
  <code-root>/
    consumer.py or main.ts
    handlers/
      <event_family>.py or .ts
    services/
    repositories/
    clients/
```

Use handlers by event family when multiple consumer domains exist.

---

## 4. CLI target

```text
repo/
  <code-root>/
    cli.py or cli.ts
    commands/
      <command>.py or .ts
    services/
    clients/
  tests/
```

### Rules

- command parsing/bootstrap stays in CLI layer
- domain logic remains reusable under services

---

## 5. Script collection target

Use this for real script collections, not ad hoc dumping grounds.

```text
repo/
  scripts/
    dev/
    ops/
    data/
```

### Rules

- group scripts by operational concern
- if scripts gain shared logic, extract a proper CLI or service package

---

## 6. One-off script exception

A single maintenance script may stay as one file while:

- it is single-use or single-concern
- it does not justify a reusable command package yet

Once multiple scripts share bootstrap or command behavior, move toward a CLI structure.
