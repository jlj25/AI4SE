"""DangerClassifier 单测：验证危险命令模式匹配与风险分级。"""

from src.config.loader import DangerRule
from src.governance.classifier import DangerClassifier, DangerLevel
from src.types import Action


def _make_rules() -> list[DangerRule]:
    return [
        DangerRule(
            name="force_delete",
            pattern=r"rm\s+(-\w*\w\w*\s+)?-rf?\s+/",
            level="dangerous",
            description="递归删除",
        ),
        DangerRule(
            name="force_push",
            pattern=r"git\s+push.*--force",
            level="dangerous",
            description="强制推送",
        ),
        DangerRule(
            name="install_pkg",
            pattern=r"(pip|npm)\s+install",
            level="warning",
            description="安装包",
        ),
    ]


def test_dangerous_rm_rf():
    classifier = DangerClassifier(_make_rules())
    action = Action(tool="run_shell", args={"command": "rm -rf /"}, thought="")
    result = classifier.classify(action)
    assert result.level == DangerLevel.DANGEROUS
    assert result.matched_rule == "force_delete"


def test_dangerous_git_force_push():
    classifier = DangerClassifier(_make_rules())
    action = Action(tool="run_shell", args={"command": "git push --force origin main"}, thought="")
    result = classifier.classify(action)
    assert result.level == DangerLevel.DANGEROUS
    assert result.matched_rule == "force_push"


def test_warning_pip_install():
    classifier = DangerClassifier(_make_rules())
    action = Action(tool="run_shell", args={"command": "pip install requests"}, thought="")
    result = classifier.classify(action)
    assert result.level == DangerLevel.WARNING
    assert result.matched_rule == "install_pkg"


def test_safe_command():
    classifier = DangerClassifier(_make_rules())
    action = Action(tool="run_shell", args={"command": "ls -la"}, thought="")
    result = classifier.classify(action)
    assert result.level == DangerLevel.SAFE
    assert result.matched_rule is None


def test_safe_file_read():
    classifier = DangerClassifier(_make_rules())
    action = Action(tool="read_file", args={"path": "src/main.py"}, thought="")
    result = classifier.classify(action)
    assert result.level == DangerLevel.SAFE


def test_highest_level_wins():
    """多条规则命中时取最高风险等级。"""
    rules = [
        DangerRule(name="warn1", pattern=r"rm", level="warning", description=""),
        DangerRule(name="danger1", pattern=r"rm\s+-rf", level="dangerous", description=""),
    ]
    classifier = DangerClassifier(rules)
    action = Action(tool="run_shell", args={"command": "rm -rf /tmp"}, thought="")
    result = classifier.classify(action)
    assert result.level == DangerLevel.DANGEROUS
