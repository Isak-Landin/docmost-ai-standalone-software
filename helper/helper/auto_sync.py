"""In-helper background auto-sync.

A single daemon thread that, while the helper MCP is loaded in a Claude session, periodically runs
the SAME reconcile pipeline the model uses (`helper.sync.sync_space`) for every discovered replica,
then posts any genuine conflicts/deletions that pipeline surfaces to the server's auto-conflict
store so the model can see them via the `/health` MCP surface.

It adds NO sync logic of its own. `sync_space` already pushes local edits, pulls remote changes,
materializes/moves pages, and surfaces real conflicts; this module only triggers it on an interval
and forwards the findings. It NEVER forces and NEVER resolves a conflict - it only parks awareness.

Activation:
- Opt-in via `DOCMOST_AUTO_SYNC` (off unless set to a truthy value), so deploying this never starts
  background syncing without explicit enablement.
- Interval via `DOCMOST_AUTO_SYNC_INTERVAL_SECONDS` (default 30).
- It only exists for the lifetime of the helper process, i.e. while a Claude session has the MCP
  loaded - an accepted limitation.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from uuid import UUID

# Mirror server.py / replica_autosync.py: make `helper.*` importable regardless of entry point.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helper import client  # noqa: E402
from helper import replica_autosync  # noqa: E402
from helper import sync as sync_mod  # noqa: E402
from helper.replica import discover_all_replica_roots  # noqa: E402

ENABLE_ENV = "DOCMOST_AUTO_SYNC"
INTERVAL_ENV = "DOCMOST_AUTO_SYNC_INTERVAL_SECONDS"
DEFAULT_INTERVAL = 30
MIN_INTERVAL = 5

_started = False
_start_lock = threading.Lock()


def enabled() -> bool:
    val = (os.environ.get(ENABLE_ENV) or "").strip().lower()
    return val not in ("", "0", "false", "off", "no")


def _interval_seconds() -> int:
    try:
        interval = int(os.environ.get(INTERVAL_ENV, str(DEFAULT_INTERVAL)))
    except ValueError:
        interval = DEFAULT_INTERVAL
    return max(interval, MIN_INTERVAL)


def _findings_payload(result: dict) -> list[dict]:
    """Map the existing reconcile contract's conflicts/deletions to auto-conflict store items
    (metadata only - the model re-fetches full detail via sync_page through the same pipeline)."""
    items: list[dict] = []
    for c in result.get("conflicts", []) or []:
        if not c.get("page_id"):
            continue
        items.append(
            {
                "page_id": str(c["page_id"]),
                "kind": "conflict",
                "reason": c.get("reason"),
                "title": c.get("title"),
                "local_path": c.get("local_path"),
                "base_revision_hash": c.get("base_revision_hash"),
                "base_version_id": str(c["base_version_id"]) if c.get("base_version_id") else None,
                "local_version": c.get("local_version"),
                "remote_version": c.get("remote_version"),
            }
        )
    for d in result.get("deletion_confirmations", []) or []:
        if not d.get("page_id"):
            continue
        items.append(
            {
                "page_id": str(d["page_id"]),
                "kind": "deletion",
                "reason": d.get("reason") or d.get("direction"),
                "title": d.get("title"),
                "local_path": d.get("local_path"),
            }
        )
    return items


def _sync_one(space_id_str: str, root: str) -> None:
    try:
        result = sync_mod.sync_space(UUID(space_id_str), local_root=root)
    except Exception as exc:  # one bad space must not stop the loop
        print({"auto_sync": "sync_error", "space_id": space_id_str, "error": str(exc)}, file=sys.stderr, flush=True)
        return
    items = _findings_payload(result)
    if items:
        try:
            client.post_auto_conflicts(UUID(space_id_str), items)
        except Exception as exc:
            print({"auto_sync": "post_error", "space_id": space_id_str, "error": str(exc)}, file=sys.stderr, flush=True)
    # Initiation parity with the MCP sync tools (which are @autosync_after): back up the replica.
    try:
        replica_autosync.autosync_async(root)
    except Exception:
        pass


def _run_once() -> None:
    for space_id_str, root in discover_all_replica_roots():
        _sync_one(space_id_str, root)


def _loop(interval: int) -> None:
    while True:
        try:
            _run_once()
        except Exception as exc:
            print({"auto_sync": "loop_error", "error": str(exc)}, file=sys.stderr, flush=True)
        time.sleep(interval)


def start_auto_sync() -> None:
    """Start the background loop once, if enabled. Idempotent; never raises."""
    global _started
    try:
        if not enabled():
            return
        with _start_lock:
            if _started:
                return
            interval = _interval_seconds()
            thread = threading.Thread(target=_loop, args=(interval,), name="docmost-auto-sync", daemon=True)
            thread.start()
            _started = True
            print({"auto_sync": "started", "interval_seconds": interval}, file=sys.stderr, flush=True)
    except Exception as exc:
        print({"auto_sync": "start_error", "error": str(exc)}, file=sys.stderr, flush=True)
