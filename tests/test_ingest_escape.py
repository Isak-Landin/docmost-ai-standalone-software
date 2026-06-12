"""Offline tests for the write-path ingest escaper (app/write/ingest_escape.py).

The escaper makes outgoing markdown safe for Docmost's `marked` ingest by escaping flanking
`_`/`__` outside code, mirroring the egress renderer's convention (emphasis is `*`/`**`; literal
`_`/`__` is escaped) so the markdown -> ProseMirror -> markdown round-trip is symmetric. The true
end-to-end round-trip is validated against a live throwaway Docmost space at deploy time.
"""

from app.write.ingest_escape import escape_markdown_for_ingest as esc


def test_reported_repro_dunder_path():
    # `app/__init__.py` -> bold `init` was the reported ISSUE-2; now kept literal.
    assert esc("the factory at app/__init__.py builds it") == \
        "the factory at app/\\_\\_init\\_\\_.py builds it"


def test_double_underscore_identifier():
    assert esc("__main__") == "\\_\\_main\\_\\_"
    assert esc("dunder __name__ here") == "dunder \\_\\_name\\_\\_ here"


def test_single_flanking_underscore_becomes_literal():
    # Dialect (already enforced by the egress): emphasis is `*`/`**`, flanking `_` is literal.
    assert esc("_italic_") == "\\_italic\\_"


def test_intraword_underscore_untouched():
    # snake_case must NOT be escaped (CommonMark does not emphasize intraword `_`).
    assert esc("a snake_case name") == "a snake_case name"
    assert esc("call do_thing_now() please") == "call do_thing_now() please"


def test_star_emphasis_preserved():
    # Only underscores are escaped; intended `*`/`**` emphasis is untouched.
    assert esc("**bold** and *italic* stay") == "**bold** and *italic* stay"


def test_inline_code_span_untouched():
    assert esc("`app/__init__.py`") == "`app/__init__.py`"
    assert esc("see `app/__init__.py` then __x__") == "see `app/__init__.py` then \\_\\_x\\_\\_"


def test_inline_code_and_text_mixed():
    assert esc("__a__ `__b__` __c__") == "\\_\\_a\\_\\_ `__b__` \\_\\_c\\_\\_"


def test_fenced_code_block_untouched():
    md = "before __x__\n```\ncode __y__ line\n```\nafter __z__"
    out = esc(md)
    assert "\ncode __y__ line\n" in out          # fence content verbatim
    assert out.startswith("before \\_\\_x\\_\\_")  # prose escaped
    assert out.endswith("after \\_\\_z\\_\\_")


def test_tilde_fence_and_info_string():
    md = "~~~python\nx = __dunder__\n~~~\ntail __y__"
    out = esc(md)
    assert "x = __dunder__" in out               # inside fence: verbatim
    assert out.endswith("tail \\_\\_y\\_\\_")


def test_idempotent_on_already_escaped():
    # The canonical read-back form re-pushes as a no-op (never double-escaped).
    already = "app/\\_\\_init\\_\\_.py"
    assert esc(already) == already
    assert esc(esc("app/__init__.py")) == esc("app/__init__.py")


def test_mixed_escaped_and_new_idempotent():
    assert esc("old \\_\\_a\\_\\_ and new __b__") == "old \\_\\_a\\_\\_ and new \\_\\_b\\_\\_"


def test_no_underscore_is_passthrough():
    s = "plain **bold**, a $price, a | pipe, a # hash"
    assert esc(s) == s


def test_empty_and_none_safe():
    assert esc("") == ""
    assert esc(None) is None
