"""
LangGraph Agent Execution & Human-in-the-Loop Router.

Endpoints:
- POST /api/v1/agent/run : Trigger autonomous agentic workflow.
- GET  /api/v1/agent/runs/{run_id} : Inspect graph execution state and checkpointer.
- POST /api/v1/agent/runs/{run_id}/approve : Resume graph with human operator approval / rejection.
- POST /api/v1/agent/stream : Server-Sent Events (SSE) stream of node transitions.
"""

import uuid
import json
import asyncio
from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from app.graph.workflow import incident_graph

router = APIRouter(prefix="/agent", tags=["Agentic Workflow & Human-in-the-Loop"])

# In-memory store of recent run states
RUNS_STORE: Dict[str, Dict[str, Any]] = {}


class RunIncidentRequest(BaseModel):
    service: str = Field("auth-api", description="Target microservice name")
    description: str = Field(
        "P99 latency spiked to 842ms, JWT validation failure rate 4.8%",
        description="Incident description or alert payload"
    )


class ApprovalRequest(BaseModel):
    approved: bool = Field(..., description="True to execute production action, False to trigger dry-run.")
    reason: Optional[str] = Field("Approved by SRE on-call lead.", description="Operator rationale.")


@router.post("/run")
async def run_agentic_workflow(payload: RunIncidentRequest):
    """
    Executes the LangGraph incident response cycle.
    If high-risk remediation is needed, graph pauses at HITL gate with status='waiting_approval'.
    """
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    initial_state = {
        "incident_id": run_id,
        "service": payload.service,
        "description": payload.description,
        "severity": "medium",
        "plan_steps": [],
        "root_cause_hypothesis": None,
        "tool_calls_requested": [],
        "tool_results": [],
        "telemetry_snapshot": {},
        "requires_human_approval": False,
        "approval_granted": None,
        "approval_reason": None,
        "pending_action": None,
        "remediation_status": "pending",
        "final_summary": None,
        "audit_log": []
    }

    config = {"configurable": {"thread_id": run_id}}
    result_state = incident_graph.invoke(initial_state, config=config)

    # Determine execution status
    needs_approval = result_state.get("requires_human_approval", False)
    approval_granted = result_state.get("approval_granted")
    
    if needs_approval and approval_granted is None:
        status = "waiting_approval"
    else:
        status = "completed"

    response_payload = {
        "run_id": run_id,
        "status": status,
        "service": result_state["service"],
        "severity": result_state["severity"],
        "requires_human_approval": needs_approval,
        "pending_action": result_state.get("pending_action"),
        "plan_steps": result_state.get("plan_steps", []),
        "root_cause_hypothesis": result_state.get("root_cause_hypothesis"),
        "tool_results_count": len(result_state.get("tool_results", [])),
        "remediation_status": result_state.get("remediation_status"),
        "final_summary": result_state.get("final_summary"),
        "audit_log": result_state.get("audit_log", [])
    }

    RUNS_STORE[run_id] = {
        "state": result_state,
        "payload": response_payload
    }
    return response_payload


@router.get("/runs/{run_id}")
async def get_run_status(run_id: str):
    """Retrieves current execution state and audit trail for a run."""
    if run_id not in RUNS_STORE:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return RUNS_STORE[run_id]["payload"]


@router.get("/runs")
async def list_recent_runs() -> List[Dict[str, Any]]:
    """Lists recent agent execution runs."""
    return [entry["payload"] for entry in reversed(list(RUNS_STORE.values()))]


@router.post("/runs/{run_id}/approve")
async def submit_human_approval(run_id: str, payload: ApprovalRequest):
    """
    Resumes LangGraph execution from the HITL Gate checkpointer.
    Transitions state to the Synthesizer node to execute or dry-run remediation.
    """
    if run_id not in RUNS_STORE:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")

    current = RUNS_STORE[run_id]["state"]
    current["approval_granted"] = payload.approved
    current["approval_reason"] = payload.reason

    config = {"configurable": {"thread_id": run_id}}
    resumed_state = incident_graph.invoke(current, config=config)

    response_payload = {
        "run_id": run_id,
        "status": "completed",
        "service": resumed_state["service"],
        "severity": resumed_state["severity"],
        "requires_human_approval": resumed_state.get("requires_human_approval"),
        "approval_granted": payload.approved,
        "approval_reason": payload.reason,
        "pending_action": resumed_state.get("pending_action"),
        "remediation_status": resumed_state.get("remediation_status"),
        "final_summary": resumed_state.get("final_summary"),
        "audit_log": resumed_state.get("audit_log", [])
    }

    RUNS_STORE[run_id] = {
        "state": resumed_state,
        "payload": response_payload
    }
    return response_payload


@router.post("/stream")
async def stream_agentic_workflow(payload: RunIncidentRequest):
    """Server-Sent Events (SSE) streaming of LangGraph state transitions."""
    async def event_generator():
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        initial_state = {
            "incident_id": run_id,
            "service": payload.service,
            "description": payload.description,
            "severity": "medium",
            "plan_steps": [],
            "root_cause_hypothesis": None,
            "tool_calls_requested": [],
            "tool_results": [],
            "telemetry_snapshot": {},
            "requires_human_approval": False,
            "approval_granted": None,
            "approval_reason": None,
            "pending_action": None,
            "remediation_status": "pending",
            "final_summary": None,
            "audit_log": []
        }

        config = {"configurable": {"thread_id": run_id}}

        # Stream node-by-node updates
        for output in incident_graph.stream(initial_state, config=config):
            for node_name, node_update in output.items():
                chunk = {
                    "run_id": run_id,
                    "node": node_name,
                    "update": node_update
                }
                yield f"data: {json.dumps(chunk, default=str)}\n\n"
                await asyncio.sleep(0.05)
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )
