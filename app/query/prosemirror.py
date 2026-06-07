"""Convert a Docmost ProseMirror JSON document to Markdown.

Handles the full Tiptap/Docmost node and mark set as observed in the running
Docmost container (starter-kit + docmost editor-ext extensions).
"""

from __future__ import annotations

from typing import Any


def prosemirror_to_markdown(doc: dict[str, Any]) -> str:
    """Convert a ProseMirror JSON doc to a Markdown string."""
    if not isinstance(doc, dict):
        return str(doc)
    return _render_node(doc).strip()


# ---------------------------------------------------------------------------
# Internal renderer
# ---------------------------------------------------------------------------

def _render_node(node: dict[str, Any], context: dict | None = None) -> str:
    node_type = node.get("type", "")
    children = node.get("content", [])
    attrs = node.get("attrs") or {}

    if node_type == "doc":
        return _join_blocks(children)

    if node_type == "paragraph":
        inner = _render_inline(children)
        return inner + "\n\n" if inner.strip() else "\n"

    if node_type == "text":
        return _apply_marks(node.get("text", ""), node.get("marks", []))

    if node_type == "heading":
        level = int(attrs.get("level", 1))
        prefix = "#" * min(max(level, 1), 6) + " "
        return prefix + _render_inline(children) + "\n\n"

    if node_type == "blockquote":
        inner = _join_blocks(children).rstrip("\n")
        lines = inner.split("\n")
        return "\n".join("> " + line for line in lines) + "\n\n"

    if node_type == "bulletList":
        return _render_list(children, ordered=False) + "\n"

    if node_type == "orderedList":
        return _render_list(children, ordered=True) + "\n"

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
        return f"```{lang}\n{text}\n```\n\n"

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
        emoji = attrs.get("emoji") or "ℹ️"
        inner = _join_blocks(children).rstrip("\n")
        lines = inner.split("\n")
        first = lines[0] if lines else ""
        rest = "\n".join("> " + l for l in lines[1:])
        block = f"> {emoji} {first}"
        if rest:
            block += "\n" + rest
        return block + "\n\n"

    if node_type == "mathInline":
        text = attrs.get("latex") or _render_inline(children)
        return f"${text}$"

    if node_type == "mathBlock":
        text = attrs.get("latex") or _render_inline(children)
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
                body_parts.append(_join_blocks(child.get("content", [])).rstrip("\n"))
        body = "\n".join(body_parts)
        lines = body.split("\n")
        indented = "\n".join("  " + l for l in lines)
        return f"<details>\n<summary>{summary}</summary>\n\n{indented}\n\n</details>\n\n"

    # Fallback: render any children
    if children:
        return _join_blocks(children)
    return ""


def _join_blocks(nodes: list[dict]) -> str:
    return "".join(_render_node(n) for n in nodes)


def _render_inline(nodes: list[dict]) -> str:
    return "".join(_render_node(n) for n in nodes)


def _wrap_flanking(text: str, marker: str) -> str:
    """Wrap text in a flanking-delimiter emphasis mark, keeping any boundary whitespace
    OUTSIDE the delimiters. CommonMark forbids whitespace immediately inside emphasis
    delimiters, so a mark whose text node carries a leading/trailing space (Docmost's
    tiptap parser absorbs the space between emphasis and an adjacent inline code span into
    the mark) must render as ' **x** ', never '** x **'. A whitespace-only run is left bare
    so we never emit empty emphasis."""
    core = text.strip()
    if not core:
        return text
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()) :]
    return f"{lead}{marker}{core}{marker}{trail}"


def _apply_marks(text: str, marks: list[dict]) -> str:
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
            text = f"`{text}`"
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


def _render_list(items: list[dict], ordered: bool) -> str:
    lines = []
    for i, item in enumerate(items):
        prefix = f"{i + 1}. " if ordered else "- "
        item_text = _render_node(item).rstrip("\n")
        # Indent continuation lines
        item_lines = item_text.split("\n")
        first = prefix + (item_lines[0] if item_lines else "")
        rest = [" " * len(prefix) + l for l in item_lines[1:] if l.strip()]
        lines.append("\n".join([first] + rest))
    return "\n".join(lines) + "\n"


def _render_task_list(items: list[dict]) -> str:
    lines = []
    for item in items:
        lines.append("- " + _render_node(item).rstrip("\n"))
    return "\n".join(lines) + "\n"


def _render_list_item(children: list[dict]) -> str:
    parts = []
    for child in children:
        rendered = _render_node(child).rstrip("\n")
        parts.append(rendered)
    return " ".join(parts)


def _render_table(rows: list[dict]) -> str:
    rendered_rows = [_render_table_row(r.get("content", [])) for r in rows]
    if not rendered_rows:
        return ""
    header = rendered_rows[0]
    col_count = header.count("|") - 1
    sep = "| " + " | ".join(["---"] * max(col_count, 1)) + " |"
    body = "\n".join(rendered_rows[1:])
    if body:
        return f"{header}\n{sep}\n{body}\n\n"
    return f"{header}\n{sep}\n\n"


def _render_table_row(cells: list[dict]) -> str:
    parts = []
    for cell in cells:
        text = _render_inline(cell.get("content", []) or
                              _flatten_children(cell)).replace("\n", " ").strip()
        parts.append(text)
    return "| " + " | ".join(parts) + " |"


def _flatten_children(node: dict) -> list[dict]:
    return node.get("content", [])
