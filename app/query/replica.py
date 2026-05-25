from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional
from uuid import UUID

from app.query.docmost import get_space_tree
from app.models import (
    PageTreeNode,
    ReplicaNameResolutionOut,
    ReplicaStandardsOut,
    ReplicaStructureOut,
    ReplicaTreeNode,
)

PAGE_CONTENT_FILE_NAME = "page.md"
PAGE_META_FILE_NAME = "_meta.json"
REPLICA_META_FILE_NAME = "_replica.json"
TREE_CACHE_FILE_NAME = "_tree.json"
REPLICA_ROOT_SUFFIX = "-replica"

_INVALID_PATH_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE_RE = re.compile(r"\s+")
_MULTI_DASH_RE = re.compile(r"-{2,}")
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def _sanitize_path_component(value: Optional[str]) -> str:
    text = (value or "").strip()
    if not text:
        text = "Untitled"
    text = _INVALID_PATH_CHARS_RE.sub("-", text)
    text = _WHITESPACE_RE.sub("-", text)
    text = _MULTI_DASH_RE.sub("-", text)
    text = text.strip().rstrip("-.")
    if not text or text in {".", ".."}:
        text = "Untitled"
    if text.upper() in _WINDOWS_RESERVED_NAMES:
        text = f"_{text}"
    return text


def _space_replica_root(space_name: Optional[str]) -> str:
    return f"./{_sanitize_path_component(space_name)}{REPLICA_ROOT_SUFFIX}"


def get_replica_standards() -> ReplicaStandardsOut:
    return ReplicaStandardsOut(
        replica_root_suffix=REPLICA_ROOT_SUFFIX,
        replica_root_example=f"./tool-ai-gateway{REPLICA_ROOT_SUFFIX}",
        page_directory_base_rule="Use the filesystem-safe page title as the base directory name. Spaces are replaced with hyphens; no spaces are allowed in any local directory or file name.",
        sibling_collision_rule="If sibling pages resolve to the same base directory name, append `__{slug_id}` to every page in that collision set.",
        final_collision_fallback_rule="If `slug_id` is missing or still collides, append `__{short_page_id}`.",
        page_content_file_name=PAGE_CONTENT_FILE_NAME,
        page_meta_file_name=PAGE_META_FILE_NAME,
        replica_meta_file_name=REPLICA_META_FILE_NAME,
        tree_cache_file_name=TREE_CACHE_FILE_NAME,
        initial_replica_source_rule="Use `get_replica_structure(space_id, local_root?)` to get the exact client-local replica layout, then let the client create or update those files locally.",
        local_addition_source_rule="Use `create_local_replica_page(space_id, ..., local_root?, existing_dir_names=...)` to get a canonical local-only page scaffold plan. The client writes the returned files locally.",
        local_replica_requirement="Maintain a local-first replica in the working copy you are editing. The client owns local file IO; the server only returns canonical path planning and sync decisions.",
        read_source_policy="Read remote Docmost first when there is no newer local replica state.",
        local_edit_policy="Apply requested documentation edits in the selected client-local working copy. Keep canonical replica descriptors in `_replica.json`, `_tree.json`, and `_meta.json`, and let the client store any local sync-base metadata it needs.",
        local_truth_policy="If newer client-local replica changes exist, report them through sync status and diff outputs instead of assuming either side should win automatically.",
        remote_sync_policy="When local and remote diverge, compute their differences programmatically against live Docmost pages and return all clashes before any forced overwrite.",
        edited_replica_reporting_rule="When local replica files are edited, `get_sync_status` should report which client-local pages changed, how they map to remote pages, and whether each change is local-only, remote-only, or conflicting.",
        remote_page_mapping_rule="Map a local replica file back to its remote page by using the containing page directory's `_meta.json` together with the replica tree entry that exposes the page `id`, `title`, `content_file_path`, and `meta_file_path`.",
        manual_sync_prompt_rule="If local and remote changes clash, return all conflicting sections and line ranges so the consuming model can choose a resolution or prompt the user when uncertain. The client applies local file updates itself.",
    )


def resolve_replica_directory_name(
    title: str,
    slug_id: Optional[str] = None,
    page_id: Optional[UUID] = None,
    existing_dir_names: Optional[list[str]] = None,
) -> ReplicaNameResolutionOut:
    existing_dir_names = existing_dir_names or []
    sanitized_title = _sanitize_path_component(title)
    slug_component = _sanitize_path_component(slug_id) if slug_id else None
    page_id_prefix = str(page_id).split("-", 1)[0] if page_id else None
    existing_casefold = {name.casefold() for name in existing_dir_names}

    if sanitized_title.casefold() not in existing_casefold:
        return ReplicaNameResolutionOut(
            input_title=title, slug_id=slug_id, page_id=page_id,
            sanitized_title=sanitized_title, local_dir_name=sanitized_title,
            collision_strategy="title",
        )

    if slug_component:
        slug_candidate = f"{sanitized_title}__{slug_component}"
        if slug_candidate.casefold() not in existing_casefold:
            return ReplicaNameResolutionOut(
                input_title=title, slug_id=slug_id, page_id=page_id,
                sanitized_title=sanitized_title, local_dir_name=slug_candidate,
                collision_strategy="title_plus_slug_id",
            )

    suffix_seed = page_id_prefix or "generated"
    for suffix_length in (8, len(suffix_seed)):
        fallback_candidate = f"{sanitized_title}__{suffix_seed[:suffix_length]}"
        if fallback_candidate.casefold() not in existing_casefold:
            return ReplicaNameResolutionOut(
                input_title=title, slug_id=slug_id, page_id=page_id,
                sanitized_title=sanitized_title, local_dir_name=fallback_candidate,
                collision_strategy="title_plus_short_page_id",
            )

    index = 2
    while True:
        fallback_candidate = f"{sanitized_title}__{suffix_seed}-{index}"
        if fallback_candidate.casefold() not in existing_casefold:
            return ReplicaNameResolutionOut(
                input_title=title, slug_id=slug_id, page_id=page_id,
                sanitized_title=sanitized_title, local_dir_name=fallback_candidate,
                collision_strategy="title_plus_numeric_fallback",
            )
        index += 1


