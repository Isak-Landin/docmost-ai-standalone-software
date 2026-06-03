All configuration is supplied via environment variables. The server reads `.env`; the helper reads `helper/.env`. Copy the matching `*.example` file and fill in real values. There is no hardcoding in application code.

## Server: Docmost database (read path)

`DOCMOST_DB_URL` takes priority when set; otherwise the individual values are used.

| Variable | Default | Description |
| --- | --- | --- |
| `DOCMOST_DB_URL` | (empty) | Full Docmost PostgreSQL DSN |
| `DOCMOST_DB_HOST` | `db` | Docmost DB host on the shared network |
| `DOCMOST_DB_PORT` | `5432` | Port |
| `DOCMOST_DB_NAME` | `docmost` | Database name |
| `DOCMOST_DB_USER` | `docmost` | User |
| `DOCMOST_DB_PASSWORD` | (empty) | Password |

## Server: bridge database (version state)

`BRIDGE_DB_URL` takes priority when set; otherwise the individual values are used.

| Variable | Default | Description |
| --- | --- | --- |
| `BRIDGE_DB_URL` | (empty) | Full bridge PostgreSQL DSN |
| `BRIDGE_DB_HOST` | `bridge-db` | Bridge DB host (the bridge-db service) |
| `BRIDGE_DB_PORT` | `5432` | Port |
| `BRIDGE_DB_NAME` | `docmost_bridge` | Database name |
| `BRIDGE_DB_USER` | `docmost_bridge` | User |
| `BRIDGE_DB_PASSWORD` | (empty) | Password |

## Server: Docmost application (write path)

| Variable | Description |
| --- | --- |
| `DOCMOST_APP_URL` | Base URL of the running Docmost web app (for example `http://docmost:3000`) |
| `DOCMOST_USER_EMAIL` | Docmost user for write auth; token held in memory only |
| `DOCMOST_USER_PASSWORD` | Docmost user password |

## Server: network, bind, transport, logging, worker

| Variable | Default | Description |
| --- | --- | --- |
| `DOCMOST_NETWORK_NAME` | `docmost_default` | External Docker network shared with Docmost |
| `LISTEN_HOST` | `0.0.0.0` | Bind host inside the container |
| `LISTEN_PORT` | `8099` | Internal port |
| `EXTERNAL_PORT` | `8099` | Published port |
| `MCP_ALLOWED_HOSTS` | (empty) | Host headers the `/mcp` transport accepts; empty disables DNS-rebinding protection |
| `WORKER_INTERVAL_SECONDS` | `15` | Seconds between observer worker passes |
| `MODE` | `dev` | `dev` or `prod` |
| `LOG_LEVEL` | `INFO` | `ALL`, `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

## Helper: `helper/.env`

| Variable | Required | Description |
| --- | --- | --- |
| `DOCMOST_MCP_SERVER_URL` | Yes | Base URL of the running server (the helper calls `/v1`, `/helper/v1`, `/auto-mcp`) |
| `DOCMOST_REPLICA_BASE` | No | Directory under which the helper discovers replicas by `_replica.json` space id. Defaults to the helper's current working directory. |

## DSN selection

For each database, if the `*_DB_URL` is set and non-empty it is used as the DSN; otherwise the DSN is built from the individual host / port / name / user / password values.