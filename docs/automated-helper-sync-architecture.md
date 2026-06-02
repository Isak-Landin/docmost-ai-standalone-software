# Automated Helper Sync - Architecture and Full Implementation Plan

Status: forward-looking plan. This document is the architecture and end-to-end implementation plan
for the automated helper-driven sync. It builds on, and does not restate, the behavior invariants in
`docs/automated-helper-sync-plan.md` (sync semantics, deletions, structural/move rules, replica
structure, drift guardrails). Read that first; this doc covers the surface move, the CRUD contract,
and the full build.

Locked architecture decisions (2026-06-01):

1. The server `/mcp` endpoint is **kept as a quiet, undocumented fallback** for manual/operator use.
   It is not the model's path and is not maintained as a normal surface.
2. The model-facing surface is the **helper MCP** only. The helper is the sole MCP the model uses.
3. The **helper <-> server contract is CRUD/REST (non-MCP)**.
4. **The server classifies, the helper orchestrates.** Classification and diffing live server-side
   (it owns the bridge version truth); the helper drives the overall flow and owns local files.
5. The helper MCP exposes **reads + the 3 sync tools + resolution tools + direct CRUD escape hatches**.
6. Conflict/deletion resolution uses **dedicated helper tools** (`resolve_conflict`,
   `confirm_deletion`) backed by the server stash/snapshot mechanism, followed by an auto re-sync.

---

## 1. Architecture overview

Two deployables, three surfaces:

```
            MCP (stdio)                 CRUD/REST  (/v1, contract-versioned)
 Model  <----------------->  Helper  <----------------------------------->  Server
 (LLM)    helper MCP surface  (client)   helper<->server contract            (bridge)
                              owns:                                          owns:
                              - local replica file IO                       - Docmost integration
                              - _tree.json / _meta.json / _replica.json      - bridge DB version truth
                              - reconcile orchestration + resolution         - classification + diffing
                              - working-copy discovery                       - remote writes (incl. move)
                                                                            - the 15s worker
                                                              quiet fallback: server /mcp (operator only)
```

- **Server** = pure bridge. Docmost reads (direct DB) + writes (Docmost REST, incl. the verified
  `/api/pages/move`), the bridge-owned version database, the reconcile classifier/differ, and the
  worker. It exposes the CRUD/REST contract to the helper. Its `/mcp` stays as a quiet operator
  fallback (decision 1) but carries no model workflow.
- **Helper** = the model's entire interface. A stdio MCP that owns all local-replica automation and
  orchestrates sync/resolution by calling the server CRUD contract. It may forward simple reads, but
  it is not a dumb proxy - it holds the local file logic and the orchestration loop.

The model knows only the helper's capabilities. It never sees the server, the bridge DB, the CRUD
contract, `caller_mode`, or page state.

---

## 2. Surface map - what lives where

### 2a. Helper MCP surface (model-facing, decision 5)

| Group | Tools |
|---|---|
| Reads (id discovery) | `list_spaces`, `get_space`, `get_space_tree`, `list_pages`, `get_page` |
| Automated sync (single id) | `sync_space(space_id)`, `sync_page_tree(parent_page_id)`, `sync_page(page_id)` |
| Resolution (decision 6) | `resolve_conflict(space_id, page_id, merged_content)`, `confirm_deletion(space_id, page_id, direction)` |
| Direct CRUD escape hatches | `create_page`, `update_page`, `delete_page`, `move_page`, `create_space`, `delete_space` |

- Sync tools take exactly one id and no state. Reads return ids/titles only.
- Resolution tools are used only after a sync returns conflicts/deletion-confirmations.
- Escape hatches are explicit overrides; normal work goes through sync. They still flow through the
  server's bridge pipeline (tracked), never around it.

### 2b. Server CRUD/REST contract (helper-facing) - section 5.

### 2c. Server `/mcp` - quiet fallback only (decision 1). Strip its model-facing instructions; keep
the read/inspection tools working for a human operator. Do not document it for the model.

---

## 3. Helper functionality (internal)

The helper owns everything local. Components (under `helper/`):

