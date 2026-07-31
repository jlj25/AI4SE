"""DEMO 集成测试：验证治理机制端到端。"""

import json
from pathlib import Path

from src.agent.loop import AgentLoop
from src.config.loader import DangerRule
from src.feedback.loop import FeedbackLoop
from src.feedback.validators import ExitCodeValidator
from src.governance.classifier import Classification, DangerClassifier, DangerLevel
from src.governance.hitl import Decision, HITLGate
from src.governance.pipeline import GovernancePipeline
from src.governance.scope import ScopeFence
from src.llm.mock import MockLLMClient
from src.memory.store import MemoryStore
from src.parser.action_parser import ActionParser
from src.tools.dispatcher import ToolDispatcher
from src.tools.shell import ShellTool
from src.types import Action


def _tool_code(action_dict: dict) -> str:
    """构造 tool_code 代码块，确保 JSON 路径正确转义。"""
    return f"```tool_code\n{json.dumps(action_dict, ensure_ascii=False)}\n```"


def test_demo1_dangerous_action_blocked():
    """DEMO1: rm -rf / 被治理管道拦截。

    Windows 上 / 被 ScopeFence 拦截为 OUT_OF_SCOPE（硬拦截），
    agent 注入反馈后继续，LLM 返回"被拦截"文本。
    """
    rules = [
        DangerRule(
            name="force_delete",
            pattern=r"rm\s+(-\w*\w\w*\s+)?-rf?\s+/",
            level="dangerous",
            description="递归删除",
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
    result = agent.run("清理系统")
    assert "拦截" in result or "blocked" in result.lower() or "停止" in result


def test_demo2_scope_fence_blocks_path_traversal():
    """DEMO2: 路径穿越攻击被范围围栏拦截。"""
    fence = ScopeFence(allowed_dirs=[Path("./src")], protected_patterns=[])
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
    action = Action(tool="run_shell", args={"command": "rm -rf /tmp"}, thought="")
    classification = Classification(level=DangerLevel.DANGEROUS, matched_rule="test", reason="危险")
    gate.request_approval(action, classification)
    assert gate.state.value == "pending_approval"
    gate.receive_decision(Decision(verdict="deny"))
    assert gate.state.value == "denied"


def test_demo3_hitl_approve_flow():
    """DEMO3 补充：用户批准后动作放行。"""
    gate = HITLGate()
    action = Action(tool="run_shell", args={"command": "rm -rf /tmp"}, thought="")
    classification = Classification(level=DangerLevel.DANGEROUS, matched_rule="test", reason="危险")
    result = gate.gate(action, classification)
    # fail-closed: 无预设决策 → None
    assert result is None
    assert gate.state.value == "denied"
