The single entry-point guide for working on and with the Docmost MCP service: every configuration,
how the bridge and the client helper interact, what to expect, the recommended path, the common
scenarios, and the exact restart procedures. The other pages in this space are deep-dives; this page
ties them together and is the place to start. Where a topic has a dedicated page it is linked at the
end of each section.

## The two halves

- Server (the bridge) - runs as Docker containers next to a live Docmost stack. It owns Docmost
  connectivity (reads from Docmost's PostgreSQL, writes through Docmost's REST API), the separate
  bridge PostgreSQL that holds version/sync state, content normalization, the reconcile brain, the
  REST + helper routes, and a background observer worker. See Architecture, MCP Server, REST API,
  Database Layer, Data Models.
- Client helper (`helper/`) - a small stdio MCP that runs on the machine where Claude Code runs. It
  is the consuming model's ONLY Docmost surface. It owns all local replica file IO and runs the
  automated reconcile by calling the server over REST. See Helper, Replica System.

There are two server-side MCP-shaped surfaces, and the model uses only one: `docmost-helper` (stdio,
the model surface) and the operator `/mcp` (HTTP, a human inspection fallback that is never
registered for the model). The helper reaches the server over REST (`/v1`, `/helper/v1`,
`/auto-mcp`), never over `/mcp`.

## Configuration reference

All configuration is environment-driven; there is no hardcoding in application code. Config lives in
four distinct places by audience:

1. Server `.env` (on the Docmost host, read by the containers). Docmost DB (read path), bridge DB
   (version state), Docmost app URL + write credentials, network/bind/ports, worker interval, mode,
   log level. Full table on the Configuration page. Copy `env.example` to `.env` and fill real
   values.
2. Helper `helper/.env` (on the client machine). `DOCMOST_MCP_SERVER_URL` (required - the server
   base URL the helper calls) and optional `DOCMOST_REPLICA_BASE` (the directory the helper scans
   for replicas by `_replica.json` space id; defaults to the helper process cwd, so it is normally
   left unset and the helper simply runs inside the repo).
3. Client shell environment via direnv `.envrc` (per repo). Loaded when you enter the repo and
   inherited by Claude Code and therefore by the helper process. Holds `GIT_SSH_COMMAND` (the repo's
   git deploy key, used for normal git and for replica autosync pushes), `CLAUDE_CONFIG_DIR` (which
   Claude home this repo uses), and optionally the autosync enable flag
   `DOCMOST_REPLICA_GIT_AUTOSYNC`.
4. MCP registration (the documented Claude Code channel). The `docmost-helper` stdio entry under
   `mcpServers` in the Claude home's `.claude.json` (user scope) - `command` is this repo's
   `helper/.venv/bin/python` running `helper/server.py` (absolute paths, so a home-scope entry works
   from any directory). The entry's `env` object is how per-repo helper values are passed; this is
   where `DOCMOST_REPLICA_AUTOSYNC_ROOTS` (the autosync origin scope) is declared. The repo's
   `.mcp.json` (project scope) is intentionally empty (`{"mcpServers": {}}`) and gitignored; skills
   and the helper registration live in the Claude home, not the repo. See claude-mcp-setup.

Autosync env (read by the helper from its process environment, so either the MCP `env` object or
`.envrc` works; declare the origin scope via the MCP `env` channel):

| Variable | Where | Meaning |
| --- | --- | --- |
| `DOCMOST_REPLICA_GIT_AUTOSYNC` | `.envrc` (or MCP `env`) | Opt in to automatic git backup of the in-repo replica. Truthy enables; unset/`0`/`false`/`off`/`no` disables. |
| `DOCMOST_REPLICA_AUTOSYNC_ROOTS` | MCP `env` (preferred) | Comma-separated repo-relative replica roots this repo OWNS and auto-pushes. Unset: a single-replica repo uses its one replica; a multi-replica repo is a safe no-op until declared. |
| `DOCMOST_REPLICA_BASE` | `helper/.env` | Discovery base for replicas; default is the helper cwd. Set only if replicas live outside the project root. |

## The bridge (server)

Three Compose services: `docmost-mcp` (FastAPI: REST + helper routes + operator `/mcp`),
`docmost-mcp-worker` (the interval observer over all spaces), and `bridge-db` (PostgreSQL for
version state). Both app services build from the same image and read `.env`.

- Deploy a code change: push to the git remote, pull on the Docmost host, then rebuild. The
  authoritative loop is `docker compose up -d --build` (or `--no-cache` for a clean rebuild of the
  image when dependencies or the renderer changed). Restart BOTH `docmost-mcp` and
  `docmost-mcp-worker` (both run the renderer).
