from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SpaceOut(BaseModel):
    id: UUID = Field(description="Space UUID")
    name: Optional[str] = Field(None, description="Display name of the space")
    description: Optional[str] = Field(None, description="Optional space description")
    slug: str = Field(description="URL-friendly identifier")
    visibility: str = Field(description="Visibility setting (e.g. public, private)")
    default_role: str = Field(description="Default member role for this space")
    creator_id: Optional[UUID] = Field(None, description="UUID of the user who created the space")
    workspace_id: UUID = Field(description="UUID of the parent workspace")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PageOut(BaseModel):
    id: UUID = Field(description="Page UUID")
    slug_id: str = Field(description="Short URL-friendly identifier")
    title: Optional[str] = Field(None, description="Page title")
    icon: Optional[str] = Field(None, description="Emoji or icon identifier")
    position: Optional[str] = Field(None, description="Sort position within the parent")
    parent_page_id: Optional[UUID] = Field(None, description="UUID of the parent page, or null for root pages")
    creator_id: Optional[UUID] = Field(None, description="UUID of the user who created the page")
    last_updated_by_id: Optional[UUID] = Field(None, description="UUID of the user who last updated the page")
    space_id: UUID = Field(description="UUID of the space this page belongs to")
    workspace_id: UUID = Field(description="UUID of the parent workspace")
    is_locked: bool = Field(description="Whether the page is locked for editing")
    content: Optional[str] = Field(
        None,
        description=(
            "Markdown content of the page. "
            "Populated on single-page GET (fetched via Docmost REST with format=markdown). "
            "Null when listing pages."
        ),
    )
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class PageMetaOut(BaseModel):
    """Page identity and metadata only - no content. Used for write operation responses."""

    id: UUID = Field(description="Page UUID")
    slug_id: str = Field(description="Short URL-friendly identifier")
    title: Optional[str] = Field(None, description="Page title")
    icon: Optional[str] = Field(None, description="Emoji or icon identifier")
    position: Optional[str] = Field(None, description="Sort position within the parent")
    parent_page_id: Optional[UUID] = Field(None, description="UUID of the parent page, or null for root pages")
    creator_id: Optional[UUID] = Field(None, description="UUID of the user who created the page")
    last_updated_by_id: Optional[UUID] = Field(None, description="UUID of the user who last updated the page")
    space_id: UUID = Field(description="UUID of the space this page belongs to")
    workspace_id: UUID = Field(description="UUID of the parent workspace")
    is_locked: bool = Field(description="Whether the page is locked for editing")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class SpaceSummaryOut(BaseModel):
    id: UUID = Field(description="Space UUID")
    name: Optional[str] = Field(None, description="Display name of the space")
    slug: str = Field(description="URL-friendly identifier")

    model_config = {"from_attributes": True}


class PageTreeNode(BaseModel):
    id: UUID = Field(description="Page UUID")
    title: Optional[str] = Field(None, description="Page title")
    slug_id: str = Field(description="Short URL-friendly identifier")
    icon: Optional[str] = Field(None, description="Emoji or icon identifier")
    parent_page_id: Optional[UUID] = Field(None, description="UUID of the parent page, or null for root pages")
    position: Optional[str] = Field(None, description="Sort position within the parent")
    has_children: bool = Field(description="Whether this page has child pages in the resolved tree")
    children: list["PageTreeNode"] = Field(default_factory=list, description="Nested child pages")

    model_config = {"from_attributes": True}


class SpaceTreeOut(BaseModel):
    space: SpaceSummaryOut
    root_pages: list[PageTreeNode] = Field(
        default_factory=list,
        description="Top-level pages in the space, each with fully nested descendants.",
    )
    orphan_pages: list[PageTreeNode] = Field(
        default_factory=list,
        description="Pages that could not be attached to a normal root because their parent is missing or unreachable.",
    )

    model_config = {"from_attributes": True}


PageTreeNode.model_rebuild()


