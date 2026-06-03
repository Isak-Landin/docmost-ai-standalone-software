from __future__ import annotations

from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models import SyncDiffHunkOut

# ---------------------------------------------------------------------------
# Request - the helper sends the current local page set for the scope plus the
# last-synced tree snapshot. The server cannot see the client filesystem, so all
# local state is explicit. Classification uses bridge head truth, not live remote.
# ---------------------------------------------------------------------------


class ReconcilePageIn(BaseModel):
    page_id: Optional[UUID] = Field(None, description="Tracked remote page UUID. Omit for a local-only page to create.")
    title: Optional[str] = None
    content: Optional[str] = None
    parent_page_id: Optional[UUID] = None
    position: Optional[str] = None
    icon: Optional[str] = None
    base_revision_hash: Optional[str] = Field(None, description="Recorded sync base (head revision at last successful sync).")
    local_path: Optional[str] = Field(None, description="Helper-side path for result correlation; opaque to the server.")
    parent_local_path: Optional[str] = Field(None, description="local_path of the parent page (dir nesting). Lets the server nest a new child under a sibling created in the same pass.")


class ReconcileTreeNodeIn(BaseModel):
    """A page as it stood at the last successful sync (from the helper's _tree.json)."""

    page_id: UUID
    parent_page_id: Optional[UUID] = None
    position: Optional[str] = None
    icon: Optional[str] = None


class ReconcileIn(BaseModel):
    scope: Literal["space", "tree", "page"] = "space"
    scope_id: Optional[UUID] = Field(None, description="parent_page_id for tree scope, page_id for page scope; null for space.")
    pages: list[ReconcilePageIn] = Field(default_factory=list)
    tree: list[ReconcileTreeNodeIn] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Response - four buckets (plan section 7). synced carries identity only;
# applied carries the canonical post-write snapshot (content only when the helper
# must materialize/update a local file); conflicts and deletion_confirmations are
# returned for a model decision and are never applied by reconcile.
# ---------------------------------------------------------------------------


class ReconcileSyncedItem(BaseModel):
    page_id: UUID
    local_path: Optional[str] = None
    base_revision_hash: Optional[str] = Field(None, description="Current head hash; the helper refreshes a stale local base to this.")


class ReconcileAppliedItem(BaseModel):
    page_id: UUID
    local_path: Optional[str] = None
    action: str = Field(description="pushed | created | pulled | moved | structural")
    title: Optional[str] = None
    slug_id: Optional[str] = None
    parent_page_id: Optional[UUID] = None
    position: Optional[str] = None
    icon: Optional[str] = None
    base_revision_hash: Optional[str] = None
    content: Optional[str] = Field(None, description="Present only when the helper must write/refresh the local file (created/pulled).")


class ReconcileConflictItem(BaseModel):
    page_id: UUID
    local_path: Optional[str] = None
    title: Optional[str] = None
    reason: str = Field(description="both_changed | delete_vs_change | structural_both_changed")
    base_revision_hash: Optional[str] = None
    local_version: Optional[str] = Field(None, description="Local content revision hash.")
    remote_version: Optional[str] = Field(None, description="Current remote (bridge head) revision hash.")
    local_content: Optional[str] = None
    remote_content: Optional[str] = None
    diff: list[SyncDiffHunkOut] = Field(default_factory=list)


class ReconcileDeletionItem(BaseModel):
    page_id: UUID
    local_path: Optional[str] = None
    title: Optional[str] = None
    direction: Literal["remote", "local"] = Field(description="remote: local removed -> soft-delete remote. local: remote removed -> drop local copy.")
    reason: str


class ReconcileErrorItem(BaseModel):
    page_id: Optional[UUID] = None
    local_path: Optional[str] = None
    message: str


class ReconcileOut(BaseModel):
    scope: str
    synced: list[ReconcileSyncedItem] = Field(default_factory=list)
    applied: list[ReconcileAppliedItem] = Field(default_factory=list)
    conflicts: list[ReconcileConflictItem] = Field(default_factory=list)
    deletion_confirmations: list[ReconcileDeletionItem] = Field(default_factory=list)
    errors: list[ReconcileErrorItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


class ResolveConflictIn(BaseModel):
    merged_content: str = Field(description="Final merged markdown to push, aligned to the current remote head.")
    title: Optional[str] = None
    base_revision_hash: Optional[str] = Field(None, description="Optional snapshot id consumed on success.")
    snapshot_id: Optional[str] = None


class ResolveConflictOut(BaseModel):
    page_id: UUID
    resolved: bool
    base_revision_hash: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None


class ConfirmDeletionIn(BaseModel):
    direction: Literal["remote", "local"]


class ConfirmDeletionOut(BaseModel):
    page_id: UUID
    direction: str
    remote_deleted: bool = False
