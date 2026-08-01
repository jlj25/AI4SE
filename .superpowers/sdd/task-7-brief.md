## Task 7: 治理管道 GovernancePipeline（治理深度 · 4/4 集成）

**Files:**
- Create: `src/governance/pipeline.py`
- Test: `tests/governance/test_pipeline.py`

**Interfaces:**
- Consumes: `ScopeFence`, `DangerClassifier`, `HITLGate`
- Produces: `GovernanceResult(blocked, action, reason, classification)`, `GovernancePipeline.process(action) -> GovernanceResult`

- [ ] **Step 1: 写失败测试**

```python
# tests/governance/test_pipeline.py
"""GovernancePipeline 单测：验证管道串联与端到端治理行为。"""
from pathlib import Path
from src.types import Action
from src.config.loader import DangerRule
from src.governance.scope import ScopeFence
from src.governance.classifier import DangerClassifier, DangerLevel
from src.governance.hitl import HITLGate, Decision
from src.governance.pipeline import GovernancePipeline, GovernanceResult


def _make_pipeline(hitl_gate: HITLGate | None = None) -> GovernancePipeline:
    fence = ScopeFence(allowed_dirs=[Path("./src"), Path("./tests")], protected_patterns=[".git/", ".env"])
    rules = [
        DangerRule(name="force_delete", pattern=r"rm\s+(-\w*\w\w*\s+)?-rf?\s+/", level="dangerous", description="递归删除"),
        DangerRule(name="install_pkg", pattern=r"pip\s+install", level="warning", description="安装包"),
    ]
    classifier = DangerClassifier(rules)
    gate = hitl_gate or HITLGate()
    return GovernancePipeline(scope_fence=fence, danger_classifier=classifier, hitl_gate=gate)


def test_safe_action_passes():
    pipeline = _make_pipeline()
    action = Action(tool="read_file", args={"path": "src/main.py"}, thought="")
    result = pipeline.process(action)
    assert not result.blocked
    assert result.action == action


def test_out_of_scope_blocked_without_hitl():
    """范围围栏硬拦截，不进 HITL。"""
    pipeline = _make_pipeline()
    action = Action(tool="write_file", args={"path": "/etc/passwd", "content": "x"}, thought="")
    result = pipeline.process(action)
    assert result.blocked
    assert "out_of_scope" in result.reason
    assert result.classification is None


def test_protected_path_blocked_without_hitl():
    pipeline = _make_pipeline()
    action = Action(tool="write_file", args={"path": ".git/config", "content": "x"}, thought="")
    result = pipeline.process(action)
    assert result.blocked
    assert "protected" in result.reason


def test_dangerous_action_blocked_when_denied():
    """DEMO1 场景：危险动作被拦截。"""
    gate = HITLGate()
    pipeline = _make_pipeline(hitl_gate=gate)
    action = Action(tool="run_shell", args={"command": "rm -rf /"}, thought="")
    # 模拟用户拒绝：在 gate 中预设 deny
    gate._decision = Decision(verdict="deny")  # noqa: SLF001
    gate._state = gate._state.__class__("pending_approval")  # 强制进入 pending
    result = pipeline.process(action)
    assert result.blocked
    assert result.classification is not None
    assert result.classification.level == DangerLevel.DANGEROUS


def test_warning_action_passes_without_hitl():
    pipeline = _make_pipeline()
    action = Action(tool="run_shell", args={"command": "pip install requests"}, thought="")
    result = pipeline.process(action)
    assert not result.blocked
    assert result.classification.level == DangerLevel.WARNING
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/governance/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 GovernancePipeline**

```python
# src/governance/pipeline.py
"""治理管道：范围围栏 → 危险分类 → HITL 门，三阶段串联。"""
from __future__ import annotations

from dataclasses import dataclass

from src.types import Action
from src.governance.scope import ScopeFence, ScopeCheckResult
from src.governance.classifier import Classification, DangerClassifier, DangerLevel
from src.governance.hitl import HITLGate


@dataclass
class GovernanceResult:
    """治理管道处理结果。"""
    blocked: bool
    action: Action | None
    reason: str
    classification: Classification | None


class GovernancePipeline:
    """治理管道，agent 主循环中每个动作执行前的必经之路。

    ① 范围围栏（硬拦截）→ ② 危险分类 → ③ HITL 门（仅 DANGEROUS）。
    每个阶段是确定性代码，无需 LLM，可用构造的 Action 单测。
    """

    def __init__(
        self,
        scope_fence: ScopeFence,
        danger_classifier: DangerClassifier,
        hitl_gate: HITLGate,
    ) -> None:
        self._scope_fence = scope_fence
        self._danger_classifier = danger_classifier
        self._hitl_gate = hitl_gate

    def process(self, action: Action) -> GovernanceResult:
        """处理动作，返回治理结果。"""
        # ① 范围围栏（硬拦截）
        scope = self._scope_fence.check(action)
        if scope != ScopeCheckResult.ALLOWED:
            return GovernanceResult(
                blocked=True, action=None, reason=scope.value, classification=None
            )
        # ② 危险分类
        classification = self._danger_classifier.classify(action)
        # ③ HITL 门（仅 DANGEROUS 触发）
        if classification.level == DangerLevel.DANGEROUS:
            final = self._hitl_gate.gate(action, classification)
            if final is None:
                return GovernanceResult(
                    blocked=True, action=None, reason="user_denied",
                    classification=classification,
                )
            action = final
        self._hitl_gate.reset()
        return GovernanceResult(
            blocked=False, action=action, reason="passed", classification=classification
        )
```

- [ ] **Step 4: 运行测试验证通过 + lint + 提交**

```bash
uv run pytest tests/governance/test_pipeline.py -v
uv run ruff check src/governance/pipeline.py tests/governance/test_pipeline.py && uv run mypy src/governance/pipeline.py
git add src/governance/pipeline.py tests/governance/test_pipeline.py
git commit -m "feat: 治理管道 GovernancePipeline（范围围栏→危险分类→HITL门 串联）"
```

---