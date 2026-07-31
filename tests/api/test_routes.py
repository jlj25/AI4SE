"""API 路由单测：验证 REST 端点与 WebSocket。"""

from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.routes import set_pending_gate
from src.governance.hitl import HITLGate, HITLState


def test_health_check():
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_approve_no_pending():
    app = create_app()
    client = TestClient(app)
    response = client.post("/api/approve", json={"verdict": "approve"})
    assert response.status_code == 200
    assert response.json()["status"] == "no_pending_action"


def test_approve_with_pending_gate():
    """设置 pending gate 后审批。"""
    app = create_app()
    client = TestClient(app)
    gate = HITLGate()
    gate._state = HITLState.PENDING_APPROVAL  # noqa: SLF001
    gate._pending_action = None  # noqa: SLF001
    set_pending_gate(gate)
    try:
        response = client.post("/api/approve", json={"verdict": "approve"})
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert gate.state == HITLState.APPROVED
    finally:
        set_pending_gate(None)


def test_deny_with_pending_gate():
    app = create_app()
    client = TestClient(app)
    gate = HITLGate()
    gate._state = HITLState.PENDING_APPROVAL  # noqa: SLF001
    gate._pending_action = None  # noqa: SLF001
    set_pending_gate(gate)
    try:
        response = client.post("/api/approve", json={"verdict": "deny"})
        assert response.status_code == 200
        assert gate.state == HITLState.DENIED
    finally:
        set_pending_gate(None)


def test_modify_with_pending_gate():
    app = create_app()
    client = TestClient(app)
    gate = HITLGate()
    gate._state = HITLState.PENDING_APPROVAL  # noqa: SLF001
    gate._pending_action = None  # noqa: SLF001
    set_pending_gate(gate)
    try:
        response = client.post(
            "/api/approve",
            json={
                "verdict": "modify",
                "modified_action": {
                    "tool": "run_shell",
                    "args": {"command": "echo safe"},
                    "thought": "",
                },
            },
        )
        assert response.status_code == 200
        assert gate.state == HITLState.MODIFIED
    finally:
        set_pending_gate(None)


def test_websocket_run():
    """WebSocket run 消息。"""
    app = create_app()
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_text('{"type": "run"}')
        msg = ws.receive_json()
        assert msg["type"] == "status"
        assert "agent" in msg["message"]
