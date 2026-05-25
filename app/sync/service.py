from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

from app.models import (
    ClientReplicaPageIn,
    LocalReplicaPageCreateIn,
    LocalReplicaPageMetaTemplateOut,
    LocalReplicaPageOut,
    LocalReplicaPageSyncTemplateOut,
    PageSyncDiffOut,
    PageSyncStatusOut,
    ReplicaStructureOut,
    SpaceSummaryOut,
    SpaceSyncDiffOut,
    SpaceSyncStatusOut,
    SyncDiffIn,
    SyncOperationOut,
    SyncOperationResultOut,
    SyncPageSnapshotOut,
    SyncSelectionIn,
    SyncStatusCountsOut,
    SyncStatusIn,
)
from app.query.docmost import get_page as fetch_page
from app.query.docmost import list_pages as fetch_pages
from app.query.replica import get_replica_structure, resolve_replica_directory_name
from app.sync.diffing import build_diff_hunks, canonicalize_content, revision_hash
from app.write.docmost import create_page as create_remote_page
from app.write.docmost import update_page as update_remote_page


@dataclass
class SyncPageContext:
    status: PageSyncStatusOut
    local_page: ClientReplicaPageIn | None
    local_title: str | None
    local_text: str | None
    remote_page: object | None
    remote_text: str | None
    desired_local_path: str | None
    desired_meta_path: str | None


@dataclass
class SyncContext:
    space: SpaceSummaryOut
    local_root: str
    page_contexts: list[SyncPageContext]


@dataclass
class LocalReplicaParentContext:
    parent_page_id: UUID | None
    parent_local_dir_path: str | None
    parent_dir_path: str


def get_sync_status(space_id: UUID, request: SyncStatusIn | None = None) -> SpaceSyncStatusOut:
    request = request or SyncStatusIn()
    context = _build_sync_context(space_id, local_root=request.local_root, pages=request.pages)
    selected = _select_page_contexts(context.page_contexts, page_ids=request.page_ids, local_paths=request.local_paths)
    if not selected:
        selected = context.page_contexts

    page_statuses = [
        page_context.status
        for page_context in selected
        if request.include_synced or page_context.status.sync_state != "synced"
    ]
    return SpaceSyncStatusOut(
        space=context.space,
        local_root=context.local_root,
        generated_at=_utcnow(),
        pipeline_expectations=_pipeline_expectations(),
        counts=_count_statuses([page_context.status for page_context in context.page_contexts]),
        pages=page_statuses,
    )


def get_sync_diff(space_id: UUID, request: SyncDiffIn | None = None) -> SpaceSyncDiffOut:
    request = request or SyncDiffIn()
    context = _build_sync_context(space_id, local_root=request.local_root, pages=request.pages)
    selected = _select_page_contexts(
        context.page_contexts,
        page_ids=[request.page_id] if request.page_id else [],
        local_paths=[request.local_path] if request.local_path else [],
    )
    if not selected:
        selected = context.page_contexts

    diff_pages = [
        _build_page_diff(page_context)
        for page_context in selected
        if request.include_synced or page_context.status.sync_state != "synced" or request.page_id is not None or request.local_path is not None
    ]
    return SpaceSyncDiffOut(
        space=context.space,
        local_root=context.local_root,
        generated_at=_utcnow(),
        pages=diff_pages,
    )