- **Working-copy discovery.** Map a `space_id` to a local replica root via a configured base
  directory + `_replica.json` `space_id` match (behavior doc section 6). The model passes only ids.
- **Replica file layer.** Read/write `page.md`, per-page `_meta.json` (full field set), the maintained
  `_tree.json` last-synced snapshot, and `_replica.json`. Atomic writes (already present). Create,
  delete, and move page directories; apply server-returned snapshots.
- **Reconcile orchestration.** For each sync call: resolve the working copy -> load `_tree.json` +
  scan the current local pages (content, title, parent, position, icon, base_revision_hash) -> POST
  the local page set + `_tree.json` + scope to the server reconcile endpoint -> apply the returned
  results to local files (write/create/delete-dir/move-dir, update `_meta.json` + `_tree.json`) ->
  return to the model: success summary + only conflicts + deletion-confirmations (with content).
- **Resolution orchestration.** Drive `resolve_conflict` / `confirm_deletion` against the server, then
  auto re-sync just the affected pages.
- **Contract-version check.** On startup, GET the server contract version and refuse/ warn on mismatch
  (section 12).

The helper holds no version truth - it always reflects what the server returns. The only local state
it persists is the sync base (`base_revision_hash`) and `active_snapshot` in `_meta.json`, plus the
`_tree.json` snapshot.

---

## 4. Reconcile pipeline (end to end)

A single `sync_*` call:

1. **Model -> helper:** `sync_space(space_id)` (or tree/page with the one id).
2. **Helper (local):** resolve working copy; load `_tree.json`; scan local pages into a payload:
   `[{page_id?, title, content, parent_page_id, position, icon, base_revision_hash, local_path}]` +
   the last-synced `_tree.json` + `scope`.
3. **Helper -> server:** `POST /v1/spaces/{id}/reconcile` with that payload.
4. **Server (classify + apply, best-effort per page):** using the bridge version truth (kept fresh by
   the worker) it classifies each page (content+title+structural+existence) and:
   - applies the clean cases itself - push (update), create, pull/materialize (returns remote
     snapshot), move (`/api/pages/move`, id-preserving), structural update;
   - **does not** apply deletions or conflicts - returns them for a decision;
   - advances bridge versions for everything it applied.
   Returns four buckets: `synced`, `applied` (with canonical snapshots + new `base_revision_hash`),
   `conflicts` (full content + remote/local version + diff), `deletion_confirmations` (pending, both
   directions).
5. **Helper (apply local):** for `applied`/`synced`/pulled snapshots, write `page.md` + `_meta.json`
   (new base hash) + update `_tree.json`; create/delete/move directories as the result dictates.
6. **Helper -> model:** success summary (counts), plus only the conflicts and deletion-confirmations,
   each carrying `remote_version`, `local_version`, `remote_content`, `local_content`, diff.
7. **Model** decides on conflicts/deletions and calls the resolution tools (section 7), or asks the
   user if unclear.

Best-effort per page and idempotent: a re-run only retouches unresolved pages.

---

## 5. Server <-> helper CRUD contract

REST, JSON, versioned under `/v1`, contract-version-stamped. The existing `/helper/v1` + `/auto-mcp`
surfaces are consolidated into this single contract; `/spaces/*` direct REST may remain for other
HTTP integrations but the helper uses `/v1` only.

### 5a. Reads (resources)

| Method | Path | Returns |
|---|---|---|
| GET | `/v1/spaces` | spaces |
| GET | `/v1/spaces/{id}` | one space |
| GET | `/v1/spaces/{id}/tree` | page tree (id, parent, position, has_children) |
| GET | `/v1/spaces/{id}/pages` | pages (no content) |
| GET | `/v1/spaces/{id}/pages/{pid}` | one page: content, title, parent, position, icon, `current_revision_hash` |

### 5b. Writes (resources, bridge-tracked - back the direct CRUD escape hatches)

