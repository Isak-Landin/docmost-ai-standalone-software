"""Convert a Docmost ProseMirror JSON document to Markdown.

This is the EGRESS renderer. Docmost ingests page markdown with `marked`
(`marked.options({ breaks: true })`) plus its callout/math extensions, then turns the
resulting HTML into Tiptap/ProseMirror JSON. For a sync to round-trip, the markdown emitted
here must re-import to the SAME ProseMirror tree. The safest way to guarantee that is to match
the conventions of Docmost's own `turndown` serializer (the proven inverse of its `marked`
importer):

- ATX headings, `-` bullets, `N.` ordered lists, fenced code, `---` thematic rules.
- Nested-list indent tracks the parent MARKER WIDTH (2 for `- `/task items, >=3 for `N. `
  ordered), because `marked` only nests a child whose indent reaches the parent's content
  column; a flat 2-space indent silently flattens ordered nesting on re-ingest.
- `- [x] ` / `- [ ] ` task items; `:::<type>` callouts; `$...$` / `$$...$$` math.
- GFM tables / strikethrough.

`marked` with `breaks: true` turns a single newline inside a paragraph into a hard break, so a
hardBreak is emitted as a bare `\n` and block separation always uses a blank line (`\n\n`).

Escaping is POSITION-AWARE: a markdown token is escaped only where the ingest grammar would
parse it as structure at that position (a `-` only at line start, `|` only inside a table cell,
`*`/`_` only when they flank into an emphasis run, code via backtick-run escalation). Ordinary
prose keeps its punctuation un-escaped so the local replica markdown stays clean.

A literal HTML-ish tag in text (`<article>`, `<a ...>`) is escaped too: tiptap's DOMParser drops
any tag outside Docmost's schema and merges its neighbours into a paragraph, so an unescaped tag
silently destroys surrounding content on re-ingest. The renderer's own intentional tag wrappers
(`<u>`/`<sup>`/`<sub>`/`<details>`) are added AFTER text escaping, so they are not affected.
"""

from __future__ import annotations

import re
from typing import Any


def prosemirror_to_markdown(doc: dict[str, Any]) -> str:
    """Convert a ProseMirror JSON doc to a Markdown string."""
    if not isinstance(doc, dict):
        return str(doc)
    return _render_node(doc).strip()


# ---------------------------------------------------------------------------
# Internal renderer
# ---------------------------------------------------------------------------