- Restart without rebuilding: `docker compose restart` (use when the running image is still correct
  and you only need a fresh process).
- Recreate: `docker compose up -d` after service definitions, mounts, env files, or networks
  changed.
- Verify: `docker compose ps`, `curl http://<host>:8099/health`, `curl http://<host>:8099/spaces`,
  and `docker compose logs -f docmost-mcp docmost-mcp-worker`.
- A helper-only change needs NO bridge rebuild (the bridge image is unaffected when `app/` did not
  change). See Deployment.

## The client helper

Normal work is reconcile-first; the model only initiates a sync and the helper plus server do the
diffing, versioning, and file IO.

1. Edit `page.md` locally and/or move page directories to restructure the hierarchy (a page's parent
   is derived from its directory nesting).
2. Call `sync_space(space_id)` - or `sync_page(space_id, page_id)` /
   `sync_page_tree(space_id, parent_page_id)` - with only the id(s).
3. The helper reconciles in one pass (push edits, create local-only pages, pull remote changes,
   materialize new remote pages, apply moves) and returns a summary: `synced_count` (already in
   sync) + `applied_count` / `applied[]` (changed this run, metadata only - page content is written
   to your local files, not returned) plus only the items needing a decision: `conflicts[]` (each
   with `remote_content` / `local_content` / diff) and `deletion_confirmations[]`. Confirm a change
   via `applied_count` / `errors[]`, not `synced_count`.
4. Resolve a conflict with `resolve_conflict(space_id, page_id, merged_content)`; apply a deletion
   with `confirm_deletion(space_id, page_id, direction)`. Ask the user when a merge or deletion is
   unclear. Never force.

`resync_space(space_id)` is the occasional whole-space variant: it re-renders EVERY page from
Docmost on the server (even unchanged ones) then runs the same two-way reconcile, so a server-side
rendering change reaches pages that were never re-edited. It heals via pull, surfaces conflicts the
same way, never force-pushes, and adds `reanchored_count`.

`create_page` / `update_page` / `delete_page` / `move_page` / `push_pages` / `pull_pages` /
`accept_remote` and the stash tools are low-level escape hatches, not the normal path. All ids must
come from live tool responses in the current session, never from memory. Content is markdown; the
page title is a separate parameter (never an H1 in the body). See Helper, Replica System, Data
Models.

## Local replica and replica git autosync

The helper keeps a per-space replica as a directory tree under the repo, one directory per page
(`page.md` + helper-owned `_meta.json`, plus a root `_replica.json` space header and `_tree.json`
last-synced snapshot). The model owns `page.md` and the directory layout; the helper owns file IO
and `_meta.json` (never hand-edit it); the server owns canonical path planning, the revision hash,
and safe Docmost writes.

The replica stays a tracked part of its repo (NOT gitignored). When the repo opts in via
`DOCMOST_REPLICA_GIT_AUTOSYNC`, the helper itself commits and pushes replica changes to the repo's
own git remote after a sync (current branch only, remote discovered dynamically, never force,
isolated to the replica subtree so unrelated staged code is never swept in). A multi-replica repo
declares which replicas it owns via `DOCMOST_REPLICA_AUTOSYNC_ROOTS`. This is git-only automation;
the Docmost-to-local sync stays manual. So replica edits may already be committed and pushed for you

- do not manually git the replica. See Replica System.

## Expectations and gotchas

- After a sync, a page's local `page.md` settles to Docmost's canonical, structure-preserving
  rendering (the basis of the revision hash). It differs from your typed bytes only in canonical-form
  choices (for example `-` bullets, ATX headings, fenced code, marker-width nested-list indent - two
  spaces under a bullet, three under an ordered item), never in structure. Treat the post-sync form
  as the source of truth.
- Write-path normalization now neutralizes the former ingest asymmetries automatically (the ingest
  half of the Conversion Gate, `app/write/ingest.py`). It re-indents an under-indented sub-list to
  the parent marker width so nesting is preserved instead of flattened, guards Docmost's leading
  front-matter strip, and escapes the tokens `marked` would otherwise mis-read outside code: flanking
  `_`/`__` (so `app/__init__.py` stays literal instead of becoming bold `init`) and non-schema HTML
  tags (so a stray `<article>` or `<div>` survives as literal text instead of being dropped with its
  neighbours). None of these need manual fixing to round-trip.
