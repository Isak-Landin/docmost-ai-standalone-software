# Docmost Helper

Client-side stdio MCP server. Handles local replica file IO, sync workflows, and stash operations. The consuming model calls this helper for all Docmost operations — never the server-side MCP directly.

## Setup

```bash
cd helper
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Edit .env — set DOCMOST_MCP_SERVER_URL to the running server base URL
```

## Registration in `.mcp.json`

Add to the repo-root `.mcp.json`:

```json
{
  "mcpServers": {
    "docmost-helper": {
      "type": "stdio",
      "command": "/absolute/path/to/docmost-mcp-server/helper/.venv/bin/python3",
      "args": ["/absolute/path/to/docmost-mcp-server/helper/server.py"]
    }
  }
}
```

The helper stdio server is additive — it loads alongside any other MCPs registered in `.mcp.json` or the Claude home config.

## Environment

| Variable | Required | Description |
|---|---|---|
| `DOCMOST_MCP_SERVER_URL` | Yes | Base URL of the running docmost-mcp server |

The helper reads `.env` from the `helper/` directory at startup via `python-dotenv`.

## Contracts

- Route prefix on server: `/helper/v1/` — do not change without updating `client.py`
- Batch sync uses: `/auto-mcp/spaces/{space_id}/pages/apply` — existing server surface, do not retire
- `DOCMOST_MCP_SERVER_URL` env var name is locked — matches this README and `.env.example`
