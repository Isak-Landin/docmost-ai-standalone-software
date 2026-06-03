There are two MCP-shaped surfaces. They are not interchangeable.

## The model surface is the helper, not `/mcp`

The consuming model (Claude Code) uses the `docmost-helper` stdio MCP for all reads, writes, and sync. The helper owns local replica file IO and talks to the server over REST (`/v1`, `/helper/v1`, `/auto-mcp`). The helper is documented on the Replica System and REST API pages and in `helper/README.md`.

## The `/mcp` endpoint is an operator fallback

`app/mcp_server.py` builds a `FastMCP` instance mounted at `/mcp` (streamable HTTP). It exists only for manual operator inspection and emergency override when the helper is unavailable. Do not register it as the model's surface.

Its published `SERVER_INSTRUCTIONS` state plainly that this surface is not the model's workflow surface, that the model uses `docmost-helper`, and that the helper reaches the server over REST and never over `/mcp`.

### Transport security

Controlled by `MCP_ALLOWED_HOSTS`. If set, only those Host headers are accepted (DNS-rebinding protection). If empty, protection is disabled (not recommended in production).

### Operator tools

The `/mcp` surface exposes reads (`list_spaces`, `get_space`, `get_space_tree`, `list_pages`, `get_page`), bridge-state inspection (`get_sync_status`, `get_sync_diff`), the server-side replica planners, and low-level write tools. These are for inspection and emergency use; routine work goes through the helper and the reconcile flow so version state stays aligned.

## Why the split

The server owns Docmost integration, bridge version truth, normalization, and remote writes. The helper owns local replica file IO and initiates reconcile. Keeping the model on the helper means every change the model makes flows through the bridge write pipeline and the reconcile brain, so heads, versions, and local sync bases stay consistent. A direct `/mcp` write by the model would bypass that discipline, which is why `/mcp` is reserved for operators.