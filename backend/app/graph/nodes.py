"""
LangGraph Nodes for Autonomous Incident Response.

Each node represents an agent phase in the cyclic graph:
1. planner_node: Analyzes the incident and decides investigation strategy.
2. investigator_node: Formulates MCP tool calls to fetch metrics & runbooks.
3. mcp_tool_node: Executes MCP tools via the MCP Server.
4. hitl_gate_node: Checks if any planned remediation requires Human-in-the-Loop approval.
5. synthesizer_node: Compiles root cause, telemetry findings, and audit log.
"""

import time
from typing import Dict, Any, List
from app.graph.state import IncidentState, AgentStep
from app.mcp.server import mcp_server


def _now() -> str:
    return time.strftime("%H:%M:%S")


def planner_node(state: IncidentState) -> Dict[str, Any]:
    """Analyzes the incoming incident, sets severity, and creates an action plan."""
    service = state.get("service", "unknown-service")
    desc = state.get("description", "")
    
    # Severity classification heuristic
    severity = "medium"
    if any(k in desc.lower() for k in ["outage", "critical", "500", "crash", "high latency", "oom"]):
        severity = "high"
    if any(k in desc.lower() for k in ["dead-letter", "p99 > 1000ms", "down"]):
        severity = "critical"

    plan = [
        f"Query real-time health and metrics for '{service}' via MCP.",
        f"Search internal SRE runbooks matching '{service}' failure modes.",
        "Synthesize telemetry and formulate remediation recommendation.",
        "Enforce Human-in-the-Loop approval before applying production mutations."
    ]

    step: AgentStep = {
        "node": "planner",
        "action": "Incident Triage & Investigation Planning",
        "status": "completed",
        "details": {
            "service": service,
            "calculated_severity": severity,
            "steps_count": len(plan)
        },
        "timestamp": _now()
    }

    return {
        "severity": severity,
        "plan_steps": plan,
        "audit_log": [step]
    }


def investigator_node(state: IncidentState) -> Dict[str, Any]:
    """Determines which MCP tools need to be called based on service and severity."""
    service = state.get("service", "auth-api")
    
    # Formulate tool calls with strict Pydantic parameters
    tools_to_call = [
        {
            "name": "check_service_health",
            "arguments": {"service": service}
        },
        {
            "name": "query_incident_metrics",
            "arguments": {"service": service, "window_hours": 6}
        },
        {
            "name": "search_runbooks",
            "arguments": {"query": "latency rollback restart", "service": service}
        }
    ]

    step: AgentStep = {
        "node": "investigator",
        "action": "MCP Tool Call Dispatch Formulation",
        "status": "completed",
        "details": {
            "dispatched_tools": [t["name"] for t in tools_to_call]
        },
        "timestamp": _now()
    }

    return {
        "tool_calls_requested": tools_to_call,
        "audit_log": [step]
    }


def mcp_tool_node(state: IncidentState) -> Dict[str, Any]:
    """Executes the requested tool calls against the registered MCP Server."""
    calls = state.get("tool_calls_requested", [])
    results: List[Dict[str, Any]] = []
    telemetry: Dict[str, Any] = {}

    for call in calls:
        tool_name = call["name"]
        args = call["arguments"]
        try:
            res = mcp_server.call_tool(tool_name, args)
            results.append(res)
            if tool_name == "query_incident_metrics":
                telemetry = res.get("output", {})
        except Exception as e:
            results.append({
                "tool": tool_name,
                "error": str(e),
                "requires_approval": False
            })

    # Derive root-cause hypothesis from telemetry
    p99 = telemetry.get("p99_latency_ms", 0)
    err = telemetry.get("error_rate_pct", 0)
    cpu = telemetry.get("cpu_pct", 0)

    hypothesis = (
        f"Service '{state.get('service')}' is exhibiting P99 latency of {p99}ms "
        f"(CPU {cpu}%, error rate {err}%). Runbook recommends scaling replicas or pod restart."
    )

    # Prepare recommended remediation
    pending_remediation = {
        "service": state.get("service"),
        "action": "restart_pods" if err > 5 else "scale_replicas",
        "dry_run": False
    }

    step: AgentStep = {
        "node": "mcp_tool_executor",
        "action": f"Executed {len(results)} MCP Tool Invocations",
        "status": "completed",
        "details": {
            "tools_executed": [r.get("tool") for r in results],
            "p99_latency": f"{p99}ms",
            "error_rate": f"{err}%"
        },
        "timestamp": _now()
    }

    return {
        "tool_results": results,
        "telemetry_snapshot": telemetry,
        "root_cause_hypothesis": hypothesis,
        "pending_action": pending_remediation,
        "audit_log": [step]
    }


