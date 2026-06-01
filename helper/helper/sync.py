from __future__ import annotations

from typing import Any
from uuid import UUID

from helper.client import (
    batch_apply,
    create_snapshot,
    delete_snapshot,
    get_page,
    get_space,
    get_space_tree,
    list_pages,
)
from helper.replica import (
    clear_active_snapshot,
    extract_title_from_page,
    find_local_pages,
    page_path_from_dir,
    read_meta,
    read_page,
    record_active_snapshot,
    resolve_page_dir,
    update_meta_after_pull,
    update_meta_after_sync,
    write_meta,
    write_page,
)


def push_pages(
    space_id: UUID,
    local_paths: list[str],
    local_root: str | None = None,
) -> dict[str, Any]:
    pages_payload = []

    for local_path in local_paths:
        meta = read_meta(local_path)
        content = read_page(local_path)
        entry: dict[str, Any] = {
            "content": content,
            "local_path": local_path,
            "operation": "replace",
            "force": False,
        }
        if meta.get("id"):
            entry["page_id"] = meta["id"]

        # Title: prefer _meta.json, fall back to first heading in page.md for local-only pages
        title = meta.get("title") or extract_title_from_page(local_path)
        if title:
            entry["title"] = title

        if meta.get("base_revision_hash"):
            entry["base_revision_hash"] = meta["base_revision_hash"]
        if meta.get("parent_page_id"):
            entry["parent_page_id"] = meta["parent_page_id"]
        pages_payload.append(entry)

    result = batch_apply(space_id, pages_payload)

    for item in result.get("results", []):
        lp = item.get("local_path")
        if not lp or not item.get("applied"):
            continue
        update_meta_after_sync(lp, item, space_id=str(space_id))
        _auto_expire_stash(space_id, lp, item.get("base_revision_hash"))

    return result


def pull_pages(
    space_id: UUID,
    page_ids: list[str] | None = None,
    local_paths: list[str] | None = None,
    local_root: str | None = None,
) -> dict[str, Any]:
    remote_pages = list_pages(space_id)
    pulled: list[dict] = []
    target_ids = set(page_ids or [])

    for rp in remote_pages:
        pid = str(rp.get("page_id", ""))

        if target_ids and pid not in target_ids:
            continue

        # Determine local path:
        # If local_paths is specified, only update pages that have a matching existing path.
        # If only page_ids is specified, create new paths under local_root for unknown pages.
        if local_paths is not None:
            local_path = _find_existing_local_path(pid, local_paths)
            if local_path is None:
                continue  # caller asked for specific local files; skip pages not tracked
        else:
            root = local_root or f"./{_space_slug(space_id)}-replica"
            page_dir = resolve_page_dir(root, rp)
            local_path = page_path_from_dir(page_dir)

        page_detail = get_page(space_id, UUID(pid))
        write_page(local_path, page_detail.get("content") or "")
        update_meta_after_pull(local_path, page_detail)
        pulled.append({"page_id": pid, "local_path": local_path})

    return {"pulled_count": len(pulled), "pages": pulled}


def sync_space(
    space_id: UUID,
    local_root: str | None = None,
) -> dict[str, Any]:
    space = get_space(space_id)
    root = local_root or f"./{space.get('slug', str(space_id))}-replica"

    local_page_paths = find_local_pages(root)
    local_page_ids: dict[str, str] = {}
    for lp in local_page_paths:
        meta = read_meta(lp)
        pid = meta.get("id")
        if pid:
            local_page_ids[pid] = lp

    push_result: dict[str, Any] = {"applied_count": 0, "drifted_count": 0, "results": []}
    if local_page_paths:
        push_result = push_pages(space_id, local_page_paths)
        # Backfill local_page_ids with IDs assigned during creation of local-only pages.
        # Without this, sync_space would try to pull pages that were just created.
        for item in push_result.get("results", []):
            if item.get("applied") and item.get("page_id") and item.get("local_path"):
                local_page_ids[str(item["page_id"])] = item["local_path"]

    # Fetch remote pages once and pull only those not already tracked locally.
    remote_pages = list_pages(space_id)
    pulled: list[dict] = []
    for rp in remote_pages:
        pid = str(rp.get("page_id", ""))
        if pid in local_page_ids:
            continue
        page_detail = get_page(space_id, UUID(pid))
        page_dir = resolve_page_dir(root, rp)
        local_path = page_path_from_dir(page_dir)
        write_page(local_path, page_detail.get("content") or "")
        update_meta_after_pull(local_path, page_detail)
        pulled.append({"page_id": pid, "local_path": local_path})

    pull_result = {"pulled_count": len(pulled), "pages": pulled}

    return {"pushed": push_result, "pulled": pull_result}


