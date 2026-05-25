from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.models import SpaceSyncDiffOut, SpaceSyncStatusOut, SyncOperationOut, SyncSelectionIn
from app.sync.service import get_sync_diff, get_sync_status, pull_replica, push_replica

router = APIRouter(prefix="/spaces/{space_id}/sync", tags=["sync"])


@router.get(
    "/status",
    response_model=SpaceSyncStatusOut,
    summary="Get sync status for a space replica",
    description=(
        "Returns the current server-side sync state for one Docmost space replica, including "
        "which local files are not in sync with remote Docmost, how each page is mapped, and "
        "which pages currently clash."
    ),
)
def sync_status(space_id: UUID, include_synced: bool = False):
    try:
        return get_sync_status(space_id, include_synced=include_synced)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get(
    "/diff",
    response_model=SpaceSyncDiffOut,
    summary="Get sync diff for a space replica",
    description=(
        "Returns line-based local-vs-remote diff hunks for the selected page or for all unsynced "
        "pages in the space replica. Use this before deciding how to resolve clashes."
    ),
)
def sync_diff(
    space_id: UUID,
    page_id: Optional[UUID] = None,
    local_path: Optional[str] = None,
    include_synced: bool = False,
):
    try:
        return get_sync_diff(space_id, page_id=page_id, local_path=local_path, include_synced=include_synced)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/pull",
    response_model=SyncOperationOut,
    summary="Pull remote Docmost changes into the server-side replica",
    description=(
        "Materializes missing remote pages locally, refreshes local files when remote is ahead, "
        "and returns all clashes when local and remote both changed. Set `force=true` to take "
        "remote content when conflicts exist."
    ),
)
def pull_sync(space_id: UUID, body: SyncSelectionIn):
    try:
        return pull_replica(space_id, body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/push",
    response_model=SyncOperationOut,
    summary="Push server-side replica changes to remote Docmost",
    description=(
        "Pushes local replica changes to remote Docmost, creates remote pages for local-only "
        "replica entries, and returns all clashes when local and remote both changed. Set "
        "`force=true` to take local content when conflicts exist."
    ),
)
def push_sync(space_id: UUID, body: SyncSelectionIn):
    try:
        return push_replica(space_id, body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
