"""MockLLMClient：按脚本返回预设响应，用于离线单测。"""
from __future__ import annotations

from src.llm.base import LLMClient
from src.types import Message


class MockLLMClient(LLMClient):
    """按脚本逐条返回预设响应的 mock LLM。"""

    def __init__(self, script: list[str]) -> None:
        self._script = script
        self._index = 0
        self.call_history: list[list[Message]] = []

    def chat(self, messages: list[Message]) -> str:
        self.call_history.append(messages)
        if self._index >= len(self._script):
            raise IndexError(f"脚本耗尽：已返回 {self._index} 条，无更多预设响应")
        response = self._script[self._index]
        self._index += 1
        return response
