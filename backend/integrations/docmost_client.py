import os
from typing import Dict, Any
import requests


def fetch_page_content(*, space_id: str, page_id: str) -> Dict[str, Any]:
    base = (os.getenv("DOCMOST_FETCHER_INTERNAL_BASE_URL") or "").rstrip("/")
    if not base:
        raise RuntimeError("DOCMOST_FETCHER_INTERNAL_BASE_URL is required")

    url = f"{base}/get-content"
    # REMOVED SPACE_ID FOR SINGLE PAGE CONTENT FETCH
    #  params={"space_id": space_id, "page_id": page_id}
    r = requests.get(url, params={"page_id": page_id}, timeout=20)
    r.raise_for_status()
    return r.json()
