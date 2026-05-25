from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional
from uuid import UUID

from app.models import (
    PageSyncDiffOut,
    PageSyncStatusOut,
    SpaceSummaryOut,
    SpaceSyncDiffOut,
    SpaceSyncStatusOut,
    SyncOperationOut,
    SyncOperationResultOut,
    SyncSelectionIn,
    SyncStatusCountsOut,
)
from app.query.docmost import get_page as fetch_page
from app.query.docmost import list_pages as fetch_pages
from app.query.replica import get_replica_structure
from app.sync.diffing import build_diff_hunks, content_hash
from app.sync.models import ReplicaPageState
from app.sync.storage import (
    flatten_replica_nodes,
    get_local_replica_paths,
    read_local_content,
    scan_local_replica,
    write_content_file,
    write_page_state,
    write_remote_page_snapshot,
    write_replica_state,
)
from app.write.docmost import create_page as create_remote_page
from app.write.docmost import update_page as update_remote_page


@dataclass
class SyncPageContext:
    status: PageSyncStatusOut
    local_text: str | None
    remote_text: str | None
    meta: ReplicaPageState | None
    remote_page: object | None
    desired_content_path: str | None
    desired_meta_path: str | None


@dataclass
class SyncContext:
    space: SpaceSummaryOut
    replica_root: str
    replica_root_abs_path: str
    replica_exists: bool
    page_contexts: list[SyncPageContext]


def get_sync_status(space_id: UUID, *, include_synced: bool = False) -> SpaceSyncStatusOut:
    context = _build_sync_context(space_id)
    page_statuses = [
        page_context.status
        for page_context in context.page_contexts
        if include_synced or page_context.status.sync_state != "synced"
    ]
    return SpaceSyncStatusOut(
        space=context.space,
        replica_root=context.replica_root,
        replica_root_abs_path=context.replica_root_abs_path,
        replica_exists=context.replica_exists,
        generated_at=datetime.utcnow(),
        pipeline_expectations=_pipeline_expectations(),
        counts=_count_statuses([page_context.status for page_context in context.page_contexts]),
        pages=page_statuses,
    )


def get_sync_diff(
    space_id: UUID,
    *,
    page_id: UUID | None = None,
    local_path: str | None = None,
    include_synced: bool = False,
) -> SpaceSyncDiffOut:
    context = _build_sync_context(space_id)
    selected = _select_page_contexts(context.page_contexts, page_ids=[page_id] if page_id else [], local_paths=[local_path] if local_path else [])

    if not selected:
        selected = context.page_contexts

    diff_pages = [
        _build_page_diff(page_context)
        for page_context in selected
        if include_synced or page_context.status.sync_state != "synced" or page_id is not None or local_path is not None
    ]

    return SpaceSyncDiffOut(
        space=context.space,
        replica_root=context.replica_root,
        replica_root_abs_path=context.replica_root_abs_path,
        generated_at=datetime.utcnow(),
        pages=diff_pages,
    )


