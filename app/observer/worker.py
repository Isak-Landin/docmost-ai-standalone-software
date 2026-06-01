from __future__ import annotations

import argparse
import os
import time
from uuid import UUID

from app.bridge.services.observer import observe_space


def _observe_all() -> None:
    """Run one observer pass over every Docmost space."""
    from app.query.docmost import list_spaces

    for space in list_spaces():
        try:
            result = observe_space(space.id)
            print(
                {
                    "space_id": str(result.space_id),
                    "checked": result.checked_pages,
                    "bridge_confirmed": result.bridge_writes_confirmed,
                    "ext_updates": result.external_updates_recorded,
                    "ext_deletes": result.external_deletions_recorded,
                },
                flush=True,
            )
        except Exception as exc:
            print({"space_id": str(space.id), "error": str(exc)}, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Observe Docmost spaces and record bridge-owned remote changes."
    )
    parser.add_argument(
        "space_id",
        nargs="?",
        help="Observe one space once. Omit (or pass --loop) to observe all spaces on an interval.",
    )
    parser.add_argument("--loop", action="store_true", help="Run continuously over all spaces.")
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("WORKER_INTERVAL_SECONDS", "15")),
        help="Seconds between loop passes (default 15).",
    )
    args = parser.parse_args()

    if args.loop or not args.space_id:
        print({"worker": "started", "interval_seconds": args.interval}, flush=True)
        while True:
            try:
                _observe_all()
            except Exception as exc:
                print({"worker_loop_error": str(exc)}, flush=True)
            time.sleep(args.interval)
        return

    result = observe_space(UUID(args.space_id))
    print(
        {
            "space_id": str(result.space_id),
            "checked_pages": result.checked_pages,
            "bridge_writes_confirmed": result.bridge_writes_confirmed,
            "external_updates_recorded": result.external_updates_recorded,
            "external_deletions_recorded": result.external_deletions_recorded,
        }
    )


if __name__ == "__main__":
    main()
