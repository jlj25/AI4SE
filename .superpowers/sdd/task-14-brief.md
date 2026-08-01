## Task 14: API 层（FastAPI + WebSocket）

**Files:**
- Create: `src/api/__init__.py`, `src/api/main.py`, `src/api/routes.py`, `src/api/ws.py`
- Test: `tests/api/__init__.py`, `tests/api/test_routes.py`

**Interfaces:**
- Consumes: `AgentLoop`, `HITLGate`
- Produces: FastAPI app, REST `/api/health`, `/api/approve`, WebSocket `/ws`

- [ ] **Step 1: 写失败测试**

```python
# tests/api/__init__.py
```

```python
# tests/api/test_routes.py
"""API 路由单测：验证 REST 端点。"""
from fastapi.testclient import TestClient
from src.api.main import create_app


def test_health_check():
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_approve_endpoint():
    app = create_app()
    client = TestClient(app)
    response = client.post("/api/approve", json={"verdict": "approve"})
    assert response.status_code == 200


def test_deny_endpoint():
    app = create_app()
    client = TestClient(app)
    response = client.post("/api/approve", json={"verdict": "deny"})
    assert response.status_code == 200


def test_modify_endpoint():
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/approve",
        json={
            "verdict": "modify",
            "modified_action": {"tool": "run_shell", "args": {"command": "echo safe"}, "thought": ""},
        },
    )
    assert response.status_code == 200
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/api/test_routes.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 API 层**

```python
# src/api/__init__.py
"""API 子包。"""
```

```python
# src/api/main.py
"""FastAPI 应用工厂。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router


def create_app() -> FastAPI:
    """创建 FastAPI 应用。"""
    app = FastAPI(title="NJUSE Coding Agent", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    return app
```

```python
# src/api/routes.py
"""REST 路由。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from src.types import Action
from src.governance.hitl import Decision

router = APIRouter()

# 全局 HITLGate 引用（由 ws 模块设置）
_pending_gate = None


def set_pending_gate(gate) -> None:
    """设置当前等待审批的 HITLGate。"""
    global _pending_gate
    _pending_gate = gate


class ApproveRequest(BaseModel):
    """审批请求。"""
    verdict: str
    modified_action: dict | None = None


@router.get("/health")
def health() -> dict:
    """健康检查。"""
    return {"status": "ok"}


@router.post("/approve")
def approve(req: ApproveRequest) -> dict:
    """处理用户审批决策。"""
    if _pending_gate is None:
        return {"status": "no_pending_action"}
    modified = None
    if req.modified_action:
        modified = Action(
            tool=req.modified_action["tool"],
            args=req.modified_action.get("args", {}),
            thought=req.modified_action.get("thought", ""),
        )
    _pending_gate.receive_decision(Decision(verdict=req.verdict, modified_action=modified))
    return {"status": "ok", "verdict": req.verdict}
```

```python
# src/api/ws.py
"""WebSocket 端点：实时推送 agent 状态与审批请求。"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.api.routes import set_pending_gate

ws_router = APIRouter()


@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket 端点，处理 agent 交互。"""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "run":
                await websocket.send_json({"type": "status", "message": "agent 启动"})
            elif msg.get("type") == "approve":
                set_pending_gate(None)
                await websocket.send_json({"type": "status", "message": "已审批"})
    except WebSocketDisconnect:
        pass
```

- [ ] **Step 4: 运行测试验证通过 + lint + 提交**

```bash
uv run pytest tests/api/test_routes.py -v
uv run ruff check src/api/ tests/api/ && uv run mypy src/api/
git add src/api/ tests/api/
git commit -m "feat: API 层（FastAPI + REST /health /approve + WebSocket /ws）"
```

---