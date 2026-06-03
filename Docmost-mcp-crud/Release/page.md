This page summarizes what the service currently provides. The service is a private bridge used to give an MCP-consuming model (Claude Code) versioned, reconcilable access to a live Docmost deployment.

## Current capabilities

- REST API over Docmost: spaces, pages, tree, create / update / move / delete, all through a bridge write pipeline.
- Bridge-owned version state in a separate PostgreSQL database: a head plus append-only version history per page, with write intents and receipts.
- Single revision-hash derivation from Docmost read-back content, so every surface (helper, direct CRUD, the worker, and direct Docmost-UI edits) agrees on the hash.
- A reconcile brain (`POST /v1/spaces/{id}/reconcile`) that classifies each page three-way and applies clean one-sided changes, returning conflicts and deletion confirmations for a decision.
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