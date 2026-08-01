## Task 4: 范围围栏 ScopeFence（治理深度 · 1/4）

**Files:**
- Create: `src/governance/__init__.py`, `src/governance/scope.py`
- Test: `tests/governance/__init__.py`, `tests/governance/test_scope.py`

**Interfaces:**
- Consumes: `Action` from `src/types.py`
- Produces: `ScopeCheckResult(Enum)`, `ScopeFence.check(action: Action) -> ScopeCheckResult`

- [ ] **Step 1: 写失败测试**

```python
# tests/governance/__init__.py
```

```python
# tests/governance/test_scope.py
"""ScopeFence 单测：验证范围围栏的路径检查与穿越攻击防御。"""
from pathlib import Path
from src.types import Action
from src.governance.scope import ScopeFence, ScopeCheckResult


def test_allowed_path():
    fence = ScopeFence(allowed_dirs=[Path("./src"), Path("./tests")], protected_patterns=[".git/", ".env"])
    action = Action(tool="write_file", args={"path": "src/main.py", "content": "x"}, thought="")
    assert fence.check(action) == ScopeCheckResult.ALLOWED


def test_out_of_scope_path():
    fence = ScopeFence(allowed_dirs=[Path("./src")], protected_patterns=[])
    action = Action(tool="write_file", args={"path": "/etc/passwd", "content": "x"}, thought="")
    assert fence.check(action) == ScopeCheckResult.OUT_OF_SCOPE


def test_protected_path_git():
    fence = ScopeFence(allowed_dirs=[Path("./")], protected_patterns=[".git/"])
    action = Action(tool="write_file", args={"path": ".git/config", "content": "x"}, thought="")
    assert fence.check(action) == ScopeCheckResult.PROTECTED


def test_protected_path_env():
    fence = ScopeFence(allowed_dirs=[Path("./")], protected_patterns=[".env"])
    action = Action(tool="read_file", args={"path": ".env"}, thought="")
    assert fence.check(action) == ScopeCheckResult.PROTECTED


def test_path_traversal_dotdot():
    """路径穿越攻击：用 .. 绕过范围。"""
    fence = ScopeFence(allowed_dirs=[Path("./src")], protected_patterns=[])
    action = Action(tool="write_file", args={"path": "src/../../../etc/passwd", "content": "x"}, thought="")
    assert fence.check(action) == ScopeCheckResult.OUT_OF_SCOPE


def test_shell_command_with_protected_path():
    """shell 命令涉及受保护路径时也检查。"""
    fence = ScopeFence(allowed_dirs=[Path("./src")], protected_patterns=[".git/"])
    action = Action(tool="run_shell", args={"command": "cat .git/config"}, thought="")
    assert fence.check(action) == ScopeCheckResult.PROTECTED


def test_shell_command_safe():
    fence = ScopeFence(allowed_dirs=[Path("./src")], protected_patterns=[".git/"])
    action = Action(tool="run_shell", args={"command": "ls -la"}, thought="")
    assert fence.check(action) == ScopeCheckResult.ALLOWED
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/governance/test_scope.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 ScopeFence**

```python
# src/governance/__init__.py
"""治理子包。"""
```

```python
# src/governance/scope.py
"""范围围栏：检查动作目标是否在允许范围内，硬拦截不可审批放行。"""
from __future__ import annotations

import fnmatch
from enum import Enum
from pathlib import Path

from src.types import Action


class ScopeCheckResult(Enum):
    """范围围栏检查结果。"""
    ALLOWED = "allowed"
    OUT_OF_SCOPE = "out_of_scope"
    PROTECTED = "protected"


class ScopeFence:
    """范围围栏，硬拦截超出允许目录或触碰受保护路径的动作。

    PROTECTED 和 OUT_OF_SCOPE 均直接阻断，不进 HITL——绝对边界。
    路径解析处理 .. 、绝对/相对路径等绕过手段。
    """

    def __init__(self, allowed_dirs: list[Path], protected_patterns: list[str]) -> None:
        self._allowed_dirs = [d.resolve() for d in allowed_dirs]
        self._protected_patterns = protected_patterns

    def check(self, action: Action) -> ScopeCheckResult:
        """检查动作是否在允许范围内。"""
        paths = self._extract_paths(action)
        for path_str in paths:
            result = self._check_path(path_str)
            if result != ScopeCheckResult.ALLOWED:
                return result
        return ScopeCheckResult.ALLOWED

    def _extract_paths(self, action: Action) -> list[str]:
        """从动作中提取涉及的文件路径。"""
        paths: list[str] = []
        if action.tool in ("read_file", "write_file", "list_dir"):
            if "path" in action.args:
                paths.append(action.args["path"])
        elif action.tool == "run_shell":
            cmd = action.args.get("command", "")
            paths.extend(self._extract_paths_from_shell(cmd))
        return paths

    def _extract_paths_from_shell(self, command: str) -> list[str]:
        """从 shell 命令中提取文件路径参数（简化版）。"""
        tokens = command.split()
        paths: list[str] = []
        for token in tokens:
            if ("/" in token or "." in token) and not token.startswith("-"):
                paths.append(token)
        return paths

    def _check_path(self, path_str: str) -> ScopeCheckResult:
        """检查单个路径是否在范围内且不触碰受保护路径。"""
        path = Path(path_str)
        for pattern in self._protected_patterns:
            clean = pattern.rstrip("/")
            if fnmatch.fnmatch(path.name, clean) or fnmatch.fnmatch(path_str, pattern):
                return ScopeCheckResult.PROTECTED
            if path.match(clean):
                return ScopeCheckResult.PROTECTED
        resolved = path.resolve()
        for allowed_dir in self._allowed_dirs:
            try:
                resolved.relative_to(allowed_dir)
                return ScopeCheckResult.ALLOWED
            except ValueError:
                continue
        return ScopeCheckResult.OUT_OF_SCOPE
```

- [ ] **Step 4: 运行测试验证通过 + lint + 提交**

```bash
uv run pytest tests/governance/test_scope.py -v
uv run ruff check src/governance/ tests/governance/ && uv run mypy src/governance/
git add src/governance/ tests/governance/
git commit -m "feat: 范围围栏 ScopeFence（路径检查/穿越防御/受保护路径硬拦截）"
```

---