# Docmost MCP

Docmost MCP runs alongside a live Docmost deployment on the same Docker network,
connects directly to the Docmost PostgreSQL database, and exposes that content
through both a remote MCP endpoint for agents and a REST API for conventional
HTTP integrations.

It is designed for the common setup where Docmost stays containerized on one
server while GitHub Copilot CLI or another MCP-compatible client connects from a
different machine.

## MCP capabilities

The `/mcp` endpoint gives GitHub Copilot CLI and other MCP-compatible clients a
remote Docmost toolset over streamable HTTP.

| Capability | Tools |
|---|---|
| Resolve the correct Docmost space | `list_spaces`, `get_space` |
| Inspect hierarchy and page listings | `get_space_tree`, `list_pages` |
| Read full page content as markdown | `get_page` |
| Inspect replica rules and layout | `get_replica_standards`, `resolve_replica_directory_name`, `get_replica_structure` |
| Scaffold a local-only replica page | `create_local_replica_page` |
| Inspect sync status and diff clashes | `get_sync_status`, `get_sync_diff` |
| Pull or push a local working-copy replica | `pull_replica`, `push_replica` |
| Create or delete spaces | `create_space`, `delete_space` |
| Create, update, or delete pages | `create_page`, `update_page`, `delete_page` |

All page content is markdown in and markdown out.

## REST capabilities

The REST API exposes the same core access patterns over HTTP for direct
integrations, manual inspection, and non-MCP automation.

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | process health check only; does not verify database connectivity |
| `GET` | `/spaces` | list all non-deleted spaces |
| `GET` | `/spaces/{space_id}` | get one non-deleted space |
| `GET` | `/spaces/{space_id}/tree` | get the nested page tree for one space |
| `GET` | `/spaces/{space_id}/replica-structure` | get the deterministic local replica layout for one space |
| `GET` | `/spaces/{space_id}/pages` | list all non-deleted pages in a space (no content) |
| `GET` | `/spaces/{space_id}/pages/{page_id}` | get one page with full markdown content |
| `GET` | `/replica/standards` | get local replica naming, structure, and sync rules |
| `GET` | `/replica/resolve-directory-name` | resolve the correct local directory name for a page title |
| `GET` | `/spaces/{space_id}/sync/status` | get sync status for a space replica or chosen local working copy |
| `GET` | `/spaces/{space_id}/sync/diff` | get line-based local-vs-remote diff hunks for one page or all unsynced pages |
| `POST` | `/spaces` | create a new space |
| `DELETE` | `/spaces/{space_id}` | permanently delete a space and all its pages |
| `POST` | `/spaces/{space_id}/pages` | create a page (add `parent_page_id` for a child page) |
| `PUT` | `/spaces/{space_id}/pages/{page_id}` | update a page title and/or content (markdown) |
| `DELETE` | `/spaces/{space_id}/pages/{page_id}` | soft-delete a page |
| `POST` | `/spaces/{space_id}/sync/local-pages` | scaffold a new local-only page in the chosen local working copy |
| `POST` | `/spaces/{space_id}/sync/pull` | materialize or refresh the chosen local working copy from remote Docmost |
| `POST` | `/spaces/{space_id}/sync/push` | push chosen local working-copy changes back to remote Docmost |

Write routes authenticate against Docmost automatically using
`DOCMOST_APP_URL`, `DOCMOST_USER_EMAIL`, and `DOCMOST_USER_PASSWORD` from
`.env`. Content is markdown in and out, and the update route supports
`operation: replace | append | prepend`.

## Prerequisites

Before setup, make sure you have:

1. a running Docmost environment with PostgreSQL - **v0.71.1 or later required** for content write operations to function correctly (see note below)
2. Docker and Docker Compose available on the server where this service will run
3. network access from this service container to the live Docmost PostgreSQL container
4. network access from your Copilot CLI machine to the published Docmost MCP URL
5. the Docmost database credentials or DSN

> **Docmost version requirement - v0.71.1+**
>
> Content write operations (creating and updating page content) require Docmost v0.71.1 or later.
> Earlier versions silently discard the content field, resulting in pages being created empty.
>
> Upgrading Docmost carries no risk to your existing page data. Docmost upgrades are
> non-destructive - your spaces, pages, and history are stored in PostgreSQL and are not
> affected by a container image update. To upgrade, pull the latest image and recreate
> the container:
>
> ```bash
> docker compose pull docmost && docker compose up -d docmost
> ```
>
> To check which version you are currently running:
>
> ```bash
> docker exec docmost cat /app/apps/server/package.json | grep '"version"' | head -1
> ```

## Full setup from start to finish

Two setup methods are available. Both result in the same running service.

### Option A: from the published Docker image (recommended)

Pull the image directly from GitHub Container Registry - no clone or build step needed:

```bash
mkdir -p /opt/docmost-mcp && cd /opt/docmost-mcp
```

Create a `docker-compose.yml`:

