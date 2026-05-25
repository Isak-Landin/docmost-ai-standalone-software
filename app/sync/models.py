from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


SYNC_FILE_SCHEMA_VERSION = 1
SYNC_FILE_NAME = "_sync.json"
CANONICAL_REPLICA_GENERATED_FROM = "Docmost remote space and local replica bootstrap"


class ReplicaSpaceState(BaseModel):
    schema_version: int = Field(default=SYNC_FILE_SCHEMA_VERSION)
    space_id: UUID
    space_name: Optional[str] = None
    space_slug: str
    replica_root: str
    last_pulled_at: Optional[datetime] = None
    last_pushed_at: Optional[datetime] = None
    updated_at: datetime


class ReplicaPageState(BaseModel):
    schema_version: int = Field(default=SYNC_FILE_SCHEMA_VERSION)
    page_id: Optional[UUID] = None
    space_id: UUID
    title: Optional[str] = None
    slug_id: Optional[str] = None
    parent_page_id: Optional[UUID] = None
    local_dir_path: str
    content_file_path: str
    meta_file_path: str
    base_content_hash: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    last_sync_remote_updated_at: Optional[datetime] = None
    last_sync_title: Optional[str] = None


@dataclass
class LocalReplicaScan:
    replica_state: Optional[ReplicaSpaceState]
    page_metas: list[ReplicaPageState] = field(default_factory=list)
    page_meta_by_id: dict[UUID, ReplicaPageState] = field(default_factory=dict)
    page_meta_by_content_path: dict[str, ReplicaPageState] = field(default_factory=dict)
    root_exists: bool = False


@dataclass
class LocalReplicaPaths:
    root_path: Path
    replica_meta_path: Path
    replica_sync_path: Path
    tree_cache_path: Path
