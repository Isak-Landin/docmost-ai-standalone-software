from __future__ import annotations

import hashlib
import unicodedata
from difflib import SequenceMatcher

from app.models import SyncDiffHunkOut


def canonicalize_title(text: str | None) -> str:
    normalized = (text or "").strip()
    return unicodedata.normalize("NFC", normalized)


def canonicalize_content(text: str | None) -> str:
    normalized = (text or "").lstrip("\ufeff")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = unicodedata.normalize("NFC", normalized)
    return "\n".join(normalized.splitlines())


def content_hash(text: str | None) -> str:
    normalized = canonicalize_content(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def revision_hash(title: str | None, text: str | None) -> str:
    normalized_title = canonicalize_title(title)
    normalized_content = canonicalize_content(text)
    payload = f"{normalized_title}\n---\n{normalized_content}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_diff_hunks(local_text: str | None, remote_text: str | None) -> list[SyncDiffHunkOut]:
    local_lines = canonicalize_content(local_text).splitlines()
    remote_lines = canonicalize_content(remote_text).splitlines()

    matcher = SequenceMatcher(a=local_lines, b=remote_lines)
    hunks: list[SyncDiffHunkOut] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        kind = {"replace": "replace", "insert": "insert", "delete": "delete"}[tag]
        hunks.append(
            SyncDiffHunkOut(
                kind=kind,
                local_start_line=_start_line(i1),
                local_end_line=_end_line(i1, i2),
                remote_start_line=_start_line(j1),
                remote_end_line=_end_line(j1, j2),
                local_lines=local_lines[i1:i2],
                remote_lines=remote_lines[j1:j2],
            )
        )

    return hunks


def _start_line(index: int) -> int:
    return index + 1


def _end_line(start_index: int, end_index: int) -> int:
    return start_index if start_index == end_index else end_index
