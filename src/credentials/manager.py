"""凭据管理：OS 钥匙串为主，环境变量为备选。

不将 key 写入代码或日志。get() 返回值仅供 LLMClient 内部使用。
"""

from __future__ import annotations

import contextlib
import getpass
import os

import keyring
from dotenv import load_dotenv


class CredentialManager:
    """凭据安全存储：OS 钥匙串为主，环境变量为备选。

    优先级：钥匙串 > OPENAI_API_KEY > LLM_API_KEY > .env 文件。
    不将 key 写入代码或日志。is_configured() 不回显明文。
    """

    SERVICE_NAME = "njuse-coding-agent"
    KEY_NAME = "api_key"

    def __init__(self, service_name: str = SERVICE_NAME) -> None:
        self._service_name = service_name
        self._load_dotenv()

    def _load_dotenv(self) -> None:
        """尝试从 .env 文件加载环境变量。"""
        load_dotenv()

    def store(self, api_key: str) -> None:
        """存储 API key 到 OS 钥匙串。"""
        keyring.set_password(self._service_name, self.KEY_NAME, api_key)

    def is_configured(self) -> bool:
        """检查是否已配置，返回 bool，不回显明文。"""
        if keyring.get_password(self._service_name, self.KEY_NAME):
            return True
        return bool(
            os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
        )

    def get(self) -> str | None:
        """获取 API key（仅供内部使用，返回值禁止进入日志/事件）。"""
        key = keyring.get_password(self._service_name, self.KEY_NAME)
        if key:
            return key
        return os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")

    def update(self, new_key: str) -> None:
        """更新 API key。"""
        self.store(new_key)

    def clear(self) -> None:
        """清除钥匙串中的 API key。"""
        with contextlib.suppress(keyring.errors.PasswordDeleteError):
            keyring.delete_password(self._service_name, self.KEY_NAME)

    def interactive_setup(self) -> str | None:
        """首次运行引导：getpass 隐藏输入，确认后存储。

        返回值：
        - None：已配置或用户取消
        - "stored"：成功存储
        """
        if self.is_configured():
            return None
        key = getpass.getpass("请输入 API key（输入不可见）: ")
        if not key:
            return None
        self.store(key)
        return "stored"

    def get_api_key(self) -> str:
        """获取 API key，未配置时抛 RuntimeError。"""
        key = self.get()
        if not key:
            raise RuntimeError(
                "未找到 API key，请通过 interactive_setup() 配置"
                "或设置 OPENAI_API_KEY / LLM_API_KEY 环境变量",
            )
        return key

    def get_base_url(self) -> str:
        """获取 base URL。"""
        return os.environ.get("OPENAI_BASE_URL", "https://api.njusehub.ai/v1")

    def get_model(self) -> str:
        """获取模型名。"""
        return os.environ.get("LLM_MODEL", "njusehub/glm-5.2")
