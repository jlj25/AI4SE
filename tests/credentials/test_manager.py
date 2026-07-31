"""CredentialManager 单测：验证凭据安全获取。"""

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
        msg = "应抛出异常"
        raise AssertionError(msg)
    except (ValueError, RuntimeError):
        pass


def test_get_model_default():
    mgr = CredentialManager()
    assert "glm" in mgr.get_model().lower()


def test_get_model_from_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "custom-model")
    mgr = CredentialManager()
    assert mgr.get_model() == "custom-model"


def test_llm_api_key_fallback(monkeypatch):
    """OPENAI_API_KEY 不存在时回退到 LLM_API_KEY。"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "sk-fallback-key")
    mgr = CredentialManager()
    assert mgr.get_api_key() == "sk-fallback-key"
