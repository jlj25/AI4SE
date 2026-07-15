"""ConfigLoader 单测：验证 YAML 加载与字段校验。"""

from pathlib import Path

from src.config.loader import ConfigLoader, DangerRule


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
