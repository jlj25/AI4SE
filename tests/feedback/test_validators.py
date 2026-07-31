"""验证器单测：验证确定性反馈信号生成。"""

from src.feedback.validators import ExitCodeValidator, OutputContainsValidator
from src.types import Action, FeedbackType, ToolResult


def test_exit_code_success():
    validator = ExitCodeValidator(expected_exit_code=0)
    result = ToolResult(success=True, stdout="done")
    signal = validator.validate(
        Action(tool="run_shell", args={"command": "ls"}, thought=""),
        result,
    )
    assert signal.type == FeedbackType.SUCCESS
    assert "通过" in signal.message


def test_exit_code_failure():
    validator = ExitCodeValidator(expected_exit_code=0)
    result = ToolResult(success=False, stderr="command not found", exit_code=127)
    signal = validator.validate(
        Action(tool="run_shell", args={"command": "bad"}, thought=""),
        result,
    )
    assert signal.type == FeedbackType.FAILURE
    assert "失败" in signal.message


def test_output_contains_success():
    validator = OutputContainsValidator(expected_substring="PASS")
    result = ToolResult(success=True, stdout="tests PASS")
    signal = validator.validate(
        Action(tool="run_shell", args={"command": "pytest"}, thought=""),
        result,
    )
    assert signal.type == FeedbackType.SUCCESS


def test_output_contains_failure():
    validator = OutputContainsValidator(expected_substring="PASS")
    result = ToolResult(success=True, stdout="tests FAILED")
    signal = validator.validate(
        Action(tool="run_shell", args={"command": "pytest"}, thought=""),
        result,
    )
    assert signal.type == FeedbackType.FAILURE


def test_no_validators_returns_info():
    """无验证器时返回 INFO 信号。"""
    from src.feedback.loop import FeedbackLoop

    loop = FeedbackLoop(validators=[])
    action = Action(tool="run_shell", args={"command": "ls"}, thought="")
    result = ToolResult(success=True, stdout="x")
    signal = loop._aggregate(action, result)  # noqa: SLF001
    assert signal.type == FeedbackType.INFO
