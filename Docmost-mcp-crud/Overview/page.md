# Overview

**Docmost MCP** is a bridge service that gives MCP-compatible AI clients read and write access to documentation in a running Docmost instance, without modifying Docmost itself.

It exposes two surfaces:

- A **remote MCP endpoint** for MCP-compatible clients
- A **REST API** for conventional HTTP access, including a local-first replica sync workflow

## Purpose

The service lets MCP-consuming models maintain Docmost documentation programmatically - reading, creating, and updating pages - against a privately self-hosted Docmost instance. It is designed to run as a container on the same server and Docker network as the live Docmost stack, while being reachable from a separate machine running an MCP client.

## Relationship to Docmost

Docmost is separate upstream software that this service does not own or modify. The bridge integrates with Docmost from the outside:

- It **reads** Docmost content directly from the Docmost PostgreSQL database (read-only).
- It **writes** by calling Docmost's own REST write API.
- It keeps its own **separate bridge PostgreSQL database** for version and sync state, distinct from Docmost's database.

Because writes ride on Docmost's REST page pipeline, the bridge requires **Docmost v0.71.1 or later** (see [Deployment](../Deployment/page.md) for the exact reason).

## Key characteristics

- **Read and write** - reads cover spaces, pages, and the page tree; writes cover create, update, and delete for spaces and pages
- **Two transports** - the same core operations are available over the MCP endpoint and over REST
- **Local-first sync** - a replica/sync workflow (status, diff, pull, push) lets a client maintain a local editable copy of remote docs and reconcile changes safely
- **Bridge-owned writes** - page writes are recorded in the bridge database around each remote Docmost write
- **Space-scoped** - pages are always queried within a space; there is no global page lookup
- **Markdown in, markdown out** - page content is accepted and returned as markdown
- **Explicit not-found errors** - if data does not exist the service returns a clear error; it never invents structure

## Tech stack

| Component | Technology |
|---|---|
| Web framework | FastAPI |
| MCP layer | `mcp` library (`FastMCP`) |
| Databases | PostgreSQL via `psycopg2` (Docmost read DB + bridge state DB) |
| Models | Pydantic v2 |
| Runtime | Python 3.12 |
| Deployment | Docker / Docker Compose |

## Entry point

`app/main.py` - creates the FastAPI app, registers all routers, mounts the MCP sub-app, and manages the MCP session lifespan.
