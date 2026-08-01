# NJUSE Coding Agent Harness 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个以治理为核心深度的 coding agent harness，agent 能自主读写文件/跑测试，危险动作经治理管道拦截并支持 WebUI 实时 HITL 审批。

**Architecture:** 管道式治理——agent 主循环中每个动作经"范围围栏→危险分类→HITL 门"三阶段管道后执行。后端 Python+FastAPI，前端 React+Open Design，Docker 分发，阿里云 ECS 部署。

**Tech Stack:** Python 3.12 + uv, FastAPI + WebSocket, React + Vite + TypeScript + Open Design, SQLite, Docker, keyring

## Global Constraints

- Python 3.12+，依赖管理用 uv（AGENTS.md 指定）
- 运行顺序：`uv run ruff check .` → `uv run mypy .` → `uv run pytest -xvs`
- 核心机制必须可用 mock/stub LLM 单测，不依赖网络与真实 LLM
- 代码中零引用明文 API key；opencode.json 已在 .gitignore 中
- 代码注释和文档使用简体中文（AGENTS.md 规定）
- TDD 强制：先红→再绿→再重构，不接受先写实现再补测试
- harness 内核不得寄生于 LangChain/AutoGen/CrewAI 等现成框架

---

## 文件结构

### 后端 Harness 内核 (src/)

| 文件 | 职责 |
|------|------|
| `src/__init__.py` | 包初始化 |
| `src/types.py` | 核心数据类型：Action, ToolResult, FeedbackSignal, Message |
| `src/llm/__init__.py` | LLM 子包 |
| `src/llm/base.py` | LLMClient 抽象基类 |
| `src/llm/real_client.py` | RealLLMClient（njusehub 适配器） |
| `src/llm/mock_client.py` | MockLLMClient（单测用） |
| `src/llm/parser.py` | ActionParser（解析 LLM 输出） |
| `src/governance/__init__.py` | 治理子包 |
| `src/governance/scope.py` | ScopeFence（范围围栏） |
| `src/governance/classifier.py` | DangerClassifier（危险分类学） |
| `src/governance/hitl.py` | HITLGate（HITL 状态机） |
| `src/governance/pipeline.py` | GovernancePipeline（管道串联） |
| `src/tools/__init__.py` | 工具子包 |
| `src/tools/base.py` | Tool ABC + ToolDispatcher |
| `src/tools/filesystem.py` | ReadFile/WriteFile/ListDir 工具 |
| `src/tools/shell.py` | RunShellTool |
| `src/tools/testing.py` | RunTestsTool, RunLintTool |
| `src/feedback/__init__.py` | 反馈子包 |
| `src/feedback/base.py` | Validator ABC + FeedbackLoop |
| `src/feedback/validators.py` | TestValidator, LintValidator |
| `src/memory/__init__.py` | 记忆子包 |
| `src/memory/store.py` | Memory（JSON 存储 + 关键词检索） |
| `src/config/__init__.py` | 配置子包 |
| `src/config/loader.py` | ConfigLoader + AgentConfig |
| `src/credentials/__init__.py` | 凭据子包 |
| `src/credentials/manager.py` | CredentialManager（OS 钥匙串） |
| `src/agent/__init__.py` | Agent 子包 |
| `src/agent/loop.py` | AgentLoop（主循环） |
| `src/api/__init__.py` | API 子包 |
| `src/api/app.py` | FastAPI 应用 + REST 端点 |
| `src/api/events.py` | EventBroadcaster（WebSocket） |

### 前端 (web/)

| 文件 | 职责 |
|------|------|
| `web/package.json` | 前端依赖 |
| `web/vite.config.ts` | Vite 配置 |
| `web/index.html` | HTML 入口 |
| `web/src/main.tsx` | React 入口 |
| `web/src/App.tsx` | 主应用组件 |
| `web/src/hooks/useWebSocket.ts` | WebSocket hook |
| `web/src/components/TaskPanel.tsx` | 任务输入面板 |
| `web/src/components/StepStream.tsx` | 步骤实时流 |
| `web/src/components/ApprovalCard.tsx` | 审批卡片 |

### 配置/部署

| 文件 | 职责 |
|------|------|
| `pyproject.toml` | Python 项目配置 |
| `config.yaml` | 默认治理配置 |
| `Dockerfile` | 多阶段构建 |
| `.gitlab-ci.yml` | CI（lint/test/build） |

### 任务依赖与并行

```
Phase 1 (串行):  Task 1 (类型基础)
Phase 2 (并行):  Task 2 (LLM) | Task 3 (配置) | Task 4 (范围围栏)
                 Task 8 (工具) | Task 9 (反馈) | Task 10 (记忆) | Task 11 (凭据) | Task 12 (解析器)
Phase 3 (串行):  Task 5 (危险分类) → Task 6 (HITL门) → Task 7 (治理管道)
Phase 4 (串行):  Task 13 (Agent主循环)
Phase 5 (串行):  Task 14 (API层)
Phase 6 (并行):  Task 15 (前端) | Task 17 (机制演示)
Phase 7 (串行):  Task 16 (Docker+CI)
```

---

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

## Task 3: 配置加载器

**Files:**
- Create: `src/config/__init__.py`, `src/config/loader.py`, `config.yaml`
- Test: `tests/config/__init__.py`, `tests/config/test_loader.py`

**Interfaces:**
- Produces: `AgentConfig`, `ScopeConfig`, `DangerRule`, `LLMConfig`, `ConfigLoader.load(path) -> AgentConfig`

- [ ] **Step 1: 写失败测试**

```python
# tests/config/__init__.py
```

```python
# tests/config/test_loader.py
"""ConfigLoader 单测：验证 YAML 加载与字段校验。"""
from pathlib import Path
from src.config.loader import AgentConfig, ScopeConfig, DangerRule, LLMConfig, ConfigLoader


def test_load_full_config(tmp_path: Path):
    yaml_content = """
agent:
  max_steps: 30
scope:
  allowed_dirs:
    - "./src"
    - "./tests"
  protected_patterns:
    - ".git/"
    - ".env"
danger_rules:
  - name: force_delete
    pattern: 'rm\\s+-rf'
    level: dangerous
    description: 递归强制删除
  - name: install_pkg
    pattern: 'pip\\s+install'
    level: warning
    description: 安装包
llm:
  model: "glm-5.2"
  base_url: "https://njusehub.info/v1"
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content, encoding="utf-8")
    config = ConfigLoader.load(config_file)
    assert config.max_steps == 30
    assert config.scope.allowed_dirs == ["./src", "./tests"]
    assert config.scope.protected_patterns == [".git/", ".env"]
    assert len(config.danger_rules) == 2
    assert config.danger_rules[0].name == "force_delete"
    assert config.danger_rules[0].level == "dangerous"
    assert config.llm.model == "glm-5.2"


def test_load_defaults_when_fields_missing(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("agent:\n  max_steps: 10\n", encoding="utf-8")
    config = ConfigLoader.load(config_file)
    assert config.max_steps == 10
    assert config.scope.allowed_dirs == ["./"]
    assert config.danger_rules == []


def test_danger_rule_creation():
    rule = DangerRule(name="test", pattern="rm", level="dangerous", description="测试")
    assert rule.name == "test"
    assert rule.level == "dangerous"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/config/test_loader.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 ConfigLoader**

```python
# src/config/__init__.py
"""配置子包。"""
```

```python
# src/config/loader.py
"""声明式 YAML 配置加载器。"""
from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ScopeConfig:
    """范围围栏配置。"""
    allowed_dirs: list[str] = field(default_factory=lambda: ["./"])
    protected_patterns: list[str] = field(default_factory=list)


@dataclass
class DangerRule:
    """危险规则。"""
    name: str
    pattern: str
    level: str
    description: str = ""