def create_local_replica_page(space_id: UUID, request: LocalReplicaPageCreateIn) -> LocalReplicaPageOut:
    if request.parent_page_id is not None and request.parent_local_path:
        raise ValueError("Pass either parent_page_id or parent_local_path, not both.")

    replica_structure = _resolve_replica_structure(space_id, local_root=request.local_root)
    parent_context = _resolve_parent_context(replica_structure, request.parent_page_id, request.parent_local_path)

    sibling_dir_names = set(request.existing_dir_names)
    sibling_dir_names.update(_remote_sibling_dir_names(replica_structure, parent_context.parent_page_id))
    naming = resolve_replica_directory_name(
        title=request.title,
        existing_dir_names=sorted(sibling_dir_names),
    )

    local_dir_path = _join_client_path(parent_context.parent_dir_path, naming.local_dir_name)
    content_file_path = _join_client_path(local_dir_path, "page.md")
    meta_file_path = _join_client_path(local_dir_path, "_meta.json")
    meta_template = LocalReplicaPageMetaTemplateOut(
        id=None,
        title=request.title,
        slug_id=None,
        parent_page_id=parent_context.parent_page_id,
        parent_local_dir_path=parent_context.parent_local_dir_path,
        space_id=space_id,
        content_file_path=content_file_path,
        meta_file_path=meta_file_path,
    )

    return LocalReplicaPageOut(
        space=replica_structure.space,
        local_root=replica_structure.replica_root,
        title=request.title,
        parent_page_id=parent_context.parent_page_id,
        parent_local_path=parent_context.parent_local_dir_path,
        local_dir_path=local_dir_path,
        content_file_path=content_file_path,
        meta_file_path=meta_file_path,
        sync_state="local_only_page",
        recommended_next_action="push_replica",
        naming=naming,
        content=canonicalize_content(request.content),
        meta_template=meta_template,
        sync_template=LocalReplicaPageSyncTemplateOut(base_revision_hash=None),
        message="Client-local page scaffold planned. Write page.md and _meta.json locally, then call push_replica when the page is ready to create in Docmost.",
    )


def pull_replica(space_id: UUID, selection: SyncSelectionIn | None = None) -> SyncOperationOut:
    selection = selection or SyncSelectionIn()
    context = _build_sync_context(space_id, local_root=selection.local_root, pages=selection.pages)
    selected = _select_page_contexts(context.page_contexts, page_ids=selection.page_ids, local_paths=selection.local_paths)
    if not selected:
        selected = context.page_contexts

    results: list[SyncOperationResultOut] = []
    for page_context in selected:
        status = page_context.status
        conflict_hunks = build_diff_hunks(page_context.local_text, page_context.remote_text) if status.has_conflicts else []

        if status.sync_state in {"remote_only_page", "remote_only_change", "local_missing"} or (
            status.sync_state == "conflicted" and selection.force
        ):
            if page_context.remote_page is None or page_context.remote_text is None:
                results.append(
                    _skip_result(
                        page_context,
                        "pull_skipped",
                        "Remote page details are incomplete for this pull result.",
                        conflicts=conflict_hunks,
                        recommended_next_action="get_sync_diff",
                    )
                )
                continue

            action = "pulled"
            message = "Remote Docmost snapshot returned for the client to write locally."
            if status.sync_state == "remote_only_page":
                action = "materialized_local"
                message = "Remote page snapshot returned for first-time local materialization."
            elif status.sync_state == "conflicted":
                action = "pulled_forced"
                message = "Remote Docmost snapshot returned and local divergence intentionally overridden."

            results.append(
                _applied_result(
                    page_context,
                    action,
                    message,
                    snapshot=_snapshot_from_remote(page_context),
                )
            )
            continue

        if status.sync_state == "synced":
            results.append(_skip_result(page_context, "already_synced", "Client-local and remote Docmost state already match."))
            continue

        if status.sync_state == "local_only_change":
            results.append(
                _skip_result(
                    page_context,
                    "pull_skipped",
                    "Client-local page is ahead of remote Docmost. Push it, or force pull to take the current remote page.",
                    recommended_next_action="push_replica",
                )
            )
            continue

        if status.sync_state == "conflicted":
            results.append(
                _skip_result(
                    page_context,
                    "conflict",
                    "Client-local and remote Docmost both changed. Inspect the diff first or force pull to take remote.",
                    conflicts=conflict_hunks,
                    recommended_next_action="get_sync_diff",
                )
            )
            continue

        if status.sync_state == "local_only_page":
            results.append(
                _skip_result(
                    page_context,
                    "pull_skipped",
                    "Local-only page has no remote Docmost page to pull.",
                    recommended_next_action="push_replica",
                )
            )
            continue

        if status.sync_state == "remote_deleted":
            results.append(
                _skip_result(
                    page_context,
                    "pull_skipped",
                    "Remote page no longer exists. Review the local page before deciding whether to recreate it.",
                    recommended_next_action="review_remote_deletion",
                )
            )
            continue

    return _build_operation_out(context, "pull", selection.force, results)


