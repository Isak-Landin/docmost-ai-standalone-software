from __future__ import annotations

from app.bridge.services.diffing import build_diff_hunks as build_bridge_diff_hunks
from app.bridge.services.normalization import canonicalize_content, canonicalize_title
from app.bridge.services.versioning import content_hash, revision_hash
from app.models import SyncDiffHunkOut


def build_diff_hunks(local_text: str | None, remote_text: str | None) -> list[SyncDiffHunkOut]:
    return [
        SyncDiffHunkOut(
            kind=hunk.kind,
            local_start_line=hunk.local_start_line,
            local_end_line=hunk.local_end_line,
            remote_start_line=hunk.remote_start_line,
            remote_end_line=hunk.remote_end_line,
            local_lines=hunk.local_lines,
            remote_lines=hunk.remote_lines,
        )
        for hunk in build_bridge_diff_hunks(local_text, remote_text)
    ]