def hitl_gate_node(state: IncidentState) -> Dict[str, Any]:
    """
    Human-in-the-Loop (HITL) Safety Gate.
    Determines whether the pending remediation is high-risk and requires human approval.
    """
    pending = state.get("pending_action") or {}
    action = pending.get("action", "")
    dry_run = pending.get("dry_run", False)

    # Destructive actions require explicit human operator confirmation
    high_risk_actions = {"restart_pods", "scale_replicas", "rollback_release", "flush_cache"}
    needs_approval = (action in high_risk_actions) and not dry_run

    granted = state.get("approval_granted")

    if needs_approval and granted is None:
        status = "waiting_approval"
        step_action = f"Blocked: Awaiting Human Operator Approval for '{action}' on '{pending.get('service')}'"
    elif granted is True:
        status = "completed"
        step_action = f"Human Approval GRANTED: Proceeding to execute '{action}'."
    elif granted is False:
        status = "completed"
        step_action = f"Human Approval REJECTED: Remediating via non-destructive dry-run only."
    else:
        status = "completed"
        step_action = "Action considered safe; no human gating required."

    step: AgentStep = {
        "node": "hitl_gate",
        "action": step_action,
        "status": status,
        "details": {
            "action": action,
            "requires_human_approval": needs_approval,
            "approval_granted": granted
        },
        "timestamp": _now()
    }

    return {
        "requires_human_approval": needs_approval,
        "audit_log": [step]
    }


def synthesizer_node(state: IncidentState) -> Dict[str, Any]:
    """Compiles the final incident post-mortem report and executes remediation if approved."""
    pending = state.get("pending_action") or {}
    granted = state.get("approval_granted")
    service = state.get("service")
    action = pending.get("action", "none")

    if granted is True:
        # Execute approved mutation via MCP
        remediation_res = mcp_server.call_tool("execute_remediation_action", {
            "service": service,
            "action": action,
            "dry_run": False
        })
        remediation_status = "executed"
        outcome = remediation_res.get("output", {}).get("result", "Action applied successfully.")
    elif granted is False:
        remediation_res = mcp_server.call_tool("execute_remediation_action", {
            "service": service,
            "action": action,
            "dry_run": True
        })
        remediation_status = "dry_run"
        outcome = "Human operator rejected mutation. Fallback dry-run completed."
    else:
        remediation_status = "pending"
        outcome = "Awaiting human operator decision."

    summary = (
        f"### Incident Post-Mortem & Resolution Report\n\n"
        f"**Service:** `{service}` | **Severity:** `{state.get('severity', 'medium').upper()}`\n\n"
        f"**Root Cause:** {state.get('root_cause_hypothesis', 'Unknown')}\n\n"
        f"**MCP Tool Execution:** Checked runbooks, retrieved live metrics (P99: {state.get('telemetry_snapshot', {}).get('p99_latency_ms', 'N/A')}ms).\n\n"
        f"**Remediation Outcome:** {outcome}\n\n"
        f"**Audit Status:** `{remediation_status.upper()}`"
    )

    step: AgentStep = {
        "node": "synthesizer",
        "action": "Final Synthesis & Post-Mortem Generation",
        "status": "completed",
        "details": {
            "remediation_status": remediation_status,
            "outcome": outcome
        },
        "timestamp": _now()
    }

    return {
        "remediation_status": remediation_status,
        "final_summary": summary,
        "audit_log": [step]
    }

