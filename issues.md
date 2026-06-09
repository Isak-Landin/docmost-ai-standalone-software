# Known Issues

Status: ISSUE-1 FIXED IN CODE (renderer + a `resync` heal path); pending live deploy,
throwaway-space E2E, and a one-time `resync` of real spaces. See the RESOLUTION section at the
bottom of ISSUE-1 for what changed, the corrected recovery story, and the remaining ops steps.

This file is the dedicated issues log for docmost-mcp-server. (There is no
`usage.md` in this repo; nothing to migrate from.)

---

## ISSUE-1: ProseMirror -> Markdown round-trip corrupts nested lists, dashes, and other constructs

Status: FIXED IN CODE (egress renderer rewritten + `resync` heal path added). Real syncs stay
frozen until the fix is deployed and real spaces are healed via `resync_space` (see RESOLUTION).
The diagnosis below is preserved as reference.
Severity: HIGH (silent, whole-page, data-mangling).
Discovered: 2026-06-09, during a HostNodex docs sync (the "Workflows" page nested
bullet list collapsed onto fewer lines after a push).

### Operational warning (read first)

Until this is fixed, DO NOT run `sync_space` / `sync_page` / `sync_page_tree` on
any real page, and never pull/`accept_remote` a real page. The normal sync flow
round-trips the WHOLE page through Docmost's parser and a lossy custom Markdown
renderer, then OVERWRITES the entire local `page.md` with the reserialized form -
so sections you never edited get mangled too. A single sync of a page that
contains nested lists (or several other constructs below) silently rewrites it.

Safe to do meanwhile:
- Read-only inspection of source code.
- Unit-testing `prosemirror_to_markdown` directly with hand-built ProseMirror JSON
  (no Docmost, no network - the safest reproduction; see "How to reproduce").
- End-to-end probing ONLY inside a brand-new throwaway test space you create for
  this purpose; never an existing space/page.

### Symptoms (observed)

- Nested bullet lists are flattened: a parent bullet and its first nested child
  collapse onto one physical line (`- Parent - ChildA`), while later nested
  children remain as separate, re-indented bullets. The author's intended 2-space
  nesting is not preserved.
- `-`, `--`, `---` are treated INCONSISTENTLY: sometimes as list markers / nesting,
  sometimes as a horizontal rule, sometimes as raw text - depending on surrounding
  context the author cannot see.
- A `-` intended as a literal text symbol (e.g. an inline " - " separator, or a
  standalone `---`) can be re-interpreted as structure on the next round-trip.
- The corruption appears in parts of the page that were never edited.

### Root cause

There are TWO converters in the round-trip, and only one of them lives in this repo:

1. Markdown -> ProseMirror (INGEST) is NOT implemented here. The write layer ships
   the raw local Markdown string to Docmost's REST API with `format: "markdown"`
   (`app/write/docmost.py:110-112` for create, `:143-146` for update). Docmost's
   own server-side markdown parser (CommonMark/markdown-it + Tiptap) decides what
   `-`, `---`, nested indentation, and inline dashes mean. This repo does not
   configure or constrain that parser, and there is no Markdown parser dependency
   anywhere in the repo (`requirements.txt` has none).

2. ProseMirror -> Markdown (EGRESS) is a bespoke, hand-rolled, LOSSY renderer:
   `prosemirror_to_markdown` in `app/query/prosemirror.py:12`. This is the single
   point where structure is lost.

The round-trip that overwrites your file:

- Normal sync sends local Markdown to Docmost (`app/bridge/services/write_pipeline.py:118`
  `update_page_via_bridge` -> `:206` `update_remote_page` -> `app/write/docmost.py:118`).
- It then reads the page BACK from Docmost and reserializes the WHOLE document via
  the lossy renderer to form the "canonical" content
  (`app/bridge/services/canonical.py:23-42` -> `app/query/docmost.py:163` `get_page`
  -> `prosemirror_to_markdown` at `app/query/docmost.py:166,180`).
- That reserialized Markdown becomes the canonical head content and the revision
  hash basis, and is handed back as `applied[].content`
  (`app/reconcile/service.py:365-367,380`).
- The helper writes it OVER the local file:
  `helper/helper/sync.py:284-285` (`write_page(local_path, content)`).

