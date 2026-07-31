"""工具分发器：注册表 + 分发。"""

from __future__ import annotations

from src.tools.base import Tool
from src.types import Action, ToolResult


class ToolDispatcher:
    """工具分发器，按 tool 名查找注册的工具并执行。"""

    def __init__(self) -> None:
        self._registry: dict[str, Tool] = {}

    def register(self, name: str, tool: Tool) -> None:
        """注册工具。"""
        self._registry[name] = tool

    def dispatch(self, action: Action) -> ToolResult:
        """分发动作到对应工具。"""
        tool = self._registry.get(action.tool)
        if tool is None:
            return ToolResult(
                success=False,
                stderr=f"错误：未注册的工具 '{action.tool}'",
                exit_code=1,
            )
        try:
            return tool.execute(action)
        except Exception as e:
            return ToolResult(success=False, stderr=str(e), exit_code=1)
