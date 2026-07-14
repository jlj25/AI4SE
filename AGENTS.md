# NJUSE — AI4SE Coding Agent Harness

Python project using `uv`. Build a Coding Agent Harness from scratch.

## Project constraints (from assignment spec)

**Must implement** as your own code:
- Agent main loop: organize context → call LLM → parse action → dispatch → inject results → halt check
- Injectable mock LLM abstraction (abstract base / protocol)
- Tool dispatch system (filesystem, shell, build/test commands)
- Governance guardrails: intercept dangerous actions before execution
- Feedback loop: deterministic validator/sensor that parses output, judges correctness, feeds back into the loop
- Memory: cross-session storage with selective retrieval (not full-context dump)
- Configuration: declarative rules that constrain agent behavior

**Must NOT use** as a dependency:
- LangChain `AgentExecutor`, AutoGen, CrewAI, LlamaIndex agent, or any coding agent SDK's built-in agent runner
- You may use low-level parts: LLM provider chat completion API, HTTP libraries, vector stores, parsing libraries

**Code, not prompts**: feedback signals and danger guardrails must be implemented as deterministic code functions, not as instructions in the system prompt. Test: "remove the real LLM — can you still unit-test the mechanism?" If no, it doesn't count.

## Architecture direction

- One dimension should be the "deep" main contribution (suggested: governance/safety, feedback loop, or tool dispatch). Others get a working minimum.
- All core mechanisms must be testable with a mock/stub LLM, no network, no real model.
- Keep the kernel small and separable from any "contents" (prompts, config files, rules).

## Commands (configure via pyproject.toml)

```
uv run pytest              # run all tests
uv run pytest -xvs         # quick focused run
uv run pytest -k test_name # single test
uv run mypy .              # type check
uv run ruff check .        # lint
uv run ruff format .       # format
```

Run order: `ruff check .` → `mypy .` → `pytest -xvs`

# ======================
# 全局强制交互规则（最高优先级，任何场景不可忽略）
# ======================
## 一、语言输出规定
1. 所有解释、分析、文档描述、代码注释、总结内容统一使用简体中文书写。
2. 代码类英文专有名词（库名、变量、模型ID、命令）可以保留英文，但必须紧跟中文说明。
3. 禁止大段纯英文回复，默认全程中文沟通；仅在我明确要求英文输出时，才可切换语言。
4. 你生成的 SPEC.md、CHECKLIST.md、context_pack.md 等项目文档，正文描述全部使用中文。
