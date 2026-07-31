"""工具分发系统单测：验证注册、分发、执行。"""

import contextlib
import tempfile
from pathlib import Path

from src.tools.dispatcher import ToolDispatcher
from src.tools.fs import ListDirTool, ReadFileTool, WriteFileTool
from src.tools.shell import ShellTool
from src.types import Action, ToolResult


def test_register_and_dispatch_read_file():
    dispatcher = ToolDispatcher()
    dispatcher.register("read_file", ReadFileTool())
    with _tmp_dir() as tmp:
        p = Path(tmp) / "test.txt"
        p.write_text("hello world", encoding="utf-8")
        action = Action(tool="read_file", args={"path": str(p)}, thought="")
        result = dispatcher.dispatch(action)
        assert isinstance(result, ToolResult)
        assert result.success
        assert "hello world" in result.stdout


def test_write_then_read():
    dispatcher = ToolDispatcher()
    dispatcher.register("write_file", WriteFileTool())
    dispatcher.register("read_file", ReadFileTool())
    with _tmp_dir() as tmp:
        path = str(Path(tmp) / "out.txt")
        write_action = Action(
            tool="write_file",
            args={"path": path, "content": "data"},
            thought="",
        )
        dispatcher.dispatch(write_action)
        read_action = Action(tool="read_file", args={"path": path}, thought="")
        result = dispatcher.dispatch(read_action)
        assert result.success
        assert "data" in result.stdout


def test_list_dir():
    dispatcher = ToolDispatcher()
    dispatcher.register("list_dir", ListDirTool())
    with _tmp_dir() as tmp:
        (Path(tmp) / "a.txt").write_text("a", encoding="utf-8")
        (Path(tmp) / "b.txt").write_text("b", encoding="utf-8")
        action = Action(tool="list_dir", args={"path": tmp}, thought="")
        result = dispatcher.dispatch(action)
        assert result.success
        assert "a.txt" in result.stdout
        assert "b.txt" in result.stdout


def test_shell_tool():
    dispatcher = ToolDispatcher()
    dispatcher.register("run_shell", ShellTool())
    action = Action(tool="run_shell", args={"command": "echo hello"}, thought="")
    result = dispatcher.dispatch(action)
    assert result.success
    assert "hello" in result.stdout


def test_unknown_tool_returns_error():
    dispatcher = ToolDispatcher()
    action = Action(tool="nonexistent", args={}, thought="")
    result = dispatcher.dispatch(action)
    assert not result.success
    assert "未注册" in result.stderr or "unknown" in result.stderr.lower()


def test_read_nonexistent_file():
    dispatcher = ToolDispatcher()
    dispatcher.register("read_file", ReadFileTool())
    action = Action(
        tool="read_file",
        args={"path": "/nonexistent/path/file.txt"},
        thought="",
    )
    result = dispatcher.dispatch(action)
    assert not result.success


def test_dispatch_exception_caught():
    """工具内部抛异常时 dispatcher 捕获并返回错误结果。"""

    class BoomTool(ReadFileTool):
        def execute(self, action: Action) -> ToolResult:
            raise RuntimeError("boom")

    dispatcher = ToolDispatcher()
    dispatcher.register("read_file", BoomTool())
    action = Action(tool="read_file", args={"path": "x"}, thought="")
    result = dispatcher.dispatch(action)
    assert not result.success
    assert "boom" in result.stderr


@contextlib.contextmanager
def _tmp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp
