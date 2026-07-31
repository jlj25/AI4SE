"""记忆存储：跨会话存储 + 选择性检索（关键词匹配，非全量 dump）。"""

from __future__ import annotations

from src.types import Message


class MemoryStore:
    """记忆存储，基于关键词匹配的选择性检索。

    不做全量上下文 dump，而是按查询关键词检索最相关的 k 条消息。
    使用简单的子串匹配 + 时间排序（最新优先）。
    生产环境可替换为向量存储，接口不变。
    """

    def __init__(self) -> None:
        self._messages: list[Message] = []

    def store(self, msg: Message) -> None:
        """存储消息。"""
        self._messages.append(msg)

    def retrieve(self, query: str, k: int = 5) -> list[Message]:
        """按关键词检索最相关的 k 条消息。"""
        query_lower = query.lower()
        scored: list[tuple[int, Message]] = []
        for idx, msg in enumerate(self._messages):
            content_lower = msg.content.lower()
            if query_lower in content_lower:
                scored.append((idx, msg))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [msg for _, msg in scored[:k]]

    def clear(self) -> None:
        """清空记忆。"""
        self._messages.clear()

    def all_messages(self) -> list[Message]:
        """返回所有消息（用于上下文构建）。"""
        return list(self._messages)