```yaml
services:
  docmost-mcp:
    container_name: docmost-mcp
    image: ghcr.io/isak-landin/docmost-mcp-api:latest
    restart: unless-stopped
    env_file: .env
    environment:
      DOCMOST_DB_HOST: ${DOCMOST_DB_HOST}
      DOCMOST_DB_PORT: ${DOCMOST_DB_PORT}
      DOCMOST_DB_NAME: ${DOCMOST_DB_NAME}
      DOCMOST_DB_USER: ${DOCMOST_DB_USER}
      DOCMOST_DB_PASSWORD: ${DOCMOST_DB_PASSWORD}
      LISTEN_HOST: ${LISTEN_HOST:-0.0.0.0}
      LISTEN_PORT: ${LISTEN_PORT:-8099}
      DOCMOST_APP_URL: ${DOCMOST_APP_URL}
      DOCMOST_USER_EMAIL: ${DOCMOST_USER_EMAIL}
      DOCMOST_USER_PASSWORD: ${DOCMOST_USER_PASSWORD}
      DOCMOST_REPLICA_ROOT_BASE: ${DOCMOST_REPLICA_ROOT_BASE:-/var/lib/docmost-mcp/replicas}
    ports:
      - "${EXTERNAL_PORT:-8099}:${LISTEN_PORT:-8099}"
    volumes:
      - docmost_mcp_replica_data:/var/lib/docmost-mcp/replicas
    networks:
      - docmost_network

networks:
  docmost_network:
    external: true
    name: ${DOCMOST_NETWORK_NAME:-docmost_default}

volumes:
  docmost_mcp_replica_data:
```