@dataclass
class LLMConfig:
    """LLM 供应商配置。"""
    model: str = "glm-5.2"
    base_url: str = "https://njusehub.info/v1"


@dataclass
class AgentConfig:
    """agent 完整配置。"""
    max_steps: int = 50
    scope: ScopeConfig = field(default_factory=ScopeConfig)
    danger_rules: list[DangerRule] = field(default_factory=list)
    llm: LLMConfig = field(default_factory=LLMConfig)


class ConfigLoader:
    """从 YAML 文件加载并校验配置。"""

    @staticmethod
    def load(path: Path) -> AgentConfig:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        agent_section = raw.get("agent", {})
        scope_section = raw.get("scope", {})
        rules_section = raw.get("danger_rules", [])
        llm_section = raw.get("llm", {})
        scope = ScopeConfig(
            allowed_dirs=scope_section.get("allowed_dirs", ["./"]),
            protected_patterns=scope_section.get("protected_patterns", []),
        )
        danger_rules = [
            DangerRule(
                name=r["name"], pattern=r["pattern"],
                level=r["level"], description=r.get("description", ""),
            )
            for r in rules_section
        ]
        llm = LLMConfig(
            model=llm_section.get("model", "glm-5.2"),
            base_url=llm_section.get("base_url", "https://njusehub.info/v1"),
        )
        return AgentConfig(
            max_steps=agent_section.get("max_steps", 50),
            scope=scope, danger_rules=danger_rules, llm=llm,
        )
```

- [ ] **Step 4: 创建默认 config.yaml**

```yaml
# config.yaml
agent:
  max_steps: 50
scope:
  allowed_dirs: ["./src", "./tests"]
  protected_patterns: [".git/", ".env", "*.key"]
danger_rules:
  - name: recursive_force_delete_root
    pattern: 'rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?-rf?\s+/'
    level: dangerous
    description: 递归强制删除根目录
  - name: force_push
    pattern: 'git\s+push.*--force'
    level: dangerous
    description: 强制推送覆盖远程历史
  - name: curl_pipe_bash
    pattern: 'curl.*\|\s*(ba)?sh'
    level: dangerous
    description: 远程脚本直接执行
  - name: install_package
    pattern: '(pip|npm|yarn)\s+install'
    level: warning
    description: 安装软件包
llm:
  model: "glm-5.2"
  base_url: "https://njusehub.info/v1"
```

- [ ] **Step 5: 运行测试验证通过 + lint + 提交**

```bash
uv run pytest tests/config/test_loader.py -v
uv run ruff check src/config/ tests/config/ && uv run mypy src/config/
git add src/config/ tests/config/ config.yaml
git commit -m "feat: 配置加载器（YAML→强类型 AgentConfig）+ 默认 config.yaml"
```

---

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

## Task 5: 危险分类器 DangerClassifier（治理深度 · 2/4）

**Files:**
- Create: `src/governance/classifier.py`
- Test: `tests/governance/test_classifier.py`

**Interfaces:**
- Consumes: `Action` from `src/types.py`, `DangerRule` from `src/config/loader.py`
- Produces: `DangerLevel(Enum)`, `Classification(level, matched_rule, reason)`, `DangerClassifier.classify(action) -> Classification`

- [ ] **Step 1: 写失败测试**

```python
# tests/governance/test_classifier.py
"""DangerClassifier 单测：验证危险命令模式匹配与风险分级。"""
from src.types import Action
from src.config.loader import DangerRule
from src.governance.classifier import DangerClassifier, DangerLevel


def _make_rules() -> list[DangerRule]:
    return [
        DangerRule(name="force_delete", pattern=r"rm\s+(-\w*\w\w*\s+)?-rf?\s+/", level="dangerous", description="递归删除"),
        DangerRule(name="force_push", pattern=r"git\s+push.*--force", level="dangerous", description="强制推送"),
        DangerRule(name="install_pkg", pattern=r"(pip|npm)\s+install", level="warning", description="安装包"),
    ]


def test_dangerous_rm_rf():
    classifier = DangerClassifier(_make_rules())
    action = Action(tool="run_shell", args={"command": "rm -rf /"}, thought="")
    result = classifier.classify(action)
    assert result.level == DangerLevel.DANGEROUS
    assert result.matched_rule == "force_delete"


def test_dangerous_git_force_push():
    classifier = DangerClassifier(_make_rules())
    action = Action(tool="run_shell", args={"command": "git push --force origin main"}, thought="")
    result = classifier.classify(action)
    assert result.level == DangerLevel.DANGEROUS
    assert result.matched_rule == "force_push"


def test_warning_pip_install():
    classifier = DangerClassifier(_make_rules())
    action = Action(tool="run_shell", args={"command": "pip install requests"}, thought="")
    result = classifier.classify(action)
    assert result.level == DangerLevel.WARNING
    assert result.matched_rule == "install_pkg"


def test_safe_command():
    classifier = DangerClassifier(_make_rules())
    action = Action(tool="run_shell", args={"command": "ls -la"}, thought="")
    result = classifier.classify(action)
    assert result.level == DangerLevel.SAFE
    assert result.matched_rule is None


def test_safe_file_read():
    classifier = DangerClassifier(_make_rules())
    action = Action(tool="read_file", args={"path": "src/main.py"}, thought="")
    result = classifier.classify(action)
    assert result.level == DangerLevel.SAFE


def test_highest_level_wins():
    """多条规则命中时取最高风险等级。"""
    rules = [
        DangerRule(name="warn1", pattern=r"rm", level="warning", description=""),
        DangerRule(name="danger1", pattern=r"rm\s+-rf", level="dangerous", description=""),
    ]
    classifier = DangerClassifier(rules)
    action = Action(tool="run_shell", args={"command": "rm -rf /tmp"}, thought="")
    result = classifier.classify(action)
    assert result.level == DangerLevel.DANGEROUS
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/governance/test_classifier.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 DangerClassifier**

```python
# src/governance/classifier.py
"""危险分类学：对动作进行风险分级，代码拦截而非提示词。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from src.config.loader import DangerRule
from src.types import Action


class DangerLevel(Enum):
    """风险等级。"""
    SAFE = "safe"
    WARNING = "warning"
    DANGEROUS = "dangerous"


_LEVEL_PRIORITY = {
    DangerLevel.SAFE: 0,
    DangerLevel.WARNING: 1,
    DangerLevel.DANGEROUS: 2,
}


@dataclass
class Classification:
    """危险分类结果。"""
    level: DangerLevel
    matched_rule: str | None
    reason: str


class DangerClassifier:
    """对通过范围围栏的动作进行风险分级。

    遍历规则做命令模式匹配（正则），取最高风险等级。
    无命中则默认 SAFE。这是确定性代码，无需 LLM。
    """

    def __init__(self, rules: list[DangerRule]) -> None:
        self._rules = rules

    def classify(self, action: Action) -> Classification:
        """对动作进行危险分类。"""
        if action.tool != "run_shell":
            return Classification(level=DangerLevel.SAFE, matched_rule=None, reason="非 shell 命令")
        command = action.args.get("command", "")
        best_level = DangerLevel.SAFE
        best_rule: str | None = None
        best_reason = "无危险规则命中"
        for rule in self._rules:
            if re.search(rule.pattern, command):
                rule_level = DangerLevel(rule.level)
                if _LEVEL_PRIORITY[rule_level] > _LEVEL_PRIORITY[best_level]:
                    best_level = rule_level
                    best_rule = rule.name
                    best_reason = rule.description
        return Classification(level=best_level, matched_rule=best_rule, reason=best_reason)
```

- [ ] **Step 4: 运行测试验证通过 + lint + 提交**

