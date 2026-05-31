from __future__ import annotations

from uuid import UUID, uuid4

from app.bridge.schemas.state import LocalPageSnapshotRecord


def create_snapshot(
    cur,
    *,
    page_id: UUID,
    space_id: UUID,
    content: str,
    base_revision_hash: str | None,
    local_path: str | None,
) -> LocalPageSnapshotRecord:
    snapshot_id = uuid4()
    cur.execute(
        """
        INSERT INTO local_page_snapshots (
            id, page_id, space_id, local_path, content,
            base_revision_hash, snapshotted_at, status, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, NOW(), 'active', NOW())
        RETURNING *
        """,
        (
            str(snapshot_id),
            str(page_id),
            str(space_id),
            local_path,
            content,
            base_revision_hash,
        ),
    )
    return _map_snapshot(cur.fetchone())


def get_snapshot(
    cur,
    *,
    page_id: UUID,
    snapshot_id: UUID,
) -> LocalPageSnapshotRecord | None:
    cur.execute(
        """
        SELECT * FROM local_page_snapshots
        WHERE id = %s AND page_id = %s
        LIMIT 1
        """,
        (str(snapshot_id), str(page_id)),
    )
    row = cur.fetchone()
    return _map_snapshot(row) if row else None


def delete_snapshot(
    cur,
    *,
    page_id: UUID,
    snapshot_id: UUID,
) -> bool:
    cur.execute(
        """
        DELETE FROM local_page_snapshots
        WHERE id = %s AND page_id = %s
        """,
        (str(snapshot_id), str(page_id)),
    )
    return cur.rowcount > 0


def _map_snapshot(row: dict) -> LocalPageSnapshotRecord:
    return LocalPageSnapshotRecord(
        id=UUID(str(row["id"])),
        page_id=UUID(str(row["page_id"])),
        space_id=UUID(str(row["space_id"])),
        local_path=row.get("local_path"),
        content=row["content"],
        base_revision_hash=row.get("base_revision_hash"),
        snapshotted_at=row["snapshotted_at"],
        status=row["status"],
        created_at=row["created_at"],
    )
