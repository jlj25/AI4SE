"""CLI 入口：命令行交互式 agent，类似 llama-cli。

用法：
  njuse-cli "你的任务"          # 单次任务模式
  njuse-cli                     # 交互式对话模式
  njuse-cli --mock "你的任务"   # 用 MockLLM 离线测试
"""

from __future__ import annotations

import sys

from src.agent.factory import create_agent
from src.llm.base import LLMClient
from src.llm.mock import MockLLMClient


def _format_event(event: dict[str, object]) -> str | None:
    """将 agent 事件格式化为终端输出文本。"""
    etype = event.get("type", "")

    if etype == "task_started":
        return None
    if etype == "step_started":
        return None
    if etype == "thought":
        content = str(event.get("content", ""))
        return f"  [思考] {content}"
    if etype == "action_parsed":
        tool = event.get("tool", "")
        args = event.get("args", {})
        thought = event.get("thought", "")
        return f"  [动作] {tool}({args}) — {thought}"
    if etype == "governance_check":
        blocked = event.get("blocked", False)
        reason = event.get("reason", "")
        if blocked:
            return f"  [治理] 已拦截: {reason}"
        return None
    if etype == "action_executed":
        success = event.get("success", False)
        stdout = str(event.get("stdout", ""))[:200]
        stderr = str(event.get("stderr", ""))[:200] if event.get("stderr") else ""
        status = "成功" if success else "失败"
        lines = [f"  [执行] {status}"]
        if stdout:
            lines.append(f"         输出: {stdout}")
        if stderr:
            lines.append(f"         错误: {stderr}")
        return "\n".join(lines)
    if etype == "action_blocked":
        reason = event.get("reason", "")
        return f"  [拦截] {reason}"
    if etype == "task_completed":
        response = str(event.get("response", ""))
        return f"  [完成] {response}"
    if etype == "max_iterations_reached":
        return "  [警告] 达到最大迭代次数"
    if etype == "error":
        message = event.get("message", "")
        return f"  [错误] {message}"
    return None


def _print_event(event: dict[str, object]) -> None:
    """事件回调：打印到终端。"""
    text = _format_event(event)
    if text:
        print(text, flush=True)


def run_interactive(use_mock: bool = False) -> None:
    """交互式对话模式。"""
    llm: LLMClient | None = (
        MockLLMClient(
            script=[
                "[MockLLM] 模拟回复 1",
                "[MockLLM] 模拟回复 2",
                "[MockLLM] 模拟回复 3",
            ]
        )
        if use_mock
        else None
    )
    agent = create_agent(llm=llm, on_event=_print_event)

    print("NJUSE Coding Agent — 交互模式")
    print("输入 'quit' 或 'exit' 退出，'clear' 清空上下文")
    print()

    while True:
        try:
            user_input = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            break
        if user_input.lower() == "clear":
            agent._context.clear()
            agent._initialized = False
            print("  [上下文已清空]")
            continue

        print()
        result = agent.run(user_input)
        print(f"  Agent: {result}")
        print()


def run_single(task: str, use_mock: bool = False) -> None:
    """单次任务模式。"""
    llm: LLMClient | None = (
        MockLLMClient(script=["[MockLLM] 这是一条模拟回复，用于离线测试 CLI 功能。"])
        if use_mock
        else None
    )
    agent = create_agent(llm=llm, on_event=_print_event)
    result = agent.run(task)
    print(f"Agent: {result}")


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口。"""
    args = argv if argv is not None else sys.argv[1:]

    use_mock = "--mock" in args
    args = [a for a in args if a != "--mock"]

    if args:
        run_single(" ".join(args), use_mock=use_mock)
    else:
        run_interactive(use_mock=use_mock)

    return 0


if __name__ == "__main__":
    sys.exit(main())
