"""Round-trip / structural tests for the ProseMirror -> Markdown egress renderer.

The renderer must emit markdown that re-imports (via Docmost's `marked`, breaks:true) to the
same ProseMirror tree. We cannot run `marked` here, so we assert the rendered markdown matches
the conventions of Docmost's own `turndown` serializer (the proven inverse) and that ordinary
prose is NOT over-escaped. The true end-to-end round-trip is validated against a live throwaway
Docmost space at deploy time.
"""

from app.query.prosemirror import prosemirror_to_markdown


# --- ProseMirror node builders -------------------------------------------------

def doc(*content):
    return {"type": "doc", "content": list(content)}


def para(*inline):
    items = [t if isinstance(t, dict) else {"type": "text", "text": t} for t in inline]
    return {"type": "paragraph", "content": items}


def text(s, marks=None):
    n = {"type": "text", "text": s}
    if marks:
        n["marks"] = marks
    return n


def bullet(*items):
    return {"type": "bulletList", "content": list(items)}


def ordered(*items, start=None):
    n = {"type": "orderedList", "content": list(items)}
    if start is not None:
        n["attrs"] = {"start": start}
    return n


def li(*blocks):
    return {"type": "listItem", "content": list(blocks)}


def task_list(*items):
    return {"type": "taskList", "content": list(items)}


def task_item(checked, *blocks):
    return {"type": "taskItem", "attrs": {"checked": checked}, "content": list(blocks)}


def cell(*blocks):
    return {"type": "tableCell", "content": list(blocks)}


def row(*cells):
    return {"type": "tableRow", "content": list(cells)}


def render(node):
    return prosemirror_to_markdown(node)


# --- Fault A: nested-list flattening (the headline bug) ------------------------

def test_nested_bullet_list_is_indented_not_flattened():
    d = doc(bullet(li(
        para("Parent"),
        bullet(li(para("ChildA")), li(para("ChildB"))),
    )))
    assert render(d) == "- Parent\n  - ChildA\n  - ChildB"


def test_three_level_nesting_uses_two_spaces_per_level():
    d = doc(bullet(li(
        para("Parent"),
        bullet(li(
            para("ChildA"),
            bullet(li(para("GrandA"))),
        )),
    )))
    assert render(d) == "- Parent\n  - ChildA\n    - GrandA"


def test_ordered_list_respects_start_attr():
    d = doc(ordered(li(para("a")), li(para("b")), start=3))
    assert render(d) == "3. a\n4. b"


def test_mixed_ordered_with_nested_bullet():
    d = doc(ordered(li(para("Step"), bullet(li(para("sub"))))))
    assert render(d) == "1. Step\n  - sub"


def test_task_list_preserves_checkboxes():
    d = doc(task_list(task_item(True, para("done")), task_item(False, para("todo"))))
    assert render(d) == "- [x] done\n- [ ] todo"


def test_nested_task_list_indents():
    d = doc(task_list(task_item(False, para("parent"),
                                task_list(task_item(True, para("child"))))))
    assert render(d) == "- [ ] parent\n  - [x] child"


# --- Callout: round-trips via :::type, not "> emoji" ---------------------------

def test_callout_uses_colon_fence_with_type():
    d = doc({"type": "callout", "attrs": {"type": "warning"},
             "content": [para("Be careful")]})
    assert render(d) == ":::warning\nBe careful\n:::"


def test_callout_defaults_to_info():
    d = doc({"type": "callout", "content": [para("note")]})
    assert render(d) == ":::info\nnote\n:::"


# --- Code: fence + backtick-run escalation -------------------------------------

def test_code_block_escalates_fence_past_internal_backticks():
    d = doc({"type": "codeBlock", "attrs": {"language": "python"},
             "content": [text("a\n```\nb")]})
    assert render(d) == "````python\na\n```\nb\n````"


def test_inline_code_escalates_backticks():
    d = doc(para(text("a`b", marks=[{"type": "code"}])))
    assert render(d) == "``a`b``"


