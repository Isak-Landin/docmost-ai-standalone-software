"""Make outgoing markdown safe for Docmost's `marked` ingest (the write half of ISSUE-2).

Docmost parses page content sent with `format:"markdown"` using `marked` (CommonMark + extensions).
Flanking `_`/`__` that are NOT inside a code span are read as emphasis, so an unescaped code/path
token such as `app/__init__.py` is stored as bold `init` and read back as `app/**init**.py`.

The bridge's egress renderer (`app/query/prosemirror.py`) already enforces a single convention on
the way OUT: emphasis is emitted only as `*`/`**` (`_apply_marks`) and literal flanking `_`/`__` in
text is escaped to `\\_\\_` (`_escape_inline` / `_UNDER_RUN`). This module applies the SAME
convention on the way IN, so the write path stops letting `marked` impose its own dialect. That
makes the round-trip symmetric: a literal `app/__init__.py` stays literal end to end.

Properties:
- Position-aware: never touches inline-code spans or fenced code blocks (their content is literal to
  `marked` already, and emphasis markers there are intentional).
- Idempotent: an already-escaped `\\_` is never re-escaped (the `(?<!\\)` guard), so re-pushing the
  canonical read-back form is a no-op and the reconcile/revision-hash stays stable.
- Minimal: only flanking `_`/`__` are escaped. `*`/`**` emphasis, backticks, links and structural
  block markers are left untouched (escaping those would corrupt intentional formatting).
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


def _escape_underscore_runs(text: str) -> str:
    def _esc(m: re.Match) -> str:
        delim, inner = m.group(1), m.group(2)
        escaped_delim = "".join("\\" + ch for ch in delim)
        return escaped_delim + inner + escaped_delim

    return _FLANKING_UNDERSCORE.sub(_esc, text)


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
                out.append(_escape_underscore_runs(line[i:]))  # unmatched ` -> literal text
                i = n
        else:
            k = line.find("`", i)
            if k == -1:
                out.append(_escape_underscore_runs(line[i:]))
                i = n
            else:
                out.append(_escape_underscore_runs(line[i:k]))
                i = k
    return "".join(out)


def escape_markdown_for_ingest(md: str) -> str:
    """Escape flanking `_`/`__` outside code (spans + fences), idempotently, so Docmost's `marked`
    stores them as literal text instead of emphasis. Mirrors the egress renderer's convention."""
    if not md or ("_" not in md):
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