def pull_replica(space_id: UUID, selection: SyncSelectionIn | None = None) -> SyncOperationOut:
    selection = selection or SyncSelectionIn()
    context = _build_sync_context(space_id)
    selected = _select_page_contexts(context.page_contexts, page_ids=selection.page_ids, local_paths=selection.local_paths)
    if not selected:
        selected = context.page_contexts

    results: list[SyncOperationResultOut] = []
    any_applied = False

    for page_context in selected:
        status = page_context.status
        conflict_hunks = build_diff_hunks(page_context.local_text, page_context.remote_text) if status.has_conflicts else []

        if status.sync_state in {"remote_only_page", "remote_only_change", "local_missing"} or (
            status.sync_state == "conflicted" and selection.force
        ):
            if page_context.remote_page is None or page_context.desired_content_path is None or page_context.desired_meta_path is None:
                results.append(_skip_result(page_context, "pull_skipped", "Remote page metadata is incomplete for local materialization.", conflict_hunks, recommended_next_action="get_sync_diff"))
                continue

            remote_page = page_context.remote_page
            if page_context.meta is not None and status.sync_state != "remote_only_page":
                write_content_file(page_context.meta.content_file_path, page_context.remote_text or "")
                updated_meta = page_context.meta.model_copy(
                    update={
                        "title": getattr(remote_page, "title", None) or page_context.meta.title,
                        "slug_id": getattr(remote_page, "slug_id", None) or page_context.meta.slug_id,
                        "parent_page_id": getattr(remote_page, "parent_page_id", None) or page_context.meta.parent_page_id,
                        "base_content_hash": content_hash(page_context.remote_text),
                        "last_sync_at": datetime.utcnow(),
                        "last_sync_remote_updated_at": getattr(remote_page, "updated_at", None),
                        "last_sync_title": getattr(remote_page, "title", None) or page_context.meta.title,
                    }
                )
                write_page_state(updated_meta)
            else:
                from app.query.replica import get_replica_structure as _fetch_replica_structure  # local import avoids stale tree after writes

                replica_structure = _fetch_replica_structure(space_id)
                desired_node = flatten_replica_nodes(replica_structure).get(status.page_id) if status.page_id else None
                if desired_node is None:
                    results.append(_skip_result(page_context, "pull_skipped", "Could not resolve the current replica path for the remote page.", conflict_hunks, recommended_next_action="get_sync_diff"))
                    continue

                write_remote_page_snapshot(
                    replica_structure,
                    desired_node,
                    content=page_context.remote_text or "",
                    title=getattr(remote_page, "title", None),
                    slug_id=getattr(remote_page, "slug_id", None),
                    parent_page_id=getattr(remote_page, "parent_page_id", None),
                    base_content_hash=content_hash(page_context.remote_text),
                    remote_updated_at=getattr(remote_page, "updated_at", None),
                )
            action = "pulled_forced" if status.sync_state == "conflicted" and selection.force else "pulled"
            message = "Remote content materialized into the server-side replica."
            if status.sync_state == "remote_only_page":
                action = "materialized_local"
                message = "Remote page materialized locally for the first time."
            any_applied = True
            results.append(_applied_result(page_context, action, message))
            continue

        if status.sync_state == "synced":
            results.append(_skip_result(page_context, "already_synced", "Local and remote content already match."))
            continue

        if status.sync_state == "local_only_change":
            results.append(_skip_result(page_context, "pull_skipped", "Local replica is ahead of remote. Push it or force pull to overwrite it.", recommended_next_action="push_replica"))
            continue

        if status.sync_state == "conflicted":
            results.append(_skip_result(page_context, "conflict", "Local and remote both changed. Force pull to take remote, or inspect the diff first.", conflict_hunks, recommended_next_action="get_sync_diff"))
            continue

        if status.sync_state == "local_only_page":
            results.append(_skip_result(page_context, "pull_skipped", "Local-only page has no remote content to pull.", recommended_next_action="push_replica"))
            continue

        if status.sync_state == "remote_deleted":
            results.append(_skip_result(page_context, "pull_skipped", "Remote page no longer exists. Inspect the conflict before deciding whether to keep or recreate the local copy.", recommended_next_action="review_remote_deletion"))
            continue

    _refresh_replica_state(space_id, operation="pull", write_state=True)
    return _build_operation_out(context, "pull", selection.force, results, any_applied)


