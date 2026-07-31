"""凭据管理：从环境变量安全获取 API key，不硬编码。"""

from __future__ import annotations

import os

from dotenv import load_dotenv


class CredentialManager:
    """凭据管理器，从环境变量读取 API key 和 base URL。

    优先级：OPENAI_API_KEY > LLM_API_KEY > .env 文件。
    不将 key 写入代码或日志。
    """

    def __init__(self) -> None:
        self._load_dotenv()

    def _load_dotenv(self) -> None:
        """尝试从 .env 文件加载。"""
        load_dotenv()

    def get_api_key(self) -> str:
        """获取 API key。"""
        key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
        if not key:
            raise RuntimeError(
                "未找到 API key，请设置 OPENAI_API_KEY 或 LLM_API_KEY 环境变量",
            )
        return key

    def get_base_url(self) -> str:
        """获取 base URL。"""
        return os.environ.get("OPENAI_BASE_URL", "https://api.njusehub.ai/v1")

    def get_model(self) -> str:
        """获取模型名。"""
        return os.environ.get("LLM_MODEL", "njusehub/glm-5.2")
