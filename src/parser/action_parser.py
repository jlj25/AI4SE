"""动作解析器：从 LLM 输出文本中提取结构化动作。"""

from __future__ import annotations

import json
import re

from src.types import Action


class ActionParser:
    """动作解析器，从 LLM 输出中提取 ```tool_code 代码块并解析为 Action。

    使用正则提取代码块，JSON 解析内容，容错处理缺失字段。
    确定性代码，无 LLM 依赖。
    """

    _PATTERN = re.compile(r"```tool_code\s*\n(.*?)\n```", re.DOTALL)

    def parse(self, text: str) -> list[Action]:
        """从文本中解析所有动作。"""
        actions: list[Action] = []
        for match in self._PATTERN.finditer(text):
            block = match.group(1).strip()
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            tool = data.get("tool", "")
            if not tool:
                continue
            args = data.get("args", {})
            thought = data.get("thought", "")
            actions.append(Action(tool=tool, args=args, thought=thought))
        return actions
