import json
import os
from typing import Any, Dict, List, Optional

import requests


def chat(*, messages: List[Dict[str, Any]]) -> str:
    base = (os.getenv("OLLAMA_BASE_URL") or "").rstrip("/")
    model = (os.getenv("OLLAMA_MODEL") or "").strip()
    if not base:
        raise RuntimeError("OLLAMA_BASE_URL is required")
    if not model:
        raise RuntimeError("OLLAMA_MODEL is required")

    options_json = (os.getenv("OLLAMA_OPTIONS_JSON") or "").strip()
    options: Optional[Dict[str, Any]] = None
    if options_json:
        options = json.loads(options_json)

    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if options is not None:
        payload["options"] = options

    r = requests.post(f"{base}/api/chat", json=payload, timeout=180)
    r.raise_for_status()
    data = r.json()

    # Ollama returns { message: { role, content, ... }, ... }
    msg = (data.get("message") or {})
    content = msg.get("content")
    if not isinstance(content, str):
        raise RuntimeError(f"Unexpected Ollama response shape: {data}")
    return content
