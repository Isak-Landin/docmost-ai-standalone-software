# Docmost MCP Server — Claude Code instructions

Use the **docmost-helper** stdio MCP for all Docmost reads, writes, and sync. It is the only
Docmost surface you need.

## Local replica

The helper keeps a local replica of a Docmost space as a directory tree, one directory per page:

- `page.md` — the page content. Edit it locally; the helper pushes your edits on the next sync.
- `_meta.json` — helper-managed. Do not edit it.

Restructure the hierarchy by moving a page's directory; the helper re-parents the page to match
the new nesting on the next sync.

## Normal sync workflow

You only initiate a sync; the helper does everything else.

1. Edit `page.md` locally and/or move page directories to restructure.
2. Call `sync_space(space_id)` (or `sync_page(space_id, page_id)` /
   `sync_page_tree(space_id, parent_page_id)`) with only the id(s).
3. The helper reconciles in one pass: pushes your edits, creates new local-only pages, pulls
   remote changes, materializes new remote pages, and applies moves/re-parents.
4. The result is a summary: `synced_count` (already in sync) + `applied_count` / `applied[]`
   (changed this run — metadata only; page content is written to your local files, not returned),
   plus only the items needing a decision: `conflicts[]` (each with `remote_content`,
   `local_content`, diff) and `deletion_confirmations[]`. Confirm a change via `applied_count` /
   `errors[]`, not `synced_count`. A clean sync needs no force and surfaces no conflicts.

## Conflict + deletion resolution

When a sync returns `conflicts[]` or `deletion_confirmations[]`:

- Conflict (both sides changed): inspect `remote_content` / `local_content` / diff, then call
  `resolve_conflict(space_id, page_id, merged_content)` with the final merged markdown. Ask the
  user if the right merge is unclear.
- Deletion: call `confirm_deletion(space_id, page_id, direction)` — `remote` deletes the remote
  page and drops the local copy; `local` accepts a remote deletion by dropping the local copy.
  Sync never deletes on its own.

`stash_page` / `accept_remote` / `push_pages` / `pull_pages` remain as low-level escape hatches;
normal work goes through the three sync tools.

## Whole-space resync

`resync_space(space_id)` is an occasional whole-space variant of `sync_space`. It first re-renders
EVERY page from Docmost on the server (not just pages whose content changed), then runs the same
two-way reconcile. Use it when you need every page brought into sync regardless of whether it
changed — for example after the server's markdown rendering was changed, so pages that were never
re-edited still pick up the corrected rendering, or to recover from suspected drift. A page whose
only difference is the re-render heals automatically as a pull (no content returned); a page that
also has un-pushed local edits surfaces as a `conflicts[]` entry for your decision. It never
force-pushes, so it cannot overwrite or corrupt either side, and it returns the normal summary
plus `reanchored_count` (pages whose server render changed this run). Prefer plain `sync_space` for
everyday work.

## Replica git backup (automatic)

The replica stays a tracked part of this repo (it is NOT gitignored). When this repo opts in via
`DOCMOST_REPLICA_GIT_AUTOSYNC` in its `.envrc`, a helper-managed cron commits and pushes replica
changes to the repo's own git remote on a schedule. So replica edits are versioned for you: do not
be surprised to find them already committed/pushed, and do not manually `git` the replica. This is
git-only automation; the Docmost<->local sync above is still yours to run.

## IDs

All `space_id`, `page_id`, and `parent_page_id` values must come from live tool responses in the
current session (`list_spaces`, `list_pages`, `get_space_tree`). Never use IDs from memory or
inference.

## Content rules

- All content is markdown. Never pass any other format.
- Page title is a separate parameter — do not include it as a `# Heading` in the content body.
- Use plain ASCII punctuation — no Unicode em-dashes, curly quotes, or ellipsis characters.
