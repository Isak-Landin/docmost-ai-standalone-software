The conversion gate (markdown to ProseMirror on the way in, ProseMirror to markdown on the way out)
is lossless and idempotent for the constructs the bridge owns: headings, bullet / ordered / task
lists with nesting, tables, callouts, code, inline marks, horizontal rules, and block / inline math
all round-trip structurally, and re-pushing a canonical read-back is a no-op. The items below are the
remaining edges, all owned by Docmost's own markdown parser and not preventable by the egress
renderer. (The former two-space ordered-indent INPUT case and the leading front-matter strip are now
handled on the write path - see Conversion Gate.)

## Already-flattened stored pages cannot self-heal from markdown

The write path now re-indents an under-indented sub-list to the parent marker width before sending
(see Conversion Gate), so a page with an INTACT local source heals automatically on the next push:
its nesting is restored remotely.

The residual is a page whose nesting was already lost in DOCMOST STORAGE (it was ingested before the
gate fixes, or edited flat directly in the Docmost UI) AND has no intact local source. There the
stored ProseMirror is already flat, and the egress renderer can only render what is stored, so a
resync renders the flat form faithfully - it cannot reconstruct structure that is gone. Healing such
a page means re-creating the intended nesting in a local source and pushing it, not pulling.

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