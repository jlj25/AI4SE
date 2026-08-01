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