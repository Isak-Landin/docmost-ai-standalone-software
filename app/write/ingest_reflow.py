"""Block-structure countermalform for Docmost's `marked` ingest (the block half of the conversion gate).

Docmost converts page content sent with ``format:"markdown"`` in two server-side stages (verified
against ``docmost/docmost:latest``, ``marked@17.0.5``, in core/page/services/page.service.js
``parseProsemirrorContent``):

    markdown --markdownToHtml (marked, breaks:true)--> HTML --htmlToJson (happy-dom + tiptap
    DOMParser)--> ProseMirror JSON --> DB

This module neutralises the two block-level corruptions that happen in those stages, BEFORE the
inline escaper (``ingest_escape.py``) runs:

1. Ordered-list flatten (marked tokenizer, stage A). `marked` follows CommonMark: a child list
   nests only when its indent reaches the PARENT MARKER'S CONTENT COLUMN -- two columns under a
   `- ` bullet/task item, three under `1. `, four under `10. `, widening with the marker. A nested
   list indented only two spaces under an ordered parent (the shape Docmost's OWN turndown export
   emits, and a common hand-authored / pasted shape) falls short of the parent content column, so
   `marked` FLATTENS it: the sub-items collapse into the parent as <br> + literal "1."/"2." text
   instead of a nested list. The egress renderer (app/query/prosemirror.py ``_indent_continuation``)
   already emits the correct form -- ``indent = " " * len(marker)`` -- so anything that has flowed
   through the gate round-trips cleanly; ``reflow_ordered_lists_for_ingest`` applies that SAME
   marker-width invariant on the way IN, re-indenting an under-indented sub-list to the parent's
   content column so it nests instead of flattening.

2. Front-matter strip (markdownToHtml, stage A). ``markdownToHtml`` strips a leading
   ``---...---`` block as YAML front matter (``/^\\s*---[\\s\\S]*?---\\s*/``) BEFORE marked runs,
   so a body that opens with a `---` thematic break and contains a later `---` would lose
   everything between. ``guard_frontmatter_strip`` rewrites only that leading dash thematic break
   to `***` (an equivalent break marked does not treat as front matter).

Design -- deliberately conservative, never make content worse:
- Only PURE list regions are reflowed: a maximal run of consecutive list-marker lines (no blank
  lines, no paragraph/code continuation, no thematic breaks). In such a region every line is a
  marker, so re-indenting marker lines is fully correct -- there is no continuation content to
  misalign. A list whose items carry paragraphs, code blocks, or blank-line looseness is left
  untouched (the documented manual re-indent workaround still applies). A general CommonMark-grade
  reflow of arbitrary nested content is NOT attempted on purpose: under-indented input is genuinely
  ambiguous to a line scanner, and a wrong guess would corrupt, so we act only where intent is
  unambiguous.
- The intended tree is read from ORIGINAL indentation (deeper original indent = deeper level);
  each child is then re-emitted at its parent's marker-width content column. Only under-indented
  (and over-indented) children move; an already marker-width child is byte-identical.
- No-op on canonical egress output (already marker-width) and idempotent: a second pass finds
  nothing to move, so the revision-hash fixed point is preserved.
- Skips fenced code blocks; a tab-led line is never recognised as a marker, so it is left as-is.
"""

from __future__ import annotations

import re

# A list-item marker at line start: indent, marker (bullet char or ordered number+delim), the run
# of spaces before content, then the rest. Content column = len(indent)+len(marker)+len(spaces).
_MARKER = re.compile(r"^( *)([-*+]|\d{1,9}[.)])( {1,4})(.*)$")

# A fenced code block opener/closer: optional indent then >= 3 backticks or tildes.
_FENCE = re.compile(r"^( *)(`{3,}|~{3,})")

# A thematic break (---, ***, ___, optionally space-separated): a rule, NOT a list item.
_THEMATIC_BREAK = re.compile(r"^ *([-*_])( *\1){2,} *$")

