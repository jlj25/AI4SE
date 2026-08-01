## Task 9: 反馈闭环 + 验证器

**Files:**
- Create: `src/feedback/__init__.py`, `src/feedback/validators.py`, `src/feedback/loop.py`
- Test: `tests/feedback/__init__.py`, `tests/feedback/test_validators.py`, `tests/feedback/test_loop.py`

**Interfaces:**
- Consumes: `ToolResult` from `src/types.py`, `Action` from `src/types.py`
- Produces: `FeedbackSignal` from `src/types.py`, `Validator(ABC)`, `ExitCodeValidator`, `OutputContainsValidator`, `FeedbackLoop`

- [ ] **Step 1: 写失败测试**

```python
# tests/feedback/__init__.py
```

```python
# tests/feedback/test_validators.py
"""验证器单测：验证确定性反馈信号生成。"""
from src.types import Action, ToolResult, FeedbackSignal, FeedbackType
from src.feedback.validators import ExitCodeValidator, OutputContainsValidator


def test_exit_code_success():
    validator = ExitCodeValidator(expected_exit_code=0)
    result = ToolResult(success=True, output="done", error=None)
    signal = validator.validate(Action(tool="run_shell", args={"command": "ls"}, thought=""), result)
    assert signal.type == FeedbackType.SUCCESS
    assert "通过" in signal.message


def test_exit_code_failure():
    validator = ExitCodeValidator(expected_exit_code=0)
    result = ToolResult(success=False, output="", error="command not found")
    signal = validator.validate(Action(tool="run_shell", args={"command": "bad"}, thought=""), result)
    assert signal.type == FeedbackType.FAILURE
    assert "失败" in signal.message


def test_output_contains_success():
    validator = OutputContainsValidator(expected_substring="PASS")
    result = ToolResult(success=True, output="tests PASS", error=None)
    signal = validator.validate(Action(tool="run_shell", args={"command": "pytest"}, thought=""), result)
    assert signal.type == FeedbackType.SUCCESS


def test_output_contains_failure():
    validator = OutputContainsValidator(expected_substring="PASS")
    result = ToolResult(success=True, output="tests FAILED", error=None)
    signal = validator.validate(Action(tool="run_shell", args={"command": "pytest"}, thought=""), result)
    assert signal.type == FeedbackType.FAILURE
```

```python
# tests/feedback/test_loop.py
"""反馈闭环单测：验证信号注入回上下文。"""
from src.types import Action, ToolResult, Message, FeedbackSignal, FeedbackType
from src.feedback.loop import FeedbackLoop
from src.feedback.validators import ExitCodeValidator


def test_feedback_injected_into_context():
    loop = FeedbackLoop(validators=[ExitCodeValidator(expected_exit_code=0)])
    action = Action(tool="run_shell", args={"command": "ls"}, thought="")
    result = ToolResult(success=True, output="file.txt", error=None)
    context: list[Message] = []
    loop.process(action, result, context)
    assert len(context) == 1
    assert context[0].role == "tool"
    assert "file.txt" in context[0].content
    assert context[0].feedback is not None
    assert context[0].feedback.type == FeedbackType.SUCCESS


def test_feedback_failure_injected():
    loop = FeedbackLoop(validators=[ExitCodeValidator(expected_exit_code=0)])
    action = Action(tool="run_shell", args={"command": "bad"}, thought="")
    result = ToolResult(success=False, output="", error="not found")
    context: list[Message] = []
    loop.process(action, result, context)
    assert context[0].feedback.type == FeedbackType.FAILURE
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/feedback/ -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现验证器与反馈闭环**

```python
# src/feedback/__init__.py
"""反馈子包。"""
```

```python
# src/feedback/validators.py
"""确定性验证器：解析工具输出，判断成功/失败。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.types import Action, ToolResult, FeedbackSignal, FeedbackType


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
            message=f"退出码验证失败: {result.error or '未知错误'}",
        )


class OutputContainsValidator(Validator):
    """输出包含验证器：检查 stdout 是否包含期望子串。"""

    def __init__(self, expected_substring: str) -> None:
        self._expected = expected_substring

    def validate(self, action: Action, result: ToolResult) -> FeedbackSignal:
        if self._expected in result.output:
            return FeedbackSignal(
                type=FeedbackType.SUCCESS,
                message=f"输出包含 '{self._expected}'，验证通过",
            )
        return FeedbackSignal(
            type=FeedbackType.FAILURE,
            message=f"输出未包含 '{self._expected}'，验证失败",
        )
```

```python
# src/feedback/loop.py
"""反馈闭环：验证器 → 反馈信号 → 注入上下文。"""
from __future__ import annotations

from src.types import Action, ToolResult, Message, FeedbackSignal, FeedbackType
from src.feedback.validators import Validator


class FeedbackLoop:
    """反馈闭环，将工具结果经验证器转为信号并注入上下文。

    多个验证器取最严重信号（FAILURE > SUCCESS）。
    """

    def __init__(self, validators: list[Validator]) -> None:
        self._validators = validators

    def process(
        self, action: Action, result: ToolResult, context: list[Message],
    ) -> FeedbackSignal:
        """处理工具结果，注入反馈到上下文，返回信号。"""
        signal = self._aggregate(action, result)
        content = f"工具: {action.tool}\n输出: {result.output}\n错误: {result.error or '无'}"
        context.append(Message(role="tool", content=content, feedback=signal))
        return signal

    def _aggregate(self, action: Action, result: ToolResult) -> FeedbackSignal:
        """聚合多个验证器结果，取最严重。"""
        signals = [v.validate(action, result) for v in self._validators]
        if not signals:
            return FeedbackSignal(type=FeedbackType.INFO, message="无验证器")
        for sig in signals:
            if sig.type == FeedbackType.FAILURE:
                return sig
        return signals[0]
```

- [ ] **Step 4: 运行测试验证通过 + lint + 提交**

```bash
uv run pytest tests/feedback/ -v
uv run ruff check src/feedback/ tests/feedback/ && uv run mypy src/feedback/
git add src/feedback/ tests/feedback/
git commit -m "feat: 反馈闭环（Validator ABC + ExitCode/OutputContains 验证器 + FeedbackLoop）"
```

---