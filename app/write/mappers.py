from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.bridge.schemas.operations import BridgeWriteResult
from app.models import PageMetaOut, PageOut, SpaceOut
from app.query.prosemirror import prosemirror_to_markdown


def map_page_meta(page: dict) -> PageMetaOut:
    return PageMetaOut(
        id=page["id"],
        slug_id=page.get("slugId") or page.get("slug_id") or "",
        title=page.get("title"),
        icon=page.get("icon"),
        position=page.get("position"),
        parent_page_id=page.get("parentPageId") or page.get("parent_page_id"),
        creator_id=page.get("creatorId") or page.get("creator_id"),
        last_updated_by_id=page.get("lastUpdatedById") or page.get("last_updated_by_id"),
        space_id=page.get("spaceId") or page.get("space_id"),
        workspace_id=page.get("workspaceId") or page.get("workspace_id"),
        is_locked=page.get("isLocked") or page.get("is_locked") or False,
        created_at=page.get("createdAt") or page.get("created_at") or datetime.now(timezone.utc),
        updated_at=page.get("updatedAt") or page.get("updated_at") or datetime.now(timezone.utc),
    )


def map_space(data: dict) -> SpaceOut:
    return SpaceOut(
        id=data["id"],
        name=data.get("name"),
        description=data.get("description"),
        slug=data["slug"],
        visibility=data.get("visibility", "private"),
        default_role=data.get("defaultRole", "writer"),
        creator_id=data.get("creatorId"),
        workspace_id=data["workspaceId"],
        created_at=data.get("createdAt") or datetime.now(timezone.utc),
        updated_at=data.get("updatedAt") or datetime.now(timezone.utc),
    )


def map_page_out_from_rest(data: dict) -> PageOut:
    page = data.get("page", data)
    raw_content = page.get("content")
    if isinstance(raw_content, dict):
        content = prosemirror_to_markdown(raw_content)
    else:
        content = raw_content

    return PageOut(
        id=page["id"],
        slug_id=page.get("slugId") or page.get("slug_id") or "",
        title=page.get("title"),
        icon=page.get("icon"),
        position=page.get("position"),
        parent_page_id=page.get("parentPageId") or page.get("parent_page_id"),
        creator_id=page.get("creatorId") or page.get("creator_id"),
        last_updated_by_id=page.get("lastUpdatedById") or page.get("last_updated_by_id"),
        space_id=page.get("spaceId") or page.get("space_id") or "",
        workspace_id=page.get("workspaceId") or page.get("workspace_id") or "",
        is_locked=page.get("isLocked") or page.get("is_locked") or False,
        content=content,
        created_at=page.get("createdAt") or page.get("created_at") or datetime.now(timezone.utc),
        updated_at=page.get("updatedAt") or page.get("updated_at") or datetime.now(timezone.utc),
    )


def map_page_out_from_bridge_result(result: BridgeWriteResult) -> PageOut:
    page = result.remote_page
    return PageOut(
        id=result.page_id,
        slug_id=result.slug_id or page.get("slugId") or page.get("slug_id") or "",
        title=result.title,
        icon=page.get("icon"),
        position=page.get("position"),
        parent_page_id=result.parent_page_id,
        creator_id=page.get("creatorId") or page.get("creator_id"),
        last_updated_by_id=page.get("lastUpdatedById") or page.get("last_updated_by_id"),
        space_id=result.space_id,
        workspace_id=page.get("workspaceId") or page.get("workspace_id") or "",
        is_locked=page.get("isLocked") or page.get("is_locked") or False,
        content=result.content,
        created_at=page.get("createdAt") or page.get("created_at") or datetime.now(timezone.utc),
        updated_at=result.remote_updated_at or page.get("updatedAt") or page.get("updated_at") or datetime.now(timezone.utc),
    )
