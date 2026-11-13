"""
LangGraph State Schemas for AgenticOps Incident Response.

Defines the shared state dictionary passed across all nodes in the cyclic graph,
including execution steps, collected telemetry, tool calls, and human approval flags.
"""

from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict
import operator


class AgentStep(TypedDict):
    node: str
    action: str
    status: str  # in_progress | completed | failed | waiting_approval
    details: Dict[str, Any]
    timestamp: str


class IncidentState(TypedDict):
    # Incident context
    incident_id: str
    service: str
    description: str
    severity: str  # low | medium | high | critical

    # Investigation & Planning
    plan_steps: List[str]
    root_cause_hypothesis: Optional[str]

    # MCP Tooling & Telemetry
    tool_calls_requested: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    telemetry_snapshot: Dict[str, Any]

    # Human-in-the-Loop (HITL) Gate
    requires_human_approval: bool
    approval_granted: Optional[bool]
    approval_reason: Optional[str]
    pending_action: Optional[Dict[str, Any]]

    # Final Synthesis
    remediation_status: str  # pending | executed | blocked | dry_run
    final_summary: Optional[str]
    audit_log: Annotated[List[AgentStep], operator.add]
