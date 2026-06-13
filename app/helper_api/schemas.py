from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Read responses
# ---------------------------------------------------------------------------

class HelperSpaceOut(BaseModel):
    space_id: UUID
    name: str
    slug: str
    description: Optional[str] = None


class HelperPageOut(BaseModel):
    page_id: UUID
    space_id: UUID
    title: Optional[str] = None
    content: Optional[str] = None
    parent_page_id: Optional[UUID] = None
    slug_id: Optional[str] = None
    position: Optional[str] = None
    icon: Optional[str] = None
    current_revision_hash: Optional[str] = None
    current_version_id: Optional[UUID] = None


class HelperPageTreeNodeOut(BaseModel):
    page_id: UUID
    title: Optional[str] = None
    parent_page_id: Optional[UUID] = None
    children: list["HelperPageTreeNodeOut"] = []

    model_config = {"from_attributes": True}


class HelperSpaceTreeOut(BaseModel):
    space_id: UUID
    roots: list[HelperPageTreeNodeOut] = []


# ---------------------------------------------------------------------------
# Write inputs and responses
# ---------------------------------------------------------------------------

class HelperPageCreateIn(BaseModel):
    title: str
    content: Optional[str] = None
    parent_page_id: Optional[UUID] = None


class HelperPageUpdateIn(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    operation: Literal["replace", "append", "prepend"] = "replace"
    base_revision_hash: Optional[str] = None
    force: bool = False


class HelperPageMoveIn(BaseModel):
    position: str
    parent_page_id: Optional[UUID] = None


class HelperPageWriteOut(BaseModel):
    page_id: UUID
    title: Optional[str] = None
    parent_page_id: Optional[UUID] = None
    slug_id: Optional[str] = None
    base_revision_hash: Optional[str] = None
    base_version_id: Optional[UUID] = None


class HelperSpaceCreateIn(BaseModel):
    name: str
    slug: str


class HelperSpaceWriteOut(BaseModel):
    space_id: UUID
    name: str
    slug: str


# ---------------------------------------------------------------------------
# Snapshot inputs and responses
# ---------------------------------------------------------------------------

class HelperSnapshotCreateIn(BaseModel):
    content: str
    base_revision_hash: Optional[str] = None
    local_path: Optional[str] = None


class HelperSnapshotOut(BaseModel):
    snapshot_id: UUID
    page_id: UUID
    space_id: UUID
    content: str
    base_revision_hash: Optional[str] = None
    snapshotted_at: datetime
    status: str