def push_replica(space_id: UUID, selection: SyncSelectionIn | None = None) -> SyncOperationOut:
    selection = selection or SyncSelectionIn()
    context = _build_sync_context(space_id, local_root=selection.local_root, pages=selection.pages)
    selected = _select_page_contexts(context.page_contexts, page_ids=selection.page_ids, local_paths=selection.local_paths)
    if not selected:
        selected = context.page_contexts

    selected = sorted(selected, key=lambda page_context: _path_depth(page_context.status.local_path or page_context.status.desired_local_path))
    known_page_ids = _known_page_ids_by_local_path(context.page_contexts)
    results: list[SyncOperationResultOut] = []

    for page_context in selected:
        status = page_context.status
        conflict_hunks = build_diff_hunks(page_context.local_text, page_context.remote_text) if status.has_conflicts else []

        if status.sync_state in {"local_only_change"} or (status.sync_state == "conflicted" and selection.force):
            if page_context.local_text is None or status.page_id is None:
                results.append(
                    _skip_result(
                        page_context,
                        "push_skipped",
                        "Client-local page data is incomplete for a remote update.",
                        conflicts=conflict_hunks,
                        recommended_next_action="get_sync_diff",
                    )
                )
                continue

            normalized_local_text = canonicalize_content(page_context.local_text)
            response = update_remote_page(
                page_id=str(status.page_id),
                title=page_context.local_title,
                content=normalized_local_text,
                operation="replace",
            )
            remote_page = response.get("page", response)
            resolved_title = remote_page.get("title") or page_context.local_title
            resolved_slug_id = remote_page.get("slugId") or remote_page.get("slug_id") or status.slug_id
            resolved_parent_page_id = _coerce_uuid(remote_page.get("parentPageId") or remote_page.get("parent_page_id")) or status.parent_page_id
            snapshot = SyncPageSnapshotOut(
                page_id=status.page_id,
                title=resolved_title,
                slug_id=resolved_slug_id,
                parent_page_id=resolved_parent_page_id,
                local_path=status.local_path,
                meta_file_path=status.meta_file_path,
                content=normalized_local_text,
                base_revision_hash=revision_hash(resolved_title, normalized_local_text),
            )
            action = "pushed_forced" if status.sync_state == "conflicted" and selection.force else "pushed"
            results.append(
                _applied_result(
                    page_context,
                    action,
                    "Client-local page pushed to remote Docmost.",
                    snapshot=snapshot,
                )
            )
            _remember_snapshot_paths(snapshot, known_page_ids)
            continue

        if status.sync_state == "local_only_page":
            if page_context.local_text is None:
                results.append(
                    _skip_result(
                        page_context,
                        "push_skipped",
                        "Local-only page is missing client-local content.",
                        recommended_next_action="get_sync_diff",
                    )
                )
                continue

            parent_page_id = _resolve_local_only_parent_page_id(page_context, known_page_ids)
            if page_context.local_page and page_context.local_page.parent_local_path and parent_page_id is None:
                results.append(
                    _skip_result(
                        page_context,
                        "push_skipped",
                        "Parent local-only page has not been pushed yet. Push the parent first or include it in the same push.",
                        recommended_next_action="push_replica",
                    )
                )
                continue

            normalized_local_text = canonicalize_content(page_context.local_text)
            response = create_remote_page(
                space_id=str(space_id),
                title=page_context.local_title,
                content=normalized_local_text,
                parent_page_id=str(parent_page_id) if parent_page_id else None,
            )
            remote_page = response.get("page", response)
            created_page_id = UUID(str(remote_page["id"]))
            resolved_title = remote_page.get("title") or page_context.local_title
            resolved_slug_id = remote_page.get("slugId") or remote_page.get("slug_id")
            resolved_parent_page_id = _coerce_uuid(remote_page.get("parentPageId") or remote_page.get("parent_page_id")) or parent_page_id
            snapshot = SyncPageSnapshotOut(
                page_id=created_page_id,
                title=resolved_title,
                slug_id=resolved_slug_id,
                parent_page_id=resolved_parent_page_id,
                local_path=status.local_path or status.desired_local_path,
                meta_file_path=status.meta_file_path,
                content=normalized_local_text,
                base_revision_hash=revision_hash(resolved_title, normalized_local_text),
            )
            results.append(
                _applied_result(
                    page_context,
                    "created_remote",
                    "Local-only page created in remote Docmost.",
                    snapshot=snapshot,
                )
            )
            _remember_snapshot_paths(snapshot, known_page_ids)
            continue

        if status.sync_state == "synced":
            results.append(_skip_result(page_context, "already_synced", "Client-local and remote Docmost state already match."))
            continue

        if status.sync_state == "remote_only_change":
            results.append(
                _skip_result(
                    page_context,
                    "push_skipped",
                    "Remote Docmost is ahead of the client-local page. Pull it first or force push to overwrite remote.",
                    recommended_next_action="pull_replica",
                )
            )
            continue

        if status.sync_state == "conflicted":
            results.append(
                _skip_result(
                    page_context,
                    "conflict",
                    "Client-local and remote Docmost both changed. Inspect the diff first or force push to take local.",
                    conflicts=conflict_hunks,
                    recommended_next_action="get_sync_diff",
                )
            )
            continue

        if status.sync_state == "remote_only_page":
            results.append(
                _skip_result(
                    page_context,
                    "push_skipped",
                    "Remote page has not been included in the current client-local page set. Pull it or pass the local page state before pushing.",
                    recommended_next_action="pull_replica",
                )
            )
            continue

        if status.sync_state == "remote_deleted":
            results.append(
                _skip_result(
                    page_context,
                    "push_skipped",
                    "Remote page no longer exists. Review the local page and decide whether to recreate it as a new page.",
                    recommended_next_action="review_remote_deletion",
                )
            )
            continue

        if status.sync_state == "local_missing":
            results.append(
                _skip_result(
                    page_context,
                    "push_skipped",
                    "Client-local content is missing. Restore the local page or pull the current remote page.",
                    recommended_next_action="pull_replica",
                )
            )
            continue

    return _build_operation_out(context, "push", selection.force, results)


