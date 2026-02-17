from typing import Any, Dict, List


def build_messages(*, user_message: str, page_blobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Returns Ollama-style messages[].
    page_blobs are the *fetched* objects from docmost-fetcher, already filtered by caller.
    """
    messages: List[Dict[str, Any]] = []

    # System: context
    for blob in page_blobs:
        # blob is expected to contain {"ok": True, "page": {...}}
        page = (blob.get("page") or {})
        title = page.get("title") or "(untitled)"
        text = page.get("text_content") or ""
        messages.append({
            "role": "system",
            "content": f"{title}:\n{text}",
        })

    messages.append({"role": "user", "content": user_message})
    return messages
