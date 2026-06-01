from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.bridge.db.connection import get_conn
from app.bridge.errors import BridgeConflictError, BridgeStateError
from app.bridge.repositories.observer_checkpoints import upsert_observer_checkpoint
from app.bridge.repositories.page_heads import get_page_head, list_page_heads_for_space, mark_page_deleted, upsert_page_head
from app.bridge.repositories.page_versions import upsert_page_version
from app.bridge.repositories.write_intents import (
    create_write_intent,
    list_pending_write_intents_for_space,
    mark_write_intent_applied,
    mark_write_intent_failed,
    mark_write_intent_orphaned,
)
from app.bridge.repositories.write_receipts import (
    create_write_receipt,
    expire_write_receipts_for_space,
    expire_write_receipts_for_intent,
    mark_write_receipts_confirmed_for_intent,
    mark_write_receipt_confirmed,
)
from app.bridge.schemas.operations import BridgeWriteResult
from app.bridge.services.bootstrap import ensure_space_bootstrapped
from app.bridge.services.normalization import apply_content_operation, canonicalize_title
from app.bridge.services.versioning import assert_head_alignment, snapshot_from_page
from app.query.prosemirror import prosemirror_to_markdown
from app.write.docmost import create_page as create_remote_page
from app.write.docmost import delete_page as delete_remote_page
from app.write.docmost import get_page_info
from app.write.docmost import move_page as move_remote
from app.write.docmost import update_page as update_remote_page


@dataclass(frozen=True)
class RemotePageContext:
    page_id: UUID
    space_id: UUID
    title: str | None
    slug_id: str | None
    parent_page_id: UUID | None
    content: str
    position: str | None
    icon: str | None
    updated_at: Any
    raw_page: dict[str, Any]


