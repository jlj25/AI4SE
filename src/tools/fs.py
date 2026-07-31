"""文件系统工具：读、写、列目录。"""

from __future__ import annotations

from pathlib import Path

from src.tools.base import Tool
from src.types import Action, ToolResult


class ReadFileTool(Tool):
    """读取文件内容。"""

    def execute(self, action: Action) -> ToolResult:
        path = Path(action.args["path"])
        try:
            content = path.read_text(encoding="utf-8")
            return ToolResult(success=True, stdout=content)
        except FileNotFoundError:
            return ToolResult(success=False, stderr=f"文件不存在: {path}", exit_code=1)
        except Exception as e:
            return ToolResult(success=False, stderr=str(e), exit_code=1)


class WriteFileTool(Tool):
    """写入文件内容。"""

    def execute(self, action: Action) -> ToolResult:
        path = Path(action.args["path"])
        content = action.args["content"]
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return ToolResult(success=True, stdout=f"已写入 {path}")
        except Exception as e:
            return ToolResult(success=False, stderr=str(e), exit_code=1)


class ListDirTool(Tool):
    """列出目录内容。"""

    def execute(self, action: Action) -> ToolResult:
        path = Path(action.args["path"])
        try:
            entries = [f.name for f in path.iterdir()]
            return ToolResult(success=True, stdout="\n".join(entries))
        except Exception as e:
            return ToolResult(success=False, stderr=str(e), exit_code=1)
