"""
Model Context Protocol (MCP) Tool & Resource Server.

Implements MCP JSON-RPC 2.0 primitives (`tools/list`, `tools/call`,
`resources/list`, `resources/read`) with strict Pydantic input schemas
so any LangGraph agent or external MCP client can discover and invoke tools.
"""

from typing import Any, Callable, Dict, List, Optional, Type
from pydantic import BaseModel, Field


class SearchRunbooksInput(BaseModel):
    query: str = Field(..., description="Keywords describing the incident or issue.")
    service: str = Field("all", description="Target microservice name, e.g., auth-api, billing-worker.")


class QueryMetricsInput(BaseModel):
    service: str = Field(..., description="Service identifier to inspect.")
    window_hours: int = Field(6, ge=1, le=72, description="Lookback window in hours.")


class CheckServiceHealthInput(BaseModel):
    service: str = Field(..., description="Service name to probe.")


class ExecuteRemediationInput(BaseModel):
    service: str = Field(..., description="Service to remediate.")
    action: str = Field(..., description="Action: restart_pods | scale_replicas | flush_cache | rollback_release")
    dry_run: bool = Field(False, description="If true, only simulate without mutating state.")


# Simulated enterprise knowledge & telemetry backing the MCP tools
RUNBOOKS = {
    "auth-api": {
        "title": "Auth API Latency & Token Store Runbook",
        "steps": [
            "Check Redis connection pool saturation and JWT signing key cache.",
            "If P99 > 500ms, scale auth-api replicas from 3 to 6 or flush stale session keys.",
            "Verify upstream OAuth provider rate limits before restarting pods.",
        ],
    },
    "billing-worker": {
        "title": "Billing Worker Dead-Letter Queue Runbook",
        "steps": [
            "Inspect Stripe webhook retry backlog and DB lock contention.",
            "Rollback recent worker release if error rate exceeds 5% after deployment.",
        ],
    },
    "rag-indexer": {
        "title": "RAG Vector Indexer OOM & Ingestion Runbook",
        "steps": [
            "Check embedding batch size and pgvector HNSW memory usage.",
            "Reduce chunk concurrency or restart worker pods with dry-run verification first.",
        ],
    },
}

SERVICE_METRICS = {
    "auth-api": {"p99_latency_ms": 842, "error_rate_pct": 4.8, "cpu_pct": 89, "status": "degraded"},
    "billing-worker": {"p99_latency_ms": 310, "error_rate_pct": 6.4, "cpu_pct": 72, "status": "critical"},
    "rag-indexer": {"p99_latency_ms": 190, "error_rate_pct": 0.4, "cpu_pct": 41, "status": "healthy"},
}


class MCPToolDefinition(BaseModel):
    name: str
    description: str
    requires_approval: bool = False
    input_schema: Dict[str, Any]


class MCPServer:
    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._register_default_tools()

    def register_tool(
        self,
        name: str,
        description: str,
        schema_cls: Type[BaseModel],
        handler: Callable[[BaseModel], Dict[str, Any]],
        requires_approval: bool = False,
    ):
        self._tools[name] = {
            "definition": MCPToolDefinition(
                name=name,
                description=description,
                requires_approval=requires_approval,
                input_schema=schema_cls.model_json_schema(),
            ),
            "schema_cls": schema_cls,
            "handler": handler,
        }

    def _register_default_tools(self):
        self.register_tool(
            name="search_runbooks",
            description="Search internal SRE runbooks for remediation playbooks.",
            schema_cls=SearchRunbooksInput,
            handler=self._handle_search_runbooks,
        )
        self.register_tool(
            name="query_incident_metrics",
            description="Fetch live P99 latency, CPU, and error rate telemetry for a service.",
            schema_cls=QueryMetricsInput,
            handler=self._handle_query_metrics,
        )
        self.register_tool(
            name="check_service_health",
            description="Check current health status and active alerts for a microservice.",
            schema_cls=CheckServiceHealthInput,
            handler=self._handle_check_health,
        )
        self.register_tool(
            name="execute_remediation_action",
            description="Execute a production remediation action (requires human approval unless dry_run=True).",
            schema_cls=ExecuteRemediationInput,
            handler=self._handle_execute_remediation,
            requires_approval=True,
        )

    def _handle_search_runbooks(self, args: SearchRunbooksInput) -> Dict[str, Any]:
        matches = []
        for svc, rb in RUNBOOKS.items():
            if args.service in ("all", svc) or args.query.lower() in rb["title"].lower() or any(
                args.query.lower() in s.lower() for s in rb["steps"]
            ):
                matches.append({"service": svc, **rb})
        if not matches:
            matches = [{"service": k, **v} for k, v in RUNBOOKS.items()]
        return {"matches": matches, "count": len(matches)}

    def _handle_query_metrics(self, args: QueryMetricsInput) -> Dict[str, Any]:
        metrics = SERVICE_METRICS.get(
            args.service,
            {"p99_latency_ms": 145, "error_rate_pct": 0.2, "cpu_pct": 35, "status": "healthy"},
        )
        return {"service": args.service, "window_hours": args.window_hours, **metrics}

    def _handle_check_health(self, args: CheckServiceHealthInput) -> Dict[str, Any]:
        metrics = SERVICE_METRICS.get(args.service, {"status": "healthy", "error_rate_pct": 0.1})
        return {
            "service": args.service,
            "status": metrics["status"],
            "alert_active": metrics["status"] != "healthy",
        }

    def _handle_execute_remediation(self, args: ExecuteRemediationInput) -> Dict[str, Any]:
        mode = "DRY_RUN" if args.dry_run else "EXECUTED"
        return {
            "service": args.service,
            "action": args.action,
            "mode": mode,
            "result": f"{mode}: '{args.action}' applied to '{args.service}' cleanly.",
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        return [entry["definition"].model_dump() for entry in self._tools.values()]

    def list_resources(self) -> List[Dict[str, Any]]:
        return [
            {
                "uri": f"runbook://{svc}",
                "name": rb["title"],
                "mimeType": "application/json",
            }
            for svc, rb in RUNBOOKS.items()
        ]

    def read_resource(self, uri: str) -> Dict[str, Any]:
        svc = uri.replace("runbook://", "").strip()
        if svc not in RUNBOOKS:
            raise ValueError(f"Unknown MCP resource URI: {uri}")
        return {"uri": uri, "contents": RUNBOOKS[svc]}

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name not in self._tools:
            raise ValueError(f"Unknown MCP tool: {name}")
        entry = self._tools[name]
        validated = entry["schema_cls"](**arguments)
        output = entry["handler"](validated)
        return {
            "tool": name,
            "requires_approval": entry["definition"].requires_approval and not arguments.get("dry_run", False),
            "arguments": validated.model_dump(),
            "output": output,
        }

    def handle_jsonrpc(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        req_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params") or {}
        try:
            if method == "tools/list":
                result = {"tools": self.list_tools()}
            elif method == "tools/call":
                result = self.call_tool(params.get("name", ""), params.get("arguments", {}))
            elif method == "resources/list":
                result = {"resources": self.list_resources()}
            elif method == "resources/read":
                result = self.read_resource(params.get("uri", ""))
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": str(exc)},
            }


mcp_server = MCPServer()

