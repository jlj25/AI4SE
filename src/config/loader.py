"""声明式 YAML 配置加载器。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


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


class ConfigLoader:
    """从 YAML 文件加载并校验配置。"""

    @staticmethod
    def load(path: Path) -> AgentConfig:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        agent_section = raw.get("agent", {})
        scope_section = raw.get("scope", {})
        rules_section = raw.get("danger_rules", [])
        llm_section = raw.get("llm", {})
        scope = ScopeConfig(
            allowed_dirs=scope_section.get("allowed_dirs", ["./"]),
            protected_patterns=scope_section.get("protected_patterns", []),
        )
        danger_rules = [
            DangerRule(
                name=r["name"],
                pattern=r["pattern"],
                level=r["level"],
                description=r.get("description", ""),
            )
            for r in rules_section
        ]
        llm = LLMConfig(
            model=llm_section.get("model", "glm-5.2"),
            base_url=llm_section.get("base_url", "https://njusehub.info/v1"),
        )
        return AgentConfig(
            max_steps=agent_section.get("max_steps", 50),
            scope=scope,
            danger_rules=danger_rules,
            llm=llm,
        )
