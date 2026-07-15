"""LLM 客户端抽象基类。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.types import Message


class LLMClient(ABC):
    """可注入 mock 的 LLM 抽象层。"""

    @abstractmethod
    def chat(self, messages: list[Message]) -> str:
        """发送对话消息，返回 LLM 响应字符串。"""
        ...
