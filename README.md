# DOCMOST AI EXTENSION
___
Docmost AI Extension is a self-hosted AI integration layer for Docmost.
It enables structured, environment-driven AI interaction with selected
Docmost pages without modifying the Docmost core system.

The system is designed for deterministic backend orchestration,
strict database separation, and full Docker-based deployment.
___
## PLACEHOLDERS (EDIT THESE BEFORE DISTRIBUTION)

```
REPOSITORY
<REPO_URL>
<PROJECT_DIRECTORY>

CONTAINER PORTS
<DOCMOST_FETCHER_PORT>
<AI_BACKEND_PORT>
<POSTGRES_DOCMOST_PORT>
<POSTGRES_AI_PORT>
<REDIS_PORT>
<OLLAMA_PORT>

DOCMOST DATABASE
<DOCMOST_DB_HOST>
<DOCMOST_DB_PORT>
<DOCMOST_DB_NAME>
<DOCMOST_DB_USER>
<DOCMOST_DB_PASSWORD>

AI DATABASE
<AI_DB_HOST>
<AI_DB_PORT>
<AI_DB_NAME>
<AI_DB_USER>
<AI_DB_PASSWORD>

LLM RUNTIME
<OLLAMA_HOST>
<OLLAMA_PORT>
```
___
## PROJECT OVERVIEW


The extension allows a user to:

- Select one or multiple Docmost pages
- Provide an instruction or message
- Send both to a backend job system
- Fetch page content directly from the Docmost database
- Construct a structured prompt
- Call a locally hosted LLM (for example via Ollama)
- Store AI results in a dedicated AI database
- Stream job status and final output back to the UI

The project avoids SaaS dependencies and is intended for
self-hosted deployments.
___
## ARCHITECTURE

***The system consists of separate services***:

1. Docmost Fetcher
   - Read-only proxy
   - Connects to Docmost PostgreSQL
   - Fetches spaces, pages and page content

2. AI Backend
   - Handles job creation
   - Coordinates page retrieval
   - Calls the LLM runtime
   - Stores results

3. LLM Runtime
   - Executes model inference
   - Typically Ollama or other self-hosted runtime

4. AI Database
   - Stores job metadata
   - Stores AI responses
   - Fully separated from Docmost DB

5. Optional Redis
   - Used for background job processing

___
## WORKFLOW


1. UI sends:
   - space_id
   - selected_page_ids[]
   - user message

2. AI Backend:
   - Creates job entry
   - Calls Docmost Fetcher
   - Retrieves selected page content

3. Worker:
   - Builds structured prompt
   - Sends prompt to LLM runtime
   - Receives response

4. Result:
   - Stored in AI database
   - Delivered back to UI (SSE or polling)
___
## DESIGN PRINCIPLES

• No hardcoded runtime configuration
• All configuration from environment variables
• Strict read-only access to Docmost DB
• Separate AI storage database
• Deterministic execution flow
• Explicit UUID handling
• Docker-first deployment model
___
## INSTALLATION

Clone repository:
```bash
    git clone <REPO_URL>
    cd <PROJECT_DIRECTORY>
```
Configure environment:
```bash
    cp .env.example .env
    # edit placeholders listed above
```
Start containers:
```bash
    docker compose up --build -d
```
___
## EXPOSED SERVICES

Docmost Fetcher        -> <DOCMOST_FETCHER_PORT>
AI Backend API         -> <AI_BACKEND_PORT>
Docmost PostgreSQL     -> <POSTGRES_DOCMOST_PORT>
AI PostgreSQL          -> <POSTGRES_AI_PORT>
Redis (optional)       -> <REDIS_PORT>
LLM Runtime            -> <OLLAMA_PORT>

___
## SECURITY MODEL

• Docmost database is read-only from this extension
• AI database is isolated
• LLM runtime is internal network only
• No direct modification of Docmost content
• All inter-service communication happens over Docker network

___
## FUTURE EXTENSIONS

- Streaming token responses
- AI-generated diffs against pages
- Embedding-based semantic search
- Scalable background workers
- Permission-aware AI filtering

___
## LICENSE


Specify your license here.

# ============================================================
