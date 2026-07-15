"""核心数据类型定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FeedbackType(Enum):
    """反馈信号类型。"""

    SUCCESS = "success"
    FAILURE = "failure"
    INFO = "info"


@dataclass
class FeedbackSignal:
    """反馈闭环的客观信号。"""

    type: FeedbackType
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class Message:
    """LLM 对话消息。"""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    feedback: FeedbackSignal | None = None


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
