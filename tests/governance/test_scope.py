"""ScopeFence 单测：验证范围围栏的路径检查与穿越攻击防御。"""

from pathlib import Path

from src.governance.scope import ScopeCheckResult, ScopeFence
from src.types import Action


def test_allowed_path():
    fence = ScopeFence(
        allowed_dirs=[Path("./src"), Path("./tests")], protected_patterns=[".git/", ".env"]
    )
    action = Action(tool="write_file", args={"path": "src/main.py", "content": "x"}, thought="")
    assert fence.check(action) == ScopeCheckResult.ALLOWED


def test_out_of_scope_path():
    fence = ScopeFence(allowed_dirs=[Path("./src")], protected_patterns=[])
    action = Action(tool="write_file", args={"path": "/etc/passwd", "content": "x"}, thought="")
    assert fence.check(action) == ScopeCheckResult.OUT_OF_SCOPE


def test_protected_path_git():
    fence = ScopeFence(allowed_dirs=[Path("./")], protected_patterns=[".git/"])
    action = Action(tool="write_file", args={"path": ".git/config", "content": "x"}, thought="")
    assert fence.check(action) == ScopeCheckResult.PROTECTED


def test_protected_path_env():
    fence = ScopeFence(allowed_dirs=[Path("./")], protected_patterns=[".env"])
    action = Action(tool="read_file", args={"path": ".env"}, thought="")
    assert fence.check(action) == ScopeCheckResult.PROTECTED


def test_path_traversal_dotdot():
    """路径穿越攻击：用 .. 绕过范围。"""
    fence = ScopeFence(allowed_dirs=[Path("./src")], protected_patterns=[])
    action = Action(
        tool="write_file", args={"path": "src/../../../etc/passwd", "content": "x"}, thought=""
    )
    assert fence.check(action) == ScopeCheckResult.OUT_OF_SCOPE


def test_shell_command_with_protected_path():
    """shell 命令涉及受保护路径时也检查。"""
    fence = ScopeFence(allowed_dirs=[Path("./src")], protected_patterns=[".git/"])
    action = Action(tool="run_shell", args={"command": "cat .git/config"}, thought="")
    assert fence.check(action) == ScopeCheckResult.PROTECTED


def test_shell_command_safe():
    fence = ScopeFence(allowed_dirs=[Path("./src")], protected_patterns=[".git/"])
    action = Action(tool="run_shell", args={"command": "ls -la"}, thought="")
    assert fence.check(action) == ScopeCheckResult.ALLOWED
