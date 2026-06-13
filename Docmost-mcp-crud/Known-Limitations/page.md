The conversion gate (markdown to ProseMirror on the way in, ProseMirror to markdown on the way out)
is lossless and idempotent for the constructs the bridge owns: headings, bullet / ordered / task
lists with nesting, tables, callouts, code, inline marks, horizontal rules, and block / inline math
all round-trip structurally, and re-pushing a canonical read-back is a no-op. The items below are the
remaining edges. Two are owned by Docmost's own markdown parser and cannot be prevented by the egress
renderer; one is a deliberately deferred input normalization.

## Two-space ordered-list indent is not auto-renested (deferred)

Docmost ingests markdown with `marked` (breaks:true), which nests a child list only when the child
is indented to the parent marker's content width: a bullet marker (`- `) is two columns, but an
ordered marker (`1. `) is three, and `10.` is four. So an ordered sub-list indented only two spaces
falls outside its parent item and `marked` flattens it - the sub-items are folded into the parent as
line breaks plus literal `1.` / `2.` text instead of a nested list.

The egress renderer already emits the correct form: it indents each nested list to the parent marker
width (three spaces under `1. `, widening with the marker), so anything that has flowed through the
gate round-trips cleanly. The gap is purely on the INPUT side: markdown authored or pasted with a
two-space ordered indent is not auto-corrected on the write path.

This is intentional. Detecting and renesting a two-space ordered sub-list safely requires a real
CommonMark block parser - a line-level heuristic cannot tell a genuine under-indented sub-item from a
lazy paragraph continuation, a bullet child (which is correct at two spaces), an indented code block,
or already-flattened literal text - and that parser would duplicate the structural authority the
egress renderer already owns, risking drift between two sources of truth. A parser-based ingest
reflow was specified but deferred.

Docmost's own editor exports nested ordered lists at a two-space indent, so Docmost's own
export-then-reimport round-trip is itself lossy for nested ordered lists. A two-space ordered indent
is therefore a Docmost-origin signature, not random input - but the safe fix is still to re-indent.

Workaround: re-indent the ordered sub-list to the marker width (three spaces under `1. `) in the
local source, then sync. Change a two-space sub-list:

```
1. parent
  1. child
  2. child

```

to a marker-width sub-list:

```
1. parent
   1. child
   2. child

```

## Already-flattened stored pages cannot self-heal from markdown

If a page's stored ProseMirror is already flattened (it was ingested before the egress fix, or with a
two-space ordered indent), the nesting is gone on Docmost's side. The egress renderer can only render
what is stored, so a resync renders the flat form faithfully - it cannot reconstruct lost structure.
The intended structure survives only in an intact local source, so healing such a page means
re-pushing that source (after re-indenting any two-space ordered list as above), not pulling.

## Math delimiters are claimed by Docmost on ingest

Docmost's math extension grabs a literal double-dollar block or a bare single-dollar pair in prose on
ingest and turns it into a math node; the egress renderer cannot prevent this because Docmost owns the
parse. Write math you mean as math, and backtick or describe in prose any dollar amounts or literal
delimiters you do NOT want parsed (for example a price). Block and inline math that you DO intend
round-trip correctly.

## Inline code spans with edge whitespace

Docmost's ingest collapses whitespace at the boundary of an inline code span (markdown to HTML to
ProseMirror). A code span whose content ends with a space, immediately followed by a space and a
word, loses that outer space - the parser stores the following text without its leading space. For
example this input:

```
the `10. ` marker

```

is stored and read back as:

```
the `10. `marker

```

The result is stable and idempotent (re-pushing it is a no-op, so it does not churn or diverge), but
it is lossy. Do not rely on a space sitting directly next to a code span that carries its own edge
whitespace; follow such a span with punctuation, or drop the trailing space inside it.

## Node types with no verified markdown syntax

A few Docmost node types have no agreed markdown representation that round-trips - for example embeds
such as YouTube, mentions, emoji, and text color / highlight marks. They are out of scope for the
markdown gate and are left as documented limits rather than guessed at.

## See also

Data Models (the canonical rendering and revision hash), Developer Handbook (expectations and
gotchas), Architecture (where the renderer and write path live).