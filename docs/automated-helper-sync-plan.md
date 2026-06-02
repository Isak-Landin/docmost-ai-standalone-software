# Automated Helper-Driven Sync - Design and Implementation Plan

Status: forward-looking plan. The system is partially implemented; this document defines the target
behavior and the work to reach it. Nothing here is built beyond the pieces explicitly marked as
existing. Companion documents: `docs/automated-helper-sync-architecture.md` (the full architecture -
helper/server surfaces, the CRUD contract, resolution, and the phased build) and
`docs/docmost-write-api.md` (Docmost REST write contract and the v0.71.1 requirement). This doc holds
the behavior invariants those build on.

This plan is written to be drift-resistant. The invariants in sections 2-7 and the guardrails in
section 12 are load-bearing: omitting or "simplifying" any of them changes the behavior and will
produce a sync that misclassifies or corrupts state. Read section 12 before changing anything.

---

## 1. Purpose and boundaries

- **Purpose.** Let MCP-consuming models maintain Docmost documentation programmatically, substituting
  for Docmost's paid API tier on a privately self-hosted instance.
- **Licensing constraint.** The Docmost team explicitly permits this provided it is NOT published
  publicly. Do not open-source or publicly distribute this service.
- **Docmost is separate upstream software.** We do not own or modify it. The bridge integrates from
  the outside: it reads Docmost's PostgreSQL directly (read-only), writes via Docmost's REST API, and
  keeps its own separate bridge PostgreSQL database for version and sync state.
- **Version floor: Docmost v0.71.1 or later.** This is a dependency on Docmost's own request
  pipeline (global `ValidationPipe({ whitelist: true })` strips undeclared fields; from 0.71.1 the
  page DTOs declare `content`/`format`/`operation`, and content is parsed markdown -> HTML ->
  ProseMirror). See `docs/docmost-write-api.md`. Do not assume writes work below 0.71.1.

### Ownership split (do not blur)

- **Server** owns: Docmost integration, bridge state, content/title normalization, revision hashing,
  diffing, reconcile classification, and all remote Docmost writes. The server CANNOT see the client
  filesystem.
- **Helper** owns: local replica file IO, working-copy discovery, maintenance of the local
  descriptors (`_meta.json`, `_tree.json`, `_replica.json`), presenting the MCP tools to the model,
  and applying server-returned results to local files.

---

## 2. Target workflow (authoritative behavior)

- **The consuming model talks ONLY to the helper surface.** The helper (docmost-helper stdio MCP)
  presents the tools and takes the model's requests. The server's own `/mcp` surface is for
  override/inspection/fallback only - it is NOT the model's normal interface.
- **Three tools, one id each, model holds no state:**
  - `sync_space(space_id)`
  - `sync_page_tree(parent_page_id)` - the parent page inclusive plus all descendants
  - `sync_page(page_id)`
  The model passes ONLY that id. It does not pass paths, page content, page state, or base hashes,
  and it is not expected to know any page's sync state.
- **One call performs a full bidirectional reconcile** for the requested scope, in one pass:
  push local-ahead pages, create local-only pages, pull remote-ahead pages, materialize remote-only
  pages, and apply structural changes - see sections 4 and 5 for deletions and moves.
- **Version write-back on BOTH sides after every successful page sync.** The bridge DB version is
  updated AND the local `_meta.json` `base_revision_hash` is updated to the new synced revision. If
  either side is not updated, the next sync will misclassify the page.
- **Full fidelity is mandatory.** A sync must reconcile content, title, deletions, moves /
  re-parenting, position / ordering, and icon / metadata. If any dimension is skipped, the next sync
  on that page or scope will fail. "Content-only" sync is not acceptable.
- **Return contract.** The response reports success for the synced unit and returns real page content
  ONLY for items needing a decision:
  - synced pages: identity only, no content (keeps model context small).
  - conflicts: full detail (see section 3).
  - deletion-confirmations: per page (see section 4).
  - moves: re-parent/reorder applied, page id preserved (see section 5).
- **Best-effort per page.** Clean pages commit immediately (bridge + local `_meta`). Failures are
  returned but do not roll back successful pages. A re-run retries only the unresolved pages
  (idempotent).
