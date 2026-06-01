from __future__ import annotations

from uuid import UUID, uuid4

from app.bridge.schemas.operations import BridgePageSnapshot
from app.bridge.schemas.state import PageVersionRecord


def upsert_page_version(cur, snapshot: BridgePageSnapshot, *, source: str, write_intent_id: UUID | None = None) -> PageVersionRecord:
    cur.execute(
        """
        INSERT INTO page_versions (
            id,
            page_id,
            space_id,
            revision_hash,
            title,
            content,
            slug_id,
            parent_page_id,
            source,
            source_write_intent_id,
            remote_updated_at,
            position,
            icon,
            observed_at,
            created_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
        )
        ON CONFLICT (page_id, revision_hash)
        DO UPDATE SET
            title = EXCLUDED.title,
            content = EXCLUDED.content,
            slug_id = COALESCE(EXCLUDED.slug_id, page_versions.slug_id),
            parent_page_id = COALESCE(EXCLUDED.parent_page_id, page_versions.parent_page_id),
            source = EXCLUDED.source,
            source_write_intent_id = COALESCE(EXCLUDED.source_write_intent_id, page_versions.source_write_intent_id),
            remote_updated_at = COALESCE(EXCLUDED.remote_updated_at, page_versions.remote_updated_at),
            position = COALESCE(EXCLUDED.position, page_versions.position),
            icon = COALESCE(EXCLUDED.icon, page_versions.icon),
            observed_at = NOW()
        RETURNING *
        """,
        (
            str(uuid4()),
            str(snapshot.page_id),
            str(snapshot.space_id),
            snapshot.revision_hash,
            snapshot.title,
            snapshot.content,
            snapshot.slug_id,
            str(snapshot.parent_page_id) if snapshot.parent_page_id else None,
            source,
            str(write_intent_id) if write_intent_id else None,
            snapshot.remote_updated_at,
            snapshot.position,
            snapshot.icon,
        ),
    )
    return _map_page_version(cur.fetchone())


def _map_page_version(row: dict) -> PageVersionRecord:
    return PageVersionRecord(
        id=UUID(str(row["id"])),
        page_id=UUID(str(row["page_id"])),
        space_id=UUID(str(row["space_id"])),
        revision_hash=row["revision_hash"],
        title=row.get("title"),
        content=row.get("content") or "",
        slug_id=row.get("slug_id"),
        parent_page_id=UUID(str(row["parent_page_id"])) if row.get("parent_page_id") else None,
        source=row["source"],
        source_write_intent_id=UUID(str(row["source_write_intent_id"])) if row.get("source_write_intent_id") else None,
        remote_updated_at=row.get("remote_updated_at"),
        position=row.get("position"),
        icon=row.get("icon"),
        observed_at=row["observed_at"],
        created_at=row["created_at"],
    )
