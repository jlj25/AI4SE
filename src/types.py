"""核心数据类型定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    """LLM 对话消息。"""

    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class Action:
    """agent 解析出的动作。"""

    tool: str
    args: dict[str, Any]
    thought: str


@dataclass
class ToolResult:
    """工具执行结果。"""

    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0


@dataclass
class FeedbackSignal:
    """反馈闭环的客观信号。"""

    success: bool
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
