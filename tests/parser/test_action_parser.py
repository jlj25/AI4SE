"""ActionParser 单测：验证从 LLM 输出中解析动作。"""

from src.parser.action_parser import ActionParser
from src.types import Action


def test_parse_single_action():
    text = """我来读取文件：

```tool_code
{"tool": "read_file", "args": {"path": "src/main.py"}, "thought": "查看主文件"}
```"""
    actions = ActionParser().parse(text)
    assert len(actions) == 1
    assert actions[0].tool == "read_file"
    assert actions[0].args["path"] == "src/main.py"
    assert actions[0].thought == "查看主文件"


def test_parse_multiple_actions():
    text = """```tool_code
{"tool": "read_file", "args": {"path": "a.py"}, "thought": "读a"}
```
中间文字
```tool_code
{"tool": "run_shell", "args": {"command": "ls"}, "thought": "列目录"}
```"""
    actions = ActionParser().parse(text)
    assert len(actions) == 2
    assert actions[0].tool == "read_file"
    assert actions[1].tool == "run_shell"


def test_parse_no_action():
    text = "这是纯文本回复，没有动作。"
    actions = ActionParser().parse(text)
    assert actions == []


def test_parse_malformed_json_skipped():
    text = """```tool_code
{invalid json}
```"""
    actions = ActionParser().parse(text)
    assert actions == []


def test_parse_missing_fields():
    text = """```tool_code
{"tool": "read_file"}
```"""
    actions = ActionParser().parse(text)
    assert len(actions) == 1
    assert actions[0].tool == "read_file"
    assert actions[0].args == {}
    assert actions[0].thought == ""


def test_parse_empty_tool_skipped():
    """tool 字段为空时跳过。"""
    text = """```tool_code
{"tool": "", "args": {}, "thought": ""}
```"""
    actions = ActionParser().parse(text)
    assert actions == []


def test_parse_non_dict_skipped():
    """JSON 解析为非 dict 时跳过。"""
    text = """```tool_code
["not", "a", "dict"]
```"""
    actions = ActionParser().parse(text)
    assert actions == []


def test_parse_returns_action_instances():
    """解析结果为 Action 实例。"""
    text = """```tool_code
{"tool": "write_file", "args": {"path": "x", "content": "y"}, "thought": "写"}
```"""
    actions = ActionParser().parse(text)
    assert len(actions) == 1
    assert isinstance(actions[0], Action)