Then continue from [step 2](#2-confirm-the-shared-docker-network-name) below. Skip the build step - replace `docker compose up --build -d` with `docker compose up -d`.

---

### Option B: from source

Create the target directory on the same server that hosts the live Docmost deployment:

```bash
mkdir -p /opt/docmost-mcp
```

Then either clone the repository into that directory:

```bash
git clone https://github.com/Isak-Landin/docmost-mcp-server.git /opt/docmost-mcp
cd /opt/docmost-mcp
```

Or copy an existing local checkout into place:

```bash
cp -a /path/to/docmost-mcp-server/. /opt/docmost-mcp/
cd /opt/docmost-mcp
```

### 2. Confirm the shared Docker network name

By default this project joins the Docker network named `docmost_default`.

Set `DOCMOST_NETWORK_NAME` in your `.env` if your Docmost stack uses a different network name:

```env
DOCMOST_NETWORK_NAME=my_custom_network
```

To find your Docmost network name:

```bash
docker network ls | grep docmost
```

### 3. Create the runtime environment file

Copy the example file:

```bash
cp env.example .env
```

Then edit `.env`.

### 4. Fill in `.env`

You can configure the database in one of two ways.

#### Option A: full DSN

Use `DOCMOST_DB_URL` if you want a single connection string:

```env
DOCMOST_DB_URL=postgresql://<DB_USER>:<DB_PASSWORD>@<DB_HOST>:5432/<DB_NAME>
```

#### Option B: separate values

If you do not use `DOCMOST_DB_URL`, set the individual values:

```env
DOCMOST_DB_HOST=<DOCMOST_DB_HOSTNAME_ON_DOCKER_NETWORK>
DOCMOST_DB_PORT=5432
DOCMOST_DB_NAME=<DOCMOST_DB_NAME>
DOCMOST_DB_USER=<DOCMOST_DB_USER>
DOCMOST_DB_PASSWORD=<DOCMOST_DB_PASSWORD>
```

#### API and MCP listen values

These control where the container listens:

```env
LISTEN_HOST=0.0.0.0
LISTEN_PORT=8099
EXTERNAL_PORT=8099
```

Meaning:

- `LISTEN_HOST`: bind host inside the container
- `LISTEN_PORT`: port inside the container
- `EXTERNAL_PORT`: port published on the server

#### Server-side replica root

The bundled Docker Compose setup persists the server-side replica under `/var/lib/docmost-mcp/replicas`.

If you want a different persistent location, set:

```env
DOCMOST_REPLICA_ROOT_BASE=/path/on/the/server
```

When unset outside the bundled Compose workflow, replica paths such as `./My-Space-replica/` are resolved relative to the project root. For real deployments, use a persistent bind mount or volume so replica state survives container recreates.

#### Example full `.env`

```env
DOCMOST_DB_URL=
DOCMOST_DB_HOST=<DOCMOST_DB_HOSTNAME_ON_DOCKER_NETWORK>
DOCMOST_DB_PORT=5432
DOCMOST_DB_NAME=<DOCMOST_DB_NAME>
DOCMOST_DB_USER=<DOCMOST_DB_USER>
DOCMOST_DB_PASSWORD=<DOCMOST_DB_PASSWORD>

DOCMOST_APP_URL=http://<DOCMOST_CONTAINER_NAME>:3000
DOCMOST_USER_EMAIL=<YOUR_DOCMOST_USER_EMAIL>
DOCMOST_USER_PASSWORD=<YOUR_DOCMOST_USER_PASSWORD>

DOCMOST_NETWORK_NAME=docmost_default

LISTEN_HOST=0.0.0.0
LISTEN_PORT=8099
EXTERNAL_PORT=8099

MCP_ALLOWED_HOSTS=<YOUR_DOCMOST_MCP_HOSTNAME>
DOCMOST_REPLICA_ROOT_BASE=/var/lib/docmost-mcp/replicas

MODE=prod
LOG_LEVEL=INFO
```

### 5. Build and start the container

**Option A (image):**

```bash
docker compose up -d
```

**Option B (source):**

```bash
docker compose up --build -d
```

This will:

1. pull the published image (Option A) or build from `Dockerfile` (Option B)
2. create or recreate the `docmost-mcp` container
3. attach it to the external Docker network set by `DOCMOST_NETWORK_NAME`
4. expose the service on the configured external port

### 6. Confirm the container is running

```bash
docker compose ps
```

You should see the `docmost-mcp` service/container running.

If you need logs:

```bash
docker compose logs -f
```

### 7. Verify the HTTP endpoints

Use placeholders for your real host name or IP:

```bash
curl http://<YOUR_DOCMOST_MCP_HOST>:8099/health
```

Expected response:

```json
{"ok":true}
```

This only confirms that the service process is reachable. It does **not** confirm that
the Docmost database is reachable.

Open the REST docs:

```text
http://<YOUR_DOCMOST_MCP_HOST>:8099/docs
```

MCP endpoint:

```text
http://<YOUR_DOCMOST_MCP_HOST>:8099/mcp
```

If you are putting this behind a reverse proxy, the MCP URL may instead be:

```text
https://<YOUR_DOCMOST_MCP_HOST>/mcp
```

To verify a database-backed route as part of manual testing, also try:

```bash
curl http://<YOUR_DOCMOST_MCP_HOST>:8099/spaces
```

If the database is unreachable, the read routes return:

- REST: `503` with `{"detail":"Docmost database connection failed"}`
- MCP: tool error with `Docmost database connection failed`

To inspect the exact local-replica projection for one space, use:

```text
http://<YOUR_DOCMOST_MCP_HOST>:8099/spaces/<SPACE_ID>/replica-structure
```

To inspect replica naming and sync rules without a space-specific lookup, use:

```text
http://<YOUR_DOCMOST_MCP_HOST>:8099/replica/standards
```

#### Write endpoints

Write routes require `DOCMOST_APP_URL` plus `DOCMOST_USER_*` in `.env`.
Authentication is transparent, and the full route list is in
[REST capabilities](#rest-capabilities).

### 8. Optional: place behind HTTPS or a reverse proxy

If Copilot CLI runs on another machine, HTTPS is usually the cleanest approach.

Typical reverse proxy responsibilities:

- terminate TLS
- expose a stable hostname
- forward `/mcp` to the container
- forward `/health`, `/docs`, and REST routes if you want those externally reachable

Example placeholder public URL:

```text
https://<YOUR_DOCMOST_MCP_HOST>/mcp
```

## GitHub Copilot CLI setup

Because the MCP endpoint is remote and container-hosted, your GitHub Copilot CLI
machine does **not** need any local wrapper script for Docmost MCP.

Copilot CLI only needs a configured MCP server pointing at the remote URL.

Copilot CLI already includes the GitHub MCP server by default. Docmost MCP is an
additional remote MCP server you add to extend Copilot CLI with Docmost access.

Configured MCP server details are saved per Copilot config home. Create a
dedicated Docmost-only home first:

```bash
mkdir -p "$HOME/copilot-docmost"
export COPILOT_HOME="$HOME/copilot-docmost"
```

That keeps Docmost MCP configuration and Docmost-specific instructions out of
your normal default Copilot home.

### Recommended layout

Use these two files inside the dedicated Docmost home:

```text
$HOME/copilot-docmost/mcp-config.json
$HOME/copilot-docmost/copilot-instructions.md
```

Keep your normal:

```text
~/.copilot/copilot-instructions.md
```

generic. Do **not** keep Docmost-specific behavior in the default global
instructions file, or it will clash with unrelated work.

### Recommended start command

```bash
mkdir -p "$HOME/copilot-docmost"
export COPILOT_HOME="$HOME/copilot-docmost"
copilot
```

### Add the MCP server

Inside Copilot CLI:

```text
/mcp add
```

Then enter the remote HTTP MCP URL:

```text
https://<YOUR_DOCMOST_MCP_HOST>/mcp
```

Allow these tools:

```text
list_spaces
get_space
get_space_tree
get_replica_standards
resolve_replica_directory_name
get_replica_structure
create_local_replica_page
get_sync_status
get_sync_diff
pull_replica
push_replica
list_pages
get_page
create_space
delete_space
create_page
update_page
delete_page
```

After saving with `/mcp add`, verify that:

- the saved URL ends with `/mcp`
- there is no stray whitespace in the URL
- the allowlist includes the tree and replica tools, not just page lookup tools

### Recommended `mcp-config.json`

Store this in:

```text
$COPILOT_HOME/mcp-config.json
```

```json
{
  "mcpServers": {
    "docmost-mcp": {
      "type": "http",
      "url": "https://<YOUR_DOCMOST_MCP_HOST>/mcp",
      "tools": [
        "list_spaces",
        "get_space",
        "get_space_tree",
        "list_pages",
        "get_page",
        "get_replica_standards",
        "resolve_replica_directory_name",
        "get_replica_structure",
        "create_local_replica_page",
        "get_sync_status",
        "get_sync_diff",
        "pull_replica",
        "push_replica",
        "create_space",
        "delete_space",
        "create_page",
        "update_page",
        "delete_page"
      ]
    }
  }
}
```

### Recommended `copilot-instructions.md`

Store this in:

```text
$COPILOT_HOME/copilot-instructions.md
```

```md
# Instructions
We are working with extremely complex and sensitive structures.
Therefor we can't afford your common assumptions and usual approach to be implemented.
It is essential that all following rules are followed.

Clarification. Internal documentation is not docs that exist in the repository you have access to. It is the copilot internal documentation for a session.

- Always read internal documentation before attempting to answer or take action if action is not external documentation aimed.
- Always update internal documentation when new insight is established which does not match the current internal documentation.
- Always update internal documentation determined that previously mentioned additions, edits and deletes were accepted and not reflected in internal documentation.
- Don't Update documentation, project or internal, until change is implemented.
- Don't update project docmost documentation unless asked for.
- Mention deprecated project documentation when noticed to be deprecated.
- Keep ownership boundaries strict.
- Prefer simple return contracts.
- Don't expect existence of code or non-existence of code when asked or derived addition or creation of code conclusion.
- Always verify that other code, module or package does not exist as owner of wanted implementation. Since we never want to duplicate codebase responsibilities.
- Only make additions or creations when required to keep project codebase integrity or required as a result of avoidance to mix ownership.
- Don't guess or invent new rules or module ownerships.

## Repo and runtime workflow

- Always make repository changes locally. Never make source changes directly on a remote host.
- Treat hosted runtime environments as remote. Do not host the project locally.
- Use remote logs and remote runtime behavior to debug deployed issues, then implement the fix locally in the repo.
- Do not use remote edits as a substitute for local implementation. Remote environments are for observation, logs, validation, and deployment state, not source authoring.

## Docmost MCP - reading

Use the docmost-mcp MCP server as the primary long-term documentation source when the task is about Docmost-backed project documentation or the user directs work through Docmost.
Remote Docmost pages are the authoritative long-term representation of the project - deprecation is not the default assumption.
Only treat a page as stale or outdated when there is a clear, verified conflict with current code or runtime behavior, not merely because a local replica was edited.

If documentation, documented behavior, page names, or relevant file/path references are mentioned without full context and Docmost is part of the task, consult docmost-mcp before guessing.
Internal session documentation and Docmost documentation are complementary - use both when Docmost is in scope. Neither replaces the other.
When using docmost-mcp, always resolve the correct space first with list_spaces, then inspect pages within that space.
Pages are space-scoped and are not global lookups.
Use get_space_tree when you need the nested structure of a space.
Use list_pages for a flat listing. Use get_page for a single page with full markdown content.

## Local replica management

Maintain or create a local-first replica in the working copy you are editing. If you do not pass
`local_root`, the service uses its default replica location at `./{space_name}-replica/`.
No spaces are allowed in any local replica directory or file name. Replace spaces with hyphens in all local paths (e.g. "Local LLM Helper" -> `Local-LLM-Helper-replica`).
Use `get_replica_structure(space_id, local_root?)` for the exact local replica layout of an existing space and for initial replica creation in a chosen working copy.
Use `create_local_replica_page(..., local_root?)` to scaffold new local-only pages in the chosen local working copy.
Use get_replica_standards and resolve_replica_directory_name only when you need to inspect or verify naming behavior.
Use the replica tree mapping plus `_meta.json` to relate local replica files back to remote pages.

Ownership split:

- the **server** controls canonical replica structure, metadata paths, sync bookkeeping files, and comparison normalization
- the **server** also enforces stale-push detection from each page's recorded sync base
- the **client** controls which local working-copy root is active, page edits, which pages to operate on, and whether to force a winner after reviewing status or diff output

When local replica files are edited, use `get_sync_status(space_id, local_root?)` to discover which files changed and which remote pages they correspond to.
Use `get_sync_diff(space_id, ..., local_root?)` to return the differing sections and line numbers whenever local and remote diverge.
Use `pull_replica(..., local_root?)` to materialize or refresh local files from remote Docmost.
Use `push_replica(..., local_root?)` to update remote Docmost from the selected local working copy.
`pull_replica` is one-way and does not auto-push local changes first.
`push_replica` is one-way and does not auto-pull remote changes first.
Representation-only drift is normalized server-side before comparison so CRLF vs LF, BOM, Unicode normalization form, and final-newline differences do not create false conflicts.
If local and remote both changed since the last sync base, return the clashes first and force push or force pull only after the consuming model has chosen a winner or asked the user. This lets multiple local working copies cooperate safely: once one working copy pushes, another working copy must pull or consciously force before it can push stale content.

## Docmost MCP - writing

The docmost-mcp MCP server supports write operations. Auth is handled automatically - never call an auth route first.
All content is markdown in and out.

Before creating a page, use get_space_tree or list_pages to check if a matching page already exists.
Use create_local_replica_page for normal local-first page creation in the selected working-copy replica, then edit locally and push when ready.
Use resolve_replica_directory_name and get_replica_standards only when you need to inspect naming behavior directly.

Use create_page to create a new page. Pass parent_page_id to create a nested child page.
Use push_replica for normal local-replica sync work. Whole-space sync is `push_replica(..., local_root=...)` with no page selectors. Selected-page sync is `push_replica(..., local_root=..., page_ids=[...])`. Single local-only page sync is `push_replica(..., local_root=..., local_paths=[...])`. Use update_page as the low-level fallback when you intentionally want to bypass the higher-level sync workflow. Prefer update_page over delete+create - Docmost preserves page history on update.
Use delete_page ONLY when the user has clearly confirmed a page should be removed, or when a local edit makes it unambiguous that the page no longer exists (e.g. the local file was deliberately deleted and the user agreed). Never delete speculatively.
Use delete_space ONLY on explicit user instruction.

All IDs passed to write tools must originate from a live MCP tool response - never from memory, local files, or inference:
- space_id: from list_spaces or create_space
- parent_page_id: from list_pages, get_space_tree, or a prior create_page response
- A create_page id is valid as parent_page_id only within the same uninterrupted sequence - re-resolve via list_pages or get_space_tree if any deletion has occurred since that creation
- A 404 from any write tool means the given ID does not exist in live Docmost; use a read tool to resolve the correct ID and retry

Content formatting rules (applies to all page content passed to create_page and update_page):
Do NOT use Unicode typographic characters in page content. These characters are not reliably rendered across all Docmost consumers and may appear as garbled text or question marks.
Forbidden characters and their plain-text replacements:
- em dash (-) -> use hyphen with surrounding spaces ( - ) or a plain hyphen (-)
- en dash (-) -> use a plain hyphen (-)
- right arrow (->) -> use the two-character sequence ->
- double arrow (=>) -> use the two-character sequence =>
- ellipsis (...) -> use three plain dots (...)
- curly quotes (" " ' ') -> use straight quotes (" and ')
When inline text separation is needed, use a plain hyphen (-) as the separator.
When syncing local -> remote:
1. Choose the working-copy root first. Pass `local_root` when you want the sync to operate on a repo-local replica rather than the service default at `./{space_name}-replica/`.
2. Call `get_sync_status` to identify which tracked pages are local-only, remote-only, conflicting, or already synced.
3. Call `get_sync_diff` when you need the exact line-based clash details before choosing a resolution.
4. Use `create_local_replica_page` when a brand-new local-only page needs to be scaffolded in the replica.
5. Use `push_replica` for local-ahead changes and local-only pages.
6. Use `pull_replica` for remote-ahead changes.
7. Leave `page_ids` and `local_paths` empty to sync the whole space, pass `page_ids` to sync selected tracked pages, or pass `local_paths` to sync a specific local-only page.
8. If another working copy pushed in between, the stale working copy will surface as `remote_only_change` or `conflicted` and must pull or force after reviewing the diff.
9. Do not expect `pull_replica` to push first, and do not expect `push_replica` to pull first - blocked attempts should follow the recommended next action from sync status or operation results.
10. If both local and remote changed, choose whether to `force` push or `force` pull only after inspecting the clash output.
11. Never delete remote pages based solely on a missing local file without user confirmation.

Sync request and response hints:

- `get_sync_status(space_id, include_synced=false, local_root?)` returns per-page `recommended_action`, `allowed_actions`, and space-level `pipeline_expectations`
- `get_sync_diff(space_id, page_id?, local_path?, include_synced=false, local_root?)` lets automation narrow diff inspection to one tracked page or one local replica path; when `local_path` belongs to a single replica root, the service can infer that working-copy root automatically
- `create_local_replica_page(space_id, title, content?, parent_page_id?, parent_local_path?, local_root?)` scaffolds a canonical local-only page directory, `page.md`, and `_meta.json` without making the client hand-write replica metadata
- `pull_replica` and `push_replica` accept `{"local_root": "...", "page_ids": [...], "local_paths": [...], "force": false}` so automation can target a whole space, a selected set of tracked pages, or a single local-only page inside one working copy
- blocked `pull_replica` or `push_replica` results return `recommended_next_action` so callers can continue the intended pipeline instead of guessing

## Naming rules (spaces)

Space slugs must be alphanumeric with no spaces or dashes (e.g. "mydocs", not "my-docs").
Use get_replica_standards to verify naming conventions before creating spaces or pages.
```

This is the one recommended Docmost-specific instruction file. Do not split the
same Docmost behavior across multiple competing instruction files unless you
deliberately want to manage instruction precedence yourself.

### Resulting behavior

With the dedicated Docmost home configured this way:

- Docmost MCP is available only when you start Copilot with `COPILOT_HOME="$HOME/copilot-docmost"`
- the Docmost-specific instructions live alongside the Docmost MCP config
- your default global Copilot instructions stay free of Docmost-specific assumptions
- the consumer is explicitly told to:
  - use Docmost as the primary **long-term** documentation source (not assumed stale)
  - use both internal session docs and Docmost - neither replaces the other
  - check whether a page already exists before creating one
  - scaffold new local-only pages via `create_local_replica_page`, and use `get_replica_standards` / `resolve_replica_directory_name` only when inspecting naming behavior
  - use `local_root` to select the active working-copy replica when needed
  - use `get_sync_status` and `get_sync_diff` to reason about the selected working-copy state
  - use `push_replica` and `pull_replica` for whole-space, selected-page, or single-page replica sync work
  - use `create_page` with `parent_page_id` for nested child pages
  - **only delete** remote pages when the user has confirmed removal - never speculatively
  - return clashes before forcing a sync winner when local and remote diverge

## Updating the running service

When you change code or dependencies:

```bash
docker compose up --build -d
```

To restart without rebuilding:

```bash
docker compose restart
```

To stop the service:

```bash
docker compose down
```

## Troubleshooting

### Health endpoint fails

Check:

1. the container is running
2. the published port is correct
3. the reverse proxy is forwarding correctly if one is used

### MCP cannot connect

Check:

1. the configured MCP URL ends with `/mcp`
2. the Copilot CLI machine can reach the host and port
3. HTTPS or proxy settings are correct if the endpoint is remote
4. the MCP config includes all intended tools (read + write)

### MCP returns "Session not found" after a rebuild or restart

`/mcp` uses streamable HTTP sessions. When the service process restarts, old session ids become invalid.

Check:

1. the service finished restarting cleanly
2. the MCP client opened a fresh session after the restart instead of reusing the old one
3. you retried from a new Copilot/MCP session if the previous one was connected before the rebuild

### Page lookup is confusing or keeps failing

Check:

1. you identified the correct `space_id` via `/spaces` or `list_spaces` first
2. you are using that same `space_id` for `/spaces/{space_id}/tree`, `/spaces/{space_id}/pages`, `get_space_tree`, or `list_pages`
3. you are not treating page lookup as global across all spaces
4. the page may genuinely be stale, deleted, or in a different space

### Replica layout or naming is inconsistent

Check:

1. you are using `/spaces/{space_id}/replica-structure` or `get_replica_structure` for existing remote content
2. you are using `/replica/standards` or `get_replica_standards` for the shared local-replica rules
3. you are using `/spaces/{space_id}/sync/local-pages` or `create_local_replica_page` for new local-only pages
4. you are treating the local replica as the working source of truth only after newer local edits actually exist
5. you are using `get_sync_status` and `get_sync_diff` to inspect drift in the selected working copy before forcing a sync winner

### Database connection fails

Check:

1. the credentials in `.env`
2. the database host name reachable from inside the Docker network
3. the external network name in `docker-compose.yml`
4. whether the live Docmost PostgreSQL container is actually on that network

### Wrong scope in Copilot CLI

If Docmost MCP is appearing in unrelated work:

1. move it into a dedicated `COPILOT_HOME`
2. remove it from your default `~/.copilot/mcp-config.json`
3. start Docmost-only sessions with the dedicated Copilot home

## Local non-Docker run

If you want to run the service locally without Docker:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8099
```

You still need valid Docmost database connectivity through the configured env vars.
If your `.env` uses a Docker-only hostname such as `db`, that local run will fail unless
your machine can resolve that hostname. For non-Docker local runs, set `DOCMOST_DB_HOST`
or `DOCMOST_DB_URL` to a database address reachable from the host machine.

## Intended lookup and write flow

This service is **space-first**.

1. use `list_spaces` or `GET /spaces` to identify the correct Docmost space
2. select the matching space by name, then use its `id` as `space_id`
3. use `get_space_tree(space_id)` or `GET /spaces/{space_id}/tree` for the full nested structure
4. use `list_pages(space_id)` or `GET /spaces/{space_id}/pages` for a flat list
5. use `get_page(space_id, page_id)` or `GET /spaces/{space_id}/pages/{page_id}` for a single page with markdown content

Before creating a page:
- check whether the page already exists via `get_space_tree` or `list_pages`
- use `create_local_replica_page` when the real intent is to start a new local-only page first
- use `get_replica_standards` and `resolve_replica_directory_name` only when you need to inspect naming behavior directly
- use `create_page` with `parent_page_id` to create nested child pages at any depth

All IDs passed to write operations must originate from a live MCP tool response - never from memory, local files, or inference:
- `space_id` must come from `list_spaces` or `create_space`
- `parent_page_id` must come from `list_pages`, `get_space_tree`, or a prior `create_page` response
- A `create_page` response id is valid as `parent_page_id` only within the same uninterrupted sequence - if any deletion or space removal has occurred since that creation, re-resolve with `list_pages` or `get_space_tree` first
- A **404** from any write tool means the given ID does not exist in the live Docmost instance; resolve the correct ID via a read tool and retry

When updating existing pages:
- prefer `update_page` over delete+create - Docmost preserves full page history on update
- use `operation=replace` (default) to overwrite, `append` to add after, `prepend` to add before

Important clarifications:

- page lookup is not global; pages are always scoped to a space
- the tools and routes accept `space_id`, not a space name string
- if you only know a space name, resolve it through `list_spaces` first
- the tree is built dynamically from `pages.parent_page_id`
- `parent_page_id = null` means the page is a top-level page in the space
- `orphan_pages` contains pages whose parent is missing or unreachable

## Recommended documentation-source workflow

The intended usage is **not** merely "Docmost-related tasks."

The intended usage is:

- Docmost MCP is the primary **long-term** documentation source for the active project - remote pages are not presumed stale or deprecated
- established project direction, user decisions, and documented behavior should be read from Docmost when not fully present in the prompt
- internal session documentation and Docmost documentation are complementary - use both
- if the user refers to docs, documentation, a documented page, or a file/path that may be documented externally, check Docmost before guessing
- maintain a local-first replica in the working copy being edited; if no `local_root` is passed, use the default location at `./{space_name}-replica/`

Recommended local-replica behavior:

1. choose the active working-copy replica root; if omitted, the default is `./{space_name}-replica/`
2. use `get_replica_structure(space_id, local_root?)` as the source for the initial replica layout
3. use `create_local_replica_page(..., local_root?)` for new local-only pages not yet on remote
4. use `get_sync_status(..., local_root?)` to discover which local files are unsynced and how each one maps to remote Docmost
5. use `get_sync_diff(..., local_root?)` to inspect all differing sections and line ranges whenever local and remote diverge
6. use `pull_replica(..., local_root?)` to refresh missing or remote-ahead pages locally
7. use `push_replica(..., local_root?)` to send local-ahead or local-only pages to remote Docmost
8. leave selectors empty for whole-space sync, pass `page_ids` for selected tracked pages, or pass `local_paths` for a single local-only page
9. if another working copy has pushed in between, the stale working copy must pull or deliberately force after reviewing the diff
10. never delete remote pages based solely on a missing local file without user confirmation

## Replica structure and naming standard

Use the replica surfaces when you want the client to stop guessing local layout.

- use `get_replica_standards()` or `GET /replica/standards` for the shared policy
- use `get_replica_structure(space_id, local_root?)` or `GET /spaces/{space_id}/replica-structure?local_root=...` for the full local layout of an existing remote space
- use `create_local_replica_page(...)` or `POST /spaces/{space_id}/sync/local-pages` when creating a new local-only page in the selected local working copy
- use `resolve_replica_directory_name(...)` or `GET /replica/resolve-directory-name` only when you need to inspect naming behavior directly

Replica root:

- root path: `./{space_name}-replica/`
- spaces in the space name are replaced with hyphens (e.g. "Local LLM Helper" -> `./Local-LLM-Helper-replica/`)
- no spaces are allowed in any local directory or file name

Per-page replica mapping:

- every Docmost page maps to a **directory**
- the page's own content lives in `page.md`
- the page's metadata lives in `_meta.json`
- the page's sync bookkeeping lives in `_sync.json`
- child pages become nested subdirectories under the parent page directory
- the replica tree output already maps each remote page to:
  - page `id`
  - page `title`
  - `content_file_path`
  - `meta_file_path`
- use that mapping plus each page directory's `_meta.json` to tell the user which local file corresponds to which remote page

Replica root support files:

- `_replica.json` stores canonical replica metadata
- `_tree.json` stores the canonical resolved tree snapshot used for the replica
- `_sync.json` stores server-managed replica sync state

Directory naming rule:

1. use the filesystem-safe page title as the base directory name - spaces are replaced with hyphens
2. if sibling pages collide at the same level, use `{title}__{slug_id}`
3. if `slug_id` is missing or still collides, use `{title}__{short_page_id}`
4. no spaces are allowed in any local directory or file name at any level

Sync and truth rule:

- remote Docmost is the long-term authoritative documentation source - not assumed stale
- the editable working copy is whichever replica root the client selected for the operation
- when local replica files are edited, `get_sync_status` must call out the changed local file paths explicitly
- when those edited files correspond to remote pages, sync status must identify the remote page title and page id
- when local and remote diverge, `get_sync_diff` must return all differing sections and line ranges
- when one working copy pushes before another, the stale working copy must be blocked until it pulls or intentionally forces after reviewing the diff
- to sync: use `push_replica` and `pull_replica` as the primary workflow, and use `force` only after a deliberate resolution choice

The MCP server also publishes built-in instructions (from `app/mcp_server.py` `SERVER_INSTRUCTIONS`):

```text
This server exposes Docmost spaces and pages for both reading and writing.

## Reading
Use list_spaces to find the correct space. Use get_space_tree for page hierarchy.
Use list_pages for a flat page list. Use get_page for a single page with markdown content.
If the user gives a space name rather than a UUID, resolve it with list_spaces first.
Pages are always space-scoped - always pass space_id together with page_id.

## Writing
All write tools authenticate automatically - never call an auth tool first.
Use create_space to create a new space (slug must be alphanumeric, no dashes).
Use create_page to create a page. Pass parent_page_id to create nested child pages.
Use update_page to update an existing page's title and/or content.
  Prefer update_page over delete+create - Docmost preserves page history on update.
  Use operation='replace' (default) to overwrite, 'append' or 'prepend' to add content.
Use delete_page to soft-delete a page (it moves to Docmost trash).
Use delete_space to permanently delete a space and all its contents.
All content is markdown in and out. Never pass ProseMirror JSON to write tools.

Content formatting rules (applies to all page content passed to create_page and update_page):
Do NOT use Unicode typographic characters in page content. These characters are not reliably
rendered across all Docmost consumers and may appear as garbled text or question marks.
Forbidden characters and their plain-text replacements:
  em dash (-)    -> use hyphen with surrounding spaces ( - ) or a plain hyphen (-)
  en dash (-)    -> use a plain hyphen (-)
  right arrow (->) -> use the two-character sequence ->
  double arrow (=>) -> use the two-character sequence =>
  ellipsis (...)  -> use three plain dots (...)
  curly quotes (" " ' ') -> use straight quotes (" and ')
When inline text separation is needed, use a plain hyphen (-) as the separator.

All IDs passed to write tools (space_id, page_id, parent_page_id) must originate from a
prior MCP tool response in the current session - never from memory, local files, or inference.
  - space_id: must come from list_spaces or create_space.
  - parent_page_id: must come from list_pages, get_space_tree, or a create_page response.
A 404 from any write tool means the given ID does not exist in the live Docmost instance.
Resolve by calling the appropriate read tool (list_spaces, list_pages) to obtain a valid ID.

## Replica management
Maintain or create a local-first replica in the working copy being edited. If local_root is omitted, use the default location at `./{space_name}-replica/`.
All local replica directory and file names must not contain spaces - replace with hyphens.
Use get_replica_structure(space_id, local_root?) for the initial local replica layout.
Use create_local_replica_page(..., local_root?) for local-only additions.
Use get_replica_standards and resolve_replica_directory_name only when you need to inspect naming behavior directly.
Call get_sync_status(space_id, local_root?) first to classify the current state before choosing a sync action.
Use get_sync_status to identify changed files, map them to remote pages, and report whether they are local-only, remote-only, or conflicting.
Use get_sync_diff(space_id, ..., local_root?) to return differing sections and line numbers for every clash.
Use get_sync_diff before any force pull or force push decision.
Use pull_replica(..., local_root?) and push_replica(..., local_root?) as the primary sync workflow. Leave selectors empty for whole-space sync, pass page_ids for selected tracked pages, or pass local_paths for a single local-only page. Only force a winner after a deliberate resolution choice.
If one working copy pushes before another, the stale working copy must pull or intentionally force after reviewing the diff.
When a sync result returns recommended_next_action, follow that next step instead of retrying the same blocked operation.
If content looks stale, deprecated, or inconsistent with verified behavior, say so explicitly.
If requested data is missing, report that explicitly instead of guessing.
```

## Architecture

Typical deployment:

1. the live Docmost stack already exists on a server
2. this service runs as a separate container on that same server
3. this service joins the same Docker network as Docmost so it can reach the Docmost PostgreSQL container
4. Copilot CLI runs on a different machine and connects remotely to `https://<YOUR_DOCMOST_MCP_HOST>/mcp`

## Files in this project

Important files:

| File | Purpose |
|---|---|
| `Dockerfile` | builds the Docmost MCP image |
| `docker-compose.yml` | runs the Docmost MCP container |
| `env.example` | example runtime configuration |
| `requirements.txt` | Python dependencies |
| `app/main.py` | FastAPI application entrypoint |
| `app/mcp_server.py` | MCP server and all MCP tool definitions |
| `app/models.py` | shared Pydantic models for request/response |
| `app/docmost_auth/auth.py` | Docmost login; stores JWT in memory; never persisted |
| `app/query/docmost.py` | DB + REST read operations (spaces, pages, tree, replica) |
| `app/query/routers/` | REST GET routes for read operations |
| `app/write/docmost.py` | httpx REST client for all write operations |
| `app/write/routers/spaces.py` | POST/DELETE `/spaces` REST routes |
| `app/write/routers/pages.py` | POST/PUT/DELETE `/spaces/{id}/pages` REST routes |
| `docs/docmost-write-api.md` | Docmost write API notes (auth, POST-only, response wrapper) |

## Data model

**Spaces** - `public.spaces`

Columns exposed: `id`, `name`, `description`, `slug`, `visibility`, `default_role`,
`creator_id`, `workspace_id`, `created_at`, `updated_at`.

**Pages** - `public.pages`

Columns exposed: `id`, `slug_id`, `title`, `icon`, `position`, `parent_page_id`,
`creator_id`, `last_updated_by_id`, `space_id`, `workspace_id`, `is_locked`,
`content`, `created_at`, `updated_at`.

Deleted Docmost rows are excluded by checking `deleted_at IS NULL`.

## Known issues

**Page title duplication (fixed)** — `create_page` and `update_page` both pass `title` as
a dedicated field; Docmost renders it as the page header above the body. `SERVER_INSTRUCTIONS`
and tool descriptions now explicitly prohibit including the title as a `# Heading` in the
content body, which previously caused it to render twice. Pages created before this
instruction fix still carry a duplicate `# Heading` in their stored content — `update_page`
will not strip it automatically; content must be explicitly rewritten to remove it.

## License

See `LICENSE`.
