from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from app.bridge.db.connection import get_conn
from app.bridge.repositories.page_heads import get_page_head, list_page_heads_for_space
from app.bridge.schemas.state import PageHeadRecord
from app.bridge.services.bootstrap import ensure_space_bootstrapped
from app.bridge.services.versioning import revision_hash
from app.bridge.services.write_pipeline import (
    create_page_via_bridge,
    move_page_via_bridge,
    update_page_via_bridge,
)
from app.reconcile.schemas import (
    ReconcileAppliedItem,
    ReconcileConflictItem,
    ReconcileDeletionItem,
    ReconcileErrorItem,
    ReconcileIn,
    ReconcileOut,
    ReconcilePageIn,
    ReconcileSyncedItem,
    ReconcileTreeNodeIn,
)
from app.sync.diffing import build_diff_hunks


# ---------------------------------------------------------------------------
# Classification primitives
# ---------------------------------------------------------------------------

def _s(value) -> str | None:
    return str(value) if value is not None else None


def _three_way(local: str | None, base: str | None, head: str | None) -> str:
    """Content three-way. A None base is an UNKNOWN baseline (no recorded sync) -> conflict."""
    if local == head:
        return "synced"
    if base is None:
        return "conflict"
    if base == head:
        return "local_ahead"
    if base == local:
        return "remote_ahead"
    return "conflict"


def _three_way_struct(local: str | None, base: str | None, head: str | None) -> str:
    """Structural three-way. None is a LEGITIMATE value (root parent / no icon), not unknown,
    so it never forces a conflict. The baseline comes from the last-synced tree node."""
    if local == head:
        return "synced"
    if base == head:
        return "local_ahead"
    if base == local:
        return "remote_ahead"
    return "conflict"


def _combine(*states: str) -> str:
    """Fold per-field states into one disposition. Mixed directions clash."""
    s = set(states)
    if "conflict" in s:
        return "conflict"
    has_local = "local_ahead" in s
    has_remote = "remote_ahead" in s
    if has_local and has_remote:
        return "conflict"
    if has_local:
        return "local_ahead"
    if has_remote:
        return "remote_ahead"
    return "synced"


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------

def _scoped_page_ids(request: ReconcileIn, all_heads: list[PageHeadRecord]) -> set[UUID]:
    if request.scope == "space":
        return {h.page_id for h in all_heads}
    if request.scope == "page":
        return {request.scope_id} if request.scope_id else set()
    if request.scope == "tree":
        if not request.scope_id:
            return set()
        children: dict[UUID, list[UUID]] = defaultdict(list)
        for h in all_heads:
            if h.parent_page_id:
                children[h.parent_page_id].append(h.page_id)
        result: set[UUID] = set()
        stack = [request.scope_id]
        while stack:
            node = stack.pop()
            if node in result:
                continue
            result.add(node)
            stack.extend(children.get(node, []))
        return result
    return set()


# ---------------------------------------------------------------------------
# Reconcile entry
# ---------------------------------------------------------------------------