def _build_sync_context(space_id: UUID, *, local_root: str | None, pages: list[ClientReplicaPageIn]) -> SyncContext:
    replica_structure = _resolve_replica_structure(space_id, local_root=local_root)
    remote_nodes = _flatten_replica_nodes(replica_structure)
    remote_pages = {page.id: fetch_page(space_id, page.id) for page in fetch_pages(space_id)}

    local_by_id: dict[UUID, ClientReplicaPageIn] = {}
    local_without_id: list[ClientReplicaPageIn] = []
    for page in pages:
        if page.page_id is not None:
            local_by_id[page.page_id] = page
        else:
            local_without_id.append(page)

    page_contexts: list[SyncPageContext] = []

    for page_id, remote_page in remote_pages.items():
        local_page = local_by_id.get(page_id)
        node = remote_nodes.get(page_id)
        desired_local_path = node.content_file_path if node else None
        desired_meta_path = node.meta_file_path if node else None
        local_title = local_page.title if local_page and local_page.title is not None else remote_page.title
        local_text = local_page.content if local_page else None
        local_path = _normalize_client_path(local_page.local_path) if local_page and local_page.local_path else desired_local_path
        meta_file_path = _normalize_client_path(local_page.meta_file_path) if local_page and local_page.meta_file_path else desired_meta_path
        local_exists = local_page is not None and local_page.content is not None
        base_revision = local_page.base_revision_hash if local_page else None
        local_revision = revision_hash(local_title, local_text) if local_exists else None
        remote_text = remote_page.content or ""
        remote_revision = revision_hash(remote_page.title, remote_text)
        status = _build_page_status(
            page_id=page_id,
            title=remote_page.title or (local_page.title if local_page else None),
            slug_id=remote_page.slug_id or (local_page.slug_id if local_page else None),
            parent_page_id=remote_page.parent_page_id or (local_page.parent_page_id if local_page else None),
            remote_exists=True,
            local_present=local_page is not None,
            local_exists=local_exists,
            base_revision_hash=base_revision,
            local_revision_hash=local_revision,
            remote_revision_hash=remote_revision,
            local_path=local_path,
            desired_local_path=desired_local_path,
            meta_file_path=meta_file_path,
        )
        page_contexts.append(
            SyncPageContext(
                status=status,
                local_page=local_page,
                local_title=local_title,
                local_text=local_text,
                remote_page=remote_page,
                remote_text=remote_text,
                desired_local_path=desired_local_path,
                desired_meta_path=desired_meta_path,
            )
        )

    remote_page_ids = set(remote_pages.keys())
    for local_page in local_without_id:
        local_title = local_page.title
        local_path = _normalize_client_path(local_page.local_path)
        meta_file_path = _normalize_client_path(local_page.meta_file_path)
        local_exists = local_page.content is not None
        local_revision = revision_hash(local_title, local_page.content) if local_exists else None
        status = _build_page_status(
            page_id=None,
            title=local_title,
            slug_id=local_page.slug_id,
            parent_page_id=local_page.parent_page_id,
            remote_exists=False,
            local_present=True,
            local_exists=local_exists,
            base_revision_hash=local_page.base_revision_hash,
            local_revision_hash=local_revision,
            remote_revision_hash=None,
            local_path=local_path,
            desired_local_path=local_path,
            meta_file_path=meta_file_path,
        )
        page_contexts.append(
            SyncPageContext(
                status=status,
                local_page=local_page,
                local_title=local_title,
                local_text=local_page.content,
                remote_page=None,
                remote_text=None,
                desired_local_path=local_path,
                desired_meta_path=meta_file_path,
            )
        )

    for page_id, local_page in local_by_id.items():
        if page_id in remote_page_ids:
            continue
        local_title = local_page.title
        local_path = _normalize_client_path(local_page.local_path)
        meta_file_path = _normalize_client_path(local_page.meta_file_path)
        local_exists = local_page.content is not None
        local_revision = revision_hash(local_title, local_page.content) if local_exists else None
        status = _build_page_status(
            page_id=page_id,
            title=local_title,
            slug_id=local_page.slug_id,
            parent_page_id=local_page.parent_page_id,
            remote_exists=False,
            local_present=True,
            local_exists=local_exists,
            base_revision_hash=local_page.base_revision_hash,
            local_revision_hash=local_revision,
            remote_revision_hash=None,
            local_path=local_path,
            desired_local_path=local_path,
            meta_file_path=meta_file_path,
        )
        page_contexts.append(
            SyncPageContext(
                status=status,
                local_page=local_page,
                local_title=local_title,
                local_text=local_page.content,
                remote_page=None,
                remote_text=None,
                desired_local_path=local_path,
                desired_meta_path=meta_file_path,
            )
        )

    page_contexts.sort(key=lambda page_context: (page_context.status.local_path or page_context.status.desired_local_path or "", page_context.status.title or ""))
    return SyncContext(
        space=replica_structure.space,
        local_root=replica_structure.replica_root,
        page_contexts=page_contexts,
    )


