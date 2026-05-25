from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.models import (
    LocalReplicaPageCreateIn,
    LocalReplicaPageOut,
    SpaceSyncDiffOut,
    SpaceSyncStatusOut,
    SyncOperationOut,
    SyncSelectionIn,
)
from app.sync.service import create_local_replica_page, get_sync_diff, get_sync_status, pull_replica, push_replica

router = APIRouter(prefix="/spaces/{space_id}/sync", tags=["sync"])


@router.get(
    "/status",
    response_model=SpaceSyncStatusOut,
    summary="Get sync status for a space replica",
    description=(
        "Returns the current sync state for one Docmost space replica, including "
        "which local files are not in sync with remote Docmost, how each page is mapped, and "
        "which pages currently clash. Pass local_root to inspect a specific local working copy."
    ),
)
def sync_status(space_id: UUID, include_synced: bool = False, local_root: Optional[str] = None):
    try:
        return get_sync_status(space_id, include_synced=include_synced, local_root=local_root)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get(
    "/diff",
    response_model=SpaceSyncDiffOut,
    summary="Get sync diff for a space replica",
    description=(
        "Returns line-based local-vs-remote diff hunks for the selected page or for all unsynced "
        "pages in the space replica. Use this before deciding how to resolve clashes. "
        "Pass local_root or an explicit local_path inside the target working copy when needed."
    ),
)
def sync_diff(
    space_id: UUID,
    page_id: Optional[UUID] = None,
    local_path: Optional[str] = None,
    include_synced: bool = False,
    local_root: Optional[str] = None,
):
    try:
        return get_sync_diff(space_id, page_id=page_id, local_path=local_path, include_synced=include_synced, local_root=local_root)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/local-pages",
    response_model=LocalReplicaPageOut,
    summary="Scaffold a new local-only page in a local replica",
    description=(
        "Creates a canonical local-only page directory, page.md, and _meta.json inside the selected local working copy "
        "so local-first documentation work can begin before any remote Docmost page exists."
    ),
)
def create_local_sync_page(space_id: UUID, body: LocalReplicaPageCreateIn):
    try:
        return create_local_replica_page(space_id, body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/pull",
    response_model=SyncOperationOut,
    summary="Pull remote Docmost changes into a local replica",
    description=(
        "Materializes missing remote pages locally, refreshes local files when remote is ahead, "
        "and returns all clashes when local and remote both changed. Set `force=true` to take "
        "remote content when conflicts exist. Use local_root to target a specific working copy."
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
    summary="Push local replica changes to remote Docmost",
    description=(
        "Pushes local replica changes to remote Docmost, creates remote pages for local-only "
        "replica entries, and returns all clashes when local and remote both changed. Set "
        "`force=true` to take local content when conflicts exist. Use local_root to target a specific working copy."
    ),
)
def push_sync(space_id: UUID, body: SyncSelectionIn):
    try:
        return push_replica(space_id, body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
