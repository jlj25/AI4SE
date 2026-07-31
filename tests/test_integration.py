"""端到端集成测试：MockLLM 驱动完整 agent 流程。"""

import json

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
from src.tools.fs import ListDirTool, ReadFileTool, WriteFileTool
from src.tools.shell import ShellTool


def _tool_code(action_dict: dict) -> str:
    """构造 tool_code 代码块，确保 JSON 路径正确转义。"""
    return f"```tool_code\n{json.dumps(action_dict, ensure_ascii=False)}\n```"


def test_full_workflow_read_file(tmp_path):
    """完整工作流：用户请求 → agent 读文件 → 返回内容。"""
    file_path = tmp_path / "target.txt"
    file_path.write_text("integration test content", encoding="utf-8")

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
        script=[
            _tool_code(
                {
                    "tool": "read_file",
                    "args": {"path": str(file_path)},
                    "thought": "读取目标文件",
                }
            ),
            "文件内容是 integration test content",
        ]
    )
    agent = AgentLoop(
        llm=mock,
        parser=ActionParser(),
        pipeline=pipeline,
        dispatcher=dispatcher,
        feedback=FeedbackLoop([ExitCodeValidator()]),
        memory=MemoryStore(),
        max_iterations=5,
    )
    result = agent.run("读取目标文件")
    assert "integration test content" in result


def test_full_workflow_write_then_list(tmp_path):
    """完整工作流：写文件 → 列目录 → 返回文件名。"""
    fence = ScopeFence(allowed_dirs=[tmp_path], protected_patterns=[".git/"])
    pipeline = GovernancePipeline(
        scope_fence=fence,
        danger_classifier=DangerClassifier([]),
        hitl_gate=HITLGate(),
    )
    dispatcher = ToolDispatcher()
    dispatcher.register("write_file", WriteFileTool())
    dispatcher.register("list_dir", ListDirTool())

    file_path = tmp_path / "created.txt"
    mock = MockLLMClient(
        script=[
            _tool_code(
                {
                    "tool": "write_file",
                    "args": {"path": str(file_path), "content": "hello"},
                    "thought": "写文件",
                }
            ),
            _tool_code(
                {
                    "tool": "list_dir",
                    "args": {"path": str(tmp_path)},
                    "thought": "列目录",
                }
            ),
            "目录中有 created.txt",
        ]
    )
    agent = AgentLoop(
        llm=mock,
        parser=ActionParser(),
        pipeline=pipeline,
        dispatcher=dispatcher,
        feedback=FeedbackLoop([ExitCodeValidator()]),
        memory=MemoryStore(),
        max_iterations=5,
    )
    result = agent.run("写文件并列目录")
    assert "created.txt" in result


def test_full_workflow_shell_echo(tmp_path):
    """完整工作流：执行 shell 命令。"""
    fence = ScopeFence(allowed_dirs=[tmp_path], protected_patterns=[".git/"])
    pipeline = GovernancePipeline(
        scope_fence=fence,
        danger_classifier=DangerClassifier([]),
        hitl_gate=HITLGate(),
    )
    dispatcher = ToolDispatcher()
    dispatcher.register("run_shell", ShellTool())

    mock = MockLLMClient(
        script=[
            _tool_code(
                {
                    "tool": "run_shell",
                    "args": {"command": "echo integration_test"},
                    "thought": "执行 echo",
                }
            ),
            "命令执行成功",
        ]
    )
    agent = AgentLoop(
        llm=mock,
        parser=ActionParser(),
        pipeline=pipeline,
        dispatcher=dispatcher,
        feedback=FeedbackLoop([ExitCodeValidator()]),
        memory=MemoryStore(),
        max_iterations=5,
    )
    result = agent.run("执行命令")
    assert "成功" in result