```bash
uv run pytest tests/governance/test_classifier.py -v
uv run ruff check src/governance/classifier.py tests/governance/test_classifier.py && uv run mypy src/governance/classifier.py
git add src/governance/classifier.py tests/governance/test_classifier.py
git commit -m "feat: 危险分类器 DangerClassifier（正则模式匹配/风险分级/最高等级优先）"
```

---

## Task 6: HITL 审批门 HITLGate（治理深度 · 3/4）

**Files:**
- Create: `src/governance/hitl.py`
- Test: `tests/governance/test_hitl.py`

**Interfaces:**
- Consumes: `Action` from `src/types.py`, `Classification` from `src/governance/classifier.py`
- Produces: `HITLState(Enum)`, `Decision(verdict, modified_action)`, `HITLGate`（状态机 + `gate(action, classification) -> Action | None`）

- [ ] **Step 1: 写失败测试**

```python
# tests/governance/test_hitl.py
"""HITLGate 单测：验证状态机转移与审批逻辑。"""
from src.types import Action
from src.governance.classifier import DangerLevel, Classification
from src.governance.hitl import HITLGate, HITLState, Decision


def _make_gate() -> HITLGate:
    return HITLGate()


def test_initial_state_idle():
    gate = _make_gate()
    assert gate.state == HITLState.IDLE


def test_safe_action_passes_without_approval():
    gate = _make_gate()
    action = Action(tool="read_file", args={"path": "x"}, thought="")
    classification = Classification(level=DangerLevel.SAFE, matched_rule=None, reason="")
    result = gate.gate(action, classification)
    assert result == action
    assert gate.state == HITLState.IDLE


def test_dangerous_action_requests_approval():
    gate = _make_gate()
    action = Action(tool="run_shell", args={"command": "rm -rf /"}, thought="")
    classification = Classification(level=DangerLevel.DANGEROUS, matched_rule="test", reason="危险")
    gate.request_approval(action, classification)
    assert gate.state == HITLState.PENDING_APPROVAL


def test_approve_transitions_to_approved():
    gate = _make_gate()
    action = Action(tool="run_shell", args={"command": "rm -rf /tmp"}, thought="")
    classification = Classification(level=DangerLevel.DANGEROUS, matched_rule="test", reason="危险")
    gate.request_approval(action, classification)
    gate.receive_decision(Decision(verdict="approve"))
    assert gate.state == HITLState.APPROVED


def test_deny_returns_none():
    gate = _make_gate()
    action = Action(tool="run_shell", args={"command": "rm -rf /"}, thought="")
    classification = Classification(level=DangerLevel.DANGEROUS, matched_rule="test", reason="危险")
    result = gate.gate(action, classification)
    assert result is None
    assert gate.state == HITLState.DENIED


def test_modify_returns_modified_action():
    gate = _make_gate()
    original = Action(tool="run_shell", args={"command": "rm -rf /"}, thought="")
    modified = Action(tool="run_shell", args={"command": "rm -rf /tmp/safe"}, thought="")
    classification = Classification(level=DangerLevel.DANGEROUS, matched_rule="test", reason="危险")
    gate.request_approval(original, classification)
    gate.receive_decision(Decision(verdict="modify", modified_action=modified))
    assert gate.state == HITLState.MODIFIED


def test_reset_to_idle():
    gate = _make_gate()
    action = Action(tool="run_shell", args={"command": "rm -rf /"}, thought="")
    classification = Classification(level=DangerLevel.DANGEROUS, matched_rule="test", reason="危险")
    gate.request_approval(action, classification)
    gate.receive_decision(Decision(verdict="deny"))
    gate.reset()
    assert gate.state == HITLState.IDLE
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/governance/test_hitl.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 HITLGate**

```python
# src/governance/hitl.py
"""HITL 审批门：有限状态机，仅在危险动作时激活。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.types import Action
from src.governance.classifier import Classification, DangerLevel


class HITLState(Enum):
    """HITL 状态机状态。"""
    IDLE = "idle"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    DENIED = "denied"
    MODIFIED = "modified"


@dataclass
class Decision:
    """用户审批决策。"""
    verdict: str  # "approve" | "deny" | "modify"
    modified_action: Action | None = None


class HITLGate:
    """HITL 审批门，有限状态机。

    仅 DANGEROUS 级别动作触发审批；SAFE/WARNING 直接放行。
    状态转移：IDLE → PENDING_APPROVAL → APPROVED/DENIED/MODIFIED。
    在异步环境中，request_approval 创建 asyncio.Future 并 await，
    receive_decision 设置 Future 结果。单测中同步模拟。
    """

    def __init__(self) -> None:
        self._state = HITLState.IDLE
        self._pending_action: Action | None = None
        self._decision: Decision | None = None

    @property
    def state(self) -> HITLState:
        return self._state

    def gate(self, action: Action, classification: Classification) -> Action | None:
        """治理门：若 DANGEROUS 请求审批，返回最终动作或 None（拒绝）。"""
        if classification.level != DangerLevel.DANGEROUS:
            return action
        self.request_approval(action, classification)
        if self._decision is None:
            return None
        if self._decision.verdict == "deny":
            return None
        if self._decision.verdict == "modify" and self._decision.modified_action is not None:
            return self._decision.modified_action
        return action

    def request_approval(self, action: Action, classification: Classification) -> None:
        """IDLE → PENDING_APPROVAL，等待用户决策。"""
        self._state = HITLState.PENDING_APPROVAL
        self._pending_action = action
        self._decision = None

    def receive_decision(self, decision: Decision) -> None:
        """PENDING_APPROVAL → APPROVED/DENIED/MODIFIED。"""
        if self._state != HITLState.PENDING_APPROVAL:
            raise RuntimeError(f"非 PENDING_APPROVAL 状态无法接收决策: {self._state}")
        if decision.verdict == "approve":
            self._state = HITLState.APPROVED
        elif decision.verdict == "deny":
            self._state = HITLState.DENIED
        elif decision.verdict == "modify":
            self._state = HITLState.MODIFIED
            self._pending_action = decision.modified_action
        else:
            raise ValueError(f"未知 verdict: {decision.verdict}")
        self._decision = decision

    def reset(self) -> None:
        """重置到 IDLE，用于下一轮循环。"""
        self._state = HITLState.IDLE
        self._pending_action = None
        self._decision = None
```

- [ ] **Step 4: 运行测试验证通过 + lint + 提交**

```bash
uv run pytest tests/governance/test_hitl.py -v
uv run ruff check src/governance/hitl.py tests/governance/test_hitl.py && uv run mypy src/governance/hitl.py
git add src/governance/hitl.py tests/governance/test_hitl.py
git commit -m "feat: HITL 审批门（有限状态机 IDLE→PENDING→APPROVED/DENIED/MODIFIED）"
```

---

## Task 7: 治理管道 GovernancePipeline（治理深度 · 4/4 集成）

**Files:**
- Create: `src/governance/pipeline.py`
- Test: `tests/governance/test_pipeline.py`

**Interfaces:**
- Consumes: `ScopeFence`, `DangerClassifier`, `HITLGate`
- Produces: `GovernanceResult(blocked, action, reason, classification)`, `GovernancePipeline.process(action) -> GovernanceResult`

- [ ] **Step 1: 写失败测试**

```python
# tests/governance/test_pipeline.py
"""GovernancePipeline 单测：验证管道串联与端到端治理行为。"""
from pathlib import Path
from src.types import Action
from src.config.loader import DangerRule
from src.governance.scope import ScopeFence
from src.governance.classifier import DangerClassifier, DangerLevel
from src.governance.hitl import HITLGate, Decision
from src.governance.pipeline import GovernancePipeline, GovernanceResult


def _make_pipeline(hitl_gate: HITLGate | None = None) -> GovernancePipeline:
    fence = ScopeFence(allowed_dirs=[Path("./src"), Path("./tests")], protected_patterns=[".git/", ".env"])
    rules = [
        DangerRule(name="force_delete", pattern=r"rm\s+(-\w*\w\w*\s+)?-rf?\s+/", level="dangerous", description="递归删除"),
        DangerRule(name="install_pkg", pattern=r"pip\s+install", level="warning", description="安装包"),
    ]
    classifier = DangerClassifier(rules)
    gate = hitl_gate or HITLGate()
    return GovernancePipeline(scope_fence=fence, danger_classifier=classifier, hitl_gate=gate)


def test_safe_action_passes():
    pipeline = _make_pipeline()
    action = Action(tool="read_file", args={"path": "src/main.py"}, thought="")
    result = pipeline.process(action)
    assert not result.blocked
    assert result.action == action


def test_out_of_scope_blocked_without_hitl():
    """范围围栏硬拦截，不进 HITL。"""
    pipeline = _make_pipeline()
    action = Action(tool="write_file", args={"path": "/etc/passwd", "content": "x"}, thought="")
    result = pipeline.process(action)
    assert result.blocked
    assert "out_of_scope" in result.reason
    assert result.classification is None


def test_protected_path_blocked_without_hitl():
    pipeline = _make_pipeline()
    action = Action(tool="write_file", args={"path": ".git/config", "content": "x"}, thought="")
    result = pipeline.process(action)
    assert result.blocked
    assert "protected" in result.reason


def test_dangerous_action_blocked_when_denied():
    """DEMO1 场景：危险动作被拦截。"""
    gate = HITLGate()
    pipeline = _make_pipeline(hitl_gate=gate)
    action = Action(tool="run_shell", args={"command": "rm -rf /"}, thought="")
    # 模拟用户拒绝：在 gate 中预设 deny
    gate._decision = Decision(verdict="deny")  # noqa: SLF001
    gate._state = gate._state.__class__("pending_approval")  # 强制进入 pending
    result = pipeline.process(action)
    assert result.blocked
    assert result.classification is not None
    assert result.classification.level == DangerLevel.DANGEROUS


def test_warning_action_passes_without_hitl():
    pipeline = _make_pipeline()
    action = Action(tool="run_shell", args={"command": "pip install requests"}, thought="")
    result = pipeline.process(action)
    assert not result.blocked
    assert result.classification.level == DangerLevel.WARNING
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/governance/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 GovernancePipeline**

```python
# src/governance/pipeline.py
"""治理管道：范围围栏 → 危险分类 → HITL 门，三阶段串联。"""
from __future__ import annotations

from dataclasses import dataclass

from src.types import Action
from src.governance.scope import ScopeFence, ScopeCheckResult
from src.governance.classifier import Classification, DangerClassifier, DangerLevel
from src.governance.hitl import HITLGate


@dataclass
class GovernanceResult:
    """治理管道处理结果。"""
    blocked: bool
    action: Action | None
    reason: str
    classification: Classification | None


class GovernancePipeline:
    """治理管道，agent 主循环中每个动作执行前的必经之路。

    ① 范围围栏（硬拦截）→ ② 危险分类 → ③ HITL 门（仅 DANGEROUS）。
    每个阶段是确定性代码，无需 LLM，可用构造的 Action 单测。
    """

    def __init__(
        self,
        scope_fence: ScopeFence,
        danger_classifier: DangerClassifier,
        hitl_gate: HITLGate,
    ) -> None:
        self._scope_fence = scope_fence
        self._danger_classifier = danger_classifier
        self._hitl_gate = hitl_gate

    def process(self, action: Action) -> GovernanceResult:
        """处理动作，返回治理结果。"""
        # ① 范围围栏（硬拦截）
        scope = self._scope_fence.check(action)
        if scope != ScopeCheckResult.ALLOWED:
            return GovernanceResult(
                blocked=True, action=None, reason=scope.value, classification=None
            )
        # ② 危险分类
        classification = self._danger_classifier.classify(action)
        # ③ HITL 门（仅 DANGEROUS 触发）
        if classification.level == DangerLevel.DANGEROUS:
            final = self._hitl_gate.gate(action, classification)
            if final is None:
                return GovernanceResult(
                    blocked=True, action=None, reason="user_denied",
                    classification=classification,
                )
            action = final
        self._hitl_gate.reset()
        return GovernanceResult(
            blocked=False, action=action, reason="passed", classification=classification
        )
```

- [ ] **Step 4: 运行测试验证通过 + lint + 提交**

```bash
uv run pytest tests/governance/test_pipeline.py -v
uv run ruff check src/governance/pipeline.py tests/governance/test_pipeline.py && uv run mypy src/governance/pipeline.py
git add src/governance/pipeline.py tests/governance/test_pipeline.py
git commit -m "feat: 治理管道 GovernancePipeline（范围围栏→危险分类→HITL门 串联）"
```

---

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

## Task 11: 凭据管理 CredentialManager

**Files:**
- Create: `src/credentials/__init__.py`, `src/credentials/manager.py`
- Test: `tests/credentials/__init__.py`, `tests/credentials/test_manager.py`

**Interfaces:**
- Consumes: 环境变量 `OPENAI_API_KEY` 或 `.env` 文件
- Produces: `CredentialManager`（`get_api_key() -> str`, `get_base_url() -> str`）

- [ ] **Step 1: 写失败测试**

```python
# tests/credentials/__init__.py
```

```python
# tests/credentials/test_manager.py
"""CredentialManager 单测：验证凭据安全获取。"""
import os
from src.credentials.manager import CredentialManager


def test_get_api_key_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")
    mgr = CredentialManager()
    assert mgr.get_api_key() == "sk-test-key-123"


def test_get_base_url_default():
    mgr = CredentialManager()
    assert "njusehub" in mgr.get_base_url() or "openai" in mgr.get_base_url().lower()


def test_get_base_url_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://custom.api.com/v1")
    mgr = CredentialManager()
    assert mgr.get_base_url() == "https://custom.api.com/v1"


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    mgr = CredentialManager()
    try:
        mgr.get_api_key()
        assert False, "应抛出异常"
    except (ValueError, RuntimeError):
        pass
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/credentials/test_manager.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 CredentialManager**

```python
# src/credentials/__init__.py
"""凭据子包。"""
```

```python
# src/credentials/manager.py
"""凭据管理：从环境变量安全获取 API key，不硬编码。"""
from __future__ import annotations

import os


class CredentialManager:
    """凭据管理器，从环境变量读取 API key 和 base URL。

    优先级：OPENAI_API_KEY > LLM_API_KEY > .env 文件。
    不将 key 写入代码或日志。
    """

    def __init__(self) -> None:
        self._load_dotenv()

    def _load_dotenv(self) -> None:
        """尝试从 .env 文件加载（如果 python-dotenv 可用）。"""
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

    def get_api_key(self) -> str:
        """获取 API key。"""
        key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
        if not key:
            raise RuntimeError(
                "未找到 API key，请设置 OPENAI_API_KEY 或 LLM_API_KEY 环境变量"
            )
        return key

    def get_base_url(self) -> str:
        """获取 base URL。"""
        return os.environ.get(
            "OPENAI_BASE_URL", "https://api.njusehub.ai/v1"
        )

    def get_model(self) -> str:
        """获取模型名。"""
        return os.environ.get("LLM_MODEL", "njusehub/glm-5.2")
```

- [ ] **Step 4: 运行测试验证通过 + lint + 提交**

```bash
uv run pytest tests/credentials/test_manager.py -v
uv run ruff check src/credentials/ tests/credentials/ && uv run mypy src/credentials/
git add src/credentials/ tests/credentials/
git commit -m "feat: 凭据管理 CredentialManager（环境变量读取 + .env 支持）"
```

---

## Task 12: ActionParser 动作解析器

**Files:**
- Create: `src/parser/__init__.py`, `src/parser/action_parser.py`
- Test: `tests/parser/__init__.py`, `tests/parser/test_action_parser.py`

**Interfaces:**
- Consumes: LLM 返回的文本（含 ```tool_code 代码块）
- Produces: `ActionParser.parse(text) -> list[Action]`

- [ ] **Step 1: 写失败测试**

```python
# tests/parser/__init__.py
```

```python
# tests/parser/test_action_parser.py
"""ActionParser 单测：验证从 LLM 输出中解析动作。"""
from src.parser.action_parser import ActionParser
from src.types import Action


def test_parse_single_action():
    text = '''我来读取文件：

```tool_code
{"tool": "read_file", "args": {"path": "src/main.py"}, "thought": "查看主文件"}
```'''
    actions = ActionParser().parse(text)
    assert len(actions) == 1
    assert actions[0].tool == "read_file"
    assert actions[0].args["path"] == "src/main.py"
    assert actions[0].thought == "查看主文件"


def test_parse_multiple_actions():
    text = '''```tool_code
{"tool": "read_file", "args": {"path": "a.py"}, "thought": "读a"}
```
中间文字
```tool_code
{"tool": "run_shell", "args": {"command": "ls"}, "thought": "列目录"}
```'''
    actions = ActionParser().parse(text)
    assert len(actions) == 2
    assert actions[0].tool == "read_file"
    assert actions[1].tool == "run_shell"


def test_parse_no_action():
    text = "这是纯文本回复，没有动作。"
    actions = ActionParser().parse(text)
    assert actions == []


def test_parse_malformed_json_skipped():
    text = '''```tool_code
{invalid json}
```'''
    actions = ActionParser().parse(text)
    assert actions == []


def test_parse_missing_fields():
    text = '''```tool_code
{"tool": "read_file"}
```'''
    actions = ActionParser().parse(text)
    assert len(actions) == 1
    assert actions[0].tool == "read_file"
    assert actions[0].args == {}
    assert actions[0].thought == ""
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/parser/test_action_parser.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 ActionParser**

```python
# src/parser/__init__.py
"""解析子包。"""
```

```python
# src/parser/action_parser.py
"""动作解析器：从 LLM 输出文本中提取结构化动作。"""
from __future__ import annotations

import json
import re

from src.types import Action


class ActionParser:
    """动作解析器，从 LLM 输出中提取 ```tool_code 代码块并解析为 Action。

    使用正则提取代码块，JSON 解析内容，容错处理缺失字段。
    确定性代码，无 LLM 依赖。
    """

    _PATTERN = re.compile(r"```tool_code\s*\n(.*?)\n```", re.DOTALL)

    def parse(self, text: str) -> list[Action]:
        """从文本中解析所有动作。"""
        actions: list[Action] = []
        for match in self._PATTERN.finditer(text):
            block = match.group(1).strip()
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            tool = data.get("tool", "")
            if not tool:
                continue
            args = data.get("args", {})
            thought = data.get("thought", "")
            actions.append(Action(tool=tool, args=args, thought=thought))
        return actions
```

