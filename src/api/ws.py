"""WebSocket 端点：实时推送 agent 状态与审批请求。"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.agent.factory import create_agent
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
                task = msg.get("input", "")
                if not task:
                    await websocket.send_json(
                        {"type": "error", "message": "空输入"}
                    )
                    continue

                await websocket.send_json(
                    {"type": "status", "message": f"任务已接收: {task[:80]}"}
                )

                ev_loop = asyncio.get_event_loop()

                def on_event(
                    event: dict[str, object], _loop: asyncio.AbstractEventLoop = ev_loop
                ) -> None:
                    asyncio.run_coroutine_threadsafe(
                        websocket.send_json(event), _loop
                    )

                def run_agent(
                    _task: str = task,
                    _loop: asyncio.AbstractEventLoop = ev_loop,
                ) -> None:
                    try:
                        agent = create_agent(on_event=on_event)
                        agent.run(_task)
                    except Exception as e:
                        asyncio.run_coroutine_threadsafe(
                            websocket.send_json(
                                {"type": "error", "message": str(e)}
                            ),
                            _loop,
                        )

                import threading

                thread = threading.Thread(target=run_agent, daemon=True)
                thread.start()

            elif msg.get("type") == "approve":
                set_pending_gate(None)
                await websocket.send_json(
                    {"type": "status", "message": "已审批"}
                )

    except WebSocketDisconnect:
        pass
