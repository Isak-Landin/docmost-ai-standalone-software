"""The single revision-hash content-derivation point.

Every `revision_hash` in the bridge MUST be derived here, from Docmost's stored content read
back and rendered deterministically (ProseMirror -> markdown). Docmost is the only place all
surfaces converge: bridge MCP, bridge CRUD, helper push, the worker/observer, and direct Docmost
UI edits all end up as the same stored ProseMirror, and `query.docmost.get_page` renders it the
same way every time (it strips Docmost's volatile per-node ids). Anchoring every head/version to
this one derivation makes the hash identical regardless of which surface produced the change, so
the input-vs-rendered drift cannot occur.

Do NOT hash caller-supplied input markdown anywhere; always finalize through these functions.
"""

from __future__ import annotations

from uuid import UUID

from app.bridge.schemas.operations import BridgePageSnapshot
from app.bridge.services.versioning import snapshot_from_page
from app.query.docmost import get_page as _fetch_rendered_page


def snapshot_from_fetched_page(page) -> BridgePageSnapshot:
    """Derive the canonical snapshot from a query.docmost PageOut (content already rendered to
    markdown from Docmost's ProseMirror). This is THE hash basis for every origin."""
    return snapshot_from_page(
        page_id=page.id,
        space_id=page.space_id,
        title=page.title,
        slug_id=page.slug_id,
        parent_page_id=page.parent_page_id,
        content=page.content,
        remote_updated_at=page.updated_at,
        position=page.position,
        icon=page.icon,
    )


def canonical_page_snapshot(space_id: UUID, page_id: UUID) -> BridgePageSnapshot:
    """Read a page back from Docmost and derive its canonical snapshot. Used by the write
    pipeline after a remote write so a write-origin head equals an observe-origin head exactly."""
    return snapshot_from_fetched_page(_fetch_rendered_page(space_id, page_id))
