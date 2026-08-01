"""CLI 单元测试：mock LLM 驱动，验证事件格式化和入口逻辑。"""

import json
from unittest.mock import patch

from src.cli import _format_event, main, run_single


def _tool_code(action_dict: dict) -> str:
    return f"```tool_code\n{json.dumps(action_dict, ensure_ascii=False)}\n```"


def test_format_event_thought():
    """thought 事件格式化为 [思考] 前缀。"""
    event = {"type": "thought", "step": 0, "content": "我在思考"}
    result = _format_event(event)
    assert result is not None
    assert "[思考]" in result
    assert "我在思考" in result


def test_format_event_action_parsed():
    """action_parsed 事件格式化为 [动作] 前缀。"""
    event = {
        "type": "action_parsed",
        "step": 0,
        "tool": "read_file",
        "args": {"path": "foo.py"},
        "thought": "读取文件",
    }
    result = _format_event(event)
    assert result is not None
    assert "[动作]" in result
    assert "read_file" in result
    assert "foo.py" in result


def test_format_event_governance_blocked():
    """governance_check 拦截事件格式化为 [治理] 前缀。"""
    event = {"type": "governance_check", "step": 0, "blocked": True, "reason": "out_of_scope"}
    result = _format_event(event)
    assert result is not None
    assert "[治理]" in result
    assert "out_of_scope" in result


def test_format_event_governance_passed():
    """governance_check 通过事件返回 None（不打印）。"""
    event = {"type": "governance_check", "step": 0, "blocked": False, "reason": "passed"}
    result = _format_event(event)
    assert result is None


def test_format_event_action_executed_success():
    """action_executed 成功事件格式化为 [执行] 成功。"""
    event = {
        "type": "action_executed",
        "step": 0,
        "success": True,
        "stdout": "file content here",
        "stderr": "",
    }
    result = _format_event(event)
    assert result is not None
    assert "[执行]" in result
    assert "成功" in result


def test_format_event_action_executed_failure():
    """action_executed 失败事件格式化为 [执行] 失败。"""
    event = {
        "type": "action_executed",
        "step": 0,
        "success": False,
        "stdout": "",
        "stderr": "command not found",
    }
    result = _format_event(event)
    assert result is not None
    assert "失败" in result
    assert "command not found" in result


def test_format_event_task_completed():
    """task_completed 事件格式化为 [完成] 前缀。"""
    event = {"type": "task_completed", "response": "任务完成结果"}
    result = _format_event(event)
    assert result is not None
    assert "[完成]" in result
    assert "任务完成结果" in result


def test_format_event_action_blocked():
    """action_blocked 事件格式化为 [拦截] 前缀。"""
    event = {"type": "action_blocked", "step": 0, "reason": "dangerous"}
    result = _format_event(event)
    assert result is not None
    assert "[拦截]" in result
    assert "dangerous" in result


def test_format_event_max_iterations():
    """max_iterations_reached 事件格式化为 [警告] 前缀。"""
    event = {"type": "max_iterations_reached"}
    result = _format_event(event)
    assert result is not None
    assert "[警告]" in result


def test_format_event_unknown():
    """未知事件返回 None。"""
    event = {"type": "something_else"}
    result = _format_event(event)
    assert result is None


def test_format_event_suppressed_types():
    """task_started 和 step_started 事件返回 None（不打印噪音）。"""
    assert _format_event({"type": "task_started", "input": "test"}) is None
    assert _format_event({"type": "step_started", "step": 0}) is None


def test_run_single_with_mock(capsys):
    """单次任务模式：mock LLM 返回纯文本，CLI 输出结果。"""
    with patch("src.cli.create_agent") as mock_factory:
        mock_factory.return_value.run.return_value = "这是一个测试回复"
        mock_factory.return_value._context = []
        mock_factory.return_value._initialized = False
        run_single("测试任务", use_mock=True)
    captured = capsys.readouterr()
    assert "这是一个测试回复" in captured.out


def test_main_single_task(capsys):
    """main 入口：带参数时走单次任务模式。"""
    with patch("src.cli.run_single") as mock_run:
        exit_code = main(["你好"])
    mock_run.assert_called_once()
    assert exit_code == 0


def test_main_interactive(capsys):
    """main 入口：无参数时走交互模式。"""
    with patch("src.cli.run_interactive") as mock_run:
        exit_code = main([])
    mock_run.assert_called_once()
    assert exit_code == 0


def test_main_mock_flag():
    """main 入口：--mock 标志正确解析。"""
    with patch("src.cli.run_single") as mock_run:
        main(["--mock", "测试"])
    mock_run.assert_called_once_with("测试", use_mock=True)
