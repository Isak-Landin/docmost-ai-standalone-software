from __future__ import annotations

from typing import Any
from uuid import UUID

import os
import shutil

from helper.client import (
    batch_apply,
    confirm_deletion_remote,
    create_snapshot,
    delete_page as client_delete_page,
    delete_snapshot,
    get_page,
    get_space,
    get_space_tree,
    list_pages,
    observe,
    reconcile as client_reconcile,
    resolve_conflict_remote,
)
from helper.replica import (
    clear_active_snapshot,
    extract_title_from_page,
    find_local_pages,
    page_path_from_dir,
    read_meta,
    read_page,
    read_tree_snapshot,
    record_active_snapshot,
    resolve_local_root,
    resolve_page_dir,
    split_leading_h1,
    update_meta_after_pull,
    update_meta_after_sync,
    write_meta,
    write_page,
    write_replica_header,
    write_tree_snapshot,
)


def _title_and_body(local_path: str, meta: dict[str, Any]) -> tuple[str | None, str]:
    """Resolve a page's title and the body to send. A tracked page keeps its helper-owned
    _meta.json title and full body. For a local-only page with no recorded title, a leading
    '# H1' is lifted into the title AND stripped from the body, so Docmost never renders the
    title plus a duplicate H1; if there is no leading H1 the first line is used as the title
    (legacy fallback) and the body is left intact."""
    raw = read_page(local_path)
    if meta.get("title"):
        return meta["title"], raw
    h1_title, body = split_leading_h1(raw)
    if h1_title:
        return h1_title, body
    return extract_title_from_page(local_path), raw


def push_pages(
    space_id: UUID,
    local_paths: list[str],
    local_root: str | None = None,
) -> dict[str, Any]:
    pages_payload = []

    for local_path in local_paths:
        meta = read_meta(local_path)
        title, content = _title_and_body(local_path, meta)
        entry: dict[str, Any] = {
            "content": content,
            "local_path": local_path,
            "operation": "replace",
            "force": False,
        }
        if meta.get("id"):
            entry["page_id"] = meta["id"]
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
    root = resolve_local_root(str(space_id), slug=space.get("slug"), local_root=local_root)
    write_replica_header(root, str(space_id), slug=space.get("slug"), name=space.get("name"))
    return _reconcile_sync(space_id, root, scope="space", scope_id=None)


def resync_space(
    space_id: UUID,
    local_root: str | None = None,
) -> dict[str, Any]:
    """Re-anchor + reconcile a whole space. Unlike sync_space, this first re-renders EVERY page
    on the server from Docmost's current content - even pages whose stored content did not change
    - so an egress-renderer change propagates. It then runs the SAME two-way reconcile: a page
    whose only difference is the corrected render heals as a pull (no content surfaced); a page
    with un-pushed local edits surfaces as a conflict. It never force-pushes, so it cannot corrupt
    a page by sending stale local markdown. Returns the normal sync summary plus reanchored_count
    (pages whose server-side render changed this run)."""
    space = get_space(space_id)
    root = resolve_local_root(str(space_id), slug=space.get("slug"), local_root=local_root)
    write_replica_header(root, str(space_id), slug=space.get("slug"), name=space.get("name"))
    # Re-anchor every head server-side from Docmost (no local files touched here).
    observed = observe(space_id, force_rerender=True)
    # Then the normal reconcile pass applies any heal-pulls locally and surfaces real clashes.
    result = _reconcile_sync(space_id, root, scope="space", scope_id=None)
    result["reanchored_count"] = observed.get("reanchored_count", 0)
    return result


