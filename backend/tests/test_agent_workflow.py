import pytest
from app.graph.workflow import incident_graph


def test_agent_graph_execution_hitl_pause():
    initial_state = {
        "incident_id": "test-inc-1",
        "service": "auth-api",
        "description": "500 errors and high P99 latency in auth-api",
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

    config = {"configurable": {"thread_id": "test-thread-1"}}
    res = incident_graph.invoke(initial_state, config=config)

    # High-risk action should have triggered human approval pause
    assert res["requires_human_approval"] is True
    assert res["approval_granted"] is None
    assert len(res["audit_log"]) >= 4
    assert res["pending_action"] is not None


def test_agent_graph_resume_with_approval():
    initial_state = {
        "incident_id": "test-inc-2",
        "service": "auth-api",
        "description": "Critical outage in auth-api",
        "severity": "high",
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

    config = {"configurable": {"thread_id": "test-thread-2"}}
    state_paused = incident_graph.invoke(initial_state, config=config)

    # Simulate human operator granting approval
    state_paused["approval_granted"] = True
    state_paused["approval_reason"] = "Approved by on-call engineer."

    resumed = incident_graph.invoke(state_paused, config=config)

    assert resumed["remediation_status"] == "executed"
    assert resumed["final_summary"] is not None
    assert "Incident Post-Mortem" in resumed["final_summary"]
