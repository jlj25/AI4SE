"""演示脚本：展示治理机制（移除真实 LLM，用 MockLLM 验证）。

运行：uv run python demo/run_demo.py
"""

import json
from pathlib import Path

from src.agent.loop import AgentLoop
from src.config.loader import DangerRule
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
    """构造 tool_code 代码块。"""
    return f"```tool_code\n{json.dumps(action_dict, ensure_ascii=False)}\n```"


def main() -> None:
    """演示入口：展示治理管道拦截危险动作。"""
    rules = [
        DangerRule(
            name="force_delete",
            pattern=r"rm\s+(-\w*\w\w*\s+)?-rf?\s+/",
            level="dangerous",
            description="递归删除",
        ),
        DangerRule(
            name="install_pkg",
            pattern=r"pip\s+install",
            level="warning",
            description="安装包",
        ),
    ]
    fence = ScopeFence(
        allowed_dirs=[Path(".")],
        protected_patterns=[".git/", ".env"],
    )
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
        script=[
            _tool_code(
                {
                    "tool": "run_shell",
                    "args": {"command": "rm -rf /"},
                    "thought": "清理",
                }
            ),
            "动作被拦截，我停止操作",
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
    result = agent.run("演示：危险动作拦截")
    print(f"结果: {result}")


if __name__ == "__main__":
    main()