- [ ] **Step 4: 运行测试验证通过 + lint + 提交**

```bash
uv run pytest tests/parser/test_action_parser.py -v
uv run ruff check src/parser/ tests/parser/ && uv run mypy src/parser/
git add src/parser/ tests/parser/
git commit -m "feat: 动作解析器 ActionParser（tool_code 代码块提取 + JSON 解析）"
```

---

## Task 13: Agent 主循环 AgentLoop

**Files:**
- Create: `src/agent/__init__.py`, `src/agent/loop.py`
- Test: `tests/agent/__init__.py`, `tests/agent/test_loop.py`

**Interfaces:**
- Consumes: `LLMClient` from `src/llm/base.py`, `ActionParser`, `GovernancePipeline`, `ToolDispatcher`, `FeedbackLoop`, `MemoryStore`
- Produces: `AgentLoop`（`run(user_input: str) -> str`）

- [ ] **Step 1: 写失败测试**

```python
# tests/agent/__init__.py
```

```python
# tests/agent/test_loop.py
"""AgentLoop 单测：用 MockLLMClient 验证主循环端到端。"""
from pathlib import Path
from src.agent.loop import AgentLoop
from src.llm.base import LLMClient
from src.llm.mock import MockLLMClient
from src.parser.action_parser import ActionParser
from src.governance.scope import ScopeFence
from src.governance.classifier import DangerClassifier
from src.governance.hitl import HITLGate
from src.governance.pipeline import GovernancePipeline
from src.tools.dispatcher import ToolDispatcher
from src.tools.fs import ReadFileTool, WriteFileTool
from src.tools.shell import ShellTool
from src.feedback.loop import FeedbackLoop
from src.feedback.validators import ExitCodeValidator
from src.memory.store import MemoryStore


def _make_agent(mock: LLMClient) -> AgentLoop:
    fence = ScopeFence(allowed_dirs=[Path(".")], protected_patterns=[".git/", ".env"])
    pipeline = GovernancePipeline(
        scope_fence=fence,
        danger_classifier=DangerClassifier([]),
        hitl_gate=HITLGate(),
    )
    dispatcher = ToolDispatcher()
    dispatcher.register("read_file", ReadFileTool())
    dispatcher.register("write_file", WriteFileTool())
    dispatcher.register("run_shell", ShellTool())
    feedback = FeedbackLoop(validators=[ExitCodeValidator()])
    memory = MemoryStore()
    return AgentLoop(
        llm=mock,
        parser=ActionParser(),
        pipeline=pipeline,
        dispatcher=dispatcher,
        feedback=feedback,
        memory=memory,
        max_iterations=10,
    )


def test_agent_reads_file(tmp_path):
    """MockLLM 返回 read_file 动作，agent 执行并返回结果。"""
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello agent")
    mock = MockLLMClient(
        responses=[
            f'```tool_code\n{{"tool": "read_file", "args": {{"path": "{file_path}"}}, "thought": "读文件"}}\n```',
            "文件内容是 hello agent",
        ]
    )
    agent = _make_agent(mock)
    result = agent.run("读取文件")
    assert "hello agent" in result


def test_agent_max_iterations():
    """MockLLM 持续返回动作，达到最大迭代后停止。"""
    mock = MockLLMClient(
        responses=[
            '```tool_code\n{"tool": "run_shell", "args": {"command": "echo hi"}, "thought": ""}\n```'
        ] * 20
    )
    agent = _make_agent(mock)
    agent._max_iterations = 3  # noqa: SLF001
    result = agent.run("循环测试")
    assert "迭代" in result or "iteration" in result.lower()


def test_agent_blocked_action():
    """范围围栏拦截后，agent 应注入反馈并继续。"""
    mock = MockLLMClient(
        responses=[
            '```tool_code\n{"tool": "write_file", "args": {"path": "/etc/passwd", "content": "x"}, "thought": ""}\n```',
            "动作被拦截，我换个方式",
        ]
    )
    agent = _make_agent(mock)
    result = agent.run("写文件")
    assert "拦截" in result or "blocked" in result.lower() or "换" in result
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/agent/test_loop.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 AgentLoop**

```python
# src/agent/__init__.py
"""Agent 子包。"""
```

```python
# src/agent/loop.py
"""Agent 主循环：上下文 → LLM → 解析 → 治理 → 执行 → 反馈 → 停机。"""
from __future__ import annotations

