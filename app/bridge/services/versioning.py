from __future__ import annotations

import hashlib

from app.bridge.errors import BridgeConflictError
from app.bridge.schemas.operations import BridgePageSnapshot
from app.bridge.schemas.state import PageHeadRecord
from app.bridge.services.normalization import canonicalize_content, canonicalize_title


def content_hash(text: str | None) -> str:
    normalized = canonicalize_content(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def revision_hash(title: str | None, text: str | None) -> str:
    normalized_title = canonicalize_title(title)
    normalized_content = canonicalize_content(text)
    payload = f"{normalized_title}\n---\n{normalized_content}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def assert_head_alignment(
    current_head: PageHeadRecord | None,
    *,
    expected_base_revision_hash: str | None,
    require_alignment: bool,
    force: bool,
) -> None:
    if force or not require_alignment:
        return
    if current_head is None or current_head.current_revision_hash is None:
        raise BridgeConflictError("Bridge head is missing for this page. Bootstrap or observe the page before applying aligned writes.")
    if not expected_base_revision_hash:
        raise BridgeConflictError("Aligned bridge writes require a base_revision_hash.")
    if current_head.current_revision_hash != expected_base_revision_hash:
        raise BridgeConflictError(
            f"Bridge head mismatch. Expected {expected_base_revision_hash}, current head is {current_head.current_revision_hash}."
        )


def snapshot_from_page(
    *,
    page_id,
    space_id,
    title: str | None,
    slug_id: str | None,
    parent_page_id,
    content: str | None,
    remote_updated_at,
    is_deleted: bool = False,
) -> BridgePageSnapshot:
    normalized_title = canonicalize_title(title) or None
    normalized_content = canonicalize_content(content)
    return BridgePageSnapshot(
        page_id=page_id,
        space_id=space_id,
        title=normalized_title,
        slug_id=slug_id,
        parent_page_id=parent_page_id,
        content=normalized_content,
        revision_hash=revision_hash(normalized_title, normalized_content),
        remote_updated_at=remote_updated_at,
        is_deleted=is_deleted,
    )
