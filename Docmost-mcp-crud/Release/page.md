# Release

## v1.0.0 (baseline)

First stable release of the Docmost MCP service.

### Distribution

The service is run from source via Docker Compose on the server hosting Docmost (build-and-run; no
separate registry pull required). See [Deployment](../Deployment/page.md) for the current setup.

### What was included in v1.0.0

- REST API for Docmost: spaces, pages, children, create, update, delete
- MCP server exposing the core operations as callable tools
- Markdown in / markdown out
- Auth handled transparently on every write request
- Fully environment-driven - no hardcoded values
- Docker Compose setup with shared external network support
- Hardened MCP server instructions: all write tool IDs must originate from live tool responses,
  never inferred or invented

### Known characteristics

Context-window usage is high per session when used through an AI coding assistant. A full workflow
(refactoring, re-analysing, local replica management, remote sync) typically consumes tens to a few
hundred KB of context for a tested case of roughly 25 documentation files.

### Limitations (v1.0.0)

- REST write routes return page identity and metadata only - content is not echoed back. Use a
  page read if content verification is needed after a write.
- Space slugs must be alphanumeric, no dashes or spaces (a Docmost constraint).

## Since v1.0.0

Later work added, and the service now includes:

- A **local-first replica and sync workflow** (status, diff, pull, push) for maintaining a local
  editable copy of remote docs and reconciling changes safely.
- A **separate bridge state database** that records version and sync state around each remote write.

See [Replica System](../Replica-System/page.md), [REST API](../REST-API/page.md), and
[Architecture](../Architecture/page.md) for details.
