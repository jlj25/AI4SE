# Task 2 报告：LLM 抽象层 + MockLLMClient

## 实现内容

按 brief 逐字实现 LLM 抽象层，共 3 个源文件 + 2 个测试文件：

- `src/llm/__init__.py`：包初始化，仅含模块 docstring。
- `src/llm/base.py`：定义 `LLMClient`（ABC），声明抽象方法 `chat(messages: list[Message]) -> str`。
- `src/llm/mock_client.py`：`MockLLMClient(LLMClient)`，按 `script` 列表逐条返回预设响应；记录 `call_history`；脚本耗尽时抛 `IndexError("脚本耗尽：…")`。
- `tests/llm/__init__.py`：空包标记。
- `tests/llm/test_mock_client.py`：3 个单测，覆盖脚本返回、脚本耗尽、调用历史记录。

## TDD 证据

### RED（先写测试，验证失败）

运行 `uv run pytest tests/llm/test_mock_client.py -v`，结果：

```
ModuleNotFoundError: No module named 'src.llm'
1 error in 0.27s
```

失败原因符合 brief Step 2 预期（`ModuleNotFoundError`），且失败源于功能缺失而非笔误。

### GREEN（最小实现，验证通过）

按 brief Step 3 逐字写入 3 个源文件后，运行同一命令：

```
tests/llm/test_mock_client.py::test_mock_returns_scripted_response PASSED [ 33%]
tests/llm/test_mock_client.py::test_mock_raises_when_script_exhausted PASSED [ 66%]
tests/llm/test_mock_client.py::test_mock_records_call_history PASSED     [100%]
3 passed in 0.06s
```

### 全量验证（lint → mypy → 全部测试）

- `uv run ruff check src/llm/ tests/llm/`：初次报 2 个 I001（import 排序），`ruff check --fix` 自动修正后 `All checks passed!`。
- `uv run mypy src/llm/`：`Success: no issues found in 3 source files`（strict 模式）。
- `uv run pytest tests/ -v`：8 passed（3 新 + 5 旧），无回归。

## 变更文件

| 文件 | 操作 |
|------|------|
| `src/llm/__init__.py` | 新增 |
| `src/llm/base.py` | 新增 |
| `src/llm/mock_client.py` | 新增 |
| `tests/llm/__init__.py` | 新增 |
| `tests/llm/test_mock_client.py` | 新增 |

共 5 files changed, 64 insertions(+)。

## 自检发现

1. **import 顺序**：brief 原文将 `from src.types` 写在 `from src.llm.base` 之前，ruff 的 isort 要求按字母序排列（`src.llm.base` < `src.types`），已由 `ruff check --fix` 自动修正。这是纯格式调整，不改变语义，且 brief Step 4 本身就要求跑 `ruff check`，属预期流程。
2. **`import pytest` 内联**：brief 在 `test_mock_raises_when_script_exhausted` 函数体内内联 `import pytest`。ruff 未报警（局部导入合法），保留 brief 原样未动。
3. **docstring 全中文**：所有模块/类/方法 docstring 均为简体中文，符合 AGENTS.md 规定。
4. **无代码注释**：未添加任何 `#` 注释，仅保留 docstring。
5. **ABC 可实例化检查**：`LLMClient` 为 ABC，直接实例化会抛 `TypeError`（抽象方法未实现），符合"可注入 mock"的设计意图——真实 LLM 客户端子类化此基类，测试用 `MockLLMClient`。

## 隐患/关注点

- **commit message 不一致**：用户任务描述 Step 5 给出的 commit message 为 `feat: LLM 抽象层 + MockLLMClient（可注入 mock 用于离线单测）`，而 brief Step 4 给出的是 `feat: LLM 抽象层 + MockLLMClient（按脚本返回，可断言调用历史）`。两者语义均准确但措辞不同。鉴于用户明确指示"follow the brief verbatim"且 brief 被指定为"the exact values to use verbatim"的来源，已采用 brief 版本。如需改用用户 Step 5 版本，可 `git commit --amend` 修改。
- **CRLF 警告**：Windows 环境下 git 提示 LF 将被替换为 CRLF，属平台正常行为，不影响功能。
- **Python 版本**：pyproject.toml 声明 `requires-python = ">=3.12"`，实际 venv 为 3.13.7；`from __future__ import annotations` 在 3.12+ 非必需但无害，保留以与 brief 一致。
