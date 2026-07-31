"""HITL 审批门：有限状态机，仅在危险动作时激活。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.governance.classifier import Classification, DangerLevel
from src.types import Action


class HITLState(Enum):
    """HITL 状态机状态。"""

    IDLE = "idle"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    DENIED = "denied"
    MODIFIED = "modified"


@dataclass
class Decision:
    """用户审批决策。"""

    verdict: str  # "approve" | "deny" | "modify"
    modified_action: Action | None = None


class HITLGate:
    """HITL 审批门，有限状态机。

    仅 DANGEROUS 级别动作触发审批；SAFE/WARNING 直接放行。
    状态转移：IDLE → PENDING_APPROVAL → APPROVED/DENIED/MODIFIED。
    在异步环境中，request_approval 创建 asyncio.Future 并 await，
    receive_decision 设置 Future 结果。单测中同步模拟：若 gate 在
    PENDING_APPROVAL 时无决策可用，按 fail-closed 直接判为 DENIED。
    """

    def __init__(self) -> None:
        self._state = HITLState.IDLE
        self._pending_action: Action | None = None
        self._decision: Decision | None = None

    @property
    def state(self) -> HITLState:
        return self._state

    def gate(self, action: Action, classification: Classification) -> Action | None:
        """治理门：若 DANGEROUS 请求审批，返回最终动作或 None（拒绝）。

        fail-closed：DANGEROUS 动作若无可用决策，直接判 DENIED 并返回 None。
        """
        if classification.level != DangerLevel.DANGEROUS:
            return action
        self.request_approval(action, classification)
        if self._decision is None:
            self._state = HITLState.DENIED
            return None
        if self._decision.verdict == "deny":
            return None
        if self._decision.verdict == "modify" and self._decision.modified_action is not None:
            return self._decision.modified_action
        return action

    def request_approval(self, action: Action, classification: Classification) -> None:
        """IDLE → PENDING_APPROVAL，等待用户决策。"""
        self._state = HITLState.PENDING_APPROVAL
        self._pending_action = action
        self._decision = None

    def receive_decision(self, decision: Decision) -> None:
        """PENDING_APPROVAL → APPROVED/DENIED/MODIFIED。"""
        if self._state != HITLState.PENDING_APPROVAL:
            raise RuntimeError(f"非 PENDING_APPROVAL 状态无法接收决策: {self._state}")
        if decision.verdict == "approve":
            self._state = HITLState.APPROVED
        elif decision.verdict == "deny":
            self._state = HITLState.DENIED
        elif decision.verdict == "modify":
            self._state = HITLState.MODIFIED
            self._pending_action = decision.modified_action
        else:
            raise ValueError(f"未知 verdict: {decision.verdict}")
        self._decision = decision

    def reset(self) -> None:
        """重置到 IDLE，用于下一轮循环。"""
        self._state = HITLState.IDLE
        self._pending_action = None
        self._decision = None
