"""范围围栏：检查动作目标是否在允许范围内，硬拦截不可审批放行。"""
from __future__ import annotations

import fnmatch
from enum import Enum
from pathlib import Path

from src.types import Action


class ScopeCheckResult(Enum):
    """范围围栏检查结果。"""

    ALLOWED = "allowed"
    OUT_OF_SCOPE = "out_of_scope"
    PROTECTED = "protected"


class ScopeFence:
    """范围围栏，硬拦截超出允许目录或触碰受保护路径的动作。

    PROTECTED 和 OUT_OF_SCOPE 均直接阻断，不进 HITL——绝对边界。
    路径解析处理 .. 、绝对/相对路径等绕过手段。
    """

    def __init__(self, allowed_dirs: list[Path], protected_patterns: list[str]) -> None:
        self._allowed_dirs = [d.resolve() for d in allowed_dirs]
        self._protected_patterns = protected_patterns

    def check(self, action: Action) -> ScopeCheckResult:
        """检查动作是否在允许范围内。"""
        paths = self._extract_paths(action)
        for path_str in paths:
            result = self._check_path(path_str)
            if result != ScopeCheckResult.ALLOWED:
                return result
        return ScopeCheckResult.ALLOWED

    def _extract_paths(self, action: Action) -> list[str]:
        """从动作中提取涉及的文件路径。"""
        paths: list[str] = []
        if action.tool in ("read_file", "write_file", "list_dir"):
            if "path" in action.args:
                paths.append(action.args["path"])
        elif action.tool == "run_shell":
            cmd = action.args.get("command", "")
            paths.extend(self._extract_paths_from_shell(cmd))
        return paths

    def _extract_paths_from_shell(self, command: str) -> list[str]:
        """从 shell 命令中提取文件路径参数（简化版）。"""
        tokens = command.split()
        paths: list[str] = []
        for token in tokens:
            if ("/" in token or "." in token) and not token.startswith("-"):
                paths.append(token)
        return paths

    def _check_path(self, path_str: str) -> ScopeCheckResult:
        """检查单个路径是否在范围内且不触碰受保护路径。"""
        path = Path(path_str)
        for pattern in self._protected_patterns:
            clean = pattern.rstrip("/")
            if fnmatch.fnmatch(path.name, clean) or fnmatch.fnmatch(path_str, pattern):
                return ScopeCheckResult.PROTECTED
            if clean in path.parts:
                return ScopeCheckResult.PROTECTED
        resolved = path.resolve()
        for allowed_dir in self._allowed_dirs:
            try:
                resolved.relative_to(allowed_dir)
                return ScopeCheckResult.ALLOWED
            except ValueError:
                continue
        return ScopeCheckResult.OUT_OF_SCOPE
