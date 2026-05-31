from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class PageVersionRecord:
    id: UUID
    page_id: UUID
    space_id: UUID
    revision_hash: str
    title: str | None
    content: str
    slug_id: str | None
    parent_page_id: UUID | None
    source: str
    source_write_intent_id: UUID | None
    remote_updated_at: datetime | None
    observed_at: datetime
    created_at: datetime


@dataclass(frozen=True)
class PageHeadRecord:
    page_id: UUID
    space_id: UUID
    current_version_id: UUID | None
    current_revision_hash: str | None
    title: str | None
    content: str
    slug_id: str | None
    parent_page_id: UUID | None
    remote_updated_at: datetime | None
    is_deleted: bool
    last_source: str
    last_checked_at: datetime
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class WriteIntentRecord:
    id: UUID
    page_id: UUID | None
    space_id: UUID
    action: str
    caller_mode: str
    status: str
    expected_base_revision_hash: str | None
    target_revision_hash: str | None
    title: str | None
    content: str | None
    parent_page_id: UUID | None
    operation: str | None
    error_text: str | None
    remote_page_id: UUID | None
    created_at: datetime
    updated_at: datetime
    applied_at: datetime | None
    failed_at: datetime | None


@dataclass(frozen=True)
class WriteReceiptRecord:
    id: UUID
    write_intent_id: UUID
    page_id: UUID
    space_id: UUID
    expected_revision_hash: str
    status: str
    expires_at: datetime | None
    created_at: datetime
    confirmed_at: datetime | None


@dataclass(frozen=True)
class ObserverCheckpointRecord:
    page_id: UUID
    space_id: UUID
    last_seen_remote_updated_at: datetime | None
    last_observed_revision_hash: str | None
    last_checked_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class LocalPageSnapshotRecord:
    id: UUID
    page_id: UUID
    space_id: UUID
    local_path: str | None
    content: str
    base_revision_hash: str | None
    snapshotted_at: datetime
    status: str
    created_at: datetime
