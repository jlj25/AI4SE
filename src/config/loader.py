"""声明式 YAML 配置加载器。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ALLOWED_LEVELS: set[str] = {"dangerous", "warning", "safe"}


class ConfigError(Exception):
    """配置加载或校验错误。"""


@dataclass
class ScopeConfig:
    """范围围栏配置。"""

    allowed_dirs: list[str] = field(default_factory=lambda: ["./"])
    protected_patterns: list[str] = field(default_factory=list)


@dataclass
class DangerRule:
    """危险规则。"""

    name: str
    pattern: str
    level: str
    description: str = ""


@dataclass
class LLMConfig:
    """LLM 供应商配置。"""

    model: str = "glm-5.2"
    base_url: str = "https://njusehub.info/v1"


@dataclass
class AgentConfig:
    """agent 完整配置。"""

    max_steps: int = 50
    scope: ScopeConfig = field(default_factory=ScopeConfig)
    danger_rules: list[DangerRule] = field(default_factory=list)
    llm: LLMConfig = field(default_factory=LLMConfig)


def _section_kwargs(section: Any, allowed_keys: set[str]) -> dict[str, Any]:
    """从 YAML 段落提取属于允许键的字段；None/空段落返回空字典，交由 dataclass 默认值兜底。"""
    if not section:
        return {}
    return {k: v for k, v in section.items() if k in allowed_keys}


def _build_danger_rules(rules_section: Any) -> list[DangerRule]:
    """构建危险规则列表，校验类型、必填字段与 level 取值。"""
    if not rules_section:
        return []
    if not isinstance(rules_section, list):
        raise ConfigError(f"danger_rules 必须是列表，实际: {type(rules_section).__name__}")
    rules: list[DangerRule] = []
    for index, rule in enumerate(rules_section):
        if not isinstance(rule, dict):
            raise ConfigError(f"danger_rules[{index}] 必须是映射，实际: {type(rule).__name__}")
        for required in ("name", "pattern", "level"):
            if required not in rule:
                raise ConfigError(f"danger_rules[{index}] 缺少必填字段: {required}")
        level = rule["level"]
        if level not in ALLOWED_LEVELS:
            raise ConfigError(
                f"danger_rules[{index}].level 非法: {level!r}，允许值: {sorted(ALLOWED_LEVELS)}"
            )
        rules.append(
            DangerRule(**_section_kwargs(rule, {"name", "pattern", "level", "description"}))
        )
    return rules


class ConfigLoader:
    """从 YAML 文件加载并校验配置。"""

    @staticmethod
    def load(path: Path) -> AgentConfig:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        scope = ScopeConfig(
            **_section_kwargs(raw.get("scope"), {"allowed_dirs", "protected_patterns"})
        )
        llm = LLMConfig(**_section_kwargs(raw.get("llm"), {"model", "base_url"}))
        danger_rules = _build_danger_rules(raw.get("danger_rules"))
        agent_kwargs = _section_kwargs(raw.get("agent"), {"max_steps"})
        return AgentConfig(**agent_kwargs, scope=scope, danger_rules=danger_rules, llm=llm)
