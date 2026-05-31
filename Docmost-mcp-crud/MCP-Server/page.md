# MCP Server

The MCP server is implemented with `FastMCP` (from the `mcp` library) in `app/mcp_server.py`. It is mounted at `/` under the FastAPI app and exposes the MCP endpoint at `/mcp`.

The published server instructions direct clients to prefer the companion `docmost-helper` for normal read, write, and sync workflows, and to use the tools below directly for inspection or manual override. The tools remain available either way.

## Lifecycle

The MCP session manager runs inside the FastAPI lifespan context in `app/main.py`:

```python
@asynccontextmanager
async def app_lifespan(_: FastAPI):
    async with mcp.session_manager.run():
        yield
```

## Transport security

Controlled by the `MCP_ALLOWED_HOSTS` environment variable.

- If `MCP_ALLOWED_HOSTS` is set: only those Host headers are accepted (DNS-rebinding protection enabled)
- If `MCP_ALLOWED_HOSTS` is empty: DNS-rebinding protection is disabled

## Exposed tools

### Read tools

| Tool | Input | Description |
|---|---|---|
| `list_spaces` | _(none)_ | List all non-deleted spaces |
| `get_space` | `space_id: UUID` | Get one space by UUID |
| `get_space_tree` | `space_id: UUID` | Get the nested page tree for a space |
| `get_replica_standards` | _(none)_ | Get local replica naming, layout, and sync rules |
| `resolve_replica_directory_name` | `title`, `slug_id?`, `page_id?`, `existing_dir_names?` | Resolve the local directory name for a page title |
| `get_replica_structure` | `space_id: UUID`, `local_root?: str` | Get the deterministic local replica layout for a space, optionally projected into a chosen working copy |
| `create_local_replica_page` | `space_id: UUID`, `title`, `content?`, `parent_page_id?`, `parent_local_path?`, `local_root?: str`, `existing_dir_names?: str[]` | Return the canonical local-only page scaffold plan for the client to write locally |
| `get_sync_status` | `space_id: UUID`, `pages?: ClientReplicaPageIn[]`, `page_ids?: UUID[]`, `local_paths?: str[]`, `include_synced?: bool`, `local_root?: str` | Get sync status from client-reported local page state |
| `get_sync_diff` | `space_id: UUID`, `pages?: ClientReplicaPageIn[]`, `page_id?: UUID`, `local_path?: str`, `include_synced?: bool`, `local_root?: str` | Get line-based local-vs-remote diff hunks from client-reported local page state |
| `pull_replica` | `space_id: UUID`, `pages?: ClientReplicaPageIn[]`, `page_ids?: UUID[]`, `local_paths?: str[]`, `force?: bool`, `local_root?: str` | Return canonical remote snapshots the client should write locally |
| `push_replica` | `space_id: UUID`, `pages?: ClientReplicaPageIn[]`, `page_ids?: UUID[]`, `local_paths?: str[]`, `force?: bool`, `local_root?: str` | Push selected client-local page changes back to remote Docmost |
| `list_pages` | `space_id: UUID` | List all pages in a space |
| `get_page` | `space_id: UUID`, `page_id: UUID` | Get one page by UUID within its space |

### Write tools

| Tool | Input | Description |
|---|---|---|
| `create_space` | `name`, `slug`, `description?` | Create a new Docmost space |
| `delete_space` | `space_id` | Permanently delete a space and all its pages |
| `create_page` | `space_id`, `title?`, `content?`, `parent_page_id?` | Create a new page; content is markdown |
| `update_page` | `page_id`, `title?`, `content?`, `operation?` | Update title and/or content; operation: replace, append, prepend |
| `delete_page` | `page_id` | Soft-delete a page (moves to Docmost trash) |

Write tools authenticate automatically via `DOCMOST_USER_EMAIL` and `DOCMOST_USER_PASSWORD`. `create_page` and `update_page` return the page including its markdown content; `delete_page` and `delete_space` return a deletion result. Page writes are recorded in the bridge database around the remote Docmost write.

## Error handling

| Source error | MCP error |
|---|---|
| `DocmostConnectionError` | `ToolError` |
| `SpaceNotFoundError` | `ToolError` |
| `PageNotFoundError` | `ToolError` |

## Built-in instructions (published to MCP clients)

The `FastMCP` instance includes a `SERVER_INSTRUCTIONS` string that guides MCP clients on how to use the server. Key rules published:

- Start with `list_spaces` when you need to identify the correct space
- Use `get_space_tree` for the full nested hierarchy
- Use `get_replica_structure` for the deterministic local replica layout
- Use `create_local_replica_page(..., local_root?, existing_dir_names=...)` for local-first page creation in the selected working copy
- Pages are always space-scoped
- All write tool IDs must originate from live tool responses - never inferred or invented
- Prefer `update_page` over delete+create to preserve Docmost page history
- Maintain a local-first replica in the working copy being edited; if local_root is omitted, the default is `./{space_name}-replica/`
- The client owns local file IO and local sync-base storage; the server never scans the client filesystem
- Call `get_sync_status` first and pass the current client-local page state to classify local-ahead, remote-ahead, conflicting, and synced pages
- Call `get_sync_diff` before any force pull or force push choice
- `pull_replica` returns canonical remote snapshots for the client to write locally
- `push_replica` never reads the client filesystem; it only writes the client-supplied page state to Docmost
- If a sync result returns `recommended_next_action`, follow that next step instead of retrying blindly
- If local and remote both changed, return clashes before forcing a sync winner
