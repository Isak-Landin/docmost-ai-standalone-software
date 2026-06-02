from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from app.auto_mcp import routers as auto_mcp
from app.contract import router as contract_router
from app.helper_api import routers as helper_api
from app.mcp_server import mcp
from app.reconcile import routers as reconcile
from app.query.routers import health, pages, replica, spaces
from app.sync import routers as sync
from app.write.routers import pages as write_pages
from app.write.routers import spaces as write_spaces


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title="Docmost MCP",
    description=(
        "REST and MCP bridge for Docmost. "
        "Exposes Docmost reads, bridge-owned writes, sync routes, and helper automation routes."
    ),
    version="1.0.0",
    lifespan=app_lifespan,
)

app.include_router(health.router)
app.include_router(replica.router)
app.include_router(sync.router)
app.include_router(auto_mcp.router)
app.include_router(contract_router)
# Helper-facing CRUD contract: served under /v1 (canonical) and /helper/v1 (back-compat).
app.include_router(helper_api.router, prefix="/v1")
app.include_router(helper_api.router, prefix="/helper/v1")
# Reconcile brain + resolution endpoints: same /v1 (+ /helper/v1) surface.
app.include_router(reconcile.router, prefix="/v1")
app.include_router(reconcile.router, prefix="/helper/v1")
# Query (read) routes — backed by direct PostgreSQL access
app.include_router(spaces.router)
app.include_router(pages.router)
# Write routes — backed by Docmost REST API
app.include_router(write_spaces.router)
app.include_router(write_pages.router)
# FastMCP already exposes /mcp inside the sub-app, so mount it at root.
app.mount("/", mcp.streamable_http_app())


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("LISTEN_HOST", "0.0.0.0")
    port = int(os.getenv("LISTEN_PORT", "8099"))
    uvicorn.run("app.main:app", host=host, port=port, reload=False)
