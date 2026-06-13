from __future__ import annotations

from uuid import UUID, uuid4


def upsert_auto_conflict(
    cur,
    *,
    space_id: UUID,
    page_id: UUID,
    kind: str,
    reason: str | None,
    title: str | None,
    local_path: str | None,
    base_revision_hash: str | None,
    base_version_id: UUID | None,
    local_version: str | None,
    remote_version: str | None,
) -> dict:
    """Insert or refresh one (space, page) conflict entry. Keyed UNIQUE(space_id, page_id) so a
    re-detected conflict refreshes in place rather than duplicating. Never removes other rows."""
    cur.execute(
        """
        INSERT INTO auto_sync_conflicts (
            id, space_id, page_id, kind, reason, title, local_path,
            base_revision_hash, base_version_id, local_version, remote_version,
            detected_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (space_id, page_id)
        DO UPDATE SET
            kind = EXCLUDED.kind,
            reason = EXCLUDED.reason,
            title = EXCLUDED.title,
            local_path = EXCLUDED.local_path,
            base_revision_hash = EXCLUDED.base_revision_hash,
            base_version_id = EXCLUDED.base_version_id,
            local_version = EXCLUDED.local_version,
            remote_version = EXCLUDED.remote_version,
            updated_at = NOW()
        RETURNING *
        """,
        (
            str(uuid4()),
            str(space_id),
            str(page_id),
            kind,
            reason,
            title,
            local_path,
            base_revision_hash,
            str(base_version_id) if base_version_id else None,
            local_version,
            remote_version,
        ),
    )
    return dict(cur.fetchone())


def list_auto_conflicts(cur, space_id: UUID | None = None) -> list[dict]:
    if space_id is not None:
        cur.execute(
            "SELECT * FROM auto_sync_conflicts WHERE space_id = %s ORDER BY updated_at DESC",
            (str(space_id),),
        )
    else:
        cur.execute("SELECT * FROM auto_sync_conflicts ORDER BY updated_at DESC")
    return [dict(row) for row in cur.fetchall()]


def clear_auto_conflict(cur, space_id: UUID, page_id: UUID) -> bool:
    cur.execute(
        "DELETE FROM auto_sync_conflicts WHERE space_id = %s AND page_id = %s",
        (str(space_id), str(page_id)),
    )
    return cur.rowcount > 0
