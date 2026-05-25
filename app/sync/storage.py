from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from app.models import ReplicaStructureOut, ReplicaTreeNode
from app.sync.config import absolute_path_to_logical, logical_path_to_absolute
from app.sync.diffing import canonicalize_content
from app.sync.models import (
    CANONICAL_REPLICA_GENERATED_FROM,
    LocalReplicaPaths,
    LocalReplicaScan,
    ReplicaPageState,
    ReplicaSpaceState,
    SYNC_FILE_NAME,
)


def get_local_replica_paths(replica_structure: ReplicaStructureOut) -> LocalReplicaPaths:
    root_path = logical_path_to_absolute(replica_structure.replica_root)
    return LocalReplicaPaths(
        root_path=root_path,
        replica_meta_path=logical_path_to_absolute(replica_structure.replica_meta_file_path),
        replica_sync_path=root_path / SYNC_FILE_NAME,
        tree_cache_path=logical_path_to_absolute(replica_structure.tree_cache_file_path),
    )


def scan_local_replica(replica_structure: ReplicaStructureOut) -> LocalReplicaScan:
    paths = get_local_replica_paths(replica_structure)
    replica_state = _read_replica_state(paths.replica_meta_path, paths.replica_sync_path)
    page_metas: list[ReplicaPageState] = []
    page_meta_by_id: dict[UUID, ReplicaPageState] = {}
    page_meta_by_content_path: dict[str, ReplicaPageState] = {}

    if paths.root_path.exists():
        for meta_path in sorted(paths.root_path.rglob(replica_structure.standards.page_meta_file_name)):
            page_state = _read_page_state(meta_path)
            page_metas.append(page_state)
            if page_state.page_id is not None:
                page_meta_by_id[page_state.page_id] = page_state
            page_meta_by_content_path[page_state.content_file_path] = page_state

    return LocalReplicaScan(
        replica_state=replica_state,
        page_metas=page_metas,
        page_meta_by_id=page_meta_by_id,
        page_meta_by_content_path=page_meta_by_content_path,
        root_exists=paths.root_path.exists(),
    )


def read_local_content(content_path: str) -> tuple[bool, str | None]:
    abs_path = logical_path_to_absolute(content_path)
    if not abs_path.exists():
        return False, None
    return True, abs_path.read_text(encoding="utf-8")


def write_replica_state(
    replica_structure: ReplicaStructureOut,
    *,
    last_pulled_at: datetime | None = None,
    last_pushed_at: datetime | None = None,
) -> None:
    paths = get_local_replica_paths(replica_structure)
    paths.root_path.mkdir(parents=True, exist_ok=True)

    existing = _read_replica_state(paths.replica_meta_path, paths.replica_sync_path)
    state = ReplicaSpaceState(
        space_id=replica_structure.space.id,
        space_name=replica_structure.space.name,
        space_slug=replica_structure.space.slug,
        replica_root=replica_structure.replica_root,
        last_pulled_at=last_pulled_at if last_pulled_at is not None else (existing.last_pulled_at if existing else None),
        last_pushed_at=last_pushed_at if last_pushed_at is not None else (existing.last_pushed_at if existing else None),
        updated_at=_utcnow(),
    )
    _write_json(paths.replica_meta_path, _canonical_replica_meta(replica_structure))
    _write_json(paths.replica_sync_path, _canonical_replica_sync(state))
    _write_json(paths.tree_cache_path, _canonical_tree_cache(replica_structure))


def write_remote_page_snapshot(
    replica_structure: ReplicaStructureOut,
    node: ReplicaTreeNode,
    *,
    content: str,
    title: str | None,
    slug_id: str | None,
    parent_page_id: UUID | None,
    base_content_hash: str,
    remote_updated_at: datetime | None,
) -> ReplicaPageState:
    write_content_file(node.content_file_path, content)

    page_state = ReplicaPageState(
        page_id=node.id,
        space_id=replica_structure.space.id,
        title=title,
        slug_id=slug_id,
        parent_page_id=parent_page_id,
        local_dir_path=node.local_dir_path,
        content_file_path=node.content_file_path,
        meta_file_path=node.meta_file_path,
        base_content_hash=base_content_hash,
        last_sync_at=_utcnow(),
        last_sync_remote_updated_at=remote_updated_at,
        last_sync_title=title,
    )
    _write_page_files(page_state)
    return page_state


def write_page_state(page_state: ReplicaPageState) -> ReplicaPageState:
    _write_page_files(page_state)
    return page_state


def write_content_file(content_file_path: str, content: str) -> None:
    content_abs_path = logical_path_to_absolute(content_file_path)
    content_abs_path.parent.mkdir(parents=True, exist_ok=True)
    content_abs_path.write_text(canonicalize_content(content), encoding="utf-8")


def flatten_replica_nodes(replica_structure: ReplicaStructureOut) -> dict[UUID, ReplicaTreeNode]:
    nodes: dict[UUID, ReplicaTreeNode] = {}
    for node in replica_structure.root_pages + replica_structure.orphan_pages:
        _walk_node(node, nodes)
    return nodes


def _walk_node(node: ReplicaTreeNode, nodes: dict[UUID, ReplicaTreeNode]) -> None:
    nodes[node.id] = node
    for child in node.children:
        _walk_node(child, nodes)


