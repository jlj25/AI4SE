"""HITLGate 单测：验证状态机转移与审批逻辑。"""
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
