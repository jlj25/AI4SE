# Task 7 Report: GovernancePipeline

## 结果
- **状态**: complete
- **提交**: `6dfd035` feat: 治理管道 GovernancePipeline（范围围栏→危险分类→HITL门 串联）
- **测试**: 7/7 通过，全量 51/51 通过
- **Lint/Type**: ruff check + format + mypy 全绿

## 实现内容
- `src/governance/pipeline.py`: GovernancePipeline 类 + GovernanceResult dataclass
- `tests/governance/test_pipeline.py`: 7 个测试覆盖全部路径

## 与 Brief 的偏差及原因
Brief 中的 `test_dangerous_action_blocked_when_denied` 使用 `rm -rf /` 作为危险命令。
在 Windows 上，`/` 被 ScopeFence._extract_paths_from_shell 提取为路径 token，
resolve() 解析为驱动器根目录（如 `C:\`），不在 allowed_dirs 内，
返回 OUT_OF_SCOPE 硬拦截，永远到不了 DangerClassifier 和 HITLGate。

**适配方案**: 新增 `force_push` 规则（`git push.*--force`），用 `git push --force` 作为
危险命令——它不含文件路径 token，通过 ScopeFence，被 DangerClassifier 分级为 DANGEROUS，
触发 HITLGate。同时预设 gate 状态为 PENDING_APPROVAL + deny 决策，验证拦截路径。

## 额外测试
- `test_dangerous_action_fail_closed_without_decision`: 验证 fail-closed 语义（无决策 → DENIED）
- `test_safe_shell_command_passes`: 验证 SAFE 级 shell 命令正常放行

## 治理管道流程
```
Action → ① ScopeFence.check()
         ├─ OUT_OF_SCOPE/PROTECTED → blocked, reason=scope.value, classification=None
         └─ ALLOWED → ② DangerClassifier.classify()
                      ├─ SAFE/WARNING → 放行, classification=结果
                      └─ DANGEROUS → ③ HITLGate.gate()
                                     ├─ None (denied/fail-closed) → blocked, reason="user_denied"
                                     └─ Action (approved/modified) → 放行, final_action=gated
                                     → HITLGate.reset()
```
