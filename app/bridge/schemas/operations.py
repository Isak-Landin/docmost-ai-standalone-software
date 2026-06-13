from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class BridgePageSnapshot:
    page_id: UUID
    space_id: UUID
    title: str | None
    slug_id: str | None
    parent_page_id: UUID | None
    content: str
    revision_hash: str
    remote_updated_at: datetime | None
    is_deleted: bool = False
    position: str | None = None
    icon: str | None = None


@dataclass(frozen=True)
class BridgeWriteResult:
    page_id: UUID
    space_id: UUID
    title: str | None
    slug_id: str | None
    parent_page_id: UUID | None
    content: str
    base_revision_hash: str
    base_version_id: UUID | None
    remote_updated_at: datetime | None
    action: str
    caller_mode: str
    write_intent_id: UUID
    remote_page: dict[str, Any]


@dataclass(frozen=True)
class ObserveSpaceResult:
    space_id: UUID
    checked_pages: int
    bridge_writes_confirmed: int
    external_updates_recorded: int
    external_deletions_recorded: int
    reanchored_count: int = 0