- **Model instruction.** The helper/MCP tool instructions must tell the model: if anything is unclear
  or uncertain (a conflict resolution, a deletion decision), ask the user for a definitive answer.

---

## 3. Source of truth, freshness, and what counts as a conflict

- **The bridge DB version tracker is the source of truth**, and it holds full version history. For any
  page it knows the exact content of the version that the local `base_revision_hash` points to AND
  the current remote version. From those it can determine which side is newer and compute both diffs
  (local-vs-its-base and local-vs-current-remote). The sync does NOT fetch live remote per call as its
  comparison base, and it does NOT treat the bridge as a bare head pointer.
- **Worker / observer = fixed 15-second background cadence**, independent of sync calls. Every 15s it
  checks each space page for changes made directly in the Docmost UI (i.e. changes NOT made through
  the bridge), and updates the bridge version ONLY when a change has occurred. This is what keeps the
  bridge truth from falling behind direct-UI edits. The worker is not event-driven and is not
  triggered by sync calls.
- **A local change is NOT a conflict.** Canonical example: a page is at base = version-a with content
  "abc"; the model edits it locally to "abcdef" while remote is still version-a. This is the intended
  local-change case (`local_only_change`) and must push cleanly. The `base_revision_hash` stored in
  `_meta.json` legitimately lags the current local content - that lag is expected, not drift.
- **A conflict is only "both changed since the recorded base".** Local content differs from the base
  AND remote differs from the same base. Only then is the page a conflict.
- **Conflict response payload (per conflicted page):** `remote_version`, `local_version`,
  `remote_content`, `local_content`, and the line-level diff. The model decides how to reconcile and
  asks the user if uncertain. The sync never auto-resolves a conflict.

---

## 4. Deletions

- **Docmost deletes are soft.** A delete sets a `deleted_at` column; the page row is not removed.
  Reads already filter `deleted_at IS NULL`.
- **Sync never deletes silently.** Detected deletions (either direction) are returned as per-page
  deletion-confirmation items in the response. The model confirms each one (and asks the user if
  unsure); a follow-up call applies the confirmed deletions. A sync pass does not delete on its own.
- **Both directions:** a page removed locally implies a soft-delete of the remote page; a
  remote-deleted page implies removing the local copy.
- **Disambiguation requires `_tree.json`.** A real deletion is "was present in the last-synced tree,
  local file is now gone". A page that was simply never materialized locally (present remotely, no
  local file yet) is NOT a deletion - it is a remote-only page to pull/materialize. Globbing
  `page.md` alone cannot tell these apart; the last-synced `_tree.json` snapshot is what makes the
  distinction possible.
- **Deletion of a changed page is a conflict, not a clean confirmation.** If the page targeted for
  deletion on one side has its own changes since the base on the other side, surface it as a conflict
  for the model rather than a simple delete confirmation.

---

## 5. Structural changes (parent / position / icon)

- **Tracked separately from the content revision hash.** `revision_hash` stays `sha256(title +
  separator + content)`. Parent, position, and icon are stored and compared as separate fields in
  bridge state, `_meta.json`, and `_tree.json`. A structural-only change does not change the content
  revision hash.
- **Structural-only changes are non-conflicting** unless both sides changed the same structural field
  to different values.
- **Moves / re-parenting use Docmost's true move endpoint (verified).** Verified 2026-06-01 against
  the live v0.71.1 instance: `POST /api/pages/move {pageId, position, parentPageId}` re-parents a page
  through an external authenticated write AND preserves the page id (no recreate, no lost history). So
  a locally moved page is realized by a bridge move call - the id survives and is unchanged in
  `_meta.json`/`_tree.json`. The bridge must add a `move_page` write function;
  `app/write/docmost.py` currently has only create / update / delete.
- **Icon and other metadata** are synced through `update` - Docmost's `UpdatePageDto` accepts `icon`.
  Note: the current bridge `update_page` sends only title/content/operation/format and must be
  extended to also send `icon` (and any other supported metadata being reconciled).
