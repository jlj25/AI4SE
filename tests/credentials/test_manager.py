"""CredentialManager 单测：验证凭据安全存储与检索。

测试覆盖：
- OS 钥匙串存储/读取/更新/清除
- is_configured 不回显明文
- 环境变量回退
- interactive_setup 首次引导
- get_api_key 未配置时抛异常
"""

import keyring

from src.credentials.manager import CredentialManager

# --- 测试辅助：用内存 dict 替代真实 OS 钥匙串 ---


def _mock_keyring(monkeypatch):
    """用内存 dict 替代真实 OS 钥匙串，避免污染系统。"""
    store: dict[str, str] = {}

    def _set(service: str, username: str, password: str) -> None:
        store[f"{service}:{username}"] = password

    def _get(service: str, username: str) -> str | None:
        return store.get(f"{service}:{username}")

    def _delete(service: str, username: str) -> None:
        key = f"{service}:{username}"
        if key in store:
            del store[key]
        else:
            raise keyring.errors.PasswordDeleteError

    monkeypatch.setattr(keyring, "set_password", _set)
    monkeypatch.setattr(keyring, "get_password", _get)
    monkeypatch.setattr(keyring, "delete_password", _delete)


# --- 钥匙串存储/读取 ---


def test_store_and_get_keyring(monkeypatch):
    """store 写入钥匙串后，get 能读回。"""
    _mock_keyring(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    mgr = CredentialManager()
    mgr.store("sk-test-keyring-123")
    assert mgr.get() == "sk-test-keyring-123"


def test_is_configured_true_keyring(monkeypatch):
    """钥匙串有 key → is_configured 返回 True，不回显明文。"""
    _mock_keyring(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    mgr = CredentialManager()
    mgr.store("sk-secret-key")
    assert mgr.is_configured() is True
    assert mgr.is_configured() is not str  # 返回 bool 不是 str


def test_is_configured_true_env(monkeypatch):
    """环境变量有 key → is_configured 返回 True。"""
    _mock_keyring(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")
    mgr = CredentialManager()
    assert mgr.is_configured() is True


def test_is_configured_false(monkeypatch):
    """无 key → is_configured 返回 False。"""
    _mock_keyring(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    mgr = CredentialManager()
    assert mgr.is_configured() is False


def test_get_returns_none_if_not_configured(monkeypatch):
    """未配置 → get 返回 None。"""
    _mock_keyring(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    mgr = CredentialManager()
    assert mgr.get() is None


def test_clear_removes_key(monkeypatch):
    """clear 后钥匙串中无 key。"""
    _mock_keyring(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    mgr = CredentialManager()
    mgr.store("sk-to-clear")
    assert mgr.is_configured() is True
    mgr.clear()
    assert mgr.is_configured() is False
    assert mgr.get() is None


def test_clear_when_not_configured_no_error(monkeypatch):
    """未配置时 clear 不报错。"""
    _mock_keyring(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    mgr = CredentialManager()
    mgr.clear()  # 不应抛异常


def test_update_changes_key(monkeypatch):
    """update 替换旧 key。"""
    _mock_keyring(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    mgr = CredentialManager()
    mgr.store("sk-old-key")
    mgr.update("sk-new-key")
    assert mgr.get() == "sk-new-key"
    assert mgr.get() != "sk-old-key"


def test_keyring_takes_priority_over_env(monkeypatch):
    """钥匙串有 key 时优先于环境变量。"""
    _mock_keyring(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")

    mgr = CredentialManager()
    mgr.store("sk-keyring-key")
    assert mgr.get() == "sk-keyring-key"


def test_env_fallback_when_keyring_empty(monkeypatch):
    """钥匙串无 key 时回退到环境变量。"""
    _mock_keyring(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-fallback")

    mgr = CredentialManager()
    assert mgr.get() == "sk-env-fallback"


def test_get_api_key_raises_if_not_configured(monkeypatch):
    """未配置时 get_api_key 抛 RuntimeError。"""
    _mock_keyring(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    mgr = CredentialManager()
    try:
        mgr.get_api_key()
        msg = "应抛出异常"
        raise AssertionError(msg)
    except (ValueError, RuntimeError):
        pass


def test_interactive_setup_skips_if_configured(monkeypatch):
    """已配置时 interactive_setup 跳过。"""
    _mock_keyring(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    mgr = CredentialManager()
    mgr.store("sk-existing")
    result = mgr.interactive_setup()
    assert result is None  # 已配置，跳过


def test_interactive_setup_stores_key(monkeypatch):
    """interactive_setup 通过 getpass 录入并存储 key。"""
    _mock_keyring(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    import getpass

    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "sk-input-key")

    mgr = CredentialManager()
    result = mgr.interactive_setup()
    assert result == "stored"
    assert mgr.get() == "sk-input-key"


def test_interactive_setup_cancelled(monkeypatch):
    """用户输入空串时取消。"""
    _mock_keyring(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    import getpass

    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "")

    mgr = CredentialManager()
    result = mgr.interactive_setup()
    assert result is None
    assert not mgr.is_configured()


# --- 保留原有环境变量测试 ---


def test_get_base_url_default():
    mgr = CredentialManager()
    assert "njusehub" in mgr.get_base_url() or "openai" in mgr.get_base_url().lower()


def test_get_base_url_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://custom.api.com/v1")
    mgr = CredentialManager()
    assert mgr.get_base_url() == "https://custom.api.com/v1"


def test_get_model_default():
    mgr = CredentialManager()
    assert "glm" in mgr.get_model().lower()


def test_get_model_from_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "custom-model")
    mgr = CredentialManager()
    assert mgr.get_model() == "custom-model"


def test_llm_api_key_fallback(monkeypatch):
    """OPENAI_API_KEY 不存在时回退到 LLM_API_KEY。"""
    _mock_keyring(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "sk-fallback-key")
    mgr = CredentialManager()
    assert mgr.get_api_key() == "sk-fallback-key"
