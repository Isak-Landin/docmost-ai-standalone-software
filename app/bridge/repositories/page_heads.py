from __future__ import annotations

from uuid import UUID

from app.bridge.schemas.operations import BridgePageSnapshot
from app.bridge.schemas.state import PageHeadRecord


def get_page_head(cur, page_id: UUID) -> PageHeadRecord | None:
    cur.execute(
        """
        SELECT *
        FROM page_heads
        WHERE page_id = %s
        LIMIT 1
        """,
        (str(page_id),),
    )
    row = cur.fetchone()
    return _map_page_head(row) if row else None


def list_page_heads_for_space(cur, space_id: UUID) -> list[PageHeadRecord]:
    cur.execute(
        """
        SELECT *
        FROM page_heads
        WHERE space_id = %s
        ORDER BY page_id ASC
        """,
        (str(space_id),),
    )
    return [_map_page_head(row) for row in cur.fetchall()]


def upsert_page_head(cur, snapshot: BridgePageSnapshot, *, version_id: UUID | None, source: str) -> PageHeadRecord:
    cur.execute(
        """
        INSERT INTO page_heads (
            page_id,
            space_id,
            current_version_id,
            current_revision_hash,
            title,
            content,
            slug_id,
            parent_page_id,
            remote_updated_at,
            is_deleted,
            last_source,
            last_checked_at,
            created_at,
            updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), NOW()
        )
        ON CONFLICT (page_id)
        DO UPDATE SET
            space_id = EXCLUDED.space_id,
            current_version_id = EXCLUDED.current_version_id,
            current_revision_hash = EXCLUDED.current_revision_hash,
            title = EXCLUDED.title,
            content = EXCLUDED.content,
            slug_id = COALESCE(EXCLUDED.slug_id, page_heads.slug_id),
            parent_page_id = COALESCE(EXCLUDED.parent_page_id, page_heads.parent_page_id),
            remote_updated_at = COALESCE(EXCLUDED.remote_updated_at, page_heads.remote_updated_at),
            is_deleted = EXCLUDED.is_deleted,
            last_source = EXCLUDED.last_source,
            last_checked_at = NOW(),
            updated_at = NOW()
        RETURNING *
        """,
        (
            str(snapshot.page_id),
            str(snapshot.space_id),
            str(version_id) if version_id else None,
            snapshot.revision_hash,
            snapshot.title,
            snapshot.content,
            snapshot.slug_id,
            str(snapshot.parent_page_id) if snapshot.parent_page_id else None,
            snapshot.remote_updated_at,
            snapshot.is_deleted,
            source,
        ),
    )
    return _map_page_head(cur.fetchone())


def mark_page_deleted(cur, page_id: UUID, space_id: UUID, *, source: str) -> PageHeadRecord:
    cur.execute(
        """
        INSERT INTO page_heads (
            page_id,
            space_id,
            current_version_id,
            current_revision_hash,
            title,
            content,
            slug_id,
            parent_page_id,
            remote_updated_at,
            is_deleted,
            last_source,
            last_checked_at,
            created_at,
            updated_at
        )
        VALUES (
            %s, %s, NULL, NULL, NULL, '', NULL, NULL, NULL, TRUE, %s, NOW(), NOW(), NOW()
        )
        ON CONFLICT (page_id)
        DO UPDATE SET
            current_version_id = NULL,
            is_deleted = TRUE,
            current_revision_hash = NULL,
            last_source = EXCLUDED.last_source,
            remote_updated_at = NULL,
            last_checked_at = NOW(),
            updated_at = NOW()
        RETURNING *
        """,
        (str(page_id), str(space_id), source),
    )
    return _map_page_head(cur.fetchone())


def _map_page_head(row: dict) -> PageHeadRecord:
    return PageHeadRecord(
        page_id=UUID(str(row["page_id"])),
        space_id=UUID(str(row["space_id"])),
        current_version_id=UUID(str(row["current_version_id"])) if row.get("current_version_id") else None,
        current_revision_hash=row.get("current_revision_hash"),
        title=row.get("title"),
        content=row.get("content") or "",
        slug_id=row.get("slug_id"),
        parent_page_id=UUID(str(row["parent_page_id"])) if row.get("parent_page_id") else None,
        remote_updated_at=row.get("remote_updated_at"),
        is_deleted=bool(row.get("is_deleted")),
        last_source=row["last_source"],
        last_checked_at=row["last_checked_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
