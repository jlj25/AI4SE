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