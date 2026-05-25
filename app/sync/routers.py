from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.models import (
    LocalReplicaPageCreateIn,
    LocalReplicaPageOut,
    SyncDiffIn,
    SyncSelectionIn,
    SyncStatusIn,
    SpaceSyncDiffOut,
    SpaceSyncStatusOut,
    SyncOperationOut,
)
from app.sync.service import create_local_replica_page, get_sync_diff, get_sync_status, pull_replica, push_replica

router = APIRouter(prefix="/spaces/{space_id}/sync", tags=["sync"])


@router.post(
    "/status",
    response_model=SpaceSyncStatusOut,
    summary="Get sync status for a space replica",
    description=(
        "Returns the current sync state for one Docmost space using the client-reported local page state "
        "supplied in the request body. The server compares that local state against live Docmost pages and "
        "returns page mappings, drift classification, and recommended next actions."
    ),
)
def sync_status(space_id: UUID, body: SyncStatusIn):
    try:
        return get_sync_status(space_id, body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/diff",
    response_model=SpaceSyncDiffOut,
    summary="Get sync diff for a space replica",
    description=(
        "Returns line-based client-local-vs-remote diff hunks for the selected page or for all unsynced pages "
        "using the client-reported local page state supplied in the request body. Use this before deciding how "
        "to resolve clashes."
    ),
)
def sync_diff(space_id: UUID, body: SyncDiffIn):
    try:
        return get_sync_diff(space_id, body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/local-pages",
    response_model=LocalReplicaPageOut,
    summary="Plan a new local-only page in a local replica",
    description=(
        "Returns the canonical client-local paths, page.md content, and `_meta.json` payload for a new local-only page "
        "inside the selected local replica. The client writes those files locally."
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
        "Compares the client-reported local page state to live Docmost pages and returns canonical remote snapshots "
        "for pages that should be materialized or refreshed locally. Set `force=true` to take the current remote page "
        "even when the client-local page diverged."
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
        "Pushes the client-reported local page state to remote Docmost when the sync status allows it, creates remote "
        "pages for local-only entries, and returns clashes when local and remote both changed. Set `force=true` to take "
        "the client-local page over the current remote Docmost page."
    ),
)
def push_sync(space_id: UUID, body: SyncSelectionIn):
    try:
        return push_replica(space_id, body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
