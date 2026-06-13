"""Standalone auto-sync conflict awareness store.

This surface is deliberately separate from the reconcile/write/observe pipeline. It only records
conflicts/deletions the background auto-sync detected (so the /health MCP tool can make the model
aware of them) and lets the model clear them. The server never auto-clears: clearing is a model
action only (resolve route / confirm-deletion / health_resolve), because the server can never know
the live local state with certainty and must never force or overwrite without model inclusion.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.auto_conflict.schemas import (
    AutoConflictListOut,
    AutoConflictOut,
    AutoConflictPostIn,
    AutoConflictPostOut,
    AutoConflictResolveOut,
)
from app.bridge.db.connection import get_conn
from app.bridge.db.schema import ensure_schema
from app.bridge.repositories.auto_sync_conflicts import (
    clear_auto_conflict,
    list_auto_conflicts,
    upsert_auto_conflict,
)

router = APIRouter(tags=["auto-conflict"])


def _map(row: dict) -> AutoConflictOut:
    return AutoConflictOut(
        space_id=row["space_id"],
        page_id=row["page_id"],
        kind=row.get("kind") or "conflict",
        reason=row.get("reason"),
        title=row.get("title"),
        local_path=row.get("local_path"),
        base_revision_hash=row.get("base_revision_hash"),
        base_version_id=row.get("base_version_id"),
        local_version=row.get("local_version"),
        remote_version=row.get("remote_version"),
        detected_at=row.get("detected_at"),
        updated_at=row.get("updated_at"),
    )


@router.post(
    "/spaces/{space_id}/auto-conflicts",
    response_model=AutoConflictPostOut,
    summary="Store/refresh auto-sync-detected conflicts for a space (helper -> server)",
)
def post_auto_conflicts(space_id: UUID, body: AutoConflictPostIn) -> AutoConflictPostOut:
    try:
        ensure_schema()
        with get_conn() as conn:
            with conn.cursor() as cur:
                for item in body.conflicts:
                    upsert_auto_conflict(
                        cur,
                        space_id=space_id,
                        page_id=item.page_id,
                        kind=item.kind,
                        reason=item.reason,
                        title=item.title,
                        local_path=item.local_path,
                        base_revision_hash=item.base_revision_hash,
                        base_version_id=item.base_version_id,
                        local_version=item.local_version,
                        remote_version=item.remote_version,
                    )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AutoConflictPostOut(space_id=space_id, stored=len(body.conflicts))


@router.get(
    "/auto-conflicts",
    response_model=AutoConflictListOut,
    summary="List pending auto-sync-detected conflicts across all spaces (for /health)",
)
def get_all_auto_conflicts() -> AutoConflictListOut:
    try:
        ensure_schema()
        with get_conn() as conn:
            with conn.cursor() as cur:
                rows = list_auto_conflicts(cur, None)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    items = [_map(row) for row in rows]
    return AutoConflictListOut(count=len(items), conflicts=items)


@router.get(
    "/spaces/{space_id}/auto-conflicts",
    response_model=AutoConflictListOut,
    summary="List pending auto-sync-detected conflicts for a space",
)
def get_space_auto_conflicts(space_id: UUID) -> AutoConflictListOut:
    try:
        ensure_schema()
        with get_conn() as conn:
            with conn.cursor() as cur:
                rows = list_auto_conflicts(cur, space_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    items = [_map(row) for row in rows]
    return AutoConflictListOut(count=len(items), conflicts=items)


@router.post(
    "/spaces/{space_id}/auto-conflicts/{page_id}/resolved",
    response_model=AutoConflictResolveOut,
    summary="Clear one auto-sync conflict entry (model-controlled only)",
)
def resolve_auto_conflict(space_id: UUID, page_id: UUID) -> AutoConflictResolveOut:
    try:
        ensure_schema()
        with get_conn() as conn:
            with conn.cursor() as cur:
                cleared = clear_auto_conflict(cur, space_id, page_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AutoConflictResolveOut(space_id=space_id, page_id=page_id, cleared=cleared)
