"""ConfigLoader 单测：验证 YAML 加载与字段校验。"""

from pathlib import Path

import pytest

from src.config.loader import ConfigError, ConfigLoader, DangerRule

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REPO_CONFIG = REPO_ROOT / "config" / "config.yaml"


def test_load_full_config(tmp_path: Path):
    yaml_content = r"""
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
    pattern: 'rm\s+-rf'
    level: dangerous
    description: 递归强制删除
  - name: install_pkg
    pattern: 'pip\s+install'
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


def test_default_config_loads():
    """仓库默认 config/config.yaml 必须可干净加载且字段合法。"""
    config = ConfigLoader.load(REPO_CONFIG)
    assert config.max_steps > 0
    assert len(config.danger_rules) >= 1
    assert config.llm.model  # 非空字符串


def test_null_sections_use_defaults(tmp_path: Path):
    """各段落为 null 时应优雅回退到默认值，而非抛 AttributeError。"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("agent:\nscope:\nllm:\ndanger_rules:\n", encoding="utf-8")
    config = ConfigLoader.load(config_file)
    assert config.max_steps == 50
    assert config.scope.allowed_dirs == ["./"]
    assert config.scope.protected_patterns == []
    assert config.danger_rules == []
    assert config.llm.model == "glm-5.2"


def test_danger_rule_missing_required_field_raises_config_error(tmp_path: Path):
    """danger_rules 缺少必填字段应抛 ConfigError，而非裸 KeyError。"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        'danger_rules:\n  - pattern: "rm"\n    level: dangerous\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="name"):
        ConfigLoader.load(config_file)


def test_invalid_level_raises_config_error(tmp_path: Path):
    """level 不在允许集合内应抛 ConfigError。"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        'danger_rules:\n  - name: x\n    pattern: "rm"\n    level: bogus\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="level"):
        ConfigLoader.load(config_file)


def test_danger_rules_not_list_raises_config_error(tmp_path: Path):
    """danger_rules 非列表应抛 ConfigError。"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("danger_rules: not-a-list\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        ConfigLoader.load(config_file)
