from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.query.db import DocmostConnectionError
from app.query.docmost import SpaceNotFoundError
from app.models import ReplicaNameResolutionOut, ReplicaStandardsOut, ReplicaStructureOut
from app.query.replica import (
    get_replica_standards as fetch_replica_standards,
    get_replica_structure as fetch_replica_structure,
    resolve_replica_directory_name as resolve_directory_name,
)

router = APIRouter(tags=["replica"])


@router.get(
    "/replica/standards",
    response_model=ReplicaStandardsOut,
    summary="Get replica standards",
    description=(
        "Returns the naming, file-layout, and sync-behavior rules for the local documentation replica. "
        "Use this when a client needs to create or update local replica content without guessing the standard."
    ),
)
def get_replica_standards():
    return fetch_replica_standards()


@router.get(
    "/replica/resolve-directory-name",
    response_model=ReplicaNameResolutionOut,
    summary="Resolve a replica directory name",
    description=(
        "Resolves the local replica directory name for a page title under the current naming standard. "
        "Use this for planned local-only pages or edits that do not yet exist on remote Docmost."
    ),
)
def get_replica_directory_name(
    title: str,
    slug_id: Optional[str] = None,
    page_id: Optional[UUID] = None,
    existing_dir_names: List[str] = Query(default=[]),
):
    return resolve_directory_name(
        title=title,
        slug_id=slug_id,
        page_id=page_id,
        existing_dir_names=existing_dir_names,
    )


@router.get(
    "/spaces/{space_id}/replica-structure",
    response_model=ReplicaStructureOut,
    summary="Get replica structure for a space",
    description=(
        "Returns the deterministic local replica layout for one space, including local directory names, "
        "nested paths, content file paths, metadata file paths, and replica-level files. "
        "Pass local_root when you want those paths projected into a specific local working copy."
    ),
    responses={
        404: {"description": "Space not found."},
        503: {"description": "Docmost database connection failed."},
    },
)
def get_replica_structure(space_id: UUID, local_root: Optional[str] = None):
    try:
        return fetch_replica_structure(space_id, replica_root=local_root)
    except DocmostConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SpaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
