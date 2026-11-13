"""
Model Context Protocol (MCP) JSON-RPC 2.0 Router.

Exposes standard MCP protocol endpoints:
- POST /api/v1/mcp (JSON-RPC 2.0 gateway)
- GET  /api/v1/mcp/tools (REST shortcut for UI)
- GET  /api/v1/mcp/resources (REST shortcut for UI)
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from app.mcp.server import mcp_server

router = APIRouter(prefix="/mcp", tags=["Model Context Protocol (MCP)"])


@router.post("")
async def handle_mcp_jsonrpc(payload: Dict[str, Any]):
    """Standard Model Context Protocol JSON-RPC 2.0 endpoint."""
    return mcp_server.handle_jsonrpc(payload)


@router.get("/tools")
async def list_mcp_tools() -> List[Dict[str, Any]]:
    """Lists all registered MCP tools with their Pydantic JSON schemas."""
    return mcp_server.list_tools()


@router.get("/resources")
async def list_mcp_resources() -> List[Dict[str, Any]]:
    """Lists discoverable MCP enterprise resources (runbooks, documentation)."""
    return mcp_server.list_resources()