def create_page_via_bridge(
    *,
    space_id: UUID,
    title: str | None,
    content: str | None,
    parent_page_id: UUID | None,
    caller_mode: str,
    expected_base_revision_hash: str | None = None,
    force: bool = False,
) -> BridgeWriteResult:
    del expected_base_revision_hash, force
    ensure_space_bootstrapped(space_id)

    snapshot = snapshot_from_page(
        page_id=UUID(int=0),
        space_id=space_id,
        title=title,
        slug_id=None,
        parent_page_id=parent_page_id,
        content=content,
        remote_updated_at=None,
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            intent = create_write_intent(
                cur,
                page_id=None,
                space_id=space_id,
                action="create_page",
                caller_mode=caller_mode,
                expected_base_revision_hash=None,
                target_revision_hash=snapshot.revision_hash,
                title=snapshot.title,
                content=snapshot.content,
                parent_page_id=parent_page_id,
                operation="replace",
            )

    remote_response: dict[str, Any] | None = None
    remote_page_id: UUID | None = None
    try:
        remote_response = create_remote_page(
            space_id=str(space_id),
            title=snapshot.title,
            content=snapshot.content,
            parent_page_id=str(parent_page_id) if parent_page_id else None,
        )
        remote_page = remote_response.get("page", remote_response)
        remote_page_id = UUID(str(remote_page["id"]))
        finalized_snapshot = snapshot_from_page(
            page_id=remote_page_id,
            space_id=space_id,
            title=remote_page.get("title") or snapshot.title,
            slug_id=remote_page.get("slugId") or remote_page.get("slug_id"),
            parent_page_id=_coerce_uuid(remote_page.get("parentPageId") or remote_page.get("parent_page_id")) or parent_page_id,
            content=snapshot.content,
            remote_updated_at=remote_page.get("updatedAt") or remote_page.get("updated_at"),
        )
        return _finalize_write(
            intent_id=intent.id,
            snapshot=finalized_snapshot,
            action="created_remote",
            caller_mode=caller_mode,
            remote_page=remote_page,
            receipt_id=None,
            rollback_remote=None,
        )
    except Exception as exc:
        _mark_intent_failed(intent.id, error_text=str(exc), remote_page_id=remote_page_id)
        raise


def update_page_via_bridge(
    *,
    page_id: UUID,
    title: str | None,
    content: str | None,
    operation: str,
    caller_mode: str,
    expected_base_revision_hash: str | None = None,
    force: bool = False,
    expected_space_id: UUID | None = None,
) -> BridgeWriteResult:
    remote_before = fetch_remote_page_context(page_id)
    if expected_space_id and remote_before.space_id != expected_space_id:
        raise BridgeStateError("Page does not belong to the requested space.")
    ensure_space_bootstrapped(remote_before.space_id)

    with get_conn() as conn:
        with conn.cursor() as cur:
            current_head = get_page_head(cur, page_id)
            assert_head_alignment(
                current_head,
                expected_base_revision_hash=expected_base_revision_hash,
                require_alignment=caller_mode != "crud",
                force=force,
            )

            resolved_title = remote_before.title if title is None else canonicalize_title(title) or None
            resolved_content = remote_before.content if content is None else apply_content_operation(
                remote_before.content,
                content,
                operation,
            )
            target_snapshot = snapshot_from_page(
                page_id=page_id,
                space_id=remote_before.space_id,
                title=resolved_title,
                slug_id=remote_before.slug_id,
                parent_page_id=remote_before.parent_page_id,
                content=resolved_content,
                remote_updated_at=remote_before.updated_at,
            )
            if current_head is not None and current_head.current_revision_hash == target_snapshot.revision_hash:
                return BridgeWriteResult(
                    page_id=page_id,
                    space_id=remote_before.space_id,
                    title=target_snapshot.title,
                    slug_id=remote_before.slug_id,
                    parent_page_id=remote_before.parent_page_id,
                    content=target_snapshot.content,
                    base_revision_hash=target_snapshot.revision_hash,
                    remote_updated_at=remote_before.updated_at,
                    action="unchanged",
                    caller_mode=caller_mode,
                    write_intent_id=UUID(int=0),
                    remote_page=remote_before.raw_page,
                )
            intent = create_write_intent(
                cur,
                page_id=page_id,
                space_id=remote_before.space_id,
                action="update_page",
                caller_mode=caller_mode,
                expected_base_revision_hash=expected_base_revision_hash,
                target_revision_hash=target_snapshot.revision_hash,
                title=target_snapshot.title,
                content=target_snapshot.content,
                parent_page_id=target_snapshot.parent_page_id,
                operation=operation,
            )
            receipt = create_write_receipt(
                cur,
                write_intent_id=intent.id,
                page_id=page_id,
                space_id=remote_before.space_id,
                expected_revision_hash=target_snapshot.revision_hash,
            )

    remote_response: dict[str, Any] | None = None
    try:
        remote_response = update_remote_page(
            page_id=str(page_id),
            title=resolved_title,
            content=resolved_content if content is not None else None,
            operation="replace",
        )
        remote_page = remote_response.get("page", remote_response)
        finalized_snapshot = snapshot_from_page(
            page_id=page_id,
            space_id=remote_before.space_id,
            title=remote_page.get("title") or target_snapshot.title,
            slug_id=remote_page.get("slugId") or remote_page.get("slug_id") or remote_before.slug_id,
            parent_page_id=_coerce_uuid(remote_page.get("parentPageId") or remote_page.get("parent_page_id")) or remote_before.parent_page_id,
            content=target_snapshot.content,
            remote_updated_at=remote_page.get("updatedAt") or remote_page.get("updated_at"),
        )
        return _finalize_write(
            intent_id=intent.id,
            snapshot=finalized_snapshot,
            action="updated_remote",
            caller_mode=caller_mode,
            remote_page=remote_page,
            receipt_id=receipt.id,
            rollback_remote=remote_before,
        )
    except Exception as exc:
        _mark_intent_failed(intent.id, error_text=str(exc), remote_page_id=page_id)
        raise


def move_page_via_bridge(
    *,
    page_id: UUID,
    position: str,
    parent_page_id: UUID | None,
    caller_mode: str,
    expected_space_id: UUID | None = None,
) -> BridgeWriteResult:
    remote_before = fetch_remote_page_context(page_id)
    if expected_space_id and remote_before.space_id != expected_space_id:
        raise BridgeStateError("Page does not belong to the requested space.")
    ensure_space_bootstrapped(remote_before.space_id)

    target_parent = parent_page_id if parent_page_id is not None else remote_before.parent_page_id
    target_snapshot = snapshot_from_page(
        page_id=page_id,
        space_id=remote_before.space_id,
        title=remote_before.title,
        slug_id=remote_before.slug_id,
        parent_page_id=target_parent,
        content=remote_before.content,
        remote_updated_at=remote_before.updated_at,
        position=position,
        icon=remote_before.icon,
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            intent = create_write_intent(
                cur,
                page_id=page_id,
                space_id=remote_before.space_id,
                action="move_page",
                caller_mode=caller_mode,
                expected_base_revision_hash=None,
                target_revision_hash=target_snapshot.revision_hash,
                title=target_snapshot.title,
                content=target_snapshot.content,
                parent_page_id=target_parent,
                operation=None,
            )

    try:
        remote_response = move_remote(
            page_id=str(page_id),
            position=position,
            parent_page_id=str(parent_page_id) if parent_page_id else None,
        )
        remote_page = remote_response.get("page", remote_response) if isinstance(remote_response, dict) else {}
        if not isinstance(remote_page, dict):
            remote_page = {}
        new_parent = _coerce_uuid(remote_page.get("parentPageId") or remote_page.get("parent_page_id")) or target_parent
        new_position = remote_page.get("position") or position
        finalized_snapshot = snapshot_from_page(
            page_id=page_id,
            space_id=remote_before.space_id,
            title=remote_before.title,
            slug_id=remote_before.slug_id,
            parent_page_id=new_parent,
            content=remote_before.content,
            remote_updated_at=remote_page.get("updatedAt") or remote_page.get("updated_at") or remote_before.updated_at,
            position=new_position,
            icon=remote_before.icon,
        )
        return _finalize_write(
            intent_id=intent.id,
            snapshot=finalized_snapshot,
            action="moved_remote",
            caller_mode=caller_mode,
            remote_page=remote_page,
            receipt_id=None,
            rollback_remote=None,
        )
    except Exception as exc:
        _mark_intent_failed(intent.id, error_text=str(exc), remote_page_id=page_id)
        raise


def delete_space_via_bridge(*, space_id: UUID, caller_mode: str) -> None:
    from app.write.docmost import delete_space as delete_remote_space

    ensure_space_bootstrapped(space_id)

    with get_conn() as conn:
        with conn.cursor() as cur:
            intent = create_write_intent(
                cur,
                page_id=None,
                space_id=space_id,
                action="delete_space",
                caller_mode=caller_mode,
                expected_base_revision_hash=None,
                target_revision_hash=None,
                title=None,
                content=None,
                parent_page_id=None,
                operation=None,
            )
            known_heads = list_page_heads_for_space(cur, space_id)

    try:
        delete_remote_space(str(space_id))
        with get_conn() as conn:
            with conn.cursor() as cur:
                for head in known_heads:
                    mark_page_deleted(cur, head.page_id, space_id, source="bridge_write")
                    upsert_observer_checkpoint(
                        cur,
                        page_id=head.page_id,
                        space_id=space_id,
                        last_seen_remote_updated_at=None,
                        last_observed_revision_hash=None,
                    )
                expire_write_receipts_for_space(cur, space_id)
                for pending_intent in list_pending_write_intents_for_space(cur, space_id):
                    if pending_intent.id == intent.id:
                        continue
                    mark_write_intent_orphaned(
                        cur,
                        pending_intent.id,
                        error_text="Bridge space delete superseded this pending page-level intent.",
                        remote_page_id=pending_intent.page_id,
                    )
                mark_write_intent_applied(cur, intent.id, remote_page_id=None)
                mark_write_receipts_confirmed_for_intent(cur, intent.id)
    except Exception as exc:
        _mark_intent_failed(intent.id, error_text=str(exc), remote_page_id=None)
        raise


def delete_page_via_bridge(*, page_id: UUID, caller_mode: str, expected_space_id: UUID | None = None) -> None:
    remote_before = fetch_remote_page_context(page_id)
    if expected_space_id and remote_before.space_id != expected_space_id:
        raise BridgeStateError("Page does not belong to the requested space.")
    ensure_space_bootstrapped(remote_before.space_id)

    with get_conn() as conn:
        with conn.cursor() as cur:
            intent = create_write_intent(
                cur,
                page_id=page_id,
                space_id=remote_before.space_id,
                action="delete_page",
                caller_mode=caller_mode,
                expected_base_revision_hash=None,
                target_revision_hash=None,
                title=remote_before.title,
                content=remote_before.content,
                parent_page_id=remote_before.parent_page_id,
                operation=None,
            )

    try:
        delete_remote_page(str(page_id))
        with get_conn() as conn:
            with conn.cursor() as cur:
                mark_page_deleted(cur, page_id, remote_before.space_id, source="bridge_write")
                upsert_observer_checkpoint(
                    cur,
                    page_id=page_id,
                    space_id=remote_before.space_id,
                    last_seen_remote_updated_at=None,
                    last_observed_revision_hash=None,
                )
                mark_write_intent_applied(cur, intent.id, remote_page_id=page_id)
    except Exception as exc:
        _mark_intent_failed(intent.id, error_text=str(exc), remote_page_id=page_id)
        raise


def fetch_remote_page_context(page_id: UUID) -> RemotePageContext:
    data = get_page_info(str(page_id))
    page = data.get("page", data)
    raw_content = page.get("content")
    if isinstance(raw_content, dict):
        content = prosemirror_to_markdown(raw_content)
    else:
        content = raw_content or ""

    return RemotePageContext(
        page_id=UUID(str(page["id"])),
        space_id=UUID(str(page.get("spaceId") or page.get("space_id"))),
        title=page.get("title"),
        slug_id=page.get("slugId") or page.get("slug_id"),
        parent_page_id=_coerce_uuid(page.get("parentPageId") or page.get("parent_page_id")),
        content=content,
        position=page.get("position"),
        icon=page.get("icon"),
        updated_at=page.get("updatedAt") or page.get("updated_at"),
        raw_page=page,
    )


def _finalize_write(
    *,
    intent_id: UUID,
    snapshot,
    action: str,
    caller_mode: str,
    remote_page: dict[str, Any],
    receipt_id: UUID | None,
    rollback_remote: RemotePageContext | None,
) -> BridgeWriteResult:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                version = upsert_page_version(cur, snapshot, source="bridge_write", write_intent_id=intent_id)
                upsert_page_head(cur, snapshot, version_id=version.id, source="bridge_write")
                upsert_observer_checkpoint(
                    cur,
                    page_id=snapshot.page_id,
                    space_id=snapshot.space_id,
                    last_seen_remote_updated_at=snapshot.remote_updated_at,
                    last_observed_revision_hash=snapshot.revision_hash,
                )
                mark_write_intent_applied(cur, intent_id, remote_page_id=snapshot.page_id)
                if receipt_id:
                    mark_write_receipt_confirmed(cur, receipt_id)
    except Exception as exc:
        rollback_error = _compensate_remote_write(snapshot=snapshot, action=action, rollback_remote=rollback_remote)
        error_text = f"Bridge finalization failed after remote write: {exc}"
        if rollback_error is not None:
            error_text = f"{error_text}. Rollback failed: {rollback_error}"
        _mark_intent_failed(intent_id, error_text=error_text, remote_page_id=snapshot.page_id)
        raise BridgeStateError(error_text) from exc

    return BridgeWriteResult(
        page_id=snapshot.page_id,
        space_id=snapshot.space_id,
        title=snapshot.title,
        slug_id=snapshot.slug_id,
        parent_page_id=snapshot.parent_page_id,
        content=snapshot.content,
        base_revision_hash=snapshot.revision_hash,
        remote_updated_at=snapshot.remote_updated_at,
        action=action,
        caller_mode=caller_mode,
        write_intent_id=intent_id,
        remote_page=remote_page,
    )


def _compensate_remote_write(*, snapshot, action: str, rollback_remote: RemotePageContext | None) -> str | None:
    try:
        if action == "created_remote":
            delete_remote_page(str(snapshot.page_id))
            return None
        if action == "updated_remote" and rollback_remote is not None:
            update_remote_page(
                page_id=str(snapshot.page_id),
                title=rollback_remote.title,
                content=rollback_remote.content,
                operation="replace",
            )
            return None
    except Exception as exc:  # compensation failures must be surfaced explicitly
        return str(exc)
    return None


def _mark_intent_failed(intent_id: UUID, *, error_text: str, remote_page_id: UUID | None) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            mark_write_intent_failed(cur, intent_id, error_text=error_text, remote_page_id=remote_page_id)
            expire_write_receipts_for_intent(cur, intent_id)


def _coerce_uuid(value) -> UUID | None:
    if not value:
        return None
    return UUID(str(value))
