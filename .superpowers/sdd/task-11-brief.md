## Task 11: 凭据管理 CredentialManager

**Files:**
- Create: `src/credentials/__init__.py`, `src/credentials/manager.py`
- Test: `tests/credentials/__init__.py`, `tests/credentials/test_manager.py`

**Interfaces:**
- Consumes: 环境变量 `OPENAI_API_KEY` 或 `.env` 文件
- Produces: `CredentialManager`（`get_api_key() -> str`, `get_base_url() -> str`）

- [ ] **Step 1: 写失败测试**

```python
# tests/credentials/__init__.py
```

```python
# tests/credentials/test_manager.py
"""CredentialManager 单测：验证凭据安全获取。"""
import os
from src.credentials.manager import CredentialManager


def test_get_api_key_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")
    mgr = CredentialManager()
    assert mgr.get_api_key() == "sk-test-key-123"


def test_get_base_url_default():
    mgr = CredentialManager()
    assert "njusehub" in mgr.get_base_url() or "openai" in mgr.get_base_url().lower()


def test_get_base_url_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://custom.api.com/v1")
    mgr = CredentialManager()
    assert mgr.get_base_url() == "https://custom.api.com/v1"


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    mgr = CredentialManager()
    try:
        mgr.get_api_key()
        assert False, "应抛出异常"
    except (ValueError, RuntimeError):
        pass
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/credentials/test_manager.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 CredentialManager**

```python
# src/credentials/__init__.py
"""凭据子包。"""
```

```python
# src/credentials/manager.py
"""凭据管理：从环境变量安全获取 API key，不硬编码。"""
from __future__ import annotations

import os


class CredentialManager:
    """凭据管理器，从环境变量读取 API key 和 base URL。

    优先级：OPENAI_API_KEY > LLM_API_KEY > .env 文件。
    不将 key 写入代码或日志。
    """

    def __init__(self) -> None:
        self._load_dotenv()

    def _load_dotenv(self) -> None:
        """尝试从 .env 文件加载（如果 python-dotenv 可用）。"""
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

    def get_api_key(self) -> str:
        """获取 API key。"""
        key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
        if not key:
            raise RuntimeError(
                "未找到 API key，请设置 OPENAI_API_KEY 或 LLM_API_KEY 环境变量"
            )
        return key

    def get_base_url(self) -> str:
        """获取 base URL。"""
        return os.environ.get(
            "OPENAI_BASE_URL", "https://api.njusehub.ai/v1"
        )

    def get_model(self) -> str:
        """获取模型名。"""
        return os.environ.get("LLM_MODEL", "njusehub/glm-5.2")
```

- [ ] **Step 4: 运行测试验证通过 + lint + 提交**

```bash
uv run pytest tests/credentials/test_manager.py -v
uv run ruff check src/credentials/ tests/credentials/ && uv run mypy src/credentials/
git add src/credentials/ tests/credentials/
git commit -m "feat: 凭据管理 CredentialManager（环境变量读取 + .env 支持）"
```

---