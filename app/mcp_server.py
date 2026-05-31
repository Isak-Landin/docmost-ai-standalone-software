from __future__ import annotations

import os
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.fastmcp.server import TransportSecuritySettings

from app.bridge.services.write_pipeline import create_page_via_bridge, delete_page_via_bridge, delete_space_via_bridge, update_page_via_bridge
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
from app.models import (
    ClientReplicaPageIn,
    DeletedOut,
    LocalReplicaPageCreateIn,
    LocalReplicaPageOut,
    PageOut,
    ReplicaNameResolutionOut,
    ReplicaStandardsOut,
    ReplicaStructureOut,
    SpaceOut,
    SyncDiffIn,
    SyncSelectionIn,
    SyncStatusIn,
    SpaceSyncDiffOut,
    SpaceSyncStatusOut,
    SpaceTreeOut,
    SyncOperationOut,
)
from app.write.docmost import create_space as docmost_create_space
from app.query.replica import (
    get_replica_standards as fetch_replica_standards,
    get_replica_structure as fetch_replica_structure,
    resolve_replica_directory_name as resolve_replica_directory_name_impl,
)
from app.sync.service import (
    create_local_replica_page as run_create_local_replica_page,
    get_sync_diff as fetch_sync_diff,
    get_sync_status as fetch_sync_status,
    pull_replica as run_pull_replica,
    push_replica as run_push_replica,
)
from app.write.mappers import map_page_out_from_bridge_result, map_space

SERVER_INSTRUCTIONS = """
## IMPORTANT: Use the docmost-helper MCP for all normal operations

If the docmost-helper stdio MCP is available in your session, use it for all Docmost
operations — reads, writes, and sync. The helper owns local replica file IO and
provides the correct sync contract with the server.

Only call tools on this server (docmost-mcp) directly when:
- The helper is unavailable (fallback / manual override)
- You need direct inspection of bridge state (get_sync_status, get_sync_diff)
- You are performing a single targeted read without a local replica

The helper calls this server via REST (/helper/v1/ and /auto-mcp/) — never via this MCP
surface. Do not instruct the helper to call /mcp.

---

This server exposes a bridge to Docmost spaces and pages for both reading and writing.

This MCP surface is the server-side half of a bridge.
The server owns Docmost integration, bridge state, normalization, and remote writes.
The helper owns local replica file IO, working-copy selection, page edits,
and any locally stored sync-base metadata. Do not assume the server can see or scan
the client working copy. Provide client-local page state explicitly in replica and
sync calls.

## Reading
Use list_spaces to find the correct space. Use get_space_tree for page hierarchy.
Use list_pages for a flat page list. Use get_page for a single page with markdown content.
If the user gives a space name rather than a UUID, resolve it with list_spaces first.
Pages are always space-scoped — always pass space_id together with page_id.

## Writing
All write tools authenticate automatically — never call an auth tool first.
Use push_replica and pull_replica as the normal local-first workflow when the user
is working from a client-owned replica.
Use create_space to create a new space (slug must be alphanumeric, no dashes).
Use create_page to create a page. Pass parent_page_id to create nested child pages.
Use update_page to update an existing page's title and/or content.
  Prefer update_page over delete+create — Docmost preserves page history on update.
  Use operation='replace' (default) to overwrite, 'append' or 'prepend' to add content.
Use delete_page to soft-delete a page (it moves to Docmost trash).
Use delete_space to permanently delete a space and all its contents.
Bridge-owned page writes are recorded in the bridge database before and after the remote Docmost write.
All content is markdown in and out. Never pass ProseMirror JSON to write tools.

Page title rules (applies to create_page and update_page):
The page title is always passed as a separate 'title' parameter — it is rendered by Docmost
as the page header above the body. Never include the title as a H1 heading (# Title) at the
top of the content markdown. Doing so causes the title to appear twice in the rendered page.

Content formatting rules (applies to all page content passed to create_page and update_page):
Do NOT use Unicode typographic characters in page content. These characters are not reliably
rendered across all Docmost consumers and may appear as garbled text or question marks.
Forbidden characters and their plain-text replacements:
  em dash (-)    -> use hyphen with surrounding spaces ( - ) or a plain hyphen (-)
  en dash (-)    -> use a plain hyphen (-)
  right arrow (->) -> use the two-character sequence ->
  double arrow (=>) -> use the two-character sequence =>
  ellipsis (...)  -> use three plain dots (...)
  curly quotes (" " ' ') -> use straight quotes (" and ')
When inline text separation is needed, use a plain hyphen (-) as the separator.

All IDs passed to write tools (space_id, page_id, parent_page_id) must originate from a
prior MCP tool response in the current session — never from memory, local files, or inference.
  - space_id: must come from list_spaces or create_space.
  - parent_page_id: must come from list_pages, get_space_tree, or a create_page response.
A 404 from any write tool means the given ID does not exist in the live Docmost instance.
Resolve by calling the appropriate read tool (list_spaces, list_pages) to obtain a valid ID.

## Replica management (override / inspection only)

Prefer the docmost-helper MCP for all sync and write workflows involving a local replica.
The tools below remain available for manual inspection and fine-grained override.

Use get_replica_structure and get_replica_standards to inspect the canonical replica layout.
Use get_sync_status(space_id, pages=[...]) to classify local vs remote state without writing.
Use get_sync_diff(space_id, pages=[...]) to see line-level diffs before a force decision.
Use push_replica and pull_replica only for manual override when the helper is unavailable.

All local replica file IO, _meta.json updates, and stash management belong to the helper.
The server owns path planning, normalization, bridge version checks, and remote writes.
Helper-driven automation lives on the REST-only /auto-mcp surface, not as an MCP tool.

When a sync result returns recommended_next_action, follow that step.
Do not force a sync winner without reviewing the diff first.
If content looks stale or inconsistent, say so explicitly rather than guessing.
""".strip()

