from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.bridge.db.connection import get_conn
from app.bridge.errors import BridgeConflictError, BridgeStateError
from app.bridge.repositories.page_heads import get_page_head
from app.bridge.services.write_pipeline import delete_page_via_bridge, update_page_via_bridge
from app.reconcile.schemas import (
    ConfirmDeletionIn,
    ConfirmDeletionOut,
    ReconcileIn,
    ReconcileOut,
    ResolveConflictIn,
    ResolveConflictOut,
)
from app.reconcile.service import reconcile

router = APIRouter(tags=["reconcile"])


@router.post(
    "/spaces/{space_id}/reconcile",
    response_model=ReconcileOut,
    summary="Classify + apply a scoped bidirectional reconcile; return the four buckets",
)
def reconcile_space(space_id: UUID, body: ReconcileIn) -> ReconcileOut:
    try:
        return reconcile(space_id, body)
    except BridgeStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/spaces/{space_id}/pages/{page_id}/resolve",
    response_model=ResolveConflictOut,
    summary="Resolve a conflict by pushing merged_content aligned to the current remote head",
)
def resolve_conflict_route(space_id: UUID, page_id: UUID, body: ResolveConflictIn) -> ResolveConflictOut:
    with get_conn() as conn:
        with conn.cursor() as cur:
            head = get_page_head(cur, page_id)
    if head is None or head.current_revision_hash is None:
        raise HTTPException(status_code=404, detail="No current bridge head for this page.")
    try:
        res = update_page_via_bridge(
            page_id=page_id,
            title=body.title,
            content=body.merged_content,
            operation="replace",
            caller_mode="auto_sync",
            expected_base_revision_hash=head.current_revision_hash,
            expected_space_id=space_id,
        )
    except BridgeConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ResolveConflictOut(
        page_id=page_id,
        resolved=True,
        base_revision_hash=res.base_revision_hash,
        base_version_id=res.base_version_id,
        title=res.title,
        content=res.content,
    )


@router.post(
    "/spaces/{space_id}/pages/{page_id}/confirm-deletion",
    response_model=ConfirmDeletionOut,
    summary="Apply a confirmed deletion in the given direction",
)
def confirm_deletion_route(space_id: UUID, page_id: UUID, body: ConfirmDeletionIn) -> ConfirmDeletionOut:
    if body.direction == "remote":
        try:
            delete_page_via_bridge(page_id=page_id, caller_mode="auto_sync", expected_space_id=space_id)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return ConfirmDeletionOut(page_id=page_id, direction="remote", remote_deleted=True)
    # direction == "local": accept a remote deletion; the helper drops the local copy.
    return ConfirmDeletionOut(page_id=page_id, direction="local", remote_deleted=False)
