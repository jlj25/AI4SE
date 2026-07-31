"""危险分类学：对动作进行风险分级，代码拦截而非提示词。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from src.config.loader import DangerRule
from src.types import Action


class DangerLevel(Enum):
    """风险等级。"""

    SAFE = "safe"
    WARNING = "warning"
    DANGEROUS = "dangerous"


_LEVEL_PRIORITY = {
    DangerLevel.SAFE: 0,
    DangerLevel.WARNING: 1,
    DangerLevel.DANGEROUS: 2,
}


@dataclass
class Classification:
    """危险分类结果。"""

    level: DangerLevel
    matched_rule: str | None
    reason: str


class DangerClassifier:
    """对通过范围围栏的动作进行风险分级。

    遍历规则做命令模式匹配（正则），取最高风险等级。
    无命中则默认 SAFE。这是确定性代码，无需 LLM。
    """

    def __init__(self, rules: list[DangerRule]) -> None:
        self._rules = rules

    def classify(self, action: Action) -> Classification:
        """对动作进行危险分类。"""
        if action.tool != "run_shell":
            return Classification(level=DangerLevel.SAFE, matched_rule=None, reason="非 shell 命令")
        command = action.args.get("command", "")
        best_level = DangerLevel.SAFE
        best_rule: str | None = None
        best_reason = "无危险规则命中"
        for rule in self._rules:
            if re.search(rule.pattern, command):
                rule_level = DangerLevel(rule.level)
                if _LEVEL_PRIORITY[rule_level] > _LEVEL_PRIORITY[best_level]:
                    best_level = rule_level
                    best_rule = rule.name
                    best_reason = rule.description
        return Classification(level=best_level, matched_rule=best_rule, reason=best_reason)
