## Task 1: 项目脚手架 + 核心类型

**Files:**
- Create: `pyproject.toml`, `src/__init__.py`, `src/types.py`
- Test: `tests/__init__.py`, `tests/test_types.py`

**Interfaces:**
- Produces: `Action(tool: str, args: dict, thought: str)`, `ToolResult(success: bool, stdout: str, stderr: str, exit_code: int)`, `FeedbackSignal(success: bool, message: str, details: dict)`, `Message(role: str, content: str)`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[project]
name = "njuse-coding-agent"
version = "0.1.0"
description = "Coding Agent Harness with governance-focused deep dimension"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn>=0.32.0",
    "httpx>=0.28.0",
    "keyring>=25.0.0",
    "pyyaml>=6.0",
    "websockets>=14.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.12"
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]
```

- [ ] **Step 2: 初始化项目并安装依赖**

Run: `uv sync --all-extras`
Expected: 成功创建 .venv 并安装依赖

- [ ] **Step 3: 写失败测试**

```python
# tests/__init__.py
```

```python
# tests/test_types.py
"""核心数据类型的测试。"""
from src.types import Action, ToolResult, FeedbackSignal, Message


def test_action_creation():
    action = Action(tool="read_file", args={"path": "src/main.py"}, thought="读取主文件")
    assert action.tool == "read_file"
    assert action.args == {"path": "src/main.py"}
    assert action.thought == "读取主文件"


def test_tool_result_success():
    result = ToolResult(success=True, stdout="hello", stderr="", exit_code=0)
    assert result.success is True
    assert result.stdout == "hello"
    assert result.exit_code == 0


def test_tool_result_failure():
    result = ToolResult(success=False, stdout="", stderr="not found", exit_code=1)
    assert result.success is False
    assert result.stderr == "not found"


def test_feedback_signal():
    signal = FeedbackSignal(success=False, message="2 tests failed", details={"count": 2})
    assert signal.success is False
    assert signal.details == {"count": 2}


def test_message_roles():
    msg = Message(role="user", content="修复 bug")
    assert msg.role == "user"
    assert msg.content == "修复 bug"
```

- [ ] **Step 4: 运行测试验证失败**

Run: `uv run pytest tests/test_types.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 5: 实现 src/types.py**

```python
# src/__init__.py
"""NJUSE Coding Agent Harness 内核。"""
```

```python
# src/types.py
"""核心数据类型定义。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Message:
    """LLM 对话消息。"""
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class Action:
    """agent 解析出的动作。"""
    tool: str
    args: dict
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
    details: dict = field(default_factory=dict)
```

- [ ] **Step 6: 运行测试验证通过**

Run: `uv run pytest tests/test_types.py -v`
Expected: 5 passed

- [ ] **Step 7: lint + typecheck + 提交**

```bash
uv run ruff check src/ tests/ && uv run mypy src/
git add pyproject.toml src/ tests/
git commit -m "feat: 项目脚手架 + 核心类型 (Action/ToolResult/FeedbackSignal/Message)"
```

---