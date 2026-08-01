## Task 8: 工具分发系统 + 具体工具

**Files:**
- Create: `src/tools/__init__.py`, `src/tools/base.py`, `src/tools/fs.py`, `src/tools/shell.py`, `src/tools/dispatcher.py`
- Test: `tests/tools/__init__.py`, `tests/tools/test_dispatcher.py`

**Interfaces:**
- Consumes: `Action` from `src/types.py`, `ToolResult` from `src/types.py`
- Produces: `Tool(ABC)`, `ToolDispatcher`, 具体工具 `ReadFileTool`, `WriteFileTool`, `ListDirTool`, `ShellTool`

- [ ] **Step 1: 写失败测试**

```python
# tests/tools/__init__.py
```

```python
# tests/tools/test_dispatcher.py
"""工具分发系统单测：验证注册、分发、执行。"""
import tempfile
from pathlib import Path
from src.types import Action, ToolResult
from src.tools.dispatcher import ToolDispatcher
from src.tools.fs import ReadFileTool, WriteFileTool, ListDirTool
from src.tools.shell import ShellTool


def test_register_and_dispatch_read_file():
    dispatcher = ToolDispatcher()
    dispatcher.register("read_file", ReadFileTool())
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "test.txt"
        p.write_text("hello world")
        action = Action(tool="read_file", args={"path": str(p)}, thought="")
        result = dispatcher.dispatch(action)
        assert isinstance(result, ToolResult)
        assert result.success
        assert "hello world" in result.output


def test_write_then_read():
    dispatcher = ToolDispatcher()
    dispatcher.register("write_file", WriteFileTool())
    dispatcher.register("read_file", ReadFileTool())
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "out.txt")
        write_action = Action(tool="write_file", args={"path": path, "content": "data"}, thought="")
        dispatcher.dispatch(write_action)
        read_action = Action(tool="read_file", args={"path": path}, thought="")
        result = dispatcher.dispatch(read_action)
        assert result.success
        assert "data" in result.output


def test_list_dir():
    dispatcher = ToolDispatcher()
    dispatcher.register("list_dir", ListDirTool())
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "a.txt").write_text("a")
        (Path(tmp) / "b.txt").write_text("b")
        action = Action(tool="list_dir", args={"path": tmp}, thought="")
        result = dispatcher.dispatch(action)
        assert result.success
        assert "a.txt" in result.output
        assert "b.txt" in result.output


def test_shell_tool():
    dispatcher = ToolDispatcher()
    dispatcher.register("run_shell", ShellTool())
    action = Action(tool="run_shell", args={"command": "echo hello"}, thought="")
    result = dispatcher.dispatch(action)
    assert result.success
    assert "hello" in result.output


def test_unknown_tool_returns_error():
    dispatcher = ToolDispatcher()
    action = Action(tool="nonexistent", args={}, thought="")
    result = dispatcher.dispatch(action)
    assert not result.success
    assert "未注册" in result.output or "unknown" in result.output.lower()


def test_read_nonexistent_file():
    dispatcher = ToolDispatcher()
    dispatcher.register("read_file", ReadFileTool())
    action = Action(tool="read_file", args={"path": "/nonexistent/path/file.txt"}, thought="")
    result = dispatcher.dispatch(action)
    assert not result.success
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/tools/test_dispatcher.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现工具基类与分发器**

```python
# src/tools/__init__.py
"""工具子包。"""
```

```python
# src/tools/base.py
"""工具抽象基类。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.types import Action, ToolResult


class Tool(ABC):
    """工具抽象基类，所有工具必须实现 execute。"""

    @abstractmethod
    def execute(self, action: Action) -> ToolResult:
        """执行动作，返回工具结果。"""
        ...
```

```python
# src/tools/dispatcher.py
"""工具分发器：注册表 + 分发。"""
from __future__ import annotations

from src.types import Action, ToolResult
from src.tools.base import Tool


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
                output=f"错误：未注册的工具 '{action.tool}'",
                error=f"Tool '{action.tool}' not registered",
            )
        try:
            return tool.execute(action)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
```

```python
# src/tools/fs.py
"""文件系统工具：读、写、列目录。"""
from __future__ import annotations

from pathlib import Path

from src.types import Action, ToolResult
from src.tools.base import Tool


class ReadFileTool(Tool):
    """读取文件内容。"""

    def execute(self, action: Action) -> ToolResult:
        path = Path(action.args["path"])
        try:
            content = path.read_text(encoding="utf-8")
            return ToolResult(success=True, output=content, error=None)
        except FileNotFoundError:
            return ToolResult(success=False, output="", error=f"文件不存在: {path}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class WriteFileTool(Tool):
    """写入文件内容。"""

    def execute(self, action: Action) -> ToolResult:
        path = Path(action.args["path"])
        content = action.args["content"]
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return ToolResult(success=True, output=f"已写入 {path}", error=None)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class ListDirTool(Tool):
    """列出目录内容。"""

    def execute(self, action: Action) -> ToolResult:
        path = Path(action.args["path"])
        try:
            entries = [f.name for f in path.iterdir()]
            return ToolResult(success=True, output="\n".join(entries), error=None)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
```

```python
# src/tools/shell.py
"""Shell 命令工具。"""
from __future__ import annotations

import subprocess

from src.types import Action, ToolResult
from src.tools.base import Tool


class ShellTool(Tool):
    """执行 shell 命令，捕获 stdout/stderr。"""

    def execute(self, action: Action) -> ToolResult:
        command = action.args["command"]
        try:
            proc = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=30,
            )
            success = proc.returncode == 0
            output = proc.stdout
            error = proc.stderr if not success else None
            return ToolResult(success=success, output=output, error=error)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="命令超时（30s）")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
```

- [ ] **Step 4: 运行测试验证通过 + lint + 提交**

```bash
uv run pytest tests/tools/test_dispatcher.py -v
uv run ruff check src/tools/ tests/tools/ && uv run mypy src/tools/
git add src/tools/ tests/tools/
git commit -m "feat: 工具分发系统（Tool ABC + ToolDispatcher + FS/Shell 工具）"
```

---