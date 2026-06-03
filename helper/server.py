from __future__ import annotations

import sys
import os

# Allow importing the helper package from the same directory
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from typing import Optional
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from helper import client, sync

_EXPECTED_CONTRACT = "1"
try:
    _contract = client.get_contract()
    if str(_contract.get("contract_version")) != _EXPECTED_CONTRACT:
        print(
            f"WARNING: docmost server contract {_contract.get('contract_version')} != expected {_EXPECTED_CONTRACT}",
            file=sys.stderr,
        )
except Exception as _exc:  # handshake is best-effort; the helper still starts
    print(f"WARNING: docmost contract handshake failed: {_exc}", file=sys.stderr)

mcp = FastMCP(
    "docmost-helper",
    instructions=(
        "Client-side helper for Docmost. This stdio MCP is the model's ONLY Docmost surface — "
        "use it for all reads, writes, and sync. Never call the server-side docmost-mcp /mcp HTTP "
        "surface; that is an operator-only inspection fallback. The helper reaches the server over "
        "REST (/v1, /helper/v1, /auto-mcp).\n\n"
        "Normal work is reconcile-first: edit page.md locally (and/or move page directories to "
        "restructure), then call sync_space(space_id) — or sync_page / sync_page_tree — with only "
        "the id. The helper diffs, versions, and applies push/create/pull/move automatically, and "
        "returns synced_count + applied plus only the items needing a decision: conflicts and "
        "deletion_confirmations. Resolve a conflict with resolve_conflict(space_id, page_id, "
        "merged_content); apply a deletion with confirm_deletion(space_id, page_id, direction). Ask "
        "the user when a merge or deletion is unclear. Never force.\n\n"
        "create_page / update_page / delete_page / move_page / push_pages / pull_pages / "
        "accept_remote and the stash tools are low-level escape hatches, not the normal path. "
        "Content is markdown; the page title is a separate parameter (never an H1 in the body); "
        "use plain ASCII punctuation."
    ),
)


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_spaces() -> list[dict]:
    """List all Docmost spaces."""
    return client.list_spaces()


@mcp.tool()
def get_space(space_id: str) -> dict:
    """Get a single Docmost space by UUID."""
    return client.get_space(UUID(space_id))


@mcp.tool()
def get_space_tree(space_id: str) -> dict:
    """Get the full page hierarchy for a space."""
    return client.get_space_tree(UUID(space_id))


@mcp.tool()
def list_pages(space_id: str) -> list[dict]:
    """List all pages in a Docmost space."""
    return client.list_pages(UUID(space_id))


@mcp.tool()
def get_page(space_id: str, page_id: str) -> dict:
    """Get a single page with markdown content and current revision hash."""
    return client.get_page(UUID(space_id), UUID(page_id))


# ---------------------------------------------------------------------------
# Write tools — spaces
# ---------------------------------------------------------------------------

@mcp.tool()
def create_space(name: str, slug: str) -> dict:
    """Create a new Docmost space. slug must be alphanumeric, no dashes."""
    return client.create_space(name, slug)


@mcp.tool()
def delete_space(space_id: str) -> None:
    """Permanently delete a space and all its pages. Irreversible."""
    client.delete_space(UUID(space_id))


# ---------------------------------------------------------------------------
# Write tools — pages
# ---------------------------------------------------------------------------

@mcp.tool()
def create_page(
    space_id: str,
    title: str,
    content: Optional[str] = None,
    parent_page_id: Optional[str] = None,
) -> dict:
    """Create a new page in a Docmost space."""
    return client.create_page(
        UUID(space_id),
        title=title,
        content=content,
        parent_page_id=UUID(parent_page_id) if parent_page_id else None,
    )


@mcp.tool()
def update_page(
    space_id: str,
    page_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    operation: str = "replace",
    base_revision_hash: Optional[str] = None,
    force: bool = False,
) -> dict:
    """Update a page's title and/or content. operation: replace | append | prepend."""
    return client.update_page(
        UUID(space_id),
        UUID(page_id),
        title=title,
        content=content,
        operation=operation,
        base_revision_hash=base_revision_hash,
        force=force,
    )


@mcp.tool()
def delete_page(space_id: str, page_id: str) -> None:
    """Delete a page. Moves it to Docmost trash."""
    client.delete_page(UUID(space_id), UUID(page_id))


@mcp.tool()
def move_page(space_id: str, page_id: str, position: str, parent_page_id: Optional[str] = None) -> dict:
    """Move/re-parent a page (id-preserving). position is a fractional-index string among the target siblings; pass parent_page_id to re-parent or omit to reorder."""
    return client.move_page(UUID(space_id), UUID(page_id), position, UUID(parent_page_id) if parent_page_id else None)


# ---------------------------------------------------------------------------
# Sync tools
# ---------------------------------------------------------------------------