def _read_replica_state(meta_path: Path, sync_path: Path) -> ReplicaSpaceState | None:
    if not meta_path.exists() and not sync_path.exists():
        return None

    meta_payload = _read_json(meta_path) if meta_path.exists() else {}
    sync_payload = _read_json(sync_path) if sync_path.exists() else {}

    space_block = meta_payload.get("space") or {}
    return ReplicaSpaceState(
        space_id=space_block.get("id") or meta_payload.get("space_id"),
        space_name=space_block.get("name") or meta_payload.get("space_name") or meta_payload.get("name"),
        space_slug=space_block.get("slug") or meta_payload.get("space_slug") or meta_payload.get("slug"),
        replica_root=meta_payload.get("replica_root") or meta_payload.get("replicaRoot") or "",
        last_pulled_at=_coerce_datetime(sync_payload.get("last_pulled_at") or meta_payload.get("last_pulled_at")),
        last_pushed_at=_coerce_datetime(sync_payload.get("last_pushed_at") or meta_payload.get("last_pushed_at")),
        updated_at=_coerce_datetime(sync_payload.get("updated_at") or meta_payload.get("updated_at")) or _utcnow(),
    )


def _read_page_state(path: Path) -> ReplicaPageState:
    meta_payload = _read_json(path)
    sync_path = path.parent / SYNC_FILE_NAME
    sync_payload = _read_json(sync_path) if sync_path.exists() else {}

    page_id = meta_payload.get("id") or meta_payload.get("page_id")
    local_dir = meta_payload.get("local_dir")
    content_file_name = meta_payload.get("content_file")
    content_file_path = meta_payload.get("content_file_path")
    if content_file_path is None and local_dir and content_file_name:
        content_file_path = f"{local_dir.rstrip('/')}/{content_file_name}"
    if content_file_path is None:
        content_file_path = absolute_path_to_logical(path.parent / "page.md")

    meta_file_path = meta_payload.get("meta_file_path") or absolute_path_to_logical(path)

    return ReplicaPageState(
        page_id=page_id,
        space_id=meta_payload.get("space_id"),
        title=meta_payload.get("title"),
        slug_id=meta_payload.get("slug_id"),
        parent_page_id=meta_payload.get("parent_page_id"),
        local_dir_path=absolute_path_to_logical(path.parent),
        content_file_path=content_file_path,
        meta_file_path=meta_file_path,
        base_content_hash=sync_payload.get("base_content_hash") or meta_payload.get("base_content_hash"),
        last_sync_at=_coerce_datetime(sync_payload.get("last_sync_at") or meta_payload.get("last_sync_at")),
        last_sync_remote_updated_at=_coerce_datetime(sync_payload.get("last_sync_remote_updated_at") or meta_payload.get("last_sync_remote_updated_at") or meta_payload.get("replica_fetched_at")),
        last_sync_title=sync_payload.get("last_sync_title") or meta_payload.get("last_sync_title") or meta_payload.get("title"),
    )


def _write_page_files(page_state: ReplicaPageState) -> None:
    meta_abs_path = logical_path_to_absolute(page_state.meta_file_path)
    sync_abs_path = meta_abs_path.parent / SYNC_FILE_NAME
    _write_json(meta_abs_path, _canonical_page_meta(page_state))
    _write_json(sync_abs_path, _canonical_page_sync(page_state))


def _canonical_replica_meta(replica_structure: ReplicaStructureOut) -> dict[str, Any]:
    return {
        "space": replica_structure.space.model_dump(mode="json"),
        "replica_root": replica_structure.replica_root,
        "page_content_file_name": replica_structure.standards.page_content_file_name,
        "page_meta_file_name": replica_structure.standards.page_meta_file_name,
        "tree_cache_file_name": replica_structure.standards.tree_cache_file_name,
        "generated_from": CANONICAL_REPLICA_GENERATED_FROM,
    }


def _canonical_replica_sync(state: ReplicaSpaceState) -> dict[str, Any]:
    return {
        "space_id": state.space_id,
        "last_pulled_at": state.last_pulled_at,
        "last_pushed_at": state.last_pushed_at,
        "updated_at": state.updated_at,
    }


def _canonical_tree_cache(replica_structure: ReplicaStructureOut) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "space": replica_structure.space.model_dump(mode="json"),
        "replica_root": replica_structure.replica_root,
        "root_pages": [_canonical_tree_node(node) for node in replica_structure.root_pages],
    }
    if replica_structure.orphan_pages:
        payload["orphan_pages"] = [_canonical_tree_node(node) for node in replica_structure.orphan_pages]
    return payload


def _canonical_tree_node(node: ReplicaTreeNode) -> dict[str, Any]:
    return {
        "id": node.id,
        "title": node.title,
        "content_file_path": node.content_file_path,
        "meta_file_path": node.meta_file_path,
        "children": [_canonical_tree_node(child) for child in node.children],
    }


def _canonical_page_meta(page_state: ReplicaPageState) -> dict[str, Any]:
    return {
        "id": page_state.page_id,
        "title": page_state.title,
        "slug_id": page_state.slug_id,
        "parent_page_id": page_state.parent_page_id,
        "space_id": page_state.space_id,
        "content_file_path": page_state.content_file_path,
        "meta_file_path": page_state.meta_file_path,
    }


def _canonical_page_sync(page_state: ReplicaPageState) -> dict[str, Any]:
    return {
        "page_id": page_state.page_id,
        "base_content_hash": page_state.base_content_hash,
        "last_sync_at": page_state.last_sync_at,
        "last_sync_remote_updated_at": page_state.last_sync_remote_updated_at,
        "last_sync_title": page_state.last_sync_title,
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    return None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n", encoding="utf-8")


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
