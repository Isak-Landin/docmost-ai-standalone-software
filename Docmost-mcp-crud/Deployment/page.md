# Deployment

## Overview

The service is deployed as a Docker container on the same server as the live Docmost stack, joined to
the same Docker network so it can reach the Docmost PostgreSQL container and the Docmost web app. It
runs alongside its own bridge-state database container.

## Docmost version requirement

**Docmost v0.71.1 or later is required for content write operations to work.**

This is a dependency on Docmost's own request pipeline, not on this service:

- Docmost applies a global NestJS `ValidationPipe({ whitelist: true })`, which strips any request
  field not declared on the target DTO.
- In versions before 0.71.1, `CreatePageDto` and `UpdatePageDto` did not declare `content` or
  `format`, so the whitelist silently dropped them and pages were created empty.
- From 0.71.1, both DTOs declare `content` and `format` (and `update` declares `operation`), so the
  bridge's markdown writes pass through, are parsed (markdown -> HTML -> ProseMirror JSON), and are
  persisted (create writes directly; update routes through the Docmost collaboration gateway).

To check the version running on your Docmost host:

```bash
docker exec <docmost-container> cat /app/apps/server/package.json | grep '"version"' | head -1
```

To update Docmost safely (no volume loss):

```bash
docker compose pull docmost
docker compose up -d --no-deps docmost
```

## Docker Compose

`docker-compose.yml` defines two services:

- `bridge-db` - a PostgreSQL container holding the bridge state database, with a healthcheck.
- `docmost-mcp` - the service container, built from the `Dockerfile`. It `depends_on` `bridge-db`
  being healthy before starting.

Key configuration:
- Reads env from `.env` via `env_file`
- Sets Docmost-DB, bridge-DB, Docmost-app, and server env vars from `.env` values
- Publishes `EXTERNAL_PORT` (default 8099) -> `LISTEN_PORT` (default 8099)
- Joins the `docmost_network` Docker network (external)
- Persists the bridge database in the `bridge_db_data` volume

## Network requirement

`docmost_network` must already exist as an external Docker network. Its name defaults to
`docmost_default` and is set by `DOCMOST_NETWORK_NAME`. This is the network created by the live
Docmost Docker Compose stack. If your Docmost network has a different name, set
`DOCMOST_NETWORK_NAME` in `.env`.

## Setup steps

1. Clone this repository onto the server running Docmost
2. Copy `env.example` to `.env` and fill in values:
   - Docmost read-database credentials (`DOCMOST_DB_*`)
   - Bridge-database credentials (`BRIDGE_DB_*`)
   - Docmost app URL and user credentials for writes (`DOCMOST_APP_URL`, `DOCMOST_USER_*`)
   - Allowed MCP hosts and network name as needed
3. Ensure the external Docmost Docker network exists (default `docmost_default`)
4. Run:
   ```bash
   docker compose up -d --build
   ```

Verify with:
```bash
curl http://localhost:8099/health
# → {"ok": true}
```

## Dockerfile

The Dockerfile is based on `python:3.12-slim`, installs Python dependencies from `requirements.txt`,
copies in `app/`, and runs the service with uvicorn:

```
uvicorn app.main:app --host ${LISTEN_HOST:-0.0.0.0} --port ${LISTEN_PORT:-8099}
```

## MCP client integration

On the remote machine, add the MCP server to your MCP-compatible client pointing to:

```
https://<YOUR_HOST>:<EXTERNAL_PORT>/mcp
```

If using a reverse proxy with a custom domain, set `MCP_ALLOWED_HOSTS` in `.env` to that domain.

## Runtime defaults

| Setting | Default |
|---|---|
| Listen host | `0.0.0.0` |
| Listen port | `8099` |
| External port | `8099` |
