from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from app.bridge.schemas.state import PageHeadRecord
from app.bridge.repositories.write_intents import (
    list_stale_pending_write_intents_for_space,
    mark_write_intent_applied,
    mark_write_intent_orphaned,
)
from app.bridge.repositories.write_receipts import mark_write_receipts_confirmed_for_intent

STALE_INTENT_WINDOW = timedelta(minutes=10)


def reconcile_stale_pending_write_intents(
    cur,
    *,
    space_id: UUID,
    page_heads_by_id: dict[UUID, PageHeadRecord],
    matched_intent_ids: set[UUID],
) -> tuple[int, int]:
    applied_count = 0
    orphaned_count = 0

    for intent in list_stale_pending_write_intents_for_space(cur, space_id=space_id, stale_after=STALE_INTENT_WINDOW):
        if intent.id in matched_intent_ids:
            continue

        if intent.action == "update_page" and intent.page_id is not None:
            head = page_heads_by_id.get(intent.page_id)
            if head and head.current_revision_hash == intent.target_revision_hash:
                mark_write_intents_applied(cur, intent_id=intent.id, remote_page_id=intent.page_id)
                applied_count += 1
            elif head and head.current_revision_hash != intent.target_revision_hash:
                mark_write_intent_orphaned(
                    cur,
                    intent.id,
                    error_text="Pending bridge update did not match the current bridge head after the stale-intent window.",
                    remote_page_id=intent.page_id,
                )
                orphaned_count += 1
            continue

        if intent.action == "delete_page" and intent.page_id is not None:
            head = page_heads_by_id.get(intent.page_id)
            if head and head.is_deleted:
                mark_write_intents_applied(cur, intent_id=intent.id, remote_page_id=intent.page_id)
                applied_count += 1
            else:
                mark_write_intent_orphaned(
                    cur,
                    intent.id,
                    error_text="Pending bridge delete did not result in a deleted bridge head after the stale-intent window.",
                    remote_page_id=intent.page_id,
                )
                orphaned_count += 1
            continue

        if intent.action == "create_page":
            matching_head = next(
                (
                    head
                    for head in page_heads_by_id.values()
                    if not head.is_deleted
                    and head.current_revision_hash == intent.target_revision_hash
                    and (head.parent_page_id == intent.parent_page_id)
                    and ((head.title or "") == (intent.title or ""))
                ),
                None,
            )
            if matching_head is not None:
                mark_write_intents_applied(cur, intent_id=intent.id, remote_page_id=matching_head.page_id)
                applied_count += 1
            else:
                mark_write_intent_orphaned(
                    cur,
                    intent.id,
                    error_text="Pending bridge create did not appear in the current bridge heads after the stale-intent window.",
                )
                orphaned_count += 1

    return applied_count, orphaned_count


def mark_write_intents_applied(cur, *, intent_id: UUID, remote_page_id: UUID | None) -> None:
   mark_write_intent_applied(cur, intent_id, remote_page_id=remote_page_id)
   mark_write_receipts_confirmed_for_intent(cur, intent_id)
