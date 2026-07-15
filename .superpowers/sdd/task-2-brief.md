## Task 2: LLM 抽象层 + MockLLMClient

**Files:**
- Create: `src/llm/__init__.py`, `src/llm/base.py`, `src/llm/mock_client.py`
- Test: `tests/llm/__init__.py`, `tests/llm/test_mock_client.py`

**Interfaces:**
- Consumes: `Message` from `src/types.py`
- Produces: `LLMClient` (ABC, `chat(messages: list[Message]) -> str`), `MockLLMClient`

- [ ] **Step 1: 写失败测试**

```python
# tests/llm/__init__.py
```

```python
# tests/llm/test_mock_client.py
"""MockLLMClient 单测：验证按脚本返回预设响应。"""
from src.types import Message
from src.llm.mock_client import MockLLMClient


def test_mock_returns_scripted_response():
    client = MockLLMClient(script=["第一个响应", "第二个响应"])
    msg = [Message(role="user", content="任务")]
    assert client.chat(msg) == "第一个响应"
    assert client.chat(msg) == "第二个响应"


def test_mock_raises_when_script_exhausted():
    import pytest
    client = MockLLMClient(script=["仅一条"])
    client.chat([Message(role="user", content="")])
    with pytest.raises(IndexError, match="脚本耗尽"):
        client.chat([Message(role="user", content="")])


def test_mock_records_call_history():
    client = MockLLMClient(script=["resp"])
    msgs = [Message(role="user", content="hello")]
    client.chat(msgs)
    assert len(client.call_history) == 1
    assert client.call_history[0] == msgs
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/llm/test_mock_client.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 LLM 抽象层**

```python
# src/llm/__init__.py
"""LLM 抽象层。"""
```

```python
# src/llm/base.py
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
```

```python
# src/llm/mock_client.py
"""MockLLMClient：按脚本返回预设响应，用于离线单测。"""
from __future__ import annotations

from src.types import Message
from src.llm.base import LLMClient


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
```

- [ ] **Step 4: 运行测试验证通过 + lint + 提交**

```bash
uv run pytest tests/llm/test_mock_client.py -v
uv run ruff check src/llm/ tests/llm/ && uv run mypy src/llm/
git add src/llm/ tests/llm/
git commit -m "feat: LLM 抽象层 + MockLLMClient（按脚本返回，可断言调用历史）"
```

---