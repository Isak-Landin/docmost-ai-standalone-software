from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.bridge.db.connection import get_conn
from app.bridge.errors import BridgeConflictError, BridgeStateError
from app.bridge.repositories.page_heads import get_page_head
from app.bridge.services.bootstrap import ensure_space_bootstrapped
from app.bridge.repositories.snapshots import (
    create_snapshot as repo_create_snapshot,
    delete_snapshot as repo_delete_snapshot,
    get_snapshot as repo_get_snapshot,
)
from app.bridge.schemas.state import LocalPageSnapshotRecord
from app.bridge.services.write_pipeline import (
    create_page_via_bridge,
    delete_page_via_bridge,
    delete_space_via_bridge,
    move_page_via_bridge,
    update_page_via_bridge,
)
from app.helper_api.schemas import (
    HelperPageCreateIn,
    HelperPageMoveIn,
    HelperPageOut,
    HelperPageTreeNodeOut,
    HelperPageUpdateIn,
    HelperPageWriteOut,
    HelperSnapshotCreateIn,
    HelperSnapshotOut,
    HelperSpaceCreateIn,
    HelperSpaceOut,
    HelperSpaceTreeOut,
    HelperSpaceWriteOut,
)
from app.models import PageOut, PageTreeNode, SpaceOut, SpaceTreeOut
from app.query.db import DocmostConnectionError
from app.query.docmost import (
    PageNotFoundError,
    SpaceNotFoundError,
    get_page as fetch_page,
    get_space as fetch_space,
    get_space_tree as fetch_space_tree,
    list_pages as fetch_pages,
    list_spaces as fetch_spaces,
)
from app.write.docmost import create_space as docmost_create_space

router = APIRouter(tags=["helper-api"])


# ---------------------------------------------------------------------------
# Read routes
# ---------------------------------------------------------------------------

@router.get("/spaces", response_model=list[HelperSpaceOut], summary="List all spaces")
def list_spaces():
    try:
        spaces = fetch_spaces()
    except DocmostConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [_map_space(s) for s in spaces]


@router.get("/spaces/{space_id}", response_model=HelperSpaceOut, summary="Get a space")
def get_space(space_id: UUID):
    try:
        space = fetch_space(space_id)
    except DocmostConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SpaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _map_space(space)


@router.get("/spaces/{space_id}/tree", response_model=HelperSpaceTreeOut, summary="Get page tree")
def get_space_tree(space_id: UUID):
    try:
        tree = fetch_space_tree(space_id)
    except DocmostConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SpaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _map_tree(space_id, tree)


@router.get(
    "/spaces/{space_id}/pages",
    response_model=list[HelperPageOut],
    summary="List pages in a space",
)
def list_pages(space_id: UUID):
    try:
        pages = fetch_pages(space_id)
    except DocmostConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SpaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_map_page(p) for p in pages]


