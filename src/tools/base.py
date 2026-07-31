"""工具抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.types import Action, ToolResult


class Tool(ABC):
    """工具抽象基类，所有工具必须实现 execute。"""

    @abstractmethod
    def execute(self, action: Action) -> ToolResult:
        """执行动作，返回工具结果。"""
        ...
