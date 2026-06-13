from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


def _meta_path(local_path: str) -> str:
    return os.path.join(os.path.dirname(local_path), "_meta.json")


def read_page(local_path: str) -> str:
    return Path(local_path).read_text(encoding="utf-8")


def write_page(local_path: str, content: str) -> None:
    _atomic_write(local_path, content)


def read_meta(local_path: str) -> dict[str, Any]:
    path = _meta_path(local_path)
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def write_meta(local_path: str, meta: dict[str, Any]) -> None:
    _atomic_write(_meta_path(local_path), json.dumps(meta, indent=2, default=str))


def update_meta_after_sync(
    local_path: str,
    response: dict[str, Any],
    space_id: str | None = None,
) -> None:
    meta = read_meta(local_path)
    if response.get("page_id"):
        meta["id"] = str(response["page_id"])
    if response.get("title") is not None:
        meta["title"] = response["title"]
    if response.get("slug_id") is not None:
        meta["slug_id"] = response["slug_id"]
    if response.get("parent_page_id") is not None:
        meta["parent_page_id"] = str(response["parent_page_id"])
    if response.get("base_revision_hash") is not None:
        meta["base_revision_hash"] = response["base_revision_hash"]
    if response.get("base_version_id") is not None:
        meta["base_version_id"] = str(response["base_version_id"])
    if space_id:
        meta["space_id"] = space_id
    meta["content_file_path"] = local_path
    meta["meta_file_path"] = _meta_path(local_path)
    write_meta(local_path, meta)


def extract_title_from_page(local_path: str) -> str | None:
    try:
        first_line = Path(local_path).read_text(encoding="utf-8").split("\n")[0].strip()
        if first_line.startswith("#"):
            return first_line.lstrip("#").strip() or None
        return first_line or None
    except (FileNotFoundError, IndexError):
        return None


def split_leading_h1(text: str) -> tuple[str | None, str]:
    """If the body starts (after optional blank lines) with a level-1 '# ' heading, return
    (title, body_without_that_heading). Otherwise (None, text). Lets a new local-only page be
    authored as '# Title\\n\\nbody' while the title is lifted into the page title field and the
    heading is removed from the body, so Docmost does not render the title plus a duplicate H1."""
    lines = text.split("\n")
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i < len(lines) and lines[i].lstrip().startswith("# "):
        title = lines[i].lstrip()[2:].strip()
        if title:
            rest = lines[:i] + lines[i + 1:]
            return title, "\n".join(rest).lstrip("\n")
    return None, text


def update_meta_after_pull(local_path: str, page: dict[str, Any]) -> None:
    meta = read_meta(local_path)
    if page.get("page_id"):
        meta["id"] = str(page["page_id"])
    if page.get("title") is not None:
        meta["title"] = page["title"]
    if page.get("slug_id") is not None:
        meta["slug_id"] = page["slug_id"]
    if page.get("space_id"):
        meta["space_id"] = str(page["space_id"])
    if page.get("parent_page_id") is not None:
        meta["parent_page_id"] = str(page["parent_page_id"])
    if page.get("position") is not None:
        meta["position"] = page["position"]
    if page.get("icon") is not None:
        meta["icon"] = page["icon"]
    # current_revision_hash from server becomes the new sync base
    if page.get("current_revision_hash") is not None:
        meta["base_revision_hash"] = page["current_revision_hash"]
    if page.get("current_version_id") is not None:
        meta["base_version_id"] = str(page["current_version_id"])
    meta["content_file_path"] = local_path
    meta["meta_file_path"] = _meta_path(local_path)
    write_meta(local_path, meta)


def clear_active_snapshot(local_path: str) -> None:
    meta = read_meta(local_path)
    meta.pop("active_snapshot", None)
    write_meta(local_path, meta)


def record_active_snapshot(local_path: str, snapshot_id: str, base_revision_hash: str | None) -> None:
    meta = read_meta(local_path)
    meta["active_snapshot"] = {
        "snapshot_id": snapshot_id,
        "base_revision_hash": base_revision_hash,
    }
    write_meta(local_path, meta)


