from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.bridge.schemas.state import ObserverCheckpointRecord


def get_observer_checkpoint(cur, page_id: UUID) -> ObserverCheckpointRecord | None:
    cur.execute(
        """
        SELECT *
        FROM observer_checkpoints
        WHERE page_id = %s
        LIMIT 1
        """,
        (str(page_id),),
    )
    row = cur.fetchone()
    return _map_observer_checkpoint(row) if row else None


def upsert_observer_checkpoint(
    cur,
    *,
    page_id: UUID,
    space_id: UUID,
    last_seen_remote_updated_at: datetime | None,
    last_observed_revision_hash: str | None,
) -> ObserverCheckpointRecord:
    cur.execute(
        """
        INSERT INTO observer_checkpoints (
            page_id,
            space_id,
            last_seen_remote_updated_at,
            last_observed_revision_hash,
            last_checked_at,
            updated_at
        )
        VALUES (
            %s, %s, %s, %s, NOW(), NOW()
        )
        ON CONFLICT (page_id)
        DO UPDATE SET
            space_id = EXCLUDED.space_id,
            last_seen_remote_updated_at = EXCLUDED.last_seen_remote_updated_at,
            last_observed_revision_hash = EXCLUDED.last_observed_revision_hash,
            last_checked_at = NOW(),
            updated_at = NOW()
        RETURNING *
        """,
        (
            str(page_id),
            str(space_id),
            last_seen_remote_updated_at,
            last_observed_revision_hash,
        ),
    )
    return _map_observer_checkpoint(cur.fetchone())


def _map_observer_checkpoint(row: dict) -> ObserverCheckpointRecord:
    return ObserverCheckpointRecord(
        page_id=UUID(str(row["page_id"])),
        space_id=UUID(str(row["space_id"])),
        last_seen_remote_updated_at=row.get("last_seen_remote_updated_at"),
        last_observed_revision_hash=row.get("last_observed_revision_hash"),
        last_checked_at=row["last_checked_at"],
        updated_at=row["updated_at"],
    )
