This page covers the bridge database tables, the read models returned to clients, and the
reconcile request / response shape. The revision hash that ties them together is defined at the
bottom.

## Bridge tables (`migrations/bridge/*.sql`)

### page_versions (append-only history)

`id`, `page_id`, `space_id`, `revision_hash`, `title`, `content`, `slug_id`, `parent_page_id`,
`position`, `icon`, `source`, `source_write_intent_id`, `remote_updated_at`, `observed_at`,
`created_at`. Unique on `(page_id, revision_hash)`. `source` is one of `bridge_write`,
`external_observer`, `bootstrap`, `rerender` (a forced re-render recorded by `resync_space`).

### page_heads (current head per page)

`page_id` (PK), `space_id`, `current_version_id`, `current_revision_hash`, `title`, `content`,
`slug_id`, `parent_page_id`, `position`, `icon`, `remote_updated_at`, `is_deleted`, `last_source`,
`last_checked_at`, timestamps.

### write_intents

`id`, `page_id`, `space_id`, `action` (`create_page` / `update_page` / `move_page` /
`delete_page` / `delete_space`), `caller_mode` (`helper` / `auto_sync` / `crud`), `status`,
`expected_base_revision_hash`, `target_revision_hash`, `title`, `content`, `parent_page_id`,
`operation`, `error_text`, `remote_page_id`, timestamps.

### write_receipts

`id`, `write_intent_id`, `page_id`, `space_id`, `expected_revision_hash`, `status`, `expires_at`,
timestamps. The observer confirms a pending write by matching the read-back hash to a receipt.

### observer_checkpoints

`page_id` (PK), `space_id`, `last_seen_remote_updated_at`, `last_observed_revision_hash`,
timestamps. Lets the worker skip pages whose Docmost `updated_at` has not advanced. A
`resync_space` forced re-render deliberately bypasses this gate so every page is re-rendered and
re-anchored even when its stored content did not change.

### local_page_snapshots

`id`, `page_id`, `space_id`, `local_path`, `content`, `base_revision_hash`, `snapshotted_at`,
`status`, `created_at`. Backs the helper stash used during conflict resolution.

## Read models (returned to clients)

- Space: `id`, `name`, `slug`, `description`, visibility / role / workspace / timestamps.
- Page: `id`, `slug_id`, `title`, `icon`, `position`, `parent_page_id`, `space_id`, `is_locked`,
  `content` (markdown), timestamps. The helper page read also carries `current_revision_hash`
  from the bridge head.
- Tree: `root_pages` (nested) plus `orphan_pages`; `parent_page_id = null` means a top-level page.

## Reconcile contract

Request (`POST /v1/spaces/{id}/reconcile`): `scope` (`space` / `tree` / `page`), optional
`scope_id`, the local `pages[]` (each: `page_id?`, `title`, `content`, `parent_page_id`,
`position`, `icon`, `base_revision_hash`, `local_path`, `parent_local_path`), and the last-synced
`tree[]` (`page_id`, `parent_page_id`, `position`, `icon`).

Server response - four buckets plus errors:

| Bucket | Meaning |
| --- | --- |
| `synced` | already in sync; carries the current head hash so the helper can refresh a stale base |
| `applied` | a clean one-sided change was applied (`pushed` / `created` / `pulled` / `moved` / `structural`); carries content only when the helper must write a local file |
| `conflicts` | both sides changed; carries `remote_content`, `local_content`, and a diff for a decision |
| `deletion_confirmations` | a deletion needs confirmation (`remote` or `local`) |

Reconcile never applies a conflict or a deletion on its own.

The server response above is what the helper consumes internally. The helper's own model-facing
summary is leaner: it writes applied content into the local files and then returns `applied[]` as
metadata only (no page content), adding `applied_count`. Only `conflicts` and `errors` carry
content out to the model. See the Helper page for that summary shape.

## Caller modes and head alignment

Every bridge write runs in one of three caller modes recorded on the intent:

- `helper` / `auto_sync` - require head alignment: the caller must pass a `base_revision_hash`
  matching the current head, so a stale client cannot clobber a newer head (a mismatch is a
  conflict, not a silent overwrite).
- `crud` - no alignment requirement; used by the direct `/spaces/*` REST write routes.

## Revision hash

```
revision_hash = sha256( canonical_title + "\n---\n" + canonical_content )

```

It is bridge-internal (never stored in Docmost) and is derived at exactly one place,
`app/bridge/services/canonical.py`, always from Docmost's stored content read back and rendered
to markdown.

How the canonical markdown is produced: Docmost stores page bodies as ProseMirror JSON, parsing
inbound markdown with the `marked` parser (`breaks: true`) plus its callout/math extensions. The
bridge renderer (`app/query/prosemirror.py`) is the faithful inverse of that ingest: it emits the
markdown that re-imports to the same ProseMirror tree, matching the conventions of Docmost's own
serializer - ATX `#` headings, `-` bullets, `N.` ordered lists, fenced code, `---` rules, `- [x]`
task items, `:::type` callouts, inline math (`$...$`) and block math (double-dollar), and
marker-width indent per nested-list level - two spaces under a `-` bullet or task item, three under a
`1.` ordered item, widening with the marker (four under `10.`), so a nested ordered list re-imports
nested instead of flattening. So structure round-trips: nested lists stay nested, tables keep their columns,
callouts keep their type. Escaping is position-aware - a token is escaped only where the parser
would read it as structure at that position (a leading `-`/`#`/`>`/`N.`, a literal `|` inside a
table cell, emphasis runs in prose, code via backtick-run escalation) - so ordinary prose keeps its
punctuation. The renderer is deterministic (it strips Docmost's volatile per-node ids), so every
surface (helper push, direct CRUD, the worker/observer, and direct Docmost-UI edits) ends up as the
same stored ProseMirror and renders identically: a write-origin head and an observe-origin head for
identical content are identical, with no input-vs-rendered drift.

A consequence for clients: after a write, the head (and the content the helper writes back to the
local replica) is this canonical rendering. It preserves structure; it differs from the exact bytes
a client typed only in the canonical-form choices above. Treat the post-sync canonical form as the
source of truth.