So even a one-line edit causes Docmost to re-emit ProseMirror for the entire page,
this renderer reserializes the entire document, and the whole local `page.md` is
replaced. There is no section-level / hunk-level apply on the write path.

### The exact mechanism (why nested lists flatten)

All line numbers in `app/query/prosemirror.py`.

A Docmost nested bullet is stored as:
`bulletList > listItem > [ paragraph, bulletList > listItem > paragraph, ... ]`.

Rendering it:

- `listItem` is rendered by `_render_list_item` (197-202):
  ```python
  def _render_list_item(children: list[dict]) -> str:
      parts = []
      for child in children:
          rendered = _render_node(child).rstrip("\n")
          parts.append(rendered)
      return " ".join(parts)          # <-- joins blocks with a SPACE
  ```
  For a list item whose children are `[paragraph, nestedBulletList]`, this renders
  the paragraph ("ParentText") and the nested list ("- ChildA\n- ChildB"), strips
  trailing newlines, and joins them with a single space:
  `"ParentText - ChildA\n- ChildB"`. The newline BEFORE "- ChildB" survives (it is
  interior), but the newline that should separate the parent from "- ChildA" is
  gone.

- Back in `_render_list` (177-187), that item text is split on `\n` and only
  CONTINUATION lines (index >= 1) get the 2-space indent:
  ```
  - ParentText - ChildA
    - ChildB
  ```
  The first nested child is glued to the parent line; the rest are indented. Because
  `_render_list_item` already collapsed the parent/first-child boundary, no amount
  of indentation logic in `_render_list` can recover the nesting - the renderer
  never threads an indentation depth through `_render_node`.

This is exactly the observed "parent + first child merged onto one line, later
children left as separate bullets" mangling.

### Why the `-` / `--` / `---` inconsistency

It is a two-parser split with NO escaping and NO round-trip-stability guarantee:

- INGEST meaning is decided by Docmost's CommonMark parser, by CONTEXT the author
  cannot see: a leading `- ` starts a bullet; a line of exactly `---` is a thematic
  break OR (directly under a paragraph line) a setext H2 underline; `--`/`---`
  inside running text is literal; an inline " - " is literal. Same characters,
  different node types, depending on blank lines / preceding paragraph / indentation.
- EGRESS re-emits each node type WITHOUT escaping: `horizontalRule` is always
  `"---\n\n"` (73-74); `text` nodes are emitted raw with no Markdown escaping
  (35-36, via `_apply_marks`); a paragraph that is literally `---` comes back as
  `---`, which Docmost will RE-parse as a thematic break on the next push; a setext
  heading was already absorbed into a `heading` node on ingest and returns as ATX
  `## ...` (38-41), silently rewriting the author's heading style.

Net: the meaning of `-`/`--`/`---` is not stable across a round-trip. A literal dash
can become structure; a structural break can collapse into adjacent text; a setext
heading silently changes style. The architecture assumes `prosemirror_to_markdown`
is a deterministic, round-trip-safe rendering (`app/bridge/services/canonical.py`
docstring) - that assumption is false for lists, dashes, and the constructs below.

### Blast radius

Whole-page, including untouched sections. `get_page` / the sync read-back reserialize
the ENTIRE ProseMirror doc (`app/query/docmost.py:180` over all children), the
reconcile write-back replaces the whole file (`app/reconcile/service.py:367` ->
`helper/helper/sync.py:285`), and the same reserializer feeds the revision hash
(`app/bridge/services/versioning.py:16`) and the background observer
(`app/bridge/services/observer.py:46-47`). So once any page is touched - or edited
in the Docmost UI and observed - its stored/served content is the reflowed form.

### Fix locus and direction (for the next session)

Primary locus: `app/query/prosemirror.py`.

1. Nested-list flattening (the headline symptom): `_render_list_item` (197-202) must
   NOT `" ".join` block children. It needs to emit each block child on its own
   line(s) and thread an indentation depth so nested `bulletList`/`orderedList`
   children are indented under their parent item instead of glued to it. Likely a
   depth/indent parameter through `_render_node` / `_render_list` / `_render_list_item`,
   with the parent paragraph on the marker line and nested lists as indented blocks.
