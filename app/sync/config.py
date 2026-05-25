from __future__ import annotations

import os
from pathlib import Path


def get_replica_root_base() -> Path:
    raw = (os.getenv("DOCMOST_REPLICA_ROOT_BASE") or ".").strip()
    return Path(raw).expanduser()


def logical_path_to_absolute(logical_path: str) -> Path:
    trimmed = logical_path[2:] if logical_path.startswith("./") else logical_path
    return (get_replica_root_base() / trimmed).resolve()


def absolute_path_to_logical(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(get_replica_root_base().resolve())
        return f"./{rel.as_posix()}"
    except ValueError:
        return path.resolve().as_posix()

