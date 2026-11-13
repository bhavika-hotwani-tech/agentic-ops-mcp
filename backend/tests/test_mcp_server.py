import pytest
from app.mcp.server import mcp_server


def test_list_tools():
    tools = mcp_server.list_tools()
    assert len(tools) >= 4
    tool_names = [t["name"] for t in tools]
    assert "search_runbooks" in tool_names
    assert "query_incident_metrics" in tool_names
    assert "check_service_health" in tool_names
    assert "execute_remediation_action" in tool_names


def test_list_resources():
    resources = mcp_server.list_resources()
    assert len(resources) >= 3
    uris = [r["uri"] for r in resources]
    assert "runbook://auth-api" in uris


def test_call_tool_check_health():
    res = mcp_server.call_tool("check_service_health", {"service": "auth-api"})
    assert res["tool"] == "check_service_health"
    assert "status" in res["output"]


def test_call_tool_metrics():
    res = mcp_server.call_tool("query_incident_metrics", {"service": "auth-api", "window_hours": 12})
    assert res["tool"] == "query_incident_metrics"
    assert res["output"]["p99_latency_ms"] > 0


def test_mcp_jsonrpc_tools_list():
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    resp = mcp_server.handle_jsonrpc(payload)
    assert resp["jsonrpc"] == "2.0"
    assert "result" in resp
    assert len(resp["result"]["tools"]) >= 4


def test_mcp_jsonrpc_tools_call():
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "search_runbooks",
            "arguments": {"query": "latency", "service": "auth-api"}
        }
    }
    resp = mcp_server.handle_jsonrpc(payload)
    assert resp["id"] == 2
    assert "result" in resp
    assert resp["result"]["output"]["count"] > 0