def _reconcile_sync(
    space_id: UUID,
    root: str,
    scope: str,
    scope_id: UUID | None,
    include_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Build the local payload, call the server reconcile brain, apply the result locally,
    and return the model-facing summary (only conflicts and deletions carry content)."""
    pages, tree = _build_reconcile_payload(root, include_ids=include_ids)
    result = client_reconcile(space_id, scope, scope_id, pages, tree)
    # Apply first: this is where the canonical content is written to the local replica files.
    _apply_reconcile_result(root, space_id, result)
    # Model-facing summary: clean items carry metadata only. Page content is deliberately
    # omitted from applied[] (it was already written to the local replica) so a clean sync
    # does not flood the model's context. Only conflicts (remote/local content + diff) and
    # errors carry content, because those need a decision.
    applied = [{k: v for k, v in item.items() if k != "content"} for item in result.get("applied", [])]
    return {
        "scope": result.get("scope"),
        "synced_count": len(result.get("synced", [])),  # pages ALREADY in sync (unchanged this run)
        "applied_count": len(applied),                   # pages changed this run
        "applied": applied,                              # metadata only; page content omitted
        "conflicts": result.get("conflicts", []),        # carry remote_content/local_content/diff
        "deletion_confirmations": result.get("deletion_confirmations", []),
        "errors": result.get("errors", []),
    }


def _id_by_dir(local_paths: list[str]) -> dict[str, str]:
    """Map each page directory (absolute) to its tracked page id."""
    mapping: dict[str, str] = {}
    for lp in local_paths:
        pid = read_meta(lp).get("id")
        if pid:
            mapping[os.path.abspath(os.path.dirname(lp))] = str(pid)
    return mapping


def _nearest_ancestor(local_path: str, dir_map: dict[str, Any], root: str) -> Any:
    """Walk up the page dir's ancestors; return the first ancestor that is itself a page dir."""
    root_abs = os.path.abspath(root)
    cur = os.path.dirname(os.path.dirname(os.path.abspath(local_path)))  # the page dir's parent dir
    while True:
        if cur in dir_map:
            return dir_map[cur]
        if cur == root_abs or cur == os.path.dirname(cur):
            return None
        cur = os.path.dirname(cur)


def _local_parent_id(local_path: str, id_by_dir: dict[str, str], root: str) -> str | None:
    """Derive a page's parent id from the local directory nesting (the model moves dirs, not _meta)."""
    return _nearest_ancestor(local_path, id_by_dir, root)


def _path_by_dir(local_paths: list[str]) -> dict[str, str]:
    return {os.path.abspath(os.path.dirname(lp)): lp for lp in local_paths}


def _build_reconcile_payload(root: str, include_ids: set[str] | None = None) -> tuple[list[dict], list[dict]]:
    local_paths = find_local_pages(root)
    id_by_dir = _id_by_dir(local_paths)
    path_by_dir = _path_by_dir(local_paths)
    pages: list[dict[str, Any]] = []
    for lp in local_paths:
        meta = read_meta(lp)
        pid = meta.get("id")
        if include_ids is not None and (pid is None or str(pid) not in include_ids):
            continue
        title, body = _title_and_body(lp, meta)
        entry: dict[str, Any] = {"content": body, "local_path": lp}
        if title:
            entry["title"] = title
        if pid:
            entry["page_id"] = str(pid)
        if meta.get("base_revision_hash"):
            entry["base_revision_hash"] = meta["base_revision_hash"]
        parent = _local_parent_id(lp, id_by_dir, root)
        if parent:
            entry["parent_page_id"] = parent
        parent_path = _nearest_ancestor(lp, path_by_dir, root)
        if parent_path:
            entry["parent_local_path"] = parent_path
        if meta.get("position") is not None:
            entry["position"] = meta["position"]
        if meta.get("icon") is not None:
            entry["icon"] = meta["icon"]
        pages.append(entry)
    tree = [
        {
            "page_id": str(n["page_id"]),
            "parent_page_id": str(n["parent_page_id"]) if n.get("parent_page_id") else None,
            "position": n.get("position"),
            "icon": n.get("icon"),
        }
        for n in read_tree_snapshot(root).get("pages", [])
        if n.get("page_id")
    ]
    return pages, tree


def _apply_reconcile_result(root: str, space_id: UUID, result: dict[str, Any]) -> None:
    for item in result.get("applied", []):
        try:
            _apply_applied_item(root, space_id, item)
        except Exception:
            pass  # best-effort; per-page failures are surfaced in result["errors"]
    for item in result.get("synced", []):
        try:
            _refresh_synced_base(root, item)
        except Exception:
            pass
    write_tree_snapshot(root, _current_tree_entries(root))


def _refresh_synced_base(root: str, item: dict[str, Any]) -> None:
    """Keep the local base aligned with the head even when nothing changed, so a later
    remote-only change is classified as remote-ahead (a pull), never as a spurious conflict."""
    base = item.get("base_revision_hash")
    if not base:
        return
    lp = _find_existing_local_path(str(item["page_id"]), find_local_pages(root))
    if not lp:
        return
    meta = read_meta(lp)
    if meta.get("base_revision_hash") != base:
        meta["base_revision_hash"] = base
        write_meta(lp, meta)


def _apply_applied_item(root: str, space_id: UUID, item: dict[str, Any]) -> None:
    pid = str(item["page_id"])
    content = item.get("content")
    local_path = item.get("local_path") or _find_existing_local_path(pid, find_local_pages(root))
    if local_path is None:
        # Remote-only page (pulled/materialized): place it under its parent's local dir.
        local_path = _materialize_local_path(root, item)
    else:
        # Existing page: relocate its dir if the remote parent differs from the local nesting.
        local_path = _relocate_if_needed(root, local_path, item)
    if content is not None:
        write_page(local_path, content)
    _write_meta_from_item(local_path, space_id, item)


def _relocate_if_needed(root: str, local_path: str, item: dict[str, Any]) -> str:
    local_paths = find_local_pages(root)
    id_by_dir = _id_by_dir(local_paths)
    parent_id = item.get("parent_page_id")
    current_parent = _local_parent_id(local_path, id_by_dir, root)
    if str(current_parent or "") == str(parent_id or ""):
        return local_path  # local nesting already matches the remote parent
    desired_parent_dir = root
    if parent_id:
        pp = _find_existing_local_path(str(parent_id), local_paths)
        if pp is None:
            return local_path  # parent not materialized locally yet; leave for a later pass
        desired_parent_dir = os.path.dirname(pp)
    cur_dir = os.path.dirname(local_path)
    new_dir = os.path.join(desired_parent_dir, os.path.basename(cur_dir))
    if os.path.abspath(new_dir) == os.path.abspath(cur_dir):
        return local_path
    os.makedirs(desired_parent_dir, exist_ok=True)
    shutil.move(cur_dir, new_dir)
    return page_path_from_dir(new_dir)


def _materialize_local_path(root: str, item: dict[str, Any]) -> str:
    parent_dir = root
    parent_id = item.get("parent_page_id")
    if parent_id:
        pp = _find_existing_local_path(str(parent_id), find_local_pages(root))
        if pp:
            parent_dir = os.path.dirname(pp)
    page_dir = resolve_page_dir(
        parent_dir,
        {"title": item.get("title"), "slug_id": item.get("slug_id"), "page_id": item["page_id"]},
    )
    return page_path_from_dir(page_dir)


def _write_meta_from_item(local_path: str, space_id: UUID, item: dict[str, Any]) -> None:
    meta = read_meta(local_path)
    meta["id"] = str(item["page_id"])
    if item.get("title") is not None:
        meta["title"] = item["title"]
    if item.get("slug_id") is not None:
        meta["slug_id"] = item["slug_id"]
    meta["space_id"] = str(space_id)
    meta["parent_page_id"] = str(item["parent_page_id"]) if item.get("parent_page_id") else None
    if item.get("position") is not None:
        meta["position"] = item["position"]
    if item.get("icon") is not None:
        meta["icon"] = item["icon"]
    if item.get("base_revision_hash"):
        meta["base_revision_hash"] = item["base_revision_hash"]
    meta["content_file_path"] = local_path
    meta["meta_file_path"] = os.path.join(os.path.dirname(local_path), "_meta.json")
    write_meta(local_path, meta)


def _current_tree_entries(root: str) -> list[dict[str, Any]]:
    """Snapshot every tracked local page (id, parent, position, icon) for next-sync diffing.
    Parent is derived from directory nesting so a moved dir is detected on the next sync."""
    local_paths = find_local_pages(root)
    id_by_dir = _id_by_dir(local_paths)
    entries: list[dict[str, Any]] = []
    for lp in local_paths:
        meta = read_meta(lp)
        pid = meta.get("id")
        if not pid:
            continue
        entries.append(
            {
                "page_id": str(pid),
                "parent_page_id": _local_parent_id(lp, id_by_dir, root),
                "position": meta.get("position"),
                "icon": meta.get("icon"),
                "local_path": lp,
            }
        )
    return entries


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
    try:
        delete_snapshot(space_id, page_id, snapshot_id)
    except Exception:
        pass  # snapshot may already have been auto-expired by a successful push
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
    space = get_space(space_id)
    root = resolve_local_root(str(space_id), slug=space.get("slug"), local_root=local_root)
    return _reconcile_sync(space_id, root, scope="page", scope_id=page_id, include_ids={str(page_id)})


def sync_page_tree(
    space_id: UUID,
    parent_page_id: UUID,
    local_root: str | None = None,
) -> dict[str, Any]:
    space = get_space(space_id)
    root = resolve_local_root(str(space_id), slug=space.get("slug"), local_root=local_root)
    tree = get_space_tree(space_id)
    node = _find_node(tree.get("roots", []), str(parent_page_id))
    ids = set(_subtree_ids(node)) if node else {str(parent_page_id)}
    return _reconcile_sync(space_id, root, scope="tree", scope_id=parent_page_id, include_ids=ids)


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


def resolve_conflict(
    space_id: UUID,
    page_id: UUID,
    merged_content: str,
    local_root: str | None = None,
) -> dict[str, Any]:
    space = get_space(space_id)
    root = resolve_local_root(str(space_id), slug=space.get("slug"), local_root=local_root)
    lp = _find_existing_local_path(str(page_id), find_local_pages(root))
    if not lp:
        return {"page_id": str(page_id), "resolved": False, "error": "page not found in local replica"}
    title = read_meta(lp).get("title")
    stash = create_stash(space_id, page_id, lp)
    # Server pushes merged_content aligned to the CURRENT remote head (no force).
    res = resolve_conflict_remote(space_id, page_id, merged_content, title=title)
    resolved_content = res.get("content") if res.get("content") is not None else merged_content
    write_page(lp, resolved_content)
    meta = read_meta(lp)
    if res.get("base_revision_hash"):
        meta["base_revision_hash"] = res["base_revision_hash"]
    write_meta(lp, meta)
    consume_stash(space_id, page_id, stash["snapshot_id"], local_path=lp)
    write_tree_snapshot(root, _current_tree_entries(root))
    return {
        "page_id": str(page_id),
        "resolved": bool(res.get("resolved")),
        "base_revision_hash": res.get("base_revision_hash"),
        "snapshot_id": stash.get("snapshot_id"),
    }


def confirm_deletion(
    space_id: UUID,
    page_id: UUID,
    direction: str,
    local_root: str | None = None,
) -> dict[str, Any]:
    space = get_space(space_id)
    root = resolve_local_root(str(space_id), slug=space.get("slug"), local_root=local_root)
    lp = _find_existing_local_path(str(page_id), find_local_pages(root))
    res = confirm_deletion_remote(space_id, page_id, direction)
    result: dict[str, Any] = {
        "page_id": str(page_id),
        "direction": direction,
        "remote_deleted": bool(res.get("remote_deleted")),
    }
    if lp:
        _remove_local_page(lp)
        result["local_removed"] = True
    write_tree_snapshot(root, _current_tree_entries(root))
    return result


def _remove_local_page(local_path: str) -> None:
    meta = os.path.join(os.path.dirname(local_path), "_meta.json")
    for f in (local_path, meta):
        try:
            os.remove(f)
        except FileNotFoundError:
            pass