def _build_page_status(
    *,
    page_id: UUID | None,
    title: str | None,
    slug_id: str | None,
    parent_page_id: UUID | None,
    remote_exists: bool,
    local_present: bool,
    local_exists: bool,
    base_revision_hash: str | None,
    local_revision_hash: str | None,
    remote_revision_hash: str | None,
    local_path: str | None,
    desired_local_path: str | None,
    meta_file_path: str | None,
) -> PageSyncStatusOut:
    if not remote_exists and page_id is None:
        sync_state = "local_only_page" if local_exists else "local_missing"
        summary = "Local-only page is ready to be created in remote Docmost." if local_exists else "Local-only page metadata exists, but client-local content is missing."
        local_changed = local_exists
        remote_changed = False
        has_conflicts = False
    elif not remote_exists:
        sync_state = "remote_deleted"
        summary = "Client-local page still tracks a remote page that no longer exists in Docmost."
        local_changed = bool(local_exists and base_revision_hash and local_revision_hash != base_revision_hash)
        remote_changed = True
        has_conflicts = False
    elif not local_present:
        sync_state = "remote_only_page"
        summary = "Remote Docmost page is not present in the current client-local page set."
        local_changed = False
        remote_changed = True
        has_conflicts = False
    elif not local_exists:
        sync_state = "local_missing"
        summary = "Client-local page metadata exists, but local content was not provided."
        local_changed = True
        remote_changed = bool(base_revision_hash and remote_revision_hash and remote_revision_hash != base_revision_hash)
        has_conflicts = False
    elif local_revision_hash == remote_revision_hash:
        sync_state = "synced"
        summary = "Client-local and remote Docmost state match."
        local_changed = bool(base_revision_hash and local_revision_hash != base_revision_hash)
        remote_changed = bool(base_revision_hash and remote_revision_hash and remote_revision_hash != base_revision_hash)
        has_conflicts = False
    elif not base_revision_hash:
        sync_state = "conflicted"
        summary = "Client-local and remote Docmost differ, and no common sync base was provided."
        local_changed = True
        remote_changed = True
        has_conflicts = True
    else:
        local_changed = bool(local_revision_hash and local_revision_hash != base_revision_hash)
        remote_changed = bool(remote_revision_hash and remote_revision_hash != base_revision_hash)
        if local_changed and not remote_changed:
            sync_state = "local_only_change"
            summary = "Client-local page changed since the last sync."
            has_conflicts = False
        elif remote_changed and not local_changed:
            sync_state = "remote_only_change"
            summary = "Remote Docmost page changed since the last sync."
            has_conflicts = False
        elif local_revision_hash == remote_revision_hash:
            sync_state = "synced"
            summary = "Client-local and remote Docmost now match, but the stored sync base is outdated."
            has_conflicts = False
        else:
            sync_state = "conflicted"
            summary = "Client-local and remote Docmost both changed since the last sync."
            has_conflicts = True

    recommended_action, allowed_actions = _recommendation_for_state(sync_state)
    return PageSyncStatusOut(
        page_id=page_id,
        title=title,
        slug_id=slug_id,
        parent_page_id=parent_page_id,
        sync_state=sync_state,
        summary=summary,
        local_path=local_path,
        desired_local_path=desired_local_path,
        meta_file_path=meta_file_path,
        remote_exists=remote_exists,
        local_exists=local_exists,
        local_changed=local_changed,
        remote_changed=remote_changed,
        has_conflicts=has_conflicts,
        recommended_action=recommended_action,
        allowed_actions=allowed_actions,
        base_revision_hash=base_revision_hash,
        local_revision_hash=local_revision_hash,
        remote_revision_hash=remote_revision_hash,
    )


