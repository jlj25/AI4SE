# Task 4 报告：范围围栏 ScopeFence（治理深度 · 1/4）

## 状态
DONE

## 交付物
- `src/governance/__init__.py`：治理子包入口
- `src/governance/scope.py`：`ScopeCheckResult` 枚举 + `ScopeFence` 类
- `tests/governance/__init__.py`
- `tests/governance/test_scope.py`：7 个单测

## 接口
- 消费：`Action`（来自 `src/types.py`）
- 产出：`ScopeCheckResult(Enum)`、`ScopeFence.check(action: Action) -> ScopeCheckResult`

## 验证
- `uv run pytest tests/governance/test_scope.py -v` → 7 passed
- `uv run ruff check src/governance/ tests/governance/` → All checks passed
- `uv run mypy src/governance/` → Success: no issues found in 2 source files

## 提交
- `3246116` feat: 范围围栏 ScopeFence（路径检查/穿越防御/受保护路径硬拦截）

## TDD 流程
1. 红：先写 7 个测试，运行确认 `ModuleNotFoundError: No module named 'src.governance'`
2. 绿：按 brief 实现 `ScopeFence`，但 brief 给出的 `_check_path` 用 `path.match(clean)` 无法识别 `.git/` 目录组件（`Path.match` 只匹配末尾组件），导致 `test_protected_path_git` 与 `test_shell_command_with_protected_path` 失败
3. 修正：将 `path.match(clean)` 替换为 `clean in path.parts`，可识别路径任意层级的受保护目录/文件名，全部测试通过
4. 重构：`ruff format` 整理测试文件（import 排序、长行折行），语义不变

## 设计要点
- **硬拦截**：`PROTECTED` 与 `OUT_OF_SCOPE` 均直接阻断，不进 HITL，符合"绝对边界"语义
- **穿越防御**：`Path.resolve()` 规范化 `..`/符号链接后，用 `relative_to(allowed_dir)` 判定归属；`src/../../../etc/passwd` 解析后落在允许目录外 → `OUT_OF_SCOPE`
- **受保护路径**：支持 `.git/`（目录模式，匹配任意层级组件）与 `.env`（文件名模式，`fnmatch` 匹配 `path.name`）
- **shell 命令检查**：简化版 token 提取——含 `/` 或 `.` 且非选项（不以 `-` 开头）的 token 视为路径，再走相同路径检查

## 偏离说明
- brief 的实现代码块中 `_check_path` 末段使用 `if path.match(clean): return PROTECTED`，该行无法通过 brief 自带的测试用例（`Path(".git/config").match(".git")` 返回 `False`，因为 `match` 仅匹配末尾组件）。按 TDD 原则（测试为需求真值），将其改为 `if clean in path.parts:`，这是使 brief 测试通过的最小修正，未改变接口与语义。

## 已知局限
- shell 路径提取为简化版（brief 明示），对引号包裹路径、管道、子命令等复杂 shell 语法可能漏报/误报；后续 `DangerClassifier`/`HITLGate` 可叠加更细的命令解析
- Windows 下绝对 Unix 路径（如 `/etc/passwd`）被 `resolve()` 视为驱动器相对路径（`D:\etc\passwd`），仍正确判为 `OUT_OF_SCOPE`，不影响安全语义

## 后续衔接
为治理深度下一任务（DangerClassifier）提供可复用的路径检查原语；`ScopeFence` 作为治理管线第一道硬闸门，输出 `ScopeCheckResult` 供 `GovernancePipeline` 串联。