def _render_node(node: dict[str, Any]) -> str:
    node_type = node.get("type", "")
    children = node.get("content", [])
    attrs = node.get("attrs") or {}

    if node_type == "doc":
        return _join_blocks(children)

    if node_type == "paragraph":
        inner = _render_inline(children)
        if not inner.strip():
            return "\n"
        # Each physical line is a potential block-start position for the ingest parser.
        lines = [_escape_block_start(line) for line in inner.split("\n")]
        return "\n".join(lines) + "\n\n"

    if node_type == "text":
        return _apply_marks(node.get("text", ""), node.get("marks", []))

    if node_type == "heading":
        level = int(attrs.get("level", 1))
        prefix = "#" * min(max(level, 1), 6) + " "
        return prefix + _render_inline(children) + "\n\n"

    if node_type == "blockquote":
        inner = _join_blocks(children).rstrip("\n")
        lines = inner.split("\n")
        return "\n".join(("> " + line).rstrip() for line in lines) + "\n\n"

    if node_type == "bulletList":
        return _render_list(children, ordered=False) + "\n"

    if node_type == "orderedList":
        start = attrs.get("start")
        try:
            start = int(start) if start is not None else 1
        except (TypeError, ValueError):
            start = 1
        return _render_list(children, ordered=True, start=start) + "\n"

    if node_type == "listItem":
        return _render_list_item(children)

    if node_type == "taskList":
        return _render_task_list(children) + "\n"

    if node_type == "taskItem":
        checked = attrs.get("checked", False)
        box = "[x] " if checked else "[ ] "
        return box + _render_list_item(children)

    if node_type in ("codeBlock", "customCodeBlock"):
        lang = attrs.get("language") or ""
        text = "".join(c.get("text", "") for c in children if c.get("type") == "text")
        fence = _code_fence(text)
        return f"{fence}{lang}\n{text}\n{fence}\n\n"

    if node_type == "hardBreak":
        return "\n"

    if node_type == "horizontalRule":
        return "---\n\n"

    if node_type in ("table", "customTable"):
        return _render_table(children)

    if node_type in ("tableRow",):
        return _render_table_row(children)

    if node_type in ("image", "tiptapImage"):
        src = attrs.get("src", "")
        alt = attrs.get("alt") or ""
        return f"![{alt}]({src})\n\n"

    if node_type == "callout":
        # Docmost's marked callout extension round-trips via `:::<type>\n...\n:::`.
        # The PM node attr is `type` in {info, success, warning, danger} (default info);
        # an unknown type is coerced to info on re-ingest.
        ctype = attrs.get("type") or "info"
        inner = _join_blocks(children).strip()
        return f":::{ctype}\n{inner}\n:::\n\n"

    if node_type == "mathInline":
        # Docmost stores the LaTeX under attrs["text"] (older builds used "latex"); the stored
        # value carries a trailing newline, so strip before wrapping. Empty -> render children.
        text = (attrs.get("latex") or attrs.get("text") or _render_inline(children)).strip()
        return f"${text}$"

    if node_type == "mathBlock":
        text = (attrs.get("latex") or attrs.get("text") or _render_inline(children)).strip()
        return f"$$\n{text}\n$$\n\n"

    if node_type == "youtube":
        src = attrs.get("src", "")
        return f"[YouTube]({src})\n\n"

    if node_type in ("details",):
        summary = ""
        body_parts = []
        for child in children:
            if child.get("type") == "detailsSummary":
                summary = _render_inline(child.get("content", []))
            elif child.get("type") == "detailsContent":
                body_parts.append(_join_blocks(child.get("content", [])).strip())
        body = "\n\n".join(p for p in body_parts if p)
        return f"<details>\n<summary>{summary}</summary>\n\n{body}\n\n</details>\n\n"

    # Fallback: render any children
    if children:
        return _join_blocks(children)
    return ""


def _join_blocks(nodes: list[dict]) -> str:
    return "".join(_render_node(n) for n in nodes)


def _render_inline(nodes: list[dict]) -> str:
    return "".join(_render_node(n) for n in nodes)


# ---------------------------------------------------------------------------
# Lists — indentation depth is threaded by indenting an item's continuation
# lines (which include any nested list) to the parent marker's width. Recursion
# makes this accumulate to the correct depth.
# ---------------------------------------------------------------------------

def _indent_continuation(item_text: str, marker: str) -> str:
    """Put the first line on the marker line; indent every continuation line (which includes any
    nested list) to the parent marker's width. `marked` nests a child list only when its indent
    reaches the parent marker's content column, so the indent MUST track the marker width: 2 for
    `- `/task items, 3+ for `N. ` ordered markers. A flat 2-space indent silently flattens ordered
    nesting on re-ingest."""
    indent = " " * len(marker)
    item_lines = item_text.split("\n")
    first = marker + (item_lines[0] if item_lines else "")
    rest = [(indent + line) if line.strip() else "" for line in item_lines[1:]]
    return "\n".join([first] + rest)


def _render_list(items: list[dict], ordered: bool, start: int = 1) -> str:
    lines = []
    for i, item in enumerate(items):
        marker = f"{start + i}. " if ordered else "- "
        item_text = _render_node(item).rstrip("\n")
        lines.append(_indent_continuation(item_text, marker))
    return "\n".join(lines) + "\n"


def _render_task_list(items: list[dict]) -> str:
    lines = []
    for item in items:
        # _render_node(taskItem) -> "[x] <body>"; body may carry nested blocks on later lines.
        item_text = _render_node(item).rstrip("\n")
        lines.append(_indent_continuation(item_text, "- "))
    return "\n".join(lines) + "\n"


