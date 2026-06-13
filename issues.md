# Known Issues

Status:
- ISSUE-3 (False `both_changed` conflict on a remote-only advance): FIX IMPLEMENTED on branch dev
  (2026-06-13), pending live verification after deploy + helper restart. The root cause was NOT the
  reconcile classifier itself - the normal reconcile path is anchor-honest and never produces
  ISSUE-3 - but the low-level escape hatches (`push_pages`, `accept_remote`) breaking the
  anchor-honesty invariant the normal path maintains. See "Resolution" below; the original diagnosis
  is retained beneath it for reference.

This file is the dedicated issues log for docmost-mcp-server.

(The prior ISSUE-2 entry - Markdown INGEST re-interpretation, RESOLVED and deployed 2026-06-12 in
commit f3eaf1a - was cleared from this log on owner instruction to replace its contents with the
ISSUE-3 diagnosis. That fix is still in the code; the full ISSUE-2 write-up is recoverable from this
file's git history.)

---

## ISSUE-3 Resolution (implemented; pending live verification)

The fix has three parts, all bridge-internal, reusing the existing helper/server pipeline:

1. Anchor honesty (the actual ISSUE-3 fix). The escape hatches were the only paths that left the
   local file out of step with its recorded base:
   - `push_pages` set the base to the canonical post-write hash but never rewrote `page.md` to that
     canonical form (the batch-apply response did not even carry it). It now returns the canonical
     `content` (`AutoPageWriteResultOut`) and the helper settles the local file to it.
   - `accept_remote` wrote live Docmost content while anchoring to the (possibly stale) bridge head
     hash. It now observes first, so content + `current_revision_hash` + `current_version_id` come
     from one consistent snapshot.
2. Version-id carry (1b, light, the rarely-used safety net). A `base_version_id` is now carried
   through the write / reconcile / resolve / get_page schemas and `_meta.json` as an opaque local
   pointer; the server heals an absent base by resolving it from its own `page_versions` store
   (server owns the chain). The hash comparator is otherwise unchanged.
3. Automation built on the fixed pipeline:
   - A 30s in-helper auto-sync module (`helper/helper/auto_sync.py`, opt-in `DOCMOST_AUTO_SYNC`)
     that triggers the existing `sync_space` per discovered replica - no duplicated sync logic.
   - A standalone `/health` awareness subsystem: `auto_sync_conflicts` table (migration 004),
     `/v1/.../auto-conflicts` routes, and MCP `health` / `health_resolve` tools. The auto-sync posts
     the conflicts it parks; clearing is model-controlled only (the server never auto-clears).

Contract bumped 1 -> 2 (added `auto-conflict`, `health`, `version-id` capabilities).

---

## ISSUE-3: A remote-only page advance is misclassified as a `both_changed` conflict because reconcile is a hash-only three-way compare with no revision-chain / ancestry model

Severity: MEDIUM. It does NOT lose or corrupt data (sync never force-pushes, and a conflict only
surfaces - it writes nothing). But it forces a human merge decision for a change that, by design,
should pull cleanly, and the surfaced "conflict" is misleading: the local side is genuinely an older
point on the same lineage as the remote, not a true divergence. Recovering requires an out-of-band
`resolve_conflict` / `accept_remote`, which (see Trigger reconstruction) is itself the operation
that seeds the next occurrence.

Discovered: 2026-06-13, during a `sync_space` of the `hostnodexdocs` space
(`019dc725-9a37-7b91-b1a0-7f30a408efc0`) after the page owner moved content directly in the Docmost
UI (cut a section out of one page into a new top-level page).

### Symptom (observed, exact)

On `sync_space`:
- The brand-new top-level page ("Ongoing model hardening", slug `lFkEGXILdv`,
  page_id `019ec113-84f3-7c2d-951f-0236cfb7ac5d`) PULLED cleanly (`applied[].action = "pulled"`).
- The page the content was moved OUT of ("HostNodex Documentation",
  page_id `019dc725-c0fe-7cac-ab90-429b81871b05`, local `hostnodex-replica/UsXVMQ0UZE/page.md`) was
  returned as a `conflicts[]` entry with `reason = "both_changed"`.

The three hashes on that conflict were all distinct:

    base_revision_hash = 0aad6531...      (the local _meta.json anchor)
    local_version      = 565b32bb...      (sha256 of the current local page.md)
    remote_version      = 260a2dfb...      (the bridge head for the page)

Three distinct hashes is exactly the fall-through `return "conflict"` of the comparator (below).

### Root cause: reconcile classifies by content-hash equality against a single stored base, with no notion of revision lineage

1. The whole decision is one symmetric three-hash comparator -
   `_three_way(local, base, head)` at `app/reconcile/service.py:38-48`:

       if local == head:  return "synced"
       if base is None:   return "conflict"
       if base == head:   return "local_ahead"     # push
       if base == local:  return "remote_ahead"    # clean pull
       return "conflict"                            # all three distinct -> both_changed

   The same shape is mirrored for the live-Docmost path in `app/sync/service.py:631-661`
   (`local_changed = local != base`, `remote_changed = remote != base`; both -> conflict).
   Conflict is emitted at `app/reconcile/service.py:296-298`; the three hashes are assembled in
   `_conflict_item` at `:232-245` (`local_version = revision_hash(title, content)` of the local
   file; `remote_version = head.current_revision_hash` from the bridge DB).

2. There is NO revision chain to consult. The bridge's version state is three flat, independent
   hashes - never a lineage:
   - `page_versions` (`migrations/bridge/001_initial.sql:1-16`) is an append log keyed
     `UNIQUE(page_id, revision_hash)` with NO `parent_version_id` / `previous_revision_hash` /
     `version_number` column.
   - `page_heads.current_revision_hash` (`:20-35`) is the single "current remote" pointer.
   - `local_page_snapshots.base_revision_hash` (`migrations/bridge/002_add_local_page_snapshots.sql:1-11`)
     is the base/anchor.
   Every hash is the bridge's OWN sha256 over canonicalized title+content
   (`app/bridge/services/versioning.py:11-20`, single basis `app/bridge/services/canonical.py`).

3. Docmost's own versioning is ignored. The bridge does not read Docmost `pageHistory` or
   `page.version` at all; the only Docmost-native field consumed is `pages.updated_at`, and it is
   used ONLY as a "did it change" skip-gate for the observer
   (`app/query/docmost.py:38-53,146-160`; `app/bridge/services/observer.py:52-59`;
   checkpoint column `migrations/bridge/001_initial.sql:78-85`). So even though Docmost DID record a
   new revision when the UI edit happened, the bridge cannot ask "is the local content an ancestor
   of the new remote revision?" - it has thrown away the only data that could answer it and compares
   opaque content hashes instead.

### Expected workflow, and why no fast-forward happened (the crux)

Remote-side edits are a NORMAL, expected input - not an anomaly. The worker folds direct-UI edits
into the bridge head PRECISELY so the next reconcile PULLS them. When local has not moved since its
last sync, a remote advance is a fast-forward: local is updated in place to the new version and its
new contents, no conflict. That is what should have happened to "HostNodex Documentation" - the UI
edit was a forward step on the same page, and local was an earlier point on that same chain.

It did not fast-forward for one reason: the ONLY fast-forward trigger is the hash-equality check
`base == local` (`service.py:46` -> `remote_ahead` -> pull). That is a proxy for "is local still the
last-synced point?", NOT an ancestry test for "is local an earlier link on head's chain?". The
stored `base` had drifted (`0aad...` != local `565b...`), so the proxy was false. And because the
bridge keeps no parent links and ignores Docmost's own revision lineage (point 2-3 above), there is
NO ancestry fallback that could still recognize local as an ancestor of head and fast-forward to the
new contents. With the cheap proxy false and no real lineage check behind it, all three hashes are
distinct and it defaults to `conflict`.

A genuine "is `local` reachable from `head` on the version chain?" check would have fast-forwarded
despite the stale base. The hash-only comparator cannot - and it further counts non-edit drift (e.g.
markdown list re-rendering on the Docmost round-trip) as "divergence", which both widens the false
conflicts and is part of why `local != base` here was not a true content fork.

### Why the brand-new sibling page pulled cleanly (but this one did not)

A bridge page that is not present locally and not in the last-synced tree takes the unconditional
pull branch at `app/reconcile/service.py:151-166` - it never runs the three-way test, so it cannot
conflict. The tracked page, by contrast, runs `_three_way`, where the drifted base trips the
fall-through. The asymmetry is purely "new page vs already-tracked page", not anything about the
content.

### Trigger reconstruction (how `base` drifted to `0aad...` while `local` was `565b...`)

PROVEN from code + the live logs:
- The page was previously in conflict and was resolved OUT OF BAND with the low-level escape hatches
  `accept_remote` then `push_pages` (not the normal reconcile path). `accept_remote` re-anchors the
  local base to the bridge head at that instant (`helper/helper/sync.py:391-404` ->
  `replica.py:102-103`, head from `app/helper_api/routers.py:122-124`); `push_pages` re-anchors to
  its post-write head (`helper/helper/sync.py:86-92` -> `replica.py:49-50`; post-write head hash
  `app/bridge/services/write_pipeline.py:420-451`).
- The page was then edited DIRECTLY in the Docmost UI. The observer worker folded that edit, writing
  a new `page_versions` row and advancing `page_heads.current_revision_hash` to `260a2dfb...` with
  `source = "external_observer"` (`app/bridge/services/observer.py:123-150`,
  `app/observer/worker.py:45,52-57`). Confirmed in the worker log: the fold landed at 13:00-13:03
  UTC (`ext_updates`, page count 92 -> 93), and it remains `bridge_confirmed:0` pending resolution.
- The reconcile then ran (mcp log 13:04:30 UTC, `POST .../reconcile` 200) and saw
  base `0aad...` != local `565b...` != head `260a...` -> `both_changed`.

INFERRED (the most probable seed of base != local, not byte-proven this run): the out-of-band
resolution re-anchored `base` to a bridge-side hash that did not end up byte-equal to the local
`page.md`'s recomputed `revision_hash`. Two mechanisms can produce that gap, both consistent with
the code:
  (a) the escape hatches re-anchor `base` to the bridge head / server-returned hash, while the local
      file is separately rewritten (the prior resolution did an `accept_remote` -> local rewrite ->
      `push_pages`); if the locally written bytes differ at all from what the bridge canonicalized
      and stored, `base` (server hash) != `local` (recomputed file hash) immediately.
  (b) the write pipeline canonicalizes/escapes content on ingest (the ISSUE-2 underscore escaper in
      `app/write/`), so the stored canonical form can differ from the raw local bytes unless the
      helper rewrites the file to the canonical round-trip; if a given escape-hatch path updates the
      `_meta.json` base but does not overwrite `page.md` with the canonical form, `base` and `local`
      diverge by construction.
Either way the root defect is the same: with no ancestry, the system cannot self-heal a drifted
base, so the drift survives until it collides with the next remote advance and surfaces as a false
conflict.

### Design intent vs implemented reality

The DESIGN already specifies the correct behavior; the implementation under-delivers it:
- `docs/automated-helper-sync-plan.md` Section 3: "A conflict is only 'both changed since the
  recorded base'... Local content differs from the base AND remote differs from the same base."
  A remote-only advance with local unchanged-from-base is, by that definition, NOT a conflict.
- `docs/automated-helper-sync-architecture.md` Section 9 names two flows separately ("Local changes
  flow helper -> /v1/reconcile -> Docmost write -> bridge version. Remote changes flow Docmost ->
  worker -> bridge version -> next reconcile -> helper -> local files"); Section 8 says the worker
  "keeps the bridge truth fresh so reconcile classifications are correct".
- `plan.md` Section 2 / Section 12 make the load-bearing invariant explicit: the base anchor must be
  written back on BOTH sides after every successful sync, or "the next sync will misclassify the
  page."

Reality: the classifier is hash-only with no chain, so that invariant is the ONLY thing standing
between correct and incorrect, and there is no recovery path (no ancestry walk, no use of Docmost's
own revision id) when it is violated. The escape hatches and any canonicalization gap can violate it
silently. So the design's "remote advance -> clean pull" guarantee holds in the clean steady state
but is fragile and unrecoverable once `base` drifts.

### User's suspicions (preserved; NOT eliminated by the diagnosis - substantially CONFIRMED)

Stated suspicion: the helper and server surfaces are not built for "server-side changes" logic vs
"client-side changes only" logic separately, but instead push both through a single pipeline that
expects them to behave identically; we are not truly accounting for versioning (the helper should
recognize, from the locally stored version vs the server's version-chain, that the remote is simply
a newer link in the SAME chain and pull it), and a true conflict should require BOTH sides to have
diverged.

Verdict:
- CONFIRMED (core): there is a single symmetric comparator (`_three_way`,
  `app/reconcile/service.py:38-48`, mirrored at `app/sync/service.py:631-661`) and NO revision-chain
  / ancestry anywhere - no parent pointers in `page_versions`, and Docmost's own `pageHistory` /
  `page.version` are unused. The system therefore literally cannot determine "newer link in the same
  chain"; it only compares content-hash equality to one stored base. "Both sides diverged = conflict"
  is the intended rule, but it is implemented as "all three hashes distinct", which a drifted base
  satisfies even when the remote is a pure descendant.
- REFINEMENT (why PARTIAL, not a blanket confirm): the code DOES distinguish direction
  (`local_ahead` vs `remote_ahead`), and a remote-only advance DOES pull cleanly WHEN `base` is still
  equal to `local`. The false conflict is conditional on a drifted/absent base (`base is None` also
  forces a conflict, `service.py:42`), not a property of every remote change. So the suspicion is
  correct about the missing versioning/ancestry and the single-pipeline shape; it is not the case
  that every server-side edit conflicts.

The suspicion is therefore retained as the accurate structural diagnosis: the absence of a real
revision model (ancestry) is the root deficiency, and the single hash-only pipeline is its
mechanism.

### Runtime state at diagnosis time (read-only inspection, host 64.112.126.69)

- Containers `docmost-mcp`, `docmost-mcp-worker`, `docmost-mcp-bridge-db` all running, 0 restarts,
  bridge-db healthy; live Docmost up. No crashloop, no errors/tracebacks in any of them.
- The sync attempt's entire remote footprint was reads + one compute: `GET /helper/v1/spaces`
  (13:04:14), `GET /helper/v1/spaces/<id>` (13:04:27), `POST /v1/spaces/<id>/reconcile` -> 200
  (13:04:30). A 6h scan found NO push / update_page / create_page / resolve / PUT / PATCH / DELETE
  for the space. The conflict path wrote nothing to Docmost or the bridge DB; bridge-db log shows
  only routine time-based Postgres checkpoints.
- The worker is current (per-space fold cadence ~21s, no backlog) and has already processed the UI
  edit; it sits at `bridge_confirmed:0` for the page, which is the correct "external update observed,
  not yet helper-confirmed" state while the conflict is unresolved.
- SAFE to re-run `sync_space` - it will idempotently re-surface the same `both_changed` conflict and
  cannot lose either side (no force-push, no auto-delete). Clearing the conflict requires an explicit
  `resolve_conflict` (supply merged markdown) or `accept_remote` (take the remote, i.e. accept the
  intended UI move) - a plain re-run alone will keep returning it.

### Key references (file:line)

- Comparator / decision tree: `app/reconcile/service.py:38-48` (`_three_way`), `:63-76` (`_combine`),
  `:285-363` (tracked reconcile), `:296-298` (conflict emit), `:232-245` (three hashes),
  `:151-166` (clean pull-of-new-page branch, no three-way). Mirror: `app/sync/service.py:631-661`.
- No revision chain; flat hash schema: `migrations/bridge/001_initial.sql:1-16` (`page_versions`,
  `UNIQUE(page_id, revision_hash)`), `:20-35` (`page_heads.current_revision_hash`),
  `migrations/bridge/002_add_local_page_snapshots.sql:1-11` (`base_revision_hash`).
- Self-computed hash; Docmost version ids unused: `app/bridge/services/versioning.py:11-20`,
  `app/bridge/services/canonical.py`; `app/query/docmost.py:38-53,146-160`;
  `app/bridge/services/observer.py:52-59` (updated_at as skip-gate only).
- Worker folds UI edit -> advances head + version, never the base:
  `app/bridge/services/observer.py:123-150`, `app/bridge/repositories/page_heads.py:36-94`;
  observer never writes `app/bridge/repositories/snapshots.py`; loop `app/observer/worker.py:45,52-57`.
- Base anchor re-anchor points: push `helper/helper/sync.py:86-92` + `helper/helper/replica.py:49-50`;
  pull/synced `helper/helper/sync.py:282-294,361-362` + `replica.py:102-103`; accept_remote
  `helper/helper/sync.py:391-404`; resolve `helper/helper/sync.py:545-546`; post-write head
  `app/bridge/services/write_pipeline.py:420-451`. Head served from `app/helper_api/routers.py:122-124`.
- Plain sync does not re-observe already-tracked heads (head only moves on worker tick or
  `resync_space`): `app/reconcile/service.py:111-115`, `app/bridge/services/bootstrap.py:19-37`.
- Design intent: `docs/automated-helper-sync-plan.md` Sections 2, 3, 10, 12;
  `docs/automated-helper-sync-architecture.md` Sections 6, 8, 9, 12.