| Method | Path | Action |
|---|---|---|
| POST | `/v1/spaces` | create space |
| DELETE | `/v1/spaces/{id}` | delete space |
| POST | `/v1/spaces/{id}/pages` | create page |
| PUT | `/v1/spaces/{id}/pages/{pid}` | update title/content/icon (operation replace/append/prepend) |
| POST | `/v1/spaces/{id}/pages/{pid}/move` | re-parent/reorder via Docmost `/api/pages/move` (id-preserving) |
| DELETE | `/v1/spaces/{id}/pages/{pid}` | soft-delete |

### 5c. Reconcile + resolution (the brain - decision 4)

| Method | Path | Action |
|---|---|---|
| POST | `/v1/spaces/{id}/reconcile` | classify + apply clean cases; return the four buckets (section 4). Body: `{scope, pages[], tree}` |
| POST | `/v1/spaces/{id}/pages/{pid}/stash` | snapshot current local content server-side; returns `snapshot_id` |
| POST | `/v1/spaces/{id}/pages/{pid}/resolve` | apply a conflict resolution (push `merged_content` aligned to current remote head); clears stash |
| POST | `/v1/spaces/{id}/pages/{pid}/confirm-deletion` | apply a confirmed deletion in the given direction |
| GET | `/v1/spaces/{id}/pages/{pid}/snapshots/{sid}` | read a stash snapshot |

### 5d. Operational

| Method | Path | Action |
|---|---|---|
| GET | `/v1/contract` | contract version + capabilities (for the helper handshake) |
| GET | `/v1/health` | process health |
| POST | `/v1/spaces/{id}/observe` | force one worker pass (operator/diagnostic; normally the worker runs on its own) |

Caller mode: all `/v1` writes and reconcile run in the aligned (`auto_sync`/`helper`) bridge mode -
they require version alignment and surface drift as conflicts. The `crud` (no-alignment) mode stays
internal to the quiet `/mcp` fallback.

---

## 6. Server versioning (bridge DB)

Source of truth (behavior doc section 3). Tables: `page_heads`, `page_versions`, `write_intents`,
`write_receipts`, `observer_checkpoints`, `local_page_snapshots`. To build:

- Add `position` and `icon` columns to `page_heads` + `page_versions` (migration 003). Keep
  `revision_hash = sha256(title + content)`; compare `parent_page_id` / `position` / `icon`
  separately (structural changes are non-conflicting unless both sides changed the same field).
- A version advances on every confirmed write (helper-driven or escape-hatch) and on every external
  change the worker observes. Each `page_head` carries the current revision + structural fields; each
  write appends a `page_version`.
- The helper's `base_revision_hash` is the head revision at the page's last successful sync; the
  server uses it to distinguish local-ahead from both-changed.

---

## 7. Resolution pipeline (decision 6)

After a sync returns conflicts/deletions, the model uses dedicated helper tools:

- **`resolve_conflict(space_id, page_id, merged_content)`** -> helper: `POST .../stash` (save current
  local), then `POST .../resolve` with `merged_content` (server pushes it aligned to the current
  remote head, advances the version), then writes the resolved content + new base locally and clears
  the stash. Then an auto re-sync of that page confirms `synced`.
- **`confirm_deletion(space_id, page_id, direction)`** -> helper: `POST .../confirm-deletion`;
  `direction = remote` soft-deletes the remote page and removes the local dir + `_tree.json` entry;
  `direction = local` recreates/keeps per the model's choice. Nothing is deleted without this call.

The stash/snapshot tables already exist and are the backing store. Deletions are soft in Docmost
(`deleted_at`) and never silent (behavior doc section 4).

---

## 8. Worker (server, separate container, same stack)

- A dedicated Compose service in the same stack (decision: separate container) running a fixed
  **15-second** loop: per tracked space, `observe_space` checks each page for changes made directly in
  the Docmost UI (non-bridge) and advances the bridge version **only when a change occurred** -
  including content, title, parent (move), position, icon, and soft-deletes.
- Independent of sync calls; it keeps the bridge truth fresh so reconcile classifications are correct.
  `POST /v1/spaces/{id}/observe` exists only as an operator/diagnostic trigger.
- Reuses `observe_space`; extend its snapshot to capture position/icon/parent.

---

