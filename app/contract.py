"""Server <-> helper contract version surface.

The helper performs a startup handshake against `/v1/contract` to detect
helper/server contract skew. Bump CONTRACT_VERSION on any breaking change to the
`/v1` (helper-facing) request/response contract.
"""

from __future__ import annotations

from fastapi import APIRouter

CONTRACT_VERSION = "1"

router = APIRouter(prefix="/v1", tags=["contract"])


@router.get("/contract", summary="Helper <-> server contract version")
def contract() -> dict:
    return {
        "contract_version": CONTRACT_VERSION,
        "surface": "docmost-helper-bridge",
        "capabilities": [
            "reads",
            "writes",
            "move",
            "snapshots",
            "auto-mcp-apply",
            "auto-mcp-observe",
        ],
    }


@router.get("/health", summary="v1 process health")
def health() -> dict:
    return {"ok": True}
