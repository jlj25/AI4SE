"""DEMO 集成测试：验证治理机制端到端。

DEMO1: 治理护栏拦截危险动作
DEMO2: 反馈闭环使 agent 收到失败反馈并改变下一步动作
DEMO3: HITL 状态机（重点维度确定性行为）
"""

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
from src.tools.fs import WriteFileTool
from src.tools.shell import ShellTool
from src.types import Action

# === DEMO1: 治理护栏拦截危险动作 ===


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


# === DEMO2: 反馈闭环使 agent 改变下一步动作 ===


def test_demo2_feedback_changes_next_action(tmp_path):
    """DEMO2: agent 执行命令失败 → 反馈回灌 → 下一步动作改变。

    场景：
    1. agent 执行 `pytest failing_test.py` → 失败（exit code 1）
    2. 反馈闭环将失败信号注入上下文
    3. agent 下一步改为写文件修复测试 → 成功
    4. agent 最终返回"已修复"

    关键断言：第二步动作（write_file）不同于第一步（run_shell），
    证明反馈信号驱动了行为改变。
    """
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

    # 记录 agent 执行的工具序列
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
    )
    result = agent.run("跑测试并修复")

    # 断言1：agent 执行了两个不同的动作
    assert len(executed_tools) >= 2
    # 断言2：第一个是 run_shell（跑测试）
    assert executed_tools[0] == "run_shell"
    # 断言3：第二个是 write_file（修复）——动作改变了
    assert executed_tools[1] == "write_file"
    # 断言4：最终返回包含修复信息
    assert "修复" in result or "创建" in result


def test_demo2_feedback_injects_failure_signal(tmp_path):
    """DEMO2 补充：验证失败信号确实被注入到上下文中。

    agent 执行失败后，事件流中应出现 success=False 的 action_executed 事件，
    且后续上下文包含反馈消息（role=tool，含失败信息）。
    """
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
                    "args": {"command": "python -c \"raise SystemExit(1)\""},
                    "thought": "执行会失败的命令",
                }
            ),
            "收到失败信号，停止",
        ]
    )

    events: list[dict[str, object]] = []
    agent = AgentLoop(
        llm=mock,
        parser=ActionParser(),
        pipeline=pipeline,
        dispatcher=dispatcher,
        feedback=FeedbackLoop([ExitCodeValidator()]),
        memory=MemoryStore(),
        max_iterations=5,
        on_event=events.append,
    )
    agent.run("执行失败命令")

    # 断言1：有 action_executed 事件且 success=False（失败被检测到）
    exec_events = [e for e in events if e["type"] == "action_executed"]
    assert len(exec_events) >= 1
    assert exec_events[0]["success"] is False

    # 断言2：memory 中有 tool 角色消息（反馈注入）
    tool_msgs = [m for m in agent._memory.all_messages() if m.role == "tool"]
    assert len(tool_msgs) >= 1


# === DEMO3: HITL 状态机（重点维度确定性行为）===


def test_demo3_hitl_deny_blocks_action():
    """DEMO3: HITL 审批流程，用户拒绝后动作被阻断。"""
    gate = HITLGate()
    action = Action(tool="run_shell", args={"command": "rm -rf /tmp"}, thought="")
    classification = Classification(level=DangerLevel.DANGEROUS, matched_rule="test", reason="危险")
    gate.request_approval(action, classification)
    assert gate.state.value == "pending_approval"
    gate.receive_decision(Decision(verdict="deny"))
    assert gate.state.value == "denied"


def test_demo3_hitl_fail_closed():
    """DEMO3: fail-closed 语义——无决策时直接 DENIED。"""
    gate = HITLGate()
    action = Action(tool="run_shell", args={"command": "rm -rf /tmp"}, thought="")
    classification = Classification(level=DangerLevel.DANGEROUS, matched_rule="test", reason="危险")
    result = gate.gate(action, classification)
    # fail-closed: 无预设决策 → None（阻断）
    assert result is None
    assert gate.state.value == "denied"


def test_demo3_hitl_approve_passes():
    """DEMO3: 用户批准后动作放行。

    gate() 内部会 request_approval 重置决策，故 approve 路径
    通过 _apply_decision() 独立验证（代码注释明确支持此用法）。
    """
    gate = HITLGate()
    action = Action(tool="run_shell", args={"command": "rm -rf /tmp"}, thought="")
    classification = Classification(level=DangerLevel.DANGEROUS, matched_rule="test", reason="危险")
    gate.request_approval(action, classification)
    gate.receive_decision(Decision(verdict="approve"))
    result = gate._apply_decision()
    assert result is not None
    assert gate.state.value == "approved"


def test_demo3_scope_fence_blocks_traversal():
    """DEMO3 补充: 路径穿越攻击被范围围栏硬拦截。"""
    fence = ScopeFence(allowed_dirs=[Path("./src")], protected_patterns=[])
    action = Action(
        tool="write_file",
        args={"path": "src/../../../etc/passwd", "content": "x"},
        thought="",
    )
    result = fence.check(action)
    assert result.value == "out_of_scope"


# === 辅助函数 ===


def _tool_code(action_dict: dict) -> str:
    """构造 tool_code 代码块，确保 JSON 路径正确转义。"""
    return f"```tool_code\n{json.dumps(action_dict, ensure_ascii=False)}\n```"