## 9. Data, version, and update management (end to end)

- **Data flow:** content/title/structure originate either locally (model edits the replica) or
  remotely (Docmost UI). Local changes flow helper -> `/v1/reconcile` -> Docmost write -> bridge
  version. Remote changes flow Docmost -> worker -> bridge version -> next reconcile -> helper ->
  local files.
- **Version management:** every page carries one revision identity (content+title hash) plus tracked
  structural fields; the bridge DB holds the authoritative head + history; the helper mirrors the
  head as its `base_revision_hash` after each successful sync.
- **Updates:** a page update (content/title/icon) is a `PUT`; a move/reorder is a `move`; a create is a
  `POST`; a delete is a confirmed soft-delete. All are bridge-tracked and version-advancing. The next
  sync after any update sees a consistent base and classifies correctly - the full-fidelity rule
  (behavior doc section 2) guarantees no dimension is skipped, so a later sync cannot fail on
  unreconciled drift.

---

## 10. Phased implementation

### Phase 0 - Contracts
- Freeze the `/v1` CRUD contract (section 5), the reconcile payload/buckets (section 4), the canonical
  replica structure, and the contract-version string.

### Phase 1 - Server bridge state + writes + worker
- Migration 003: `position`, `icon` on `page_heads`/`page_versions`.
- Capture structural fields in `snapshot_from_page` and `observe_space`.
- Write functions: `update_page` also sends `icon`; add `move_page` (Docmost `/api/pages/move`,
  id-preserving) with valid fractional-position computation.
- Worker: separate Compose service, 15s loop, change-only version advance.

### Phase 2 - Server reconcile + `/v1` contract
- Build `POST /v1/spaces/{id}/reconcile`: classify (content+title+structural+existence) using bridge
  truth + helper payload + `_tree.json`; apply clean push/create/pull/move; return the four buckets;
  never auto-delete; best-effort per page; idempotent.
- Build the resolution endpoints (`stash`/`resolve`/`confirm-deletion`) and the resource CRUD + reads
  under `/v1`, with `/v1/contract` and `/v1/health`.
- Repoint/consolidate `/helper/v1` + `/auto-mcp` into `/v1`.

### Phase 3 - Helper file layer + orchestration
- Maintain `_tree.json`, rich `_meta.json`, `_replica.json`; create/delete/move directories; apply
  server snapshots; working-copy discovery by `space_id`.
- Reconcile orchestration (section 4) and resolution orchestration (section 7).

### Phase 4 - Helper MCP surface
- Expose the full toolset (section 2a): reads, `sync_space`/`sync_page_tree`/`sync_page`,
  `resolve_conflict`/`confirm_deletion`, and the direct CRUD escape hatches (mapped to `/v1` writes).
- Model-facing instructions: single-id usage, how to read sync results, how to use resolution tools,
  and "ask the user if anything is unclear".

### Phase 5 - Server `/mcp` demotion + contract handshake
- Strip the server `/mcp` of model-facing workflow instructions; keep read/inspection tools as the
  quiet operator fallback.
- Helper-side contract-version handshake against `/v1/contract`.

### Phase 6 - End-to-end validation
- Validate against a fresh replica: whole-space, tree, and single-page sync; every dimension
  (content, title, move/re-parent, reorder, icon, create, delete); conflict + deletion resolution;
  external-UI-edit detection through the worker; best-effort partial-failure + idempotent re-run.

---

## 11. Cross-cutting

- **Idempotency:** reconcile and all writes are safe to retry; re-running a sync only retouches
  unresolved pages.
- **Contract versioning:** `/v1` plus a `/v1/contract` version the helper checks on startup; bump on
  any breaking contract change; the helper refuses a mismatched major version.
- **Error handling:** server maps Docmost/bridge failures to typed HTTP (`409` drift/conflict, `404`
  not found, `502` upstream, `503` DB); the helper surfaces these to the model as actionable states,
  never as silent failure.
- **Security/auth:** the server holds Docmost credentials (env); the helper never sees them. The `/v1`
  contract is reachable only to the helper's deployment (network-scoped), as today.
