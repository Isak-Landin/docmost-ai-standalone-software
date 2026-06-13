The conversion gate is the two-way boundary between the bridge's markdown and Docmost's stored
ProseMirror. Its two halves must stay exact inverses, because a page's revision hash is taken from a
Docmost read-back: if a write is not faithfully reproduced on read-back, the page reads as "changed"
on every later sync.

- Egress (Docmost ProseMirror to markdown): `app/query/prosemirror.py` (`prosemirror_to_markdown`).
  Deterministic, structure-preserving, with position-aware escaping.
- Ingest (markdown to Docmost): `app/write/docmost.py` POSTs page content with `format:"markdown"`;
  the last transform before the POST is `normalize_markdown_for_ingest` (`app/write/ingest.py`),
  which composes the block-structure countermalforms (`app/write/ingest_reflow.py`) and then the
  inline escaper (`app/write/ingest_escape.py`).

The gate is the faithful inverse of Docmost's OWN markdown handling, so the findings below are
properties of the Docmost version the bridge currently targets. They hold as long as that dependency
is unchanged; re-trace them on a Docmost upgrade.

## Docmost's ingest pipeline (version-pinned trace)

Verified against the running `docmost/docmost:latest` container (`marked@17.0.5`, `happy-dom`,
`@tiptap` starter-kit plus `@docmost/editor-ext`). When the bridge sends content with
`format:"markdown"`, Docmost converts it server-side in two stages before storing ProseMirror JSON:

```
POST /api/pages/{create,update}   format:"markdown"
  core/page/services/page.service.js   parseProsemirrorContent(content, "markdown")
    (A) markdownToHtml(content)    packages/editor-ext/dist/lib/markdown/utils/marked.utils.js
          marked.options({ breaks: true }).parse(...)
          + extensions: callout.marked, math-block.marked, math-inline.marked
          + custom list / listitem renderer
          + leading YAML front-matter strip:   /^\s*---[\s\S]*?---\s*/
    (B) htmlToJson(html)           collaboration/collaboration.util.js
          -> common/helpers/prosemirror/html/generateJSON.js
             new (happy-dom) Window().DOMParser  ->  ProseMirror DOMParser.fromSchema(schema).parse(body)
          -> addUniqueIdsToDoc
    jsonToNode(...) validates against the schema (unknown node types are stripped)
  -> stored in Docmost PostgreSQL

```

Stage A (marked) decides block structure and inline tokens from the markdown TEXT. Stage B
(happy-dom plus tiptap) builds the ProseMirror tree from that HTML and applies HTML whitespace
collapsing. Each corruption below happens in exactly one stage.

## Corruptions and how the gate handles each

| Corruption | Stage / cause | Disposition |
| --- | --- | --- |
| Flanking `_` / `__` read as emphasis | A, marked inline | Countermalformed: `ingest_escape.py` escapes them outside code |
| Non-schema HTML tag dropped (with its neighbours) | B, tiptap schema parse | Countermalformed: `ingest_escape.py` escapes all but the 5 schema tags |
| Sub-list flattened (nesting collapses) | A, marked list tokenizer | Countermalformed: `ingest_reflow.py` re-indents to marker width |
| Leading `---...---` eaten as front matter | A, markdownToHtml regex | Countermalformed: `ingest_reflow.py` guard rewrites the leading rule |
| `$...$` or `$$` grabbed as math | A, math extensions | Docmost-owned limit (see Known Limitations) |
| Inline-code edge whitespace collapsed | B, happy-dom whitespace | Docmost-owned limit (see Known Limitations) |

### Sub-list flatten (handled)

`marked` follows CommonMark: a child list nests only when its indent reaches the PARENT MARKER's
content column - two columns under a `-` bullet or task item, three under `1.`, four under `10.`,
widening with the marker. A nested list indented only two spaces under an ordered parent (the shape
Docmost's own turndown export emits, and a common hand-authored or pasted shape) falls short of the
content column, so the nesting collapses - the sub-items are lifted to the parent's level. Proven
against the live container, this input:

```
1. a
  1. b
  2. c

```

is stored flat (`<ol><li>a</li><li>b</li><li>c</li></ol>` - b and c become siblings of a), while the
reflowed form:

```
1. a
   1. b
   2. c

```

stores nested (`<ol><li>a<ol><li>b</li><li>c</li></ol></li></ol>`). The egress renderer already emits
the marker-width form (`indent = " " * len(marker)`), so the reflow is the SAME invariant applied on
the way IN. It is deliberately conservative: it only touches pure marker regions (a run of
consecutive marker lines), only moves under-indented (and over-indented) children, is a no-op on the
canonical egress form, and is idempotent. A list whose items carry paragraphs, code, or blank-line
looseness is left untouched (re-indent it by hand, then sync).

### Front-matter strip (handled)

`markdownToHtml` removes a leading `---...---` block as YAML front matter before marked runs, so a
body that opens with a `---` thematic break and has a later `---` would lose everything between. The
guard rewrites only that leading dash rule to `***` (an equivalent thematic break marked does not
treat as front matter), and only when the strip would actually fire.

## The shared invariant

Nested-list indent equals the parent marker's content width on BOTH halves: the egress emits it
(`indent = " " * len(marker)`) and the ingest reflow restores it. That single rule is why a nested
list round-trips - it is both the column `marked` requires to nest and the column the renderer
produces.

## Idempotence and the fixed point

Every write-path normalizer (reflow, front-matter guard, inline escaper) is a no-op on the canonical
egress form. So the round-trip is a STABLE FIXED POINT: send, Docmost stores, the read-back is the
canonical form, the local file settles to it, and the next push is a no-op - the same bytes store the
same tree, and re-pushing a read-back creates no new version. The only fatal class is a
NON-idempotent conversion (every push stores something new, so the page churns and reads as
perpetually diverged). It is guarded by the offline round-trip test corpus and a deploy-time live
idempotence check, NOT by a runtime input-vs-read-back diff - the canonical form always differs from
the typed bytes, so such a diff cannot tell legitimate canonicalization from loss.

## Version dependency

Everything above is a property of the Docmost version the bridge targets now. The file paths, the
`marked` version, the math regexes, and the whitespace behavior are pinned to that image. On a
Docmost upgrade, re-run this trace (the entry points may move) and re-verify the round-trip corpus
before trusting the gate.

## See also

Architecture (module map and request flows), Known Limitations (the Docmost-owned residuals), Data
Models (canonical rendering and the revision hash), Developer Handbook (expectations and gotchas).