def _render_list_item(children: list[dict]) -> str:
    """Render a list item's block children onto their own lines. The lead paragraph stays on
    the marker line (set by the caller); a nested list starts on the next line; any other
    block is separated by a blank line. Never space-joins blocks (the old flattening bug)."""
    parts: list[str] = []
    for child in children:
        ctype = child.get("type", "")
        rendered = _render_node(child).rstrip("\n")
        if not rendered:
            continue
        if not parts:
            parts.append(rendered)
        elif ctype in ("bulletList", "orderedList", "taskList"):
            parts.append("\n" + rendered)
        else:
            parts.append("\n\n" + rendered)
    return "".join(parts)


# ---------------------------------------------------------------------------
# Tables — escape `|` inside cells (there it is always structural). Column count
# is taken from the header row's cell count, not by counting pipes (which a
# literal `\|` would corrupt).
# ---------------------------------------------------------------------------

def _render_table(rows: list[dict]) -> str:
    if not rows:
        return ""
    rendered_rows = [_render_table_row(r.get("content", [])) for r in rows]
    col_count = max(len(rows[0].get("content", [])), 1)
    header = rendered_rows[0]
    sep = "| " + " | ".join(["---"] * col_count) + " |"
    body = "\n".join(rendered_rows[1:])
    if body:
        return f"{header}\n{sep}\n{body}\n\n"
    return f"{header}\n{sep}\n\n"


def _render_table_row(cells: list[dict]) -> str:
    parts = []
    for cell in cells:
        text = _render_inline(cell.get("content", []) or _flatten_children(cell))
        text = text.replace("\n", " ").strip()
        text = text.replace("|", "\\|")  # a literal pipe in a cell is always structural
        parts.append(text)
    return "| " + " | ".join(parts) + " |"


def _flatten_children(node: dict) -> list[dict]:
    return node.get("content", [])


# ---------------------------------------------------------------------------
# Marks (inline)
# ---------------------------------------------------------------------------

def _wrap_flanking(text: str, marker: str) -> str:
    """Wrap text in a flanking-delimiter emphasis mark, keeping any boundary whitespace OUTSIDE
    the delimiters. CommonMark forbids whitespace immediately inside emphasis delimiters, so a
    mark whose text node carries a leading/trailing space (Docmost's tiptap parser absorbs the
    space between emphasis and an adjacent inline code span into the mark) must render as
    ' **x** ', never '** x **'. A whitespace-only run is left bare so we never emit empty
    emphasis."""
    core = text.strip()
    if not core:
        return text
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()) :]
    return f"{lead}{marker}{core}{marker}{trail}"


def _apply_marks(text: str, marks: list[dict]) -> str:
    has_code = any(m.get("type") == "code" for m in marks)
    if not has_code:
        text = _escape_inline(text)
    for mark in reversed(marks):
        mark_type = mark.get("type", "")
        mark_attrs = mark.get("attrs") or {}
        if mark_type == "bold":
            text = _wrap_flanking(text, "**")
        elif mark_type == "italic":
            text = _wrap_flanking(text, "*")
        elif mark_type == "strike":
            text = _wrap_flanking(text, "~~")
        elif mark_type == "code":
            text = _wrap_code(text)
        elif mark_type == "underline":
            text = f"<u>{text}</u>"
        elif mark_type == "superscript":
            text = f"<sup>{text}</sup>"
        elif mark_type == "subscript":
            text = f"<sub>{text}</sub>"
        elif mark_type == "link":
            href = mark_attrs.get("href", "")
            text = f"[{text}]({href})"
        # textStyle, color, highlight — pass through as plain text
    return text


# ---------------------------------------------------------------------------
# Position-aware escaping
# ---------------------------------------------------------------------------

