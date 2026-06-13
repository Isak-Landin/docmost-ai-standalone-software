This page summarizes what the service currently provides. The service is a private bridge used to give an MCP-consuming model (Claude Code) versioned, reconcilable access to a live Docmost deployment.

## Current capabilities

- REST API over Docmost: spaces, pages, tree, create / update / move / delete, all through a bridge write pipeline.
- Bridge-owned version state in a separate PostgreSQL database: a head plus append-only version history per page, with write intents and receipts.
- Single revision-hash derivation from Docmost read-back content, so every surface (helper, direct CRUD, the worker, and direct Docmost-UI edits) agrees on the hash.
- A reconcile brain (`POST /v1/spaces/{id}/reconcile`) that classifies each page three-way and applies clean one-sided changes, returning conflicts and deletion confirmations for a decision.
- A structure-preserving ProseMirror-to-markdown renderer that is the faithful inverse of Docmost's `marked` ingest (matching its serializer conventions, with position-aware escaping), so nested lists, tables, task lists, callouts, and code round-trip without flattening or marker corruption.
- Write-path ingest normalization that mirrors the renderer (the ingest half of the Conversion Gate): every write re-indents an under-indented sub-list to the parent marker width so nesting is preserved, guards Docmost's leading front-matter strip, and escapes flanking `_`/`__` and non-schema HTML tags outside code, so nested lists, code, paths like `app/__init__.py`, and stray tags reach Docmost faithfully instead of being flattened, parsed as bold, or silently dropped. Two Docmost-owned edges remain (the `$`/math grab and inline-code edge whitespace) - see Conversion Gate and Known Limitations.
- A whole-space resync (`resync_space`, server `force_rerender` observe + the same two-way reconcile) that re-renders every page from Docmost and brings the space into sync regardless of whether a page changed - the path that propagates a server-side rendering change, healing via pull and surfacing conflicts the same way, never force-pushing.
- A helper-facing contract under `/v1` and `/helper/v1` (reads, writes, move, snapshots, reconcile, resolve, confirm-deletion) plus batch and observe routes under `/auto-mcp`.
- A background observer worker that folds direct-Docmost-UI edits into bridge state for every space on an interval, and backfills spaces that already hold content.
- A client-side helper (stdio MCP) that is the model's only Docmost surface and owns the local replica.
- An operator `/mcp` HTTP surface for inspection and emergency override.

## Surfaces at a glance

| Surface | Audience | Transport |
| --- | --- | --- |
| `docmost-helper` | the model | stdio |
| REST + `/v1` + `/helper/v1` + `/auto-mcp` | the helper, and direct HTTP integrations | HTTP |
| `/mcp` | a human operator | streamable HTTP |

## Constraints

- Content is markdown in and out; the page title is a separate field; use plain ASCII punctuation.
- Space slugs must be alphanumeric (no spaces or dashes), a Docmost constraint.
- Write operations require Docmost v0.71.1 or later.