2. Round-trip stability for dashes and other markers: the renderer needs an escaping
   / safe-emission policy so emitted Markdown re-parses to the same ProseMirror -
   e.g. escape a leading `-`/`#`/`>`/`|`, a standalone `---`, and backticks; consider
   preserving hard breaks as `"  \n"`. Because the INGEST parser is owned by Docmost
   and cannot be constrained from this repo, round-trip safety must be enforced
   entirely on the egress side.
3. Strongly recommended: add a round-trip property test (Markdown -> ProseMirror via
   a fixture -> `prosemirror_to_markdown` -> assert structure-preserving), since this
   renderer is the canonical-hash basis and any loss silently corrupts every synced
   page.

Do NOT "fix" this by normalizing the user's input or by changing list semantics; the
correct behavior is faithful, structure-preserving, round-trip-stable rendering.

### How to reproduce (safely)

Safest (no Docmost, no network) - unit-test the renderer directly:
- Build a ProseMirror JSON fixture for a 2-level nested bullet list
  (`bulletList > listItem > [paragraph, bulletList > listItem > paragraph]`) and call
  `prosemirror_to_markdown(doc)`; observe the parent/first-child line collapse.
- Add fixtures for: an `orderedList` nested in a `listItem`; a `taskList`
  (`_render_task_list` at 190-194 drops the `[ ]`/`[x]` and routes through the same
  space-join); a `table` whose cell text contains a literal `|`
  (`_render_table_row` 218-224 does not escape it); a `horizontalRule`; a paragraph
  whose text is literally `---`.

End-to-end (ONLY in a NEW throwaway test space you create for this; never an existing
space/page): push a page containing nested lists, inline " - ", standalone `---`, a
table with `|` in a cell, and a task list; let it sync; diff the overwritten local
`page.md` against what you pushed. Tear the test space down afterward.

### Adjacent at-risk constructs (same two faults)

The faults are (i) `_render_list_item` newline-strip + space-join, and (ii) no
escaping / no round-trip awareness on egress vs. an uncontrolled ingest parser.

| Construct | File:line | Failure |
|---|---|---|
| Nested ordered lists | prosemirror.py:51-52,197-202 | Flattened/space-joined like bullets; nesting + numbering lost |
| Mixed ordered/unordered nesting | prosemirror.py:177-202 | Child sublist collapses onto parent line |
| Task lists | prosemirror.py:57-63,190-194 | Checkbox IS preserved (`- [x] ` / `- [ ] ` is correct GFM); the only real fault is nested task items flattening via the shared space-join |
| Blockquotes with nested content | prosemirror.py:43-46 | Nested list/quote inside a quote inherits flattening; lazy-continuation re-parse not guarded |
| Callouts | prosemirror.py:87-96 | Emitted as `> emoji ...`; re-ingested as a plain blockquote (type loss) |
| Fenced code blocks | prosemirror.py:65-68 | No fence-collision handling; a ``` inside the body breaks the fence |
| Inline code | prosemirror.py:162-163 | Single-backtick wrap, no backtick escalation; a backtick in content corrupts the span |
| Tables | prosemirror.py:205-224 | Literal `|` in cells not escaped; multi-line cells collapsed; alignment markers lost |
| Hard line breaks | prosemirror.py:70-71 | Emitted as bare `\n` -> re-ingested as a soft break (space); explicit break lost each round-trip |
| Setext headings | prosemirror.py:38-41 (+ ingest) | Author's setext style rewritten to ATX `##` on round-trip |
| Horizontal rules | prosemirror.py:73-74 | Always re-emitted as `---` regardless of original `***`/`___`; a literal `---` paragraph becomes a rule |
| Backslash escapes | prosemirror.py:35-36 | Renderer never emits escapes; literal-intent `\-`,`\*`,`\|`,`` \` `` cannot be reproduced |

### Key references

- Egress renderer (root cause): `app/query/prosemirror.py:12` (`prosemirror_to_markdown`),
  `:197-202` (`_render_list_item`, the flattening), `:177-187` (`_render_list`),
  `:73-74` (`horizontalRule`), `:35-36` (raw `text`), `:70-71` (`hardBreak`),
  `:218-224` (table rows).
- Ingest delegated to Docmost: `app/write/docmost.py:110-112,143-146`.
- Whole-page reserialize on read-back: `app/query/docmost.py:163-180`,
  `app/bridge/services/canonical.py:23-42`.
- Write-back overwrites local file: `app/reconcile/service.py:365-367,380`,
  `helper/helper/sync.py:284-285`.
- Hash basis + observer use the same renderer: `app/bridge/services/versioning.py:16`,
  `app/bridge/services/observer.py:46-47`.

### RESOLUTION (fixed in code)

Docmost's ingest grammar was pinned at v0.71.1 (`packages/editor-ext/src/lib/markdown/`):
markdown is parsed by `marked` (`marked.options({ breaks: true })`) plus a callout
(`:::type ... :::`) and math extensions, and Docmost ships its OWN `turndown`-based
ProseMirror->markdown serializer (`htmlToMarkdown`) - the proven inverse of its importer. The fix
makes `app/query/prosemirror.py` match turndown's conventions so emitted markdown re-imports to
the same tree.

What changed in the egress renderer (`app/query/prosemirror.py`):
- Nested lists/tasks no longer space-join their block children. The item's lead paragraph stays
  on the marker line; nested lists render as their own blocks indented a uniform 2 spaces per
  level (matching turndown's `\n  `). This fixes the headline flattening.
- Position-aware escaping (never a blanket per-char blacklist): a leading `#`/`-`/`+`/`*`/`>`/
  ordered marker / standalone `---`/`***`/`___` / fence / `:::` is escaped only at a block-start
  position; `|` is escaped only inside table cells; emphasis `*`/`_` only when they flank into a
  mark (intraword `_` left alone); links only at a `[..](`/`[..][` opener. Ordinary prose stays
  clean.