def test_inline_code_pads_when_edge_is_backtick():
    d = doc(para(text("`x", marks=[{"type": "code"}])))
    assert render(d) == "`` `x ``"


def test_inline_code_content_is_not_escaped():
    d = doc(para(text("a*b*c_d_", marks=[{"type": "code"}])))
    assert render(d) == "`a*b*c_d_`"


# --- Tables: escape literal pipes, count columns by cells ----------------------

def test_table_escapes_pipe_in_cell():
    d = doc({"type": "table", "content": [
        row(cell(para("a|b")), cell(para("c"))),
        row(cell(para("d")), cell(para("e"))),
    ]})
    assert render(d) == "| a\\|b | c |\n| --- | --- |\n| d | e |"


# --- Hard breaks + horizontal rule ---------------------------------------------

def test_hard_break_emits_single_newline():
    d = doc(para(text("line1"), {"type": "hardBreak"}, text("line2")))
    assert render(d) == "line1\nline2"


def test_block_start_escaped_after_hard_break():
    d = doc(para(text("intro"), {"type": "hardBreak"}, text("- not a list")))
    assert render(d) == "intro\n\\- not a list"


def test_horizontal_rule():
    d = doc(para("a"), {"type": "horizontalRule"}, para("b"))
    assert render(d) == "a\n\n---\n\nb"


# --- Block-start escaping (a literal line must not become structure) -----------

def test_literal_thematic_break_paragraph_is_escaped():
    assert render(doc(para("---"))) == "\\---"


def test_literal_leading_bullet_is_escaped():
    assert render(doc(para("- item"))) == "\\- item"


def test_literal_leading_heading_is_escaped():
    assert render(doc(para("# heading-like"))) == "\\# heading-like"


def test_literal_leading_blockquote_is_escaped():
    assert render(doc(para("> quote-like"))) == "\\> quote-like"


def test_literal_ordered_marker_is_escaped():
    assert render(doc(para("1. ordered-like"))) == "1\\. ordered-like"


# --- Inline emphasis / link literals (position-aware) --------------------------

def test_literal_emphasis_is_escaped():
    assert render(doc(para("*foo*"))) == "\\*foo\\*"


def test_intraword_emphasis_pair_is_escaped():
    assert render(doc(para("a*b*c"))) == "a\\*b\\*c"


def test_literal_link_opener_is_escaped():
    assert render(doc(para("see [docs](http://x) here"))) == "see \\[docs](http://x) here"


# --- The no-spurious-escaping guarantee (clean prose stays clean) --------------

def test_snake_case_underscores_are_not_escaped():
    assert render(doc(para("use snake_case_name here"))) == "use snake_case_name here"


def test_space_flanked_symbols_are_not_escaped():
    assert render(doc(para("compute 5 * 3 and 2 - 1 = 1"))) == "compute 5 * 3 and 2 - 1 = 1"


def test_plain_prose_round_trips_byte_for_byte():
    s = "Normal prose: a price of $5, C++ code, and a dash - in the middle."
    assert render(doc(para(s))) == s


# --- Marks ---------------------------------------------------------------------

def test_bold_italic_strike_underline_link_marks():
    assert render(doc(para(text("b", marks=[{"type": "bold"}])))) == "**b**"
    assert render(doc(para(text("i", marks=[{"type": "italic"}])))) == "*i*"
    assert render(doc(para(text("s", marks=[{"type": "strike"}])))) == "~~s~~"
    assert render(doc(para(text("u", marks=[{"type": "underline"}])))) == "<u>u</u>"
    link = [{"type": "link", "attrs": {"href": "http://x"}}]
    assert render(doc(para(text("click", marks=link)))) == "[click](http://x)"


def test_emphasis_boundary_whitespace_stays_outside_delimiters():
    d = doc(para(text("a"), text(" b ", marks=[{"type": "bold"}]), text("c")))
    assert render(d) == "a **b** c"


# --- Headings ------------------------------------------------------------------

def test_heading_is_atx():
    d = doc({"type": "heading", "attrs": {"level": 2}, "content": [text("Title")]})
    assert render(d) == "## Title"
