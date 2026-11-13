import pytest


def test_health_endpoint(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"
    assert res.json()["langgraph_active"] is True


def test_mcp_tools_list_endpoint(client):
    res = client.get("/api/v1/mcp/tools")
    assert res.status_code == 200
    tools = res.json()
    assert len(tools) >= 4


def test_agent_run_and_approval_flow(client):
    # 1. Trigger agent run
    run_res = client.post("/api/v1/agent/run", json={
        "service": "auth-api",
        "description": "Token verification latency exceeded 800ms"
    })
    assert run_res.status_code == 200
    run_data = run_res.json()
    run_id = run_data["run_id"]
    assert run_data["status"] == "waiting_approval"
    assert run_data["requires_human_approval"] is True

    # 2. Inspect run status
    get_res = client.get(f"/api/v1/agent/runs/{run_id}")
    assert get_res.status_code == 200
    assert get_res.json()["run_id"] == run_id

    # 3. Submit human approval
    approve_res = client.post(f"/api/v1/agent/runs/{run_id}/approve", json={
        "approved": True,
        "reason": "Approved by senior devops"
    })
    assert approve_res.status_code == 200
    approved_data = approve_res.json()
    assert approved_data["status"] == "completed"
    assert approved_data["remediation_status"] == "executed"
    assert approved_data["final_summary"] is not None


def test_agent_run_rejection_flow(client):
    run_res = client.post("/api/v1/agent/run", json={
        "service": "billing-worker",
        "description": "Webhook dead-letter queue spike"
    })
    run_id = run_res.json()["run_id"]

    # Reject mutation
    reject_res = client.post(f"/api/v1/agent/runs/{run_id}/approve", json={
        "approved": False,
        "reason": "Risk of payment data inconsistency; dry-run only."
    })
    assert reject_res.status_code == 200
    assert reject_res.json()["remediation_status"] == "dry_run"