# Emphasis runs (literal `*`/`~~` text that would re-parse as a mark). `_` is handled
# separately so intraword underscores (snake_case) are left alone, per GFM.
_STAR_RUN = re.compile(r"(\*\*|\*|~~)(\S(?:.*?\S)?|\S)\1")
_UNDER_RUN = re.compile(r"(?<![0-9A-Za-z])(__|_)(\S(?:.*?\S)?|\S)\1(?![0-9A-Za-z])")
# A `[text](` or `[text][` link/reference opener in literal text.
_LINK_OPEN = re.compile(r"\[([^\]]*)\](?=[\(\[])")
# A complete HTML-ish tag or comment in literal text. In a TEXT node every tag is literal (real
# marks/nodes never appear as text), and tiptap's DOMParser DROPS any tag its schema cannot parse
# (merging neighbours into a paragraph), so the leading `<` is escaped to keep the token literal on
# re-ingest. A bare `<` in prose ("a < b") forms no complete tag, so it is left untouched.
_HTML_TAGISH = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*?)?/?>|<!--")


def _escape_inline(text: str) -> str:
    """Escape inline tokens ONLY where the ingest grammar would parse them as structure.
    Lone, unpaired symbols (a stray `*`, a math-free `$`, `5 - 3`) are left untouched."""
    if not text:
        return text
    # Content backslashes first, so escapes we add below are not doubled.
    text = text.replace("\\", "\\\\")
    # A literal backtick always risks opening a code span; escape it (marked re-reads `\`` as a
    # literal backtick, so it never surfaces inside Docmost).
    text = text.replace("`", "\\`")

    def _esc_delims(m: re.Match) -> str:
        delim, inner = m.group(1), m.group(2)
        esc = "".join("\\" + c for c in delim)
        return esc + inner + esc

    text = _STAR_RUN.sub(_esc_delims, text)
    text = _UNDER_RUN.sub(_esc_delims, text)
    text = _LINK_OPEN.sub(lambda m: "\\[" + m.group(1) + "]", text)
    text = _HTML_TAGISH.sub(lambda m: "\\" + m.group(0), text)
    return text


def _escape_block_start(line: str) -> str:
    """Escape a leading block-start trigger so a literal line of prose is not re-parsed as a
    heading / list / quote / rule / fence / callout. Up to 3 leading spaces are insignificant
    to the parser, so they are preserved and the trigger after them is escaped."""
    stripped = line.lstrip(" ")
    lead = line[: len(line) - len(stripped)]
    s = stripped
    if not s:
        return line
    if re.match(r"#{1,6}(\s|$)", s):
        return lead + "\\" + s
    if re.match(r"[-+*]\s", s):
        return lead + "\\" + s
    if re.match(r"([-*_])\1{2,}\s*$", s):  # thematic break: ---, ***, ___
        return lead + "\\" + s
    m = re.match(r"(\d{1,9})([.)])(\s)", s)  # ordered marker
    if m:
        n = m.group(1)
        return lead + n + "\\" + s[len(n):]
    if s.startswith(">"):
        return lead + "\\" + s
    if re.match(r"(`{3,}|~{3,})", s):  # fence (also caught by backtick escaping, defensive)
        return lead + "\\" + s
    if s.startswith(":::"):  # callout fence
        return lead + "\\" + s
    return line


def _wrap_code(text: str) -> str:
    """Inline code span with backtick-run escalation (CommonMark): the delimiter is a run of
    backticks longer than any run inside the content, with a space pad when the content edges
    are backticks. No backslash escaping (it is inert inside code spans)."""
    runs = re.findall(r"`+", text)
    longest = max((len(r) for r in runs), default=0)
    ticks = "`" * (longest + 1)
    pad = " " if text.startswith("`") or text.endswith("`") or text == "" else ""
    return f"{ticks}{pad}{text}{pad}{ticks}"


def _code_fence(text: str) -> str:
    """Fenced code-block delimiter longer than any backtick run inside the body."""
    runs = re.findall(r"`+", text)
    longest = max((len(r) for r in runs), default=0)
    return "`" * max(3, longest + 1)
