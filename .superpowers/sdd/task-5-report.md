# Task 5 报告：危险分类器 DangerClassifier（治理深度 · 2/4）

## 状态
DONE

## 交付物
- `src/governance/classifier.py`：DangerClassifier 实现
- `tests/governance/test_classifier.py`：6 个单测

## 实现摘要
按 brief 逐字实现，未偏离接口契约：

- `DangerLevel(Enum)`：SAFE / WARNING / DANGEROUS 三级。
- `_LEVEL_PRIORITY`：等级优先级字典（SAFE=0, WARNING=1, DANGEROUS=2），用于"最高等级优先"判定。
- `Classification` dataclass：`level` / `matched_rule` / `reason`。
- `DangerClassifier.__init__(rules)`：注入 `list[DangerRule]`，无外部依赖。
- `DangerClassifier.classify(action)`：
  1. 非 `run_shell` 工具直接返回 SAFE（`matched_rule=None`）。
  2. 取 `args["command"]`，遍历规则用 `re.search` 做正则匹配。
  3. 命中时按 `_LEVEL_PRIORITY` 比较，仅当新等级严格更高才覆盖。
  4. 无命中默认 SAFE。

确定性代码，无 LLM、无网络、无状态——满足"代码而非提示词"硬约束。

## TDD 流程
1. **Red**：先写 6 个测试，运行报 `ModuleNotFoundError: No module named 'src.governance.classifier'`。
2. **Green**：实现 `classifier.py`，6/6 通过。
3. **Lint/Type**：ruff `All checks passed!`，mypy `Success: no issues found`。

## 测试结果
```
6 passed in 0.10s
test_dangerous_rm_rf          PASSED
test_dangerous_git_force_push PASSED
test_warning_pip_install      PASSED
test_safe_command             PASSED
test_safe_file_read           PASSED
test_highest_level_wins       PASSED
```

## 偏离说明
brief 的测试代码 `_make_rules()` 中三行 `DangerRule(...)` 单行长度超过 ruff `line-length=100`，且 import 顺序未排序（触发 I001）。为通过 lint，将这三条规则改为多行构造、import 按字母序重排。**测试逻辑与数据零改动**，仅格式调整。

## 提交
- commit: `fd4dbd0`
- message: `feat: 危险分类器 DangerClassifier（正则模式匹配/风险分级/最高等级优先）`
- files: `src/governance/classifier.py`, `tests/governance/test_classifier.py`（2 files changed, 140 insertions）

## 自审
- [x] 接口与 brief 完全一致（DangerLevel / Classification / DangerClassifier.classify）
- [x] 消费 Action、DangerRule，无新增依赖
- [x] 全中文 docstring，无代码注释
- [x] 确定性可单测（移除 LLM 仍可测）
- [x] ruff + mypy + pytest 全绿
- [x] 与 Task 4 ScopeFence 解耦：围栏管"路径边界"，分类器管"命令风险"，二者正交可串联