@router.get(
    "/spaces/{space_id}/pages/{page_id}",
    response_model=HelperPageOut,
    summary="Get a page with content and current revision hash",
)
def get_page(space_id: UUID, page_id: UUID):
    try:
        page = fetch_page(space_id, page_id)
    except DocmostConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (SpaceNotFoundError, PageNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    current_revision_hash: str | None = None
    current_version_id: UUID | None = None
    try:
        ensure_space_bootstrapped(space_id)
        with get_conn() as conn:
            with conn.cursor() as cur:
                head = get_page_head(cur, page_id)
                if head:
                    current_revision_hash = head.current_revision_hash
                    current_version_id = head.current_version_id
    except Exception:
        pass  # bridge head absence is not an error — page may not be tracked yet

    return _map_page(page, current_revision_hash=current_revision_hash, current_version_id=current_version_id)


# ---------------------------------------------------------------------------
# Write routes — spaces
# ---------------------------------------------------------------------------

@router.post(
    "/spaces",
    response_model=HelperSpaceWriteOut,
    status_code=201,
    summary="Create a space",
)
def create_space(body: HelperSpaceCreateIn):
    try:
        data = docmost_create_space(name=body.name, slug=body.slug)
    except Exception as exc:
        _raise_for_docmost_error(exc)
    return HelperSpaceWriteOut(
        space_id=data["id"],
        name=data.get("name", body.name),
        slug=data.get("slug", body.slug),
    )


@router.delete(
    "/spaces/{space_id}",
    status_code=204,
    summary="Delete a space",
)
def delete_space(space_id: UUID):
    try:
        delete_space_via_bridge(space_id=space_id, caller_mode="helper")
    except Exception as exc:
        _raise_for_docmost_error(exc)


# ---------------------------------------------------------------------------
# Write routes — pages
# ---------------------------------------------------------------------------

@router.post(
    "/spaces/{space_id}/pages",
    response_model=HelperPageWriteOut,
    status_code=201,
    summary="Create a page",
)
def create_page(space_id: UUID, body: HelperPageCreateIn):
    try:
        result = create_page_via_bridge(
            space_id=space_id,
            title=body.title,
            content=body.content,
            parent_page_id=body.parent_page_id,
            caller_mode="helper",
        )
    except BridgeConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BridgeStateError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        _raise_for_docmost_error(exc)
    return _map_write_result(result)


@router.put(
    "/spaces/{space_id}/pages/{page_id}",
    response_model=HelperPageWriteOut,
    summary="Update a page",
)
def update_page(space_id: UUID, page_id: UUID, body: HelperPageUpdateIn):
    try:
        result = update_page_via_bridge(
            page_id=page_id,
            title=body.title,
            content=body.content,
            operation=body.operation,
            caller_mode="helper",
            expected_base_revision_hash=body.base_revision_hash,
            force=body.force,
            expected_space_id=space_id,
        )
    except BridgeConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BridgeStateError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        _raise_for_docmost_error(exc)
    return _map_write_result(result)


@router.delete(
    "/spaces/{space_id}/pages/{page_id}",
    status_code=204,
    summary="Delete a page",
)
def delete_page(space_id: UUID, page_id: UUID):
    try:
        delete_page_via_bridge(
            page_id=page_id,
            caller_mode="helper",
            expected_space_id=space_id,
        )
    except BridgeStateError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        _raise_for_docmost_error(exc)


@router.post(
    "/spaces/{space_id}/pages/{page_id}/move",
    response_model=HelperPageWriteOut,
    summary="Move/re-parent a page (id-preserving)",
)
def move_page(space_id: UUID, page_id: UUID, body: HelperPageMoveIn):
    try:
        result = move_page_via_bridge(
            page_id=page_id,
            position=body.position,
            parent_page_id=body.parent_page_id,
            caller_mode="helper",
            expected_space_id=space_id,
        )
    except BridgeConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BridgeStateError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        _raise_for_docmost_error(exc)
    return _map_write_result(result)


# ---------------------------------------------------------------------------
# Snapshot routes
# ---------------------------------------------------------------------------

@router.post(
    "/spaces/{space_id}/pages/{page_id}/snapshots",
    response_model=HelperSnapshotOut,
    status_code=201,
    summary="Create a local page snapshot",
)
def create_snapshot(space_id: UUID, page_id: UUID, body: HelperSnapshotCreateIn):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                record = repo_create_snapshot(
                    cur,
                    page_id=page_id,
                    space_id=space_id,
                    content=body.content,
                    base_revision_hash=body.base_revision_hash,
                    local_path=body.local_path,
                )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _map_snapshot(record)


@router.get(
    "/spaces/{space_id}/pages/{page_id}/snapshots/{snapshot_id}",
    response_model=HelperSnapshotOut,
    summary="Get a snapshot by ID",
)
def get_snapshot(space_id: UUID, page_id: UUID, snapshot_id: UUID):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                record = repo_get_snapshot(cur, page_id=page_id, snapshot_id=snapshot_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Snapshot not found.")
    return _map_snapshot(record)


@router.delete(
    "/spaces/{space_id}/pages/{page_id}/snapshots/{snapshot_id}",
    status_code=204,
    summary="Delete a snapshot",
)
def delete_snapshot(space_id: UUID, page_id: UUID, snapshot_id: UUID):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                deleted = repo_delete_snapshot(cur, page_id=page_id, snapshot_id=snapshot_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Snapshot not found.")


# ---------------------------------------------------------------------------
# Mappers
# ---------------------------------------------------------------------------

def _map_space(space: SpaceOut) -> HelperSpaceOut:
    return HelperSpaceOut(
        space_id=space.id,
        name=space.name or "",
        slug=space.slug,
        description=space.description,
    )


def _map_page(page: PageOut, *, current_revision_hash: str | None = None, current_version_id: UUID | None = None) -> HelperPageOut:
    return HelperPageOut(
        page_id=page.id,
        space_id=page.space_id,
        title=page.title,
        content=page.content,
        parent_page_id=page.parent_page_id,
        slug_id=page.slug_id,
        position=page.position,
        icon=page.icon,
        current_revision_hash=current_revision_hash,
        current_version_id=current_version_id,
    )


def _map_tree_node(node: PageTreeNode) -> HelperPageTreeNodeOut:
    return HelperPageTreeNodeOut(
        page_id=node.id,
        title=node.title,
        parent_page_id=node.parent_page_id,
        children=[_map_tree_node(c) for c in node.children],
    )


def _map_tree(space_id: UUID, tree: SpaceTreeOut) -> HelperSpaceTreeOut:
    all_roots = [_map_tree_node(n) for n in tree.root_pages] + [
        _map_tree_node(n) for n in tree.orphan_pages
    ]
    return HelperSpaceTreeOut(space_id=space_id, roots=all_roots)


def _map_write_result(result) -> HelperPageWriteOut:
    return HelperPageWriteOut(
        page_id=result.page_id,
        title=result.title,
        parent_page_id=result.parent_page_id,
        slug_id=result.slug_id,
        base_revision_hash=result.base_revision_hash,
        base_version_id=result.base_version_id,
    )


def _map_snapshot(record: LocalPageSnapshotRecord) -> HelperSnapshotOut:
    return HelperSnapshotOut(
        snapshot_id=record.id,
        page_id=record.page_id,
        space_id=record.space_id,
        content=record.content,
        base_revision_hash=record.base_revision_hash,
        snapshotted_at=record.snapshotted_at,
        status=record.status,
    )


def _raise_for_docmost_error(exc: Exception) -> None:
    import httpx

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text
        raise HTTPException(status_code=status, detail=detail) from exc
    raise HTTPException(status_code=502, detail=str(exc)) from exc
