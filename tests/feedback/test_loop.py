"""反馈闭环单测：验证信号注入回上下文。"""

from src.feedback.loop import FeedbackLoop
from src.feedback.validators import ExitCodeValidator
from src.types import Action, FeedbackType, Message, ToolResult


def test_feedback_injected_into_context():
    loop = FeedbackLoop(validators=[ExitCodeValidator(expected_exit_code=0)])
    action = Action(tool="run_shell", args={"command": "ls"}, thought="")
    result = ToolResult(success=True, stdout="file.txt")
    context: list[Message] = []
    loop.process(action, result, context)
    assert len(context) == 1
    assert context[0].role == "tool"
    assert "file.txt" in context[0].content
    assert context[0].feedback is not None
    assert context[0].feedback.type == FeedbackType.SUCCESS


def test_feedback_failure_injected():
    loop = FeedbackLoop(validators=[ExitCodeValidator(expected_exit_code=0)])
    action = Action(tool="run_shell", args={"command": "bad"}, thought="")
    result = ToolResult(success=False, stderr="not found", exit_code=127)
    context: list[Message] = []
    loop.process(action, result, context)
    assert context[0].feedback is not None
    assert context[0].feedback.type == FeedbackType.FAILURE


def test_multiple_validators_aggregate_failure_wins():
    """多个验证器中 FAILURE 优先于 SUCCESS。"""
    from src.feedback.validators import OutputContainsValidator

    loop = FeedbackLoop(
        validators=[
            OutputContainsValidator(expected_substring="PASS"),
            ExitCodeValidator(expected_exit_code=0),
        ],
    )
    action = Action(tool="run_shell", args={"command": "pytest"}, thought="")
    result = ToolResult(success=True, stdout="tests FAILED")
    context: list[Message] = []
    signal = loop.process(action, result, context)
    assert signal.type == FeedbackType.FAILURE
