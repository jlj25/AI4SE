"""REST 路由。"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from src.governance.hitl import Decision, HITLGate
from src.types import Action

router = APIRouter()

_pending_gate: HITLGate | None = None


def set_pending_gate(gate: HITLGate | None) -> None:
    """设置当前等待审批的 HITLGate。"""
    global _pending_gate
    _pending_gate = gate


def get_pending_gate() -> HITLGate | None:
    """获取当前等待审批的 HITLGate。"""
    return _pending_gate


class ApproveRequest(BaseModel):
    """审批请求。"""

    verdict: str
    modified_action: dict[str, object] | None = None


@router.get("/health")
def health() -> dict[str, str]:
    """健康检查。"""
    return {"status": "ok"}


@router.post("/approve")
def approve(req: ApproveRequest) -> dict[str, str]:
    """处理用户审批决策。"""
    gate = _pending_gate
    if gate is None:
        return {"status": "no_pending_action"}
    modified: Action | None = None
    if req.modified_action is not None:
        raw_args = req.modified_action.get("args", {})
        args = dict(raw_args) if isinstance(raw_args, dict) else {}
        modified = Action(
            tool=str(req.modified_action.get("tool", "")),
            args=args,
            thought=str(req.modified_action.get("thought", "")),
        )
    gate.receive_decision(Decision(verdict=req.verdict, modified_action=modified))
    return {"status": "ok", "verdict": req.verdict}
