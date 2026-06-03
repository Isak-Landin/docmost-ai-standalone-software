The service deploys as three Docker containers on the same server and Docker network as the live Docmost stack.

## Docmost version requirement

Docmost v0.71.1 or later is required for content write operations. Earlier versions did not declare `content` / `format` on the page DTOs, so NestJS `ValidationPipe({ whitelist: true })` silently stripped page content. Check the running version:

```bash
docker exec docmost cat /app/apps/server/package.json | grep '"version"' | head -1

```

Docmost upgrades are non-destructive (data lives in PostgreSQL):

```bash
docker compose pull docmost && docker compose up -d docmost

```

## Compose services (`docker-compose.yml`)

| Service | Role |
| --- | --- |
| `bridge-db` | PostgreSQL 16 for bridge-owned version state (healthchecked) |
| `docmost-mcp` | FastAPI app: REST + helper routes + operator `/mcp` |
| `docmost-mcp-worker` | runs `python -m app.observer.worker --loop` (interval observer over all spaces) |

Both app services build from the same `Dockerfile`, read `.env` via `env_file`, depend on a healthy `bridge-db`, and join the external network named by `DOCMOST_NETWORK_NAME`. Only `docmost-mcp` publishes a port (`EXTERNAL_PORT` -> `LISTEN_PORT`).

## Setup

1. Place the project on the Docmost host and `cp env.example .env`.
2. Fill in the Docmost DB, bridge DB, `DOCMOST_APP_URL` + user credentials, network name, ports, `MCP_ALLOWED_HOSTS`, and `WORKER_INTERVAL_SECONDS`.
3. Ensure the external Docmost network exists (`docker network ls | grep docmost`).
4. Start:

```bash
docker compose up -d --build

```

## Verify

```bash
docker compose ps
curl http://<host>:8099/health     # {"ok": true} (process only)
curl http://<host>:8099/spaces     # 200 with spaces, or 503 if the DB is unreachable

```

REST docs are at `/docs`; the operator MCP endpoint is at `/mcp` (or `https://<host>/mcp` behind a proxy with `MCP_ALLOWED_HOSTS` set).

## Updating

```bash
docker compose up -d --build     # after code or dependency changes
docker compose restart           # restart without rebuilding
docker compose logs -f docmost-mcp docmost-mcp-worker

```

## Helper deployment

The helper runs on the machine where Claude Code runs, not on the Docmost host. See the Replica System page and `helper/README.md` for venv setup, `helper/.env`, and registration as a stdio MCP.