def _build_page_diff(page_context: SyncPageContext) -> PageSyncDiffOut:
    status = page_context.status
    return PageSyncDiffOut(
        page_id=status.page_id,
        title=status.title,
        sync_state=status.sync_state,
        summary=status.summary,
        local_path=status.local_path or status.desired_local_path,
        meta_file_path=status.meta_file_path,
        remote_exists=status.remote_exists,
        local_exists=status.local_exists,
        has_conflicts=status.has_conflicts,
        hunks=build_diff_hunks(page_context.local_text, page_context.remote_text),
    )


def _select_page_contexts(
    page_contexts: list[SyncPageContext],
    *,
    page_ids: Iterable[UUID],
    local_paths: Iterable[str],
) -> list[SyncPageContext]:
    page_id_set = {page_id for page_id in page_ids if page_id is not None}
    local_path_values = [_normalize_client_path(path) for path in local_paths if path]
    if not page_id_set and not local_path_values:
        return []

    selected: list[SyncPageContext] = []
    for page_context in page_contexts:
        status = page_context.status
        if status.page_id in page_id_set:
            selected.append(page_context)
            continue
        if any(_matches_path(status, candidate) for candidate in local_path_values):
            selected.append(page_context)
    return selected


def _matches_path(status: PageSyncStatusOut, candidate: str) -> bool:
    normalized = _normalize_client_path(candidate)
    if not normalized:
        return False
    options = {
        _normalize_client_path(status.local_path),
        _normalize_client_path(status.desired_local_path),
        _normalize_client_path(status.meta_file_path),
    }
    return normalized in {option for option in options if option}


def _count_statuses(statuses: list[PageSyncStatusOut]) -> SyncStatusCountsOut:
    counts = SyncStatusCountsOut()
    for status in statuses:
        setattr(counts, status.sync_state, getattr(counts, status.sync_state) + 1)
    return counts


def _snapshot_from_remote(page_context: SyncPageContext) -> SyncPageSnapshotOut:
    status = page_context.status
    remote_page = page_context.remote_page
    remote_title = getattr(remote_page, "title", None) if remote_page is not None else status.title
    remote_slug_id = getattr(remote_page, "slug_id", None) if remote_page is not None else status.slug_id
    remote_parent_page_id = getattr(remote_page, "parent_page_id", None) if remote_page is not None else status.parent_page_id
    remote_text = canonicalize_content(page_context.remote_text)
    return SyncPageSnapshotOut(
        page_id=status.page_id,
        title=remote_title,
        slug_id=remote_slug_id,
        parent_page_id=remote_parent_page_id,
        local_path=status.local_path or status.desired_local_path,
        meta_file_path=status.meta_file_path or page_context.desired_meta_path,
        content=remote_text,
        base_revision_hash=revision_hash(remote_title, remote_text),
    )


