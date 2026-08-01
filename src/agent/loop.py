"""Agent 主循环：上下文 → LLM → 解析 → 治理 → 执行 → 反馈 → 停机。"""

from __future__ import annotations

from collections.abc import Callable

from src.feedback.loop import FeedbackLoop
from src.governance.pipeline import GovernancePipeline
from src.llm.base import LLMClient
from src.memory.store import MemoryStore
from src.parser.action_parser import ActionParser
from src.tools.dispatcher import ToolDispatcher
from src.types import Action, Message, ToolResult

EventCallback = Callable[[dict[str, object]], None]


class AgentLoop:
    """Agent 主循环，编排所有组件。

    流程：
    1. 组织上下文（系统提示 + 记忆 + 用户输入）
    2. 调用 LLM
    3. 解析动作
    4. 治理管道检查
    5. 工具分发执行
    6. 反馈闭环注入
    7. 停机判断（无动作 / 达到最大迭代 / LLM 返回纯文本）
    """

    def __init__(
        self,
        llm: LLMClient,
        parser: ActionParser,
        pipeline: GovernancePipeline,
        dispatcher: ToolDispatcher,
        feedback: FeedbackLoop,
        memory: MemoryStore,
        max_iterations: int = 10,
        on_event: EventCallback | None = None,
    ) -> None:
        self._llm = llm
        self._parser = parser
        self._pipeline = pipeline
        self._dispatcher = dispatcher
        self._feedback = feedback
        self._memory = memory
        self._max_iterations = max_iterations
        self._on_event = on_event
        self._context: list[Message] = []
        self._initialized = False

    def _emit(self, event: dict[str, object]) -> None:
        """发送事件回调。"""
        if self._on_event:
            self._on_event(event)

    def run(self, user_input: str) -> str:
        """运行 agent 主循环。"""
        if not self._initialized:
            system_prompt = (
                "你是一个编码助手，可以通过执行工具来完成任务。\n\n"
                "## 可用工具\n\n"
                "1. read_file — 读取文件内容\n"
                '  参数: {"path": "文件路径"}\n'
                "2. write_file — 写入文件\n"
                '  参数: {"path": "文件路径", "content": "文件内容"}\n'
                "3. list_dir — 列出目录内容\n"
                '  参数: {"path": "目录路径"}\n'
                "4. run_shell — 执行 shell 命令\n"
                '  参数: {"command": "命令字符串"}\n\n'
                "## 调用格式\n\n"
                "当需要使用工具时，输出如下代码块（JSON 格式）：\n\n"
                "```tool_code\n"
                '{"tool": "工具名", "args": {"参数": "值"},'
                ' "thought": "简短说明为什么要执行这个动作"}\n'
                "```\n\n"
                "## 示例\n\n"
                "用户: 帮我看看当前目录有什么文件\n"
                "```tool_code\n"
                '{"tool": "list_dir", "args": {"path": "."}, "thought": "列出当前目录内容"}\n'
                "```\n\n"
                "用户: 读取 src/main.py\n"
                "```tool_code\n"
                '{"tool": "read_file", "args": {"path": "src/main.py"},'
                ' "thought": "读取用户指定的文件"}\n'
                "```\n\n"
                "## 注意事项\n\n"
                "- 每次只输出一个 tool_code 代码块，等待工具返回结果后再决定下一步\n"
                '- 如果不需要工具就能回答（如一般知识问题），直接用纯文本回复，不要输出 tool_code\n'
                "- thought 字段简要说明你的推理过程\n"
                "- 工具执行结果会以 tool 角色消息返回，据此决定是否需要继续操作\n"
            )
            self._context.append(Message(role="system", content=system_prompt))
            self._initialized = True

        self._context.append(Message(role="user", content=user_input))
        self._memory.store(Message(role="user", content=user_input))

        self._emit({"type": "task_started", "input": user_input})

        for i in range(self._max_iterations):
            self._emit({"type": "step_started", "step": i})

            response = self._llm.chat(self._context)
            self._context.append(Message(role="assistant", content=response))
            self._emit(
                {"type": "thought", "step": i, "content": response[:500]},
            )

            actions = self._parser.parse(response)
            if not actions:
                self._emit(
                    {"type": "task_completed", "response": response},
                )
                return response

            for action in actions:
                self._process_action(action, self._context, i)

        self._emit({"type": "max_iterations_reached"})
        return f"达到最大迭代次数 {self._max_iterations}，循环终止"

    def _process_action(
        self, action: Action, context: list[Message], step: int
    ) -> None:
        """处理单个动作：治理 → 执行 → 反馈。"""
        self._emit(
            {
                "type": "action_parsed",
                "step": step,
                "tool": action.tool,
                "args": action.args,
                "thought": action.thought,
            },
        )

        gov_result = self._pipeline.process(action)
        self._emit(
            {
                "type": "governance_check",
                "step": step,
                "blocked": gov_result.blocked,
                "reason": gov_result.reason,
            },
        )

        if gov_result.blocked:
            blocked_result = ToolResult(
                success=False,
                stderr=gov_result.reason or "blocked",
                exit_code=1,
            )
            self._feedback.process(action, blocked_result, context)
            self._emit(
                {
                    "type": "action_blocked",
                    "step": step,
                    "reason": gov_result.reason,
                },
            )
            return
        if gov_result.action is None:
            return

        final_action = gov_result.action
        tool_result = self._dispatcher.dispatch(final_action)
        self._emit(
            {
                "type": "action_executed",
                "step": step,
                "success": tool_result.success,
                "stdout": tool_result.stdout[:500],
                "stderr": tool_result.stderr[:500] if tool_result.stderr else "",
            },
        )
        self._feedback.process(final_action, tool_result, context)
        self._memory.store(
            Message(role="tool", content=tool_result.stdout),
        )
