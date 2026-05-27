from __future__ import annotations

import argparse
from uuid import UUID

from app.bridge.services.observer import observe_space


def main() -> None:
    parser = argparse.ArgumentParser(description="Observe one Docmost space and record bridge-owned remote changes.")
    parser.add_argument("space_id", help="Docmost space UUID to observe.")
    args = parser.parse_args()
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
