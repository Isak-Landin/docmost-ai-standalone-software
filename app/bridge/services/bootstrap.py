from __future__ import annotations

from threading import Lock
from uuid import UUID

from app.bridge.db.connection import get_conn
from app.bridge.db.schema import ensure_schema
from app.bridge.repositories.observer_checkpoints import upsert_observer_checkpoint
from app.bridge.repositories.page_heads import list_page_heads_for_space, upsert_page_head
from app.bridge.repositories.page_versions import upsert_page_version
from app.bridge.services.canonical import snapshot_from_fetched_page
from app.query.docmost import get_page as fetch_page
from app.query.docmost import list_pages as fetch_pages

_BOOTSTRAPPED_SPACES: set[UUID] = set()
_BOOTSTRAP_LOCK = Lock()


def ensure_space_bootstrapped(space_id: UUID) -> None:
    if space_id in _BOOTSTRAPPED_SPACES:
        return

    ensure_schema()

    with _BOOTSTRAP_LOCK:
        if space_id in _BOOTSTRAPPED_SPACES:
            return

        remote_pages = fetch_pages(space_id)
        with get_conn() as conn:
            with conn.cursor() as cur:
                known_page_ids = {head.page_id for head in list_page_heads_for_space(cur, space_id)}

        missing_pages = [page for page in remote_pages if page.id not in known_page_ids]
        if not missing_pages:
            _BOOTSTRAPPED_SPACES.add(space_id)
            return

        snapshots = []
        for remote_page in missing_pages:
            full_page = fetch_page(space_id, remote_page.id)
            snapshots.append(snapshot_from_fetched_page(full_page))

        with get_conn() as conn:
            with conn.cursor() as cur:
                for snapshot in snapshots:
                    version = upsert_page_version(cur, snapshot, source="bootstrap")
                    upsert_page_head(cur, snapshot, version_id=version.id, source="bootstrap")
                    upsert_observer_checkpoint(
                        cur,
                        page_id=snapshot.page_id,
                        space_id=snapshot.space_id,
                        last_seen_remote_updated_at=snapshot.remote_updated_at,
                        last_observed_revision_hash=snapshot.revision_hash,
                    )
        _BOOTSTRAPPED_SPACES.add(space_id)
