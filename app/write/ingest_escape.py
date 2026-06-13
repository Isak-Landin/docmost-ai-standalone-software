"""Make outgoing markdown safe for Docmost's `marked` ingest (the write half of the conversion gate).

Docmost parses page content sent with `format:"markdown"` in two stages: `marked` (CommonMark +
breaks:true + callout/math extensions) renders it to HTML, then tiptap's `DOMParser` builds the
ProseMirror tree against Docmost's schema. Two ingest hazards corrupt content silently, so this
module neutralises both on the way OUT, mirroring the egress renderer in `app/query/prosemirror.py`:

1. Flanking `_`/`__` outside code are read by `marked` as emphasis, so a code/path token such as
   `app/__init__.py` would be stored as bold `init` and read back as `app/**init**.py`. The egress
   renderer already emits emphasis only as `*`/`**` and escapes literal flanking `_`/`__`; this
   applies the SAME convention on the way in, so a literal `app/__init__.py` stays literal end to end.
2. Raw HTML tags. tiptap's `DOMParser` keeps only tags its schema has a parse rule for and SILENTLY
   DROPS the rest, merging their neighbours into a paragraph -- a block wrapper like `<article>` /
   `<div>` takes whole sections with it (the observed empty-`##`-heading data loss). So every HTML
   tag is escaped to literal text EXCEPT the handful Docmost parses back to a node/mark, which the
   egress renderer itself emits: <u>/<sup>/<sub>/<details>/<summary>.

Properties:
- Position-aware: never touches inline-code spans or fenced code blocks (their content is literal to
  `marked` already, so emphasis markers and `<tags>` there are intentional).
- Idempotent: an already-escaped `\\_` or `\\<` is never re-escaped (the `(?<!\\)` guard), so
  re-pushing the canonical read-back form is a no-op and the reconcile/revision-hash stays stable.
- Minimal: only flanking `_`/`__` and non-schema HTML tags are escaped. `*`/`**` emphasis, backticks,
  links and structural block markers are left untouched (escaping those would corrupt formatting).
"""

from __future__ import annotations

import re

# A flanking `_`/`__` run that `marked` would read as emphasis: at a non-word boundary, not
# intraword (so `snake_case` is left alone), and NOT already backslash-escaped (idempotency).
_FLANKING_UNDERSCORE = re.compile(
    r"(?<![0-9A-Za-z\\])(__|_)(\S(?:.*?\S)?|\S)\1(?![0-9A-Za-z])"
)

# A line that opens or closes a fenced code block: optional indent then a run of >= 3 ` or ~.
_FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})")

# HTML tags Docmost's schema parses back to a node/mark (the egress emits exactly these), so they
# pass through to be parsed; every other tag is escaped to literal text. An unmatched tag is
# silently dropped by tiptap's DOMParser and its neighbours merged into a paragraph (the
# section-drop data loss), so an unsupported raw tag like <article>/<div> must never reach `marked`
# unescaped. Only a COMPLETE tag/comment matches -- a bare `<` in prose ("a < b") is left alone.
_INGEST_HTML_ALLOWED = {"u", "sup", "sub", "details", "summary"}
_HTML_TAGISH = re.compile(r"(?<!\\)<(?:/?([A-Za-z][A-Za-z0-9-]*)(?:\s[^<>]*?)?/?>|!--)")


def _escape_underscore_runs(text: str) -> str:
    def _esc(m: re.Match) -> str:
        delim, inner = m.group(1), m.group(2)
        escaped_delim = "".join("\\" + ch for ch in delim)
        return escaped_delim + inner + escaped_delim

    return _FLANKING_UNDERSCORE.sub(_esc, text)


def _escape_html_tags(text: str) -> str:
    """Escape the leading `<` of any HTML tag/comment not in the schema allowlist, so `marked`
    keeps it as literal text instead of letting tiptap drop it (and its neighbours)."""
    def _esc(m: re.Match) -> str:
        name = (m.group(1) or "").lower()
        if name in _INGEST_HTML_ALLOWED:
            return m.group(0)  # supported tag: let Docmost parse it back to a node/mark
        return "\\" + m.group(0)

    return _HTML_TAGISH.sub(_esc, text)


def _escape_text_segment(text: str) -> str:
    """Escape both ingest hazards (flanking `_`/`__` and non-schema HTML tags) in non-code text."""
    return _escape_html_tags(_escape_underscore_runs(text))


def _escape_outside_inline_code(line: str) -> str:
    """Escape flanking `_`/`__` in a single line, skipping inline-code spans (`` `...` ``)."""
    out: list[str] = []
    i, n = 0, len(line)
    while i < n:
        if line[i] == "`":
            j = i
            while j < n and line[j] == "`":
                j += 1
            run = line[i:j]  # opening backtick run
            close = line.find(run, j)  # matching closing run of the same length
            if close != -1:
                out.append(line[i:close + len(run)])  # code span: verbatim
                i = close + len(run)
            else:
                out.append(_escape_text_segment(line[i:]))  # unmatched ` -> literal text
                i = n
        else:
            k = line.find("`", i)
            if k == -1:
                out.append(_escape_text_segment(line[i:]))
                i = n
            else:
                out.append(_escape_text_segment(line[i:k]))
                i = k
    return "".join(out)


def escape_markdown_for_ingest(md: str) -> str:
    """Escape the two ingest hazards outside code (inline spans + fenced blocks), idempotently, so
    Docmost stores them as authored: flanking `_`/`__` (else read as emphasis) and non-schema HTML
    tags (else dropped by tiptap, taking neighbours with them). Mirrors the egress renderer."""
    if not md or ("_" not in md and "<" not in md):
        return md
    out: list[str] = []
    in_fence = False
    fence_token = ""
    for line in md.split("\n"):
        m = _FENCE.match(line)
        if in_fence:
            out.append(line)  # inside a fence: verbatim
            if m and m.group(2)[0] == fence_token[0] and len(m.group(2)) >= len(fence_token):
                in_fence, fence_token = False, ""
            continue
        if m:
            in_fence, fence_token = True, m.group(2)
            out.append(line)  # the opening fence line itself: verbatim
            continue
        out.append(_escape_outside_inline_code(line))
    return "\n".join(out)