def _transport_security() -> TransportSecuritySettings:
    raw = os.getenv("MCP_ALLOWED_HOSTS", "")
    allowed = [h.strip() for h in raw.split(",") if h.strip()]
    return TransportSecuritySettings(allowed_hosts=allowed) if allowed else TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    )


mcp = FastMCP(
    "Docmost MCP",
    instructions=SERVER_INSTRUCTIONS,
    json_response=True,
    transport_security=_transport_security(),
)


@mcp.tool()
def list_spaces() -> list[SpaceOut]:
    """List all non-deleted Docmost spaces. Use this first when you need to identify a space by name."""
    try:
        return fetch_spaces()
    except DocmostConnectionError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def get_space(space_id: UUID) -> SpaceOut:
    """Get one Docmost space by UUID."""
    try:
        return fetch_space(space_id)
    except DocmostConnectionError as exc:
        raise ToolError(str(exc)) from exc
    except SpaceNotFoundError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def get_space_tree(space_id: UUID) -> SpaceTreeOut:
    """Get the fully nested page tree for one space identified by space_id."""
    try:
        return fetch_space_tree(space_id)
    except DocmostConnectionError as exc:
        raise ToolError(str(exc)) from exc
    except SpaceNotFoundError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def get_replica_standards() -> ReplicaStandardsOut:
    """Get the shared naming, layout, and sync rules for local documentation replicas."""
    return fetch_replica_standards()


@mcp.tool()
def resolve_replica_directory_name(
    title: str,
    slug_id: str | None = None,
    page_id: UUID | None = None,
    existing_dir_names: list[str] | None = None,
) -> ReplicaNameResolutionOut:
    """Resolve the correct local replica directory name for a page title under the shared standard."""
    return resolve_replica_directory_name_impl(
        title=title,
        slug_id=slug_id,
        page_id=page_id,
        existing_dir_names=existing_dir_names or [],
    )