- **Helper delivery:** the helper stays a stdio MCP in `helper/`, versioned with the repo; client
  update = pull forgejo + reinstall. The contract handshake catches helper/server skew.

---

## 12. Drift guardrails (additions to the behavior doc's section 12)

Do NOT:
- Put model workflow on the server `/mcp` - it is a quiet operator fallback only.
- Let the helper become a dumb proxy - it owns local files, orchestration, and resolution.
- Move classification/diffing into the helper - the server classifies (it owns version truth).
- Speak MCP between helper and server - that pipeline is `/v1` CRUD only.
- Apply deletions or conflicts inside `reconcile` - those are returned for a decision and applied only
  via the resolution endpoints.
- Skip the contract-version handshake, or let `/v1` writes run in `crud` (no-alignment) mode.

Do:
- Keep the model on one id per sync call, with content surfaced only for conflicts/deletions.
- Keep every write (sync, escape hatch, worker) bridge-tracked and version-advancing.
- Run the worker as its own 15s container in the same stack.

---

## 13. Skill and MCP usage (baked into the build)

Every part of this build is governed by the established skills; follow them rather than ad-hoc
reasoning. Concretely:

- **contract-boundaries** - any value crossing a boundary must stay in sync. Locked contracts in this
  build: the schema path `app/bridge/db/schema.py` (`parents[3]/migrations/bridge`) MUST match the
  Dockerfile `COPY migrations/ /app/migrations/` (this exact contract was broken and caused
  `relation "page_heads" does not exist`); the `_meta.json` field set vs the server read/write fields;
  `revision_hash = sha256(title+content)` shared by server and helper; the `/v1` contract version
  shared by server and helper; the env keys mirrored across `env.example`/`.env`/compose.
- **module-decomposition** - placement: server logic under `app/` (bridge, sync->reconcile,
  helper_api->`/v1`, write, query, observer); migrations under `migrations/bridge/`; the client under
  `helper/`. Do not put client logic in the server image or server logic in the helper.
- **docker-compose-service-debugging** - rebuild vs recreate vs restart: image/Dockerfile/deps changed
  -> `docker compose build` + `up -d`; only `.env`/env changed -> `up -d --force-recreate --no-deps`;
  process stuck, definition unchanged -> `restart`. The worker is added as its own Compose service.
- **remote-iteration-loop** - author locally, deliver through git: `git push forgejo <branch>` ->
  remote `git pull forgejo <branch>` -> rebuild/recreate -> verify. Remote is `forgejo`, not `origin`.
- **remote-server-ssh** - reach the webserver host (`isakadmin@64.112.126.69`, key `~/.ssh/id_ed25519`)
  for deploy and inspection; the remote repo's forgejo key is `/home/isakadmin/.ssh/mcp-docmost` via
  its `.envrc` `GIT_SSH_COMMAND` (not auto-loaded in non-interactive ssh - set it explicitly).
- **external-provider-integration** - Docmost is the external provider: ground request/response shapes
  in the running container's compiled source (DTOs, routes, interceptor), use idempotent ensure flows
  (`ensure_space_bootstrapped`, `ensure_schema`), and handle missing credentials explicitly (the
  placeholder-creds incident).
- **development-env-real-values** - `env.example` holds the real working values for this private setup
  (incl. `STRONG_*` DB passwords, real Docmost creds); copy `env.example` -> `.env` on deploy. Never
  swap real values for fake placeholders.
- **documented-answers** - for any Docmost behavior question, verify against the container source, not
  recollection (this is how move-vs-recreate and the v0.71.1 pipeline were settled).
- **web-coder** - for HTTP/REST/transport details of the `/v1` contract and the MCP stdio transport.

MCP usage during the build:

- **docker-mcp** - inspect/operate the engine (ps, logs, exec) when diagnosing the deployed stack.
- **docmost-helper** (the client MCP) - the surface under test; consume it via the local registration
  to validate end to end. **docmost-mcp** (server `/mcp`) - quiet fallback/inspection only.
- **chrome-devtools** - only if browser debugging becomes an unavoidable derived requirement.
