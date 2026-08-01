## Task 12: ActionParser 动作解析器

**Files:**
- Create: `src/parser/__init__.py`, `src/parser/action_parser.py`
- Test: `tests/parser/__init__.py`, `tests/parser/test_action_parser.py`

**Interfaces:**
- Consumes: LLM 返回的文本（含 ```tool_code 代码块）
- Produces: `ActionParser.parse(text) -> list[Action]`

- [ ] **Step 1: 写失败测试**

```python
# tests/parser/__init__.py
```

```python
# tests/parser/test_action_parser.py
"""ActionParser 单测：验证从 LLM 输出中解析动作。"""
from src.parser.action_parser import ActionParser
from src.types import Action


def test_parse_single_action():
    text = '''我来读取文件：

```tool_code
{"tool": "read_file", "args": {"path": "src/main.py"}, "thought": "查看主文件"}
```'''
    actions = ActionParser().parse(text)
    assert len(actions) == 1
    assert actions[0].tool == "read_file"
    assert actions[0].args["path"] == "src/main.py"
    assert actions[0].thought == "查看主文件"


def test_parse_multiple_actions():
    text = '''```tool_code
{"tool": "read_file", "args": {"path": "a.py"}, "thought": "读a"}
```
中间文字
```tool_code
{"tool": "run_shell", "args": {"command": "ls"}, "thought": "列目录"}
```'''
    actions = ActionParser().parse(text)
    assert len(actions) == 2
    assert actions[0].tool == "read_file"
    assert actions[1].tool == "run_shell"


def test_parse_no_action():
    text = "这是纯文本回复，没有动作。"
    actions = ActionParser().parse(text)
    assert actions == []


def test_parse_malformed_json_skipped():
    text = '''```tool_code
{invalid json}
```'''
    actions = ActionParser().parse(text)
    assert actions == []


def test_parse_missing_fields():
    text = '''```tool_code
{"tool": "read_file"}
```'''
    actions = ActionParser().parse(text)
    assert len(actions) == 1
    assert actions[0].tool == "read_file"
    assert actions[0].args == {}
    assert actions[0].thought == ""
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/parser/test_action_parser.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 ActionParser**

```python
# src/parser/__init__.py
"""解析子包。"""
```

```python
# src/parser/action_parser.py
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
```

- [ ] **Step 4: 运行测试验证通过 + lint + 提交**

```bash
uv run pytest tests/parser/test_action_parser.py -v
uv run ruff check src/parser/ tests/parser/ && uv run mypy src/parser/
git add src/parser/ tests/parser/
git commit -m "feat: 动作解析器 ActionParser（tool_code 代码块提取 + JSON 解析）"
```

---