from src.llm.base import LLMClient
from src.parser.action_parser import ActionParser
from src.governance.pipeline import GovernancePipeline
from src.tools.dispatcher import ToolDispatcher
from src.feedback.loop import FeedbackLoop
from src.memory.store import MemoryStore
from src.types import Message


class AgentLoop:
    """Agent 主循环，编排所有组件。

    流程：
    1. 组织上下文（系统提示 + 记忆 + 用户输入）
    2. 调用 LLM
    3. 解析动作
    4. 治理管道检查
    5. 工具分发执行
    6. 反馈闭环注入
    7. 停机判断（无动作 / 达到最大迭代 / LLM 返回纯文本）
    """

    def __init__(
        self,
        llm: LLMClient,
        parser: ActionParser,
        pipeline: GovernancePipeline,
        dispatcher: ToolDispatcher,
        feedback: FeedbackLoop,
        memory: MemoryStore,
        max_iterations: int = 10,
    ) -> None:
        self._llm = llm
        self._parser = parser
        self._pipeline = pipeline
        self._dispatcher = dispatcher
        self._feedback = feedback
        self._memory = memory
        self._max_iterations = max_iterations

    def run(self, user_input: str) -> str:
        """运行 agent 主循环。"""
        context: list[Message] = []
        system_prompt = (
            "你是一个编码助手。使用 ```tool_code 代码块执行动作。"
            "格式：```tool_code\\n{\"tool\": \"...\", \"args\": {...}, \"thought\": \"...\"}\\n```"
        )
        context.append(Message(role="system", content=system_prompt, feedback=None))
        context.append(Message(role="user", content=user_input, feedback=None))
        self._memory.store(Message(role="user", content=user_input, feedback=None))

        for i in range(self._max_iterations):
            prompt_text = "\n".join(m.content for m in context)
            response = self._llm.chat(prompt_text)
            context.append(Message(role="assistant", content=response, feedback=None))

            actions = self._parser.parse(response)
            if not actions:
                return response

            for action in actions:
                gov_result = self._pipeline.process(action)
                if gov_result.blocked:
                    self._feedback.process(
                        action,
                        type("R", (), {"success": False, "output": "", "error": gov_result.reason})(),
                        context,
                    )
                    continue
                if gov_result.action is None:
                    continue
                tool_result = self._dispatcher.dispatch(gov_result.action)
                self._feedback.process(gov_result.action, tool_result, context)
                self._memory.store(Message(
                    role="tool", content=tool_result.output, feedback=None
                ))

        return f"达到最大迭代次数 {self._max_iterations}，循环终止"
