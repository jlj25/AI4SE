# Task 6 报告：HITL 审批门 HITLGate（治理深度 · 3/4）

## 状态
DONE_WITH_CONCERNS

## 产出文件
- `src/governance/hitl.py`（90 行）
- `tests/governance/test_hitl.py`（83 行）

## 接口实现
- `HITLState(Enum)`：IDLE / PENDING_APPROVAL / APPROVED / DENIED / MODIFIED
- `Decision(verdict: str, modified_action: Action | None = None)` dataclass
- `HITLGate`：
  - `state` 属性
  - `gate(action, classification) -> Action | None`：SAFE/WARNING 直接放行；DANGEROUS 请求审批
  - `request_approval(action, classification)`：IDLE → PENDING_APPROVAL
  - `receive_decision(decision)`：PENDING_APPROVAL → APPROVED/DENIED/MODIFIED（非法状态抛 RuntimeError，未知 verdict 抛 ValueError）
  - `reset()`：回到 IDLE

## 测试结果
```
7 passed in 0.10s
```
覆盖：初始态、SAFE 放行、DANGEROUS 请求审批、approve/deny/modify 转移、reset。

## 质量门
- `uv run ruff check`：All checks passed!
- `uv run mypy src/governance/hitl.py`：Success: no issues found
- 全中文 docstring，无代码注释。

## 提交
- `2a56f69 feat: HITL 审批门（有限状态机 IDLE→PENDING→APPROVED/DENIED/MODIFIED）`

## 关注点（Concerns）
**brief 的 `gate()` 实现与 `test_deny_returns_none` 存在冲突。**

brief 给出的 `gate()` 在 `_decision is None` 时 `return None` 但**不修改状态**，此时状态停留在 PENDING_APPROVAL。而测试 `test_deny_returns_none` 调用 `gate()` 后断言 `gate.state == HITLState.DENIED`。

按 TDD 原则（测试即规约，red→green→refactor，必须 verify pass），我选择让实现满足测试，采用 **fail-closed** 语义：DANGEROUS 动作若在同步环境中无可用决策，直接判为 DENIED 并返回 None。这与 brief docstring 中"单测中同步模拟"的意图一致，也是安全侧的正确默认（无审批即拒绝）。

偏离点：`gate()` 在 `_decision is None` 分支增加了 `self._state = HITLState.DENIED` 一行（brief 原文无此行）。其余实现与 brief 逐字一致。

## 自审清单
- [x] 状态机五态齐全，转移路径与 brief 一致
- [x] SAFE/WARNING 不触发审批（直接返回原 action）
- [x] receive_decision 在非 PENDING_APPROVAL 状态抛错（防御性）
- [x] 未知 verdict 抛 ValueError（防御性）
- [x] reset 清空 _pending_action 与 _decision，避免跨轮污染
- [x] 无 LLM 依赖，纯确定性代码，可单测

---

## 评审修复报告（Review Fix）

提交：`aab8d30 fix: HITLGate 修复（modify校验/gate死代码重构/错误路径测试/WARNING测试）`

### 修复 1（CRITICAL）：modify 缺 modified_action 静默放行原危险动作
- **问题**：`gate()` 中 `verdict=="modify"` 但 `modified_action is None` 时，条件不成立，落入 `return action`（原 DANGEROUS 动作），属安全漏洞。
- **修复**：在 `receive_decision()` 的 modify 分支前置校验 `if decision.modified_action is None: raise ValueError`，从源头拦截，gate/apply_decision 不再有放行原危险动作的路径。

### 修复 2（IMPORTANT）：gate() approve/modify/deny-with-decision 死代码
- **问题**：`gate()` 调用 `request_approval()` 会重置 `_decision = None`，导致后续 `if self._decision is None` 恒为 True，approve/modify/deny-with-decision 三条分支不可达。
- **修复**：抽取 `_apply_decision()` 辅助方法承载决策应用逻辑（deny→None、modify→modified_action、approve→pending_action、无决策→fail-closed DENIED）。`gate()` 改为 `request_approval()` 后委托 `_apply_decision()`。`_apply_decision()` 可独立调用测试，三条路径全部可达。

### 修复 3（IMPORTANT）：补防御性错误路径测试
- 新增 `test_receive_decision_raises_runtime_error_when_not_pending`：IDLE 态接收决策抛 RuntimeError。
- 新增 `test_receive_decision_raises_value_error_on_unknown_verdict`：未知 verdict 抛 ValueError。
- 新增 `test_receive_decision_raises_value_error_on_modify_without_modified_action`：modify 无 modified_action 抛 ValueError（覆盖修复 1）。

### 修复 4（IMPORTANT）：补 WARNING 级别测试
- 新增 `test_warning_action_passes_without_approval`：WARNING 与 SAFE 一样直接放行，不触发审批，状态保持 IDLE。

### 死代码可达性测试（配合修复 2）
- `test_apply_decision_approve_returns_pending_action`：approve 路径放行挂起动作。
- `test_apply_decision_deny_returns_none`：deny 路径返回 None。
- `test_apply_decision_modify_returns_modified_action`：modify 路径返回修改后动作且不等于原危险动作。
- `test_apply_decision_fail_closed_without_decision`：无决策 fail-closed 判 DENIED。

### 验证结果
```
uv run pytest tests/governance/test_hitl.py -v   → 15 passed
uv run ruff check src/governance/hitl.py tests/governance/test_hitl.py → All checks passed!
uv run mypy src/governance/hitl.py               → Success: no issues found
```

### 关注点
无新增关注点。修复 2 采用"抽取 `_apply_decision()` 可独立测试"方案，未改变 `gate()` 对外行为（同步环境 DANGEROUS 仍 fail-closed 返回 None），仅消除死代码并提升可测性。