class ReplicaStandardsOut(BaseModel):
    replica_root_suffix: str = Field(description="Suffix appended to the space name to form the replica root directory.")
    replica_root_example: str = Field(description="Example replica root directory path.")
    page_directory_base_rule: str = Field(description="Base directory naming rule for a page.")
    sibling_collision_rule: str = Field(description="How same-level directory name collisions are resolved.")
    final_collision_fallback_rule: str = Field(description="Fallback naming rule if the primary collision strategy still collides.")
    page_content_file_name: str = Field(description="File name that stores the page's markdown/text content.")
    page_meta_file_name: str = Field(description="File name that stores per-page metadata.")
    replica_meta_file_name: str = Field(description="File name that stores replica-level metadata.")
    tree_cache_file_name: str = Field(description="File name that stores the resolved tree snapshot.")
    initial_replica_source_rule: str = Field(description="How to build or refresh the initial local replica for existing remote content.")
    local_addition_source_rule: str = Field(description="How to create local-only documentation that does not yet exist on remote.")
    local_replica_requirement: str = Field(description="Whether a local replica is expected for normal client use.")
    read_source_policy: str = Field(description="How the remote Docmost source should be used for reads.")
    local_edit_policy: str = Field(description="How the local replica should be used for edits.")
    local_truth_policy: str = Field(description="How newer local-only changes should be treated before manual sync.")
    remote_sync_policy: str = Field(description="How to interpret remote state after local-only replica edits.")
    edited_replica_reporting_rule: str = Field(description="How edited local replica files should be surfaced back to the user.")
    remote_page_mapping_rule: str = Field(description="How a local replica file should be mapped back to its remote Docmost page.")
    manual_sync_prompt_rule: str = Field(description="When the client should prompt the user to sync local replica changes back to remote.")

    model_config = {"from_attributes": True}


class ReplicaNameResolutionOut(BaseModel):
    input_title: str = Field(description="Requested page title.")
    slug_id: Optional[str] = Field(None, description="Optional remote or planned slug identifier.")
    page_id: Optional[UUID] = Field(None, description="Optional remote page UUID.")
    sanitized_title: str = Field(description="Filesystem-safe form of the title used as the base directory name.")
    local_dir_name: str = Field(description="Resolved local directory name for the page.")
    collision_strategy: str = Field(description="Naming strategy used to resolve the final directory name.")

    model_config = {"from_attributes": True}


class ReplicaTreeNode(BaseModel):
    id: UUID = Field(description="Page UUID")
    title: Optional[str] = Field(None, description="Page title")
    slug_id: str = Field(description="Short URL-friendly identifier")
    parent_page_id: Optional[UUID] = Field(None, description="UUID of the parent page, or null for root pages")
    local_dir_name: str = Field(description="Resolved directory name for this page inside the replica.")
    local_dir_path: str = Field(description="Replica-relative directory path for this page.")
    content_file_path: str = Field(description="Replica-relative content file path for this page.")
    meta_file_path: str = Field(description="Replica-relative metadata file path for this page.")
    children: list["ReplicaTreeNode"] = Field(default_factory=list, description="Nested child pages in replica form.")

    model_config = {"from_attributes": True}


class ReplicaStructureOut(BaseModel):
    space: SpaceSummaryOut
    replica_root: str = Field(description="Replica root directory path for the space.")
    replica_meta_file_path: str = Field(description="Replica-relative path to the replica metadata file.")
    tree_cache_file_path: str = Field(description="Replica-relative path to the tree cache file.")
    standards: ReplicaStandardsOut
    root_pages: list[ReplicaTreeNode] = Field(
        default_factory=list,
        description="Root-level page directories in replica form, each with nested descendants.",
    )
    orphan_pages: list[ReplicaTreeNode] = Field(
        default_factory=list,
        description="Replica nodes for pages that could not be attached to a normal root because the parent is missing or unreachable.",
    )

    model_config = {"from_attributes": True}


ReplicaTreeNode.model_rebuild()


# ---------------------------------------------------------------------------
# Write request models
# ---------------------------------------------------------------------------


class SpaceCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=100, description="Display name for the new space.")
    slug: str = Field(
        min_length=2,
        max_length=100,
        pattern=r"^[a-zA-Z0-9]+$",
        description="URL-friendly identifier. Alphanumeric only, no spaces or dashes.",
    )
    description: Optional[str] = Field(None, description="Optional plain-text description.")


