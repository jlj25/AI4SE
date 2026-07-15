"""核心数据类型的测试。"""

from src.types import (
    Action,
    FeedbackSignal,
    FeedbackType,
    Message,
    ToolResult,
)


def test_action_creation():
    action = Action(tool="read_file", args={"path": "src/main.py"}, thought="读取主文件")
    assert action.tool == "read_file"
    assert action.args == {"path": "src/main.py"}
    assert action.thought == "读取主文件"


def test_tool_result_success():
    result = ToolResult(success=True, stdout="hello", stderr="", exit_code=0)
    assert result.success is True
    assert result.stdout == "hello"
    assert result.exit_code == 0


def test_tool_result_failure():
    result = ToolResult(success=False, stdout="", stderr="not found", exit_code=1)
    assert result.success is False
    assert result.stderr == "not found"


def test_feedback_signal():
    signal = FeedbackSignal(
        type=FeedbackType.FAILURE,
        message="2 tests failed",
        details={"count": 2},
    )
    assert signal.type == FeedbackType.FAILURE
    assert signal.details == {"count": 2}


def test_message_with_feedback():
    msg = Message(role="user", content="修复 bug")
    assert msg.role == "user"
    assert msg.content == "修复 bug"
    assert msg.feedback is None

    signal = FeedbackSignal(type=FeedbackType.SUCCESS, message="通过")
    msg2 = Message(role="tool", content="输出", feedback=signal)
    assert msg2.feedback is not None
    assert msg2.feedback.type == FeedbackType.SUCCESS
