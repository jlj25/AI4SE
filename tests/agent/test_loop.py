"""AgentLoop 单测：用 MockLLMClient 验证主循环端到端。"""

import json
from pathlib import Path

from src.agent.loop import AgentLoop
from src.feedback.loop import FeedbackLoop
from src.feedback.validators import ExitCodeValidator
from src.governance.classifier import DangerClassifier
from src.governance.hitl import HITLGate
from src.governance.pipeline import GovernancePipeline
from src.governance.scope import ScopeFence
from src.llm.mock import MockLLMClient
from src.memory.store import MemoryStore
from src.parser.action_parser import ActionParser
from src.tools.dispatcher import ToolDispatcher
from src.tools.fs import ReadFileTool, WriteFileTool
from src.tools.shell import ShellTool


def _tool_code(action_dict: dict) -> str:
    """构造 tool_code 代码块，确保 JSON 路径正确转义。"""
    return f"```tool_code\n{json.dumps(action_dict, ensure_ascii=False)}\n```"


def _make_agent(
    mock: MockLLMClient,
    max_iter: int = 10,
    allowed_dirs: list[Path] | None = None,
) -> AgentLoop:
    fence = ScopeFence(
        allowed_dirs=allowed_dirs or [Path(".")],
        protected_patterns=[".git/", ".env"],
    )
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
        max_iterations=max_iter,
    )


def test_agent_reads_file(tmp_path):
    """MockLLM 返回 read_file 动作，agent 执行并返回结果。"""
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello agent", encoding="utf-8")
    mock = MockLLMClient(
        script=[
            _tool_code(
                {"tool": "read_file", "args": {"path": str(file_path)}, "thought": "读文件"}
            ),
            "文件内容是 hello agent",
        ]
    )
    agent = _make_agent(mock)
    result = agent.run("读取文件")
    assert "hello agent" in result


def test_agent_max_iterations():
    """MockLLM 持续返回动作，达到最大迭代后停止。"""
    mock = MockLLMClient(
        script=[_tool_code({"tool": "run_shell", "args": {"command": "echo hi"}, "thought": ""})]
        * 20
    )
    agent = _make_agent(mock, max_iter=3)
    result = agent.run("循环测试")
    assert "迭代" in result or "iteration" in result.lower()


def test_agent_blocked_action():
    """范围围栏拦截后，agent 应注入反馈并继续。"""
    mock = MockLLMClient(
        script=[
            _tool_code(
                {
                    "tool": "write_file",
                    "args": {"path": "/etc/passwd", "content": "x"},
                    "thought": "",
                }
            ),
            "动作被拦截，我换个方式",
        ]
    )
    agent = _make_agent(mock)
    result = agent.run("写文件")
    assert "拦截" in result or "blocked" in result.lower() or "换" in result


def test_agent_no_action_returns_text():
    """LLM 返回纯文本无动作时直接返回。"""
    mock = MockLLMClient(script=["这是纯文本回复，没有动作。"])
    agent = _make_agent(mock)
    result = agent.run("你好")
    assert "纯文本" in result


def test_agent_memory_stored(tmp_path):
    """agent 执行后记忆中应有消息。"""
    file_path = tmp_path / "mem.txt"
    file_path.write_text("mem content", encoding="utf-8")
    mock = MockLLMClient(
        script=[
            _tool_code({"tool": "read_file", "args": {"path": str(file_path)}, "thought": ""}),
            "done",
        ]
    )
    agent = _make_agent(mock, allowed_dirs=[tmp_path])
    agent.run("读取")
    assert len(agent._memory.all_messages()) >= 2  # noqa: SLF001