class PageCreateIn(BaseModel):
    title: Optional[str] = Field(None, description="Page title. Defaults to empty if omitted.")
    content: Optional[str] = Field(None, description="Markdown content for the page body.")
    parent_page_id: Optional[UUID] = Field(
        None, description="UUID of the parent page. Omit for a root-level page."
    )


class PageUpdateIn(BaseModel):
    title: Optional[str] = Field(None, description="New title. Unchanged if omitted.")
    content: Optional[str] = Field(None, description="Markdown content. Unchanged if omitted.")
    operation: Literal["replace", "append", "prepend"] = Field(
        "replace",
        description=(
            "How content is applied when content is provided. "
            "'replace' overwrites the full body (default). "
            "'append' adds after existing content. "
            "'prepend' adds before existing content."
        ),
    )


class DeletedOut(BaseModel):
    deleted: bool = Field(True, description="Always true on successful deletion.")
    id: str = Field(description="UUID of the deleted resource.")


# ---------------------------------------------------------------------------
# Sync request/response models
# ---------------------------------------------------------------------------


SyncState = Literal[
    "synced",
    "local_only_change",
    "remote_only_change",
    "conflicted",
    "remote_only_page",
    "local_only_page",
    "remote_deleted",
    "local_missing",
]

SyncRecommendedAction = Literal[
    "none",
    "pull_replica",
    "push_replica",
    "get_sync_diff",
    "review_remote_deletion",
]


class SyncSelectionIn(BaseModel):
    page_ids: list[UUID] = Field(
        default_factory=list,
        description="Optional remote page UUIDs to target. Leave empty to operate on the whole space.",
    )
    local_paths: list[str] = Field(
        default_factory=list,
        description="Optional local replica content file paths to target. Useful for local-only pages without a remote UUID yet.",
    )
    force: bool = Field(
        False,
        description=(
            "When true, resolve pull or push conflicts by taking the operation's source of truth. "
            "For pull this overwrites local replica content with remote content. "
            "For push this overwrites remote content with local replica content."
        ),
    )


class SyncStatusCountsOut(BaseModel):
    synced: int = 0
    local_only_change: int = 0
    remote_only_change: int = 0
    conflicted: int = 0
    remote_only_page: int = 0
    local_only_page: int = 0
    remote_deleted: int = 0
    local_missing: int = 0


class PageSyncStatusOut(BaseModel):
    page_id: Optional[UUID] = Field(None, description="Remote page UUID when the page exists remotely.")
    title: Optional[str] = Field(None, description="Best-known page title.")
    slug_id: Optional[str] = Field(None, description="Remote slug identifier when available.")
    parent_page_id: Optional[UUID] = Field(None, description="Best-known parent page UUID.")
    sync_state: SyncState = Field(description="Computed sync state for the page.")
    summary: str = Field(description="Human-readable explanation of the current sync state.")
    local_path: Optional[str] = Field(None, description="Replica content file path relative to the configured replica root base.")
    local_abs_path: Optional[str] = Field(None, description="Absolute server-side path to the replica content file when it exists.")
    desired_local_path: Optional[str] = Field(None, description="Expected replica content file path for a remote page when it has not been materialized locally yet.")
    desired_local_abs_path: Optional[str] = Field(None, description="Absolute server-side path where the remote page would be materialized locally.")
    meta_file_path: Optional[str] = Field(None, description="Replica metadata file path relative to the configured replica root base.")
    meta_abs_path: Optional[str] = Field(None, description="Absolute server-side path to the replica metadata file when it exists.")
    remote_exists: bool = Field(description="Whether the page currently exists in remote Docmost.")
    local_exists: bool = Field(description="Whether the replica content file currently exists locally.")
    local_changed: bool = Field(description="Whether local content differs from the last sync base.")
    remote_changed: bool = Field(description="Whether remote content differs from the last sync base.")
    has_conflicts: bool = Field(description="Whether local and remote changes currently clash.")
    recommended_action: SyncRecommendedAction = Field(description="Recommended next tool or action for this page's current state.")
    allowed_actions: list[str] = Field(default_factory=list, description="Allowed next-step actions for automation or users handling this state.")
    base_content_hash: Optional[str] = Field(None, description="Hash of the last synchronized content base, when known.")
    local_content_hash: Optional[str] = Field(None, description="Hash of the current local content, when available.")
    remote_content_hash: Optional[str] = Field(None, description="Hash of the current remote content, when available.")


