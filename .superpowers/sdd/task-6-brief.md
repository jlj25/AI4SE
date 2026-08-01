## Task 6: HITL 审批门 HITLGate（治理深度 · 3/4）

**Files:**
- Create: `src/governance/hitl.py`
- Test: `tests/governance/test_hitl.py`

**Interfaces:**
- Consumes: `Action` from `src/types.py`, `Classification` from `src/governance/classifier.py`
- Produces: `HITLState(Enum)`, `Decision(verdict, modified_action)`, `HITLGate`（状态机 + `gate(action, classification) -> Action | None`）

- [ ] **Step 1: 写失败测试**

```python
# tests/governance/test_hitl.py
"""HITLGate 单测：验证状态机转移与审批逻辑。"""
from src.types import Action
from src.governance.classifier import DangerLevel, Classification
from src.governance.hitl import HITLGate, HITLState, Decision


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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/governance/test_hitl.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 HITLGate**

```python
# src/governance/hitl.py
"""HITL 审批门：有限状态机，仅在危险动作时激活。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.types import Action
from src.governance.classifier import Classification, DangerLevel


class HITLState(Enum):
    """HITL 状态机状态。"""
    IDLE = "idle"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    DENIED = "denied"
    MODIFIED = "modified"


@dataclass
class Decision:
    """用户审批决策。"""
    verdict: str  # "approve" | "deny" | "modify"
    modified_action: Action | None = None


class HITLGate:
    """HITL 审批门，有限状态机。

    仅 DANGEROUS 级别动作触发审批；SAFE/WARNING 直接放行。
    状态转移：IDLE → PENDING_APPROVAL → APPROVED/DENIED/MODIFIED。
    在异步环境中，request_approval 创建 asyncio.Future 并 await，
    receive_decision 设置 Future 结果。单测中同步模拟。
    """

    def __init__(self) -> None:
        self._state = HITLState.IDLE
        self._pending_action: Action | None = None
        self._decision: Decision | None = None

    @property
    def state(self) -> HITLState:
        return self._state

    def gate(self, action: Action, classification: Classification) -> Action | None:
        """治理门：若 DANGEROUS 请求审批，返回最终动作或 None（拒绝）。"""
        if classification.level != DangerLevel.DANGEROUS:
            return action
        self.request_approval(action, classification)
        if self._decision is None:
            return None
        if self._decision.verdict == "deny":
            return None
        if self._decision.verdict == "modify" and self._decision.modified_action is not None:
            return self._decision.modified_action
        return action

    def request_approval(self, action: Action, classification: Classification) -> None:
        """IDLE → PENDING_APPROVAL，等待用户决策。"""
        self._state = HITLState.PENDING_APPROVAL
        self._pending_action = action
        self._decision = None

    def receive_decision(self, decision: Decision) -> None:
        """PENDING_APPROVAL → APPROVED/DENIED/MODIFIED。"""
        if self._state != HITLState.PENDING_APPROVAL:
            raise RuntimeError(f"非 PENDING_APPROVAL 状态无法接收决策: {self._state}")
        if decision.verdict == "approve":
            self._state = HITLState.APPROVED
        elif decision.verdict == "deny":
            self._state = HITLState.DENIED
        elif decision.verdict == "modify":
            self._state = HITLState.MODIFIED
            self._pending_action = decision.modified_action
        else:
            raise ValueError(f"未知 verdict: {decision.verdict}")
        self._decision = decision

    def reset(self) -> None:
        """重置到 IDLE，用于下一轮循环。"""
        self._state = HITLState.IDLE
        self._pending_action = None
        self._decision = None
```

- [ ] **Step 4: 运行测试验证通过 + lint + 提交**

```bash
uv run pytest tests/governance/test_hitl.py -v
uv run ruff check src/governance/hitl.py tests/governance/test_hitl.py && uv run mypy src/governance/hitl.py
git add src/governance/hitl.py tests/governance/test_hitl.py
git commit -m "feat: HITL 审批门（有限状态机 IDLE→PENDING→APPROVED/DENIED/MODIFIED）"
```

---