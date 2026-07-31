"""GovernancePipeline 单测：验证管道串联与端到端治理行为。"""

from pathlib import Path

from src.config.loader import DangerRule
from src.governance.classifier import DangerClassifier, DangerLevel
from src.governance.hitl import Decision, HITLGate, HITLState
from src.governance.pipeline import GovernancePipeline
from src.governance.scope import ScopeFence
from src.types import Action


def _make_pipeline(hitl_gate: HITLGate | None = None) -> GovernancePipeline:
    fence = ScopeFence(
        allowed_dirs=[Path("./src"), Path("./tests")],
        protected_patterns=[".git/", ".env"],
    )
    rules = [
        DangerRule(
            name="force_delete",
            pattern=r"rm\s+(-\w*\w\w*\s+)?-rf?\s+/",
            level="dangerous",
            description="递归删除",
        ),
        DangerRule(
            name="force_push",
            pattern=r"git\s+push.*--force",
            level="dangerous",
            description="强制推送",
        ),
        DangerRule(
            name="install_pkg",
            pattern=r"pip\s+install",
            level="warning",
            description="安装包",
        ),
    ]
    classifier = DangerClassifier(rules)
    gate = hitl_gate or HITLGate()
    return GovernancePipeline(
        scope_fence=fence,
        danger_classifier=classifier,
        hitl_gate=gate,
    )


def test_safe_action_passes():
    pipeline = _make_pipeline()
    action = Action(tool="read_file", args={"path": "src/main.py"}, thought="")
    result = pipeline.process(action)
    assert not result.blocked
    assert result.action == action


def test_out_of_scope_blocked_without_hitl():
    """范围围栏硬拦截，不进 HITL。"""
    pipeline = _make_pipeline()
    action = Action(
        tool="write_file",
        args={"path": "/etc/passwd", "content": "x"},
        thought="",
    )
    result = pipeline.process(action)
    assert result.blocked
    assert "out_of_scope" in result.reason
    assert result.classification is None


def test_protected_path_blocked_without_hitl():
    pipeline = _make_pipeline()
    action = Action(
        tool="write_file",
        args={"path": ".git/config", "content": "x"},
        thought="",
    )
    result = pipeline.process(action)
    assert result.blocked
    assert "protected" in result.reason


def test_dangerous_action_blocked_when_denied():
    """DEMO1 场景：危险动作被拦截。

    使用 git push --force（无文件路径，通过范围围栏）作为危险命令，
    预设 deny 决策验证 HITL 拦截路径。
    """
    gate = HITLGate()
    pipeline = _make_pipeline(hitl_gate=gate)
    action = Action(
        tool="run_shell",
        args={"command": "git push --force origin main"},
        thought="",
    )
    gate._state = HITLState.PENDING_APPROVAL  # noqa: SLF001
    gate._decision = Decision(verdict="deny")  # noqa: SLF001
    gate._pending_action = action  # noqa: SLF001
    result = pipeline.process(action)
    assert result.blocked
    assert result.classification is not None
    assert result.classification.level == DangerLevel.DANGEROUS


def test_dangerous_action_fail_closed_without_decision():
    """DANGEROUS 动作无预设决策时 fail-closed 为 DENIED。"""
    pipeline = _make_pipeline()
    action = Action(
        tool="run_shell",
        args={"command": "git push --force"},
        thought="",
    )
    result = pipeline.process(action)
    assert result.blocked
    assert result.reason == "user_denied"
    assert result.classification is not None
    assert result.classification.level == DangerLevel.DANGEROUS


def test_warning_action_passes_without_hitl():
    pipeline = _make_pipeline()
    action = Action(
        tool="run_shell",
        args={"command": "pip install requests"},
        thought="",
    )
    result = pipeline.process(action)
    assert not result.blocked
    assert result.classification.level == DangerLevel.WARNING


def test_safe_shell_command_passes():
    pipeline = _make_pipeline()
    action = Action(tool="run_shell", args={"command": "echo hello"}, thought="")
    result = pipeline.process(action)
    assert not result.blocked
    assert result.classification is not None
    assert result.classification.level == DangerLevel.SAFE
