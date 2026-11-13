"""
LangGraph Cyclic Workflow Definition for AgenticOps.

Constructs the stateful LangGraph with:
1. Entry -> Planner Node
2. Planner -> Investigator Node
3. Investigator -> MCP Tool Executor Node
4. MCP Tool Executor -> HITL Gate Node
5. Conditional Edge:
   - If requires human approval and approval_granted is None -> PAUSE / INTERRUPT (wait_for_human)
   - Otherwise -> Synthesizer Node
6. Synthesizer -> END
"""

from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.graph.state import IncidentState
from app.graph.nodes import (
    planner_node,
    investigator_node,
    mcp_tool_node,
    hitl_gate_node,
    synthesizer_node
)


def should_pause_for_human(state: IncidentState) -> Literal["synthesizer", "wait_for_human"]:
    """Conditional router: evaluates whether HITL interrupts execution."""
    needs_approval = state.get("requires_human_approval", False)
    approval_granted = state.get("approval_granted")

    # If destructive action needs approval and operator hasn't decided yet
    if needs_approval and approval_granted is None:
        return "wait_for_human"
    return "synthesizer"


def build_incident_graph():
    """Builds and compiles the stateful LangGraph with an in-memory checkpointer."""
    workflow = StateGraph(IncidentState)

    # Register Nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("investigator", investigator_node)
    workflow.add_node("mcp_tools", mcp_tool_node)
    workflow.add_node("hitl_gate", hitl_gate_node)
    workflow.add_node("synthesizer", synthesizer_node)

    # Define Fixed Edges
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "investigator")
    workflow.add_edge("investigator", "mcp_tools")
    workflow.add_edge("mcp_tools", "hitl_gate")

    # Conditional Edge from HITL gate
    # Note: When paused for human, the state is persisted in checkpointer.
    # On resumption with approval_granted, it continues to synthesizer.
    workflow.add_conditional_edges(
        "hitl_gate",
        should_pause_for_human,
        {
            "synthesizer": "synthesizer",
            "wait_for_human": END  # Returns state to caller with waiting_approval flag
        }
    )
    workflow.add_edge("synthesizer", END)

    # Compile with checkpoint memory to support state persistence & resumption
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    return app


incident_graph = build_incident_graph()