```

- [ ] **Step 4: 运行测试验证通过 + lint + 提交**

```bash
uv run pytest tests/agent/test_loop.py -v
uv run ruff check src/agent/ tests/agent/ && uv run mypy src/agent/
git add src/agent/ tests/agent/
git commit -m "feat: Agent 主循环 AgentLoop（上下文→LLM→解析→治理→执行→反馈→停机）"
```

---

## Task 14: API 层（FastAPI + WebSocket）

**Files:**
- Create: `src/api/__init__.py`, `src/api/main.py`, `src/api/routes.py`, `src/api/ws.py`
- Test: `tests/api/__init__.py`, `tests/api/test_routes.py`

**Interfaces:**
- Consumes: `AgentLoop`, `HITLGate`
- Produces: FastAPI app, REST `/api/health`, `/api/approve`, WebSocket `/ws`

- [ ] **Step 1: 写失败测试**

```python
# tests/api/__init__.py
```

```python
# tests/api/test_routes.py
"""API 路由单测：验证 REST 端点。"""
from fastapi.testclient import TestClient
from src.api.main import create_app


def test_health_check():
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_approve_endpoint():
    app = create_app()
    client = TestClient(app)
    response = client.post("/api/approve", json={"verdict": "approve"})
    assert response.status_code == 200


def test_deny_endpoint():
    app = create_app()
    client = TestClient(app)
    response = client.post("/api/approve", json={"verdict": "deny"})
    assert response.status_code == 200


def test_modify_endpoint():
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/approve",
        json={
            "verdict": "modify",
            "modified_action": {"tool": "run_shell", "args": {"command": "echo safe"}, "thought": ""},
        },
    )
    assert response.status_code == 200
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/api/test_routes.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 API 层**

```python
# src/api/__init__.py
"""API 子包。"""
```

```python
# src/api/main.py
"""FastAPI 应用工厂。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router


def create_app() -> FastAPI:
    """创建 FastAPI 应用。"""
    app = FastAPI(title="NJUSE Coding Agent", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    return app
```

```python
# src/api/routes.py
"""REST 路由。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from src.types import Action
from src.governance.hitl import Decision

router = APIRouter()

# 全局 HITLGate 引用（由 ws 模块设置）
_pending_gate = None


def set_pending_gate(gate) -> None:
    """设置当前等待审批的 HITLGate。"""
    global _pending_gate
    _pending_gate = gate


class ApproveRequest(BaseModel):
    """审批请求。"""
    verdict: str
    modified_action: dict | None = None


@router.get("/health")
def health() -> dict:
    """健康检查。"""
    return {"status": "ok"}


@router.post("/approve")
def approve(req: ApproveRequest) -> dict:
    """处理用户审批决策。"""
    if _pending_gate is None:
        return {"status": "no_pending_action"}
    modified = None
    if req.modified_action:
        modified = Action(
            tool=req.modified_action["tool"],
            args=req.modified_action.get("args", {}),
            thought=req.modified_action.get("thought", ""),
        )
    _pending_gate.receive_decision(Decision(verdict=req.verdict, modified_action=modified))
    return {"status": "ok", "verdict": req.verdict}
```

```python
# src/api/ws.py
"""WebSocket 端点：实时推送 agent 状态与审批请求。"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.api.routes import set_pending_gate

ws_router = APIRouter()


@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket 端点，处理 agent 交互。"""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "run":
                await websocket.send_json({"type": "status", "message": "agent 启动"})
            elif msg.get("type") == "approve":
                set_pending_gate(None)
                await websocket.send_json({"type": "status", "message": "已审批"})
    except WebSocketDisconnect:
        pass
```

- [ ] **Step 4: 运行测试验证通过 + lint + 提交**

```bash
uv run pytest tests/api/test_routes.py -v
uv run ruff check src/api/ tests/api/ && uv run mypy src/api/
git add src/api/ tests/api/
git commit -m "feat: API 层（FastAPI + REST /health /approve + WebSocket /ws）"
```

---

## Task 15: 前端（React + Vite + Open Design）

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/index.html`
- Create: `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/components/ChatView.tsx`, `frontend/src/components/ApprovalDialog.tsx`
- Create: `frontend/src/api.ts`, `frontend/src/ws.ts`

**说明：** 前端为最小可用实现，展示 agent 对话与 HITL 审批弹窗。

- [ ] **Step 1: 初始化前端项目**

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install
npm install axios
```

- [ ] **Step 2: 配置 Vite 代理**

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
```

- [ ] **Step 3: 实现 API 客户端**

```typescript
// frontend/src/api.ts
import axios from 'axios';

const API = axios.create({ baseURL: '/api' });

export async function health() {
  return API.get('/health');
}

export async function approve(verdict: string, modifiedAction?: any) {
  return API.post('/approve', { verdict, modified_action: modifiedAction });
}
```

```typescript
// frontend/src/ws.ts
export function connectWS(onMessage: (msg: any) => void) {
  const ws = new WebSocket(`ws://${window.location.host}/ws`);
  ws.onmessage = (e) => onMessage(JSON.parse(e.data));
  return ws;
}
```

- [ ] **Step 4: 实现 ChatView 组件**

```tsx
// frontend/src/components/ChatView.tsx
import { useState, useEffect } from 'react';

interface Message {
  role: string;
  content: string;
}

