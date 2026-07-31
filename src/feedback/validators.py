"""确定性验证器：解析工具输出，判断成功/失败。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.types import Action, FeedbackSignal, FeedbackType, ToolResult


class Validator(ABC):
    """验证器抽象基类。"""

    @abstractmethod
    def validate(self, action: Action, result: ToolResult) -> FeedbackSignal:
        """验证工具结果，返回反馈信号。"""
        ...


class ExitCodeValidator(Validator):
    """退出码验证器：检查 success 字段。"""

    def __init__(self, expected_exit_code: int = 0) -> None:
        self._expected = expected_exit_code

    def validate(self, action: Action, result: ToolResult) -> FeedbackSignal:
        if result.success:
            return FeedbackSignal(
                type=FeedbackType.SUCCESS,
                message=f"退出码 {self._expected} 验证通过",
            )
        return FeedbackSignal(
            type=FeedbackType.FAILURE,
            message=f"退出码验证失败: {result.stderr or '未知错误'}",
        )


class OutputContainsValidator(Validator):
    """输出包含验证器：检查 stdout 是否包含期望子串。"""

    def __init__(self, expected_substring: str) -> None:
        self._expected = expected_substring

    def validate(self, action: Action, result: ToolResult) -> FeedbackSignal:
        if self._expected in result.stdout:
            return FeedbackSignal(
                type=FeedbackType.SUCCESS,
                message=f"输出包含 '{self._expected}'，验证通过",
            )
        return FeedbackSignal(
            type=FeedbackType.FAILURE,
            message=f"输出未包含 '{self._expected}'，验证失败",
        )