- Inline code and code fences use backtick-run escalation (no backslashes).
- Callouts now emit `:::<type>` (the node attr is `type` in {info,success,warning,danger}); the
  old `> emoji` form was the bug, not irreducible loss.
- Two earlier assumptions were wrong and are NOT changed: `breaks: true` means a single `\n`
  re-imports as a hardBreak, so `hardBreak` -> `\n` is correct (NOT "lost"); and the task-list
  checkbox was never dropped (see the table row above).
- A round-trip/structural test suite was added under `tests/` (offline; pytest dev dep in
  `requirements-dev.txt`).

Corrected recovery story (the original handoff was wrong here):
- The observer does NOT auto-heal after a renderer-only deploy. `observe_space`
  (`app/bridge/services/observer.py`) skips any page whose remote `updated_at` did not advance,
  and a renderer change does not touch Docmost's stored content - so heads keep the OLD render and
  reconcile classifies untouched pages as `synced`. Nothing re-renders them.
- Worse, every previously-synced local `page.md` currently holds the OLD flattened render. A plain
  edit+sync on such a page would PUSH that flattened markdown (push happens before read-back),
  re-ingesting it into a wrong tree and corrupting the stored ProseMirror. The egress fix alone
  cannot prevent this.
- Remedy added: a `resync` path. `observe_space(..., force_rerender=True)` bypasses only the
  updated-at gate and re-anchors every head from Docmost's current content through the corrected
  renderer; the new helper tool `resync_space` then runs the SAME two-way reconcile. A page whose
  only change is the corrected render heals as a pull (no content surfaced); a page with un-pushed
  local edits surfaces as a conflict. It never force-pushes, so it cannot corrupt either origin.
  New/changed: `observer.py` (flag + `reanchored_count`), `app/schemas/auto_mcp.py` +
  `app/auto_mcp/routers.py` (expose flag/count), `helper/helper/client.py`,
  `helper/helper/sync.py` (`resync_space`), `helper/server.py` (`resync_space` MCP tool).

Remaining ops (not yet done):
1. No-cache rebuild of the bridge image; restart `docmost-mcp` AND `docmost-mcp-worker`.
2. Validate in a brand-new throwaway test space (nested lists, inline `-`, standalone `---`, a
   table with `|`, a task list, a code fence with internal backticks); diff the round-trip; tear
   down.
3. `resync_space(space_id)` on each real space; resolve any surfaced conflicts.
4. Manually re-author pages whose stored ProseMirror was already corrupted by the old renderer
   (start with "Workflows") - the renderer cannot reconstruct nesting Docmost already lost.