@mcp.tool()
def get_replica_structure(space_id: UUID, local_root: str = "") -> ReplicaStructureOut:
    """Get the deterministic local replica layout for one space, optionally projected into a specific local working copy root."""
    try:
        return fetch_replica_structure(space_id, replica_root=local_root or None)
    except DocmostConnectionError as exc:
        raise ToolError(str(exc)) from exc
    except SpaceNotFoundError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def create_local_replica_page(
    space_id: UUID,
    title: str,
    content: str = "",
    parent_page_id: UUID | None = None,
    parent_local_path: str = "",
    local_root: str = "",
    existing_dir_names: list[str] | None = None,
) -> LocalReplicaPageOut:
    """Plan a new local-only page in the selected client-local working copy before pushing it to remote Docmost."""
    try:
        return run_create_local_replica_page(
            space_id,
            LocalReplicaPageCreateIn(
                title=title,
                content=content,
                parent_page_id=parent_page_id,
                parent_local_path=parent_local_path or None,
                local_root=local_root or None,
                existing_dir_names=existing_dir_names or [],
            ),
        )
    except Exception as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def get_sync_status(
    space_id: UUID,
    pages: list[ClientReplicaPageIn] | None = None,
    page_ids: list[UUID] | None = None,
    local_paths: list[str] | None = None,
    include_synced: bool = False,
    local_root: str = "",
) -> SpaceSyncStatusOut:
    """Get the current sync status for one Docmost space from the client-reported local page state."""
    try:
        return fetch_sync_status(
            space_id,
            SyncStatusIn(
                local_root=local_root or None,
                pages=pages or [],
                page_ids=page_ids or [],
                local_paths=local_paths or [],
                include_synced=include_synced,
            ),
        )
    except Exception as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def get_sync_diff(
    space_id: UUID,
    pages: list[ClientReplicaPageIn] | None = None,
    page_id: UUID | None = None,
    local_path: str = "",
    include_synced: bool = False,
    local_root: str = "",
) -> SpaceSyncDiffOut:
    """Get line-based local-vs-remote diff hunks for one page or all unsynced pages using client-reported local page state."""
    try:
        return fetch_sync_diff(
            space_id,
            SyncDiffIn(
                local_root=local_root or None,
                pages=pages or [],
                page_id=page_id,
                local_path=local_path or None,
                include_synced=include_synced,
            ),
        )
    except Exception as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def pull_replica(
    space_id: UUID,
    pages: list[ClientReplicaPageIn] | None = None,
    page_ids: list[UUID] | None = None,
    local_paths: list[str] | None = None,
    force: bool = False,
    local_root: str = "",
) -> SyncOperationOut:
    """Return canonical remote snapshots the client should materialize or refresh locally for one space."""
    try:
        return run_pull_replica(
            space_id,
            SyncSelectionIn(
                local_root=local_root or None,
                pages=pages or [],
                page_ids=page_ids or [],
                local_paths=local_paths or [],
                force=force,
            ),
        )
    except Exception as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def push_replica(
    space_id: UUID,
    pages: list[ClientReplicaPageIn] | None = None,
    page_ids: list[UUID] | None = None,
    local_paths: list[str] | None = None,
    force: bool = False,
    local_root: str = "",
) -> SyncOperationOut:
    """Push selected client-local page changes back to remote Docmost for one space."""
    try:
        return run_push_replica(
            space_id,
            SyncSelectionIn(
                local_root=local_root or None,
                pages=pages or [],
                page_ids=page_ids or [],
                local_paths=local_paths or [],
                force=force,
            ),
        )
    except Exception as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def list_pages(space_id: UUID) -> list[PageOut]:
    """List all non-deleted pages in a Docmost space identified by space_id."""
    try:
        return fetch_pages(space_id)
    except DocmostConnectionError as exc:
        raise ToolError(str(exc)) from exc
    except SpaceNotFoundError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def get_page(space_id: UUID, page_id: UUID) -> PageOut:
    """Get one Docmost page by UUID within its space, with content as markdown.

    Use list_spaces and list_pages first if you only know names.
    Content is fetched via Docmost REST (format=markdown) — not the raw DB blob.
    """
    try:
        return fetch_page(space_id, page_id)
    except DocmostConnectionError as exc:
        raise ToolError(str(exc)) from exc
    except (PageNotFoundError, SpaceNotFoundError) as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def create_space(name: str, slug: str, description: str = "") -> SpaceOut:
    """Create a new Docmost space.

    Args:
        name: Display name for the space (2–100 characters).
        slug: Alphanumeric URL identifier, no spaces or dashes (2–100 chars).
        description: Optional plain-text description (default empty).

    Authentication is handled automatically.
    """
    try:
        data = docmost_create_space(name=name, slug=slug, description=description or None)
    except Exception as exc:
        raise ToolError(str(exc)) from exc
    return map_space(data)