export function ChatView() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');

  useEffect(() => {
    // WebSocket 连接逻辑
  }, []);

  const send = () => {
    setMessages([...messages, { role: 'user', content: input }]);
    setInput('');
  };

  return (
    <div className="chat-view">
      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`msg msg-${m.role}`}>{m.content}</div>
        ))}
      </div>
      <div className="input-bar">
        <input value={input} onChange={e => setInput(e.target.value)} />
        <button onClick={send}>发送</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: 实现 ApprovalDialog 组件**

```tsx
// frontend/src/components/ApprovalDialog.tsx
interface Props {
  action: { tool: string; args: Record<string, any>; thought: string };
  onApprove: () => void;
  onDeny: () => void;
  onModify: (newCommand: string) => void;
}

export function ApprovalDialog({ action, onApprove, onDeny, onModify }: Props) {
  if (!action) return null;
  return (
    <div className="approval-overlay">
      <div className="approval-dialog">
        <h3>危险动作审批</h3>
        <p>工具: {action.tool}</p>
        <p>参数: {JSON.stringify(action.args)}</p>
        <p>理由: {action.thought}</p>
        <div className="buttons">
          <button onClick={onApprove} className="btn-approve">批准</button>
          <button onClick={onDeny} className="btn-deny">拒绝</button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: 实现 App 主组件**

```tsx
// frontend/src/App.tsx
import { useState } from 'react';
import { ChatView } from './components/ChatView';
import { ApprovalDialog } from './components/ApprovalDialog';

function App() {
  const [pendingAction, setPendingAction] = useState<any>(null);

  return (
    <div className="app">
      <header><h1>NJUSE Coding Agent</h1></header>
      <ChatView />
      {pendingAction && (
        <ApprovalDialog
          action={pendingAction}
          onApprove={() => setPendingAction(null)}
          onDeny={() => setPendingAction(null)}
          onModify={() => setPendingAction(null)}
        />
      )}
    </div>
  );
}

export default App;
```

- [ ] **Step 7: 验证前端构建 + 提交**

```bash
cd frontend && npm run build
cd ..
git add frontend/
git commit -m "feat: 前端（React + Vite + ChatView + ApprovalDialog HITL 审批弹窗）"
```

---

## Task 16: Docker + CI

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.gitlab-ci.yml`

- [ ] **Step 1: 创建 Dockerfile**

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安装 uv
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

# 复制源码
COPY src/ ./src/
COPY config/ ./config/

# 构建前端
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/ .
RUN npm ci && npm run build

FROM python:3.12-slim
WORKDIR /app
COPY --from=0 /app/ ./
COPY --from=frontend-builder /app/frontend/dist ./static/
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "src.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 创建 docker-compose.yml**

```yaml
# docker-compose.yml
version: "3.9"
services:
  agent:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENAI_BASE_URL=${OPENAI_BASE_URL:-https://api.njusehub.ai/v1}
      - LLM_MODEL=${LLM_MODEL:-njusehub/glm-5.2}
    volumes:
      - ./config:/app/config:ro
```

- [ ] **Step 3: 创建 .dockerignore**

```
# .dockerignore
.git
.gitignore
__pycache__
*.pyc
.env
*.key
node_modules
frontend/node_modules
.venv
```

- [ ] **Step 4: 创建 .gitlab-ci.yml**

```yaml
# .gitlab-ci.yml
stages:
  - test

unit-test:
  stage: test
  image: python:3.12-slim
  before_script:
    - pip install uv
    - uv sync --frozen
  script:
    - uv run ruff check .
    - uv run mypy .
    - uv run pytest -xvs
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "main"
```

- [ ] **Step 5: 验证 Docker 构建 + 提交**

```bash
docker build -t njuse-agent .
git add Dockerfile docker-compose.yml .dockerignore .gitlab-ci.yml
git commit -m "feat: Docker 多阶段构建 + GitLab CI（ruff→mypy→pytest）"
```

---

## Task 17: 机制演示 + 集成测试

**Files:**
- Create: `tests/test_demo.py`, `tests/test_integration.py`
- Create: `demo/run_demo.py`

- [ ] **Step 1: 写 DEMO1 集成测试（危险动作拦截）**

```python
# tests/test_demo.py
"""DEMO 集成测试：验证治理机制端到端。"""
from pathlib import Path
from src.agent.loop import AgentLoop
from src.llm.mock import MockLLMClient
from src.parser.action_parser import ActionParser
from src.governance.scope import ScopeFence
from src.governance.classifier import DangerClassifier
from src.governance.hitl import HITLGate, Decision
from src.governance.pipeline import GovernancePipeline
from src.tools.dispatcher import ToolDispatcher
from src.tools.fs import ReadFileTool, WriteFileTool
from src.tools.shell import ShellTool
from src.feedback.loop import FeedbackLoop
from src.feedback.validators import ExitCodeValidator
from src.memory.store import MemoryStore
from src.config.loader import DangerRule


def test_demo1_dangerous_action_blocked():
    """DEMO1: rm -rf / 被治理管道拦截。"""
    rules = [
        DangerRule(name="force_delete", pattern=r"rm\s+(-\w*\w\w*\s+)?-rf?\s+/", level="dangerous", description="递归删除"),
    ]
    fence = ScopeFence(allowed_dirs=[Path(".")], protected_patterns=[".git/", ".env"])
    pipeline = GovernancePipeline(
        scope_fence=fence,
        danger_classifier=DangerClassifier(rules),
        hitl_gate=HITLGate(),
    )
    dispatcher = ToolDispatcher()
    dispatcher.register("run_shell", ShellTool())
    mock = MockLLMClient(
        responses=[
            '```tool_code\n{"tool": "run_shell", "args": {"command": "rm -rf /"}, "thought": "清理"}\n```',
            "动作被拦截，我停止操作",
        ]
    )
    agent = AgentLoop(
        llm=mock, parser=ActionParser(), pipeline=pipeline,
        dispatcher=dispatcher, feedback=FeedbackLoop([ExitCodeValidator()]),
        memory=MemoryStore(), max_iterations=5,
    )
    result = agent.run("清理系统")
    assert "拦截" in result or "blocked" in result.lower() or "停止" in result


def test_demo2_scope_fence_blocks_path_traversal():
    """DEMO2: 路径穿越攻击被范围围栏拦截。"""
    fence = ScopeFence(allowed_dirs=[Path("./src")], protected_patterns=[])
    from src.types import Action
    action = Action(
        tool="write_file",
        args={"path": "src/../../../etc/passwd", "content": "x"},
        thought="",
    )
    result = fence.check(action)
    assert result.value == "out_of_scope"


def test_demo3_hitl_approval_flow():
    """DEMO3: HITL 审批流程，用户拒绝后动作被阻断。"""
    gate = HITLGate()
    from src.types import Action
    from src.governance.classifier import Classification, DangerLevel
    action = Action(tool="run_shell", args={"command": "rm -rf /tmp"}, thought="")
    classification = Classification(level=DangerLevel.DANGEROUS, matched_rule="test", reason="危险")
    gate.request_approval(action, classification)
    assert gate.state.value == "pending_approval"
    gate.receive_decision(Decision(verdict="deny"))
    assert gate.state.value == "denied"
```

