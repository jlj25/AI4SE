"""HITLGate 单测：验证状态机转移与审批逻辑。"""
import pytest

from src.governance.classifier import Classification, DangerLevel
from src.governance.hitl import Decision, HITLGate, HITLState
from src.types import Action


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


def test_warning_action_passes_without_approval():
    """WARNING 级别应与 SAFE 一样直接放行，不触发审批。"""
    gate = _make_gate()
    action = Action(tool="run_shell", args={"command": "git push"}, thought="")
    classification = Classification(level=DangerLevel.WARNING, matched_rule="test", reason="警告")
    result = gate.gate(action, classification)
    assert result == action
    assert gate.state == HITLState.IDLE


def test_receive_decision_raises_runtime_error_when_not_pending():
    """非 PENDING_APPROVAL 状态接收决策应抛 RuntimeError。"""
    gate = _make_gate()
    with pytest.raises(RuntimeError, match="非 PENDING_APPROVAL"):
        gate.receive_decision(Decision(verdict="approve"))


def test_receive_decision_raises_value_error_on_unknown_verdict():
    """未知 verdict 应抛 ValueError。"""
    gate = _make_gate()
    action = Action(tool="run_shell", args={"command": "rm -rf /"}, thought="")
    classification = Classification(level=DangerLevel.DANGEROUS, matched_rule="test", reason="危险")
    gate.request_approval(action, classification)
    with pytest.raises(ValueError, match="未知 verdict"):
        gate.receive_decision(Decision(verdict="bogus"))


def test_receive_decision_raises_value_error_on_modify_without_modified_action():
    """modify 决策未提供 modified_action 应抛 ValueError，避免放行原危险动作。"""
    gate = _make_gate()
    action = Action(tool="run_shell", args={"command": "rm -rf /"}, thought="")
    classification = Classification(level=DangerLevel.DANGEROUS, matched_rule="test", reason="危险")
    gate.request_approval(action, classification)
    with pytest.raises(ValueError, match="modified_action"):
        gate.receive_decision(Decision(verdict="modify", modified_action=None))


def test_apply_decision_approve_returns_pending_action():
    """approve 路径：_apply_decision 放行挂起的动作。"""
    gate = _make_gate()
    action = Action(tool="run_shell", args={"command": "rm -rf /tmp"}, thought="")
    classification = Classification(level=DangerLevel.DANGEROUS, matched_rule="test", reason="危险")
    gate.request_approval(action, classification)
    gate.receive_decision(Decision(verdict="approve"))
    result = gate._apply_decision()
    assert result == action
    assert gate.state == HITLState.APPROVED


def test_apply_decision_deny_returns_none():
    """deny 路径：_apply_decision 返回 None。"""
    gate = _make_gate()
    action = Action(tool="run_shell", args={"command": "rm -rf /"}, thought="")
    classification = Classification(level=DangerLevel.DANGEROUS, matched_rule="test", reason="危险")
    gate.request_approval(action, classification)
    gate.receive_decision(Decision(verdict="deny"))
    result = gate._apply_decision()
    assert result is None
    assert gate.state == HITLState.DENIED


def test_apply_decision_modify_returns_modified_action():
    """modify 路径：_apply_decision 返回修改后的动作，而非原危险动作。"""
    gate = _make_gate()
    original = Action(tool="run_shell", args={"command": "rm -rf /"}, thought="")
    modified = Action(tool="run_shell", args={"command": "rm -rf /tmp/safe"}, thought="")
    classification = Classification(level=DangerLevel.DANGEROUS, matched_rule="test", reason="危险")
    gate.request_approval(original, classification)
    gate.receive_decision(Decision(verdict="modify", modified_action=modified))
    result = gate._apply_decision()
    assert result == modified
    assert result != original
    assert gate.state == HITLState.MODIFIED


def test_apply_decision_fail_closed_without_decision():
    """无决策可用时 _apply_decision fail-closed 判 DENIED 并返回 None。"""
    gate = _make_gate()
    action = Action(tool="run_shell", args={"command": "rm -rf /"}, thought="")
    classification = Classification(level=DangerLevel.DANGEROUS, matched_rule="test", reason="危险")
    gate.request_approval(action, classification)
    result = gate._apply_decision()
    assert result is None
    assert gate.state == HITLState.DENIED
