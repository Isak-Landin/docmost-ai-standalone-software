from __future__ import annotations

from uuid import UUID

from app.bridge.db.connection import get_conn
from app.bridge.repositories.observer_checkpoints import get_observer_checkpoint, upsert_observer_checkpoint
from app.bridge.repositories.page_heads import list_page_heads_for_space, mark_page_deleted, upsert_page_head
from app.bridge.repositories.page_versions import upsert_page_version
from app.bridge.repositories.write_intents import (
    find_matching_pending_create_intent,
    find_matching_pending_page_intent,
    find_pending_delete_intent,
)
from app.bridge.repositories.write_receipts import get_pending_write_receipt
from app.bridge.schemas.operations import ObserveSpaceResult
from app.bridge.services.bootstrap import ensure_space_bootstrapped
from app.bridge.services.reconciliation import mark_write_intents_applied, reconcile_stale_pending_write_intents
from app.bridge.services.versioning import snapshot_from_page
from app.query.docmost import get_page as fetch_page
from app.query.docmost import list_pages as fetch_pages


def observe_space(space_id: UUID) -> ObserveSpaceResult:
    ensure_space_bootstrapped(space_id)

    remote_pages = fetch_pages(space_id)
    remote_by_id = {page.id: page for page in remote_pages}

    checked_pages = 0
    bridge_writes_confirmed = 0
    external_updates_recorded = 0
    external_deletions_recorded = 0

    with get_conn() as conn:
        with conn.cursor() as cur:
            heads = {head.page_id: head for head in list_page_heads_for_space(cur, space_id)}
            matched_intent_ids: set[UUID] = set()

            for remote_page in remote_pages:
                checked_pages += 1
                checkpoint = get_observer_checkpoint(cur, remote_page.id)

                if checkpoint and checkpoint.last_seen_remote_updated_at and remote_page.updated_at and remote_page.updated_at <= checkpoint.last_seen_remote_updated_at:
                    continue

                full_page = fetch_page(space_id, remote_page.id)
                snapshot = snapshot_from_page(
                    page_id=full_page.id,
                    space_id=full_page.space_id,
                    title=full_page.title,
                    slug_id=full_page.slug_id,
                    parent_page_id=full_page.parent_page_id,
                    content=full_page.content,
                    remote_updated_at=full_page.updated_at,
                    position=full_page.position,
                    icon=full_page.icon,
                )
                current_head = heads.get(remote_page.id)

                receipt = get_pending_write_receipt(cur, page_id=remote_page.id, expected_revision_hash=snapshot.revision_hash)
                if receipt:
                    version = upsert_page_version(cur, snapshot, source="bridge_write", write_intent_id=receipt.write_intent_id)
                    upsert_observer_checkpoint(
                        cur,
                        page_id=snapshot.page_id,
                        space_id=snapshot.space_id,
                        last_seen_remote_updated_at=snapshot.remote_updated_at,
                        last_observed_revision_hash=snapshot.revision_hash,
                    )
                    mark_write_intents_applied(cur, intent_id=receipt.write_intent_id, remote_page_id=snapshot.page_id)
                    matched_intent_ids.add(receipt.write_intent_id)
                    heads[snapshot.page_id] = upsert_page_head(cur, snapshot, version_id=version.id, source="bridge_write")
                    bridge_writes_confirmed += 1
                    continue

                pending_update = find_matching_pending_page_intent(
                    cur,
                    page_id=snapshot.page_id,
                    target_revision_hash=snapshot.revision_hash,
                )
                if pending_update:
                    version = upsert_page_version(cur, snapshot, source="bridge_write", write_intent_id=pending_update.id)
                    heads[snapshot.page_id] = upsert_page_head(cur, snapshot, version_id=version.id, source="bridge_write")
                    upsert_observer_checkpoint(
                        cur,
                        page_id=snapshot.page_id,
                        space_id=snapshot.space_id,
                        last_seen_remote_updated_at=snapshot.remote_updated_at,
                        last_observed_revision_hash=snapshot.revision_hash,
                    )
                    mark_write_intents_applied(cur, intent_id=pending_update.id, remote_page_id=snapshot.page_id)
                    matched_intent_ids.add(pending_update.id)
                    bridge_writes_confirmed += 1
                    continue

                pending_create = current_head is None and find_matching_pending_create_intent(
                    cur,
                    space_id=space_id,
                    target_revision_hash=snapshot.revision_hash,
                    title=snapshot.title,
                    parent_page_id=snapshot.parent_page_id,
                )
                if pending_create:
                    version = upsert_page_version(cur, snapshot, source="bridge_write", write_intent_id=pending_create.id)
                    heads[snapshot.page_id] = upsert_page_head(cur, snapshot, version_id=version.id, source="bridge_write")
                    upsert_observer_checkpoint(
                        cur,
                        page_id=snapshot.page_id,
                        space_id=snapshot.space_id,
                        last_seen_remote_updated_at=snapshot.remote_updated_at,
                        last_observed_revision_hash=snapshot.revision_hash,
                    )
                    mark_write_intents_applied(cur, intent_id=pending_create.id, remote_page_id=snapshot.page_id)
                    matched_intent_ids.add(pending_create.id)
                    bridge_writes_confirmed += 1
                    continue

                if current_head and current_head.current_revision_hash == snapshot.revision_hash and not current_head.is_deleted:
                    upsert_observer_checkpoint(
                        cur,
                        page_id=snapshot.page_id,
                        space_id=snapshot.space_id,
                        last_seen_remote_updated_at=snapshot.remote_updated_at,
                        last_observed_revision_hash=snapshot.revision_hash,
                    )
                    heads[snapshot.page_id] = current_head
                    continue

                version = upsert_page_version(cur, snapshot, source="external_observer")
                heads[snapshot.page_id] = upsert_page_head(cur, snapshot, version_id=version.id, source="external_observer")
                upsert_observer_checkpoint(
                    cur,
                    page_id=snapshot.page_id,
                    space_id=snapshot.space_id,
                    last_seen_remote_updated_at=snapshot.remote_updated_at,
                    last_observed_revision_hash=snapshot.revision_hash,
                )
                external_updates_recorded += 1

            missing_remote_ids = [page_id for page_id, head in heads.items() if not head.is_deleted and page_id not in remote_by_id]
            for page_id in missing_remote_ids:
                pending_delete = find_pending_delete_intent(cur, page_id=page_id)
                if pending_delete:
                    heads[page_id] = mark_page_deleted(cur, page_id, space_id, source="bridge_write")
                    mark_write_intents_applied(cur, intent_id=pending_delete.id, remote_page_id=page_id)
                    matched_intent_ids.add(pending_delete.id)
                else:
                    heads[page_id] = mark_page_deleted(cur, page_id, space_id, source="external_observer")
                    external_deletions_recorded += 1
                upsert_observer_checkpoint(
                    cur,
                    page_id=page_id,
                    space_id=space_id,
                    last_seen_remote_updated_at=None,
                    last_observed_revision_hash=None,
                )

            reconcile_stale_pending_write_intents(
                cur,
                space_id=space_id,
                page_heads_by_id=heads,
                matched_intent_ids=matched_intent_ids,
            )

    return ObserveSpaceResult(
        space_id=space_id,
        checked_pages=checked_pages,
        bridge_writes_confirmed=bridge_writes_confirmed,
        external_updates_recorded=external_updates_recorded,
        external_deletions_recorded=external_deletions_recorded,
    )
