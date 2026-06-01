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
