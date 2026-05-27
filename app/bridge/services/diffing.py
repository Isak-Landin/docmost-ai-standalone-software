from __future__ import annotations

from difflib import SequenceMatcher

from app.bridge.schemas.diff import DiffHunk
from app.bridge.services.normalization import canonicalize_content


def build_diff_hunks(local_text: str | None, remote_text: str | None) -> list[DiffHunk]:
    local_lines = canonicalize_content(local_text).splitlines()
    remote_lines = canonicalize_content(remote_text).splitlines()

    matcher = SequenceMatcher(a=local_lines, b=remote_lines)
    hunks: list[DiffHunk] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        kind = {"replace": "replace", "insert": "insert", "delete": "delete"}[tag]
        hunks.append(
            DiffHunk(
                kind=kind,
                local_start_line=i1 + 1,
                local_end_line=i1 if i1 == i2 else i2,
                remote_start_line=j1 + 1,
                remote_end_line=j1 if j1 == j2 else j2,
                local_lines=local_lines[i1:i2],
                remote_lines=remote_lines[j1:j2],
            )
        )
    return hunks