def _join_replica_path(parent_path: str, child_name: str) -> str:
    return f"{parent_path}/{child_name}" if parent_path else child_name


def _resolve_level_directory_names(nodes: list[PageTreeNode]) -> dict[UUID, ReplicaNameResolutionOut]:
    groups: dict[str, list[PageTreeNode]] = defaultdict(list)
    for node in nodes:
        groups[_sanitize_path_component(node.title).casefold()].append(node)

    resolutions: dict[UUID, ReplicaNameResolutionOut] = {}
    used_names: set[str] = set()

    for _, group_nodes in sorted(groups.items(), key=lambda item: item[0]):
        sorted_group = sorted(group_nodes, key=lambda node: (_sanitize_path_component(node.title), node.slug_id, str(node.id)))
        group_has_collision = len(sorted_group) > 1

        for node in sorted_group:
            existing_names = list(used_names)
            if group_has_collision and node.slug_id:
                existing_names.append(_sanitize_path_component(node.title))
            resolution = resolve_replica_directory_name(
                title=node.title or "Untitled",
                slug_id=node.slug_id if group_has_collision else None,
                page_id=node.id,
                existing_dir_names=existing_names,
            )
            used_names.add(resolution.local_dir_name)
            resolutions[node.id] = resolution

    return resolutions


def _build_replica_level(nodes: list[PageTreeNode], parent_path: str) -> list[ReplicaTreeNode]:
    name_resolutions = _resolve_level_directory_names(nodes)
    replica_nodes: list[ReplicaTreeNode] = []

    for node in nodes:
        resolution = name_resolutions[node.id]
        local_dir_path = _join_replica_path(parent_path, resolution.local_dir_name)
        replica_nodes.append(
            ReplicaTreeNode(
                id=node.id,
                title=node.title,
                slug_id=node.slug_id,
                parent_page_id=node.parent_page_id,
                local_dir_name=resolution.local_dir_name,
                local_dir_path=local_dir_path,
                content_file_path=f"{local_dir_path}/{PAGE_CONTENT_FILE_NAME}",
                meta_file_path=f"{local_dir_path}/{PAGE_META_FILE_NAME}",
                children=_build_replica_level(node.children, local_dir_path),
            )
        )

    return replica_nodes


def _normalize_replica_root(replica_root: str) -> str:
    normalized = (replica_root or "").strip()
    if not normalized:
        return normalized
    if normalized == ".":
        return "./"
    return normalized.rstrip("/")


def _rebase_replica_level(nodes: list[ReplicaTreeNode], parent_path: str) -> list[ReplicaTreeNode]:
    rebased: list[ReplicaTreeNode] = []
    for node in nodes:
        local_dir_path = _join_replica_path(parent_path, node.local_dir_name)
        rebased.append(
            ReplicaTreeNode(
                id=node.id,
                title=node.title,
                slug_id=node.slug_id,
                parent_page_id=node.parent_page_id,
                local_dir_name=node.local_dir_name,
                local_dir_path=local_dir_path,
                content_file_path=f"{local_dir_path}/{PAGE_CONTENT_FILE_NAME}",
                meta_file_path=f"{local_dir_path}/{PAGE_META_FILE_NAME}",
                children=_rebase_replica_level(node.children, local_dir_path),
            )
        )
    return rebased


def rebase_replica_structure(replica_structure: ReplicaStructureOut, replica_root: str) -> ReplicaStructureOut:
    normalized_root = _normalize_replica_root(replica_root)
    return ReplicaStructureOut(
        space=replica_structure.space,
        replica_root=normalized_root,
        replica_meta_file_path=f"{normalized_root}/{REPLICA_META_FILE_NAME}",
        tree_cache_file_path=f"{normalized_root}/{TREE_CACHE_FILE_NAME}",
        standards=replica_structure.standards,
        root_pages=_rebase_replica_level(replica_structure.root_pages, normalized_root),
        orphan_pages=_rebase_replica_level(replica_structure.orphan_pages, normalized_root),
    )


def get_replica_structure(space_id: UUID, replica_root: str | None = None) -> ReplicaStructureOut:
    space_tree = get_space_tree(space_id)
    default_replica_root = _space_replica_root(space_tree.space.name or space_tree.space.slug)
    standards = get_replica_standards()

    structure = ReplicaStructureOut(
        space=space_tree.space,
        replica_root=default_replica_root,
        replica_meta_file_path=f"{default_replica_root}/{REPLICA_META_FILE_NAME}",
        tree_cache_file_path=f"{default_replica_root}/{TREE_CACHE_FILE_NAME}",
        standards=standards,
        root_pages=_build_replica_level(space_tree.root_pages, default_replica_root),
        orphan_pages=_build_replica_level(space_tree.orphan_pages, default_replica_root),
    )
    return rebase_replica_structure(structure, replica_root=replica_root) if replica_root is not None else structure