def push_replica(space_id: UUID, selection: SyncSelectionIn | None = None) -> SyncOperationOut:
    selection = selection or SyncSelectionIn()
    context = _build_sync_context(space_id)
    selected = _select_page_contexts(context.page_contexts, page_ids=selection.page_ids, local_paths=selection.local_paths)
    if not selected:
        selected = context.page_contexts

    selected = sorted(selected, key=lambda page_context: ((page_context.status.local_path or "").count("/"), page_context.status.local_path or ""))
    results: list[SyncOperationResultOut] = []
    any_applied = False

    for page_context in selected:
        status = page_context.status
        conflict_hunks = build_diff_hunks(page_context.local_text, page_context.remote_text) if status.has_conflicts else []

        if status.sync_state in {"local_only_change"} or (status.sync_state == "conflicted" and selection.force):
            if page_context.meta is None or page_context.status.page_id is None or page_context.local_text is None:
                results.append(_skip_result(page_context, "push_skipped", "Local replica metadata is incomplete for a remote update.", conflict_hunks, recommended_next_action="get_sync_diff"))
                continue

            response = update_remote_page(
                page_id=str(page_context.status.page_id),
                title=page_context.meta.title,
                content=page_context.local_text,
                operation="replace",
            )
            remote_page = response.get("page", response)
            updated_meta = page_context.meta.model_copy(
                update={
                    "title": remote_page.get("title") or page_context.meta.title,
                    "slug_id": remote_page.get("slugId") or remote_page.get("slug_id") or page_context.meta.slug_id,
                    "base_content_hash": content_hash(page_context.local_text),
                    "last_sync_at": datetime.utcnow(),
                    "last_sync_remote_updated_at": _coerce_datetime(remote_page.get("updatedAt") or remote_page.get("updated_at")),
                    "last_sync_title": remote_page.get("title") or page_context.meta.title,
                }
            )
            write_page_state(updated_meta)
            any_applied = True
            action = "pushed_forced" if status.sync_state == "conflicted" and selection.force else "pushed"
            message = "Local replica content pushed to remote Docmost."
            results.append(_applied_result(page_context, action, message))
            continue

        if status.sync_state == "local_only_page":
            if page_context.meta is None or page_context.local_text is None:
                results.append(_skip_result(page_context, "push_skipped", "Local-only page is missing metadata or content.", conflict_hunks, recommended_next_action="get_sync_diff"))
                continue

            response = create_remote_page(
                space_id=str(space_id),
                title=page_context.meta.title,
                content=page_context.local_text,
                parent_page_id=str(page_context.meta.parent_page_id) if page_context.meta.parent_page_id else None,
            )
            remote_page = response.get("page", response)
            updated_meta = page_context.meta.model_copy(
                update={
                    "page_id": UUID(str(remote_page["id"])),
                    "title": remote_page.get("title") or page_context.meta.title,
                    "slug_id": remote_page.get("slugId") or remote_page.get("slug_id") or page_context.meta.slug_id,
                    "base_content_hash": content_hash(page_context.local_text),
                    "last_sync_at": datetime.utcnow(),
                    "last_sync_remote_updated_at": _coerce_datetime(remote_page.get("updatedAt") or remote_page.get("updated_at")),
                    "last_sync_title": remote_page.get("title") or page_context.meta.title,
                }
            )
            write_page_state(updated_meta)
            any_applied = True
            results.append(_applied_result(page_context, "created_remote", "Local-only page created remotely and linked to the replica."))
            continue

        if status.sync_state == "synced":
            results.append(_skip_result(page_context, "already_synced", "Local and remote content already match."))
            continue

        if status.sync_state == "remote_only_change":
            results.append(_skip_result(page_context, "push_skipped", "Remote Docmost is ahead of the local replica. Pull it or force push to overwrite it.", recommended_next_action="pull_replica"))
            continue

        if status.sync_state == "conflicted":
            results.append(_skip_result(page_context, "conflict", "Local and remote both changed. Force push to take local, or inspect the diff first.", conflict_hunks, recommended_next_action="get_sync_diff"))
            continue

        if status.sync_state == "remote_only_page":
            results.append(_skip_result(page_context, "push_skipped", "Remote page has not been materialized locally yet. Pull it first if you want a local working copy.", recommended_next_action="pull_replica"))
            continue

        if status.sync_state == "remote_deleted":
            results.append(_skip_result(page_context, "push_skipped", "Remote page no longer exists. Review the local replica and decide whether to recreate it as a new page.", recommended_next_action="review_remote_deletion"))
            continue

        if status.sync_state == "local_missing":
            results.append(_skip_result(page_context, "push_skipped", "Local content file is missing. Pull it again or restore the file before pushing.", recommended_next_action="pull_replica"))
            continue

    _refresh_replica_state(space_id, operation="push", write_state=any_applied)
    return _build_operation_out(context, "push", selection.force, results, any_applied)


