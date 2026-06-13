from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.bridge.errors import BridgeConflictError
from app.bridge.services.observer import observe_space
from app.bridge.services.write_pipeline import create_page_via_bridge, update_page_via_bridge
from app.schemas.auto_mcp import (
    AutoObserveIn,
    AutoObserveOut,
    AutoPageWriteBatchIn,
    AutoPageWriteBatchOut,
    AutoPageWriteResultOut,
)

router = APIRouter(prefix="/auto-mcp/spaces/{space_id}", tags=["auto-mcp"])


@router.post(
    "/pages/apply",
    response_model=AutoPageWriteBatchOut,
    summary="Apply helper-supplied page operations through the bridge pipeline",
)
def apply_page_operations(space_id: UUID, body: AutoPageWriteBatchIn) -> AutoPageWriteBatchOut:
    results: list[AutoPageWriteResultOut] = []
    applied_count = 0
    drifted_count = 0

    for page in body.pages:
        try:
            if page.page_id is None:
                result = create_page_via_bridge(
                    space_id=space_id,
                    title=page.title,
                    content=page.content,
                    parent_page_id=page.parent_page_id,
                    caller_mode="auto_sync",
                    expected_base_revision_hash=page.base_revision_hash,
                    force=page.force,
                )
            else:
                result = update_page_via_bridge(
                    page_id=page.page_id,
                    title=page.title,
                    content=page.content,
                    operation=page.operation,
                    caller_mode="auto_sync",
                    expected_base_revision_hash=page.base_revision_hash,
                    force=page.force,
                    expected_space_id=space_id,
                )
            applied_count += 1
            results.append(
                AutoPageWriteResultOut(
                    page_id=result.page_id,
                    title=result.title,
                    slug_id=result.slug_id,
                    parent_page_id=result.parent_page_id,
                    local_path=page.local_path,
                    action=result.action,
                    applied=True,
                    message="Bridge write applied.",
                    base_revision_hash=result.base_revision_hash,
                    base_version_id=result.base_version_id,
                    content=result.content,
                )
            )
        except BridgeConflictError as exc:
            drifted_count += 1
            results.append(
                AutoPageWriteResultOut(
                    page_id=page.page_id,
                    title=page.title,
                    parent_page_id=page.parent_page_id,
                    local_path=page.local_path,
                    action="drifted",
                    applied=False,
                    message=str(exc),
                    base_revision_hash=page.base_revision_hash,
                )
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return AutoPageWriteBatchOut(
        applied_count=applied_count,
        drifted_count=drifted_count,
        results=results,
    )


@router.post(
    "/observe",
    response_model=AutoObserveOut,
    summary="Run one observer pass for the selected space",
)
def observe_space_changes(space_id: UUID, body: AutoObserveIn | None = None) -> AutoObserveOut:
    force_rerender = bool(body.force_rerender) if body else False
    try:
        result = observe_space(space_id, force_rerender=force_rerender)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AutoObserveOut(
        space_id=result.space_id,
        checked_pages=result.checked_pages,
        bridge_writes_confirmed=result.bridge_writes_confirmed,
        external_updates_recorded=result.external_updates_recorded,
        external_deletions_recorded=result.external_deletions_recorded,
        reanchored_count=result.reanchored_count,
    )
