## Task 10: 记忆存储

**Files:**
- Create: `src/memory/__init__.py`, `src/memory/store.py`
- Test: `tests/memory/__init__.py`, `tests/memory/test_store.py`

**Interfaces:**
- Consumes: `Message` from `src/types.py`
- Produces: `MemoryStore`（`store(msg)`, `retrieve(query, k) -> list[Message]`, `clear()`）

- [ ] **Step 1: 写失败测试**

```python
# tests/memory/__init__.py
```

```python
# tests/memory/test_store.py
"""记忆存储单测：验证存储与选择性检索。"""
from src.types import Message, FeedbackSignal, FeedbackType
from src.memory.store import MemoryStore


def test_store_and_retrieve_basic():
    store = MemoryStore()
    msg = Message(role="user", content="请帮我修复 bug", feedback=None)
    store.store(msg)
    results = store.retrieve("bug", k=5)
    assert len(results) == 1
    assert "bug" in results[0].content


def test_retrieve_by_keyword():
    store = MemoryStore()
    store.store(Message(role="user", content="安装依赖", feedback=None))
    store.store(Message(role="assistant", content="运行 pytest", feedback=None))
    store.store(Message(role="tool", content="测试通过", feedback=None))
    results = store.retrieve("pytest", k=5)
    assert len(results) == 1
    assert "pytest" in results[0].content


def test_retrieve_top_k():
    store = MemoryStore()
    for i in range(10):
        store.store(Message(role="user", content=f"任务 {i}", feedback=None))
    results = store.retrieve("任务", k=3)
    assert len(results) == 3


def test_retrieve_empty_store():
    store = MemoryStore()
    results = store.retrieve("anything", k=5)
    assert results == []


def test_clear():
    store = MemoryStore()
    store.store(Message(role="user", content="hello", feedback=None))
    store.clear()
    assert store.retrieve("hello", k=5) == []


def test_retrieve_with_feedback_signal():
    """带反馈信号的消息也能被检索。"""
    store = MemoryStore()
    signal = FeedbackSignal(type=FeedbackType.FAILURE, message="测试失败")
    store.store(Message(role="tool", content="pytest 输出", feedback=signal))
    results = store.retrieve("pytest", k=5)
    assert len(results) == 1
    assert results[0].feedback is not None
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/memory/test_store.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现记忆存储**

```python
# src/memory/__init__.py
"""记忆子包。"""
```

```python
# src/memory/store.py
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
```

- [ ] **Step 4: 运行测试验证通过 + lint + 提交**

```bash
uv run pytest tests/memory/test_store.py -v
uv run ruff check src/memory/ tests/memory/ && uv run mypy src/memory/
git add src/memory/ tests/memory/
git commit -m "feat: 记忆存储（关键词选择性检索 + 跨会话存储）"
```

---