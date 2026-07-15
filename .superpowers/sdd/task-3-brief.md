## Task 3: 配置加载器

**Files:**
- Create: `src/config/__init__.py`, `src/config/loader.py`, `config.yaml`
- Test: `tests/config/__init__.py`, `tests/config/test_loader.py`

**Interfaces:**
- Produces: `AgentConfig`, `ScopeConfig`, `DangerRule`, `LLMConfig`, `ConfigLoader.load(path) -> AgentConfig`

- [ ] **Step 1: 写失败测试**

```python
# tests/config/__init__.py
```

```python
# tests/config/test_loader.py
"""ConfigLoader 单测：验证 YAML 加载与字段校验。"""
from pathlib import Path
from src.config.loader import AgentConfig, ScopeConfig, DangerRule, LLMConfig, ConfigLoader


def test_load_full_config(tmp_path: Path):
    yaml_content = """
agent:
  max_steps: 30
scope:
  allowed_dirs:
    - "./src"
    - "./tests"
  protected_patterns:
    - ".git/"
    - ".env"
danger_rules:
  - name: force_delete
    pattern: 'rm\\s+-rf'
    level: dangerous
    description: 递归强制删除
  - name: install_pkg
    pattern: 'pip\\s+install'
    level: warning
    description: 安装包
llm:
  model: "glm-5.2"
  base_url: "https://njusehub.info/v1"
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content, encoding="utf-8")
    config = ConfigLoader.load(config_file)
    assert config.max_steps == 30
    assert config.scope.allowed_dirs == ["./src", "./tests"]
    assert config.scope.protected_patterns == [".git/", ".env"]
    assert len(config.danger_rules) == 2
    assert config.danger_rules[0].name == "force_delete"
    assert config.danger_rules[0].level == "dangerous"
    assert config.llm.model == "glm-5.2"


def test_load_defaults_when_fields_missing(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("agent:\n  max_steps: 10\n", encoding="utf-8")
    config = ConfigLoader.load(config_file)
    assert config.max_steps == 10
    assert config.scope.allowed_dirs == ["./"]
    assert config.danger_rules == []


def test_danger_rule_creation():
    rule = DangerRule(name="test", pattern="rm", level="dangerous", description="测试")
    assert rule.name == "test"
    assert rule.level == "dangerous"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/config/test_loader.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 ConfigLoader**

```python
# src/config/__init__.py
"""配置子包。"""
```

```python
# src/config/loader.py
"""声明式 YAML 配置加载器。"""
from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path


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
                name=r["name"], pattern=r["pattern"],
                level=r["level"], description=r.get("description", ""),
            )
            for r in rules_section
        ]
        llm = LLMConfig(
            model=llm_section.get("model", "glm-5.2"),
            base_url=llm_section.get("base_url", "https://njusehub.info/v1"),
        )
        return AgentConfig(
            max_steps=agent_section.get("max_steps", 50),
            scope=scope, danger_rules=danger_rules, llm=llm,
        )
```

- [ ] **Step 4: 创建默认 config.yaml**

```yaml
# config.yaml
agent:
  max_steps: 50
scope:
  allowed_dirs: ["./src", "./tests"]
  protected_patterns: [".git/", ".env", "*.key"]
danger_rules:
  - name: recursive_force_delete_root
    pattern: 'rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?-rf?\s+/'
    level: dangerous
    description: 递归强制删除根目录
  - name: force_push
    pattern: 'git\s+push.*--force'
    level: dangerous
    description: 强制推送覆盖远程历史
  - name: curl_pipe_bash
    pattern: 'curl.*\|\s*(ba)?sh'
    level: dangerous
    description: 远程脚本直接执行
  - name: install_package
    pattern: '(pip|npm|yarn)\s+install'
    level: warning
    description: 安装软件包
llm:
  model: "glm-5.2"
  base_url: "https://njusehub.info/v1"
```

- [ ] **Step 5: 运行测试验证通过 + lint + 提交**

```bash
uv run pytest tests/config/test_loader.py -v
uv run ruff check src/config/ tests/config/ && uv run mypy src/config/
git add src/config/ tests/config/ config.yaml
git commit -m "feat: 配置加载器（YAML→强类型 AgentConfig）+ 默认 config.yaml"
```

---