def _applied_result(
    page_context: SyncPageContext,
    action: str,
    message: str,
    *,
    snapshot: SyncPageSnapshotOut | None = None,
) -> SyncOperationResultOut:
    return SyncOperationResultOut(
        page_id=snapshot.page_id if snapshot and snapshot.page_id is not None else page_context.status.page_id,
        title=snapshot.title if snapshot and snapshot.title is not None else page_context.status.title,
        local_path=snapshot.local_path if snapshot and snapshot.local_path is not None else (page_context.status.local_path or page_context.status.desired_local_path),
        meta_file_path=snapshot.meta_file_path if snapshot and snapshot.meta_file_path is not None else page_context.status.meta_file_path,
        sync_state_before=page_context.status.sync_state,
        action=action,
        applied=True,
        message=message,
        snapshot=snapshot,
    )


def _skip_result(
    page_context: SyncPageContext,
    action: str,
    message: str,
    *,
    conflicts: list | None = None,
    recommended_next_action: str | None = None,
) -> SyncOperationResultOut:
    return SyncOperationResultOut(
        page_id=page_context.status.page_id,
        title=page_context.status.title,
        local_path=page_context.status.local_path or page_context.status.desired_local_path,
        meta_file_path=page_context.status.meta_file_path,
        sync_state_before=page_context.status.sync_state,
        action=action,
        applied=False,
        message=message,
        recommended_next_action=recommended_next_action,
        conflicts=conflicts or [],
    )


def _build_operation_out(
    context: SyncContext,
    operation: str,
    force: bool,
    results: list[SyncOperationResultOut],
) -> SyncOperationOut:
    return SyncOperationOut(
        space=context.space,
        operation=operation,
        local_root=context.local_root,
        force=force,
        generated_at=_utcnow(),
        applied_count=sum(1 for result in results if result.applied),
        skipped_count=sum(1 for result in results if not result.applied and result.action != "conflict"),
        conflict_count=sum(1 for result in results if result.action == "conflict"),
        results=results,
    )


def _pipeline_expectations() -> list[str]:
    return [
        "Call get_sync_status first and pass the current client-local page states you want compared against live Docmost.",
        "Call get_sync_diff before any force operation or whenever the recommended action is get_sync_diff.",
        "The client owns local replica files and sync-base storage. The server owns canonical path planning, Docmost comparison, diffing, and safe remote writes.",
        "pull_replica never writes the client filesystem. It returns canonical remote snapshots for the client to materialize or refresh locally.",
        "push_replica never reads the client filesystem. It only writes the client-supplied page state to remote Docmost when the sync state allows it.",
        "Content comparison is canonicalized server-side to ignore representation-only drift such as BOM, CRLF vs LF, Unicode normalization form, and trailing final-newline differences.",
        "Revision hashes are computed from the canonical page title plus canonical page content.",
    ]


def _recommendation_for_state(sync_state: str) -> tuple[str, list[str]]:
    mapping = {
        "synced": ("none", []),
        "local_only_change": ("push_replica", ["get_sync_diff", "push_replica", "pull_replica(force)"]),
        "remote_only_change": ("pull_replica", ["get_sync_diff", "pull_replica", "push_replica(force)"]),
        "conflicted": ("get_sync_diff", ["get_sync_diff", "pull_replica(force)", "push_replica(force)"]),
        "remote_only_page": ("pull_replica", ["pull_replica"]),
        "local_only_page": ("push_replica", ["push_replica"]),
        "remote_deleted": ("review_remote_deletion", ["get_sync_diff", "review_remote_deletion"]),
        "local_missing": ("pull_replica", ["pull_replica"]),
    }
    return mapping[sync_state]


def _resolve_parent_context(
    replica_structure: ReplicaStructureOut,
    parent_page_id: UUID | None,
    parent_local_path: str | None,
) -> LocalReplicaParentContext:
    if parent_page_id is None and not parent_local_path:
        return LocalReplicaParentContext(None, None, replica_structure.replica_root)

    if parent_page_id is not None:
        node = _flatten_replica_nodes(replica_structure).get(parent_page_id)
        if node is None:
            raise ValueError(f"Parent page {parent_page_id} does not exist in the current remote space tree.")
        return LocalReplicaParentContext(parent_page_id, node.local_dir_path, node.local_dir_path)

    normalized_parent_path = _normalize_client_dir_path(parent_local_path or "")
    matched_node = _find_remote_node_by_local_path(replica_structure, normalized_parent_path)
    return LocalReplicaParentContext(
        matched_node.id if matched_node is not None else None,
        normalized_parent_path,
        normalized_parent_path,
    )


