"""反馈闭环：验证器 → 反馈信号 → 注入上下文。"""

from __future__ import annotations

from src.feedback.validators import Validator
from src.types import Action, FeedbackSignal, FeedbackType, Message, ToolResult


class FeedbackLoop:
    """反馈闭环，将工具结果经验证器转为信号并注入上下文。

    多个验证器取最严重信号（FAILURE > SUCCESS）。
    """

    def __init__(self, validators: list[Validator]) -> None:
        self._validators = validators

    def process(
        self,
        action: Action,
        result: ToolResult,
        context: list[Message],
    ) -> FeedbackSignal:
        """处理工具结果，注入反馈到上下文，返回信号。"""
        signal = self._aggregate(action, result)
        content = f"工具: {action.tool}\n输出: {result.stdout}\n错误: {result.stderr or '无'}"
        context.append(Message(role="tool", content=content, feedback=signal))
        return signal

    def _aggregate(self, action: Action, result: ToolResult) -> FeedbackSignal:
        """聚合多个验证器结果，取最严重。"""
        signals = [v.validate(action, result) for v in self._validators]
        if not signals:
            return FeedbackSignal(type=FeedbackType.INFO, message="无验证器")
        for sig in signals:
            if sig.type == FeedbackType.FAILURE:
                return sig
        return signals[0]