def accept_remote(
    space_id: UUID,
    page_id: UUID,
    local_path: str,
    local_root: str | None = None,
) -> dict[str, Any]:
    page = get_page(space_id, page_id)
    write_page(local_path, page.get("content") or "")
    update_meta_after_pull(local_path, page)
    return {
        "page_id": str(page_id),
        "local_path": local_path,
        "current_revision_hash": page.get("current_revision_hash"),
    }


def create_stash(space_id: UUID, page_id: UUID, local_path: str) -> dict[str, Any]:
    meta = read_meta(local_path)
    content = read_page(local_path)
    base_hash = meta.get("base_revision_hash")

    result = create_snapshot(
        space_id,
        page_id,
        content=content,
        base_revision_hash=base_hash,
        local_path=local_path,
    )

    snapshot_id = str(result["snapshot_id"])
    record_active_snapshot(local_path, snapshot_id, base_hash)

    return {
        "snapshot_id": snapshot_id,
        "snapshotted_at": result.get("snapshotted_at"),
        "base_revision_hash": base_hash,
    }


def consume_stash(space_id: UUID, page_id: UUID, snapshot_id: str, local_path: str | None = None) -> None:
    delete_snapshot(space_id, page_id, snapshot_id)
    if local_path:
        meta = read_meta(local_path)
        active = meta.get("active_snapshot", {})
        if active.get("snapshot_id") == snapshot_id:
            clear_active_snapshot(local_path)


# ---------------------------------------------------------------------------
# Stash auto-expiry — version-state driven, runs after every successful push
# ---------------------------------------------------------------------------

def _auto_expire_stash(space_id: UUID, local_path: str, new_hash: str | None) -> None:
    if not new_hash:
        return
    meta = read_meta(local_path)
    active = meta.get("active_snapshot")
    if not active:
        return
    snapshot_id = active.get("snapshot_id")
    stash_hash = active.get("base_revision_hash")
    page_id = meta.get("id")
    if not snapshot_id or not page_id:
        return
    # Both sides have moved on: stash is obsolete
    if stash_hash and stash_hash != new_hash:
        try:
            delete_snapshot(space_id, UUID(page_id), snapshot_id)
            clear_active_snapshot(local_path)
        except Exception:
            pass  # best-effort; stash remains until next successful push


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_existing_local_path(page_id: str, local_paths: list[str]) -> str | None:
    for lp in local_paths:
        meta = read_meta(lp)
        if str(meta.get("id", "")) == page_id:
            return lp
    return None


def _space_slug(space_id: UUID) -> str:
    try:
        space = get_space(space_id)
        return space.get("slug", str(space_id))
    except Exception:
        return str(space_id)


def sync_page(
    space_id: UUID,
    page_id: UUID,
    local_root: str | None = None,
) -> dict[str, Any]:
    root = local_root or f"./{_space_slug(space_id)}-replica"
    local_paths = find_local_pages(root)
    lp = _find_existing_local_path(str(page_id), local_paths)
    pushed = (
        push_pages(space_id, [lp], local_root=root)
        if lp
        else {"applied_count": 0, "drifted_count": 0, "results": []}
    )
    pulled = pull_pages(space_id, page_ids=[str(page_id)], local_root=root)
    return {"page_id": str(page_id), "pushed": pushed, "pulled": pulled}


def sync_page_tree(
    space_id: UUID,
    parent_page_id: UUID,
    local_root: str | None = None,
) -> dict[str, Any]:
    root = local_root or f"./{_space_slug(space_id)}-replica"
    tree = get_space_tree(space_id)
    node = _find_node(tree.get("roots", []), str(parent_page_id))
    ids = _subtree_ids(node) if node else []
    local_paths = find_local_pages(root)
    id_to_path = {str(read_meta(p).get("id", "")): p for p in local_paths}
    push_paths = [id_to_path[i] for i in ids if i in id_to_path]
    pushed = (
        push_pages(space_id, push_paths, local_root=root)
        if push_paths
        else {"applied_count": 0, "drifted_count": 0, "results": []}
    )
    pulled = pull_pages(space_id, page_ids=ids, local_root=root) if ids else {"pulled_count": 0, "pages": []}
    return {
        "parent_page_id": str(parent_page_id),
        "synced_page_ids": ids,
        "pushed": pushed,
        "pulled": pulled,
    }


def _find_node(roots: list[dict], target_id: str) -> dict | None:
    for n in roots:
        if str(n.get("page_id", "")) == target_id:
            return n
        found = _find_node(n.get("children", []), target_id)
        if found:
            return found
    return None


def _subtree_ids(node: dict) -> list[str]:
    ids = [str(node.get("page_id", ""))]
    for c in node.get("children", []):
        ids.extend(_subtree_ids(c))
    return ids