def _remote_sibling_dir_names(replica_structure: ReplicaStructureOut, parent_page_id: UUID | None) -> set[str]:
    if parent_page_id is None:
        return {node.local_dir_name for node in replica_structure.root_pages + replica_structure.orphan_pages}
    node = _flatten_replica_nodes(replica_structure).get(parent_page_id)
    if node is None:
        return set()
    return {child.local_dir_name for child in node.children}


def _resolve_local_only_parent_page_id(page_context: SyncPageContext, known_page_ids: dict[str, UUID]) -> UUID | None:
    local_page = page_context.local_page
    if local_page is None:
        return None
    if local_page.parent_page_id is not None:
        return local_page.parent_page_id
    if not local_page.parent_local_path:
        return None
    normalized_parent_path = _normalize_client_path(local_page.parent_local_path)
    return known_page_ids.get(normalized_parent_path)


def _known_page_ids_by_local_path(page_contexts: list[SyncPageContext]) -> dict[str, UUID]:
    known: dict[str, UUID] = {}
    for page_context in page_contexts:
        status = page_context.status
        if status.page_id is None:
            continue
        for candidate in (
            status.local_path,
            status.desired_local_path,
            status.meta_file_path,
            _normalize_client_dir_path(status.local_path),
            _normalize_client_dir_path(status.meta_file_path),
        ):
            normalized = _normalize_client_path(candidate)
            if normalized:
                known[normalized] = status.page_id
    return known


def _remember_snapshot_paths(snapshot: SyncPageSnapshotOut, known_page_ids: dict[str, UUID]) -> None:
    if snapshot.page_id is None:
        return
    for candidate in (
        snapshot.local_path,
        snapshot.meta_file_path,
        _normalize_client_dir_path(snapshot.local_path),
        _normalize_client_dir_path(snapshot.meta_file_path),
    ):
        normalized = _normalize_client_path(candidate)
        if normalized:
            known_page_ids[normalized] = snapshot.page_id


def _flatten_replica_nodes(replica_structure: ReplicaStructureOut) -> dict[UUID, object]:
    nodes: dict[UUID, object] = {}

    def walk(node) -> None:
        nodes[node.id] = node
        for child in node.children:
            walk(child)

    for node in replica_structure.root_pages + replica_structure.orphan_pages:
        walk(node)
    return nodes


def _find_remote_node_by_local_path(replica_structure: ReplicaStructureOut, candidate: str | None):
    normalized = _normalize_client_path(candidate)
    if not normalized:
        return None
    for node in _flatten_replica_nodes(replica_structure).values():
        options = {
            _normalize_client_path(node.local_dir_path),
            _normalize_client_path(node.content_file_path),
            _normalize_client_path(node.meta_file_path),
        }
        if normalized in options:
            return node
    return None


def _resolve_replica_structure(space_id: UUID, *, local_root: str | None) -> ReplicaStructureOut:
    return get_replica_structure(space_id, replica_root=local_root)


def _normalize_client_path(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized in {".", "./"}:
        return "./"
    if normalized != "/" and normalized.endswith("/"):
        normalized = normalized.rstrip("/")
    return normalized


def _normalize_client_dir_path(value: str | None) -> str | None:
    normalized = _normalize_client_path(value)
    if not normalized:
        return None
    if normalized.endswith("/page.md") or normalized.endswith("/_meta.json"):
        return normalized.rsplit("/", 1)[0]
    return normalized


def _join_client_path(parent: str, child: str) -> str:
    normalized_parent = _normalize_client_path(parent) or ""
    if not normalized_parent:
        return child
    if normalized_parent == "/":
        return f"/{child}"
    if normalized_parent.endswith("/"):
        return f"{normalized_parent}{child}"
    return f"{normalized_parent}/{child}"


def _path_depth(value: str | None) -> tuple[int, str]:
    normalized = _normalize_client_path(value) or ""
    return (normalized.count("/"), normalized)


def _coerce_uuid(value: object) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