class SpaceSyncStatusOut(BaseModel):
    space: SpaceSummaryOut
    replica_root: str = Field(description="Replica root path relative to the configured replica root base.")
    replica_root_abs_path: str = Field(description="Absolute server-side path to the space replica root.")
    replica_exists: bool = Field(description="Whether the space replica root currently exists on disk.")
    generated_at: datetime
    pipeline_expectations: list[str] = Field(default_factory=list, description="Recommended status/diff/pull/push pipeline for this replica.")
    counts: SyncStatusCountsOut
    pages: list[PageSyncStatusOut] = Field(default_factory=list)


class SyncDiffHunkOut(BaseModel):
    kind: Literal["replace", "insert", "delete"] = Field(description="Line-level diff hunk type.")
    local_start_line: int = Field(description="1-based starting line in the local content. For inserts, this is the insertion point.")
    local_end_line: int = Field(description="1-based ending line in the local content, or the line before the insertion point for inserts.")
    remote_start_line: int = Field(description="1-based starting line in the remote content. For inserts, this is the insertion point.")
    remote_end_line: int = Field(description="1-based ending line in the remote content, or the line before the insertion point for inserts.")
    local_lines: list[str] = Field(default_factory=list, description="Local lines participating in this hunk.")
    remote_lines: list[str] = Field(default_factory=list, description="Remote lines participating in this hunk.")


class PageSyncDiffOut(BaseModel):
    page_id: Optional[UUID] = Field(None, description="Remote page UUID when the page exists remotely.")
    title: Optional[str] = Field(None, description="Best-known page title.")
    sync_state: SyncState = Field(description="Computed sync state for the page.")
    summary: str = Field(description="Human-readable explanation of the diff result.")
    local_path: Optional[str] = Field(None, description="Replica content file path relative to the configured replica root base.")
    local_abs_path: Optional[str] = Field(None, description="Absolute server-side path to the replica content file when it exists.")
    remote_exists: bool = Field(description="Whether the page currently exists in remote Docmost.")
    local_exists: bool = Field(description="Whether the replica content file currently exists locally.")
    has_conflicts: bool = Field(description="Whether the diff represents a true local-vs-remote clash.")
    hunks: list[SyncDiffHunkOut] = Field(default_factory=list, description="All differing line sections between local and remote content.")


class SpaceSyncDiffOut(BaseModel):
    space: SpaceSummaryOut
    replica_root: str = Field(description="Replica root path relative to the configured replica root base.")
    replica_root_abs_path: str = Field(description="Absolute server-side path to the space replica root.")
    generated_at: datetime
    pages: list[PageSyncDiffOut] = Field(default_factory=list)


class SyncOperationResultOut(BaseModel):
    page_id: Optional[UUID] = Field(None, description="Remote page UUID when the page exists remotely.")
    title: Optional[str] = Field(None, description="Best-known page title.")
    local_path: Optional[str] = Field(None, description="Replica content file path relative to the configured replica root base.")
    local_abs_path: Optional[str] = Field(None, description="Absolute server-side path to the replica content file when it exists.")
    sync_state_before: SyncState = Field(description="The sync state before this operation processed the page.")
    action: str = Field(description="Action taken or attempted for this page.")
    applied: bool = Field(description="Whether the operation actually mutated local or remote state.")
    message: str = Field(description="Human-readable result message for this page.")
    recommended_next_action: Optional[SyncRecommendedAction] = Field(None, description="Recommended next action when this operation was blocked or skipped.")
    conflicts: list[SyncDiffHunkOut] = Field(default_factory=list, description="Conflict hunks returned when the operation could not proceed safely.")


class SyncOperationOut(BaseModel):
    space: SpaceSummaryOut
    operation: Literal["pull", "push"] = Field(description="Which sync operation was executed.")
    replica_root: str = Field(description="Replica root path relative to the configured replica root base.")
    replica_root_abs_path: str = Field(description="Absolute server-side path to the space replica root.")
    force: bool = Field(description="Whether conflict resolution was forced in favor of the operation source.")
    generated_at: datetime
    applied_count: int = 0
    skipped_count: int = 0
    conflict_count: int = 0
    results: list[SyncOperationResultOut] = Field(default_factory=list)
