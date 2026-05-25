from __future__ import annotations

import os
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.fastmcp.server import TransportSecuritySettings

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
    DeletedOut,
    LocalReplicaPageCreateIn,
    LocalReplicaPageOut,
    PageCreateIn,
    PageOut,
    PageUpdateIn,
    ReplicaNameResolutionOut,
    ReplicaStandardsOut,
    ReplicaStructureOut,
    SpaceCreateIn,
    SpaceOut,
    SpaceSyncDiffOut,
    SpaceSyncStatusOut,
    SpaceTreeOut,
    SyncOperationOut,
)
from app.write.docmost import create_page as docmost_create_page
from app.write.docmost import create_space as docmost_create_space
from app.write.docmost import delete_page as docmost_delete_page
from app.write.docmost import delete_space as docmost_delete_space
from app.write.docmost import get_page_info
from app.write.docmost import update_page as docmost_update_page
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

SERVER_INSTRUCTIONS = """
This server exposes Docmost spaces and pages for both reading and writing.

## Reading
Use list_spaces to find the correct space. Use get_space_tree for page hierarchy.
Use list_pages for a flat page list. Use get_page for a single page with markdown content.
If the user gives a space name rather than a UUID, resolve it with list_spaces first.
Pages are always space-scoped — always pass space_id together with page_id.

## Writing
All write tools authenticate automatically — never call an auth tool first.
Use create_space to create a new space (slug must be alphanumeric, no dashes).
Use create_page to create a page. Pass parent_page_id to create nested child pages.
Use update_page to update an existing page's title and/or content.
  Prefer update_page over delete+create — Docmost preserves page history on update.
  Use operation='replace' (default) to overwrite, 'append' or 'prepend' to add content.
Use delete_page to soft-delete a page (it moves to Docmost trash).
Use delete_space to permanently delete a space and all its contents.
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

## Replica management
Maintain or create a server-side replica at `./{space_name}-replica/` when the client workflow allows it.
All local replica directory and file names must not contain spaces — replace with hyphens.
Use get_replica_structure for the initial local replica layout.
Use create_local_replica_page to scaffold a new local-only page in the server-side replica before editing it.
Use get_replica_standards and resolve_replica_directory_name to inspect or verify naming behavior when needed, not to hand-write `_meta.json`.
Keep canonical replica descriptors in `_replica.json`, `_tree.json`, and per-page `_meta.json`.
Keep server-side sync bookkeeping in separate `_sync.json` files rather than redefining the replica shape.
The server owns canonical structure, metadata paths, and comparison normalization.
The client owns page edits, selection, and force decisions after reviewing status or diff output.
Call get_sync_status first to classify the current state before choosing a sync action.
Use get_sync_status to identify unsynced local or remote pages programmatically.
Use get_sync_diff to return line-based local-vs-remote differences and all clashes.
Use get_sync_diff before any force pull or force push decision.
Use pull_replica to materialize or refresh the server-side replica from remote Docmost.
Use push_replica to push local replica changes back to remote Docmost.
pull_replica never auto-pushes local changes first.
push_replica never auto-pulls remote changes first.
When a sync result returns recommended_next_action, follow that next step instead of retrying the same blocked operation.
If both local and remote changed since the last sync base, return the clashes and let the
consuming model decide whether to force pull, force push, or ask the user.
If content looks stale, deprecated, or inconsistent with verified behavior, say so explicitly.
If requested data is missing, report that explicitly instead of guessing.
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
def get_replica_structure(space_id: UUID) -> ReplicaStructureOut:
    """Get the deterministic local replica layout for one space identified by space_id."""
    try:
        return fetch_replica_structure(space_id)
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
) -> LocalReplicaPageOut:
    """Scaffold a new local-only page in the server-side replica before pushing it to remote Docmost."""
    try:
        return run_create_local_replica_page(
            space_id,
            LocalReplicaPageCreateIn(
                title=title,
                content=content,
                parent_page_id=parent_page_id,
                parent_local_path=parent_local_path or None,
            ),
        )
    except Exception as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def get_sync_status(space_id: UUID, include_synced: bool = False) -> SpaceSyncStatusOut:
    """Get the current server-side sync status for one space replica."""
    try:
        return fetch_sync_status(space_id, include_synced=include_synced)
    except Exception as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def get_sync_diff(
    space_id: UUID,
    page_id: UUID | None = None,
    local_path: str = "",
    include_synced: bool = False,
) -> SpaceSyncDiffOut:
    """Get line-based local-vs-remote diff hunks for one page or all unsynced pages in a space replica."""
    try:
        return fetch_sync_diff(
            space_id,
            page_id=page_id,
            local_path=local_path or None,
            include_synced=include_synced,
        )
    except Exception as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def pull_replica(
    space_id: UUID,
    page_ids: list[UUID] | None = None,
    local_paths: list[str] | None = None,
    force: bool = False,
) -> SyncOperationOut:
    """Pull remote Docmost changes into the server-side replica for one space."""
    try:
        from app.models import SyncSelectionIn

        return run_pull_replica(
            space_id,
            SyncSelectionIn(page_ids=page_ids or [], local_paths=local_paths or [], force=force),
        )
    except Exception as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def push_replica(
    space_id: UUID,
    page_ids: list[UUID] | None = None,
    local_paths: list[str] | None = None,
    force: bool = False,
) -> SyncOperationOut:
    """Push server-side replica changes back to remote Docmost for one space."""
    try:
        from app.models import SyncSelectionIn

        return run_push_replica(
            space_id,
            SyncSelectionIn(page_ids=page_ids or [], local_paths=local_paths or [], force=force),
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


# ---------------------------------------------------------------------------
# Write tools — authenticate transparently via DOCMOST_USER_* env vars
# ---------------------------------------------------------------------------


def _map_page_from_rest(data: dict) -> PageOut:
    from datetime import datetime as _dt
    from app.query.prosemirror import prosemirror_to_markdown

    page = data.get("page", data)
    raw_content = page.get("content")
    if isinstance(raw_content, dict):
        content = prosemirror_to_markdown(raw_content)
    else:
        content = raw_content

    return PageOut(
        id=page["id"],
        slug_id=page.get("slugId") or page.get("slug_id") or "",
        title=page.get("title"),
        icon=page.get("icon"),
        position=page.get("position"),
        parent_page_id=page.get("parentPageId") or page.get("parent_page_id"),
        creator_id=page.get("creatorId") or page.get("creator_id"),
        last_updated_by_id=page.get("lastUpdatedById") or page.get("last_updated_by_id"),
        space_id=page.get("spaceId") or page.get("space_id") or "",
        workspace_id=page.get("workspaceId") or page.get("workspace_id") or "",
        is_locked=page.get("isLocked") or page.get("is_locked") or False,
        content=content,
        created_at=page.get("createdAt") or page.get("created_at") or _dt.utcnow(),
        updated_at=page.get("updatedAt") or page.get("updated_at") or _dt.utcnow(),
    )


def _map_space_from_rest(data: dict) -> SpaceOut:
    from datetime import datetime as _dt

    return SpaceOut(
        id=data["id"],
        name=data.get("name"),
        description=data.get("description"),
        slug=data["slug"],
        visibility=data.get("visibility", "private"),
        default_role=data.get("defaultRole", "writer"),
        creator_id=data.get("creatorId"),
        workspace_id=data["workspaceId"],
        created_at=data.get("createdAt") or _dt.utcnow(),
        updated_at=data.get("updatedAt") or _dt.utcnow(),
    )


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
    return _map_space_from_rest(data)


@mcp.tool()
def delete_space(space_id: str) -> DeletedOut:
    """Permanently delete a Docmost space and all its pages.

    This is irreversible. Authentication is handled automatically.

    Args:
        space_id: UUID of the space to delete.
    """
    try:
        docmost_delete_space(space_id)
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
        data = docmost_create_page(
            space_id=space_id,
            title=title or None,
            content=content or None,
            parent_page_id=parent_page_id or None,
        )
    except Exception as exc:
        raise ToolError(str(exc)) from exc

    page_id = data.get("id") or (data.get("page", {}) or {}).get("id")
    if not page_id:
        raise ToolError(f"Docmost create did not return a page id. Response: {data}")

    try:
        full = get_page_info(page_id)
    except Exception:
        full = data
    return _map_page_from_rest(full)


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
        docmost_update_page(
            page_id=page_id,
            title=title or None,
            content=content or None,
            operation=operation or "replace",
        )
        full = get_page_info(page_id)
    except Exception as exc:
        raise ToolError(str(exc)) from exc
    return _map_page_from_rest(full)


@mcp.tool()
def delete_page(page_id: str) -> DeletedOut:
    """Soft-delete a Docmost page (moves it to trash).

    Authentication is handled automatically.

    Args:
        page_id: UUID of the page to delete.
    """
    try:
        docmost_delete_page(page_id)
    except Exception as exc:
        raise ToolError(str(exc)) from exc
    return DeletedOut(deleted=True, id=page_id)
