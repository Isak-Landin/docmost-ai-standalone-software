from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AutoPageWriteIn(BaseModel):
    page_id: UUID | None = Field(None, description="Existing remote page UUID. Leave empty to create a new page.")
    title: str | None = Field(None, description="Desired page title. Required for create, optional for update.")
    content: str | None = Field(None, description="Page markdown body provided directly by the helper upload path.")
    parent_page_id: UUID | None = Field(None, description="Optional remote parent page UUID for create operations.")
    base_revision_hash: str | None = Field(
        None,
        description="Current client-side bridge base revision for aligned automation writes.",
    )
    operation: Literal["replace", "append", "prepend"] = Field(
        "replace",
        description="How content is applied when updating an existing page.",
    )
    force: bool = Field(
        False,
        description="When true, allow the automation flow to overwrite a mismatched current bridge head.",
    )
    local_path: str | None = Field(None, description="Optional helper-side local path for result correlation.")


class AutoPageWriteBatchIn(BaseModel):
    pages: list[AutoPageWriteIn] = Field(default_factory=list, description="Ordered helper-supplied page operations.")


class AutoPageWriteResultOut(BaseModel):
    page_id: UUID | None = None
    title: str | None = None
    slug_id: str | None = None
    parent_page_id: UUID | None = None
    local_path: str | None = None
    action: str
    applied: bool
    message: str
    base_revision_hash: str | None = None


class AutoPageWriteBatchOut(BaseModel):
    applied_count: int = 0
    drifted_count: int = 0
    results: list[AutoPageWriteResultOut] = Field(default_factory=list)


class AutoObserveOut(BaseModel):
    space_id: UUID
    checked_pages: int
    bridge_writes_confirmed: int
    external_updates_recorded: int
    external_deletions_recorded: int
