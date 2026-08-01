"""Agent 工厂：创建完整配置的 AgentLoop 实例。"""

from __future__ import annotations

from pathlib import Path

from src.agent.loop import AgentLoop, EventCallback
from src.config.loader import ConfigLoader
from src.credentials.manager import CredentialManager
from src.feedback.loop import FeedbackLoop
from src.feedback.validators import ExitCodeValidator
from src.governance.classifier import DangerClassifier
from src.governance.hitl import HITLGate
from src.governance.pipeline import GovernancePipeline
from src.governance.scope import ScopeFence
from src.llm.base import LLMClient
from src.llm.real import RealLLMClient
from src.memory.store import MemoryStore
from src.parser.action_parser import ActionParser
from src.tools.dispatcher import ToolDispatcher
from src.tools.fs import ListDirTool, ReadFileTool, WriteFileTool
from src.tools.shell import ShellTool


def create_agent(
    llm: LLMClient | None = None,
    workspace: str = ".",
    on_event: EventCallback | None = None,
) -> AgentLoop:
    """创建完整配置的 AgentLoop。

    Args:
        llm: LLM 客户端，默认为 RealLLMClient
        workspace: 工作目录，默认为当前目录
        on_event: 事件回调函数
    """
    if llm is None:
        llm = RealLLMClient(CredentialManager())

    config = ConfigLoader()
    agent_config = config.load(Path("config/config.yaml"))

    ws_path = Path(workspace).resolve()
    allowed_dirs = [ws_path]

    scope_fence = ScopeFence(
        allowed_dirs=allowed_dirs,
        protected_patterns=agent_config.scope.protected_patterns,
    )
    danger_classifier = DangerClassifier(agent_config.danger_rules)
    hitl_gate = HITLGate()
    pipeline = GovernancePipeline(scope_fence, danger_classifier, hitl_gate)

    dispatcher = ToolDispatcher()
    tools = [
        ("read_file", ReadFileTool()),
        ("write_file", WriteFileTool()),
        ("list_dir", ListDirTool()),
        ("run_shell", ShellTool()),
    ]
    for name, tool in tools:
        dispatcher.register(name, tool)

    feedback = FeedbackLoop(validators=[ExitCodeValidator()])
    memory = MemoryStore()
    parser = ActionParser()

    return AgentLoop(
        llm=llm,
        parser=parser,
        pipeline=pipeline,
        dispatcher=dispatcher,
        feedback=feedback,
        memory=memory,
        max_iterations=agent_config.max_steps,
        on_event=on_event,
    )
