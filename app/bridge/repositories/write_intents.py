from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

from app.bridge.schemas.state import WriteIntentRecord


def create_write_intent(
    cur,
    *,
    page_id: UUID | None,
    space_id: UUID,
    action: str,
    caller_mode: str,
    expected_base_revision_hash: str | None,
    target_revision_hash: str | None,
    title: str | None,
    content: str | None,
    parent_page_id: UUID | None,
    operation: str | None,
) -> WriteIntentRecord:
    cur.execute(
        """
        INSERT INTO write_intents (
            id,
            page_id,
            space_id,
            action,
            caller_mode,
            status,
            expected_base_revision_hash,
            target_revision_hash,
            title,
            content,
            parent_page_id,
            operation,
            error_text,
            remote_page_id,
            created_at,
            updated_at,
            applied_at,
            failed_at
        )
        VALUES (
            %s, %s, %s, %s, %s, 'pending', %s, %s, %s, %s, %s, %s, NULL, NULL, NOW(), NOW(), NULL, NULL
        )
        RETURNING *
        """,
        (
            str(uuid4()),
            str(page_id) if page_id else None,
            str(space_id),
            action,
            caller_mode,
            expected_base_revision_hash,
            target_revision_hash,
            title,
            content,
            str(parent_page_id) if parent_page_id else None,
            operation,
        ),
    )
    return _map_write_intent(cur.fetchone())


def mark_write_intent_applied(cur, intent_id: UUID, *, remote_page_id: UUID | None) -> WriteIntentRecord:
    cur.execute(
        """
        UPDATE write_intents
        SET status = 'applied',
            remote_page_id = %s,
            applied_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (str(remote_page_id) if remote_page_id else None, str(intent_id)),
    )
    return _map_write_intent(cur.fetchone())


def mark_write_intent_failed(cur, intent_id: UUID, *, error_text: str, remote_page_id: UUID | None = None) -> WriteIntentRecord:
    cur.execute(
        """
        UPDATE write_intents
        SET status = 'failed',
            error_text = %s,
            remote_page_id = COALESCE(%s, remote_page_id),
            failed_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (error_text, str(remote_page_id) if remote_page_id else None, str(intent_id)),
    )
    return _map_write_intent(cur.fetchone())


def find_pending_create_intent(cur, *, space_id: UUID, target_revision_hash: str) -> WriteIntentRecord | None:
    cur.execute(
        """
        SELECT *
        FROM write_intents
        WHERE space_id = %s
          AND action = 'create_page'
          AND status = 'pending'
          AND target_revision_hash = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (str(space_id), target_revision_hash),
    )
    row = cur.fetchone()
    return _map_write_intent(row) if row else None


def find_matching_pending_create_intent(
    cur,
    *,
    space_id: UUID,
    target_revision_hash: str,
    title: str | None,
    parent_page_id: UUID | None,
) -> WriteIntentRecord | None:
    cur.execute(
        """
        SELECT *
        FROM write_intents
        WHERE space_id = %s
          AND action = 'create_page'
          AND status = 'pending'
          AND target_revision_hash = %s
          AND COALESCE(title, '') = COALESCE(%s, '')
          AND parent_page_id IS NOT DISTINCT FROM %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (
            str(space_id),
            target_revision_hash,
            title,
            str(parent_page_id) if parent_page_id else None,
        ),
    )
    row = cur.fetchone()
    return _map_write_intent(row) if row else None


def find_matching_pending_page_intent(cur, *, page_id: UUID, target_revision_hash: str) -> WriteIntentRecord | None:
    cur.execute(
        """
        SELECT *
        FROM write_intents
        WHERE page_id = %s
          AND action = 'update_page'
          AND status = 'pending'
          AND target_revision_hash = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (str(page_id), target_revision_hash),
    )
    row = cur.fetchone()
    return _map_write_intent(row) if row else None


def find_pending_delete_intent(cur, *, page_id: UUID) -> WriteIntentRecord | None:
    cur.execute(
        """
        SELECT *
        FROM write_intents
        WHERE page_id = %s
          AND action = 'delete_page'
          AND status = 'pending'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (str(page_id),),
    )
    row = cur.fetchone()
    return _map_write_intent(row) if row else None


def list_pending_write_intents_for_space(cur, space_id: UUID) -> list[WriteIntentRecord]:
    cur.execute(
        """
        SELECT *
        FROM write_intents
        WHERE space_id = %s
          AND status = 'pending'
        ORDER BY created_at ASC
        """,
        (str(space_id),),
    )
    return [_map_write_intent(row) for row in cur.fetchall()]


def list_stale_pending_write_intents_for_space(
    cur,
    *,
    space_id: UUID,
    stale_after: timedelta,
) -> list[WriteIntentRecord]:
    cur.execute(
        """
        SELECT *
        FROM write_intents
        WHERE space_id = %s
          AND status = 'pending'
          AND created_at <= NOW() - %s::interval
        ORDER BY created_at ASC
        """,
        (str(space_id), _format_interval(stale_after)),
    )
    return [_map_write_intent(row) for row in cur.fetchall()]


def mark_write_intent_orphaned(cur, intent_id: UUID, *, error_text: str, remote_page_id: UUID | None = None) -> WriteIntentRecord:
    cur.execute(
        """
        UPDATE write_intents
        SET status = 'orphaned',
            error_text = %s,
            remote_page_id = COALESCE(%s, remote_page_id),
            updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (error_text, str(remote_page_id) if remote_page_id else None, str(intent_id)),
    )
    return _map_write_intent(cur.fetchone())


def has_pending_delete_intent(cur, *, page_id: UUID) -> bool:
    return find_pending_delete_intent(cur, page_id=page_id) is not None


def _format_interval(delta: timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    return f"{total_seconds} seconds"


def _map_write_intent(row: dict) -> WriteIntentRecord:
    return WriteIntentRecord(
        id=UUID(str(row["id"])),
        page_id=UUID(str(row["page_id"])) if row.get("page_id") else None,
        space_id=UUID(str(row["space_id"])),
        action=row["action"],
        caller_mode=row["caller_mode"],
        status=row["status"],
        expected_base_revision_hash=row.get("expected_base_revision_hash"),
        target_revision_hash=row.get("target_revision_hash"),
        title=row.get("title"),
        content=row.get("content"),
        parent_page_id=UUID(str(row["parent_page_id"])) if row.get("parent_page_id") else None,
        operation=row.get("operation"),
        error_text=row.get("error_text"),
        remote_page_id=UUID(str(row["remote_page_id"])) if row.get("remote_page_id") else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        applied_at=row.get("applied_at"),
        failed_at=row.get("failed_at"),
    )