def resolve_page_dir(local_root: str, page: dict[str, Any]) -> str:
    title = page.get("title") or page.get("page_id") or "untitled"
    slug = page.get("slug_id") or ""
    name = slug if slug else _slugify(str(title))
    return os.path.join(local_root, name)


def page_path_from_dir(page_dir: str) -> str:
    return os.path.join(page_dir, "page.md")


def find_local_pages(local_root: str) -> list[str]:
    root = Path(local_root)
    if not root.exists():
        return []
    return [str(p) for p in root.rglob("page.md")]


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[\s]+", "-", text)
    text = re.sub(r"[^\w-]", "", text)  # keep word chars (letters, digits, _) and hyphens
    text = re.sub(r"_+", "-", text)     # replace underscores with hyphens for readability
    text = re.sub(r"-+", "-", text)     # collapse multiple hyphens
    return text[:60].strip("-") or "page"


def _atomic_write(path: str, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _tree_path(local_root: str) -> str:
    return os.path.join(local_root, "_tree.json")


def write_tree_snapshot(local_root: str, entries: list[dict[str, Any]]) -> None:
    _atomic_write(_tree_path(local_root), json.dumps({"pages": entries}, indent=2, default=str))


def read_tree_snapshot(local_root: str) -> dict[str, Any]:
    try:
        return json.loads(Path(_tree_path(local_root)).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"pages": []}


# ---------------------------------------------------------------------------
# _replica.json space header + working-copy discovery by space_id
# ---------------------------------------------------------------------------


def _replica_header_path(local_root: str) -> str:
    return os.path.join(local_root, "_replica.json")


def read_replica_header(local_root: str) -> dict[str, Any]:
    try:
        return json.loads(Path(_replica_header_path(local_root)).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_replica_header(local_root: str, space_id: str, slug: str | None = None, name: str | None = None) -> None:
    header = read_replica_header(local_root)
    header["space_id"] = str(space_id)
    if slug is not None:
        header["slug"] = slug
    if name is not None:
        header["name"] = name
    _atomic_write(_replica_header_path(local_root), json.dumps(header, indent=2, default=str))


def replica_base_dir() -> str:
    return os.environ.get("DOCMOST_REPLICA_BASE", ".")


_DISCOVERY_SKIP_DIRS = {".git", ".claude", ".venv", "node_modules", "__pycache__"}


def discover_replica_root(space_id: str, base_dir: str | None = None) -> str | None:
    base = Path(base_dir or replica_base_dir())
    if not base.exists():
        return None
    for header in base.rglob("_replica.json"):
        if set(header.parts) & _DISCOVERY_SKIP_DIRS:
            continue
        try:
            data = json.loads(header.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if str(data.get("space_id")) == str(space_id):
            return str(header.parent)
    return None


def discover_all_replica_roots(base_dir: str | None = None) -> list[tuple[str, str]]:
    """Every (space_id, root_path) replica under base_dir, by `_replica.json` marker (the same
    marker the helper already uses). The auto-sync loop uses this to enumerate spaces to reconcile."""
    base = Path(base_dir or replica_base_dir())
    if not base.exists():
        return []
    found: list[tuple[str, str]] = []
    for header in base.rglob("_replica.json"):
        if set(header.parts) & _DISCOVERY_SKIP_DIRS:
            continue
        try:
            data = json.loads(header.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        space_id = data.get("space_id")
        if space_id:
            found.append((str(space_id), str(header.parent)))
    return found


def resolve_local_root(
    space_id: str,
    slug: str | None = None,
    local_root: str | None = None,
    base_dir: str | None = None,
) -> str:
    if local_root:
        return local_root
    found = discover_replica_root(space_id, base_dir=base_dir)
    if found:
        return found
    base = base_dir or replica_base_dir()
    return os.path.join(base, f"{slug or space_id}-replica")
