## Surfaces: one model surface, one operator surface

The docmost bridge exposes two MCP-shaped surfaces; the consuming model uses only one.

- docmost-helper (stdio) - the model's sole Docmost surface. It owns local replica file IO and runs the automated reconcile. Tools: reads (list_spaces, get_space, get_space_tree, list_pages, get_page), the three sync tools (sync_space, sync_page, sync_page_tree), resolution (resolve_conflict, confirm_deletion), and low-level escape hatches (create/update/delete/move page, create/delete space, push_pages, pull_pages, and the stash tools).
- docmost-mcp (HTTP, the server's `/mcp`) - a quiet operator and inspection fallback only. It is NOT registered as a model MCP. A human operator reaches it directly when needed; the model never uses it.

## How it is registered in this environment

The Claude home is `/home/isakuser/claude-docmost-mcp` (the value of `CLAUDE_CONFIG_DIR`). Claude and Copilot are entirely separate systems; this is a Claude home and has no relationship to any Copilot home.

Claude home (user scope):

- `.claude.json` - the live config Claude Code reads. mcpServers: docmost-helper (stdio; command is this repo's `helper/.venv/bin/python` running `helper/server.py`), docker-mcp, chrome-devtools.
- `skills/` - the general, cross-project skills.

Repo (project scope), at `/home/isakuser/docmost-mcp-server/.mcp.json`:

- No MCP servers. The file is intentionally empty (`{"mcpServers": {}}`). It is also gitignored (a local-only file).

When Claude Code runs inside the repo, the model loads only the three home MCPs (docmost-helper, docker-mcp, chrome-devtools). The operator `/mcp` is deliberately absent from the model's scope.

## The model scope must not include the operator MCP

The repo `.mcp.json` previously registered the operator `docmost-mcp` HTTP MCP. Because `.mcp.json` is project scope, that pushed the operator surface and its instructions onto the model whenever Claude Code ran in this repo - out of scope for the model, whose only Docmost surface is the helper. It was removed. The tracked `claude.json.example` now shows the correct registration: the `docmost-helper` stdio entry, not the operator HTTP MCP.

## The split, and what lives where

- The model surface (docmost-helper) is registered once, in the Claude home, so it is available in every session while still running this repo's code via absolute paths.
- The operator `/mcp` is not a model MCP in any scope. It is a server endpoint a human can inspect directly.
- MCPs are kept disjoint across scopes - a single MCP loaded from two scopes double-counts its tools.
- Skills live in one scope only: the Claude home. Skills belong in the Claude home, not the target repo.

## Why the split exists (Claude Code scopes)

Claude Code resolves MCPs and skills from more than one scope:

- Project scope: a repo's `.mcp.json` (MCPs). Loads only when Claude Code runs in that directory.
- User / home scope: `$CLAUDE_CONFIG_DIR/.claude.json` (MCPs) and `$CLAUDE_CONFIG_DIR/skills/` (skills). Loads in every session, across all projects.

Placement follows from that: the helper is the model's primary surface and belongs in the home so it is always available; general tools (docker-mcp, chrome-devtools) and the skills are cross-project and also live in the home; the operator `/mcp` is not the model's surface and so is registered in no model scope at all.

## How the model uses it

1. Edit `page.md` locally, and/or move page directories to restructure the replica.
2. Call `sync_space(space_id)` (or `sync_page` / `sync_page_tree`) with only the id.
3. The helper reconciles everything (push, create, pull and materialize, move, and local-plus-remote version alignment) and returns `synced_count` and `applied`, plus only the items needing a decision: `conflicts` (with remote and local content and a diff) and `deletion_confirmations`. A clean sync needs no force.
4. Resolve a conflict with `resolve_conflict(space_id, page_id, merged_content)`; confirm a deletion with `confirm_deletion(space_id, page_id, direction)`. Ask the user if a resolution is unclear. Never force.