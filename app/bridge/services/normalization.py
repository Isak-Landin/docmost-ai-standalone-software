from __future__ import annotations

import unicodedata


def canonicalize_title(text: str | None) -> str:
    normalized = (text or "").strip()
    return unicodedata.normalize("NFC", normalized)


def canonicalize_content(text: str | None) -> str:
    normalized = (text or "").lstrip("\ufeff")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = unicodedata.normalize("NFC", normalized)
    return "\n".join(normalized.splitlines())


def apply_content_operation(existing_content: str | None, incoming_content: str | None, operation: str) -> str:
    existing = canonicalize_content(existing_content)
    incoming = canonicalize_content(incoming_content)
    if operation == "replace":
        return incoming
    if operation == "append":
        if not existing:
            return incoming
        if not incoming:
            return existing
        return f"{existing}\n{incoming}"
    if operation == "prepend":
        if not existing:
            return incoming
        if not incoming:
            return existing
        return f"{incoming}\n{existing}"
    raise ValueError(f"Unsupported page update operation: {operation}")
