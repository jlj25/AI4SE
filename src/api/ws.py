"""WebSocket 端点：实时推送 agent 状态与审批请求。"""

from __future__ import annotations

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
