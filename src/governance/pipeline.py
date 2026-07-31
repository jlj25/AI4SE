"""治理管道：范围围栏 → 危险分类 → HITL 门，三阶段串联。"""

from __future__ import annotations

from dataclasses import dataclass

from src.governance.classifier import Classification, DangerClassifier, DangerLevel
from src.governance.hitl import HITLGate
from src.governance.scope import ScopeCheckResult, ScopeFence
from src.types import Action


@dataclass
class GovernanceResult:
    """治理管道处理结果。"""

    blocked: bool
    action: Action | None
    reason: str
    classification: Classification | None


class GovernancePipeline:
    """治理管道，agent 主循环中每个动作执行前的必经之路。

    ① 范围围栏（硬拦截）→ ② 危险分类 → ③ HITL 门（仅 DANGEROUS）。
    每个阶段是确定性代码，无需 LLM，可用构造的 Action 单测。
    """

    def __init__(
        self,
        scope_fence: ScopeFence,
        danger_classifier: DangerClassifier,
        hitl_gate: HITLGate,
    ) -> None:
        self._scope_fence = scope_fence
        self._danger_classifier = danger_classifier
        self._hitl_gate = hitl_gate

    def process(self, action: Action) -> GovernanceResult:
        """处理动作，返回治理结果。"""
        # ① 范围围栏（硬拦截，不可审批放行）
        scope = self._scope_fence.check(action)
        if scope != ScopeCheckResult.ALLOWED:
            return GovernanceResult(
                blocked=True,
                action=None,
                reason=scope.value,
                classification=None,
            )
        # ② 危险分类
        classification = self._danger_classifier.classify(action)
        # ③ HITL 门（仅 DANGEROUS 触发审批）
        final_action = action
        if classification.level == DangerLevel.DANGEROUS:
            gated = self._hitl_gate.gate(action, classification)
            if gated is None:
                return GovernanceResult(
                    blocked=True,
                    action=None,
                    reason="user_denied",
                    classification=classification,
                )
            final_action = gated
        self._hitl_gate.reset()
        return GovernanceResult(
            blocked=False,
            action=final_action,
            reason="passed",
            classification=classification,
        )