def reconcile(space_id: UUID, request: ReconcileIn) -> ReconcileOut:
    ensure_space_bootstrapped(space_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            all_heads = list_page_heads_for_space(cur, space_id)
    heads_by_id = {h.page_id: h for h in all_heads}
    scoped_ids = _scoped_page_ids(request, all_heads)

    local_by_id = {p.page_id: p for p in request.pages if p.page_id is not None}
    local_new = [p for p in request.pages if p.page_id is None]
    tree_by_id = {n.page_id: n for n in request.tree}

    out = ReconcileOut(scope=request.scope)

    # (1) local-only new pages -> create
    for page in local_new:
        _apply_create(space_id, page, out)

    # (2) tracked local pages -> classify + apply
    for pid, page in local_by_id.items():
        _reconcile_tracked(space_id, page, heads_by_id.get(pid), tree_by_id.get(pid), out)

    # (3) bridge pages in scope but not present locally
    for pid in scoped_ids:
        if pid in local_by_id:
            continue
        head = heads_by_id.get(pid)
        if head is None or head.is_deleted:
            continue
        if pid in tree_by_id:
            # was synced before, local file now gone -> local deletion (-> soft-delete remote)
            out.deletion_confirmations.append(
                ReconcileDeletionItem(
                    page_id=pid,
                    local_path=None,
                    title=head.title,
                    direction="remote",
                    reason="in last-synced tree but local copy removed",
                )
            )
        else:
            # never materialized locally -> pull/materialize
            out.applied.append(
                ReconcileAppliedItem(
                    page_id=pid,
                    local_path=None,
                    action="pulled",
                    title=head.title,
                    slug_id=head.slug_id,
                    parent_page_id=head.parent_page_id,
                    position=head.position,
                    icon=head.icon,
                    base_revision_hash=head.current_revision_hash,
                    content=head.content,
                )
            )

    return out


# ---------------------------------------------------------------------------
# Per-page handling
# ---------------------------------------------------------------------------

def _apply_create(space_id: UUID, page: ReconcilePageIn, out: ReconcileOut) -> None:
    try:
        res = create_page_via_bridge(
            space_id=space_id,
            title=page.title,
            content=page.content,
            parent_page_id=page.parent_page_id,
            caller_mode="auto_sync",
        )
        remote = res.remote_page or {}
        out.applied.append(
            ReconcileAppliedItem(
                page_id=res.page_id,
                local_path=page.local_path,
                action="created",
                title=res.title,
                slug_id=res.slug_id,
                parent_page_id=res.parent_page_id,
                position=remote.get("position") or page.position,
                icon=remote.get("icon") if remote.get("icon") is not None else page.icon,
                base_revision_hash=res.base_revision_hash,
            )
        )
    except Exception as exc:  # best-effort per page
        out.errors.append(ReconcileErrorItem(page_id=None, local_path=page.local_path, message=str(exc)))


def _conflict_item(page: ReconcilePageIn, head: PageHeadRecord | None, reason: str) -> ReconcileConflictItem:
    remote_content = head.content if (head is not None and not head.is_deleted) else None
    return ReconcileConflictItem(
        page_id=page.page_id,
        local_path=page.local_path,
        title=page.title,
        reason=reason,
        base_revision_hash=page.base_revision_hash,
        local_version=revision_hash(page.title, page.content),
        remote_version=head.current_revision_hash if head else None,
        local_content=page.content,
        remote_content=remote_content,
        diff=build_diff_hunks(page.content, remote_content),
    )


def _reconcile_tracked(
    space_id: UUID,
    page: ReconcilePageIn,
    head: PageHeadRecord | None,
    node: ReconcileTreeNodeIn | None,
    out: ReconcileOut,
) -> None:
    pid = page.page_id
    assert pid is not None

    if head is None:
        out.errors.append(
            ReconcileErrorItem(page_id=pid, local_path=page.local_path, message="Page is unknown to the bridge (no head).")
        )
        return

    local_hash = revision_hash(page.title, page.content)

    # Remote soft-deleted.
    if head.is_deleted:
        if page.base_revision_hash and local_hash != page.base_revision_hash:
            out.conflicts.append(_conflict_item(page, head, reason="delete_vs_change"))
        else:
            out.deletion_confirmations.append(
                ReconcileDeletionItem(
                    page_id=pid,
                    local_path=page.local_path,
                    title=page.title,
                    direction="local",
                    reason="remote soft-deleted; drop local copy",
                )
            )
        return

    base = page.base_revision_hash
    head_hash = head.current_revision_hash

    # --- classify ---
    content_state = _three_way(local_hash, base, head_hash)
    if node is not None:
        parent_state = _three_way_struct(_s(page.parent_page_id), _s(node.parent_page_id), _s(head.parent_page_id))
        position_state = _three_way_struct(_s(page.position), _s(node.position), _s(head.position))
        structural_state = _combine(parent_state, position_state)
        icon_state = _three_way_struct(_s(page.icon), _s(node.icon), _s(head.icon))
    else:
        structural_state = "synced"
        icon_state = "synced"

    if "conflict" in (content_state, structural_state, icon_state):
        reason = "both_changed" if content_state == "conflict" else "structural_both_changed"
        out.conflicts.append(_conflict_item(page, head, reason=reason))
        return

    # --- apply clean one-sided changes ---
    try:
        current_base = base
        if content_state == "local_ahead":
            res = update_page_via_bridge(
                page_id=pid,
                title=page.title,
                content=page.content,
                operation="replace",
                caller_mode="auto_sync",
                expected_base_revision_hash=current_base,
                expected_space_id=space_id,
            )
            current_base = res.base_revision_hash

        if structural_state == "local_ahead":
            res = move_page_via_bridge(
                page_id=pid,
                position=page.position or head.position or "",
                parent_page_id=page.parent_page_id,
                caller_mode="auto_sync",
                expected_space_id=space_id,
            )
            current_base = res.base_revision_hash

        if icon_state == "local_ahead":
            res = update_page_via_bridge(
                page_id=pid,
                title=page.title,
                content=None,
                operation="replace",
                caller_mode="auto_sync",
                expected_base_revision_hash=current_base,
                expected_space_id=space_id,
                icon=page.icon,
            )
            current_base = res.base_revision_hash
    except Exception as exc:
        out.errors.append(ReconcileErrorItem(page_id=pid, local_path=page.local_path, message=str(exc)))
        return

    # --- decide what to report, reading the post-write head as canonical ---
    with get_conn() as conn:
        with conn.cursor() as cur:
            head2 = get_page_head(cur, pid) or head

    any_local = "local_ahead" in (content_state, structural_state, icon_state)
    any_remote = "remote_ahead" in (content_state, structural_state, icon_state)

    if not any_local and not any_remote:
        out.synced.append(
            ReconcileSyncedItem(page_id=pid, local_path=page.local_path, base_revision_hash=head_hash)
        )
        return

    if content_state == "local_ahead":
        action = "pushed"
    elif content_state == "remote_ahead":
        action = "pulled"
    elif structural_state == "local_ahead":
        action = "moved"
    else:
        action = "structural"

    # page.md only needs rewriting when the remote content moved (remote_ahead on content).
    content = head2.content if content_state == "remote_ahead" else None

    out.applied.append(
        ReconcileAppliedItem(
            page_id=pid,
            local_path=page.local_path,
            action=action,
            title=head2.title,
            slug_id=head2.slug_id,
            parent_page_id=head2.parent_page_id,
            position=head2.position,
            icon=head2.icon,
            base_revision_hash=head2.current_revision_hash,
            content=content,
        )
    )