@mcp.tool()
def delete_space(space_id: str) -> DeletedOut:
    """Permanently delete a Docmost space and all its pages.

    This is irreversible. Authentication is handled automatically.

    Args:
        space_id: UUID of the space to delete.
    """
    try:
        delete_space_via_bridge(space_id=UUID(space_id), caller_mode="crud")
    except Exception as exc:
        raise ToolError(str(exc)) from exc
    return DeletedOut(deleted=True, id=space_id)


@mcp.tool()
def create_page(
    space_id: str,
    title: str = "",
    content: str = "",
    parent_page_id: str = "",
) -> PageOut:
    """Create a new page in a Docmost space.

    Pass parent_page_id to create a nested child page under an existing page.
    Arbitrarily deep hierarchies are supported.
    Content is accepted as markdown. Authentication is handled automatically.

    space_id must come from list_spaces or create_space — never inferred or invented.
    parent_page_id must come from list_pages, get_space_tree, or a prior create_page response.
    A prior create_page id is only valid as parent_page_id within the same uninterrupted
    sequence — if any delete or space removal has occurred since that creation, resolve the
    current valid id with list_pages or get_space_tree before using it.
    A 404 response means the given space_id or parent_page_id does not exist in live Docmost.

    Args:
        space_id: UUID of the target space (from list_spaces or create_space).
        title: Page title (optional). Do NOT repeat this as a H1 heading in content — Docmost renders the title separately above the page body.
        content: Markdown content for the page body (optional).
        parent_page_id: UUID of the parent page (from list_pages, get_space_tree, or an uninterrupted prior create_page); leave empty for root.
    """
    try:
        result = create_page_via_bridge(
            space_id=UUID(space_id),
            title=title or None,
            content=content or None,
            parent_page_id=UUID(parent_page_id) if parent_page_id else None,
            caller_mode="crud",
        )
    except Exception as exc:
        raise ToolError(str(exc)) from exc
    return map_page_out_from_bridge_result(result)


@mcp.tool()
def update_page(
    page_id: str,
    title: str = "",
    content: str = "",
    operation: str = "replace",
) -> PageOut:
    """Update an existing Docmost page's title and/or content.

    Prefer update over delete+create — Docmost preserves page history on update.
    Content is accepted as markdown. Authentication is handled automatically.

    Args:
        page_id: UUID of the page to update.
        title: New title (leave empty to leave unchanged). Do NOT repeat this as a H1 heading in content — Docmost renders the title separately above the page body.
        content: Markdown content (leave empty to leave unchanged).
        operation: How content is applied: 'replace' (default), 'append', or 'prepend'.
    """
    try:
        result = update_page_via_bridge(
            page_id=UUID(page_id),
            title=title or None,
            content=content or None,
            operation=operation or "replace",
            caller_mode="crud",
        )
    except Exception as exc:
        raise ToolError(str(exc)) from exc
    return map_page_out_from_bridge_result(result)


@mcp.tool()
def delete_page(page_id: str) -> DeletedOut:
    """Soft-delete a Docmost page (moves it to trash).

    Authentication is handled automatically.

    Args:
        page_id: UUID of the page to delete.
    """
    try:
        delete_page_via_bridge(page_id=UUID(page_id), caller_mode="crud")
    except Exception as exc:
        raise ToolError(str(exc)) from exc
    return DeletedOut(deleted=True, id=page_id)
