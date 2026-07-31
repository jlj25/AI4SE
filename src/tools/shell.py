"""Shell 命令工具。"""

from __future__ import annotations

import subprocess

from src.tools.base import Tool
from src.types import Action, ToolResult


class ShellTool(Tool):
    """执行 shell 命令，捕获 stdout/stderr。"""

    def execute(self, action: Action) -> ToolResult:
        command = action.args["command"]
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            success = proc.returncode == 0
            return ToolResult(
                success=success,
                stdout=proc.stdout,
                stderr=proc.stderr if not success else "",
                exit_code=proc.returncode,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, stderr="命令超时（30s）", exit_code=124)
        except Exception as e:
            return ToolResult(success=False, stderr=str(e), exit_code=1)
