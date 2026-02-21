# ============================================================
# DOCMOST AI EXTENSION
# ============================================================
#
# An environment-driven AI assistant extension for Docmost.
# Designed for deterministic backend execution, strict DB separation,
# and self-hosted LLM integration (no SaaS dependency required).
#
# ============================================================
# PLACEHOLDERS (EDIT IN ONE PLACE BEFORE DISTRIBUTION)
# ============================================================
#
# <REPO_URL>
# <PROJECT_DIRECTORY>
#
# <DOCMOST_FETCHER_PORT>
# <AI_BACKEND_PORT>
# <POSTGRES_DOCMOST_PORT>
# <POSTGRES_AI_PORT>
# <REDIS_PORT>
#
# <DOCMOST_DB_HOST>
# <DOCMOST_DB_PORT>
# <DOCMOST_DB_NAME>
# <DOCMOST_DB_USER>
# <DOCMOST_DB_PASSWORD>
#
# <AI_DB_HOST>
# <AI_DB_PORT>
# <AI_DB_NAME>
# <AI_DB_USER>
# <AI_DB_PASSWORD>
#
# <OLLAMA_HOST>
# <OLLAMA_PORT>
#
# ============================================================
# OVERVIEW
# ============================================================
#
# Docmost AI Extension is a self-hosted backend system that integrates
# AI-assisted content analysis and transformation into Docmost.
#
# The extension allows users to:
#
# - Select one or multiple Docmost pages
# - Provide a message or instruction
# - Send both to a backend worker
# - Have the worker fetch page content directly from the Docmost database
# - Construct a structured prompt
# - Call a locally hosted LLM (e.g. Ollama)
# - Store the result in a dedicated AI database
# - Stream job status and final output back to the UI
#
# This project is intentionally:
#
# - Environment-driven (no hardcoded runtime values)
# - Deterministic in workflow
# - Strictly separated between read and write databases
# - Designed for Docker-based self-hosting
#
# ============================================================
# ARCHITECTURE
# ============================================================
#
# The system consists of multiple services:
#
# 1. Docmost Fetcher
#    - Read-only proxy service
#    - Connects to Docmost PostgreSQL database
#    - Fetches spaces, pages, and page content
#
# 2. AI Backend
#    - Orchestrates AI job creation and execution
#    - Stores job metadata and results
#    - Communicates with LLM runtime
#
# 3. LLM Runtime (e.g. Ollama)
#    - Executes model inference
#    - Self-hosted
#
# 4. AI Database
#    - Stores AI job requests
#    - Stores AI results
#    - Completely separate from Docmost DB
#
# 5. (Optional) Redis
#    - Used for background workers / job queues (if enabled)
#
# ============================================================
# WORKFLOW
# ============================================================
#
# 1. UI sends:
#       - space_id
#       - selected_page_ids[]
#       - user message
#
# 2. AI Backend:
#       - Creates job entry
#       - Calls Docmost Fetcher
#       - Retrieves page content
#
# 3. Worker:
#       - Builds prompt
#       - Calls LLM runtime
#       - Receives model response
#
# 4. Result:
#       - Stored in AI database
#       - UI receives updates via SSE
#
# ============================================================
# DESIGN PRINCIPLES
# ============================================================
#
# - No hardcoded configuration
# - All values from environment variables
# - Strict DB separation (Docmost = read-only)
# - Explicit UUID handling
# - Deterministic execution path
# - Clear error propagation
#
# ============================================================
# INSTALLATION
# ============================================================
#
# Clone repository:
#
#     git clone <REPO_URL>
#     cd <PROJECT_DIRECTORY>
#
# Configure environment:
#
#     cp .env.example .env
#     # edit placeholders
#
# Start services:
#
#     docker compose up --build -d
#
# ============================================================
# EXPOSED PORTS
# ============================================================
#
# Docmost Fetcher:        <DOCMOST_FETCHER_PORT>
# AI Backend API:         <AI_BACKEND_PORT>
# Docmost PostgreSQL:     <POSTGRES_DOCMOST_PORT>
# AI PostgreSQL:          <POSTGRES_AI_PORT>
# Redis (optional):       <REDIS_PORT>
# Ollama Runtime:         <OLLAMA_PORT>
#
# ============================================================
# ENVIRONMENT VARIABLES (SUMMARY)
# ============================================================
#
# DOCMOST_DB_HOST=<DOCMOST_DB_HOST>
# DOCMOST_DB_PORT=<DOCMOST_DB_PORT>
# DOCMOST_DB_NAME=<DOCMOST_DB_NAME>
# DOCMOST_DB_USER=<DOCMOST_DB_USER>
# DOCMOST_DB_PASSWORD=<DOCMOST_DB_PASSWORD>
#
# AI_DB_HOST=<AI_DB_HOST>
# AI_DB_PORT=<AI_DB_PORT>
# AI_DB_NAME=<AI_DB_NAME>
# AI_DB_USER=<AI_DB_USER>
# AI_DB_PASSWORD=<AI_DB_PASSWORD>
#
# OLLAMA_HOST=<OLLAMA_HOST>
# OLLAMA_PORT=<OLLAMA_PORT>
#
# ============================================================
# SECURITY MODEL
# ============================================================
#
# - Docmost DB is never written to.
# - AI DB is isolated from Docmost.
# - LLM runtime is internal network only.
# - All external access controlled via Docker networking.
#
# ============================================================
# FUTURE EXTENSIONS
# ============================================================
#
# - Streaming partial token responses
# - Page-level diff generation
# - AI-assisted content rewriting
# - Semantic search via embeddings
# - Background job queue scaling
#
# ============================================================
# LICENSE
# ============================================================
#
# (Specify your license here)
#
# ============================================================