def _build_sync_context(space_id: UUID) -> SyncContext:
    replica_structure = get_replica_structure(space_id)
    local_paths = get_local_replica_paths(replica_structure)
    local_scan = scan_local_replica(replica_structure)
    remote_nodes = flatten_replica_nodes(replica_structure)
    remote_pages = {page.id: fetch_page(space_id, page.id) for page in fetch_pages(space_id)}

    page_contexts: list[SyncPageContext] = []

    for page_id, remote_page in remote_pages.items():
        meta = local_scan.page_meta_by_id.get(page_id)
        node = remote_nodes.get(page_id)
        local_content_path = meta.content_file_path if meta else (node.content_file_path if node else None)
        local_exists = False
        local_text: str | None = None
        if local_content_path is not None:
            local_exists, local_text = read_local_content(local_content_path)

        remote_text = remote_page.content or ""
        base_hash = meta.base_content_hash if meta else None
        local_hash = content_hash(local_text) if local_exists and local_text is not None else None
        remote_hash = content_hash(remote_text)
        status = _build_page_status(
            page_id=page_id,
            title=remote_page.title or (meta.title if meta else None),
            slug_id=remote_page.slug_id,
            parent_page_id=remote_page.parent_page_id,
            remote_exists=True,
            local_exists=local_exists,
            meta=meta,
            local_hash=local_hash,
            remote_hash=remote_hash,
            base_hash=base_hash,
            local_content_path=local_content_path,
            desired_content_path=node.content_file_path if node else None,
            desired_meta_path=node.meta_file_path if node else None,
        )
        page_contexts.append(
            SyncPageContext(
                status=status,
                local_text=local_text,
                remote_text=remote_text,
                meta=meta,
                remote_page=remote_page,
                desired_content_path=node.content_file_path if node else None,
                desired_meta_path=node.meta_file_path if node else None,
            )
        )

    remote_page_ids = set(remote_pages.keys())
    for meta in local_scan.page_metas:
        if meta.page_id is None:
            local_exists, local_text = read_local_content(meta.content_file_path)
            local_hash = content_hash(local_text) if local_exists and local_text is not None else None
            status = _build_page_status(
                page_id=None,
                title=meta.title,
                slug_id=meta.slug_id,
                parent_page_id=meta.parent_page_id,
                remote_exists=False,
                local_exists=local_exists,
                meta=meta,
                local_hash=local_hash,
                remote_hash=None,
                base_hash=meta.base_content_hash,
                local_content_path=meta.content_file_path,
                desired_content_path=meta.content_file_path,
                desired_meta_path=meta.meta_file_path,
            )
            page_contexts.append(
                SyncPageContext(
                    status=status,
                    local_text=local_text,
                    remote_text=None,
                    meta=meta,
                    remote_page=None,
                    desired_content_path=meta.content_file_path,
                    desired_meta_path=meta.meta_file_path,
                )
            )
            continue

        if meta.page_id not in remote_page_ids:
            local_exists, local_text = read_local_content(meta.content_file_path)
            local_hash = content_hash(local_text) if local_exists and local_text is not None else None
            status = _build_page_status(
                page_id=meta.page_id,
                title=meta.title,
                slug_id=meta.slug_id,
                parent_page_id=meta.parent_page_id,
                remote_exists=False,
                local_exists=local_exists,
                meta=meta,
                local_hash=local_hash,
                remote_hash=None,
                base_hash=meta.base_content_hash,
                local_content_path=meta.content_file_path,
                desired_content_path=meta.content_file_path,
                desired_meta_path=meta.meta_file_path,
            )
            page_contexts.append(
                SyncPageContext(
                    status=status,
                    local_text=local_text,
                    remote_text=None,
                    meta=meta,
                    remote_page=None,
                    desired_content_path=meta.content_file_path,
                    desired_meta_path=meta.meta_file_path,
                )
            )

    page_contexts.sort(key=lambda page_context: (page_context.status.local_path or page_context.status.desired_local_path or "", page_context.status.title or ""))
    return SyncContext(
        space=replica_structure.space,
        replica_root=replica_structure.replica_root,
        replica_root_abs_path=str(local_paths.root_path),
        replica_exists=local_scan.root_exists,
        page_contexts=page_contexts,
    )


