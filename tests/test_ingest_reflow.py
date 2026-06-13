"""Offline tests for the write-path block reflow (app/write/ingest_reflow.py).

The reflow re-indents under-indented sub-lists to the parent marker's content column so Docmost's
`marked` nests them instead of flattening, mirroring the egress renderer's marker-width invariant
(`indent = " " * len(marker)`). It is deliberately conservative: it only touches pure marker
regions, is a no-op on the canonical egress form, and is idempotent. The end-to-end round-trip is
validated against a live throwaway Docmost space at deploy time.
"""

from app.write.ingest_reflow import (
    guard_frontmatter_strip as guard,
    reflow_ordered_lists_for_ingest as reflow,
)


# --- ordered-list flatten: the reported repro ---------------------------------------------------

def test_two_space_ordered_child_promoted_to_marker_width():
    src = "1. parent\n  1. child\n  2. child"
    assert reflow(src) == "1. parent\n   1. child\n   2. child"


def test_multi_level_uniform_two_space_promoted_per_level():
    # Docmost's own turndown export is uniform 2-space; each level widens to its marker column.
    src = "1. a\n  1. b\n    1. c"
    assert reflow(src) == "1. a\n   1. b\n      1. c"


def test_siblings_and_dedent_realign():
    src = "1. p\n  1. a\n    1. x\n  2. b"
    assert reflow(src) == "1. p\n   1. a\n      1. x\n   2. b"


def test_multi_digit_marker_width():
    # `10. ` is a four-column marker, so its children must reach column 4 (here promoted from 2).
    src = "10. parent\n  1. child"
    assert reflow(src) == "10. parent\n    1. child"


def test_paren_delimiter_marker():
    src = "1) parent\n  1) child"
    assert reflow(src) == "1) parent\n   1) child"


def test_bullet_child_of_ordered_parent_promoted():
    # A bullet child two-spaces under `1. ` (content column 3) also flattens -> promote to 3.
    src = "1. parent\n  - child"
    assert reflow(src) == "1. parent\n   - child"


# --- no-op / idempotence: the canonical egress form must round-trip unchanged -------------------

def test_already_marker_width_is_noop():
    src = "1. parent\n   1. child\n   2. child"
    assert reflow(src) == src


def test_idempotent():
    src = "1. a\n  1. b\n    1. c"
    once = reflow(src)
    assert reflow(once) == once


def test_correct_bullet_nesting_untouched():
    # Bullets nest correctly at 2 spaces (content column 2) -> never changed.
    src = "- a\n  - b\n    - c"
    assert reflow(src) == src


def test_top_level_list_untouched():
    src = "1. a\n2. b\n3. c"
    assert reflow(src) == src


# --- conservatism: leave anything that is not a pure marker region alone ------------------------

def test_loose_list_with_blank_lines_untouched():
    # A blank line breaks the pure region, so a loose list is left as-is (manual workaround).
    src = "1. parent\n\n  1. child"
    assert reflow(src) == src


def test_item_with_continuation_paragraph_untouched():
    # A continuation line is not a marker, so the region is impure -> untouched.
    src = "1. parent\n  some wrapped text\n  1. child"
    assert reflow(src) == src


def test_fenced_code_block_verbatim():
    src = "```\n1. a\n  1. b\n```"
    assert reflow(src) == src


def test_indented_listish_text_in_fence_verbatim():
    src = "intro\n```\n1. a\n  1. b\n```\ntail"
    assert reflow(src) == src


def test_thematic_break_not_treated_as_marker():
    # `- - -` is a rule, not a list item; it must not become a parent or be reflowed.
    src = "text\n- - -\nmore"
    assert reflow(src) == src


def test_empty_and_single_line_safe():
    assert reflow("") == ""
    assert reflow(None) is None
    assert reflow("just one line 1. not a list") == "just one line 1. not a list"


# --- front-matter strip guard ------------------------------------------------------------------

def test_leading_dash_rule_with_later_rule_rewritten():
    # Docmost would eat `---\n...\n---` as front matter; rewrite the leading rule to ***.
    src = "---\nintro\n---\nbody"
    assert guard(src) == "***\nintro\n---\nbody"


def test_no_second_rule_is_noop():
    # Without a closing `---`, the front-matter regex never fires, so leave it.
    src = "---\njust a thematic break then prose"
    assert guard(src) == src


def test_prose_leading_dashes_untouched():
    # A line that merely starts with --- but is not a clean rule is left alone.
    src = "--- note\nthen later ---\nmore"
    assert guard(src) == src


def test_guard_idempotent():
    src = "---\nintro\n---\nbody"
    once = guard(src)
    assert guard(once) == once


def test_guard_empty_safe():
    assert guard("") == ""
    assert guard(None) is None