- **Position / ordering** also go through `POST /api/pages/move` (the same endpoint reorders). The
  `position` is a validated fractional-index string (e.g. `a15Dl`); arbitrary values return
  `400 Invalid move position`. So the bridge must compute a valid fractional position between the
  target siblings when moving or reordering. Track `position` in bridge state and `_meta.json`.

---

## 6. Canonical local replica structure

The legacy on-disk `Docmost-mcp-crud` replica is OUT OF SCOPE for this effort (it uses an old
`_meta.json` shape without `base_revision_hash` and cannot sync). Build and validate against a fresh
replica.

Target structure for a space replica:

- `_replica.json` - space header (includes `space_id`); used by the helper to discover which local
  working copy corresponds to a given `space_id`.
- `_tree.json` - the helper-maintained LAST-SYNCED tree snapshot: every tracked page's id, parent,
  and order at the time of the last successful sync. This is the reference the reconcile diffs the
  current local tree against to detect moves, deletions, and reorders. It is not optional - without
  it, local deletions and reorders cannot be detected.
- Per page directory:
  - `page.md` - the page content (markdown).
  - `_meta.json` - canonical fields: `id`, `slug_id`, `space_id`, `title`, `parent_page_id`,
    `parent_local_dir_path`, `position`, `icon`, `base_revision_hash`, `content_file_path`,
    `meta_file_path`, `active_snapshot` (present only during conflict stashing).

`base_revision_hash` is the recorded sync base and is mandatory for every tracked page; its absence
forces a page to classify as conflicted. `position` and `icon` are mandatory for full-fidelity
structural reconcile.

**Working-copy discovery.** The model passes only an id. The helper resolves the correct local
working copy from a configured base directory plus a `_replica.json` `space_id` match. The model never
passes a path.

---

## 7. Reconcile wire contract (helper <-> server)

The server cannot see the client filesystem, so the helper must send local state explicitly.