def _build_page_status(
    *,
    page_id: UUID | None,
    title: str | None,
    slug_id: str | None,
    parent_page_id: UUID | None,
    remote_exists: bool,
    local_exists: bool,
    meta: ReplicaPageState | None,
    local_hash: str | None,
    remote_hash: str | None,
    base_hash: str | None,
    local_content_path: str | None,
    desired_content_path: str | None,
    desired_meta_path: str | None,
) -> PageSyncStatusOut:
    if not remote_exists and meta and meta.page_id is None:
        sync_state = "local_only_page" if local_exists else "local_missing"
        summary = "Local-only page is ready to be pushed to remote Docmost." if local_exists else "Local-only page metadata exists, but the local content file is missing."
        local_changed = local_exists
        remote_changed = False
        has_conflicts = False
    elif not remote_exists:
        sync_state = "remote_deleted"
        summary = "Local replica still tracks a page that no longer exists remotely."
        local_changed = bool(local_exists and base_hash and local_hash != base_hash)
        remote_changed = True
        has_conflicts = False
    elif meta is None:
        sync_state = "remote_only_page"
        summary = "Remote page has no local replica yet."
        local_changed = False
        remote_changed = True
        has_conflicts = False
    elif not local_exists:
        sync_state = "local_missing"
        summary = "Replica metadata exists, but the local content file is missing."
        local_changed = True
        remote_changed = bool(base_hash and remote_hash and remote_hash != base_hash)
        has_conflicts = False
    elif local_hash == remote_hash:
        sync_state = "synced"
        summary = "Local and remote content match."
        local_changed = bool(base_hash and local_hash != base_hash)
        remote_changed = bool(base_hash and remote_hash and remote_hash != base_hash)
        has_conflicts = False
    elif not base_hash:
        sync_state = "conflicted"
        summary = "Local and remote content differ, and no sync base is recorded."
        local_changed = True
        remote_changed = True
        has_conflicts = True
    else:
        local_changed = bool(local_hash and local_hash != base_hash)
        remote_changed = bool(remote_hash and remote_hash != base_hash)
        if local_changed and not remote_changed:
            sync_state = "local_only_change"
            summary = "Local replica changed since the last sync."
            has_conflicts = False
        elif remote_changed and not local_changed:
            sync_state = "remote_only_change"
            summary = "Remote Docmost page changed since the last sync."
            has_conflicts = False
        elif local_hash == remote_hash:
            sync_state = "synced"
            summary = "Local and remote content match, but the sync base metadata is outdated."
            has_conflicts = False
        else:
            sync_state = "conflicted"
            summary = "Local and remote both changed since the last sync."
            has_conflicts = True

    recommended_action, allowed_actions = _recommendation_for_state(sync_state)

    return PageSyncStatusOut(
        page_id=page_id,
        title=title or (meta.title if meta else None),
        slug_id=slug_id or (meta.slug_id if meta else None),
        parent_page_id=parent_page_id or (meta.parent_page_id if meta else None),
        sync_state=sync_state,
        summary=summary,
        local_path=local_content_path,
        local_abs_path=_logical_to_abs_string(local_content_path),
        desired_local_path=desired_content_path,
        desired_local_abs_path=_logical_to_abs_string(desired_content_path),
        meta_file_path=meta.meta_file_path if meta else desired_meta_path,
        meta_abs_path=_logical_to_abs_string(meta.meta_file_path if meta else desired_meta_path),
        remote_exists=remote_exists,
        local_exists=local_exists,
        local_changed=local_changed,
        remote_changed=remote_changed,
        has_conflicts=has_conflicts,
        recommended_action=recommended_action,
        allowed_actions=allowed_actions,
        base_content_hash=base_hash,
        local_content_hash=local_hash,
        remote_content_hash=remote_hash,
    )


