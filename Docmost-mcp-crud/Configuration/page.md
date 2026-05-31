# Configuration

All configuration is supplied via environment variables. Copy `env.example` to `.env` and fill in
real values. There is no hardcoding in the application code.

## Docmost read database

Connection to the live Docmost PostgreSQL database (read-only). Two modes are supported;
`DOCMOST_DB_URL` takes priority when set.

### Option A - Full DSN

| Variable | Default | Description |
|---|---|---|
| `DOCMOST_DB_URL` | _(empty)_ | Full PostgreSQL DSN, e.g. `postgresql://docmost:PASSWORD@db:5432/docmost`. Takes priority over individual components when set. |

### Option B - Individual components (used when `DOCMOST_DB_URL` is not set)

| Variable | Default | Description |
|---|---|---|
| `DOCMOST_DB_HOST` | `db` | Hostname of the Docmost PostgreSQL container on the shared Docker network |
| `DOCMOST_DB_PORT` | `5432` | PostgreSQL port |
| `DOCMOST_DB_NAME` | `docmost` | Database name |
| `DOCMOST_DB_USER` | `docmost` | Database user |
| `DOCMOST_DB_PASSWORD` | _(empty)_ | Database password |

## Bridge state database

The service's own PostgreSQL database for bridge version and sync state, separate from Docmost's
database. `BRIDGE_DB_URL` takes priority when set.

| Variable | Default | Description |
|---|---|---|
| `BRIDGE_DB_URL` | _(empty)_ | Full PostgreSQL DSN for the bridge database. Takes priority over individual components. |
| `BRIDGE_DB_HOST` | _(empty)_ | Bridge database hostname (e.g. the `bridge-db` service) |
| `BRIDGE_DB_PORT` | `5432` | Bridge database port |
| `BRIDGE_DB_NAME` | _(empty)_ | Bridge database name |
| `BRIDGE_DB_USER` | _(empty)_ | Bridge database user |
| `BRIDGE_DB_PASSWORD` | _(empty)_ | Bridge database password |

## Docmost application (writes)

Used to authenticate and perform write operations through the Docmost REST API.

| Variable | Default | Description |
|---|---|---|
| `DOCMOST_APP_URL` | _(empty)_ | Base URL of the running Docmost web application, as reachable from inside the container (e.g. `http://<DOCMOST_CONTAINER_NAME>:3000`) |
| `DOCMOST_USER_EMAIL` | _(empty)_ | Email of the Docmost user account used for writes |
| `DOCMOST_USER_PASSWORD` | _(empty)_ | Password of that Docmost user. The login token is kept in memory only. |

## Docker network

| Variable | Default | Description |
|---|---|---|
| `DOCMOST_NETWORK_NAME` | `docmost_default` | Name of the external Docker network shared with the Docmost stack |

## Server bind

| Variable | Default | Description |
|---|---|---|
| `LISTEN_HOST` | `0.0.0.0` | Address to bind the uvicorn server to |
| `LISTEN_PORT` | `8099` | Internal port the uvicorn server listens on |
| `EXTERNAL_PORT` | `8099` | External port published by Docker Compose |

## MCP transport security

| Variable | Default | Description |
|---|---|---|
| `MCP_ALLOWED_HOSTS` | _(empty)_ | Comma-separated list of Host header values the MCP transport will accept. Required when the service is behind a reverse proxy with a custom domain. If empty, DNS-rebinding protection is disabled (not recommended for production). Example: `mcp-docmost.isaklandin.com` |

## Logging

| Variable | Default | Description |
|---|---|---|
| `MODE` | `dev` | `dev` or `prod` |
| `LOG_LEVEL` | `INFO` | `ALL`, `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |

## DSN construction logic

Both databases follow the same rule (`app/query/db.py` for Docmost, `app/bridge/db/connection.py`
for the bridge):

```
if <DB>_URL is set and non-empty:
    use <DB>_URL as DSN
else:
    build DSN from <DB>_HOST, <DB>_PORT, <DB>_NAME, <DB>_USER, <DB>_PASSWORD
```
