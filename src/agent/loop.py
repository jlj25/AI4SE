"""Agent 主循环：上下文 → LLM → 解析 → 治理 → 执行 → 反馈 → 停机。"""

from __future__ import annotations

from src.feedback.loop import FeedbackLoop
from src.governance.pipeline import GovernancePipeline
from src.llm.base import LLMClient
from src.memory.store import MemoryStore
from src.parser.action_parser import ActionParser
from src.tools.dispatcher import ToolDispatcher
from src.types import Action, Message, ToolResult


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
    ) -> None:
        self._llm = llm
        self._parser = parser
        self._pipeline = pipeline
        self._dispatcher = dispatcher
        self._feedback = feedback
        self._memory = memory
        self._max_iterations = max_iterations

    def run(self, user_input: str) -> str:
        """运行 agent 主循环。"""
        context: list[Message] = []
        system_prompt = (
            "你是一个编码助手。使用 ```tool_code 代码块执行动作。"
            '格式：```tool_code\n{"tool": "...", "args": {...}, "thought": "..."}\n```'
        )
        context.append(Message(role="system", content=system_prompt))
        context.append(Message(role="user", content=user_input))
        self._memory.store(Message(role="user", content=user_input))

        for _i in range(self._max_iterations):
            response = self._llm.chat(context)
            context.append(Message(role="assistant", content=response))

            actions = self._parser.parse(response)
            if not actions:
                return response

            for action in actions:
                self._process_action(action, context)

        return f"达到最大迭代次数 {self._max_iterations}，循环终止"

    def _process_action(self, action: Action, context: list[Message]) -> None:
        """处理单个动作：治理 → 执行 → 反馈。"""
        gov_result = self._pipeline.process(action)
        if gov_result.blocked:
            blocked_result = ToolResult(
                success=False,
                stderr=gov_result.reason or "blocked",
                exit_code=1,
            )
            self._feedback.process(action, blocked_result, context)
            return
        if gov_result.action is None:
            return
        tool_result = self._dispatcher.dispatch(gov_result.action)
        self._feedback.process(gov_result.action, tool_result, context)
        self._memory.store(
            Message(role="tool", content=tool_result.stdout),
        )