def _build_page_diff(page_context: SyncPageContext) -> PageSyncDiffOut:
    status = page_context.status
    return PageSyncDiffOut(
        page_id=status.page_id,
        title=status.title,
        sync_state=status.sync_state,
        summary=status.summary,
        local_path=status.local_path,
        local_abs_path=status.local_abs_path,
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
    local_path_values = [path for path in local_paths if path]
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
    normalized = candidate.strip()
    if not normalized:
        return False
    options = {
        status.local_path or "",
        status.local_abs_path or "",
        status.desired_local_path or "",
        status.desired_local_abs_path or "",
    }
    stripped = normalized[2:] if normalized.startswith("./") else normalized
    return normalized in options or any(option and option[2:] == stripped for option in options if option.startswith("./"))


def _count_statuses(statuses: list[PageSyncStatusOut]) -> SyncStatusCountsOut:
    counts = SyncStatusCountsOut()
    for status in statuses:
        setattr(counts, status.sync_state, getattr(counts, status.sync_state) + 1)
    return counts


def _applied_result(page_context: SyncPageContext, action: str, message: str) -> SyncOperationResultOut:
    return SyncOperationResultOut(
        page_id=page_context.status.page_id,
        title=page_context.status.title,
        local_path=page_context.status.local_path,
        local_abs_path=page_context.status.local_abs_path,
        sync_state_before=page_context.status.sync_state,
        action=action,
        applied=True,
        message=message,
    )


def _skip_result(
    page_context: SyncPageContext,
    action: str,
    message: str,
    conflicts=None,
    recommended_next_action=None,
) -> SyncOperationResultOut:
    return SyncOperationResultOut(
        page_id=page_context.status.page_id,
        title=page_context.status.title,
        local_path=page_context.status.local_path,
        local_abs_path=page_context.status.local_abs_path,
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
    any_applied: bool,
) -> SyncOperationOut:
    return SyncOperationOut(
        space=context.space,
        operation=operation,
        replica_root=context.replica_root,
        replica_root_abs_path=context.replica_root_abs_path,
        force=force,
        generated_at=datetime.utcnow(),
        applied_count=sum(1 for result in results if result.applied),
        skipped_count=sum(1 for result in results if not result.applied and result.action != "conflict"),
        conflict_count=sum(1 for result in results if result.action == "conflict"),
        results=results,
    )


def _refresh_replica_state(space_id: UUID, *, operation: str, write_state: bool) -> None:
    if not write_state and operation != "pull":
        return
    replica_structure = get_replica_structure(space_id)
    now = datetime.utcnow()
    if operation == "pull":
        write_replica_state(replica_structure, last_pulled_at=now)
    else:
        write_replica_state(replica_structure, last_pushed_at=now)


def _logical_to_abs_string(value: str | None) -> str | None:
    if not value:
        return None
    from app.sync.config import logical_path_to_absolute

    return str(logical_path_to_absolute(value))


def _coerce_datetime(value: object) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    return None


def _pipeline_expectations() -> list[str]:
    return [
        "Call get_sync_status first to classify each page as local-ahead, remote-ahead, conflicted, or synced.",
        "Call get_sync_diff before any force operation or whenever the recommended action is get_sync_diff.",
        "pull_replica is one-way: it only materializes or refreshes the server-side replica from remote Docmost. It never auto-pushes local changes first.",
        "push_replica is one-way: it only writes local replica changes to remote Docmost. It never auto-pulls remote changes first.",
        "When an operation is blocked by the current state, follow the recommended_next_action instead of retrying the same command blindly.",
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
