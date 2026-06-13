"""Single write-path entrypoint that normalises outgoing markdown for Docmost's `marked` ingest.

Composes the conversion gate's write half in the order the hazards occur in Docmost's pipeline
(markdown -> marked HTML -> happy-dom/tiptap ProseMirror -> DB): block structure first
(front-matter strip guard, then ordered-list marker-width reflow), then inline escaping (flanking
`_`/`__` and non-schema HTML tags). Every step is idempotent and a no-op on the canonical egress
form, so re-pushing a read-back stays a no-op and the revision hash is stable.

All Docmost writes route their content through this one function (app/write/docmost.py).
"""

from __future__ import annotations

from app.write.ingest_escape import escape_markdown_for_ingest
from app.write.ingest_reflow import guard_frontmatter_strip, reflow_ordered_lists_for_ingest


def normalize_markdown_for_ingest(md: str) -> str:
    """Apply every write-path countermalform, block structure before inline escaping."""
    if not md:
        return md
    return escape_markdown_for_ingest(
        reflow_ordered_lists_for_ingest(guard_frontmatter_strip(md))
    )