@mcp.tool()
def sync_space(space_id: str, local_root: Optional[str] = None) -> dict:
    """Full bidirectional reconcile for a whole space in one pass. Pass ONLY the space id.
    The helper does everything automatically: pushes local edits, creates local-only pages,
    pulls remote changes, materializes new remote pages, applies moves/re-parents, and keeps
    local + remote versions aligned. Returns synced_count plus only the items needing YOUR
    decision: `conflicts` (each with remote_content, local_content, diff) and
    `deletion_confirmations`. For a conflict call resolve_conflict; for a deletion call
    confirm_deletion. If a resolution or deletion is unclear, ask the user. Never force."""
    return sync.sync_space(UUID(space_id), local_root=local_root)


@mcp.tool()
def sync_page(space_id: str, page_id: str, local_root: Optional[str] = None) -> dict:
    """Reconcile a single page by id (same automated full-fidelity reconcile as sync_space,
    scoped to one page). Returns synced_count, applied, conflicts, deletion_confirmations."""
    return sync.sync_page(UUID(space_id), UUID(page_id), local_root=local_root)


@mcp.tool()
def sync_page_tree(space_id: str, parent_page_id: str, local_root: Optional[str] = None) -> dict:
    """Reconcile a page subtree by parent id (the parent plus all descendants), full-fidelity
    and automated. Returns synced_count, applied, conflicts, deletion_confirmations."""
    return sync.sync_page_tree(UUID(space_id), UUID(parent_page_id), local_root=local_root)


@mcp.tool()
def resolve_conflict(space_id: str, page_id: str, merged_content: str, local_root: Optional[str] = None) -> dict:
    """Resolve a conflict surfaced by a sync. The server pushes your merged_content aligned to
    the CURRENT remote head (no force), then the helper writes it locally and re-aligns the base.
    Provide the final merged markdown; ask the user first if the right merge is unclear."""
    return sync.resolve_conflict(UUID(space_id), UUID(page_id), merged_content, local_root=local_root)


@mcp.tool()
def confirm_deletion(space_id: str, page_id: str, direction: str, local_root: Optional[str] = None) -> dict:
    """Confirm a deletion surfaced by a sync. direction='remote' soft-deletes the remote page and
    drops the local copy; direction='local' accepts a remote deletion by dropping the local copy.
    Sync never deletes on its own — ask the user if a deletion is unexpected."""
    return sync.confirm_deletion(UUID(space_id), UUID(page_id), direction, local_root=local_root)


@mcp.tool()
def push_pages(
    space_id: str,
    local_paths: list[str],
    local_root: Optional[str] = None,
) -> dict:
    """Push specific local pages to Docmost via the bridge write pipeline.
    Returns applied and drifted pages together in results[]. Check applied=False / action='drifted' for conflicts."""
    return sync.push_pages(UUID(space_id), local_paths=local_paths, local_root=local_root)


@mcp.tool()
def pull_pages(
    space_id: str,
    page_ids: Optional[list[str]] = None,
    local_paths: Optional[list[str]] = None,
    local_root: Optional[str] = None,
) -> dict:
    """Pull remote pages and write them to the local replica.
    Use page_ids to pull specific remote pages (creating new local files if needed).
    Use local_paths to refresh existing tracked local pages from remote."""
    return sync.pull_pages(
        UUID(space_id),
        page_ids=page_ids,
        local_paths=local_paths,
        local_root=local_root,
    )


@mcp.tool()
def accept_remote(
    space_id: str,
    page_id: str,
    local_path: str,
    local_root: Optional[str] = None,
) -> dict:
    """Overwrite local page.md and _meta.json with the current remote version.
    Use during conflict resolution after stash_page has saved local content."""
    return sync.accept_remote(
        UUID(space_id),
        UUID(page_id),
        local_path=local_path,
        local_root=local_root,
    )


# ---------------------------------------------------------------------------
# Stash tools
# ---------------------------------------------------------------------------

@mcp.tool()
def stash_page(space_id: str, page_id: str, local_path: str) -> dict:
    """Save current local page.md as a server-side snapshot before overwriting.
    Updates _meta.json with active_snapshot tracking for auto-expiry.
    Returns snapshot_id — hold this for the duration of conflict resolution."""
    return sync.create_stash(UUID(space_id), UUID(page_id), local_path)


@mcp.tool()
def get_stash(space_id: str, page_id: str, snapshot_id: str) -> dict:
    """Retrieve a previously stashed page snapshot by snapshot_id."""
    return client.get_snapshot(UUID(space_id), UUID(page_id), snapshot_id)


@mcp.tool()
def clear_stash(space_id: str, page_id: str, snapshot_id: str, local_path: Optional[str] = None) -> None:
    """Mark a snapshot as consumed and remove active_snapshot tracking from _meta.json.
    Call after conflict resolution is complete. Pass local_path to clean up _meta.json."""
    sync.consume_stash(UUID(space_id), UUID(page_id), snapshot_id, local_path=local_path)


if __name__ == "__main__":
    mcp.run()