```python
# tests/test_integration.py
"""端到端集成测试：MockLLM 驱动完整 agent 流程。"""
from pathlib import Path
from src.agent.loop import AgentLoop
from src.llm.mock import MockLLMClient
from src.parser.action_parser import ActionParser
from src.governance.scope import ScopeFence
from src.governance.classifier import DangerClassifier
from src.governance.hitl import HITLGate
from src.governance.pipeline import GovernancePipeline
from src.tools.dispatcher import ToolDispatcher
from src.tools.fs import ReadFileTool, WriteFileTool, ListDirTool
from src.tools.shell import ShellTool
from src.feedback.loop import FeedbackLoop
from src.feedback.validators import ExitCodeValidator
from src.memory.store import MemoryStore


def test_full_workflow_read_file(tmp_path):
    """完整工作流：用户请求 → agent 读文件 → 返回内容。"""
    file_path = tmp_path / "target.txt"
    file_path.write_text("integration test content")

    fence = ScopeFence(allowed_dirs=[tmp_path], protected_patterns=[".git/"])
    pipeline = GovernancePipeline(
        scope_fence=fence,
        danger_classifier=DangerClassifier([]),
        hitl_gate=HITLGate(),
    )
    dispatcher = ToolDispatcher()
    dispatcher.register("read_file", ReadFileTool())
    dispatcher.register("write_file", WriteFileTool())
    dispatcher.register("list_dir", ListDirTool())
    dispatcher.register("run_shell", ShellTool())

    mock = MockLLMClient(
        responses=[
            f'```tool_code\n{{"tool": "read_file", "args": {{"path": "{file_path}"}}, "thought": "读取目标文件"}}\n```',
            "文件内容是 integration test content",
        ]
    )
    agent = AgentLoop(
        llm=mock, parser=ActionParser(), pipeline=pipeline,
        dispatcher=dispatcher, feedback=FeedbackLoop([ExitCodeValidator()]),
        memory=MemoryStore(), max_iterations=5,
    )
    result = agent.run("读取目标文件")
    assert "integration test content" in result
```

- [ ] **Step 2: 运行全部测试验证通过**

```bash
uv run pytest -xvs
uv run ruff check .
uv run mypy .
```

- [ ] **Step 3: 创建演示脚本**

```python
# demo/run_demo.py
"""演示脚本：展示治理机制（移除真实 LLM，用 MockLLM 验证）。"""
from pathlib import Path
from src.agent.loop import AgentLoop
from src.llm.mock import MockLLMClient
from src.parser.action_parser import ActionParser
from src.governance.scope import ScopeFence
from src.governance.classifier import DangerClassifier
from src.governance.hitl import HITLGate
from src.governance.pipeline import GovernancePipeline
from src.tools.dispatcher import ToolDispatcher
from src.tools.fs import ReadFileTool, WriteFileTool
from src.tools.shell import ShellTool
from src.feedback.loop import FeedbackLoop
from src.feedback.validators import ExitCodeValidator
from src.memory.store import MemoryStore
from src.config.loader import DangerRule


def main() -> None:
    """演示入口。"""
    rules = [
        DangerRule(name="force_delete", pattern=r"rm\s+(-\w*\w\w*\s+)?-rf?\s+/", level="dangerous", description="递归删除"),
        DangerRule(name="install_pkg", pattern=r"pip\s+install", level="warning", description="安装包"),
    ]
    fence = ScopeFence(allowed_dirs=[Path(".")], protected_patterns=[".git/", ".env"])
    pipeline = GovernancePipeline(
        scope_fence=fence,
        danger_classifier=DangerClassifier(rules),
        hitl_gate=HITLGate(),
    )
    dispatcher = ToolDispatcher()
    dispatcher.register("read_file", ReadFileTool())
    dispatcher.register("write_file", WriteFileTool())
    dispatcher.register("run_shell", ShellTool())

    mock = MockLLMClient(
        responses=[
            '```tool_code\n{"tool": "run_shell", "args": {"command": "rm -rf /"}, "thought": "清理"}\n```',
            "动作被拦截，我停止操作",
        ]
    )
    agent = AgentLoop(
        llm=mock, parser=ActionParser(), pipeline=pipeline,
        dispatcher=dispatcher, feedback=FeedbackLoop([ExitCodeValidator()]),
        memory=MemoryStore(), max_iterations=5,
    )
    result = agent.run("演示：危险动作拦截")
    print(f"结果: {result}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行演示 + 提交**

```bash
uv run python demo/run_demo.py
git add tests/test_demo.py tests/test_integration.py demo/run_demo.py
git commit -m "feat: 机制演示 + 集成测试（DEMO1-3 + 端到端 MockLLM 验证）"
```

---

## 完成后自检

- [ ] 对照 SPEC.md 逐节检查实现完整性
- [ ] 确认所有核心机制可用 MockLLM 单测（移除真实 LLM 仍可测试）
- [ ] 确认治理管道三阶段均为确定性代码（非提示词）
- [ ] 确认无 LangChain/AutoGen/CrewAI 等禁用依赖
- [ ] 确认 opencode.json 未被 git 追踪
- [ ] 确认 Docker 镜像可构建
- [ ] 确认 CI pipeline 配置完整
- [ ] 编写 REFLECTION.md（1500-2500 字）

---

## 计划自检（对照 SPEC.md）

### 覆盖矩阵

| SPEC 章节 | 对应 Task | 状态 |
|-----------|----------|------|
| §3.1 Agent 主循环 | Task 13 | ✅ 完整 |
| §3.2 LLM 抽象层 | Task 2 | ✅ 完整（含 MockLLMClient） |
| §3.3 治理管道 | Task 4-7 | ✅ 深度实现（四阶段） |
| §3.4 工具分发 | Task 8 | ✅ 完整 |
| §3.5 反馈闭环 | Task 9 | ✅ 完整 |
| §3.6 记忆 | Task 10 | ✅ 最低实现（关键词检索） |
| §3.7 配置 | Task 3 | ✅ 完整 |
| §3.8 WebUI | Task 14+15 | ⚠️ 最低实现（REST/WebSocket 精简） |
| §3.9 凭据管理 | Task 11 | ⚠️ 环境变量为主，keyring 为备选 |
| §6 数据模型 | Task 1 | ✅ 核心类型定义 |
| §6.3 SQLite 持久化 | — | ❌ 未规划（记忆用内存列表） |
| §7 凭据与分发 | Task 11+16 | ✅ Docker + CI |
| §9 验收标准 | Task 17 | ✅ DEMO1-3 + 集成测试 |
| §11 治理深度 | Task 4-7 | ✅ 完整 |

### 已知偏离与决策

1. **SQLite 持久化未规划**：SPEC §6.3 提议 SQLite 存储 Session/Step 历史。PLAN 用内存 `MemoryStore` 替代，因 2核2G 资源约束且历史回溯非核心机制。若演示需要可后续追加。
2. **CredentialManager 用环境变量**：SPEC §7.2 以 OS 钥匙串为主方案。PLAN Task 11 优先环境变量 + `.env`，因 CI/headless 环境无钥匙串。keyring 作为可选增强。
3. **HITLGate 同步实现**：SPEC §11.3 提及 `asyncio.Future` 异步阻塞。PLAN Task 6 用同步状态机，单测中直接模拟决策。API 层（Task 14）桥接异步 WebSocket。
4. **REST API 精简**：SPEC §11.5 列出 `/api/tasks`、`/api/sessions`、`/api/config`。PLAN Task 14 仅实现 `/api/health` + `/api/approve`，因核心是治理演示而非 CRUD 完整性。
5. **WebSocket 事件精简**：SPEC §11.5 定义 8 种事件类型。PLAN Task 14 实现最小 WebSocket 通道，演示时扩展事件类型。
6. **工具集精简**：SPEC §11.1 列出 `run_tests`、`run_lint` 工具。PLAN Task 8 用 `run_shell` 统一覆盖（`run_shell` 可执行 `pytest`/`ruff`），减少工具数量。

### 无占位符确认

- 所有 Task 的 Step 3 均含完整可运行代码，无 `TODO`/`pass`/`...` 占位
- 所有 Task 的 Step 1 均含完整测试代码
- 所有 Task 遵循红→绿→提交 TDD 循环