- **Helper -> server (per scoped reconcile call):** the current local page set for the scope (each
  page's id if known, title, content, parent, position, icon, `base_revision_hash`, local path) AND
  the last-synced `_tree.json` snapshot (so the server can detect deletions/moves/reorders).
- **Server -> helper:** four result buckets:
  1. `synced` - ids/paths only, no content.
  2. `conflicts` - full content + remote/local version + diff (section 3).
  3. `deletion_confirmations` - per page, both directions (section 4).
  4. `moves` - re-parent/reorder applied via `POST /api/pages/move`, page id preserved (section 5).
- The helper then applies results to local files (write/create/delete/move directories, update
  `_meta.json` and `_tree.json`, apply moves), and returns successes + conflicts + deletion
  confirmations to the model.

---

## 8. Component inventory: exists vs to-build

Exists (extend, do not rebuild):
- Bridge tables + write pipeline (intent -> remote write -> receipt -> version -> head, with
  compensation).
- Observer `observe_space` (runs manually today; needs scheduling and structural fields).
- The 8-state sync engine in `app/sync/service.py` (extend to the combined full-fidelity reconcile).
- Helper `helper/helper/sync.py` and `replica.py`, and the stash / snapshot tools (seed for
  conflict/deletion resolution).
- Bridge DB schema via `migrations/bridge/*.sql` (add columns).

To build / extend:
- Structural fields in bridge state, observer, write functions, and the reconcile.
- The 15-second worker runner.
- The combined reconcile endpoint and wire contract.
- The helper file layer (`_tree.json`, rich `_meta.json`, directory create/delete/move, id remap) and
  the three single-id tools.
- Model-facing helper instructions.

---

## 9. Phased plan

### Phase 0 - Lock the contracts
- Canonical replica structure (section 6) and the reconcile wire contract (section 7).

### Phase 1 - Bridge state + worker (server)
- Migration: add `position` and `icon` to `page_heads` and `page_versions`. Keep
  `revision_hash = sha256(title+content)`; compare parent/position/icon separately.
- Capture structural fields in `snapshot_from_page` and the observer.
- 15-second worker: schedule `observe_space` per tracked space; update bridge version only on detected
  change (incl. direct-UI edits, soft-deletes, moves, position/icon).
- Extend write functions: `update_page` must also send `icon`; add a `move_page` function using
  `POST /api/pages/move` (id-preserving, verified) for re-parent and reorder, with valid fractional
  position computation.

### Phase 2 - Combined reconcile engine (server)
- Scoped reconcile (space / tree / page): per page classify content + title + structural + existence
  using bridge truth + helper-supplied local set + last-synced tree.
- Apply clean cases (push/create/pull/materialize, structural-as-needed). Surface conflicts and
  deletion-confirmations; never auto-delete; reconcile move re-ids.
- Best-effort per page, idempotent. Return the four buckets of section 7.

### Phase 3 - Helper file layer + the three tools (client)
- Maintain `_tree.json`, rich `_meta.json`, `_replica.json`; create/delete/move page directories;
  apply id remaps; atomic writes (already present).
- Working-copy resolution by `space_id` (section 6).
- `sync_space` / `sync_page_tree` / `sync_page`: resolve replica -> load tree + scan pages -> call
  reconcile -> apply results + update descriptors -> return successes + conflicts + deletion
  confirmations.

### Phase 4 - Model-facing instructions
- Helper/MCP instructions: the three capabilities, single-id usage, how to respond to conflicts and
  deletion-confirmations, and "ask the user if unclear".

### Phase 5 - Conflict and deletion RESOLUTION (now designed)
- No longer deferred. Designed in `docs/automated-helper-sync-architecture.md` (section 7): dedicated
  helper tools `resolve_conflict` / `confirm_deletion`, backed by the server stash/snapshot mechanism
  and the resolution endpoints, followed by an auto re-sync. See that doc for the full surfaces, CRUD
  contract, and phased build.

---

## 10. Write path and caller modes (do not regress)

- All bridge page writes carry a `caller_mode`. `crud` does NOT require head alignment (an escape
  hatch for direct, low-level writes). `auto_sync` and `helper` REQUIRE alignment against the bridge
  head (a base mismatch returns a conflict / drift).
- The automated sync MUST use the aligned path (`auto_sync` / `helper`), never `crud`. Using `crud`
  for sync would bypass the safety that distinguishes local-ahead from a true conflict.

---

## 11. Open items to verify (non-blocking)

- Worker host: separate Compose service/process vs in-process asyncio task on the FastAPI app.
- `_replica.json` exact field set for discovery.

(Resolved 2026-06-01: the true-move endpoint `POST /api/pages/move` is verified working through an
external authenticated write - it re-parents and reorders while preserving the page id. Move uses it,
not recreate.)

---

## 12. Drift guardrails (the easy-to-get-wrong invariants)

Do NOT:
- Build the model's normal interface on the server `/mcp` surface. The model uses the helper only.
- Make the model pass paths, page state, or base hashes. One id per call, nothing else.
- Implement sync as push-only or content-only. It is full bidirectional and full fidelity.
- Treat "local content differs from base" as a conflict. That is the intended local-change case.
- Fetch live remote per call as the comparison base, or treat the bridge as a bare head pointer. The
  bridge version history is the truth; the 15s worker keeps it fresh for direct-UI edits.
- Auto-resolve conflicts, or auto-delete anything. Conflicts and deletions are returned for a per-page
  decision; the model asks the user if unsure.
- Return page content for already-synced pages. Only conflicts/deletions/move-remaps carry content.
- Hard-delete in Docmost. Deletes are soft (`deleted_at`).
- Recreate a page on a move. Move uses `POST /api/pages/move` and PRESERVES the page id (verified) - do not create-new + delete-old.
- Fold parent/position/icon into the content revision hash.
- Drop `_tree.json` or use `page.md` globbing alone. The last-synced snapshot is required to detect
  local deletions, moves, and reorders.
- Forget to update BOTH the bridge version and the local `_meta.json` `base_revision_hash` after a
  successful sync. Skipping either side misclassifies the next sync.
- Use `caller_mode = crud` for sync writes.
- Modify Docmost itself, or run against Docmost below v0.71.1, or publish this service publicly.

Do:
- Keep the server and helper ownership boundaries strict (section 1).
- Commit clean pages best-effort and return only what failed; keep re-runs idempotent.
- Build and validate against a fresh replica; the legacy `Docmost-mcp-crud` replica is out of scope.