# Docmost's markdownToHtml front-matter strip, replicated so the guard only acts when it would fire.
_FRONTMATTER = re.compile(r"^\s*---[\s\S]*?---\s*")
# A clean leading dash thematic break (the only shape we rewrite for the front-matter guard).
_LEADING_DASH_RULE = re.compile(r"^(\s*)(-{3,})( *)(\n|$)")


def _marker_info(line: str):
    """Return ``(marker_col, marker_width)`` for a clean list-marker line, else ``None``.

    ``marker_col`` is the indent (leading spaces); ``marker_width`` is the marker plus its
    following spaces, so the content column is ``marker_col + marker_width``. Thematic breaks
    (``- - -`` etc.) are not markers.
    """
    if _THEMATIC_BREAK.match(line):
        return None
    m = _MARKER.match(line)
    if not m:
        return None
    indent, marker, spaces, _rest = m.groups()
    return len(indent), len(marker) + len(spaces)


def _reflow_region(region: list[tuple[str, tuple[int, int]]]) -> list[str]:
    """Re-indent one pure marker region to the marker-width invariant.

    The intended tree is read from ORIGINAL marker columns; each child is re-emitted at its
    parent's content column (``parent_new_col + parent_marker_width``). Frames carry both the
    original and new columns so parent lookup stays in the original coordinate space while the
    emitted indent uses the corrected one.
    """
    out: list[str] = []
    stack: list[tuple[int, int, int]] = []  # (orig_marker_col, new_marker_col, new_content_col)
    for line, (orig_mc, marker_width) in region:
        while stack and stack[-1][0] >= orig_mc:
            stack.pop()
        if stack:
            _parent_orig, _parent_new, parent_cc = stack[-1]
            new_mc = parent_cc  # align/promote every child to its parent's content column
        else:
            new_mc = orig_mc  # top-level item: keep where it is
        out.append(" " * new_mc + line[orig_mc:])
        stack.append((orig_mc, new_mc, new_mc + marker_width))
    return out


def reflow_ordered_lists_for_ingest(md: str) -> str:
    """Re-indent under-indented sub-lists to the parent marker width so `marked` nests them.

    Operates only on pure marker regions (see module docstring); idempotent and a no-op on the
    canonical egress form. Fenced code blocks are passed through verbatim.
    """
    if not md or "\n" not in md:
        return md
    lines = md.split("\n")
    out: list[str] = []
    i, n = 0, len(lines)
    in_fence = False
    fence_token = ""
    while i < n:
        line = lines[i]
        fm = _FENCE.match(line)
        if in_fence:
            out.append(line)
            if fm and fm.group(2)[0] == fence_token[0] and len(fm.group(2)) >= len(fence_token):
                in_fence, fence_token = False, ""
            i += 1
            continue
        if fm:
            in_fence, fence_token = True, fm.group(2)
            out.append(line)
            i += 1
            continue
        if _marker_info(line) is None:
            out.append(line)
            i += 1
            continue
        # Start of a pure marker region: gather the maximal run of consecutive clean marker lines.
        region: list[tuple[str, tuple[int, int]]] = []
        j = i
        while j < n and not _FENCE.match(lines[j]):
            info = _marker_info(lines[j])
            if info is None:
                break
            region.append((lines[j], info))
            j += 1
        out.extend(_reflow_region(region))
        i = j
    return "\n".join(out)


def guard_frontmatter_strip(md: str) -> str:
    """Rewrite a leading dash thematic break to `***` so Docmost does not eat it as front matter.

    Only fires when ``markdownToHtml`` would actually strip (a leading ``---`` plus a later
    ``---``) AND the leading line is a genuine dash thematic break -- so prose or tables that merely
    start with ``---`` are left alone. Idempotent (the rewritten form starts with ``***``).
    """
    if not md or not _FRONTMATTER.match(md):
        return md
    m = _LEADING_DASH_RULE.match(md)
    if not m:
        return md
    return md[: m.start(2)] + "***" + md[m.end(2):]
