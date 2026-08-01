"""演示脚本：在 MockLLM 下确定性地复现三大机制行为。

DEMO1: 治理护栏拦截危险动作（rm -rf /）
DEMO2: 反馈闭环使 agent 收到失败反馈并改变下一步动作
DEMO3: HITL 状态机——fail-closed 语义（重点维度确定性行为）

运行：uv run python demo/run_demo.py
无网络、无真实 LLM，全部由 MockLLMClient 脚本驱动。
"""

import json
from pathlib import Path

from src.agent.loop import AgentLoop
from src.config.loader import DangerRule
from src.feedback.loop import FeedbackLoop
from src.feedback.validators import ExitCodeValidator
from src.governance.classifier import Classification, DangerClassifier, DangerLevel
from src.governance.hitl import HITLGate
from src.governance.pipeline import GovernancePipeline
from src.governance.scope import ScopeFence
from src.llm.mock import MockLLMClient
from src.memory.store import MemoryStore
from src.parser.action_parser import ActionParser
from src.tools.dispatcher import ToolDispatcher
from src.tools.fs import WriteFileTool
from src.tools.shell import ShellTool
from src.types import Action

_DIVIDER = "=" * 60


def _tool_code(action_dict: dict) -> str:
    """构造 tool_code 代码块。"""
    return f"```tool_code\n{json.dumps(action_dict, ensure_ascii=False)}\n```"


def demo1_dangerous_action_blocked() -> None:
    """DEMO1: 治理护栏拦截 rm -rf /。"""
    print(_DIVIDER)
    print("DEMO1: 治理护栏拦截危险动作")
    print(_DIVIDER)

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
                    "thought": "清理系统",
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
        on_event=lambda e: print(f"  [事件] {e['type']}: {e}"),
    )
    result = agent.run("清理系统")
    print(f"  结果: {result}")
    print()


def demo2_feedback_changes_action(tmp_path: Path) -> None:
    """DEMO2: agent 执行失败 → 反馈回灌 → 下一步动作改变。"""
    print(_DIVIDER)
    print("DEMO2: 反馈闭环使 agent 改变下一步动作")
    print(_DIVIDER)

    fence = ScopeFence(allowed_dirs=[tmp_path], protected_patterns=[".git/"])
    pipeline = GovernancePipeline(
        scope_fence=fence,
        danger_classifier=DangerClassifier([]),
        hitl_gate=HITLGate(),
    )
    dispatcher = ToolDispatcher()
    dispatcher.register("run_shell", ShellTool())
    dispatcher.register("write_file", WriteFileTool())

    file_path = tmp_path / "test_foo.py"

    mock = MockLLMClient(
        script=[
            # 第一步：跑测试，会失败（文件不存在）
            _tool_code(
                {
                    "tool": "run_shell",
                    "args": {"command": f"python -m pytest {file_path}"},
                    "thought": "先跑测试看结果",
                }
            ),
            # 第二步：收到失败反馈后，改为写文件
            _tool_code(
                {
                    "tool": "write_file",
                    "args": {
                        "path": str(file_path),
                        "content": "def test_foo(): assert True",
                    },
                    "thought": "测试失败，需要先创建测试文件",
                }
            ),
            # 第三步：返回完成
            "测试文件已创建，问题已修复",
        ]
    )

    executed_tools: list[str] = []
    original_dispatch = dispatcher.dispatch

    def tracking_dispatch(action: Action) -> object:
        executed_tools.append(action.tool)
        return original_dispatch(action)

    dispatcher.dispatch = tracking_dispatch  # type: ignore[method-assign]

    agent = AgentLoop(
        llm=mock,
        parser=ActionParser(),
        pipeline=pipeline,
        dispatcher=dispatcher,
        feedback=FeedbackLoop([ExitCodeValidator()]),
        memory=MemoryStore(),
        max_iterations=5,
        on_event=lambda e: print(f"  [事件] {e['type']}: {e}"),
    )
    result = agent.run("跑测试并修复")
    print(f"  执行工具序列: {executed_tools}")
    print(f"  结果: {result}")
    print("  验证: 第一步 run_shell → 第二步 write_file（动作已改变）")
    print()


def demo3_hitl_fail_closed() -> None:
    """DEMO3: HITL 状态机——fail-closed 语义（重点维度）。"""
    print(_DIVIDER)
    print("DEMO3: HITL 状态机——fail-closed（重点维度确定性行为）")
    print(_DIVIDER)

    gate = HITLGate()
    action = Action(
        tool="run_shell",
        args={"command": "rm -rf /tmp"},
        thought="",
    )
    classification = Classification(
        level=DangerLevel.DANGEROUS,
        matched_rule="force_delete",
        reason="递归删除",
    )

    # 场景1：无预设决策 → fail-closed → 阻断
    result = gate.gate(action, classification)
    print(f"  场景1: 无预设决策 → gate 返回 {result}（None=阻断）, 状态={gate.state.value}")

    # 场景2：用户拒绝 → 阻断
    gate2 = HITLGate()
    gate2.request_approval(action, classification)
    print(f"  场景2: 请求审批 → 状态={gate2.state.value}")
    gate2.receive_decision.__wrapped__ if hasattr(gate2.receive_decision, "__wrapped__") else None
    from src.governance.hitl import Decision
    gate2.receive_decision(Decision(verdict="deny"))
    result2 = gate2.gate(action, classification)
    print(f"         用户拒绝 → gate 返回 {result2}, 状态={gate2.state.value}")

    # 场景3：用户批准 → 放行
    gate3 = HITLGate()
    gate3.request_approval(action, classification)
    gate3.receive_decision(Decision(verdict="approve"))
    result3 = gate3._apply_decision()
    approved = result3 is not None
    print(f"  场景3: 用户批准 → gate 返回 {approved}（True=放行）, 状态={gate3.state.value}")
    print()


def main() -> None:
    """演示入口：依次运行三个机制演示。"""
    import tempfile

    print()
    print("NJUSE Coding Agent Harness — 机制演示")
    print("全部由 MockLLM 驱动，无网络、无真实 LLM")
    print()

    demo1_dangerous_action_blocked()

    with tempfile.TemporaryDirectory() as tmp:
        demo2_feedback_changes_action(Path(tmp))

    demo3_hitl_fail_closed()

    print(_DIVIDER)
    print("三个演示全部完成。")
    print(_DIVIDER)


if __name__ == "__main__":
    main()