- Two ingest residuals remain, owned by Docmost's own parser and not preventable by the egress: a
  literal double-dollar or a bare single-dollar pair is grabbed by Docmost's math extension (describe
  math in prose or backtick a literal dollar), and an inline-code span whose content ends in a space
  followed by a word loses that outer space (do not lean a space on a code span's edge). Both are
  detailed on the Conversion Gate and Known Limitations pages.
- Use plain ASCII punctuation; no Unicode em-dashes, curly quotes, or ellipsis characters.

## Restarting (exact procedures)

When a restart is needed:

- Helper (client) code changed (anything under `helper/`, including a new tool, a changed
  instruction string, or the replica autosync), OR an MCP `env` value changed (for example
  `DOCMOST_REPLICA_AUTOSYNC_ROOTS`): the running helper is a long-lived stdio subprocess of Claude
  Code and does NOT pick up code or MCP-env changes until it is restarted. Claude itself cannot
  restart the helper from inside a session; you restart it.
- Bridge (server) code changed (anything under `app/`): redeploy and restart the containers (see
  below). A helper-only change does not need this.

Restart the helper (one of):

1. Restart Claude Code (exit and relaunch the CLI from the repo, with direnv active so `.envrc` and
   the MCP config load). This re-spawns the `docmost-helper` subprocess with the new code and env.
2. Or, in a running session, reconnect MCP with the `/mcp` command (re-establishes the stdio
   transport). After a server rebuild, treat a `Session not found` message as stale transport, not
   missing content - reconnect.

Verify the helper reloaded: the new tools/behavior are present (for example
`mcp__docmost-helper__*` tools list cleanly), and for autosync, a sync now also commits + pushes the
replica when enabled. The autosync log is at `~/.cache/docmost-replica-autosync.log`.

Restart the bridge:

- Code/deps changed: `docker compose up -d --build` (add `--no-cache` for a clean image), then
  `docker compose logs -f docmost-mcp docmost-mcp-worker`.
- Definition unchanged, just bounce: `docker compose restart`.

## Scenarios

- First-time client setup: create the helper venv and `helper/.env` (set `DOCMOST_MCP_SERVER_URL`);
  register `docmost-helper` in the Claude home `.claude.json` with absolute paths (see
  claude-mcp-setup); set the repo `.envrc` (git key + `CLAUDE_CONFIG_DIR`); restart Claude Code.
- Everyday docs change: edit `page.md`, `sync_space(space_id)`, act only on `conflicts` /
  `deletion_confirmations`.
- Conflict: inspect `remote_content` / `local_content` / diff, then `resolve_conflict` with the
  merged markdown; ask the user if unclear.
- Whole-space re-render (for example after a renderer fix): `resync_space(space_id)`; clean pages
  heal as pulls, edited pages surface as conflicts, `reanchored_count` reports how many re-rendered.
- Enable replica autosync: set `DOCMOST_REPLICA_GIT_AUTOSYNC` and (for a multi-replica repo)
  `DOCMOST_REPLICA_AUTOSYNC_ROOTS` in the MCP `env`; restart the helper. After that, syncs
  auto-commit + push the owned replica.
- Deploy a server change: push, pull on the host, `docker compose up -d --build`, restart both app
  services, verify.
- Deploy a helper change: push; restart the helper (no bridge rebuild).
- Troubleshooting: helper cannot find a replica - it scans `DOCMOST_REPLICA_BASE` (default cwd) for a
  matching `_replica.json`; pass an explicit `local_root` only when discovery is ambiguous.
  `Session not found` after a rebuild - reconnect MCP. A page that came back as odd text - a literal
  `$` or double-dollar pair was taken by Docmost's math extension (backtick it). Flanking `_`/`__`,
  stray HTML tags, under-indented sub-lists, and a leading front-matter rule are now normalized
  automatically on the write path. See Conversion Gate and Known Limitations.

## Recommended practices

- Drive everything through the helper's reconcile-first tools; never force, and ask the user before
  any merge or deletion that is not obvious.
- Backtick code, paths, and identifiers in page content; keep prose ASCII.
- Keep config in its correct layer: server `.env` on the host, `helper/.env` for the server URL,
  `.envrc` for the git key and enable toggle, the MCP `env` for the autosync origin scope.
- Restart the helper after any helper code or MCP-env change; rebuild the bridge only when `app/`
  changed.
- Let the in-repo replica be versioned by autosync where enabled; do not hand-git the replica.

## Deep-dive index

Overview, Architecture, Configuration, MCP Server, REST API, Database Layer, Data Models, Helper,
Replica System, Deployment, claude-mcp-setup, Conversion Gate, Known Limitations, Release.