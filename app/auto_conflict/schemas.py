from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AutoConflictItemIn(BaseModel):
    page_id: UUID
    kind: str = "conflict"
    reason: Optional[str] = None
    title: Optional[str] = None
    local_path: Optional[str] = None
    base_revision_hash: Optional[str] = None
    base_version_id: Optional[UUID] = None
    local_version: Optional[str] = None
    remote_version: Optional[str] = None


class AutoConflictPostIn(BaseModel):
    conflicts: list[AutoConflictItemIn] = Field(default_factory=list)


class AutoConflictOut(BaseModel):
    space_id: UUID
    page_id: UUID
    kind: str
    reason: Optional[str] = None
    title: Optional[str] = None
    local_path: Optional[str] = None
    base_revision_hash: Optional[str] = None
    base_version_id: Optional[UUID] = None
    local_version: Optional[str] = None
    remote_version: Optional[str] = None
    detected_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AutoConflictListOut(BaseModel):
    count: int
    conflicts: list[AutoConflictOut] = Field(default_factory=list)


class AutoConflictPostOut(BaseModel):
    space_id: UUID
    stored: int


class AutoConflictResolveOut(BaseModel):
    space_id: UUID
    page_id: UUID
    cleared: bool
